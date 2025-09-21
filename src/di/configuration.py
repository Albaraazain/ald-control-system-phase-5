# File: src/di/configuration.py
"""
Configuration-driven dependency injection container builder.
Supports loading service registrations from JSON files and environment variables.
"""
from typing import Dict, Any, Type, Optional, List, Callable
from dataclasses import dataclass, field
from .container import ServiceContainer, ServiceLifetime
from .factories import PLCServiceFactory, DatabaseServiceFactory, ParameterLoggerFactory
import json
import os
import importlib

from src.log_setup import logger

@dataclass
class ServiceConfiguration:
    """Configuration for a single service registration"""
    service_type: str
    implementation_type: Optional[str] = None
    lifetime: str = "transient"
    factory: Optional[str] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

@dataclass
class DIConfiguration:
    """Complete dependency injection configuration"""
    services: List[ServiceConfiguration] = field(default_factory=list)
    factories: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    environment: str = "development"
    debug: bool = False

class ConfigurationBasedContainerBuilder:
    """Builder for creating DI containers from configuration files"""

    def __init__(self):
        self.container = ServiceContainer()
        self._type_registry: Dict[str, Type] = {}
        self._factory_registry: Dict[str, Callable] = {}

    def register_type(self, name: str, type_class: Type) -> 'ConfigurationBasedContainerBuilder':
        """
        Register a type for configuration-based resolution.

        Args:
            name: String name to use in configuration
            type_class: The actual type/class

        Returns:
            Self for method chaining
        """
        self._type_registry[name] = type_class
        logger.debug(f"Registered type '{name}' -> {type_class.__name__}")
        return self

    def register_factory(self, name: str, factory: Callable) -> 'ConfigurationBasedContainerBuilder':
        """
        Register a factory function for configuration-based creation.

        Args:
            name: String name to use in configuration
            factory: Factory function

        Returns:
            Self for method chaining
        """
        self._factory_registry[name] = factory
        logger.debug(f"Registered factory '{name}'")
        return self

    def load_from_json(self, config_path: str) -> ServiceContainer:
        """
        Load container configuration from JSON file.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            Configured service container

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If JSON is invalid
            ValueError: If configuration is invalid
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        logger.info(f"Loading DI configuration from {config_path}")

        with open(config_path, 'r') as f:
            config_data = json.load(f)

        # Validate and create configuration object
        config = self._create_configuration(config_data)

        return self.build_from_config(config)

    def load_from_environment(self, env_var: str = 'DI_CONFIGURATION') -> ServiceContainer:
        """
        Load container configuration from environment variable.

        Args:
            env_var: Environment variable containing JSON configuration

        Returns:
            Configured service container

        Raises:
            ValueError: If environment variable not set or JSON invalid
        """
        config_json = os.getenv(env_var)
        if not config_json:
            raise ValueError(f"Environment variable '{env_var}' not set")

        logger.info(f"Loading DI configuration from environment variable {env_var}")

        try:
            config_data = json.loads(config_json)
            config = self._create_configuration(config_data)
            return self.build_from_config(config)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in environment variable '{env_var}': {str(e)}")

    def build_from_config(self, config: DIConfiguration) -> ServiceContainer:
        """
        Build container from configuration object.

        Args:
            config: DIConfiguration object

        Returns:
            Configured service container
        """
        logger.info(f"Building DI container for environment '{config.environment}' with {len(config.services)} services")

        # Configure container debug mode
        if hasattr(self.container, '_debug'):
            self.container._debug = config.debug

        # Register factories first
        self._register_factories(config.factories)

        # Register services
        for service_config in config.services:
            self._register_service(service_config)

        logger.info(f"Successfully configured DI container with {len(config.services)} services")
        return self.container

    def build_default_container(self) -> ServiceContainer:
        """
        Build a container with sensible defaults for the ALD system.

        Returns:
            Container with default service registrations
        """
        logger.info("Building default DI container for ALD system")

        # Register core interfaces
        from ..abstractions.interfaces import (
            IPLCInterface, IDatabaseService, IParameterLogger,
            IConfigurationService, IStateManager, IEventBus
        )

        self.register_type('IPLCInterface', IPLCInterface)
        self.register_type('IDatabaseService', IDatabaseService)
        self.register_type('IParameterLogger', IParameterLogger)
        self.register_type('IConfigurationService', IConfigurationService)
        self.register_type('IStateManager', IStateManager)
        self.register_type('IEventBus', IEventBus)

        # Create default configuration
        default_config = DIConfiguration(
            services=[
                ServiceConfiguration(
                    service_type='IPLCInterface',
                    factory='create_plc_service',
                    lifetime='singleton',
                    configuration={'plc_type': 'real'}
                ),
                ServiceConfiguration(
                    service_type='IDatabaseService',
                    factory='create_database_service',
                    lifetime='singleton',
                    configuration={'db_type': 'supabase'}
                ),
                ServiceConfiguration(
                    service_type='IParameterLogger',
                    factory='create_parameter_logger',
                    lifetime='singleton',
                    configuration={'logger_type': 'continuous'}
                )
            ],
            environment=os.getenv('ENVIRONMENT', 'development'),
            debug=os.getenv('DI_DEBUG', 'false').lower() == 'true'
        )

        # Register default factories
        self._register_default_factories()

        return self.build_from_config(default_config)

    def _create_configuration(self, config_data: Dict[str, Any]) -> DIConfiguration:
        """Create DIConfiguration object from dictionary"""
        services = []

        for service_data in config_data.get('services', []):
            service_config = ServiceConfiguration(
                service_type=service_data['service_type'],
                implementation_type=service_data.get('implementation_type'),
                lifetime=service_data.get('lifetime', 'transient'),
                factory=service_data.get('factory'),
                configuration=service_data.get('configuration', {}),
                dependencies=service_data.get('dependencies', [])
            )
            services.append(service_config)

        return DIConfiguration(
            services=services,
            factories=config_data.get('factories', {}),
            environment=config_data.get('environment', 'development'),
            debug=config_data.get('debug', False)
        )

    def _register_factories(self, factories_config: Dict[str, Dict[str, Any]]):
        """Register factories from configuration"""
        for factory_name, factory_config in factories_config.items():
            factory_type = factory_config.get('type')

            if factory_type == 'plc':
                self._register_plc_factories(factory_config)
            elif factory_type == 'database':
                self._register_database_factories(factory_config)
            elif factory_type == 'parameter_logger':
                self._register_parameter_logger_factories(factory_config)
            else:
                logger.warning(f"Unknown factory type '{factory_type}' for factory '{factory_name}'")

    def _register_plc_factories(self, config: Dict[str, Any]):
        """Register PLC factories from configuration"""
        plc_types = config.get('plc_types', {})

        for plc_type, factory_path in plc_types.items():
            factory_func = self._resolve_factory_function(factory_path)
            if factory_func:
                PLCServiceFactory.register(plc_type, factory_func)

    def _register_database_factories(self, config: Dict[str, Any]):
        """Register database factories from configuration"""
        db_types = config.get('db_types', {})

        for db_type, factory_path in db_types.items():
            factory_func = self._resolve_factory_function(factory_path)
            if factory_func:
                DatabaseServiceFactory.register(db_type, factory_func)

    def _register_parameter_logger_factories(self, config: Dict[str, Any]):
        """Register parameter logger factories from configuration"""
        logger_types = config.get('logger_types', {})

        for logger_type, factory_path in logger_types.items():
            factory_func = self._resolve_factory_function(factory_path)
            if factory_func:
                ParameterLoggerFactory.register(logger_type, factory_func)

    def _register_default_factories(self):
        """Register default factories for the ALD system"""

        # Default PLC factory
        async def create_plc_service(container: ServiceContainer, config: Dict[str, Any]):
            plc_type = config.get('plc_type', 'real')
            return await PLCServiceFactory.create(plc_type, container, config)

        # Default database factory
        async def create_database_service(container: ServiceContainer, config: Dict[str, Any]):
            db_type = config.get('db_type', 'supabase')
            return await DatabaseServiceFactory.create(db_type, container, config)

        # Default parameter logger factory
        async def create_parameter_logger(container: ServiceContainer, config: Dict[str, Any]):
            logger_type = config.get('logger_type', 'continuous')
            return await ParameterLoggerFactory.create(logger_type, container, config)

        self.register_factory('create_plc_service', create_plc_service)
        self.register_factory('create_database_service', create_database_service)
        self.register_factory('create_parameter_logger', create_parameter_logger)

    def _register_service(self, service_config: ServiceConfiguration):
        """Register a single service from configuration"""
        try:
            service_type = self._resolve_type(service_config.service_type)
            lifetime = ServiceLifetime(service_config.lifetime)

            if service_config.factory:
                # Use factory for service creation
                factory = self._resolve_factory(service_config.factory, service_config.configuration)
                self.container.register(service_type, factory=factory, lifetime=lifetime)

            elif service_config.implementation_type:
                # Use implementation type
                impl_type = self._resolve_type(service_config.implementation_type)
                self.container.register(service_type, impl_type, lifetime=lifetime)

            else:
                # Self-registration (interface is also implementation)
                self.container.register(service_type, lifetime=lifetime)

            logger.debug(f"Registered service {service_config.service_type} with lifetime {lifetime.value}")

        except Exception as e:
            logger.error(f"Failed to register service {service_config.service_type}: {str(e)}")
            raise

    def _resolve_type(self, type_name: str) -> Type:
        """Resolve a type from string name"""
        # Check registered types first
        if type_name in self._type_registry:
            return self._type_registry[type_name]

        # Try dynamic import
        try:
            if '.' in type_name:
                # Full module path provided
                parts = type_name.split('.')
                module_name = '.'.join(parts[:-1])
                class_name = parts[-1]

                module = importlib.import_module(module_name)
                return getattr(module, class_name)
            else:
                # Assume it's in the current package
                raise ValueError(f"Type '{type_name}' not registered and cannot be imported")

        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot resolve type '{type_name}': {str(e)}")

    def _resolve_factory(self, factory_name: str, config: Dict[str, Any]) -> Callable:
        """Resolve a factory function from string name"""
        # Check registered factories first
        if factory_name in self._factory_registry:
            factory_func = self._factory_registry[factory_name]

            # Return a closure that includes configuration
            async def configured_factory(container: ServiceContainer):
                return await factory_func(container, config)

            return configured_factory

        # Try to resolve from module path
        return self._resolve_factory_function(factory_name, config)

    def _resolve_factory_function(self, factory_path: str, config: Optional[Dict[str, Any]] = None) -> Optional[Callable]:
        """Resolve a factory function from module path"""
        try:
            parts = factory_path.split('.')
            module_name = '.'.join(parts[:-1])
            func_name = parts[-1]

            module = importlib.import_module(module_name)
            factory_func = getattr(module, func_name)

            if config:
                # Return configured factory
                async def configured_factory(container: ServiceContainer):
                    return await factory_func(container, config)
                return configured_factory
            else:
                return factory_func

        except (ImportError, AttributeError) as e:
            logger.error(f"Cannot resolve factory function '{factory_path}': {str(e)}")
            return None

def create_container_from_config(config_path: str) -> ServiceContainer:
    """
    Convenience function to create a container from configuration file.

    Args:
        config_path: Path to JSON configuration file

    Returns:
        Configured service container
    """
    builder = ConfigurationBasedContainerBuilder()
    return builder.load_from_json(config_path)

def create_default_container() -> ServiceContainer:
    """
    Convenience function to create a container with default ALD system configuration.

    Returns:
        Container with default service registrations
    """
    builder = ConfigurationBasedContainerBuilder()
    return builder.build_default_container()

# Example configuration schema for validation
CONFIGURATION_SCHEMA = {
    "type": "object",
    "properties": {
        "environment": {"type": "string"},
        "debug": {"type": "boolean"},
        "services": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service_type": {"type": "string"},
                    "implementation_type": {"type": "string"},
                    "lifetime": {"type": "string", "enum": ["singleton", "transient", "scoped"]},
                    "factory": {"type": "string"},
                    "configuration": {"type": "object"},
                    "dependencies": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["service_type"]
            }
        },
        "factories": {"type": "object"}
    },
    "required": ["services"]
}