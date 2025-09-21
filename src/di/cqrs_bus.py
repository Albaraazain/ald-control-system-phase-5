# File: src/di/cqrs_bus.py
"""
CQRS Bus implementation with command and query separation.
Provides async handling, validation, and event integration.
"""
import asyncio
import time
from typing import Dict, Any, Type, Optional, List
from collections import defaultdict

from ..abstractions.cqrs import (
    Command, Query, CommandHandler, QueryHandler, CommandBus, QueryBus,
    CommandResult, QueryResult, CommandStatus, QueryStatus
)
from ..abstractions.interfaces import IEventBus
from ..abstractions.events import CommandExecutedEvent, CommandFailedEvent
from src.log_setup import logger

class AsyncCommandBus(CommandBus):
    """
    Async command bus implementation with validation and event publishing.

    Features:
    - Command validation before execution
    - Event publishing for command lifecycle
    - Performance monitoring
    - Error handling and retry logic
    """

    def __init__(self, event_bus: Optional[IEventBus] = None):
        self._handlers: Dict[Type[Command], CommandHandler] = {}
        self._event_bus = event_bus
        self._stats = {
            'commands_processed': 0,
            'commands_failed': 0,
            'average_execution_time': 0.0
        }

    async def send(self, command: Command) -> CommandResult:
        """Send a command for execution"""
        start_time = time.perf_counter()

        try:
            # Validate command
            validation_errors = command.validate()
            if validation_errors:
                error_message = "; ".join(validation_errors)
                result = CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.FAILED,
                    error_message=f"Validation failed: {error_message}",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000
                )

                # Publish failure event
                await self._publish_command_failed(command, error_message)
                self._stats['commands_failed'] += 1
                return result

            # Find handler
            handler = self._find_handler(command)
            if not handler:
                error_message = f"No handler found for command {command.__class__.__name__}"
                result = CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.FAILED,
                    error_message=error_message,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000
                )

                await self._publish_command_failed(command, error_message)
                self._stats['commands_failed'] += 1
                return result

            # Execute command
            logger.debug(f"Executing command {command.__class__.__name__} with ID {command.command_id}")
            result = await handler.handle(command)

            # Update execution time
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Publish success event
            if result.status == CommandStatus.COMPLETED:
                await self._publish_command_executed(command, result)
                self._stats['commands_processed'] += 1
            else:
                await self._publish_command_failed(command, result.error_message or "Unknown error")
                self._stats['commands_failed'] += 1

            # Update average execution time
            self._update_average_execution_time(result.execution_time_ms)

            logger.debug(f"Command {command.command_id} completed with status {result.status.value}")
            return result

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            error_message = f"Command execution failed: {str(e)}"

            result = CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=error_message,
                execution_time_ms=execution_time
            )

            await self._publish_command_failed(command, error_message)
            self._stats['commands_failed'] += 1
            self._update_average_execution_time(execution_time)

            logger.error(f"Command {command.command_id} failed: {str(e)}")
            return result

    def register_handler(self, command_type: Type[Command], handler: CommandHandler) -> None:
        """Register a command handler"""
        self._handlers[command_type] = handler
        logger.debug(f"Registered command handler for {command_type.__name__}")

    def _find_handler(self, command: Command) -> Optional[CommandHandler]:
        """Find appropriate handler for command"""
        command_type = type(command)
        handler = self._handlers.get(command_type)

        if handler and handler.can_handle(command):
            return handler

        # Try to find handler by inheritance
        for handler_type, handler in self._handlers.items():
            if isinstance(command, handler_type) and handler.can_handle(command):
                return handler

        return None

    async def _publish_command_executed(self, command: Command, result: CommandResult):
        """Publish command executed event"""
        if not self._event_bus:
            return

        try:
            event = CommandExecutedEvent(
                command_id=command.command_id,
                command_type=command.__class__.__name__,
                issued_by=command.issued_by,
                target_aggregate=getattr(command, 'target_aggregate', 'unknown'),
                result=result.result or {},
                execution_time_ms=result.execution_time_ms
            )

            if command.correlation_id:
                event = event.with_correlation(command.correlation_id)

            await self._event_bus.publish("CommandExecuted", {"event": event})

        except Exception as e:
            logger.error(f"Failed to publish command executed event: {str(e)}")

    async def _publish_command_failed(self, command: Command, error_message: str):
        """Publish command failed event"""
        if not self._event_bus:
            return

        try:
            event = CommandFailedEvent(
                command_id=command.command_id,
                command_type=command.__class__.__name__,
                issued_by=command.issued_by,
                target_aggregate=getattr(command, 'target_aggregate', 'unknown'),
                error_message=error_message
            )

            if command.correlation_id:
                event = event.with_correlation(command.correlation_id)

            await self._event_bus.publish("CommandFailed", {"event": event})

        except Exception as e:
            logger.error(f"Failed to publish command failed event: {str(e)}")

    def _update_average_execution_time(self, execution_time: float):
        """Update average execution time statistic"""
        total_commands = self._stats['commands_processed'] + self._stats['commands_failed']
        if total_commands > 0:
            current_avg = self._stats['average_execution_time']
            self._stats['average_execution_time'] = (
                (current_avg * (total_commands - 1) + execution_time) / total_commands
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get command bus statistics"""
        return dict(self._stats)

class AsyncQueryBus(QueryBus):
    """
    Async query bus implementation with caching and performance monitoring.

    Features:
    - Query validation before execution
    - Result caching for performance
    - Performance monitoring
    - Error handling
    """

    def __init__(self, enable_caching: bool = True):
        self._handlers: Dict[Type[Query], QueryHandler] = {}
        self._enable_caching = enable_caching
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes default TTL
        self._stats = {
            'queries_processed': 0,
            'queries_failed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'average_execution_time': 0.0
        }

    async def query(self, query: Query) -> QueryResult:
        """Execute a query"""
        start_time = time.perf_counter()

        try:
            # Validate query
            validation_errors = query.validate()
            if validation_errors:
                error_message = "; ".join(validation_errors)
                return QueryResult(
                    query_id=query.query_id,
                    status=QueryStatus.FAILED,
                    error_message=f"Validation failed: {error_message}",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000
                )

            # Check cache
            if self._enable_caching:
                cache_key = self._generate_cache_key(query)
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    self._stats['cache_hits'] += 1
                    logger.debug(f"Query {query.query_id} served from cache")
                    return cached_result

            self._stats['cache_misses'] += 1

            # Find handler
            handler = self._find_handler(query)
            if not handler:
                error_message = f"No handler found for query {query.__class__.__name__}"
                return QueryResult(
                    query_id=query.query_id,
                    status=QueryStatus.FAILED,
                    error_message=error_message,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000
                )

            # Execute query
            logger.debug(f"Executing query {query.__class__.__name__} with ID {query.query_id}")
            result = await handler.handle(query)

            # Update execution time
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Cache successful results
            if self._enable_caching and result.status == QueryStatus.COMPLETED:
                cache_key = self._generate_cache_key(query)
                self._cache_result(cache_key, result)

            # Update statistics
            if result.status == QueryStatus.COMPLETED:
                self._stats['queries_processed'] += 1
            else:
                self._stats['queries_failed'] += 1

            self._update_average_execution_time(result.execution_time_ms)

            logger.debug(f"Query {query.query_id} completed with status {result.status.value}")
            return result

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            error_message = f"Query execution failed: {str(e)}"

            result = QueryResult(
                query_id=query.query_id,
                status=QueryStatus.FAILED,
                error_message=error_message,
                execution_time_ms=execution_time
            )

            self._stats['queries_failed'] += 1
            self._update_average_execution_time(execution_time)

            logger.error(f"Query {query.query_id} failed: {str(e)}")
            return result

    def register_handler(self, query_type: Type[Query], handler: QueryHandler) -> None:
        """Register a query handler"""
        self._handlers[query_type] = handler
        logger.debug(f"Registered query handler for {query_type.__name__}")

    def _find_handler(self, query: Query) -> Optional[QueryHandler]:
        """Find appropriate handler for query"""
        query_type = type(query)
        handler = self._handlers.get(query_type)

        if handler and handler.can_handle(query):
            return handler

        # Try to find handler by inheritance
        for handler_type, handler in self._handlers.items():
            if isinstance(query, handler_type) and handler.can_handle(query):
                return handler

        return None

    def _generate_cache_key(self, query: Query) -> str:
        """Generate cache key for query"""
        # Simple implementation - could be more sophisticated
        import hashlib
        import json

        query_data = {
            'type': query.__class__.__name__,
            'data': {k: v for k, v in query.__dict__.items() if k not in ['query_id', 'timestamp', 'metadata']}
        }

        query_str = json.dumps(query_data, sort_keys=True, default=str)
        return hashlib.md5(query_str.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[QueryResult]:
        """Get result from cache if not expired"""
        cached_item = self._cache.get(cache_key)
        if not cached_item:
            return None

        cached_time, result = cached_item
        if time.time() - cached_time > self._cache_ttl:
            # Expired
            del self._cache[cache_key]
            return None

        return result

    def _cache_result(self, cache_key: str, result: QueryResult):
        """Cache query result"""
        self._cache[cache_key] = (time.time(), result)

        # Simple cache size management
        if len(self._cache) > 1000:
            # Remove oldest 20% of entries
            oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])[:200]
            for key in oldest_keys:
                del self._cache[key]

    def _update_average_execution_time(self, execution_time: float):
        """Update average execution time statistic"""
        total_queries = self._stats['queries_processed'] + self._stats['queries_failed']
        if total_queries > 0:
            current_avg = self._stats['average_execution_time']
            self._stats['average_execution_time'] = (
                (current_avg * (total_queries - 1) + execution_time) / total_queries
            )

    def clear_cache(self):
        """Clear query result cache"""
        self._cache.clear()
        logger.debug("Query cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get query bus statistics"""
        return {
            **self._stats,
            'cache_size': len(self._cache)
        }

# Factory functions for DI container
async def create_command_bus(container, config: Dict[str, Any]) -> AsyncCommandBus:
    """Factory function to create command bus with dependencies"""
    try:
        # Get event bus if available
        event_bus = None
        try:
            from ..abstractions.interfaces import IEventBus
            event_bus = await container.resolve(IEventBus)
        except:
            logger.info("Event bus not available for command bus")

        command_bus = AsyncCommandBus(event_bus=event_bus)
        logger.info("Command bus created")
        return command_bus

    except Exception as e:
        logger.error(f"Failed to create command bus: {str(e)}")
        raise

async def create_query_bus(container, config: Dict[str, Any]) -> AsyncQueryBus:
    """Factory function to create query bus with dependencies"""
    try:
        enable_caching = config.get('enable_caching', True)
        query_bus = AsyncQueryBus(enable_caching=enable_caching)
        logger.info("Query bus created")
        return query_bus

    except Exception as e:
        logger.error(f"Failed to create query bus: {str(e)}")
        raise