# Application Layer Implementation for Clean Architecture

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

# Import domain interfaces (in real implementation, these would be proper imports)
from domain_interfaces import (
    DomainEvent, ParameterValue, MachineState, MachineStatus, ProcessStatus,
    IRecipeRepository, IParameterRepository, IProcessRepository, IMachineRepository,
    IPLCService, IDataLogger, IEventBus, RecipeValidationService, StateTransitionService,
    ValidationResult, ValidationException
)

# Command/Query Separation (CQRS)
class Command:
    """Base class for all commands"""
    pass

class Query:
    """Base class for all queries"""
    pass

# Commands
@dataclass(frozen=True)
class StartRecipeCommand(Command):
    recipe_id: str
    machine_id: str
    operator_id: str
    parameters_override: Dict[str, float] = field(default_factory=dict)

@dataclass(frozen=True)
class StopRecipeCommand(Command):
    process_id: str
    reason: str
    operator_id: str

@dataclass(frozen=True)
class SetParameterCommand(Command):
    parameter_id: str
    value: float
    operator_id: str

@dataclass(frozen=True)
class ControlValveCommand(Command):
    valve_number: int
    open_state: bool
    duration_ms: Optional[int]
    operator_id: str

# Queries
@dataclass(frozen=True)
class GetProcessStatusQuery(Query):
    process_id: str

@dataclass(frozen=True)
class GetMachineStateQuery(Query):
    machine_id: str

@dataclass(frozen=True)
class GetCurrentParametersQuery(Query):
    machine_id: str

@dataclass(frozen=True)
class GetProcessHistoryQuery(Query):
    machine_id: str
    limit: int = 100

# Results
@dataclass(frozen=True)
class CommandResult:
    is_success: bool
    error_message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, data: Optional[Dict[str, Any]] = None) -> 'CommandResult':
        return cls(is_success=True, data=data)

    @classmethod
    def failure(cls, error_message: str) -> 'CommandResult':
        return cls(is_success=False, error_message=error_message)

@dataclass(frozen=True)
class QueryResult:
    is_success: bool
    data: Optional[Any] = None
    error_message: Optional[str] = None

    @classmethod
    def success(cls, data: Any) -> 'QueryResult':
        return cls(is_success=True, data=data)

    @classmethod
    def failure(cls, error_message: str) -> 'QueryResult':
        return cls(is_success=False, error_message=error_message)

# Bus Interfaces
class ICommandBus(ABC):
    @abstractmethod
    async def execute(self, command: Command) -> CommandResult:
        pass

class IQueryBus(ABC):
    @abstractmethod
    async def execute(self, query: Query) -> QueryResult:
        pass

# Use Cases
class StartRecipeUseCase:
    """Use case for starting a recipe execution"""

    def __init__(
        self,
        recipe_repository: IRecipeRepository,
        process_repository: IProcessRepository,
        machine_repository: IMachineRepository,
        recipe_validation_service: RecipeValidationService,
        state_transition_service: StateTransitionService,
        event_bus: IEventBus
    ):
        self._recipe_repo = recipe_repository
        self._process_repo = process_repository
        self._machine_repo = machine_repository
        self._validation_service = recipe_validation_service
        self._state_transition_service = state_transition_service
        self._event_bus = event_bus

    async def execute(self, command: StartRecipeCommand) -> CommandResult:
        try:
            # Check if machine is available
            current_state = await self._machine_repo.get_current_state(command.machine_id)
            if current_state.status != MachineStatus.IDLE:
                return CommandResult.failure(f"Machine {command.machine_id} is not idle (status: {current_state.status})")

            # Load and validate recipe
            recipe = await self._recipe_repo.get_by_id(command.recipe_id)
            validation = self._validation_service.validate_recipe(recipe)
            if not validation.is_valid:
                return CommandResult.failure(f"Recipe validation failed: {', '.join(validation.errors)}")

            # Create new process
            process = Process.create(
                recipe_id=command.recipe_id,
                machine_id=command.machine_id,
                operator_id=command.operator_id,
                parameters_override=command.parameters_override
            )

            # Atomically update machine state and save process
            new_state = current_state.transition_to_processing(process.id)

            # Save process first
            await self._process_repo.save(process)

            # Then update machine state
            await self._machine_repo.update_state(command.machine_id, new_state)

            # Publish domain event
            event = RecipeStarted(
                aggregate_id=process.id,
                recipe_id=command.recipe_id,
                process_id=process.id,
                machine_id=command.machine_id,
                started_by=command.operator_id
            )
            await self._event_bus.publish(event)

            return CommandResult.success({"process_id": process.id})

        except Exception as e:
            return CommandResult.failure(f"Failed to start recipe: {str(e)}")

