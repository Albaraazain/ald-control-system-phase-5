# Dependency Injection Container Architecture Design

## Executive Summary

This document outlines the comprehensive dependency injection container framework designed to address the critical architectural violations identified in the ALD control system, including global singletons, tight coupling, and lack of testability.

## Current Architecture Problems Identified

### Critical Issues
1. **Global Singletons**: `plc_manager`, `data_collection_service`, `continuous_parameter_logger`
2. **Tight Coupling**: Direct imports creating circular dependencies
3. **No DI Framework**: Manual instantiation throughout codebase
4. **Poor Testability**: Hard dependencies prevent unit testing
5. **Service Lifecycle Issues**: Manual lifecycle management in main.py

### Impact Assessment
- **Testability**: Extremely difficult to unit test due to hard dependencies
- **Maintainability**: High coupling makes changes risky and expensive
- **Scalability**: Cannot easily add new services or modify existing ones
- **Reliability**: Service lifecycle errors can cascade through system

## Comprehensive DI Container Design

### 1. Core IoC Container Architecture

```python
# src/di/container.py
from typing import Dict, Any, Type, TypeVar, Generic, Callable, Union, Optional
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import weakref
from contextlib import asynccontextmanager

T = TypeVar('T')

class ServiceLifetime(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"

class ServiceDescriptor(Generic[T]):
    def __init__(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        instance: Optional[T] = None
    ):
        self.service_type = service_type
        self.implementation_type = implementation_type or service_type
        self.factory = factory
        self.lifetime = lifetime
        self.instance = instance
        self.is_async = asyncio.iscoroutinefunction(factory) if factory else False

class ServiceContainer:
    """High-performance async-compatible IoC container"""

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_services: Dict[str, Dict[Type, Any]] = {}
        self._resolving: set = set()  # Circular dependency detection
        self._lock = asyncio.Lock()
        self._health_monitors: Dict[Type, Callable] = {}

    def register(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    ) -> 'ServiceContainer':
        """Register a service with the container"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=lifetime
        )
        self._services[service_type] = descriptor
        return self

    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'ServiceContainer':
        """Register a singleton service"""
        return self.register(service_type, implementation_type, factory, ServiceLifetime.SINGLETON)

    def register_instance(self, service_type: Type[T], instance: T) -> 'ServiceContainer':
        """Register a service instance directly"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.SINGLETON,
            instance=instance
        )
        self._services[service_type] = descriptor
        self._singletons[service_type] = instance
        return self

    async def resolve(self, service_type: Type[T], scope_id: Optional[str] = None) -> T:
        """Resolve a service from the container"""
        if service_type in self._resolving:
            raise CircularDependencyError(f"Circular dependency detected for {service_type}")

        descriptor = self._services.get(service_type)
        if not descriptor:
            raise ServiceNotRegisteredError(f"Service {service_type} not registered")

        # Handle different lifetimes
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return await self._resolve_singleton(service_type, descriptor)
        elif descriptor.lifetime == ServiceLifetime.SCOPED and scope_id:
            return await self._resolve_scoped(service_type, descriptor, scope_id)
        else:
            return await self._resolve_transient(service_type, descriptor)

    async def _resolve_singleton(self, service_type: Type[T], descriptor: ServiceDescriptor[T]) -> T:
        async with self._lock:
            if service_type in self._singletons:
                return self._singletons[service_type]

            instance = await self._create_instance(service_type, descriptor)
            self._singletons[service_type] = instance
            return instance

    async def _resolve_scoped(self, service_type: Type[T], descriptor: ServiceDescriptor[T], scope_id: str) -> T:
        if scope_id not in self._scoped_services:
            self._scoped_services[scope_id] = {}

        scoped_container = self._scoped_services[scope_id]
        if service_type in scoped_container:
            return scoped_container[service_type]

        instance = await self._create_instance(service_type, descriptor)
        scoped_container[service_type] = instance
        return instance

    async def _resolve_transient(self, service_type: Type[T], descriptor: ServiceDescriptor[T]) -> T:
        return await self._create_instance(service_type, descriptor)

    async def _create_instance(self, service_type: Type[T], descriptor: ServiceDescriptor[T]) -> T:
        self._resolving.add(service_type)
        try:
            if descriptor.instance is not None:
                return descriptor.instance

            if descriptor.factory:
                if descriptor.is_async:
                    return await descriptor.factory(self)
                else:
                    return descriptor.factory(self)

            # Auto-wire constructor dependencies
            return await self._auto_wire(descriptor.implementation_type)
        finally:
            self._resolving.discard(service_type)

    async def _auto_wire(self, implementation_type: Type[T]) -> T:
        """Auto-wire constructor dependencies using type hints"""
        import inspect

        sig = inspect.signature(implementation_type.__init__)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            if param.annotation and param.annotation != inspect.Parameter.empty:
                kwargs[param_name] = await self.resolve(param.annotation)

        return implementation_type(**kwargs)

    @asynccontextmanager
    async def create_scope(self, scope_id: str = None):
        """Create a service scope for scoped services"""
        import uuid
        scope_id = scope_id or str(uuid.uuid4())

        try:
            yield scope_id
        finally:
            # Cleanup scoped services
            if scope_id in self._scoped_services:
                scoped_services = self._scoped_services[scope_id]
                for service in scoped_services.values():
                    if hasattr(service, 'dispose'):
                        await service.dispose()
                del self._scoped_services[scope_id]

    async def health_check(self) -> Dict[Type, bool]:
        """Perform health checks on registered services"""
        results = {}
        for service_type, monitor in self._health_monitors.items():
            try:
                if service_type in self._singletons:
                    service = self._singletons[service_type]
                    results[service_type] = await monitor(service)
                else:
                    results[service_type] = True  # Not instantiated yet
            except Exception:
                results[service_type] = False
        return results

    def register_health_monitor(self, service_type: Type, monitor: Callable):
        """Register a health monitor for a service"""
        self._health_monitors[service_type] = monitor

    async def dispose(self):
        """Dispose all services and cleanup resources"""
        # Dispose singletons in reverse order of creation
        for service in reversed(list(self._singletons.values())):
            if hasattr(service, 'dispose'):
                try:
                    await service.dispose()
                except Exception as e:
                    # Log but don't fail entire disposal
                    pass

        # Cleanup scoped services
        for scope_services in self._scoped_services.values():
            for service in scope_services.values():
                if hasattr(service, 'dispose'):
                    try:
                        await service.dispose()
                    except Exception:
                        pass

        self._singletons.clear()
        self._scoped_services.clear()

class CircularDependencyError(Exception):
    pass

class ServiceNotRegisteredError(Exception):
    pass
```

