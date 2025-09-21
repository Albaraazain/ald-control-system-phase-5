# Dependency Injection Framework Documentation

## Overview

The ALD Control System uses a sophisticated Dependency Injection (DI) framework built around a high-performance ServiceContainer. This framework provides inversion of control, automatic dependency resolution, and comprehensive lifecycle management for all services.

## Core Components

### ServiceContainer (`src/di/container.py`)

The ServiceContainer is the heart of the DI framework, providing:

- **Multiple Service Lifetimes**: Singleton, Transient, and Scoped
- **Async Support**: Full async/await compatibility
- **Auto-wiring**: Automatic dependency resolution via type hints
- **Circular Detection**: Prevention and reporting of circular dependencies
- **Performance Optimization**: <1ms resolution time target
- **Health Monitoring**: Service health checks and monitoring
- **Resource Management**: Proper cleanup and disposal

### Service Lifetimes

#### Singleton
```python
container.register_singleton(IPLCInterface, RealPLC)
```
- **Single Instance**: One instance per container
- **Thread-Safe**: Double-checked locking pattern
- **Shared State**: Same instance across all resolutions
- **Use Cases**: Database connections, PLC managers, configuration services

#### Transient
```python
container.register_transient(IParameterLogger, ParameterLogger)
```
- **New Instance**: Fresh instance on every resolution
- **No Shared State**: Isolated instances
- **Use Cases**: Data transfer objects, temporary services, request-scoped operations

#### Scoped
```python
container.register_scoped(ITransaction, DatabaseTransaction)
```
- **Scope Lifetime**: One instance per scope
- **Scope Management**: Automatic cleanup on scope disposal
- **Use Cases**: Request processing, transaction contexts, user sessions

## Service Registration

### Basic Registration
```python
# Interface to implementation mapping
container.register(IPLCInterface, RealPLC, ServiceLifetime.SINGLETON)

# Factory-based registration
container.register(
    IDatabaseService,
    factory=lambda container: create_database_service(container.resolve(IConfigurationService)),
    lifetime=ServiceLifetime.SINGLETON
)

# Instance registration
config = ConfigurationService()
container.register_instance(IConfigurationService, config)
```

### Convenience Methods
```python
# Simplified registration methods
container.register_singleton(IPLCInterface, RealPLC)
container.register_transient(IParameterLogger, ParameterLogger)
container.register_scoped(ITransaction, DatabaseTransaction)
```

### Factory Registration
```python
async def create_plc_interface(container: ServiceContainer) -> IPLCInterface:
    config = await container.resolve(IConfigurationService)
    if config.get('simulation_mode'):
        return SimulationPLC()
    else:
        return RealPLC()

container.register(
    IPLCInterface,
    factory=create_plc_interface,
    lifetime=ServiceLifetime.SINGLETON
)
```

## Service Resolution

### Basic Resolution
```python
# Resolve a service
plc = await container.resolve(IPLCInterface)

# Resolve with scope
async with container.create_scope() as scope_id:
    transaction = await container.resolve(ITransaction, scope_id)
    # Use transaction within scope
```

### Auto-wiring
The container automatically resolves constructor dependencies using type hints:

```python
class ParameterLogger:
    def __init__(self,
                 plc: IPLCInterface,
                 database: IDatabaseService,
                 config: Optional[IConfigurationService] = None):
        self.plc = plc
        self.database = database
        self.config = config

# Registration - dependencies auto-resolved
container.register_transient(IParameterLogger, ParameterLogger)

# Resolution - all dependencies injected automatically
logger = await container.resolve(IParameterLogger)
```

### Circular Dependency Detection
```python
# This would raise CircularDependencyError
class ServiceA:
    def __init__(self, service_b: 'ServiceB'): pass

class ServiceB:
    def __init__(self, service_a: ServiceA): pass

container.register_transient(ServiceA, ServiceA)
container.register_transient(ServiceB, ServiceB)

# Raises: CircularDependencyError: ServiceA -> ServiceB -> ServiceA
await container.resolve(ServiceA)
```

## Advanced Features

### Scoped Services
```python
# Create a scope for request processing
async with container.create_scope() as scope_id:
    # All scoped services share the same instances within this scope
    transaction1 = await container.resolve(ITransaction, scope_id)
    transaction2 = await container.resolve(ITransaction, scope_id)
    assert transaction1 is transaction2  # Same instance

    # Automatic cleanup when scope exits
```

### Health Monitoring
```python
# Register health monitor
def plc_health_monitor(plc: IPLCInterface) -> bool:
    return plc.connected

container.register_health_monitor(IPLCInterface, plc_health_monitor)

# Check service health
health_results = await container.health_check()
print(f"PLC Health: {health_results[IPLCInterface]}")
```

### Service Information
```python
# Get information about registered services
info = container.get_service_info(IPLCInterface)
print(f"Service: {info['service_type']}")
print(f"Implementation: {info['implementation_type']}")
print(f"Lifetime: {info['lifetime']}")
print(f"Dependencies: {info['dependencies']}")

# Get all registered services
all_services = container.get_all_services()
```

## Configuration-Based Registration

### ServiceConfiguration (`src/di/configuration.py`)
```python
{
    "services": {
        "plc_interface": {
            "interface": "src.abstractions.interfaces.IPLCInterface",
            "implementation": "src.plc.real_plc.RealPLC",
            "lifetime": "singleton",
            "properties": {
                "hostname": "${PLC_HOSTNAME}",
                "port": "${PLC_PORT:502}"
            }
        },
        "database_service": {
            "interface": "src.abstractions.interfaces.IDatabaseService",
            "factory": "src.di.factories.create_database_service",
            "lifetime": "singleton"
        }
    }
}
```

