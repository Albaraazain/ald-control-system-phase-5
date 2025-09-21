# ALD Control System - Architectural Blueprint v2.0

## Executive Summary

This blueprint defines the complete architectural redesign for the ALD Control System, implementing dependency injection, clean architecture, and event-driven state management to address critical issues:

- **Critical Security Issues**: Credential exposure, insecure JSON deserialization
- **Data Integrity Issues**: Race conditions, atomicity violations, consistency issues
- **Performance Bottlenecks**: Sequential operations, blocking I/O, no caching
- **Architectural Issues**: Tight coupling, global singletons, mixed concerns

## High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   CLI/API    │  │   Events     │  │   Monitoring │         │
│  │ Controllers  │  │ Handlers     │  │  Dashboard   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                 Application Layer (Use Cases)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Command    │  │    Query     │  │   Event      │         │
│  │  Handlers    │  │  Handlers    │  │  Handlers    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Domain Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Entities   │  │  Value       │  │   Domain     │         │
│  │              │  │  Objects     │  │   Events     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Domain     │  │  Aggregates  │  │   State      │         │
│  │  Services    │  │              │  │   Machine    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Repositories │  │   PLC        │  │   Event      │         │
│  │              │  │  Adapters    │  │   Store      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Database    │  │  File System │  │  External    │         │
│  │  Adapters    │  │  Adapters    │  │  Services    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Dependency Injection Framework

### 1.1 IoC Container Design

```python
# File: src/infrastructure/di/container.py
from typing import TypeVar, Type, Dict, Any, Callable, Optional
from enum import Enum
import asyncio
import inspect

T = TypeVar('T')

class Lifetime(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"

class DIContainer:
    """Dependency Injection Container with lifecycle management"""

    def __init__(self):
        self._services: Dict[str, ServiceDescriptor] = {}
        self._instances: Dict[str, Any] = {}
        self._scoped_instances: Dict[str, Dict[str, Any]] = {}
        self._circular_detection: set = set()

    def register_singleton(self, interface: Type[T], implementation: Type[T]) -> 'DIContainer':
        """Register a singleton service"""
        self._services[interface.__name__] = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=Lifetime.SINGLETON
        )
        return self

    def register_transient(self, interface: Type[T], implementation: Type[T]) -> 'DIContainer':
        """Register a transient service"""
        self._services[interface.__name__] = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=Lifetime.TRANSIENT
        )
        return self

    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> 'DIContainer':
        """Register a factory function"""
        self._services[interface.__name__] = ServiceDescriptor(
            interface=interface,
            factory=factory,
            lifetime=Lifetime.TRANSIENT
        )
        return self

    async def resolve(self, interface: Type[T], scope_id: Optional[str] = None) -> T:
        """Resolve a service instance"""
        service_name = interface.__name__

        if service_name not in self._services:
            raise ValueError(f"Service {service_name} not registered")

        descriptor = self._services[service_name]

        # Circular dependency detection
        if service_name in self._circular_detection:
            raise ValueError(f"Circular dependency detected for {service_name}")

        try:
            self._circular_detection.add(service_name)

            if descriptor.lifetime == Lifetime.SINGLETON:
                return await self._resolve_singleton(descriptor)
            elif descriptor.lifetime == Lifetime.SCOPED and scope_id:
                return await self._resolve_scoped(descriptor, scope_id)
            else:
                return await self._resolve_transient(descriptor)

        finally:
            self._circular_detection.discard(service_name)

    async def _resolve_singleton(self, descriptor: 'ServiceDescriptor') -> Any:
        """Resolve singleton instance"""
        service_name = descriptor.interface.__name__

        if service_name not in self._instances:
            self._instances[service_name] = await self._create_instance(descriptor)

        return self._instances[service_name]

    async def _resolve_scoped(self, descriptor: 'ServiceDescriptor', scope_id: str) -> Any:
        """Resolve scoped instance"""
        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = {}

        service_name = descriptor.interface.__name__

        if service_name not in self._scoped_instances[scope_id]:
            self._scoped_instances[scope_id][service_name] = await self._create_instance(descriptor)

        return self._scoped_instances[scope_id][service_name]

    async def _resolve_transient(self, descriptor: 'ServiceDescriptor') -> Any:
        """Resolve transient instance"""
        return await self._create_instance(descriptor)

    async def _create_instance(self, descriptor: 'ServiceDescriptor') -> Any:
        """Create service instance with dependency injection"""
        if descriptor.factory:
            if asyncio.iscoroutinefunction(descriptor.factory):
                return await descriptor.factory()
            else:
                return descriptor.factory()

        # Get constructor dependencies
        constructor = descriptor.implementation.__init__
        sig = inspect.signature(constructor)

        dependencies = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            if param.annotation != inspect.Parameter.empty:
                dependency = await self.resolve(param.annotation)
                dependencies[param_name] = dependency

        # Create instance
        instance = descriptor.implementation(**dependencies)

        # Initialize if async
        if hasattr(instance, 'initialize') and asyncio.iscoroutinefunction(instance.initialize):
            await instance.initialize()

        return instance

class ServiceDescriptor:
    """Service registration descriptor"""

    def __init__(self, interface: Type, implementation: Type = None,
                 factory: Callable = None, lifetime: Lifetime = Lifetime.TRANSIENT):
        self.interface = interface
        self.implementation = implementation
        self.factory = factory
        self.lifetime = lifetime
```

