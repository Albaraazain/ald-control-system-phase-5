# File: src/di/event_bus.py
"""
Production-grade event bus implementation with persistence, replay, and routing.
Implements IEventBus interface for event-driven architecture.
"""
import asyncio
import json
import weakref
from typing import Dict, Any, Optional, List, Callable, TypeVar, Generic, Type, Set
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import uuid
import pickle
import gzip
from pathlib import Path

from ..abstractions.interfaces import IEventBus, ServiceHealth, IDatabaseService
from ..abstractions.events import DomainEvent, EventMetadata, EventType, EVENT_REGISTRY
from src.log_setup import logger

T = TypeVar('T', bound=DomainEvent)

@dataclass
class EventSubscription:
    """Represents an event subscription"""
    subscription_id: str
    event_type: str
    handler: Callable[[DomainEvent], None]
    filters: Dict[str, Any]
    created_at: datetime
    is_async: bool
    max_retries: int = 3
    retry_count: int = 0

@dataclass
class StoredEvent:
    """Represents a stored event in the event store"""
    event_id: str
    event_type: str
    event_data: str  # JSON serialized event data
    metadata: str    # JSON serialized metadata
    stream_id: str
    sequence_number: int
    timestamp: datetime
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

class EventStore:
    """Event store for persisting and retrieving events"""

    def __init__(self, database_service: Optional[IDatabaseService] = None, file_path: Optional[str] = None):
        self.database_service = database_service
        self.file_path = file_path or "events.db"
        self._events: List[StoredEvent] = []
        self._sequence_counter = 0
        self._streams: Dict[str, List[StoredEvent]] = defaultdict(list)

    async def append_event(self, event: DomainEvent, stream_id: str) -> int:
        """Append an event to the event store"""
        try:
            self._sequence_counter += 1

            # Serialize event data
            event_data = json.dumps(asdict(event), default=str)
            metadata_data = json.dumps(asdict(event.metadata), default=str)

            stored_event = StoredEvent(
                event_id=event.event_id,
                event_type=event.__class__.__name__,
                event_data=event_data,
                metadata=metadata_data,
                stream_id=stream_id,
                sequence_number=self._sequence_counter,
                timestamp=event.timestamp,
                correlation_id=event.correlation_id,
                causation_id=event.metadata.causation_id
            )

            # Store in memory
            self._events.append(stored_event)
            self._streams[stream_id].append(stored_event)

            # Persist to database if available
            if self.database_service:
                await self._persist_to_database(stored_event)
            else:
                await self._persist_to_file(stored_event)

            logger.debug(f"Event {event.event_id} appended to stream {stream_id} at sequence {self._sequence_counter}")
            return self._sequence_counter

        except Exception as e:
            logger.error(f"Failed to append event {event.event_id}: {str(e)}")
            raise

    async def _persist_to_database(self, event: StoredEvent):
        """Persist event to database"""
        try:
            query = """
                INSERT INTO event_store (
                    event_id, event_type, event_data, metadata, stream_id,
                    sequence_number, timestamp, correlation_id, causation_id
                ) VALUES (
                    %(event_id)s, %(event_type)s, %(event_data)s, %(metadata)s, %(stream_id)s,
                    %(sequence_number)s, %(timestamp)s, %(correlation_id)s, %(causation_id)s
                )
            """

            params = {
                'event_id': event.event_id,
                'event_type': event.event_type,
                'event_data': event.event_data,
                'metadata': event.metadata,
                'stream_id': event.stream_id,
                'sequence_number': event.sequence_number,
                'timestamp': event.timestamp,
                'correlation_id': event.correlation_id,
                'causation_id': event.causation_id
            }

            await self.database_service.execute_query(query, params)

        except Exception as e:
            logger.error(f"Failed to persist event to database: {str(e)}")
            # Fall back to file storage
            await self._persist_to_file(event)

    async def _persist_to_file(self, event: StoredEvent):
        """Persist event to file as backup"""
        try:
            file_path = Path(self.file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            event_data = {
                'event_id': event.event_id,
                'event_type': event.event_type,
                'event_data': event.event_data,
                'metadata': event.metadata,
                'stream_id': event.stream_id,
                'sequence_number': event.sequence_number,
                'timestamp': event.timestamp.isoformat(),
                'correlation_id': event.correlation_id,
                'causation_id': event.causation_id
            }

            with open(file_path, 'a') as f:
                f.write(json.dumps(event_data) + '\n')

        except Exception as e:
            logger.error(f"Failed to persist event to file: {str(e)}")

    async def get_events(self, stream_id: str, from_sequence: int = 0) -> List[StoredEvent]:
        """Get events from a stream starting from sequence number"""
        events = self._streams.get(stream_id, [])
        return [e for e in events if e.sequence_number >= from_sequence]

    async def get_all_events(self, from_sequence: int = 0) -> List[StoredEvent]:
        """Get all events starting from sequence number"""
        return [e for e in self._events if e.sequence_number >= from_sequence]

    def deserialize_event(self, stored_event: StoredEvent) -> Optional[DomainEvent]:
        """Deserialize a stored event back to domain event"""
        try:
            event_class = EVENT_REGISTRY.get(stored_event.event_type)
            if not event_class:
                logger.warning(f"Unknown event type: {stored_event.event_type}")
                return None

            event_data = json.loads(stored_event.event_data)
            metadata_data = json.loads(stored_event.metadata)

            # Reconstruct metadata
            metadata = EventMetadata(**metadata_data)

            # Reconstruct event
            event_data['metadata'] = metadata
            return event_class(**event_data)

        except Exception as e:
            logger.error(f"Failed to deserialize event {stored_event.event_id}: {str(e)}")
            return None

class AsyncEventBus(IEventBus):
    """
    High-performance async event bus with persistence, replay, and routing capabilities.

    Features:
    - Async event publishing and handling
    - Event persistence and replay
    - Subscription filtering and routing
    - Dead letter queue for failed events
    - Event correlation and causation tracking
    - Performance monitoring
    """

    def __init__(self, event_store: Optional[EventStore] = None, max_retries: int = 3):
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._event_handlers: Dict[str, List[EventSubscription]] = defaultdict(list)
        self._event_store = event_store or EventStore()
        self._max_retries = max_retries
        self._dead_letter_queue: deque = deque(maxlen=1000)
        self._processing_queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'subscriptions_count': 0
        }

    async def start(self):
        """Start the event bus processing"""
        if self._is_running:
            return

        self._is_running = True
        self._processing_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def stop(self):
        """Stop the event bus processing"""
        if not self._is_running:
            return

        self._is_running = False

        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        logger.info("Event bus stopped")

    async def publish(self, event_type: str, data: Dict[str, Any], source: Optional[str] = None) -> bool:
        """
        Publish an event to the bus.

        For domain events, pass the DomainEvent instance in data['event']
        """
        try:
            if 'event' in data and isinstance(data['event'], DomainEvent):
                # Publishing a domain event
                event = data['event']
                if source:
                    event.metadata.source = source
            else:
                # Creating a simple event from data
                from ..abstractions.events import DomainEvent, EventMetadata
                metadata = EventMetadata(
                    event_type=EventType.INTEGRATION,
                    source=source
                )

                # Create a generic event class
                @dataclass
                class GenericEvent(DomainEvent):
                    event_data: Dict[str, Any]

                event = GenericEvent(metadata=metadata, event_data=data)

            # Store the event
            stream_id = event.metadata.aggregate_id or event.metadata.source or "default"
            await self._event_store.append_event(event, stream_id)

            # Queue for processing
            await self._processing_queue.put((event_type, event))

            self._stats['events_published'] += 1
            logger.debug(f"Published event {event_type} with ID {event.event_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {str(e)}")
            self._stats['events_failed'] += 1
            return False

    async def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to events of a specific type"""
        try:
            subscription_id = str(uuid.uuid4())
            is_async = asyncio.iscoroutinefunction(handler)

            subscription = EventSubscription(
                subscription_id=subscription_id,
                event_type=event_type,
                handler=handler,
                filters={},
                created_at=datetime.utcnow(),
                is_async=is_async,
                max_retries=self._max_retries
            )

            self._subscriptions[subscription_id] = subscription
            self._event_handlers[event_type].append(subscription)
            self._stats['subscriptions_count'] += 1

            logger.debug(f"Subscribed to {event_type} with ID {subscription_id}")
            return subscription_id

        except Exception as e:
            logger.error(f"Failed to subscribe to {event_type}: {str(e)}")
            raise

    async def subscribe_with_filter(self, event_type: str, handler: Callable[[Dict[str, Any]], None],
                                   filters: Dict[str, Any]) -> str:
        """Subscribe to events with filtering"""
        subscription_id = await self.subscribe(event_type, handler)
        self._subscriptions[subscription_id].filters = filters
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        try:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return False

            # Remove from handlers
            handlers = self._event_handlers.get(subscription.event_type, [])
            self._event_handlers[subscription.event_type] = [
                s for s in handlers if s.subscription_id != subscription_id
            ]

            # Remove subscription
            del self._subscriptions[subscription_id]
            self._stats['subscriptions_count'] -= 1

            logger.debug(f"Unsubscribed {subscription_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe {subscription_id}: {str(e)}")
            return False

    async def replay_events(self, stream_id: str, from_sequence: int = 0) -> int:
        """Replay events from a stream"""
        try:
            events = await self._event_store.get_events(stream_id, from_sequence)
            replayed_count = 0

            for stored_event in events:
                domain_event = self._event_store.deserialize_event(stored_event)
                if domain_event:
                    await self._processing_queue.put((stored_event.event_type, domain_event))
                    replayed_count += 1

            logger.info(f"Replayed {replayed_count} events from stream {stream_id}")
            return replayed_count

        except Exception as e:
            logger.error(f"Failed to replay events from {stream_id}: {str(e)}")
            return 0

    async def _process_events(self):
        """Process events from the queue"""
        while self._is_running:
            try:
                # Wait for event with timeout
                try:
                    event_type, event = await asyncio.wait_for(
                        self._processing_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                await self._handle_event(event_type, event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event processing loop: {str(e)}")

    async def _handle_event(self, event_type: str, event: DomainEvent):
        """Handle a single event"""
        handlers = self._event_handlers.get(event_type, [])
        if not handlers:
            logger.debug(f"No handlers for event type {event_type}")
            return

        # Process all handlers for this event type
        for subscription in handlers:
            await self._invoke_handler(subscription, event)

        self._stats['events_processed'] += 1

    async def _invoke_handler(self, subscription: EventSubscription, event: DomainEvent):
        """Invoke a single event handler with retry logic"""
        for attempt in range(subscription.max_retries + 1):
            try:
                # Check filters
                if not self._event_matches_filters(event, subscription.filters):
                    return

                # Prepare event data for handler
                event_data = {
                    'event': event,
                    'event_id': event.event_id,
                    'event_type': event.__class__.__name__,
                    'timestamp': event.timestamp,
                    'correlation_id': event.correlation_id,
                    'metadata': event.metadata
                }

                # Invoke handler
                if subscription.is_async:
                    await subscription.handler(event_data)
                else:
                    subscription.handler(event_data)

                # Success - reset retry count
                subscription.retry_count = 0
                return

            except Exception as e:
                subscription.retry_count += 1
                logger.error(
                    f"Handler {subscription.subscription_id} failed (attempt {attempt + 1}): {str(e)}"
                )

                if attempt < subscription.max_retries:
                    # Wait before retry with exponential backoff
                    await asyncio.sleep(0.1 * (2 ** attempt))
                else:
                    # Max retries exceeded - send to dead letter queue
                    self._dead_letter_queue.append({
                        'subscription_id': subscription.subscription_id,
                        'event': event,
                        'error': str(e),
                        'timestamp': datetime.utcnow()
                    })
                    self._stats['events_failed'] += 1

    def _event_matches_filters(self, event: DomainEvent, filters: Dict[str, Any]) -> bool:
        """Check if event matches subscription filters"""
        if not filters:
            return True

        try:
            for filter_key, filter_value in filters.items():
                if hasattr(event, filter_key):
                    event_value = getattr(event, filter_key)
                    if event_value != filter_value:
                        return False
                elif hasattr(event.metadata, filter_key):
                    metadata_value = getattr(event.metadata, filter_key)
                    if metadata_value != filter_value:
                        return False
                else:
                    # Filter key not found - doesn't match
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking event filters: {str(e)}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            **self._stats,
            'dead_letter_queue_size': len(self._dead_letter_queue),
            'processing_queue_size': self._processing_queue.qsize(),
            'is_running': self._is_running
        }

    def get_dead_letter_events(self) -> List[Dict[str, Any]]:
        """Get events from dead letter queue"""
        return list(self._dead_letter_queue)

    async def health_check(self) -> ServiceHealth:
        """Perform health check on event bus"""
        try:
            if not self._is_running:
                return ServiceHealth.UNHEALTHY

            # Check if processing task is running
            if self._processing_task and self._processing_task.done():
                return ServiceHealth.DEGRADED

            # Check dead letter queue size
            if len(self._dead_letter_queue) > 100:
                return ServiceHealth.DEGRADED

            return ServiceHealth.HEALTHY

        except Exception as e:
            logger.error(f"Event bus health check failed: {str(e)}")
            return ServiceHealth.UNHEALTHY

    async def dispose(self) -> None:
        """Clean up event bus resources"""
        await self.stop()
        self._subscriptions.clear()
        self._event_handlers.clear()
        self._dead_letter_queue.clear()
        logger.info("Event bus disposed")

# Factory function for DI container
async def create_event_bus(container, config: Dict[str, Any]) -> AsyncEventBus:
    """Factory function to create event bus with dependencies"""
    try:
        # Get database service if available
        database_service = None
        try:
            from ..abstractions.interfaces import IDatabaseService
            database_service = await container.resolve(IDatabaseService)
        except:
            logger.info("Database service not available for event store")

        # Create event store
        event_store = EventStore(database_service=database_service)

        # Create event bus
        max_retries = config.get('max_retries', 3)
        event_bus = AsyncEventBus(event_store=event_store, max_retries=max_retries)

        # Start the event bus
        await event_bus.start()

        logger.info("Event bus created and started")
        return event_bus

    except Exception as e:
        logger.error(f"Failed to create event bus: {str(e)}")
        raise