### ConfigurationBasedContainerBuilder
```python
# Build container from configuration
builder = ConfigurationBasedContainerBuilder()
container = await builder.build_from_file("container_config.json")

# Environment variable substitution
# ${PLC_HOSTNAME} -> resolves from environment
# ${PLC_PORT:502} -> resolves from environment with default 502
```

## Service Factories (`src/di/factories.py`)

### PLC Factory
```python
async def create_plc_interface(container: ServiceContainer) -> IPLCInterface:
    config = await container.resolve(IConfigurationService)

    if config.get('simulation_mode', False):
        logger.info("Creating simulation PLC interface")
        return SimulationPLC()
    else:
        logger.info("Creating real PLC interface")
        hostname = config.get('plc.hostname', 'localhost')
        port = config.get('plc.port', 502)
        return RealPLC(hostname=hostname, port=port)
```

### Database Factory
```python
async def create_database_service(container: ServiceContainer) -> IDatabaseService:
    config = await container.resolve(IConfigurationService)

    # Create connection pool
    pool = AsyncDatabaseConnectionPool(
        connection_string=config.get('database.connection_string'),
        max_connections=config.get('database.max_connections', 20),
        timeout=config.get('database.timeout', 30)
    )

    return DatabaseService(pool)
```

## Performance Optimization

### Resolution Caching
- **Fast Path**: Singleton resolution uses cached instances
- **Performance Target**: <1ms resolution time
- **Memory Efficient**: Weak references for cached services

### Async Optimization
- **Non-blocking**: All service creation is async-compatible
- **Concurrent Resolution**: Multiple services can be resolved simultaneously
- **Async Factories**: Support for async service factory methods

### Resource Management
```python
# Proper container disposal
try:
    # Use container
    service = await container.resolve(IService)
finally:
    # Cleanup all resources
    await container.dispose()
```

## Integration with Existing Code

### Service Locator Pattern
```python
# Global service locator for legacy code compatibility
from src.di.service_locator import ServiceLocator

# Initialize with container
ServiceLocator.initialize(container)

# Legacy code can resolve services
plc = await ServiceLocator.resolve(IPLCInterface)
```

### Migration Helper
```python
# Gradual migration from manual dependency management
from src.di.migration import MigrationHelper

# Wrap existing code with DI
@MigrationHelper.inject_dependencies
class LegacyService:
    def __init__(self, plc: IPLCInterface = None):
        # DI will inject PLC if None
        self.plc = plc or ServiceLocator.resolve(IPLCInterface)
```

## Testing with Dependency Injection

### Mock Services
```python
class MockPLC(IPLCInterface):
    def __init__(self):
        self.connected = True
        self.parameters = {}

    async def read_parameter(self, parameter_id: str) -> float:
        return self.parameters.get(parameter_id, 0.0)

# Test setup
test_container = ServiceContainer()
test_container.register_singleton(IPLCInterface, MockPLC)

# Test execution
logger = await test_container.resolve(IParameterLogger)
# Logger now uses MockPLC instead of real PLC
```

### Test Containers
```python
# Create isolated test container
async def create_test_container() -> ServiceContainer:
    container = ServiceContainer()

    # Register test implementations
    container.register_singleton(IPLCInterface, MockPLC)
    container.register_singleton(IDatabaseService, InMemoryDatabase)
    container.register_transient(IParameterLogger, ParameterLogger)

    return container

# Use in tests
async def test_parameter_logging():
    container = await create_test_container()
    logger = await container.resolve(IParameterLogger)

    # Test with mock dependencies
    result = await logger.log_parameters({"temp": 25.0})
    assert result is True
```

## Error Handling

### Common Exceptions
```python
# Service not registered
try:
    unknown_service = await container.resolve(IUnknownService)
except ServiceNotRegisteredError as e:
    logger.error(f"Service not found: {e}")

# Circular dependency
try:
    circular_service = await container.resolve(ICircularService)
except CircularDependencyError as e:
    logger.error(f"Circular dependency: {e}")

# Container disposed
try:
    await container.dispose()
    service = await container.resolve(IService)
except RuntimeError as e:
    logger.error(f"Container disposed: {e}")
```

### Diagnostics
```python
# Service resolution diagnostics
try:
    service = await container.resolve(IService)
except Exception as e:
    # Get service info for debugging
    info = container.get_service_info(IService)
    logger.error(f"Resolution failed for {info}: {e}")
```

## Best Practices

### 1. Interface Design
- Define clear, focused interfaces
- Use dependency injection for all external dependencies
- Prefer composition over inheritance

### 2. Service Registration
- Register services at application startup
- Use appropriate lifetimes for each service type
- Prefer factory methods for complex service creation

### 3. Service Resolution
- Resolve services at the composition root
- Avoid service locator pattern in business logic
- Use scoped services for request-specific operations

### 4. Testing
- Use mock implementations for all external dependencies
- Create isolated test containers
- Test service registration and resolution

### 5. Performance
- Register expensive services as singletons
- Use lazy initialization where appropriate
- Monitor service resolution performance

This dependency injection framework provides a robust foundation for building testable, maintainable, and high-performance applications while maintaining loose coupling between components.