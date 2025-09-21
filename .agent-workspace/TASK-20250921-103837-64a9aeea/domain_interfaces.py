# Domain Layer Interfaces and Base Classes for Clean Architecture

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar, Generic
from uuid import uuid4

# Base Domain Types
T = TypeVar('T')

class DomainException(Exception):
    """Base exception for domain layer"""
    pass

class ValidationException(DomainException):
    """Raised when domain validation fails"""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {', '.join(errors)}")

@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> 'ValidationResult':
        return cls(is_valid=True)

    @classmethod
    def failure(cls, errors: List[str]) -> 'ValidationResult':
        return cls(is_valid=False, errors=errors)

# Enums
class MachineStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    OFFLINE = "offline"

class ProcessStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ERROR = "error"

class StepType(Enum):
    VALVE = "valve"
    PURGE = "purge"
    PARAMETER = "parameter"
    LOOP = "loop"

class ParameterDataType(Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"

class DataQuality(Enum):
    GOOD = "good"
    BAD = "bad"
    UNCERTAIN = "uncertain"

# Domain Events
@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: str = ""
    event_version: int = 1

# Value Objects
@dataclass(frozen=True)
class ParameterConstraints:
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[float]] = None
    data_type: ParameterDataType = ParameterDataType.FLOAT

    def validate_value(self, value: Any) -> ValidationResult:
        errors = []

        # Type validation
        if self.data_type == ParameterDataType.FLOAT and not isinstance(value, (int, float)):
            errors.append(f"Expected float, got {type(value)}")
        elif self.data_type == ParameterDataType.INTEGER and not isinstance(value, int):
            errors.append(f"Expected integer, got {type(value)}")
        elif self.data_type == ParameterDataType.BOOLEAN and not isinstance(value, bool):
            errors.append(f"Expected boolean, got {type(value)}")

        if errors:
            return ValidationResult.failure(errors)

        # Range validation for numeric types
        if self.data_type in [ParameterDataType.FLOAT, ParameterDataType.INTEGER]:
            if self.min_value is not None and value < self.min_value:
                errors.append(f"Value {value} below minimum {self.min_value}")
            if self.max_value is not None and value > self.max_value:
                errors.append(f"Value {value} above maximum {self.max_value}")

        # Allowed values validation
        if self.allowed_values is not None and value not in self.allowed_values:
            errors.append(f"Value {value} not in allowed values {self.allowed_values}")

        return ValidationResult.success() if not errors else ValidationResult.failure(errors)

@dataclass(frozen=True)
class MachineState:
    status: MachineStatus
    current_process_id: Optional[str] = None
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    def can_transition_to(self, new_status: MachineStatus) -> bool:
        """Define valid state transitions"""
        valid_transitions = {
            MachineStatus.IDLE: [MachineStatus.PROCESSING, MachineStatus.ERROR, MachineStatus.OFFLINE],
            MachineStatus.PROCESSING: [MachineStatus.IDLE, MachineStatus.ERROR, MachineStatus.OFFLINE],
            MachineStatus.ERROR: [MachineStatus.IDLE, MachineStatus.OFFLINE],
            MachineStatus.OFFLINE: [MachineStatus.IDLE, MachineStatus.ERROR]
        }
        return new_status in valid_transitions.get(self.status, [])

    def transition_to_processing(self, process_id: str) -> 'MachineState':
        """Create new state for processing transition"""
        if not self.can_transition_to(MachineStatus.PROCESSING):
            raise ValidationException([f"Cannot transition from {self.status} to PROCESSING"])

        return MachineState(
            status=MachineStatus.PROCESSING,
            current_process_id=process_id,
            last_heartbeat=datetime.utcnow()
        )

    def transition_to_idle(self) -> 'MachineState':
        """Create new state for idle transition"""
        if not self.can_transition_to(MachineStatus.IDLE):
            raise ValidationException([f"Cannot transition from {self.status} to IDLE"])

        return MachineState(
            status=MachineStatus.IDLE,
            current_process_id=None,
            last_heartbeat=datetime.utcnow()
        )

@dataclass(frozen=True)
class ParameterValue:
    parameter_id: str
    value: float
    timestamp: datetime
    quality: DataQuality = DataQuality.GOOD
    source: str = "PLC"

    def is_valid_for_constraints(self, constraints: ParameterConstraints) -> ValidationResult:
        return constraints.validate_value(self.value)

# Domain Events
@dataclass(frozen=True)
class RecipeStarted(DomainEvent):
    recipe_id: str
    process_id: str
    machine_id: str
    started_by: str

@dataclass(frozen=True)
class RecipeCompleted(DomainEvent):
    recipe_id: str
    process_id: str
    machine_id: str
    duration_ms: int

@dataclass(frozen=True)
class RecipeAborted(DomainEvent):
    recipe_id: str
    process_id: str
    machine_id: str
    reason: str
    aborted_by: str

@dataclass(frozen=True)
class StepStarted(DomainEvent):
    step_id: str
    process_id: str
    step_type: StepType
    step_order: int

@dataclass(frozen=True)
class StepCompleted(DomainEvent):
    step_id: str
    process_id: str
    step_type: StepType
    duration_ms: int

