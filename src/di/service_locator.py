# File: src/di/service_locator.py
"""
Service locator pattern implementation for global access to the DI container.
Provides a bridge between the current singleton pattern and the new DI architecture.
"""
from typing import Type, TypeVar, Optional, Dict, Any
from .container import ServiceContainer, ServiceNotRegisteredError

from src.log_setup import logger

T = TypeVar('T')

class ServiceLocator:
    """
    Global service locator for accessing the DI container.

    Provides a static interface for service resolution while maintaining
    the flexibility of the underlying container architecture.
    """

    _container: Optional[ServiceContainer] = None
    _current_scope: Optional[str] = None
    _is_configured = False

    @classmethod
    def configure(cls, container: ServiceContainer) -> None:
        """
        Configure the service locator with a container.

        Args:
            container: The service container to use for resolution
        """
        cls._container = container
        cls._is_configured = True
        logger.info("ServiceLocator configured with DI container")

    @classmethod
    async def get(cls, service_type: Type[T]) -> T:
        """
        Get a service from the container.

        Args:
            service_type: The service type to resolve

        Returns:
            Service instance

        Raises:
            RuntimeError: If ServiceLocator not configured
            ServiceNotRegisteredError: If service is not registered
        """
        if not cls._is_configured or not cls._container:
            raise RuntimeError(
                "ServiceLocator not configured. Call ServiceLocator.configure(container) first."
            )

        try:
            return await cls._container.resolve(service_type, cls._current_scope)
        except Exception as e:
            logger.error(f"Failed to resolve service {service_type.__name__} via ServiceLocator: {str(e)}")
            raise

    @classmethod
    def get_sync(cls, service_type: Type[T]) -> T:
        """
        Get a service synchronously (for non-async contexts).

        Note: This should only be used for services that are already instantiated
        (like singletons) or have sync factories.

        Args:
            service_type: The service type to resolve

        Returns:
            Service instance

        Raises:
            RuntimeError: If ServiceLocator not configured or service requires async resolution
        """
        if not cls._is_configured or not cls._container:
            raise RuntimeError(
                "ServiceLocator not configured. Call ServiceLocator.configure(container) first."
            )

        # Check if it's a singleton that's already created
        if hasattr(cls._container, '_singletons') and service_type in cls._container._singletons:
            return cls._container._singletons[service_type]

        # For non-async services, we can try direct instantiation
        descriptor = cls._container._services.get(service_type)
        if not descriptor:
            raise ServiceNotRegisteredError(f"Service {service_type.__name__} not registered")

        if descriptor.factory and descriptor.is_async:
            raise RuntimeError(
                f"Service {service_type.__name__} requires async resolution. Use ServiceLocator.get() instead."
            )

        # This is a simplified sync path - should be used sparingly
        logger.warning(f"Synchronous resolution of {service_type.__name__} - consider using async version")

        if descriptor.instance:
            return descriptor.instance

        if descriptor.factory:
            return descriptor.factory(cls._container)

        # Direct instantiation (no auto-wiring in sync mode)
        return descriptor.implementation_type()

    @classmethod
    def try_get(cls, service_type: Type[T]) -> Optional[T]:
        """
        Try to get a service, returning None if not available.

        Args:
            service_type: The service type to resolve

        Returns:
            Service instance or None if not available
        """
        try:
            return cls.get_sync(service_type)
        except Exception:
            return None

    @classmethod
    async def try_get_async(cls, service_type: Type[T]) -> Optional[T]:
        """
        Try to get a service asynchronously, returning None if not available.

        Args:
            service_type: The service type to resolve

        Returns:
            Service instance or None if not available
        """
        try:
            return await cls.get(service_type)
        except Exception:
            return None

    @classmethod
    def set_scope(cls, scope_id: str) -> None:
        """
        Set the current scope for scoped services.

        Args:
            scope_id: The scope identifier
        """
        cls._current_scope = scope_id
        logger.debug(f"ServiceLocator scope set to {scope_id}")

    @classmethod
    def clear_scope(cls) -> None:
        """Clear the current scope."""
        cls._current_scope = None
        logger.debug("ServiceLocator scope cleared")

    @classmethod
    def get_current_scope(cls) -> Optional[str]:
        """Get the current scope identifier."""
        return cls._current_scope

    @classmethod
    async def health_check(cls) -> Dict[Type, bool]:
        """
        Perform health check on all services.

        Returns:
            Dictionary mapping service types to health status
        """
        if not cls._is_configured or not cls._container:
            return {}

        return await cls._container.health_check()

    @classmethod
    def get_service_info(cls, service_type: Type) -> Optional[Dict[str, Any]]:
        """
        Get information about a registered service.

        Args:
            service_type: The service type to query

        Returns:
            Service information or None if not registered
        """
        if not cls._is_configured or not cls._container:
            return None

        return cls._container.get_service_info(service_type)

    @classmethod
    def get_all_services(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered services.

        Returns:
            Dictionary of service information
        """
        if not cls._is_configured or not cls._container:
            return {}

        services = cls._container.get_all_services()
        return {service['service_type']: service for service in services}

    @classmethod
    def is_configured(cls) -> bool:
        """Check if the service locator is configured."""
        return cls._is_configured

    @classmethod
    def is_service_registered(cls, service_type: Type) -> bool:
        """
        Check if a service type is registered.

        Args:
            service_type: The service type to check

        Returns:
            True if registered, False otherwise
        """
        if not cls._is_configured or not cls._container:
            return False

        return service_type in cls._container._services

    @classmethod
    async def dispose(cls) -> None:
        """Dispose the underlying container and reset the locator."""
        if cls._container:
            await cls._container.dispose()

        cls._container = None
        cls._current_scope = None
        cls._is_configured = False
        logger.info("ServiceLocator disposed and reset")

    @classmethod
    def reset(cls) -> None:
        """Reset the service locator (for testing purposes)."""
        cls._container = None
        cls._current_scope = None
        cls._is_configured = False
        logger.debug("ServiceLocator reset")