class StopRecipeUseCase:
    """Use case for stopping a recipe execution"""

    def __init__(
        self,
        process_repository: IProcessRepository,
        machine_repository: IMachineRepository,
        state_transition_service: StateTransitionService,
        event_bus: IEventBus
    ):
        self._process_repo = process_repository
        self._machine_repo = machine_repository
        self._state_transition_service = state_transition_service
        self._event_bus = event_bus

    async def execute(self, command: StopRecipeCommand) -> CommandResult:
        try:
            # Get current process
            process = await self._process_repo.get_by_id(command.process_id)
            if process.status not in [ProcessStatus.RUNNING, ProcessStatus.PENDING]:
                return CommandResult.failure(f"Process {command.process_id} is not running (status: {process.status})")

            # Update process status
            process.abort(command.reason, command.operator_id)
            await self._process_repo.save(process)

            # Update machine state to idle
            current_state = await self._machine_repo.get_current_state(process.machine_id)
            new_state = current_state.transition_to_idle()
            await self._machine_repo.update_state(process.machine_id, new_state)

            # Publish domain event
            event = RecipeAborted(
                aggregate_id=process.id,
                recipe_id=process.recipe_id,
                process_id=process.id,
                machine_id=process.machine_id,
                reason=command.reason,
                aborted_by=command.operator_id
            )
            await self._event_bus.publish(event)

            return CommandResult.success({"process_id": process.id, "status": "aborted"})

        except Exception as e:
            return CommandResult.failure(f"Failed to stop recipe: {str(e)}")

class LogParametersUseCase:
    """High-performance parameter logging use case with dual-mode support"""

    def __init__(
        self,
        plc_service: IPLCService,
        parameter_repository: IParameterRepository,
        data_logger: IDataLogger,
        machine_repository: IMachineRepository,
        event_bus: IEventBus,
        performance_monitor: 'IPerformanceMonitor'
    ):
        self._plc_service = plc_service
        self._parameter_repo = parameter_repository
        self._data_logger = data_logger
        self._machine_repo = machine_repository
        self._event_bus = event_bus
        self._performance_monitor = performance_monitor

    async def execute(self) -> CommandResult:
        try:
            with self._performance_monitor.measure("parameter_logging_cycle"):
                # Step 1: Atomic state read (critical for race condition prevention)
                machine_state = await self._machine_repo.get_current_state("default_machine")

                # Step 2: Get active parameters with caching
                with self._performance_monitor.measure("parameter_metadata_fetch"):
                    parameters = await self._parameter_repo.get_active_parameters()

                if not parameters:
                    return CommandResult.success({"logged_count": 0, "message": "No active parameters"})

                # Step 3: Bulk parameter read from PLC (high-performance)
                with self._performance_monitor.measure("bulk_plc_read"):
                    parameter_values = await self._plc_service.read_parameters_bulk(parameters)

                # Step 4: Validate parameter values and detect anomalies
                with self._performance_monitor.measure("parameter_validation"):
                    validated_values, anomalies = await self._validate_and_filter_values(
                        parameter_values, parameters
                    )

                # Step 5: Log to appropriate tables based on machine state (atomic operation)
                with self._performance_monitor.measure("database_logging"):
                    if machine_state.status == MachineStatus.PROCESSING and machine_state.current_process_id:
                        # Process mode: dual-table logging
                        await self._data_logger.log_process_data(
                            machine_state.current_process_id,
                            validated_values
                        )
                        logging_mode = "process_mode"
                    else:
                        # Idle mode: single-table logging
                        await self._data_logger.log_parameter_history(validated_values)
                        logging_mode = "idle_mode"

                # Step 6: Publish anomaly events asynchronously
                if anomalies:
                    await self._publish_anomaly_events(anomalies, machine_state.current_process_id)

                return CommandResult.success({
                    "logged_count": len(validated_values),
                    "anomaly_count": len(anomalies),
                    "logging_mode": logging_mode,
                    "machine_status": machine_state.status.value
                })

        except Exception as e:
            # Log error but don't break the continuous logging cycle
            await self._event_bus.publish(ParameterLoggingFailed(
                error_message=str(e),
                timestamp=datetime.utcnow()
            ))
            return CommandResult.failure(f"Parameter logging failed: {str(e)}")

    async def _validate_and_filter_values(
        self,
        parameter_values: List[ParameterValue],
        parameters: List['Parameter']
    ) -> tuple[List[ParameterValue], List[ParameterValue]]:
        """Validate parameter values and separate normal values from anomalies"""

        validated_values = []
        anomalies = []

        # Create parameter lookup for constraints
        param_lookup = {p.id: p for p in parameters}

        for value in parameter_values:
            parameter = param_lookup.get(value.parameter_id)
            if not parameter:
                anomalies.append(value)
                continue

            # Validate against constraints
            validation = value.is_valid_for_constraints(parameter.constraints)
            if validation.is_valid:
                validated_values.append(value)
            else:
                anomalies.append(value)

        return validated_values, anomalies

    async def _publish_anomaly_events(
        self,
        anomalies: List[ParameterValue],
        process_id: Optional[str]
    ):
        """Publish parameter validation failed events for anomalies"""

        for anomaly in anomalies:
            event = ParameterValidationFailed(
                aggregate_id=anomaly.parameter_id,
                parameter_id=anomaly.parameter_id,
                value=anomaly.value,
                constraint_violation="Value outside acceptable range",
                process_id=process_id
            )
            await self._event_bus.publish(event)

