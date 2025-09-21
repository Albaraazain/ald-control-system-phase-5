# File: src/abstractions/cqrs.py
"""
CQRS (Command Query Responsibility Segregation) implementation.
Provides command and query separation with async handling and validation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypeVar, Generic, Type, List
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from enum import Enum

from .events import DomainEvent, EventMetadata
from src.log_setup import logger

T = TypeVar('T')
TCommand = TypeVar('TCommand', bound='Command')
TQuery = TypeVar('TQuery', bound='Query')
TResult = TypeVar('TResult')

class CommandStatus(Enum):
    """Status of command execution"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueryStatus(Enum):
    """Status of query execution"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class CommandResult:
    """Result of command execution"""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    events_generated: List[DomainEvent] = field(default_factory=list)

@dataclass
class QueryResult(Generic[T]):
    """Result of query execution"""
    query_id: str
    status: QueryStatus
    data: Optional[T] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    total_count: Optional[int] = None

# Base Command and Query Classes
@dataclass
class Command(ABC):
    """Base class for all commands (write operations)"""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    issued_by: str = "system"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def validate(self) -> List[str]:
        """Validate command parameters. Return list of validation errors."""
        pass

@dataclass
class Query(ABC, Generic[T]):
    """Base class for all queries (read operations)"""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    requested_by: str = "system"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def validate(self) -> List[str]:
        """Validate query parameters. Return list of validation errors."""
        pass

# Command Handler Interface
class CommandHandler(ABC, Generic[TCommand]):
    """Base class for command handlers"""

    @abstractmethod
    async def handle(self, command: TCommand) -> CommandResult:
        """Handle a command and return result"""
        pass

    @abstractmethod
    def can_handle(self, command: Command) -> bool:
        """Check if this handler can handle the given command"""
        pass

# Query Handler Interface
class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Base class for query handlers"""

    @abstractmethod
    async def handle(self, query: TQuery) -> QueryResult[TResult]:
        """Handle a query and return result"""
        pass

    @abstractmethod
    def can_handle(self, query: Query) -> bool:
        """Check if this handler can handle the given query"""
        pass

# ALD Process Commands
@dataclass
class StartProcessCommand(Command):
    """Command to start an ALD process"""
    recipe_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors = []
        if not self.recipe_id:
            errors.append("recipe_id is required")
        if not self.recipe_id.strip():
            errors.append("recipe_id cannot be empty")
        return errors

@dataclass
class StopProcessCommand(Command):
    """Command to stop a running ALD process"""
    process_id: str
    reason: str = "manual_stop"

    def validate(self) -> List[str]:
        errors = []
        if not self.process_id:
            errors.append("process_id is required")
        return errors

@dataclass
class SetParameterCommand(Command):
    """Command to set a parameter value"""
    parameter_id: str
    value: float
    process_id: Optional[str] = None

    def validate(self) -> List[str]:
        errors = []
        if not self.parameter_id:
            errors.append("parameter_id is required")
        if self.value is None:
            errors.append("value is required")
        return errors

@dataclass
class ControlValveCommand(Command):
    """Command to control a valve"""
    valve_number: int
    state: bool  # True = open, False = close
    duration_ms: Optional[int] = None
    process_id: Optional[str] = None

    def validate(self) -> List[str]:
        errors = []
        if self.valve_number is None or self.valve_number < 0:
            errors.append("valve_number must be a non-negative integer")
        if self.duration_ms is not None and self.duration_ms <= 0:
            errors.append("duration_ms must be positive")
        return errors

@dataclass
class ExecutePurgeCommand(Command):
    """Command to execute a purge operation"""
    duration_ms: int
    process_id: Optional[str] = None

    def validate(self) -> List[str]:
        errors = []
        if self.duration_ms is None or self.duration_ms <= 0:
            errors.append("duration_ms must be positive")
        return errors

# ALD Process Queries
@dataclass
class GetActiveProcessesQuery(Query[List[Dict[str, Any]]]):
    """Query to get all active processes"""
    include_parameters: bool = False

    def validate(self) -> List[str]:
        return []  # No validation needed

@dataclass
class GetProcessHistoryQuery(Query[List[Dict[str, Any]]]):
    """Query to get process execution history"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    recipe_id: Optional[str] = None
    limit: int = 100
    offset: int = 0

    def validate(self) -> List[str]:
        errors = []
        if self.limit <= 0:
            errors.append("limit must be positive")
        if self.offset < 0:
            errors.append("offset must be non-negative")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            errors.append("start_date must be before end_date")
        return errors

@dataclass
class GetParameterValuesQuery(Query[Dict[str, float]]):
    """Query to get current parameter values"""
    parameter_ids: Optional[List[str]] = None

    def validate(self) -> List[str]:
        return []  # No validation needed

@dataclass
class GetParameterHistoryQuery(Query[List[Dict[str, Any]]]):
    """Query to get parameter value history"""
    parameter_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 1000

    def validate(self) -> List[str]:
        errors = []
        if not self.parameter_id:
            errors.append("parameter_id is required")
        if self.limit <= 0:
            errors.append("limit must be positive")
        return errors

@dataclass
class GetSystemStatusQuery(Query[Dict[str, Any]]):
    """Query to get overall system status"""
    include_health_checks: bool = True

    def validate(self) -> List[str]:
        return []  # No validation needed

@dataclass
class GetRecipesQuery(Query[List[Dict[str, Any]]]):
    """Query to get available recipes"""
    active_only: bool = True

    def validate(self) -> List[str]:
        return []  # No validation needed

# Command and Query Bus Interfaces
class CommandBus(ABC):
    """Interface for command bus"""

    @abstractmethod
    async def send(self, command: Command) -> CommandResult:
        """Send a command for execution"""
        pass

    @abstractmethod
    def register_handler(self, command_type: Type[Command], handler: CommandHandler) -> None:
        """Register a command handler"""
        pass

class QueryBus(ABC):
    """Interface for query bus"""

    @abstractmethod
    async def query(self, query: Query[T]) -> QueryResult[T]:
        """Execute a query"""
        pass

    @abstractmethod
    def register_handler(self, query_type: Type[Query], handler: QueryHandler) -> None:
        """Register a query handler"""
        pass

# Command Registry for type mapping
COMMAND_REGISTRY: Dict[str, Type[Command]] = {
    'StartProcess': StartProcessCommand,
    'StopProcess': StopProcessCommand,
    'SetParameter': SetParameterCommand,
    'ControlValve': ControlValveCommand,
    'ExecutePurge': ExecutePurgeCommand,
}

# Query Registry for type mapping
QUERY_REGISTRY: Dict[str, Type[Query]] = {
    'GetActiveProcesses': GetActiveProcessesQuery,
    'GetProcessHistory': GetProcessHistoryQuery,
    'GetParameterValues': GetParameterValuesQuery,
    'GetParameterHistory': GetParameterHistoryQuery,
    'GetSystemStatus': GetSystemStatusQuery,
    'GetRecipes': GetRecipesQuery,
}

def get_command_type(command_name: str) -> Optional[Type[Command]]:
    """Get command type class from command name"""
    return COMMAND_REGISTRY.get(command_name)

def get_query_type(query_name: str) -> Optional[Type[Query]]:
    """Get query type class from query name"""
    return QUERY_REGISTRY.get(query_name)

def register_command_type(command_name: str, command_class: Type[Command]) -> None:
    """Register a new command type"""
    COMMAND_REGISTRY[command_name] = command_class

def register_query_type(query_name: str, query_class: Type[Query]) -> None:
    """Register a new query type"""
    QUERY_REGISTRY[query_name] = query_class