### 1.2 Service Locator Pattern

```python
# File: src/infrastructure/di/service_locator.py
from typing import TypeVar, Type, Optional
from .container import DIContainer

T = TypeVar('T')

class ServiceLocator:
    """Centralized service access point"""

    _container: Optional[DIContainer] = None
    _scope_id: Optional[str] = None

    @classmethod
    def configure(cls, container: DIContainer):
        """Configure the service locator with a container"""
        cls._container = container

    @classmethod
    async def get(cls, interface: Type[T]) -> T:
        """Get service instance"""
        if cls._container is None:
            raise RuntimeError("ServiceLocator not configured")

        return await cls._container.resolve(interface, cls._scope_id)

    @classmethod
    def set_scope(cls, scope_id: str):
        """Set current scope for scoped services"""
        cls._scope_id = scope_id

    @classmethod
    def clear_scope(cls):
        """Clear current scope"""
        cls._scope_id = None
```

## 2. Event-Driven State Management

### 2.1 Domain Events System

```python
# File: src/domain/events/event_system.py
from typing import List, Dict, Type, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import asyncio
import uuid

@dataclass
class DomainEvent(ABC):
    """Base class for all domain events"""
    event_id: str = None
    timestamp: datetime = None
    aggregate_id: str = None

    def __post_init__(self):
        if self.event_id is None:
            self.event_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

@dataclass
class ProcessStartedEvent(DomainEvent):
    """Event fired when a process starts"""
    process_id: str
    recipe_id: str
    machine_id: str

@dataclass
class ProcessStoppedEvent(DomainEvent):
    """Event fired when a process stops"""
    process_id: str
    reason: str
    machine_id: str

@dataclass
class MachineStateChangedEvent(DomainEvent):
    """Event fired when machine state changes"""
    machine_id: str
    old_state: str
    new_state: str
    process_id: Optional[str] = None

class EventHandler(ABC):
    """Base class for event handlers"""

    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle the event"""
        pass

class EventBus:
    """Event bus for publishing and subscribing to domain events"""

    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[EventHandler]] = {}
        self._event_store: List[DomainEvent] = []

    def subscribe(self, event_type: Type[DomainEvent], handler: EventHandler):
        """Subscribe to an event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent):
        """Publish an event to all subscribers"""
        # Store event for event sourcing
        self._event_store.append(event)

        # Get handlers for this event type
        handlers = self._handlers.get(type(event), [])

        # Execute all handlers concurrently
        if handlers:
            tasks = [handler.handle(event) for handler in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_events(self, aggregate_id: str = None) -> List[DomainEvent]:
        """Get events from store"""
        if aggregate_id:
            return [e for e in self._event_store if e.aggregate_id == aggregate_id]
        return self._event_store.copy()
```

