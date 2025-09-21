# File: src/domain/aggregates.py
"""
Domain aggregates for the ALD control system.
Aggregates ensure consistency boundaries and encapsulate business rules.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime

from .entities import ALDProcess, Recipe, ProcessStep, Parameter, ProcessStatus, StepType
from .value_objects import ProcessId, RecipeId, ParameterId, Duration
from ..abstractions.events import DomainEvent
from src.log_setup import logger

class AggregateRoot:
    """Base class for aggregate roots"""

    def __init__(self):
        self._domain_events: List[DomainEvent] = []
        self._version = 1

    def add_domain_event(self, event: DomainEvent):
        """Add a domain event to be published"""
        self._domain_events.append(event)

    def get_domain_events(self) -> List[DomainEvent]:
        """Get all domain events"""
        return self._domain_events.copy()

    def clear_domain_events(self):
        """Clear all domain events"""
        self._domain_events.clear()

    def mark_changed(self):
        """Mark aggregate as changed"""
        self._version += 1

    @property
    def version(self) -> int:
        """Get aggregate version"""
        return self._version

class ProcessAggregate(AggregateRoot):
    """
    Process aggregate managing ALD process lifecycle and consistency.

    Ensures business rules around process execution, step transitions,
    and parameter management.
    """

    def __init__(self, process: ALDProcess, recipe: Recipe):
        super().__init__()
        self._process = process
        self._recipe = recipe
        self._parameters: Dict[ParameterId, Parameter] = {}
        self._execution_context: Dict[str, Any] = {}

    @property
    def process(self) -> ALDProcess:
        """Get the process entity"""
        return self._process

    @property
    def recipe(self) -> Recipe:
        """Get the recipe entity"""
        return self._recipe

    @property
    def process_id(self) -> ProcessId:
        """Get process ID"""
        return self._process.process_id

    def add_parameter(self, parameter: Parameter):
        """Add a parameter to the process"""
        self._parameters[parameter.parameter_id] = parameter
        self.mark_changed()

    def get_parameter(self, parameter_id: ParameterId) -> Optional[Parameter]:
        """Get a parameter by ID"""
        return self._parameters.get(parameter_id)

    def start_process(self, started_by: str) -> bool:
        """Start the ALD process"""
        try:
            # Validate preconditions
            if self._process.status != ProcessStatus.IDLE:
                raise ValueError(f"Cannot start process in status {self._process.status}")

            # Validate recipe
            recipe_errors = self._recipe.validate()
            if recipe_errors:
                raise ValueError(f"Recipe validation failed: {'; '.join(recipe_errors)}")

            # Validate required parameters are available
            self._validate_required_parameters()

            # Start the process
            self._process.started_by = started_by
            self._process.start(self._recipe)

            # Add events from process entity
            for event in self._process.get_domain_events():
                self.add_domain_event(event)
            self._process.clear_domain_events()

            self.mark_changed()
            logger.info(f"Process {self.process_id} started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start process {self.process_id}: {str(e)}")
            self._process.fail(str(e))
            return False

    def execute_next_step(self) -> bool:
        """Execute the next step in the recipe"""
        try:
            if not self._process.is_running():
                raise ValueError("Process is not running")

            current_step_number = self._process.current_step + 1
            step = self._recipe.get_step(current_step_number)

            if not step:
                # No more steps, complete the process
                self._process.complete()
                self._add_process_events()
                return True

            # Validate step can be executed
            if not step.can_execute(self._execution_context):
                raise ValueError(f"Step {step.step_number} cannot be executed in current context")

            # Execute step based on type
            success = self._execute_step(step)

            if success:
                self._process.advance_step()
                self._add_process_events()
                logger.info(f"Step {step.step_number} executed successfully")
            else:
                self._process.fail(f"Step {step.step_number} execution failed")

            self.mark_changed()
            return success

        except Exception as e:
            logger.error(f"Failed to execute step: {str(e)}")
            self._process.fail(str(e))
            self._add_process_events()
            return False

    def stop_process(self, stopped_by: str, reason: str = "manual_stop") -> bool:
        """Stop the process"""
        try:
            if not self._process.can_be_cancelled():
                raise ValueError("Process cannot be stopped in current state")

            self._process.cancel(stopped_by)
            self._add_process_events()
            self.mark_changed()

            logger.info(f"Process {self.process_id} stopped by {stopped_by}: {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop process {self.process_id}: {str(e)}")
            return False

    def update_parameter(self, parameter_id: ParameterId, value: float, source: str = "plc") -> bool:
        """Update a parameter value"""
        try:
            parameter = self._parameters.get(parameter_id)
            if not parameter:
                raise ValueError(f"Parameter {parameter_id} not found")

            if not parameter.validate_value(value):
                raise ValueError(f"Value {value} is out of range for parameter {parameter_id}")

            parameter.update_value(value, source)

            # Add events from parameter entity
            for event in parameter.get_domain_events():
                self.add_domain_event(event)
            parameter.clear_domain_events()

            # Update execution context
            self._execution_context[str(parameter_id)] = value

            self.mark_changed()
            return True

        except Exception as e:
            logger.error(f"Failed to update parameter {parameter_id}: {str(e)}")
            return False

    def _execute_step(self, step: ProcessStep) -> bool:
        """Execute a specific step"""
        from ..abstractions.events import ProcessStepStartedEvent

        # Emit step started event
        event = ProcessStepStartedEvent(
            process_id=str(self.process_id),
            step_id=step.id,
            step_type=step.step_type.value,
            step_number=step.step_number,
            step_parameters=step.parameters
        )
        self.add_domain_event(event)

        try:
            if step.step_type == StepType.VALVE:
                return self._execute_valve_step(step)
            elif step.step_type == StepType.PURGE:
                return self._execute_purge_step(step)
            elif step.step_type == StepType.PARAMETER:
                return self._execute_parameter_step(step)
            elif step.step_type == StepType.WAIT:
                return self._execute_wait_step(step)
            else:
                logger.warning(f"Unknown step type: {step.step_type}")
                return True  # Skip unknown steps

        except Exception as e:
            from ..abstractions.events import ProcessStepFailedEvent

            # Emit step failed event
            event = ProcessStepFailedEvent(
                process_id=str(self.process_id),
                step_id=step.id,
                step_type=step.step_type.value,
                step_number=step.step_number,
                error_message=str(e)
            )
            self.add_domain_event(event)
            return False

    def _execute_valve_step(self, step: ProcessStep) -> bool:
        """Execute a valve control step"""
        from ..abstractions.events import ValveOperationEvent

        valve_number = step.parameters.get('valve_number')
        state = step.parameters.get('state')
        duration_ms = step.parameters.get('duration_ms')

        # Record valve operation
        event = ValveOperationEvent(
            valve_number=valve_number,
            operation="open" if state else "close",
            duration_ms=duration_ms,
            process_id=str(self.process_id)
        )
        self.add_domain_event(event)

        # In real implementation, this would interface with PLC
        logger.info(f"Valve {valve_number} {'opened' if state else 'closed'}")
        return True

    def _execute_purge_step(self, step: ProcessStep) -> bool:
        """Execute a purge step"""
        from ..abstractions.events import PurgeOperationEvent

        duration_ms = step.parameters.get('duration_ms')

        # Record purge operation
        event = PurgeOperationEvent(
            duration_ms=duration_ms,
            process_id=str(self.process_id)
        )
        self.add_domain_event(event)

        # In real implementation, this would interface with PLC
        logger.info(f"Purge executed for {duration_ms}ms")
        return True

    def _execute_parameter_step(self, step: ProcessStep) -> bool:
        """Execute a parameter setting step"""
        parameter_id = ParameterId(step.parameters.get('parameter_id'))
        value = step.parameters.get('value')

        return self.update_parameter(parameter_id, value, "recipe")

    def _execute_wait_step(self, step: ProcessStep) -> bool:
        """Execute a wait step"""
        duration_ms = step.parameters.get('duration_ms')

        # In real implementation, this would use async sleep
        logger.info(f"Wait step for {duration_ms}ms")
        return True

    def _validate_required_parameters(self):
        """Validate that all required parameters are available"""
        # Extract parameter requirements from recipe
        required_params = set()
        for step in self._recipe.steps:
            if step.step_type == StepType.PARAMETER:
                param_id = step.parameters.get('parameter_id')
                if param_id:
                    required_params.add(ParameterId(param_id))

        # Check that all required parameters are available
        missing_params = required_params - set(self._parameters.keys())
        if missing_params:
            raise ValueError(f"Missing required parameters: {[str(p) for p in missing_params]}")

    def _add_process_events(self):
        """Add events from process entity to aggregate"""
        for event in self._process.get_domain_events():
            self.add_domain_event(event)
        self._process.clear_domain_events()

    def get_status_summary(self) -> Dict[str, Any]:
        """Get current status summary"""
        return {
            'process_id': str(self.process_id),
            'recipe_id': str(self._recipe.recipe_id),
            'status': self._process.status.value,
            'current_step': self._process.current_step,
            'total_steps': self._process.total_steps,
            'progress_percentage': self._process.get_progress_percentage(),
            'started_at': self._process.started_at.isoformat() if self._process.started_at else None,
            'duration_seconds': self._process.get_total_duration(),
            'parameters_count': len(self._parameters),
            'error_message': self._process.error_message
        }

class RecipeAggregate(AggregateRoot):
    """
    Recipe aggregate managing recipe definition and validation.
    """

    def __init__(self, recipe: Recipe):
        super().__init__()
        self._recipe = recipe

    @property
    def recipe(self) -> Recipe:
        """Get the recipe entity"""
        return self._recipe

    @property
    def recipe_id(self) -> RecipeId:
        """Get recipe ID"""
        return self._recipe.recipe_id

    def add_step(self, step_type: StepType, name: str, parameters: Dict[str, Any],
                 duration: Optional[Duration] = None, conditions: Dict[str, Any] = None) -> ProcessStep:
        """Add a new step to the recipe"""
        step = ProcessStep(
            step_number=len(self._recipe.steps) + 1,
            step_type=step_type,
            name=name,
            parameters=parameters,
            duration=duration,
            conditions=conditions or {}
        )

        # Validate step
        errors = step.validate_parameters()
        if errors:
            raise ValueError(f"Step validation failed: {'; '.join(errors)}")

        self._recipe.add_step(step)
        self.mark_changed()

        logger.info(f"Added step {step.step_number} to recipe {self.recipe_id}")
        return step

    def remove_step(self, step_number: int) -> bool:
        """Remove a step from the recipe"""
        try:
            self._recipe.remove_step(step_number)
            self.mark_changed()
            logger.info(f"Removed step {step_number} from recipe {self.recipe_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove step {step_number}: {str(e)}")
            return False

    def validate_recipe(self) -> List[str]:
        """Validate the entire recipe"""
        return self._recipe.validate()

    def update_estimated_duration(self):
        """Update the estimated duration based on steps"""
        self._recipe.estimated_duration = self._recipe.calculate_estimated_duration()
        self.mark_changed()

class ParameterAggregate(AggregateRoot):
    """
    Parameter aggregate managing parameter definitions and values.
    """

    def __init__(self):
        super().__init__()
        self._parameters: Dict[ParameterId, Parameter] = {}

    def add_parameter(self, parameter: Parameter):
        """Add a parameter to the aggregate"""
        self._parameters[parameter.parameter_id] = parameter
        self.mark_changed()

    def get_parameter(self, parameter_id: ParameterId) -> Optional[Parameter]:
        """Get a parameter by ID"""
        return self._parameters.get(parameter_id)

    def get_all_parameters(self) -> List[Parameter]:
        """Get all parameters"""
        return list(self._parameters.values())

    def update_parameter_value(self, parameter_id: ParameterId, value: float, source: str = "plc") -> bool:
        """Update a parameter value"""
        parameter = self._parameters.get(parameter_id)
        if not parameter:
            return False

        parameter.update_value(value, source)

        # Add events from parameter
        for event in parameter.get_domain_events():
            self.add_domain_event(event)
        parameter.clear_domain_events()

        self.mark_changed()
        return True

    def get_current_values(self) -> Dict[ParameterId, float]:
        """Get current values of all parameters"""
        return {
            param_id: param.current_value
            for param_id, param in self._parameters.items()
            if param.current_value is not None
        }

    def get_out_of_range_parameters(self) -> List[Parameter]:
        """Get parameters that are out of their acceptable range"""
        return [param for param in self._parameters.values() if not param.is_in_range()]

class SystemAggregate(AggregateRoot):
    """
    System aggregate managing overall system state and operations.
    """

    def __init__(self):
        super().__init__()
        self._active_processes: Dict[ProcessId, ProcessAggregate] = {}
        self._system_parameters = ParameterAggregate()
        self._system_status = "idle"
        self._startup_time = datetime.utcnow()

    def start_process(self, recipe: Recipe, started_by: str, parameters: Dict[str, Any] = None) -> ProcessAggregate:
        """Start a new ALD process"""
        # Create process
        process_id = ProcessId("")  # Will generate UUID
        process = ALDProcess(
            process_id=process_id,
            recipe_id=recipe.recipe_id,
            status=ProcessStatus.IDLE,
            started_by=started_by,
            parameters=parameters or {}
        )

        # Create process aggregate
        process_aggregate = ProcessAggregate(process, recipe)

        # Add system parameters to process
        for param in self._system_parameters.get_all_parameters():
            process_aggregate.add_parameter(param)

        # Start the process
        if process_aggregate.start_process(started_by):
            self._active_processes[process_id] = process_aggregate
            self._update_system_status()
            self.mark_changed()

            # Add events from process aggregate
            for event in process_aggregate.get_domain_events():
                self.add_domain_event(event)
            process_aggregate.clear_domain_events()

            logger.info(f"Started new process {process_id}")
            return process_aggregate
        else:
            raise RuntimeError("Failed to start process")

    def get_process(self, process_id: ProcessId) -> Optional[ProcessAggregate]:
        """Get a process by ID"""
        return self._active_processes.get(process_id)

    def get_active_processes(self) -> List[ProcessAggregate]:
        """Get all active processes"""
        return [p for p in self._active_processes.values() if p.process.is_running()]

    def stop_process(self, process_id: ProcessId, stopped_by: str, reason: str = "manual_stop") -> bool:
        """Stop a process"""
        process_aggregate = self._active_processes.get(process_id)
        if not process_aggregate:
            return False

        success = process_aggregate.stop_process(stopped_by, reason)
        if success:
            # Add events from process aggregate
            for event in process_aggregate.get_domain_events():
                self.add_domain_event(event)
            process_aggregate.clear_domain_events()

            self._update_system_status()
            self.mark_changed()

        return success

    def add_system_parameter(self, parameter: Parameter):
        """Add a system-wide parameter"""
        self._system_parameters.add_parameter(parameter)

        # Add to all active processes
        for process_aggregate in self._active_processes.values():
            process_aggregate.add_parameter(parameter)

        self.mark_changed()

    def update_system_parameter(self, parameter_id: ParameterId, value: float, source: str = "plc") -> bool:
        """Update a system parameter value"""
        success = self._system_parameters.update_parameter_value(parameter_id, value, source)

        if success:
            # Update in all active processes
            for process_aggregate in self._active_processes.values():
                process_aggregate.update_parameter(parameter_id, value, source)

            # Add events from parameter aggregate
            for event in self._system_parameters.get_domain_events():
                self.add_domain_event(event)
            self._system_parameters.clear_domain_events()

            self.mark_changed()

        return success

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        active_processes = self.get_active_processes()

        return {
            'system_status': self._system_status,
            'startup_time': self._startup_time.isoformat(),
            'uptime_seconds': (datetime.utcnow() - self._startup_time).total_seconds(),
            'active_processes_count': len(active_processes),
            'total_processes_count': len(self._active_processes),
            'system_parameters_count': len(self._system_parameters.get_all_parameters()),
            'out_of_range_parameters': len(self._system_parameters.get_out_of_range_parameters())
        }

    def _update_system_status(self):
        """Update system status based on active processes"""
        active_processes = self.get_active_processes()

        if not active_processes:
            self._system_status = "idle"
        elif len(active_processes) == 1:
            self._system_status = "running"
        else:
            self._system_status = f"running_{len(active_processes)}_processes"