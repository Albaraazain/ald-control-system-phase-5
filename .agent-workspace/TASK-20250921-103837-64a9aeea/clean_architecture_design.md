# Clean Architecture Design for ALD Control System

## Architecture Overview

This document defines a comprehensive clean architecture implementation for the ALD control system, addressing critical issues identified by the architecture team:

- **Security**: Critical credential exposure and JSON deserialization vulnerabilities
- **Performance**: Sequential PLC reads and synchronous database operations
- **Data Integrity**: Race conditions and atomicity violations in dual-mode logging
- **Coupling**: Global singletons and tight coupling throughout the system
- **Testing**: Lack of unit testing and dependency injection support

## Clean Architecture Layers

### 1. Domain Layer (Core Business Logic)

#### Entities
```python
# src/domain/entities/recipe.py
@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    description: str
    steps: List['Step']
    parameters: Dict[str, 'Parameter']
    validation_rules: 'RecipeValidationRules'

    def validate(self) -> ValidationResult:
        """Validate recipe integrity and business rules"""

    def estimate_duration(self) -> Duration:
        """Calculate estimated execution time"""

# src/domain/entities/step.py
@dataclass(frozen=True)
class Step:
    id: str
    step_type: StepType
    configuration: 'StepConfiguration'
    order: int
    duration_ms: Optional[int]

    def execute(self, context: 'ExecutionContext') -> 'StepResult':
        """Execute step with given context"""

# src/domain/entities/parameter.py
@dataclass(frozen=True)
class Parameter:
    id: str
    name: str
    modbus_address: int
    data_type: ParameterDataType
    constraints: 'ParameterConstraints'
    read_frequency: Optional[int]

    def validate_value(self, value: Any) -> ValidationResult:
        """Validate parameter value against constraints"""

# src/domain/entities/process.py
@dataclass
class Process:
    id: str
    recipe_id: str
    machine_id: str
    status: ProcessStatus
    started_at: datetime
    completed_at: Optional[datetime]
    data_points: List['ProcessDataPoint']

    def transition_to(self, new_status: ProcessStatus) -> DomainEvent:
        """Transition process status with domain event"""
```

#### Value Objects
```python
# src/domain/value_objects/machine_state.py
@dataclass(frozen=True)
class MachineState:
    status: MachineStatus  # idle, processing, error, offline
    current_process_id: Optional[str]
    last_heartbeat: datetime
    error_message: Optional[str]

    def can_transition_to(self, new_status: MachineStatus) -> bool:
        """Validate state transition rules"""

# src/domain/value_objects/parameter_value.py
@dataclass(frozen=True)
class ParameterValue:
    parameter_id: str
    value: float
    timestamp: datetime
    quality: DataQuality
    source: str

    def is_within_bounds(self, constraints: ParameterConstraints) -> bool:
        """Check if value meets parameter constraints"""

# src/domain/value_objects/step_configuration.py
@dataclass(frozen=True)
class ValveStepConfiguration:
    valve_number: int
    open_state: bool
    duration_ms: int

@dataclass(frozen=True)
class PurgeStepConfiguration:
    duration_ms: int
    pressure_threshold: Optional[float]

@dataclass(frozen=True)
class ParameterStepConfiguration:
    parameter_id: str
    target_value: float
    tolerance: float
    timeout_ms: int
```

#### Domain Services
```python
# src/domain/services/recipe_validation_service.py
class RecipeValidationService:
    def validate_recipe(self, recipe: Recipe) -> ValidationResult:
        """Validate recipe structure and business rules"""

    def validate_step_sequence(self, steps: List[Step]) -> ValidationResult:
        """Validate step execution sequence"""

    def validate_parameter_constraints(self, recipe: Recipe) -> ValidationResult:
        """Validate all recipe parameters meet constraints"""

# src/domain/services/state_transition_service.py
class StateTransitionService:
    def validate_transition(
        self,
        current_state: MachineState,
        new_status: MachineStatus
    ) -> ValidationResult:
        """Validate machine state transition is allowed"""

    def create_transition_event(
        self,
        current_state: MachineState,
        new_status: MachineStatus,
        trigger: str
    ) -> DomainEvent:
        """Create domain event for state transition"""
```