### 2.2 State Machine Implementation

```python
# File: src/domain/state/machine_state.py
from enum import Enum
from typing import Dict, Set, Optional
from dataclasses import dataclass
from .events import EventBus, MachineStateChangedEvent

class MachineState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    PROCESSING = "processing"
    STOPPING = "stopping"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class ProcessState(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ERROR = "error"

@dataclass
class StateTransition:
    from_state: MachineState
    to_state: MachineState
    event: str
    guard: Optional[Callable] = None

class MachineStateMachine:
    """Finite state machine for machine state management"""

    def __init__(self, event_bus: EventBus, machine_id: str):
        self._event_bus = event_bus
        self._machine_id = machine_id
        self._current_state = MachineState.IDLE
        self._current_process_id: Optional[str] = None

        # Define valid state transitions
        self._transitions: Dict[MachineState, Set[MachineState]] = {
            MachineState.IDLE: {MachineState.STARTING, MachineState.MAINTENANCE},
            MachineState.STARTING: {MachineState.PROCESSING, MachineState.ERROR, MachineState.IDLE},
            MachineState.PROCESSING: {MachineState.STOPPING, MachineState.ERROR, MachineState.PAUSED},
            MachineState.STOPPING: {MachineState.IDLE, MachineState.ERROR},
            MachineState.PAUSED: {MachineState.PROCESSING, MachineState.STOPPING, MachineState.ERROR},
            MachineState.ERROR: {MachineState.IDLE, MachineState.MAINTENANCE},
            MachineState.MAINTENANCE: {MachineState.IDLE}
        }

    async def transition_to(self, new_state: MachineState, process_id: Optional[str] = None) -> bool:
        """Attempt to transition to a new state"""
        if new_state not in self._transitions.get(self._current_state, set()):
            return False

        old_state = self._current_state
        self._current_state = new_state

        if process_id:
            self._current_process_id = process_id
        elif new_state == MachineState.IDLE:
            self._current_process_id = None

        # Publish state change event
        event = MachineStateChangedEvent(
            machine_id=self._machine_id,
            old_state=old_state.value,
            new_state=new_state.value,
            process_id=self._current_process_id
        )

        await self._event_bus.publish(event)
        return True

    @property
    def current_state(self) -> MachineState:
        """Get current machine state"""
        return self._current_state

    @property
    def current_process_id(self) -> Optional[str]:
        """Get current process ID"""
        return self._current_process_id

    def can_transition_to(self, state: MachineState) -> bool:
        """Check if transition is valid"""
        return state in self._transitions.get(self._current_state, set())
```

## 3. Clean Architecture Implementation

### 3.1 Domain Layer

```python
# File: src/domain/entities/process.py
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from ..value_objects import ProcessId, RecipeId, MachineId
from ..events import DomainEvent

@dataclass
class Process:
    """Process aggregate root"""
    id: ProcessId
    recipe_id: RecipeId
    machine_id: MachineId
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_step: Optional[int] = None

    def __post_init__(self):
        self._events: List[DomainEvent] = []

    def start(self):
        """Start the process"""
        if self.status != "created":
            raise ValueError("Process can only be started from created state")

        self.status = "running"
        self.started_at = datetime.utcnow()

        # Add domain event
        from ..events import ProcessStartedEvent
        event = ProcessStartedEvent(
            process_id=str(self.id),
            recipe_id=str(self.recipe_id),
            machine_id=str(self.machine_id)
        )
        self._events.append(event)

    def complete(self):
        """Complete the process"""
        if self.status != "running":
            raise ValueError("Process can only be completed from running state")

        self.status = "completed"
        self.completed_at = datetime.utcnow()

        # Add domain event
        from ..events import ProcessStoppedEvent
        event = ProcessStoppedEvent(
            process_id=str(self.id),
            reason="completed",
            machine_id=str(self.machine_id)
        )
        self._events.append(event)

    def get_uncommitted_events(self) -> List[DomainEvent]:
        """Get uncommitted domain events"""
        return self._events.copy()

    def mark_events_as_committed(self):
        """Mark events as committed"""
        self._events.clear()

# File: src/domain/value_objects.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ProcessId:
    value: str

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class RecipeId:
    value: str

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class MachineId:
    value: str

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class ParameterValue:
    parameter_id: str
    value: float
    timestamp: datetime
    quality: str = "good"

    def __post_init__(self):
        if self.quality not in ["good", "bad", "uncertain"]:
            raise ValueError("Invalid quality value")
```