class SetParameterUseCase:
    """Use case for setting parameter values"""

    def __init__(
        self,
        plc_service: IPLCService,
        parameter_repository: IParameterRepository,
        event_bus: IEventBus
    ):
        self._plc_service = plc_service
        self._parameter_repo = parameter_repository
        self._event_bus = event_bus

    async def execute(self, command: SetParameterCommand) -> CommandResult:
        try:
            # Get parameter definition
            parameter = await self._parameter_repo.get_by_id(command.parameter_id)

            # Validate value against constraints
            validation = parameter.constraints.validate_value(command.value)
            if not validation.is_valid:
                return CommandResult.failure(f"Parameter validation failed: {', '.join(validation.errors)}")

            # Write to PLC
            success = await self._plc_service.write_parameter(command.parameter_id, command.value)
            if not success:
                return CommandResult.failure("Failed to write parameter to PLC")

            # Publish domain event
            event = ParameterValueChanged(
                aggregate_id=command.parameter_id,
                parameter_id=command.parameter_id,
                old_value=None,  # TODO: Read current value first
                new_value=command.value,
                process_id=None  # TODO: Get current process if any
            )
            await self._event_bus.publish(event)

            return CommandResult.success({
                "parameter_id": command.parameter_id,
                "new_value": command.value
            })

        except Exception as e:
            return CommandResult.failure(f"Failed to set parameter: {str(e)}")

# Command and Query Handlers
class CommandHandler:
    """Main command handler routing commands to appropriate use cases"""

    def __init__(
        self,
        start_recipe_use_case: StartRecipeUseCase,
        stop_recipe_use_case: StopRecipeUseCase,
        set_parameter_use_case: SetParameterUseCase
    ):
        self._start_recipe_use_case = start_recipe_use_case
        self._stop_recipe_use_case = stop_recipe_use_case
        self._set_parameter_use_case = set_parameter_use_case

    async def handle(self, command: Command) -> CommandResult:
        """Route command to appropriate use case"""

        match command:
            case StartRecipeCommand() as cmd:
                return await self._start_recipe_use_case.execute(cmd)
            case StopRecipeCommand() as cmd:
                return await self._stop_recipe_use_case.execute(cmd)
            case SetParameterCommand() as cmd:
                return await self._set_parameter_use_case.execute(cmd)
            case _:
                return CommandResult.failure(f"Unsupported command type: {type(command)}")

class QueryHandler:
    """Main query handler for read operations"""

    def __init__(
        self,
        process_repository: IProcessRepository,
        machine_repository: IMachineRepository,
        parameter_repository: IParameterRepository
    ):
        self._process_repo = process_repository
        self._machine_repo = machine_repository
        self._parameter_repo = parameter_repository

    async def handle(self, query: Query) -> QueryResult:
        """Route query to appropriate handler"""

        try:
            match query:
                case GetProcessStatusQuery() as q:
                    process = await self._process_repo.get_by_id(q.process_id)
                    return QueryResult.success(process)

                case GetMachineStateQuery() as q:
                    state = await self._machine_repo.get_current_state(q.machine_id)
                    return QueryResult.success(state)

                case GetCurrentParametersQuery() as q:
                    parameters = await self._parameter_repo.get_active_parameters()
                    return QueryResult.success(parameters)

                case GetProcessHistoryQuery() as q:
                    history = await self._process_repo.get_process_history(q.machine_id, q.limit)
                    return QueryResult.success(history)

                case _:
                    return QueryResult.failure(f"Unsupported query type: {type(query)}")

        except Exception as e:
            return QueryResult.failure(f"Query execution failed: {str(e)}")

