# API and Interface Documentation

## Overview

The ALD Control System provides a comprehensive set of interfaces and APIs for all major components. This documentation covers all service interfaces, their contracts, usage patterns, and implementation guidelines.

## Core Service Interfaces

### IPLCInterface (`src/abstractions/interfaces.py:18-152`)

Primary interface for PLC hardware communication.

#### Connection Management
```python
@property
async def connected(self) -> bool:
    """Check if PLC is currently connected"""

async def initialize(self) -> bool:
    """Initialize PLC connection"""

async def disconnect(self) -> bool:
    """Disconnect from PLC"""

async def health_check(self) -> ServiceHealth:
    """Perform health check on PLC connection"""
```

#### Parameter Operations
```python
async def read_parameter(self, parameter_id: str) -> float:
    """Read a single parameter value from the PLC"""

async def write_parameter(self, parameter_id: str, value: float) -> bool:
    """Write a parameter value to the PLC"""

async def read_all_parameters(self) -> Dict[str, float]:
    """Read all parameter values from the PLC"""

async def read_bulk_parameters(self, parameter_ids: List[str]) -> Dict[str, float]:
    """Read multiple parameters in a single operation for performance"""
```

#### Hardware Control
```python
async def control_valve(self, valve_number: int, state: bool,
                       duration_ms: Optional[int] = None) -> bool:
    """Control a valve state with optional duration"""

async def execute_purge(self, duration_ms: int) -> bool:
    """Execute a purge operation for the specified duration"""
```

#### Usage Example
```python
# Initialize PLC
plc = await container.resolve(IPLCInterface)
await plc.initialize()

# Read parameters
temperature = await plc.read_parameter("TEMP_01")
parameters = await plc.read_bulk_parameters(["TEMP_01", "PRESS_01", "FLOW_01"])

# Control hardware
await plc.control_valve(1, True, duration_ms=5000)
await plc.execute_purge(duration_ms=10000)

# Cleanup
await plc.disconnect()
```

### IDatabaseService (`src/abstractions/interfaces.py:154-243`)

Database operations interface with transaction support.

#### Query Operations
```python
async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Execute a database query with optional parameters"""

async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> bool:
    """Execute a query with multiple parameter sets"""

async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Fetch a single row from query result"""

async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch all rows from query result"""
```

#### Transaction Management
```python
async def begin_transaction(self) -> 'ITransaction':
    """Begin a database transaction"""

# Transaction interface
async def commit(self) -> bool:
    """Commit the transaction"""

async def rollback(self) -> bool:
    """Roll back the transaction"""
```

#### Usage Example
```python
# Basic operations
db = await container.resolve(IDatabaseService)

# Simple query
result = await db.fetch_one(
    "SELECT * FROM parameters WHERE id = :id",
    {"id": "TEMP_01"}
)

# Bulk operations
params_list = [
    {"id": "TEMP_01", "value": 25.0, "timestamp": time.time()},
    {"id": "PRESS_01", "value": 1013.25, "timestamp": time.time()}
]
await db.execute_many(
    "INSERT INTO parameter_values (id, value, timestamp) VALUES (:id, :value, :timestamp)",
    params_list
)

# Transaction usage
async with await db.begin_transaction() as tx:
    await tx.execute("UPDATE process_state SET status = :status", {"status": "running"})
    await tx.execute("INSERT INTO process_log (message) VALUES (:msg)", {"msg": "Process started"})
    # Auto-commit on successful exit, rollback on exception
```

### IParameterLogger (`src/abstractions/interfaces.py:306-392`)

High-performance parameter logging interface.

#### Lifecycle Management
```python
async def start(self) -> bool:
    """Start the parameter logging service"""

async def stop(self) -> bool:
    """Stop the parameter logging service"""

async def dispose(self) -> None:
    """Clean up resources and stop logging"""
```

#### Logging Operations
```python
async def log_parameters(self, parameters: Dict[str, float],
                        process_id: Optional[str] = None,
                        timestamp: Optional[float] = None) -> bool:
    """Log parameter values with optional process association"""

async def log_dual_mode(self, parameters: Dict[str, float],
                       process_id: Optional[str] = None,
                       machine_status: Optional[str] = None) -> bool:
    """Log parameters in dual-mode (both parameter_value_history and process_data_points)"""
```