### 3.2 Application Layer (Use Cases)

```python
# File: src/application/use_cases/start_process.py
from typing import Protocol
from ..interfaces import ProcessRepository, EventBus
from ...domain.entities import Process
from ...domain.value_objects import ProcessId, RecipeId, MachineId

class StartProcessCommand:
    def __init__(self, process_id: str, recipe_id: str, machine_id: str):
        self.process_id = process_id
        self.recipe_id = recipe_id
        self.machine_id = machine_id

class StartProcessUseCase:
    def __init__(self, process_repository: ProcessRepository, event_bus: EventBus):
        self._process_repository = process_repository
        self._event_bus = event_bus

    async def execute(self, command: StartProcessCommand) -> bool:
        """Execute the start process use case"""
        try:
            # Create process entity
            process = Process(
                id=ProcessId(command.process_id),
                recipe_id=RecipeId(command.recipe_id),
                machine_id=MachineId(command.machine_id),
                status="created",
                started_at=None
            )

            # Domain logic
            process.start()

            # Save to repository
            await self._process_repository.save(process)

            # Publish domain events
            events = process.get_uncommitted_events()
            for event in events:
                await self._event_bus.publish(event)

            process.mark_events_as_committed()

            return True

        except Exception as e:
            # Log error and return failure
            return False
```

## 4. Repository Pattern Implementation

```python
# File: src/infrastructure/repositories/process_repository.py
from typing import Optional, Protocol
from ...domain.entities import Process
from ...domain.value_objects import ProcessId
from ..database import DatabaseConnection

class ProcessRepository(Protocol):
    async def save(self, process: Process) -> None:
        ...

    async def get_by_id(self, process_id: ProcessId) -> Optional[Process]:
        ...

    async def get_current_for_machine(self, machine_id: str) -> Optional[Process]:
        ...

class PostgresProcessRepository(ProcessRepository):
    def __init__(self, db_connection: DatabaseConnection):
        self._db = db_connection

    async def save(self, process: Process) -> None:
        """Save process to database"""
        query = """
        INSERT INTO processes (id, recipe_id, machine_id, status, started_at, completed_at, current_step)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            completed_at = EXCLUDED.completed_at,
            current_step = EXCLUDED.current_step
        """

        await self._db.execute(
            query,
            str(process.id),
            str(process.recipe_id),
            str(process.machine_id),
            process.status,
            process.started_at,
            process.completed_at,
            process.current_step
        )

    async def get_by_id(self, process_id: ProcessId) -> Optional[Process]:
        """Get process by ID"""
        query = """
        SELECT id, recipe_id, machine_id, status, started_at, completed_at, current_step
        FROM processes
        WHERE id = $1
        """

        row = await self._db.fetch_one(query, str(process_id))

        if row:
            return Process(
                id=ProcessId(row['id']),
                recipe_id=RecipeId(row['recipe_id']),
                machine_id=MachineId(row['machine_id']),
                status=row['status'],
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                current_step=row['current_step']
            )

        return None
```

## 5. Circuit Breaker Pattern

```python
# File: src/infrastructure/resilience/circuit_breaker.py
from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
import asyncio

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker for external dependencies"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker"""
        return (self.last_failure_time and
                datetime.utcnow() - self.last_failure_time >= timedelta(seconds=self.recovery_timeout))

    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
```

## 6. Performance Architecture

### 6.1 Async Pipeline Design

