# File: src/domain/entities.py
"""
Domain entities for the ALD control system.
Contains core business objects with identity and lifecycle.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import uuid

from ..abstractions.events import DomainEvent
from .value_objects import ProcessId, RecipeId, ParameterId, Duration

class ProcessStatus(Enum):
    """Status of an ALD process"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepType(Enum):
    """Types of process steps"""
    VALVE = "valve"
    PURGE = "purge"
    PARAMETER = "parameter"
    LOOP = "loop"
    WAIT = "wait"
    CONDITION = "condition"

class ParameterType(Enum):
    """Types of parameters"""
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    FLOW_RATE = "flow_rate"
    VOLTAGE = "voltage"
    CURRENT = "current"
    TIME = "time"
    POSITION = "position"
    CONCENTRATION = "concentration"

@dataclass
class Entity:
    """Base entity class with identity"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    def __post_init__(self):
        self._domain_events: List[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent):
        """Add a domain event to be published"""
        self._domain_events.append(event)

    def get_domain_events(self) -> List[DomainEvent]:
        """Get all domain events"""
        return self._domain_events.copy()

    def clear_domain_events(self):
        """Clear all domain events"""
        self._domain_events.clear()

    def mark_updated(self):
        """Mark entity as updated"""
        self.updated_at = datetime.utcnow()
        self.version += 1

@dataclass
class Parameter(Entity):
    """Parameter entity representing a measurable system parameter"""
    parameter_id: ParameterId
    name: str
    parameter_type: ParameterType
    unit: str
    current_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    read_address: Optional[str] = None
    write_address: Optional[str] = None
    is_writable: bool = False
    is_critical: bool = False
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        if not self.id:
            self.id = str(self.parameter_id)

    def update_value(self, new_value: float, source: str = "plc"):
        """Update parameter value and emit event"""
        from ..abstractions.events import ParameterChangedEvent

        old_value = self.current_value
        self.current_value = new_value
        self.mark_updated()

        # Add domain event
        event = ParameterChangedEvent(
            parameter_id=str(self.parameter_id),
            old_value=old_value,
            new_value=new_value,
            change_source=source
        )
        self.add_domain_event(event)

    def validate_value(self, value: float) -> bool:
        """Validate if value is within acceptable range"""
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True

    def is_in_range(self) -> bool:
        """Check if current value is in acceptable range"""
        if self.current_value is None:
            return False
        return self.validate_value(self.current_value)

@dataclass
class ProcessStep(Entity):
    """Process step entity representing a single step in a recipe"""
    step_number: int
    step_type: StepType
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[Duration] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    is_critical: bool = False
    can_skip: bool = False
    description: str = ""

    def validate_parameters(self) -> List[str]:
        """Validate step parameters based on type"""
        errors = []

        if self.step_type == StepType.VALVE:
            if 'valve_number' not in self.parameters:
                errors.append("valve_number is required for valve steps")
            if 'state' not in self.parameters:
                errors.append("state is required for valve steps")

        elif self.step_type == StepType.PURGE:
            if 'duration_ms' not in self.parameters:
                errors.append("duration_ms is required for purge steps")

        elif self.step_type == StepType.PARAMETER:
            if 'parameter_id' not in self.parameters:
                errors.append("parameter_id is required for parameter steps")
            if 'value' not in self.parameters:
                errors.append("value is required for parameter steps")

        elif self.step_type == StepType.WAIT:
            if 'duration_ms' not in self.parameters:
                errors.append("duration_ms is required for wait steps")

        return errors

    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if step can be executed in current context"""
        # Check conditions
        for condition_key, condition_value in self.conditions.items():
            if condition_key not in context:
                return False
            if context[condition_key] != condition_value:
                return False

        return True

@dataclass
class Recipe(Entity):
    """Recipe entity representing a complete ALD process recipe"""
    recipe_id: RecipeId
    name: str
    description: str
    steps: List[ProcessStep] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    version_number: str = "1.0"
    created_by: str = "system"
    tags: List[str] = field(default_factory=list)
    estimated_duration: Optional[Duration] = None

    def __post_init__(self):
        super().__post_init__()
        if not self.id:
            self.id = str(self.recipe_id)

    def add_step(self, step: ProcessStep):
        """Add a step to the recipe"""
        if not step.step_number:
            step.step_number = len(self.steps) + 1
        self.steps.append(step)
        self.mark_updated()

    def remove_step(self, step_number: int):
        """Remove a step from the recipe"""
        self.steps = [s for s in self.steps if s.step_number != step_number]
        # Renumber remaining steps
        for i, step in enumerate(self.steps):
            step.step_number = i + 1
        self.mark_updated()

    def get_step(self, step_number: int) -> Optional[ProcessStep]:
        """Get a step by number"""
        for step in self.steps:
            if step.step_number == step_number:
                return step
        return None

    def validate(self) -> List[str]:
        """Validate recipe integrity"""
        errors = []

        if not self.name:
            errors.append("Recipe name is required")

        if not self.steps:
            errors.append("Recipe must have at least one step")

        # Validate step numbering
        step_numbers = [s.step_number for s in self.steps]
        if len(set(step_numbers)) != len(step_numbers):
            errors.append("Duplicate step numbers found")

        if step_numbers != list(range(1, len(step_numbers) + 1)):
            errors.append("Step numbers must be consecutive starting from 1")

        # Validate individual steps
        for step in self.steps:
            step_errors = step.validate_parameters()
            errors.extend([f"Step {step.step_number}: {error}" for error in step_errors])

        return errors

    def calculate_estimated_duration(self) -> Duration:
        """Calculate estimated duration based on steps"""
        total_ms = 0

        for step in self.steps:
            if step.duration:
                total_ms += step.duration.total_milliseconds

            # Add default durations for step types
            if step.step_type == StepType.VALVE:
                total_ms += step.parameters.get('duration_ms', 1000)
            elif step.step_type == StepType.PURGE:
                total_ms += step.parameters.get('duration_ms', 5000)
            elif step.step_type == StepType.WAIT:
                total_ms += step.parameters.get('duration_ms', 1000)
            else:
                total_ms += 500  # Default execution time

        return Duration(milliseconds=total_ms)