#### Status and Monitoring
```python
def get_status(self) -> Dict[str, Any]:
    """Get current status of the parameter logger"""

async def health_check(self) -> ServiceHealth:
    """Perform health check on parameter logging service"""
```

#### Usage Example
```python
# Initialize logger
logger = await container.resolve(IParameterLogger)
await logger.start()

# Log parameters
parameters = {
    "TEMP_01": 25.0,
    "PRESS_01": 1013.25,
    "FLOW_01": 2.5
}

# Idle mode logging
await logger.log_parameters(parameters)

# Process mode logging (dual-mode)
await logger.log_dual_mode(
    parameters,
    process_id="PROCESS_12345",
    machine_status="running"
)

# Monitor status
status = logger.get_status()
print(f"Logging rate: {status['logging_rate']} parameters/second")
```

### IEventBus (`src/abstractions/interfaces.py:394-442`)

Event-driven communication interface.

#### Event Publishing
```python
async def publish(self, event_type: str, data: Dict[str, Any],
                 source: Optional[str] = None) -> bool:
    """Publish an event to the bus"""
```

#### Event Subscription
```python
async def subscribe(self, event_type: str,
                   handler: Callable[[Dict[str, Any]], None]) -> str:
    """Subscribe to events of a specific type"""

async def unsubscribe(self, subscription_id: str) -> bool:
    """Unsubscribe from events"""
```

#### Usage Example
```python
# Initialize event bus
event_bus = await container.resolve(IEventBus)

# Define event handler
async def handle_process_event(event_data: Dict[str, Any]):
    print(f"Process event: {event_data}")

# Subscribe to events
subscription_id = await event_bus.subscribe("process.state_changed", handle_process_event)

# Publish events
await event_bus.publish(
    "process.state_changed",
    {
        "process_id": "PROCESS_12345",
        "old_state": "stopped",
        "new_state": "running",
        "timestamp": time.time()
    },
    source="recipe_executor"
)

# Cleanup
await event_bus.unsubscribe(subscription_id)
```

### IStateManager (`src/abstractions/interfaces.py:495-547`)

Centralized state management interface.

#### State Operations
```python
async def get_machine_state(self) -> Dict[str, Any]:
    """Get current machine state"""

async def set_machine_state(self, state: Dict[str, Any]) -> bool:
    """Set machine state atomically"""

async def transition_state(self, from_state: str, to_state: str,
                          context: Optional[Dict[str, Any]] = None) -> bool:
    """Perform atomic state transition"""
```

#### State Monitoring
```python
async def watch_state_changes(self, callback: Callable[[Dict[str, Any]], None]) -> str:
    """Watch for state changes"""
```

#### Usage Example
```python
# Initialize state manager
state_mgr = await container.resolve(IStateManager)

# Get current state
current_state = await state_mgr.get_machine_state()
print(f"Current state: {current_state['status']}")

# Atomic state transition
success = await state_mgr.transition_state(
    from_state="idle",
    to_state="running",
    context={"process_id": "PROCESS_12345", "recipe_id": "RECIPE_001"}
)

# Watch for state changes
async def on_state_change(new_state: Dict[str, Any]):
    print(f"State changed to: {new_state}")

watcher_id = await state_mgr.watch_state_changes(on_state_change)
```

## API Usage Patterns

### Dependency Injection Pattern
```python
class RecipeExecutor:
    def __init__(self,
                 plc: IPLCInterface,
                 database: IDatabaseService,
                 logger: IParameterLogger,
                 event_bus: IEventBus,
                 state_manager: IStateManager):
        self.plc = plc
        self.database = database
        self.logger = logger
        self.event_bus = event_bus
        self.state_manager = state_manager

    async def execute_recipe(self, recipe_id: str) -> bool:
        # Use injected dependencies
        await self.state_manager.transition_state("idle", "running")
        await self.event_bus.publish("recipe.started", {"recipe_id": recipe_id})
        # ... recipe execution logic
```