#### Domain Events
```python
# src/domain/events/recipe_events.py
@dataclass(frozen=True)
class RecipeStarted(DomainEvent):
    recipe_id: str
    process_id: str
    machine_id: str
    started_by: str
    timestamp: datetime

@dataclass(frozen=True)
class RecipeCompleted(DomainEvent):
    recipe_id: str
    process_id: str
    machine_id: str
    duration_ms: int
    timestamp: datetime

# src/domain/events/parameter_events.py
@dataclass(frozen=True)
class ParameterValueChanged(DomainEvent):
    parameter_id: str
    old_value: Optional[float]
    new_value: float
    process_id: Optional[str]
    timestamp: datetime

@dataclass(frozen=True)
class ParameterValidationFailed(DomainEvent):
    parameter_id: str
    value: float
    constraint_violation: str
    timestamp: datetime
```

### 2. Application Layer (Use Cases & Orchestration)

#### Use Cases
```python
# src/application/use_cases/start_recipe_use_case.py
class StartRecipeUseCase:
    def __init__(
        self,
        recipe_repository: IRecipeRepository,
        process_repository: IProcessRepository,
        machine_repository: IMachineRepository,
        recipe_validation_service: RecipeValidationService,
        event_bus: IEventBus
    ):
        self._recipe_repo = recipe_repository
        self._process_repo = process_repository
        self._machine_repo = machine_repository
        self._validation_service = recipe_validation_service
        self._event_bus = event_bus

    async def execute(self, command: StartRecipeCommand) -> StartRecipeResult:
        # Validate machine is available
        machine = await self._machine_repo.get_by_id(command.machine_id)
        if machine.state.status != MachineStatus.IDLE:
            return StartRecipeResult.failure("Machine not available")

        # Load and validate recipe
        recipe = await self._recipe_repo.get_by_id(command.recipe_id)
        validation = self._validation_service.validate_recipe(recipe)
        if not validation.is_valid:
            return StartRecipeResult.failure(validation.errors)

        # Create process and transition machine state
        process = Process.create(recipe.id, machine.id, command.operator_id)
        await self._process_repo.save(process)

        # Atomically update machine state
        new_state = machine.state.transition_to_processing(process.id)
        await self._machine_repo.update_state(machine.id, new_state)

        # Publish domain event
        event = RecipeStarted(recipe.id, process.id, machine.id, command.operator_id)
        await self._event_bus.publish(event)

        return StartRecipeResult.success(process.id)

# src/application/use_cases/log_parameters_use_case.py
class LogParametersUseCase:
    """High-performance parameter logging with dual-mode support"""

    def __init__(
        self,
        plc_service: IPLCService,
        parameter_repository: IParameterRepository,
        data_logger: IDataLogger,
        machine_repository: IMachineRepository,
        event_bus: IEventBus
    ):
        self._plc_service = plc_service
        self._parameter_repo = parameter_repository
        self._data_logger = data_logger
        self._machine_repo = machine_repository
        self._event_bus = event_bus

    async def execute(self) -> LogParametersResult:
        # Atomic state read
        machine_state = await self._machine_repo.get_current_state()

        # Bulk parameter read from PLC
        parameters = await self._parameter_repo.get_active_parameters()
        parameter_values = await self._plc_service.read_parameters_bulk(parameters)

        # Validate parameter values
        validated_values = self._validate_parameter_values(parameter_values)

        # Log to appropriate tables based on machine state
        if machine_state.status == MachineStatus.PROCESSING:
            await self._data_logger.log_process_data(
                machine_state.current_process_id,
                validated_values
            )
        else:
            await self._data_logger.log_parameter_history(validated_values)

        # Publish parameter events for anomalies
        await self._publish_anomaly_events(validated_values)

        return LogParametersResult.success(len(validated_values))
```

