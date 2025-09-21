# File: src/di/factories.py
"""
Factory pattern integration with dependency injection container.
Provides configuration-driven service creation and factory registration.
"""
from typing import Type, Dict, Any, Callable, TypeVar, Optional, Awaitable, Union
from abc import ABC, abstractmethod
from .container import ServiceContainer
from ..abstractions.interfaces import IPLCInterface, IDatabaseService, IParameterLogger

from src.log_setup import logger

T = TypeVar('T')

class ServiceFactory(ABC):
    """Abstract base factory for creating services"""

    @abstractmethod
    async def create(self, container: ServiceContainer, config: Dict[str, Any]) -> Any:
        """Create a service instance with configuration"""
        pass

    @abstractmethod
    def get_service_type(self) -> Type:
        """Get the service type this factory creates"""
        pass

class PLCServiceFactory:
    """Factory for creating PLC interfaces with DI support"""

    _factories: Dict[str, Callable[[ServiceContainer, Dict[str, Any]], Awaitable[IPLCInterface]]] = {}

    @classmethod
    def register(cls, plc_type: str, factory: Callable[[ServiceContainer, Dict[str, Any]], Awaitable[IPLCInterface]]):
        """
        Register a PLC factory.

        Args:
            plc_type: Type identifier for the PLC (e.g., 'real', 'simulation')
            factory: Async factory function that creates the PLC interface
        """
        cls._factories[plc_type] = factory
        logger.debug(f"Registered PLC factory for type '{plc_type}'")

    @classmethod
    async def create(cls, plc_type: str, container: ServiceContainer, config: Optional[Dict[str, Any]] = None) -> IPLCInterface:
        """
        Create a PLC interface using the registered factory.

        Args:
            plc_type: Type of PLC to create
            container: DI container for dependency resolution
            config: Optional configuration parameters

        Returns:
            PLC interface instance

        Raises:
            ValueError: If PLC type is not registered
        """
        if plc_type not in cls._factories:
            raise ValueError(f"Unknown PLC type: {plc_type}. Registered types: {list(cls._factories.keys())}")

        factory = cls._factories[plc_type]
        config = config or {}

        logger.info(f"Creating PLC interface for type '{plc_type}'")
        try:
            plc_interface = await factory(container, config)
            logger.info(f"Successfully created PLC interface for type '{plc_type}'")
            return plc_interface
        except Exception as e:
            logger.error(f"Failed to create PLC interface for type '{plc_type}': {str(e)}")
            raise

    @classmethod
    def get_registered_types(cls) -> List[str]:
        """Get list of registered PLC types"""
        return list(cls._factories.keys())

    @classmethod
    def is_registered(cls, plc_type: str) -> bool:
        """Check if a PLC type is registered"""
        return plc_type in cls._factories

class DatabaseServiceFactory:
    """Factory for creating database services with DI support"""

    _factories: Dict[str, Callable[[ServiceContainer, Dict[str, Any]], Awaitable[IDatabaseService]]] = {}

    @classmethod
    def register(cls, db_type: str, factory: Callable[[ServiceContainer, Dict[str, Any]], Awaitable[IDatabaseService]]):
        """
        Register a database factory.

        Args:
            db_type: Type identifier for the database (e.g., 'supabase', 'postgresql')
            factory: Async factory function that creates the database service
        """
        cls._factories[db_type] = factory
        logger.debug(f"Registered database factory for type '{db_type}'")

    @classmethod
    async def create(cls, db_type: str, container: ServiceContainer, config: Optional[Dict[str, Any]] = None) -> IDatabaseService:
        """
        Create a database service using the registered factory.

        Args:
            db_type: Type of database service to create
            container: DI container for dependency resolution
            config: Optional configuration parameters

        Returns:
            Database service instance

        Raises:
            ValueError: If database type is not registered
        """
        if db_type not in cls._factories:
            raise ValueError(f"Unknown database type: {db_type}. Registered types: {list(cls._factories.keys())}")

        factory = cls._factories[db_type]
        config = config or {}

        logger.info(f"Creating database service for type '{db_type}'")
        try:
            db_service = await factory(container, config)
            logger.info(f"Successfully created database service for type '{db_type}'")
            return db_service
        except Exception as e:
            logger.error(f"Failed to create database service for type '{db_type}': {str(e)}")
            raise

    @classmethod
    def get_registered_types(cls) -> List[str]:
        """Get list of registered database types"""
        return list(cls._factories.keys())

    @classmethod
    def is_registered(cls, db_type: str) -> bool:
        """Check if a database type is registered"""
        return db_type in cls._factories