# Application Services
class ParameterLoggingService:
    """High-level service orchestrating continuous parameter logging"""

    def __init__(
        self,
        log_parameters_use_case: LogParametersUseCase,
        scheduler: 'ITaskScheduler',
        performance_monitor: 'IPerformanceMonitor',
        health_monitor: 'IHealthMonitor'
    ):
        self._log_parameters_use_case = log_parameters_use_case
        self._scheduler = scheduler
        self._performance_monitor = performance_monitor
        self._health_monitor = health_monitor
        self._is_running = False

    async def start_continuous_logging(self):
        """Start 1-second interval parameter logging with performance monitoring"""

        if self._is_running:
            return

        self._is_running = True

        # Schedule repeating task with high precision
        await self._scheduler.schedule_repeating(
            task=self._log_parameters_with_monitoring,
            interval_ms=1000,
            jitter_tolerance_ms=10,  # Allow max 10ms jitter
            max_retries=3
        )

    async def stop_continuous_logging(self):
        """Stop continuous parameter logging"""
        self._is_running = False
        await self._scheduler.cancel_all_tasks()

    async def _log_parameters_with_monitoring(self):
        """Execute parameter logging with comprehensive monitoring"""

        start_time = datetime.utcnow()

        try:
            # Execute parameter logging
            result = await self._log_parameters_use_case.execute()

            # Calculate execution time
            execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update health metrics
            await self._health_monitor.record_cycle(
                success=result.is_success,
                execution_time_ms=execution_time_ms,
                logged_count=result.data.get('logged_count', 0) if result.data else 0
            )

            # Performance monitoring
            self._performance_monitor.record_metric("parameter_logging_cycle_time", execution_time_ms)

            if not result.is_success:
                await self._handle_logging_error(result.error_message)

        except Exception as e:
            await self._handle_logging_error(str(e))

    async def _handle_logging_error(self, error_message: str):
        """Handle parameter logging errors with appropriate recovery"""

        await self._health_monitor.record_error(error_message)

        # TODO: Implement error recovery strategies:
        # - Exponential backoff for transient errors
        # - Circuit breaker for persistent PLC issues
        # - Fallback to cached parameter values
        # - Alert notifications for critical failures

# Bus Implementations
class InMemoryCommandBus(ICommandBus):
    """Simple in-memory command bus implementation"""

    def __init__(self, command_handler: CommandHandler):
        self._command_handler = command_handler

    async def execute(self, command: Command) -> CommandResult:
        return await self._command_handler.handle(command)

class InMemoryQueryBus(IQueryBus):
    """Simple in-memory query bus implementation"""

    def __init__(self, query_handler: QueryHandler):
        self._query_handler = query_handler

    async def execute(self, query: Query) -> QueryResult:
        return await self._query_handler.handle(query)

# Additional Domain Events for Application Layer
@dataclass(frozen=True)
class ParameterLoggingFailed(DomainEvent):
    error_message: str

# Performance and Health Monitoring Interfaces
class IPerformanceMonitor(ABC):
    @abstractmethod
    def measure(self, operation_name: str) -> 'PerformanceContext':
        pass

    @abstractmethod
    def record_metric(self, metric_name: str, value: float) -> None:
        pass

class IHealthMonitor(ABC):
    @abstractmethod
    async def record_cycle(self, success: bool, execution_time_ms: float, logged_count: int) -> None:
        pass

    @abstractmethod
    async def record_error(self, error_message: str) -> None:
        pass

class ITaskScheduler(ABC):
    @abstractmethod
    async def schedule_repeating(
        self,
        task: callable,
        interval_ms: int,
        jitter_tolerance_ms: int = 0,
        max_retries: int = 0
    ) -> None:
        pass

    @abstractmethod
    async def cancel_all_tasks(self) -> None:
        pass

# This application layer provides:
# 1. Clean separation of commands and queries (CQRS)
# 2. Use cases that encapsulate business logic
# 3. High-performance parameter logging with monitoring
# 4. Event-driven architecture integration
# 5. Error handling and recovery mechanisms
# 6. Performance monitoring and health checks