#### Command/Query Handlers (CQRS)
```python
# src/application/commands/recipe_commands.py
@dataclass(frozen=True)
class StartRecipeCommand:
    recipe_id: str
    machine_id: str
    operator_id: str
    parameters_override: Dict[str, float] = field(default_factory=dict)

@dataclass(frozen=True)
class StopRecipeCommand:
    process_id: str
    reason: str
    operator_id: str

# src/application/queries/process_queries.py
@dataclass(frozen=True)
class GetProcessStatusQuery:
    process_id: str

@dataclass(frozen=True)
class GetMachineStateQuery:
    machine_id: str

# src/application/handlers/command_handlers.py
class RecipeCommandHandler:
    def __init__(
        self,
        start_recipe_use_case: StartRecipeUseCase,
        stop_recipe_use_case: StopRecipeUseCase
    ):
        self._start_recipe_use_case = start_recipe_use_case
        self._stop_recipe_use_case = stop_recipe_use_case

    async def handle(self, command: Command) -> CommandResult:
        match command:
            case StartRecipeCommand() as cmd:
                return await self._start_recipe_use_case.execute(cmd)
            case StopRecipeCommand() as cmd:
                return await self._stop_recipe_use_case.execute(cmd)
            case _:
                raise UnsupportedCommandError(type(command))
```

#### Application Services
```python
# src/application/services/parameter_logging_service.py
class ParameterLoggingService:
    """High-level service orchestrating parameter logging"""

    def __init__(
        self,
        log_parameters_use_case: LogParametersUseCase,
        scheduler: ITaskScheduler,
        performance_monitor: IPerformanceMonitor
    ):
        self._log_parameters_use_case = log_parameters_use_case
        self._scheduler = scheduler
        self._performance_monitor = performance_monitor

    async def start_continuous_logging(self):
        """Start 1-second interval parameter logging"""
        await self._scheduler.schedule_repeating(
            task=self._log_parameters_with_monitoring,
            interval_ms=1000,
            jitter_tolerance_ms=10
        )

    async def _log_parameters_with_monitoring(self):
        with self._performance_monitor.measure("parameter_logging"):
            result = await self._log_parameters_use_case.execute()
            if not result.is_success:
                await self._handle_logging_error(result.error)
```

### 3. Infrastructure Layer (External Dependencies)

#### Repository Implementations
```python
# src/infrastructure/repositories/supabase_recipe_repository.py
class SupabaseRecipeRepository(IRecipeRepository):
    def __init__(self, db_pool: AsyncDatabasePool):
        self._db_pool = db_pool

    async def get_by_id(self, recipe_id: str) -> Recipe:
        async with self._db_pool.acquire() as conn:
            recipe_data = await conn.fetch_one(
                "SELECT * FROM recipes WHERE id = $1", recipe_id
            )
            steps_data = await conn.fetch_all(
                "SELECT * FROM recipe_steps WHERE recipe_id = $1 ORDER BY step_order",
                recipe_id
            )
            return self._map_to_domain(recipe_data, steps_data)

    async def save(self, recipe: Recipe) -> None:
        async with self._db_pool.transaction() as trans:
            await trans.execute(
                "INSERT INTO recipes (id, name, description) VALUES ($1, $2, $3)",
                recipe.id, recipe.name, recipe.description
            )
            for step in recipe.steps:
                await trans.execute(
                    "INSERT INTO recipe_steps (...) VALUES (...)",
                    # step data
                )

# src/infrastructure/repositories/supabase_parameter_repository.py
class SupabaseParameterRepository(IParameterRepository):
    def __init__(self, db_pool: AsyncDatabasePool, cache: ICache):
        self._db_pool = db_pool
        self._cache = cache

    async def get_active_parameters(self) -> List[Parameter]:
        # Check cache first for performance
        cached = await self._cache.get("active_parameters")
        if cached:
            return cached

        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch_all(
                "SELECT * FROM parameters WHERE active = true"
            )
            parameters = [self._map_to_domain(row) for row in rows]
            await self._cache.set("active_parameters", parameters, ttl_seconds=60)
            return parameters
```

