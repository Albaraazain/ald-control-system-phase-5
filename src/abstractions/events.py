# File: src/abstractions/events.py
"""
Event-driven architecture base classes and domain events.
Provides foundation for event sourcing, CQRS, and event-driven communication.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from enum import Enum

T = TypeVar('T')

class EventType(Enum):
    """Standard event types for the ALD system"""
    DOMAIN = "domain"           # Business domain events
    INTEGRATION = "integration" # External system integration events
    SYSTEM = "system"          # System-level events
    ERROR = "error"            # Error and exception events
    AUDIT = "audit"            # Audit trail events

@dataclass
class EventMetadata:
    """Metadata for all events in the system"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.DOMAIN
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    source: Optional[str] = None
    version: int = 1
    user_id: Optional[str] = None
    aggregate_id: Optional[str] = None
    aggregate_type: Optional[str] = None
    sequence_number: Optional[int] = None

@dataclass
class DomainEvent(ABC):
    """Base class for all domain events"""
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self):
        if not self.metadata.aggregate_type:
            self.metadata.aggregate_type = self.__class__.__module__.split('.')[-2] if '.' in self.__class__.__module__ else 'unknown'

    @property
    def event_id(self) -> str:
        return self.metadata.event_id

    @property
    def timestamp(self) -> datetime:
        return self.metadata.timestamp

    @property
    def correlation_id(self) -> Optional[str]:
        return self.metadata.correlation_id

    def with_correlation(self, correlation_id: str) -> 'DomainEvent':
        """Return new event with correlation ID"""
        new_event = self.__class__(**{k: v for k, v in self.__dict__.items() if k != 'metadata'})
        new_event.metadata = EventMetadata(
            **{k: v for k, v in self.metadata.__dict__.items()},
            correlation_id=correlation_id
        )
        return new_event

    def with_causation(self, causation_id: str) -> 'DomainEvent':
        """Return new event with causation ID"""
        new_event = self.__class__(**{k: v for k, v in self.__dict__.items() if k != 'metadata'})
        new_event.metadata = EventMetadata(
            **{k: v for k, v in self.metadata.__dict__.items()},
            causation_id=causation_id
        )
        return new_event

# ALD Process Domain Events
@dataclass
class ProcessStartedEvent(DomainEvent):
    """Event fired when an ALD process starts"""
    process_id: str
    recipe_id: str
    recipe_name: str
    started_by: str
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessStoppedEvent(DomainEvent):
    """Event fired when an ALD process stops"""
    process_id: str
    recipe_id: str
    stop_reason: str
    stopped_by: str
    duration_seconds: float
    completion_status: str  # 'completed', 'cancelled', 'error'

@dataclass
class ProcessStepStartedEvent(DomainEvent):
    """Event fired when a process step starts"""
    process_id: str
    step_id: str
    step_type: str
    step_number: int
    step_parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessStepCompletedEvent(DomainEvent):
    """Event fired when a process step completes"""
    process_id: str
    step_id: str
    step_type: str
    step_number: int
    duration_seconds: float
    result: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessStepFailedEvent(DomainEvent):
    """Event fired when a process step fails"""
    process_id: str
    step_id: str
    step_type: str
    step_number: int
    error_message: str
    error_details: Dict[str, Any] = field(default_factory=dict)

# PLC Operation Events
@dataclass
class PLCConnectedEvent(DomainEvent):
    """Event fired when PLC connection is established"""
    plc_address: str
    connection_method: str
    plc_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PLCDisconnectedEvent(DomainEvent):
    """Event fired when PLC connection is lost"""
    plc_address: str
    disconnect_reason: str
    was_expected: bool = False

@dataclass
class ParameterChangedEvent(DomainEvent):
    """Event fired when a parameter value changes"""
    parameter_id: str
    old_value: Optional[float]
    new_value: float
    change_source: str  # 'plc', 'user', 'recipe'
    process_id: Optional[str] = None