class ParameterLoggerFactory:
    """Factory for creating parameter logger services"""

    _factories: Dict[str, Callable[[ServiceContainer, Dict[str, Any]], Awaitable[IParameterLogger]]] = {}

    @classmethod
    def register(cls, logger_type: str, factory: Callable[[ServiceContainer, Dict[str, Any]], Awaitable[IParameterLogger]]):
        """
        Register a parameter logger factory.

        Args:
            logger_type: Type identifier for the logger (e.g., 'continuous', 'high_performance')
            factory: Async factory function that creates the parameter logger
        """
        cls._factories[logger_type] = factory
        logger.debug(f"Registered parameter logger factory for type '{logger_type}'")

    @classmethod
    async def create(cls, logger_type: str, container: ServiceContainer, config: Optional[Dict[str, Any]] = None) -> IParameterLogger:
        """
        Create a parameter logger using the registered factory.

        Args:
            logger_type: Type of parameter logger to create
            container: DI container for dependency resolution
            config: Optional configuration parameters

        Returns:
            Parameter logger instance

        Raises:
            ValueError: If logger type is not registered
        """
        if logger_type not in cls._factories:
            raise ValueError(f"Unknown parameter logger type: {logger_type}. Registered types: {list(cls._factories.keys())}")

        factory = cls._factories[logger_type]
        config = config or {}

        logger.info(f"Creating parameter logger for type '{logger_type}'")
        try:
            param_logger = await factory(container, config)
            logger.info(f"Successfully created parameter logger for type '{logger_type}'")
            return param_logger
        except Exception as e:
            logger.error(f"Failed to create parameter logger for type '{logger_type}': {str(e)}")
            raise

    @classmethod
    def get_registered_types(cls) -> List[str]:
        """Get list of registered parameter logger types"""
        return list(cls._factories.keys())

# Factory registration decorators
def register_plc_factory(plc_type: str):
    """
    Decorator for registering PLC factories.

    Args:
        plc_type: Type identifier for the PLC

    Example:
        @register_plc_factory('real')
        async def create_real_plc(container: ServiceContainer, config: Dict[str, Any]) -> IPLCInterface:
            # Factory implementation
            pass
    """
    def decorator(factory_func):
        PLCServiceFactory.register(plc_type, factory_func)
        return factory_func
    return decorator

def register_database_factory(db_type: str):
    """
    Decorator for registering database factories.

    Args:
        db_type: Type identifier for the database

    Example:
        @register_database_factory('supabase')
        async def create_supabase_service(container: ServiceContainer, config: Dict[str, Any]) -> IDatabaseService:
            # Factory implementation
            pass
    """
    def decorator(factory_func):
        DatabaseServiceFactory.register(db_type, factory_func)
        return factory_func
    return decorator

def register_parameter_logger_factory(logger_type: str):
    """
    Decorator for registering parameter logger factories.

    Args:
        logger_type: Type identifier for the parameter logger

    Example:
        @register_parameter_logger_factory('high_performance')
        async def create_hp_logger(container: ServiceContainer, config: Dict[str, Any]) -> IParameterLogger:
            # Factory implementation
            pass
    """
    def decorator(factory_func):
        ParameterLoggerFactory.register(logger_type, factory_func)
        return factory_func
    return decorator