### 2. Service Locator Pattern Implementation

```python
# src/di/service_locator.py
from typing import Type, TypeVar, Optional
from .container import ServiceContainer

T = TypeVar('T')

class ServiceLocator:
    """Global service locator for accessing DI container"""

    _container: Optional[ServiceContainer] = None
    _current_scope: Optional[str] = None

    @classmethod
    def configure(cls, container: ServiceContainer):
        """Configure the service locator with a container"""
        cls._container = container

    @classmethod
    async def get(cls, service_type: Type[T]) -> T:
        """Get a service from the container"""
        if not cls._container:
            raise RuntimeError("ServiceLocator not configured")

        return await cls._container.resolve(service_type, cls._current_scope)

    @classmethod
    def set_scope(cls, scope_id: str):
        """Set the current scope for scoped services"""
        cls._current_scope = scope_id

    @classmethod
    def clear_scope(cls):
        """Clear the current scope"""
        cls._current_scope = None

    @classmethod
    async def health_check(cls) -> Dict[Type, bool]:
        """Perform health check on all services"""
        if not cls._container:
            return {}
        return await cls._container.health_check()
```

### 3. Interface Abstraction Layer

```python
# src/abstractions/interfaces.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio

class IPLCInterface(ABC):
    """Abstract interface for PLC communication"""

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        pass

    @abstractmethod
    async def read_parameter(self, parameter_id: str) -> float:
        pass

    @abstractmethod
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        pass

    @abstractmethod
    async def read_all_parameters(self) -> Dict[str, float]:
        pass

    @abstractmethod
    async def control_valve(self, valve_number: int, state: bool, duration_ms: Optional[int] = None) -> bool:
        pass

    @abstractmethod
    async def execute_purge(self, duration_ms: int) -> bool:
        pass

    @property
    @abstractmethod
    def connected(self) -> bool:
        pass

class IDatabaseService(ABC):
    """Abstract interface for database operations"""

    @abstractmethod
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        pass

    @abstractmethod
    async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> bool:
        pass

    @abstractmethod
    async def begin_transaction(self) -> 'ITransaction':
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

class ITransaction(ABC):
    """Abstract interface for database transactions"""

    @abstractmethod
    async def commit(self) -> bool:
        pass

    @abstractmethod
    async def rollback(self) -> bool:
        pass

    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        pass

    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class IParameterLogger(ABC):
    """Abstract interface for parameter logging services"""

    @abstractmethod
    async def start(self) -> bool:
        pass

    @abstractmethod
    async def stop(self) -> bool:
        pass

    @abstractmethod
    async def log_parameters(self, parameters: Dict[str, float], process_id: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        pass

class IEventBus(ABC):
    """Abstract interface for event-driven communication"""

    @abstractmethod
    async def publish(self, event_type: str, data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def subscribe(self, event_type: str, handler: Callable) -> str:
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        pass
```