#### External Service Adapters
```python
# src/infrastructure/adapters/modbus_plc_adapter.py
class ModbusPLCAdapter(IPLCService):
    def __init__(
        self,
        connection_pool: ModbusConnectionPool,
        performance_monitor: IPerformanceMonitor
    ):
        self._connection_pool = connection_pool
        self._performance_monitor = performance_monitor

    async def read_parameters_bulk(
        self,
        parameters: List[Parameter]
    ) -> List[ParameterValue]:
        """High-performance bulk parameter reading"""

        # Group parameters by address ranges for bulk reads
        address_groups = self._group_by_address_ranges(parameters)

        # Read all groups concurrently
        tasks = [
            self._read_address_group(group)
            for group in address_groups
        ]

        with self._performance_monitor.measure("bulk_plc_read"):
            group_results = await asyncio.gather(*tasks)

        # Flatten and map to parameter values
        return self._map_to_parameter_values(group_results, parameters)

    async def _read_address_group(
        self,
        group: AddressGroup
    ) -> List[RawValue]:
        async with self._connection_pool.acquire() as client:
            return await client.read_holding_registers(
                group.start_address,
                group.count
            )

# src/infrastructure/adapters/supabase_data_logger.py
class SupabaseDataLogger(IDataLogger):
    def __init__(self, db_pool: AsyncDatabasePool):
        self._db_pool = db_pool

    async def log_process_data(
        self,
        process_id: str,
        parameter_values: List[ParameterValue]
    ) -> None:
        """Atomic dual-table logging for process mode"""

        async with self._db_pool.transaction() as trans:
            # Insert to parameter_value_history
            await self._bulk_insert_parameter_history(trans, parameter_values)

            # Insert to process_data_points
            process_data_points = [
                ProcessDataPoint.from_parameter_value(pv, process_id)
                for pv in parameter_values
            ]
            await self._bulk_insert_process_data(trans, process_data_points)

    async def log_parameter_history(
        self,
        parameter_values: List[ParameterValue]
    ) -> None:
        """Single-table logging for idle mode"""

        async with self._db_pool.acquire() as conn:
            await self._bulk_insert_parameter_history(conn, parameter_values)
```

### 4. Interface Adapters Layer (Controllers & Presenters)

#### Controllers
```python
# src/interfaces/controllers/command_controller.py
class CommandController:
    def __init__(
        self,
        command_bus: ICommandBus,
        logger: ILogger,
        auth_service: IAuthenticationService
    ):
        self._command_bus = command_bus
        self._logger = logger
        self._auth_service = auth_service

    async def handle_supabase_command(self, command_data: Dict[str, Any]) -> None:
        """Handle incoming commands from Supabase realtime"""

        try:
            # Authenticate and authorize
            operator = await self._auth_service.authenticate(command_data)

            # Parse command
            command = self._parse_command(command_data)

            # Execute via command bus
            result = await self._command_bus.execute(command)

            # Log result
            await self._log_command_result(command, result, operator.id)

        except Exception as e:
            await self._handle_command_error(command_data, e)

# src/interfaces/controllers/parameter_controller.py
class ParameterController:
    def __init__(
        self,
        query_bus: IQueryBus,
        parameter_formatter: IParameterFormatter
    ):
        self._query_bus = query_bus
        self._formatter = parameter_formatter

    async def get_current_parameters(
        self,
        machine_id: str
    ) -> ParameterResponse:
        query = GetCurrentParametersQuery(machine_id)
        result = await self._query_bus.execute(query)
        return self._formatter.format_parameters(result.parameters)
```

#### Presenters & Response Models
```python
# src/interfaces/presenters/process_presenter.py
class ProcessPresenter:
    def present_process_status(self, process: Process) -> ProcessStatusResponse:
        return ProcessStatusResponse(
            id=process.id,
            recipe_name=process.recipe.name,
            status=process.status.value,
            started_at=process.started_at.isoformat(),
            progress_percentage=self._calculate_progress(process),
            current_step=self._get_current_step_name(process),
            estimated_completion=self._estimate_completion(process)
        )

# src/interfaces/response_models/process_responses.py
@dataclass(frozen=True)
class ProcessStatusResponse:
    id: str
    recipe_name: str
    status: str
    started_at: str
    progress_percentage: float
    current_step: str
    estimated_completion: Optional[str]
```