class GenericServiceFactory:
    """Generic factory for any service type with configuration-based creation"""

    def __init__(self, service_type: Type[T], implementation_type: Type[T]):
        self.service_type = service_type
        self.implementation_type = implementation_type

    async def create(self, container: ServiceContainer, config: Optional[Dict[str, Any]] = None) -> T:
        """
        Create a service instance with optional configuration.

        Args:
            container: DI container for dependency resolution
            config: Optional configuration parameters

        Returns:
            Service instance
        """
        # Use the container's auto-wiring capabilities
        return await container._auto_wire(self.implementation_type)

class ConfigurableServiceFactory:
    """Factory that creates services based on configuration parameters"""

    def __init__(self, service_type: Type[T]):
        self.service_type = service_type
        self._implementations: Dict[str, Type[T]] = {}
        self._default_implementation: Optional[Type[T]] = None

    def register_implementation(self, name: str, implementation_type: Type[T], is_default: bool = False):
        """
        Register an implementation variant.

        Args:
            name: Name of the implementation variant
            implementation_type: The implementation class
            is_default: Whether this is the default implementation
        """
        self._implementations[name] = implementation_type
        if is_default or not self._default_implementation:
            self._default_implementation = implementation_type

        logger.debug(f"Registered implementation '{name}' for service {self.service_type.__name__}")

    async def create(self, container: ServiceContainer, config: Optional[Dict[str, Any]] = None) -> T:
        """
        Create a service instance based on configuration.

        Args:
            container: DI container for dependency resolution
            config: Configuration parameters (should include 'implementation' key)

        Returns:
            Service instance
        """
        config = config or {}
        implementation_name = config.get('implementation', 'default')

        # Resolve implementation type
        if implementation_name == 'default':
            implementation_type = self._default_implementation
        else:
            implementation_type = self._implementations.get(implementation_name)

        if not implementation_type:
            available = list(self._implementations.keys()) + ['default']
            raise ValueError(
                f"Unknown implementation '{implementation_name}' for {self.service_type.__name__}. "
                f"Available: {available}"
            )

        logger.debug(f"Creating {self.service_type.__name__} with implementation '{implementation_name}'")

        # Use container's auto-wiring for dependency injection
        return await container._auto_wire(implementation_type)

# Utility functions for factory management
def register_factories_from_config(container: ServiceContainer, config: Dict[str, Any]):
    """
    Register services and factories from configuration.

    Args:
        container: DI container to register services with
        config: Configuration dictionary with factory definitions
    """
    factories_config = config.get('factories', {})

    for service_name, factory_config in factories_config.items():
        factory_type = factory_config.get('type')
        service_config = factory_config.get('config', {})

        if factory_type == 'plc':
            # Register PLC service with factory
            plc_type = service_config.get('plc_type', 'real')

            async def plc_factory(cont: ServiceContainer) -> IPLCInterface:
                return await PLCServiceFactory.create(plc_type, cont, service_config)

            container.register_singleton(IPLCInterface, factory=plc_factory)

        elif factory_type == 'database':
            # Register database service with factory
            db_type = service_config.get('db_type', 'supabase')

            async def db_factory(cont: ServiceContainer) -> IDatabaseService:
                return await DatabaseServiceFactory.create(db_type, cont, service_config)

            container.register_singleton(IDatabaseService, factory=db_factory)

        elif factory_type == 'parameter_logger':
            # Register parameter logger with factory
            logger_type = service_config.get('logger_type', 'continuous')

            async def logger_factory(cont: ServiceContainer) -> IParameterLogger:
                return await ParameterLoggerFactory.create(logger_type, cont, service_config)

            container.register_singleton(IParameterLogger, factory=logger_factory)

        else:
            logger.warning(f"Unknown factory type '{factory_type}' for service '{service_name}'")

    logger.info(f"Registered {len(factories_config)} factory-based services from configuration")