@dataclass
class ALDProcess(Entity):
    """ALD Process entity representing a running or completed process"""
    process_id: ProcessId
    recipe_id: RecipeId
    status: ProcessStatus
    started_by: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: int = 0
    total_steps: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        if not self.id:
            self.id = str(self.process_id)

    def start(self, recipe: Recipe):
        """Start the process with a recipe"""
        from ..abstractions.events import ProcessStartedEvent

        self.status = ProcessStatus.STARTING
        self.started_at = datetime.utcnow()
        self.total_steps = len(recipe.steps)
        self.current_step = 0
        self.mark_updated()

        # Add domain event
        event = ProcessStartedEvent(
            process_id=str(self.process_id),
            recipe_id=str(self.recipe_id),
            recipe_name=recipe.name,
            started_by=self.started_by,
            parameters=self.parameters
        )
        self.add_domain_event(event)

    def advance_step(self):
        """Advance to next step"""
        from ..abstractions.events import ProcessStepCompletedEvent

        if self.current_step < self.total_steps:
            # Log step completion
            step_info = {
                'step_number': self.current_step,
                'completed_at': datetime.utcnow().isoformat(),
                'duration': self.get_current_step_duration()
            }
            self.execution_log.append(step_info)

            # Emit step completed event
            event = ProcessStepCompletedEvent(
                process_id=str(self.process_id),
                step_id=str(self.current_step),
                step_type="unknown",  # Would need step details
                step_number=self.current_step,
                duration_seconds=self.get_current_step_duration()
            )
            self.add_domain_event(event)

            self.current_step += 1
            self.mark_updated()

            # Check if process is complete
            if self.current_step >= self.total_steps:
                self.complete()

    def complete(self):
        """Mark process as completed"""
        from ..abstractions.events import ProcessStoppedEvent

        self.status = ProcessStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.mark_updated()

        # Calculate duration
        duration = 0.0
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()

        # Add domain event
        event = ProcessStoppedEvent(
            process_id=str(self.process_id),
            recipe_id=str(self.recipe_id),
            stop_reason="completed",
            stopped_by="system",
            duration_seconds=duration,
            completion_status="completed"
        )
        self.add_domain_event(event)

    def fail(self, error_message: str):
        """Mark process as failed"""
        from ..abstractions.events import ProcessStoppedEvent

        self.status = ProcessStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        self.mark_updated()

        # Calculate duration
        duration = 0.0
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()

        # Add domain event
        event = ProcessStoppedEvent(
            process_id=str(self.process_id),
            recipe_id=str(self.recipe_id),
            stop_reason="error",
            stopped_by="system",
            duration_seconds=duration,
            completion_status="failed"
        )
        self.add_domain_event(event)

    def cancel(self, cancelled_by: str = "user"):
        """Cancel the process"""
        from ..abstractions.events import ProcessStoppedEvent

        self.status = ProcessStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.mark_updated()

        # Calculate duration
        duration = 0.0
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()

        # Add domain event
        event = ProcessStoppedEvent(
            process_id=str(self.process_id),
            recipe_id=str(self.recipe_id),
            stop_reason="cancelled",
            stopped_by=cancelled_by,
            duration_seconds=duration,
            completion_status="cancelled"
        )
        self.add_domain_event(event)

    def get_current_step_duration(self) -> float:
        """Get duration of current step in seconds"""
        if not self.execution_log:
            return 0.0

        last_entry = self.execution_log[-1]
        if 'started_at' in last_entry:
            started = datetime.fromisoformat(last_entry['started_at'])
            return (datetime.utcnow() - started).total_seconds()

        return 0.0

    def get_total_duration(self) -> float:
        """Get total process duration in seconds"""
        if not self.started_at:
            return 0.0

        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    def is_running(self) -> bool:
        """Check if process is currently running"""
        return self.status in [ProcessStatus.STARTING, ProcessStatus.RUNNING]

    def can_be_cancelled(self) -> bool:
        """Check if process can be cancelled"""
        return self.status in [ProcessStatus.STARTING, ProcessStatus.RUNNING, ProcessStatus.PAUSED]

    def get_progress_percentage(self) -> float:
        """Get progress as percentage"""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100.0