### Error Handling Pattern
```python
from src.abstractions.interfaces import (
    PLCConnectionError, PLCParameterError,
    DatabaseConnectionError, DatabaseQueryError
)

async def safe_parameter_read(plc: IPLCInterface, parameter_id: str) -> Optional[float]:
    try:
        return await plc.read_parameter(parameter_id)
    except PLCConnectionError:
        logger.error("PLC connection lost during parameter read")
        return None
    except PLCParameterError as e:
        logger.error(f"Invalid parameter {parameter_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading parameter: {e}")
        return None
```

### Async Context Manager Pattern
```python
async def execute_with_transaction(db: IDatabaseService, operations: List[Callable]):
    async with await db.begin_transaction() as tx:
        for operation in operations:
            await operation(tx)
        # Auto-commit on success, rollback on exception
```

### Bulk Operations Pattern
```python
async def efficient_parameter_logging(plc: IPLCInterface, logger: IParameterLogger):
    # Read all parameters in bulk for performance
    all_parameters = await plc.read_all_parameters()

    # Log in dual-mode if process is running
    state = await state_manager.get_machine_state()
    if state.get('status') == 'running':
        await logger.log_dual_mode(
            all_parameters,
            process_id=state.get('process_id'),
            machine_status='running'
        )
    else:
        await logger.log_parameters(all_parameters)
```

## Performance Considerations

### Bulk Operations
- **PLC Bulk Reads**: Use `read_bulk_parameters()` instead of multiple `read_parameter()` calls
- **Database Batch Operations**: Use `execute_many()` for bulk inserts/updates
- **Event Batching**: Batch related events when possible

### Connection Management
- **Connection Pooling**: Database connections are automatically pooled
- **PLC Connection Reuse**: PLC connections are managed by the PLC manager
- **Resource Cleanup**: Always call `dispose()` methods for proper cleanup

### Async Best Practices
- **Non-blocking Operations**: All interface methods are async
- **Concurrent Operations**: Use `asyncio.gather()` for concurrent operations
- **Timeout Handling**: Implement timeouts for long-running operations

## Error Handling Guidelines

### Exception Hierarchy
```python
ServiceError (Base)
├── PLCConnectionError
├── PLCParameterError
├── DatabaseConnectionError
├── DatabaseQueryError
├── ConfigurationError
└── StateTransitionError
```

### Error Recovery Patterns
1. **Retry with Backoff**: For transient connection errors
2. **Circuit Breaker**: For repeated service failures
3. **Graceful Degradation**: Fallback to simulation mode
4. **Event Notification**: Publish error events for monitoring

### Logging Guidelines
- **Structured Logging**: Use structured log format with context
- **Error Context**: Include relevant context in error messages
- **Performance Logging**: Log slow operations for optimization
- **Security Logging**: Log security-relevant events

## Testing Interface Implementations

### Mock Implementations
```python
class MockPLCInterface(IPLCInterface):
    def __init__(self):
        self._connected = False
        self._parameters = {}

    async def initialize(self) -> bool:
        self._connected = True
        return True

    async def read_parameter(self, parameter_id: str) -> float:
        if not self._connected:
            raise PLCConnectionError("PLC not connected")
        return self._parameters.get(parameter_id, 0.0)
```

### Test Containers
```python
async def create_test_container() -> ServiceContainer:
    container = ServiceContainer()

    # Register mock implementations
    container.register_singleton(IPLCInterface, MockPLCInterface)
    container.register_singleton(IDatabaseService, InMemoryDatabaseService)
    container.register_singleton(IParameterLogger, MockParameterLogger)

    return container
```

### Integration Testing
```python
async def test_full_recipe_execution():
    container = await create_test_container()
    executor = await container.resolve(RecipeExecutor)

    # Test with mock dependencies
    result = await executor.execute_recipe("TEST_RECIPE")
    assert result is True
```

This comprehensive interface documentation provides the foundation for understanding and implementing all system components while maintaining consistency and reliability across the platform.