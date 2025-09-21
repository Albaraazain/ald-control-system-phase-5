# File: src/di/container.py
"""
High-performance async-compatible IoC container for dependency injection.
Designed to address architectural violations and enable testable, maintainable code.
"""
from typing import Dict, Any, Type, TypeVar, Generic, Callable, Union, Optional, Set, List
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import weakref
from contextlib import asynccontextmanager
import inspect
import uuid
import time
from dataclasses import dataclass

from src.log_setup import logger

T = TypeVar('T')

class ServiceLifetime(Enum):
    """Service lifetime management options"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"

@dataclass
class ServiceDescriptor(Generic[T]):
    """Describes how a service should be registered and created"""
    service_type: Type[T]
    implementation_type: Optional[Type[T]] = None
    factory: Optional[Callable[..., T]] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    instance: Optional[T] = None
    dependencies: Optional[List[Type]] = None

    def __post_init__(self):
        self.is_async = asyncio.iscoroutinefunction(self.factory) if self.factory else False
        if not self.implementation_type:
            self.implementation_type = self.service_type

class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected"""
    pass

class ServiceNotRegisteredError(Exception):
    """Raised when attempting to resolve an unregistered service"""
    pass

class ServiceContainer:
    """
    High-performance async-compatible IoC container.

    Features:
    - Multiple service lifetimes (singleton, transient, scoped)
    - Async service factories and auto-wiring
    - Circular dependency detection
    - Service health monitoring
    - Thread-safe operations
    - Performance optimized for <1ms resolution time
    """

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_services: Dict[str, Dict[Type, Any]] = {}
        self._resolving: Set[Type] = set()  # Circular dependency detection
        self._lock = asyncio.Lock()
        self._health_monitors: Dict[Type, Callable] = {}
        self._creation_times: Dict[Type, float] = {}
        self._resolution_cache: Dict[Type, Any] = {}
        self._is_disposed = False

    def register(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    ) -> 'ServiceContainer':
        """
        Register a service with the container.

        Args:
            service_type: The interface or abstract type
            implementation_type: Concrete implementation (defaults to service_type)
            factory: Factory function for custom creation
            lifetime: Service lifetime management

        Returns:
            Self for method chaining
        """
        if self._is_disposed:
            raise RuntimeError("Container has been disposed")

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=lifetime
        )

        # Analyze dependencies for auto-wiring
        if not factory and implementation_type:
            descriptor.dependencies = self._analyze_dependencies(implementation_type)

        self._services[service_type] = descriptor

        # Clear cache for this service type
        self._resolution_cache.pop(service_type, None)

        logger.debug(f"Registered service {service_type.__name__} with lifetime {lifetime.value}")
        return self

    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'ServiceContainer':
        """Register a singleton service"""
        return self.register(service_type, implementation_type, factory, ServiceLifetime.SINGLETON)

    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'ServiceContainer':
        """Register a transient service"""
        return self.register(service_type, implementation_type, factory, ServiceLifetime.TRANSIENT)

    def register_scoped(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'ServiceContainer':
        """Register a scoped service"""
        return self.register(service_type, implementation_type, factory, ServiceLifetime.SCOPED)

    def register_instance(self, service_type: Type[T], instance: T) -> 'ServiceContainer':
        """Register a service instance directly"""
        if self._is_disposed:
            raise RuntimeError("Container has been disposed")

        descriptor = ServiceDescriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.SINGLETON,
            instance=instance
        )
        self._services[service_type] = descriptor
        self._singletons[service_type] = instance

        logger.debug(f"Registered instance for {service_type.__name__}")
        return self

    async def resolve(self, service_type: Type[T], scope_id: Optional[str] = None) -> T:
        """
        Resolve a service from the container.

        Args:
            service_type: The service type to resolve
            scope_id: Optional scope identifier for scoped services

        Returns:
            Service instance

        Raises:
            ServiceNotRegisteredError: If service is not registered
            CircularDependencyError: If circular dependency detected
        """
        if self._is_disposed:
            raise RuntimeError("Container has been disposed")

        start_time = time.perf_counter()

        try:
            # Check for circular dependencies
            if service_type in self._resolving:
                chain = " -> ".join([t.__name__ for t in self._resolving])
                raise CircularDependencyError(
                    f"Circular dependency detected: {chain} -> {service_type.__name__}"
                )

            descriptor = self._services.get(service_type)
            if not descriptor:
                raise ServiceNotRegisteredError(f"Service {service_type.__name__} not registered")

            # Handle different lifetimes
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                instance = await self._resolve_singleton(service_type, descriptor)
            elif descriptor.lifetime == ServiceLifetime.SCOPED and scope_id:
                instance = await self._resolve_scoped(service_type, descriptor, scope_id)
            else:
                instance = await self._resolve_transient(service_type, descriptor)

            resolution_time = (time.perf_counter() - start_time) * 1000
            if resolution_time > 1.0:  # Log if resolution takes > 1ms
                logger.warning(
                    f"Slow service resolution: {service_type.__name__} took {resolution_time:.2f}ms"
                )

            return instance

        except Exception as e:
            logger.error(f"Failed to resolve service {service_type.__name__}: {str(e)}")
            raise

    async def _resolve_singleton(self, service_type: Type[T], descriptor: ServiceDescriptor[T]) -> T:
        """Resolve a singleton service with thread safety"""
        # Fast path: check if already created
        if service_type in self._singletons:
            return self._singletons[service_type]

        # Slow path: create with lock
        async with self._lock:
            # Double-check pattern
            if service_type in self._singletons:
                return self._singletons[service_type]

            instance = await self._create_instance(service_type, descriptor)
            self._singletons[service_type] = instance
            self._creation_times[service_type] = time.time()

            logger.debug(f"Created singleton instance for {service_type.__name__}")
            return instance

    async def _resolve_scoped(self, service_type: Type[T], descriptor: ServiceDescriptor[T], scope_id: str) -> T:
        """Resolve a scoped service"""
        if scope_id not in self._scoped_services:
            self._scoped_services[scope_id] = {}

        scoped_container = self._scoped_services[scope_id]
        if service_type in scoped_container:
            return scoped_container[service_type]

        instance = await self._create_instance(service_type, descriptor)
        scoped_container[service_type] = instance

        logger.debug(f"Created scoped instance for {service_type.__name__} in scope {scope_id}")
        return instance

    async def _resolve_transient(self, service_type: Type[T], descriptor: ServiceDescriptor[T]) -> T:
        """Resolve a transient service"""
        instance = await self._create_instance(service_type, descriptor)
        logger.debug(f"Created transient instance for {service_type.__name__}")
        return instance

    async def _create_instance(self, service_type: Type[T], descriptor: ServiceDescriptor[T]) -> T:
        """Create a service instance using the appropriate method"""
        self._resolving.add(service_type)
        try:
            # Return existing instance if available
            if descriptor.instance is not None:
                return descriptor.instance

            # Use factory if provided
            if descriptor.factory:
                if descriptor.is_async:
                    return await descriptor.factory(self)
                else:
                    result = descriptor.factory(self)
                    # Handle factory that returns a coroutine
                    if asyncio.iscoroutine(result):
                        return await result
                    return result

            # Auto-wire constructor dependencies
            return await self._auto_wire(descriptor.implementation_type)

        finally:
            self._resolving.discard(service_type)

    async def _auto_wire(self, implementation_type: Type[T]) -> T:
        """Auto-wire constructor dependencies using type hints"""
        try:
            sig = inspect.signature(implementation_type.__init__)
            kwargs = {}

            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                # Check for type annotation
                if param.annotation and param.annotation != inspect.Parameter.empty:
                    # Handle optional parameters
                    if hasattr(param.annotation, '__origin__') and param.annotation.__origin__ is Union:
                        # Handle Optional[T] which is Union[T, None]
                        args = param.annotation.__args__
                        if len(args) == 2 and type(None) in args:
                            non_none_type = args[0] if args[1] is type(None) else args[1]
                            if non_none_type in self._services:
                                kwargs[param_name] = await self.resolve(non_none_type)
                    else:
                        # Required dependency
                        if param.annotation in self._services:
                            kwargs[param_name] = await self.resolve(param.annotation)
                        elif param.default == inspect.Parameter.empty:
                            logger.warning(
                                f"Cannot resolve required dependency {param.annotation.__name__} "
                                f"for {implementation_type.__name__}"
                            )

            return implementation_type(**kwargs)

        except Exception as e:
            logger.error(f"Auto-wiring failed for {implementation_type.__name__}: {str(e)}")
            raise

    def _analyze_dependencies(self, implementation_type: Type) -> List[Type]:
        """Analyze constructor dependencies for a type"""
        dependencies = []
        try:
            sig = inspect.signature(implementation_type.__init__)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                if param.annotation and param.annotation != inspect.Parameter.empty:
                    dependencies.append(param.annotation)
        except Exception:
            pass  # Ignore analysis errors

        return dependencies

    @asynccontextmanager
    async def create_scope(self, scope_id: str = None):
        """
        Create a service scope for scoped services.

        Args:
            scope_id: Optional scope identifier

        Yields:
            scope_id: The scope identifier for use with resolve()
        """
        scope_id = scope_id or str(uuid.uuid4())

        logger.debug(f"Creating service scope {scope_id}")

        try:
            yield scope_id
        finally:
            await self._cleanup_scope(scope_id)

    async def _cleanup_scope(self, scope_id: str):
        """Cleanup scoped services for a scope"""
        if scope_id in self._scoped_services:
            scoped_services = self._scoped_services[scope_id]

            # Dispose services in reverse order of creation
            for service in reversed(list(scoped_services.values())):
                if hasattr(service, 'dispose'):
                    try:
                        dispose_method = getattr(service, 'dispose')
                        if asyncio.iscoroutinefunction(dispose_method):
                            await dispose_method()
                        else:
                            dispose_method()
                    except Exception as e:
                        logger.error(f"Error disposing scoped service: {str(e)}")

            del self._scoped_services[scope_id]
            logger.debug(f"Cleaned up service scope {scope_id}")

    async def health_check(self) -> Dict[Type, bool]:
        """
        Perform health checks on registered services.

        Returns:
            Dictionary mapping service types to health status
        """
        results = {}

        for service_type, monitor in self._health_monitors.items():
            try:
                if service_type in self._singletons:
                    service = self._singletons[service_type]
                    if asyncio.iscoroutinefunction(monitor):
                        results[service_type] = await monitor(service)
                    else:
                        results[service_type] = monitor(service)
                else:
                    results[service_type] = True  # Not instantiated yet
            except Exception as e:
                logger.error(f"Health check failed for {service_type.__name__}: {str(e)}")
                results[service_type] = False

        return results

    def register_health_monitor(self, service_type: Type, monitor: Callable[[Any], bool]):
        """Register a health monitor for a service"""
        self._health_monitors[service_type] = monitor
        logger.debug(f"Registered health monitor for {service_type.__name__}")

    def get_service_info(self, service_type: Type) -> Optional[Dict[str, Any]]:
        """Get information about a registered service"""
        descriptor = self._services.get(service_type)
        if not descriptor:
            return None

        return {
            'service_type': service_type.__name__,
            'implementation_type': descriptor.implementation_type.__name__,
            'lifetime': descriptor.lifetime.value,
            'has_factory': descriptor.factory is not None,
            'dependencies': [dep.__name__ for dep in (descriptor.dependencies or [])],
            'is_singleton_created': service_type in self._singletons,
            'creation_time': self._creation_times.get(service_type)
        }

    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get information about all registered services"""
        return [self.get_service_info(service_type) for service_type in self._services.keys()]

    async def dispose(self):
        """Dispose all services and cleanup resources"""
        if self._is_disposed:
            return

        logger.info("Disposing service container...")

        try:
            # Dispose singletons in reverse order of creation
            singleton_items = sorted(
                self._singletons.items(),
                key=lambda x: self._creation_times.get(x[0], 0),
                reverse=True
            )

            for service_type, service in singleton_items:
                if hasattr(service, 'dispose'):
                    try:
                        dispose_method = getattr(service, 'dispose')
                        if asyncio.iscoroutinefunction(dispose_method):
                            await dispose_method()
                        else:
                            dispose_method()
                        logger.debug(f"Disposed singleton service {service_type.__name__}")
                    except Exception as e:
                        logger.error(f"Error disposing {service_type.__name__}: {str(e)}")

            # Cleanup scoped services
            for scope_id in list(self._scoped_services.keys()):
                await self._cleanup_scope(scope_id)

            # Clear all containers
            self._singletons.clear()
            self._scoped_services.clear()
            self._services.clear()
            self._health_monitors.clear()
            self._creation_times.clear()
            self._resolution_cache.clear()
            self._resolving.clear()

            self._is_disposed = True
            logger.info("Service container disposed successfully")

        except Exception as e:
            logger.error(f"Error during container disposal: {str(e)}")
            raise

    def __del__(self):
        """Ensure cleanup on garbage collection"""
        if not self._is_disposed and self._singletons:
            logger.warning("Service container was not properly disposed")