### 4. Factory Pattern Integration

```python
# src/di/factories.py
from typing import Type, Dict, Any, Callable
from .container import ServiceContainer
from ..abstractions.interfaces import IPLCInterface, IDatabaseService

class PLCFactory:
    """Factory for creating PLC interfaces with DI support"""

    _factories: Dict[str, Callable[[ServiceContainer], IPLCInterface]] = {}

    @classmethod
    def register(cls, plc_type: str, factory: Callable[[ServiceContainer], IPLCInterface]):
        """Register a PLC factory"""
        cls._factories[plc_type] = factory

    @classmethod
    async def create(cls, plc_type: str, container: ServiceContainer) -> IPLCInterface:
        """Create a PLC interface using the container"""
        if plc_type not in cls._factories:
            raise ValueError(f"Unknown PLC type: {plc_type}")

        factory = cls._factories[plc_type]
        return await factory(container)

class DatabaseFactory:
    """Factory for creating database services with DI support"""

    _factories: Dict[str, Callable[[ServiceContainer], IDatabaseService]] = {}

    @classmethod
    def register(cls, db_type: str, factory: Callable[[ServiceContainer], IDatabaseService]):
        """Register a database factory"""
        cls._factories[db_type] = factory

    @classmethod
    async def create(cls, db_type: str, container: ServiceContainer) -> IDatabaseService:
        """Create a database service using the container"""
        if db_type not in cls._factories:
            raise ValueError(f"Unknown database type: {db_type}")

        factory = cls._factories[db_type]
        return await factory(container)

# Factory registration helpers
def register_plc_factory(plc_type: str):
    """Decorator for registering PLC factories"""
    def decorator(factory_func):
        PLCFactory.register(plc_type, factory_func)
        return factory_func
    return decorator

def register_database_factory(db_type: str):
    """Decorator for registering database factories"""
    def decorator(factory_func):
        DatabaseFactory.register(db_type, factory_func)
        return factory_func
    return decorator
```

### 5. Configuration System Integration

```python
# src/di/configuration.py
from typing import Dict, Any, Type, Optional
from dataclasses import dataclass
from .container import ServiceContainer, ServiceLifetime
import json
import os

@dataclass
class ServiceConfiguration:
    service_type: str
    implementation_type: str
    lifetime: str = "transient"
    configuration: Dict[str, Any] = None
    factory: Optional[str] = None

@dataclass
class DIConfiguration:
    services: List[ServiceConfiguration]
    factories: Dict[str, str]
    environment: str = "development"

class ConfigurationBasedContainerBuilder:
    """Builder for creating containers from configuration"""

    def __init__(self):
        self.container = ServiceContainer()
        self._type_registry: Dict[str, Type] = {}

    def register_type(self, name: str, type_class: Type):
        """Register a type for configuration-based resolution"""
        self._type_registry[name] = type_class
        return self

    def load_from_json(self, config_path: str) -> ServiceContainer:
        """Load container configuration from JSON file"""
        with open(config_path, 'r') as f:
            config_data = json.load(f)

        config = DIConfiguration(**config_data)
        return self.build_from_config(config)

    def load_from_environment(self) -> ServiceContainer:
        """Load container configuration from environment variables"""
        config_json = os.getenv('DI_CONFIGURATION')
        if not config_json:
            raise ValueError("DI_CONFIGURATION environment variable not set")

        config_data = json.loads(config_json)
        config = DIConfiguration(**config_data)
        return self.build_from_config(config)

    def build_from_config(self, config: DIConfiguration) -> ServiceContainer:
        """Build container from configuration object"""

        # Register services
        for service_config in config.services:
            service_type = self._resolve_type(service_config.service_type)
            impl_type = self._resolve_type(service_config.implementation_type)
            lifetime = ServiceLifetime(service_config.lifetime)

            if service_config.factory:
                factory = self._resolve_factory(service_config.factory, service_config.configuration)
                self.container.register(service_type, factory=factory, lifetime=lifetime)
            else:
                self.container.register(service_type, impl_type, lifetime=lifetime)

        return self.container

    def _resolve_type(self, type_name: str) -> Type:
        """Resolve a type from string name"""
        if type_name in self._type_registry:
            return self._type_registry[type_name]

        # Try to import dynamically
        parts = type_name.split('.')
        module_name = '.'.join(parts[:-1])
        class_name = parts[-1]

        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    def _resolve_factory(self, factory_name: str, config: Dict[str, Any]) -> Callable:
        """Resolve a factory function from string name"""
        parts = factory_name.split('.')
        module_name = '.'.join(parts[:-1])
        func_name = parts[-1]

        module = __import__(module_name, fromlist=[func_name])
        factory_func = getattr(module, func_name)

        # Return a closure that includes configuration
        def configured_factory(container: ServiceContainer):
            return factory_func(container, config or {})

        return configured_factory
```