@dataclass
class ValveOperationEvent(DomainEvent):
    """Event fired for valve operations"""
    valve_number: int
    operation: str  # 'open', 'close'
    duration_ms: Optional[int]
    process_id: Optional[str] = None
    success: bool = True

@dataclass
class PurgeOperationEvent(DomainEvent):
    """Event fired for purge operations"""
    duration_ms: int
    process_id: Optional[str] = None
    success: bool = True

# Command Events (CQRS)
@dataclass
class CommandEvent(DomainEvent):
    """Base class for command events"""
    command_id: str
    command_type: str
    issued_by: str
    target_aggregate: str

@dataclass
class CommandExecutedEvent(CommandEvent):
    """Event fired when a command is successfully executed"""
    result: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

@dataclass
class CommandFailedEvent(CommandEvent):
    """Event fired when a command fails"""
    error_message: str
    error_details: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0

# System Events
@dataclass
class SystemStartedEvent(DomainEvent):
    """Event fired when the ALD system starts"""
    system_version: str
    startup_mode: str  # 'normal', 'recovery', 'maintenance'
    services_started: List[str] = field(default_factory=list)

@dataclass
class SystemShuttingDownEvent(DomainEvent):
    """Event fired when the ALD system is shutting down"""
    shutdown_reason: str
    shutdown_initiated_by: str
    graceful: bool = True

@dataclass
class HealthCheckEvent(DomainEvent):
    """Event fired for system health checks"""
    component: str
    health_status: str  # 'healthy', 'degraded', 'unhealthy'
    details: Dict[str, Any] = field(default_factory=dict)

# Error Events
@dataclass
class ErrorOccurredEvent(DomainEvent):
    """Event fired when system errors occur"""
    error_type: str
    error_message: str
    component: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

# Event Store Events
@dataclass
class EventStoredEvent(DomainEvent):
    """Event fired when an event is persisted to the event store"""
    stored_event_id: str
    stored_event_type: str
    stream_id: str
    sequence_number: int
    storage_duration_ms: float

# Integration Events
@dataclass
class DatabaseOperationEvent(DomainEvent):
    """Event fired for database operations"""
    operation_type: str  # 'insert', 'update', 'delete', 'select'
    table_name: str
    affected_rows: int
    duration_ms: float
    success: bool = True
    error_message: Optional[str] = None

@dataclass
class ExternalSystemEvent(DomainEvent):
    """Event fired for external system interactions"""
    system_name: str
    operation: str
    request_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True

# Event Registry for type mapping
EVENT_REGISTRY: Dict[str, Type[DomainEvent]] = {
    # Process Events
    'ProcessStarted': ProcessStartedEvent,
    'ProcessStopped': ProcessStoppedEvent,
    'ProcessStepStarted': ProcessStepStartedEvent,
    'ProcessStepCompleted': ProcessStepCompletedEvent,
    'ProcessStepFailed': ProcessStepFailedEvent,

    # PLC Events
    'PLCConnected': PLCConnectedEvent,
    'PLCDisconnected': PLCDisconnectedEvent,
    'ParameterChanged': ParameterChangedEvent,
    'ValveOperation': ValveOperationEvent,
    'PurgeOperation': PurgeOperationEvent,

    # Command Events
    'CommandExecuted': CommandExecutedEvent,
    'CommandFailed': CommandFailedEvent,

    # System Events
    'SystemStarted': SystemStartedEvent,
    'SystemShuttingDown': SystemShuttingDownEvent,
    'HealthCheck': HealthCheckEvent,
    'ErrorOccurred': ErrorOccurredEvent,
    'EventStored': EventStoredEvent,

    # Integration Events
    'DatabaseOperation': DatabaseOperationEvent,
    'ExternalSystem': ExternalSystemEvent,
}

def get_event_type(event_name: str) -> Optional[Type[DomainEvent]]:
    """Get event type class from event name"""
    return EVENT_REGISTRY.get(event_name)

def register_event_type(event_name: str, event_class: Type[DomainEvent]) -> None:
    """Register a new event type"""
    EVENT_REGISTRY[event_name] = event_class