```python
# File: src/infrastructure/performance/async_pipeline.py
import asyncio
from typing import List, Callable, Any, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ParameterReading:
    parameter_id: str
    value: float
    timestamp: datetime
    quality: str = "good"

class AsyncParameterPipeline:
    """High-performance async pipeline for parameter logging"""

    def __init__(self, plc_interface, data_repository, cache_service):
        self.plc_interface = plc_interface
        self.data_repository = data_repository
        self.cache_service = cache_service
        self.buffer: List[ParameterReading] = []
        self.buffer_lock = asyncio.Lock()
        self.batch_size = 50
        self.flush_interval = 1.0  # 1 second

    async def start_pipeline(self):
        """Start the parameter logging pipeline"""
        # Start concurrent tasks
        tasks = [
            self._parameter_reader_task(),
            self._buffer_flusher_task(),
            self._metadata_cache_refresher_task()
        ]

        await asyncio.gather(*tasks)

    async def _parameter_reader_task(self):
        """Task to read parameters from PLC"""
        while True:
            try:
                # Use bulk read operation for performance
                parameters = await self.plc_interface.read_all_parameters_bulk()

                timestamp = datetime.utcnow()
                readings = [
                    ParameterReading(
                        parameter_id=param_id,
                        value=value,
                        timestamp=timestamp
                    )
                    for param_id, value in parameters.items()
                ]

                # Add to buffer
                async with self.buffer_lock:
                    self.buffer.extend(readings)

                # Sleep for 1 second interval
                await asyncio.sleep(1.0)

            except Exception as e:
                # Log error and continue
                await asyncio.sleep(5.0)  # Back off on error

    async def _buffer_flusher_task(self):
        """Task to flush buffer to database"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)

                # Get current buffer
                async with self.buffer_lock:
                    if not self.buffer:
                        continue

                    current_batch = self.buffer[:self.batch_size]
                    self.buffer = self.buffer[self.batch_size:]

                # Flush to database (concurrent operation)
                await self.data_repository.bulk_insert_parameters(current_batch)

            except Exception as e:
                # Log error and continue
                pass

    async def _metadata_cache_refresher_task(self):
        """Task to refresh parameter metadata cache"""
        while True:
            try:
                # Refresh cache every 5 minutes
                await asyncio.sleep(300)
                await self.cache_service.refresh_parameter_metadata()

            except Exception as e:
                # Log error and continue
                pass
```

## 7. Configuration System

```python
# File: src/infrastructure/configuration/config_provider.py
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import os
import json
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    pool_size: int = 10

@dataclass
class PLCConfig:
    type: str
    host: str
    port: int
    timeout: int = 5

@dataclass
class ApplicationConfig:
    machine_id: str
    log_level: str
    data_collection_interval: float
    batch_size: int
    database: DatabaseConfig
    plc: PLCConfig

class ConfigProvider(ABC):
    """Abstract configuration provider"""

    @abstractmethod
    def get_config(self) -> ApplicationConfig:
        pass

class EnvironmentConfigProvider(ConfigProvider):
    """Environment-based configuration provider"""

    def get_config(self) -> ApplicationConfig:
        return ApplicationConfig(
            machine_id=os.getenv("MACHINE_ID", "default"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            data_collection_interval=float(os.getenv("DATA_COLLECTION_INTERVAL", "1.0")),
            batch_size=int(os.getenv("BATCH_SIZE", "50")),
            database=DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "ald_control"),
                username=os.getenv("DB_USER", "ald_user"),
                password=os.getenv("DB_PASSWORD", ""),
                pool_size=int(os.getenv("DB_POOL_SIZE", "10"))
            ),
            plc=PLCConfig(
                type=os.getenv("PLC_TYPE", "simulation"),
                host=os.getenv("PLC_HOST", "localhost"),
                port=int(os.getenv("PLC_PORT", "502")),
                timeout=int(os.getenv("PLC_TIMEOUT", "5"))
            )
        )

class FileConfigProvider(ConfigProvider):
    """File-based configuration provider"""

    def __init__(self, config_file: str):
        self.config_file = config_file

    def get_config(self) -> ApplicationConfig:
        with open(self.config_file, 'r') as f:
            data = json.load(f)

        return ApplicationConfig(
            machine_id=data["machine_id"],
            log_level=data["log_level"],
            data_collection_interval=data["data_collection_interval"],
            batch_size=data["batch_size"],
            database=DatabaseConfig(**data["database"]),
            plc=PLCConfig(**data["plc"])
        )
```