### 6. Migration Strategy from Current Architecture

```python
# src/di/migration.py
from typing import Any, Dict
from .container import ServiceContainer
from .service_locator import ServiceLocator

class MigrationHelper:
    """Helper for migrating from singleton pattern to DI"""

    def __init__(self, container: ServiceContainer):
        self.container = container
        self._legacy_instances: Dict[str, Any] = {}

    def register_legacy_singleton(self, name: str, instance: Any):
        """Register a legacy singleton instance"""
        self._legacy_instances[name] = instance
        # Also register in DI container for new code
        self.container.register_instance(type(instance), instance)

    def get_legacy_instance(self, name: str) -> Any:
        """Get a legacy singleton instance"""
        return self._legacy_instances.get(name)

    async def migrate_to_di(self, legacy_name: str, service_type: Type):
        """Migrate a legacy singleton to DI-managed service"""
        if legacy_name in self._legacy_instances:
            instance = self._legacy_instances[legacy_name]

            # Register with DI container
            self.container.register_instance(service_type, instance)

            # Remove from legacy registry
            del self._legacy_instances[legacy_name]

            return True
        return False

# Global migration helper
_migration_helper: Optional[MigrationHelper] = None

def get_migration_helper() -> MigrationHelper:
    global _migration_helper
    if _migration_helper is None:
        raise RuntimeError("Migration helper not initialized")
    return _migration_helper

def initialize_migration(container: ServiceContainer):
    global _migration_helper
    _migration_helper = MigrationHelper(container)

# Legacy compatibility functions
def get_plc_manager():
    """Legacy function to get PLC manager - redirects to DI"""
    try:
        return ServiceLocator.get(IPLCInterface)
    except:
        # Fallback to legacy singleton during migration
        helper = get_migration_helper()
        return helper.get_legacy_instance('plc_manager')

def get_data_collection_service():
    """Legacy function to get data collection service - redirects to DI"""
    try:
        return ServiceLocator.get(IParameterLogger)
    except:
        # Fallback to legacy singleton during migration
        helper = get_migration_helper()
        return helper.get_legacy_instance('data_collection_service')
```

## Performance Optimization Strategy

### 1. Service Resolution Performance
- **Target**: < 1ms per resolution
- **Caching**: Pre-computed resolution graphs
- **Lazy Loading**: Services created only when needed
- **Bulk Resolution**: Resolve multiple services in single operation

### 2. Memory Optimization
- **Weak References**: For non-singleton services
- **Scope Management**: Automatic cleanup of scoped services
- **Resource Pooling**: Connection pools and object reuse

### 3. Concurrency Safety
- **Lock-free Operations**: Where possible using atomic operations
- **Minimal Locking**: Fine-grained locks for critical sections
- **Async Compatibility**: Full async/await support throughout

## Integration with Other Agent Findings

### Performance Engineer Coordination
- Support bulk operations identified as bottleneck
- Integration with async pipeline design
- Database connection pooling support

### Data Integrity Specialist Coordination
- Transactional service patterns
- Atomic state management
- Event-driven architecture support

### Security Architect Coordination
- Secure configuration management
- Credential isolation and protection
- Input validation at service boundaries

## Next Steps

1. **Core Container Implementation**: Implement the base ServiceContainer class
2. **Interface Abstractions**: Create all service interfaces
3. **Factory Integration**: Implement factory pattern with DI
4. **Migration Tools**: Create helpers for gradual migration
5. **Configuration System**: Implement config-driven service setup
6. **Testing Framework**: Create DI-compatible testing utilities
7. **Performance Validation**: Benchmark and optimize container performance

This architecture provides a solid foundation for eliminating the architectural violations while maintaining compatibility during migration and optimizing for the performance requirements identified by other agents.