### 5. Event-Driven Architecture

#### Event Bus Implementation
```python
# src/infrastructure/events/async_event_bus.py
class AsyncEventBus(IEventBus):
    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[IEventHandler]] = {}
        self._middleware: List[IEventMiddleware] = []

    def subscribe(self, event_type: Type[DomainEvent], handler: IEventHandler):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        # Apply middleware (logging, metrics, etc.)
        for middleware in self._middleware:
            await middleware.before_publish(event)

        # Get handlers for event type
        handlers = self._handlers.get(type(event), [])

        # Execute all handlers concurrently
        if handlers:
            tasks = [handler.handle(event) for handler in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Apply middleware after
        for middleware in self._middleware:
            await middleware.after_publish(event)

# src/application/events/handlers/parameter_event_handlers.py
class ParameterAnomalyHandler(IEventHandler[ParameterValidationFailed]):
    def __init__(self, alert_service: IAlertService):
        self._alert_service = alert_service

    async def handle(self, event: ParameterValidationFailed) -> None:
        await self._alert_service.send_alert(
            AlertType.PARAMETER_ANOMALY,
            f"Parameter {event.parameter_id} validation failed: {event.constraint_violation}",
            severity=AlertSeverity.HIGH
        )

class StateTransitionHandler(IEventHandler[MachineStateChanged]):
    def __init__(self, notification_service: INotificationService):
        self._notification_service = notification_service

    async def handle(self, event: MachineStateChanged) -> None:
        await self._notification_service.notify_state_change(
            event.machine_id,
            event.old_status,
            event.new_status
        )
```

### 6. Dependency Injection Container Integration

```python
# src/infrastructure/di/container_builder.py
class ContainerBuilder:
    def __init__(self):
        self._container = Container()

    def build_production_container(self) -> Container:
        # Infrastructure layer
        self._register_database_services()
        self._register_plc_services()
        self._register_external_services()

        # Domain services
        self._register_domain_services()

        # Application layer
        self._register_use_cases()
        self._register_command_handlers()
        self._register_event_handlers()

        # Interface adapters
        self._register_controllers()
        self._register_presenters()

        return self._container

    def _register_database_services(self):
        self._container.register(
            IAsyncDatabasePool,
            lambda: AsyncDatabasePool(DATABASE_CONFIG),
            lifestyle=Lifestyle.SINGLETON
        )

        self._container.register(
            IRecipeRepository,
            SupabaseRecipeRepository,
            lifestyle=Lifestyle.SCOPED
        )

    def _register_use_cases(self):
        self._container.register(
            StartRecipeUseCase,
            lifestyle=Lifestyle.SCOPED
        )

        self._container.register(
            LogParametersUseCase,
            lifestyle=Lifestyle.SCOPED
        )
```

## Migration Strategy Integration

This clean architecture design coordinates with the migration strategy:

1. **Phase 1**: Implement DI container and interfaces
2. **Phase 2**: Create adapters for existing services
3. **Phase 3**: Gradually migrate use cases
4. **Phase 4**: Remove legacy implementations

## Performance Considerations

- **Async everywhere**: All I/O operations are async
- **Bulk operations**: PLC reads and database writes are batched
- **Connection pooling**: Database and PLC connections are pooled
- **Caching**: Parameter metadata and configuration are cached
- **Event-driven**: Loose coupling through domain events

## Security Integration

- **Secure configuration**: Credentials managed through DI
- **Input validation**: All inputs validated at domain boundaries
- **Authentication**: Integrated into controllers
- **Audit logging**: All operations logged through events

## Data Integrity Integration

- **Atomic operations**: Database transactions ensure consistency
- **Event sourcing**: State changes tracked through events
- **Validation**: Domain-driven validation at all layers
- **Monitoring**: Real-time data quality monitoring

This design provides a solid foundation for the architectural overhaul while addressing all critical issues identified by the specialist agents.