## 8. Migration Strategy

### Phase 1: Infrastructure Setup (Week 1)
1. Implement DI container and service locator
2. Create configuration system
3. Set up event bus and basic event handling
4. Implement circuit breaker pattern

### Phase 2: Repository Layer (Week 2)
1. Create repository interfaces
2. Implement PostgreSQL repositories
3. Add connection pooling and transaction support
4. Create caching layer

### Phase 3: Domain Layer (Week 3)
1. Define domain entities and value objects
2. Implement domain services
3. Create state machine for process management
4. Add domain event handling

### Phase 4: Application Layer (Week 4)
1. Implement use cases with CQRS pattern
2. Create command and query handlers
3. Add validation and business rule enforcement
4. Implement saga pattern for complex workflows

### Phase 5: Integration (Week 5)
1. Replace existing singletons with DI
2. Migrate data access to repositories
3. Replace direct coupling with event-driven communication
4. Update main application bootstrap

## 9. Security Architecture

### 9.1 Secure Configuration Management

```python
# File: src/infrastructure/security/secure_config.py
import os
from cryptography.fernet import Fernet
from typing import Dict, Any

class SecureConfigManager:
    """Secure configuration management"""

    def __init__(self, encryption_key: str = None):
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            # Generate key from environment or default
            key = os.getenv("CONFIG_ENCRYPTION_KEY")
            if key:
                self.cipher = Fernet(key.encode())
            else:
                self.cipher = None

    def decrypt_config(self, encrypted_value: str) -> str:
        """Decrypt configuration value"""
        if self.cipher:
            return self.cipher.decrypt(encrypted_value.encode()).decode()
        return encrypted_value

    def get_secure_value(self, key: str, default: str = None) -> str:
        """Get configuration value with decryption"""
        value = os.getenv(key, default)
        if value and value.startswith("enc:"):
            return self.decrypt_config(value[4:])
        return value
```

### 9.2 Input Validation Framework

```python
# File: src/infrastructure/security/validation.py
from typing import Any, List, Dict
from abc import ABC, abstractmethod
import re

class ValidationRule(ABC):
    @abstractmethod
    def validate(self, value: Any) -> bool:
        pass

    @abstractmethod
    def get_error_message(self) -> str:
        pass

class NumericRangeRule(ValidationRule):
    def __init__(self, min_value: float, max_value: float):
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any) -> bool:
        try:
            num_value = float(value)
            return self.min_value <= num_value <= self.max_value
        except (ValueError, TypeError):
            return False

    def get_error_message(self) -> str:
        return f"Value must be between {self.min_value} and {self.max_value}"

class InputValidator:
    """Centralized input validation"""

    def __init__(self):
        self.rules: Dict[str, List[ValidationRule]] = {}

    def add_rule(self, field: str, rule: ValidationRule):
        if field not in self.rules:
            self.rules[field] = []
        self.rules[field].append(rule)

    def validate(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate input data"""
        errors = {}

        for field, value in data.items():
            if field in self.rules:
                field_errors = []
                for rule in self.rules[field]:
                    if not rule.validate(value):
                        field_errors.append(rule.get_error_message())

                if field_errors:
                    errors[field] = field_errors

        return errors
```

## Conclusion

This architectural blueprint provides a comprehensive solution that addresses all identified issues:

1. **Dependency Injection**: Replaces global singletons with proper DI container
2. **Clean Architecture**: Separates concerns with clear layer boundaries
3. **Event-Driven Design**: Eliminates race conditions with atomic state management
4. **Performance**: Async pipelines with bulk operations and caching
5. **Security**: Secure configuration and input validation
6. **Testability**: Interface-based design enables comprehensive testing

The implementation should be done in phases to ensure stability and maintainability while addressing critical security and data integrity issues immediately.