@dataclass(frozen=True)
class StepFailed(DomainEvent):
    step_id: str
    process_id: str
    step_type: StepType
    error_message: str

@dataclass(frozen=True)
class ParameterValueChanged(DomainEvent):
    parameter_id: str
    old_value: Optional[float]
    new_value: float
    process_id: Optional[str]

@dataclass(frozen=True)
class ParameterValidationFailed(DomainEvent):
    parameter_id: str
    value: float
    constraint_violation: str
    process_id: Optional[str]

@dataclass(frozen=True)
class MachineStateChanged(DomainEvent):
    machine_id: str
    old_status: MachineStatus
    new_status: MachineStatus
    process_id: Optional[str]

# Repository Interfaces
class IRepository(ABC, Generic[T]):
    """Base repository interface"""

    @abstractmethod
    async def get_by_id(self, id: str) -> T:
        pass

    @abstractmethod
    async def save(self, entity: T) -> None:
        pass

class IRecipeRepository(IRepository['Recipe']):
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional['Recipe']:
        pass

    @abstractmethod
    async def get_all_active(self) -> List['Recipe']:
        pass

class IParameterRepository(IRepository['Parameter']):
    @abstractmethod
    async def get_active_parameters(self) -> List['Parameter']:
        pass

    @abstractmethod
    async def get_by_modbus_address(self, address: int) -> Optional['Parameter']:
        pass

class IProcessRepository(IRepository['Process']):
    @abstractmethod
    async def get_active_process(self, machine_id: str) -> Optional['Process']:
        pass

    @abstractmethod
    async def get_process_history(self, machine_id: str, limit: int = 100) -> List['Process']:
        pass

class IMachineRepository(IRepository['Machine']):
    @abstractmethod
    async def get_current_state(self, machine_id: str) -> MachineState:
        pass

    @abstractmethod
    async def update_state(self, machine_id: str, new_state: MachineState) -> None:
        pass

# Service Interfaces
class IPLCService(ABC):
    @abstractmethod
    async def read_parameter(self, parameter_id: str) -> ParameterValue:
        pass

    @abstractmethod
    async def read_parameters_bulk(self, parameters: List['Parameter']) -> List[ParameterValue]:
        pass

    @abstractmethod
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        pass

    @abstractmethod
    async def control_valve(self, valve_number: int, state: bool, duration_ms: Optional[int] = None) -> bool:
        pass

    @abstractmethod
    async def execute_purge(self, duration_ms: int) -> bool:
        pass

class IDataLogger(ABC):
    @abstractmethod
    async def log_process_data(self, process_id: str, parameter_values: List[ParameterValue]) -> None:
        pass

    @abstractmethod
    async def log_parameter_history(self, parameter_values: List[ParameterValue]) -> None:
        pass

class IEventBus(ABC):
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        pass

    @abstractmethod
    def subscribe(self, event_type: type, handler: 'IEventHandler') -> None:
        pass

class IEventHandler(ABC, Generic[T]):
    @abstractmethod
    async def handle(self, event: T) -> None:
        pass

# Domain Services
class RecipeValidationService:
    def validate_recipe(self, recipe: 'Recipe') -> ValidationResult:
        errors = []

        if not recipe.steps:
            errors.append("Recipe must have at least one step")

        # Validate step order
        expected_order = 1
        for step in sorted(recipe.steps, key=lambda s: s.order):
            if step.order != expected_order:
                errors.append(f"Step order gap detected: expected {expected_order}, got {step.order}")
            expected_order += 1

        # Validate step configurations
        for step in recipe.steps:
            step_validation = self._validate_step(step)
            if not step_validation.is_valid:
                errors.extend(step_validation.errors)

        return ValidationResult.success() if not errors else ValidationResult.failure(errors)

    def _validate_step(self, step: 'Step') -> ValidationResult:
        errors = []

        if step.step_type == StepType.VALVE:
            if not hasattr(step.configuration, 'valve_number'):
                errors.append("Valve step missing valve_number")
        elif step.step_type == StepType.PURGE:
            if not hasattr(step.configuration, 'duration_ms'):
                errors.append("Purge step missing duration_ms")
        elif step.step_type == StepType.PARAMETER:
            if not hasattr(step.configuration, 'parameter_id'):
                errors.append("Parameter step missing parameter_id")

        return ValidationResult.success() if not errors else ValidationResult.failure(errors)

class StateTransitionService:
    def validate_transition(self, current_state: MachineState, new_status: MachineStatus) -> ValidationResult:
        if not current_state.can_transition_to(new_status):
            return ValidationResult.failure([
                f"Invalid state transition from {current_state.status} to {new_status}"
            ])
        return ValidationResult.success()

    def create_transition_event(
        self,
        machine_id: str,
        current_state: MachineState,
        new_status: MachineStatus,
        process_id: Optional[str] = None
    ) -> MachineStateChanged:
        return MachineStateChanged(
            aggregate_id=machine_id,
            machine_id=machine_id,
            old_status=current_state.status,
            new_status=new_status,
            process_id=process_id
        )

# This file provides the foundation for the domain layer of the clean architecture.
# It defines all the core domain concepts, value objects, events, and service interfaces
# that will be implemented in the full clean architecture redesign.