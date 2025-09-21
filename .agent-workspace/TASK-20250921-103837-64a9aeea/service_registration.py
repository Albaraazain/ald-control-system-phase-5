# File: src/infrastructure/di/service_registration.py
"""
Service registration framework for ALD Control System v2.0
Provides centralized service configuration and registration for the DI container.
"""

from typing import Dict, Any, Type, Callable
from .interfaces.core_interfaces import *
from .container import DIContainer, Lifetime

class ServiceRegistry:
    """Centralized service registration for dependency injection"""

    def __init__(self, container: DIContainer):
        self._container = container
        self._registered_services: Dict[str, bool] = {}

    def register_all_services(self, config: Dict[str, Any]) -> None:
        """Register all application services with the DI container"""

        # Register infrastructure services first
        self._register_infrastructure_services(config)

        # Register domain services
        self._register_domain_services()

        # Register application services
        self._register_application_services()

        # Register external interfaces
        self._register_external_interfaces(config)

    def _register_infrastructure_services(self, config: Dict[str, Any]) -> None:
        """Register infrastructure layer services"""

        # Configuration Service (Singleton)
        self._container.register_singleton(
            IConfigurationService,
            self._get_configuration_implementation(config)
        )

        # Credential Manager (Singleton)
        self._container.register_singleton(
            ICredentialManager,
            self._get_credential_manager_implementation(config)
        )

        # Database Connection Pool (Singleton)
        self._container.register_singleton(
            IConnectionPool,
            self._get_connection_pool_implementation(config)
        )

        # Transaction Manager (Singleton)
        self._container.register_singleton(
            ITransactionManager,
            self._get_transaction_manager_implementation()
        )

        # Cache Service (Singleton)
        self._container.register_singleton(
            ICacheService,
            self._get_cache_service_implementation(config)
        )

        # Event Bus (Singleton)
        self._container.register_singleton(
            IEventBus,
            self._get_event_bus_implementation()
        )

        # Circuit Breaker Factory (Singleton)
        self._container.register_factory(
            ICircuitBreaker,
            self._create_circuit_breaker
        )

        # Health Check Services
        self._register_health_checks()

        # Metrics Collector (Singleton)
        self._container.register_singleton(
            IMetricsCollector,
            self._get_metrics_collector_implementation(config)
        )

    def _register_domain_services(self) -> None:
        """Register domain layer services"""

        # State Manager (Singleton)
        self._container.register_singleton(
            IStateManager,
            self._get_state_manager_implementation()
        )

        # Input Validator (Singleton)
        self._container.register_singleton(
            IInputValidator,
            self._get_input_validator_implementation()
        )

    def _register_application_services(self) -> None:
        """Register application layer services"""

        # Parameter Logger (Singleton)
        self._container.register_singleton(
            IParameterLogger,
            self._get_parameter_logger_implementation()
        )

        # Data Collection Service (Singleton)
        self._container.register_singleton(
            IDataCollectionService,
            self._get_data_collection_service_implementation()
        )

    def _register_external_interfaces(self, config: Dict[str, Any]) -> None:
        """Register external interface services"""

        # PLC Factory (Singleton)
        self._container.register_singleton(
            IPLCFactory,
            self._get_plc_factory_implementation()
        )

        # PLC Interface (Singleton - managed by factory)
        self._container.register_factory(
            IPLCInterface,
            lambda: self._create_plc_interface(config)
        )

    def _register_repositories(self) -> None:
        """Register repository services (called by transaction manager)"""

        # Parameter Repository (Scoped to transaction)
        self._container.register_transient(
            IParameterRepository,
            self._get_parameter_repository_implementation()
        )

        # Process Repository (Scoped to transaction)
        self._container.register_transient(
            IProcessRepository,
            self._get_process_repository_implementation()
        )

        # Machine Repository (Scoped to transaction)
        self._container.register_transient(
            IMachineRepository,
            self._get_machine_repository_implementation()
        )

    def _register_health_checks(self) -> None:
        """Register health check services"""

        health_checks = [
            ('database', self._get_database_health_check()),
            ('plc', self._get_plc_health_check()),
            ('cache', self._get_cache_health_check()),
            ('eventbus', self._get_eventbus_health_check())
        ]

        for name, health_check_class in health_checks:
            self._container.register_transient(
                IHealthCheck,
                health_check_class
            )

    # Implementation getters (to be replaced with actual implementations)

    def _get_configuration_implementation(self, config: Dict[str, Any]) -> Type:
        """Get configuration service implementation"""
        # Import actual implementation
        from ..configuration.environment_config_provider import EnvironmentConfigProvider
        return EnvironmentConfigProvider

    def _get_credential_manager_implementation(self, config: Dict[str, Any]) -> Type:
        """Get credential manager implementation"""
        from ..security.secure_credential_manager import SecureCredentialManager
        return SecureCredentialManager

    def _get_connection_pool_implementation(self, config: Dict[str, Any]) -> Type:
        """Get database connection pool implementation"""
        from ..database.async_connection_pool import AsyncConnectionPool
        return AsyncConnectionPool

    def _get_transaction_manager_implementation(self) -> Type:
        """Get transaction manager implementation"""
        from ..database.async_transaction_manager import AsyncTransactionManager
        return AsyncTransactionManager

    def _get_cache_service_implementation(self, config: Dict[str, Any]) -> Type:
        """Get cache service implementation"""
        from ..cache.redis_cache_service import RedisCacheService
        return RedisCacheService

    def _get_event_bus_implementation(self) -> Type:
        """Get event bus implementation"""
        from ..events.async_event_bus import AsyncEventBus
        return AsyncEventBus

    def _get_state_manager_implementation(self) -> Type:
        """Get state manager implementation"""
        from ..state.atomic_state_manager import AtomicStateManager
        return AtomicStateManager

    def _get_input_validator_implementation(self) -> Type:
        """Get input validator implementation"""
        from ..security.comprehensive_input_validator import ComprehensiveInputValidator
        return ComprehensiveInputValidator

    def _get_parameter_logger_implementation(self) -> Type:
        """Get parameter logger implementation"""
        from ..data_collection.high_performance_parameter_logger import HighPerformanceParameterLogger
        return HighPerformanceParameterLogger

    def _get_data_collection_service_implementation(self) -> Type:
        """Get data collection service implementation"""
        from ..data_collection.orchestrated_data_collection_service import OrchestratedDataCollectionService
        return OrchestratedDataCollectionService

    def _get_plc_factory_implementation(self) -> Type:
        """Get PLC factory implementation"""
        from ..plc.enhanced_plc_factory import EnhancedPLCFactory
        return EnhancedPLCFactory

    def _get_parameter_repository_implementation(self) -> Type:
        """Get parameter repository implementation"""
        from ..repositories.postgres_parameter_repository import PostgresParameterRepository
        return PostgresParameterRepository

    def _get_process_repository_implementation(self) -> Type:
        """Get process repository implementation"""
        from ..repositories.postgres_process_repository import PostgresProcessRepository
        return PostgresProcessRepository

    def _get_machine_repository_implementation(self) -> Type:
        """Get machine repository implementation"""
        from ..repositories.postgres_machine_repository import PostgresMachineRepository
        return PostgresMachineRepository

    def _get_metrics_collector_implementation(self, config: Dict[str, Any]) -> Type:
        """Get metrics collector implementation"""
        from ..monitoring.prometheus_metrics_collector import PrometheusMetricsCollector
        return PrometheusMetricsCollector

    def _get_database_health_check(self) -> Type:
        """Get database health check implementation"""
        from ..monitoring.database_health_check import DatabaseHealthCheck
        return DatabaseHealthCheck

    def _get_plc_health_check(self) -> Type:
        """Get PLC health check implementation"""
        from ..monitoring.plc_health_check import PLCHealthCheck
        return PLCHealthCheck

    def _get_cache_health_check(self) -> Type:
        """Get cache health check implementation"""
        from ..monitoring.cache_health_check import CacheHealthCheck
        return CacheHealthCheck

    def _get_eventbus_health_check(self) -> Type:
        """Get event bus health check implementation"""
        from ..monitoring.eventbus_health_check import EventBusHealthCheck
        return EventBusHealthCheck

    # Factory methods

    async def _create_plc_interface(self, config: Dict[str, Any]) -> IPLCInterface:
        """Create PLC interface using factory"""
        factory = await self._container.resolve(IPLCFactory)
        plc_config = config.get('plc', {})
        plc_type = plc_config.get('type', 'simulation')
        return await factory.create_plc(plc_type, plc_config)

    def _create_circuit_breaker(self) -> ICircuitBreaker:
        """Create circuit breaker instance"""
        from ..resilience.async_circuit_breaker import AsyncCircuitBreaker
        return AsyncCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception
        )

class BackwardCompatibilityRegistry:
    """Registry for backward compatibility adapters during migration"""

    def __init__(self, container: DIContainer):
        self._container = container
        self._adapters_enabled = True

    def register_compatibility_adapters(self) -> None:
        """Register adapter patterns for backward compatibility"""

        if not self._adapters_enabled:
            return

        # Register PLC Manager Adapter
        self._container.register_singleton(
            'PLCManagerAdapter',
            self._get_plc_manager_adapter()
        )

        # Register Data Collection Service Adapter
        self._container.register_singleton(
            'DataCollectionServiceAdapter',
            self._get_data_collection_adapter()
        )

        # Register Configuration Adapter
        self._container.register_singleton(
            'ConfigurationAdapter',
            self._get_configuration_adapter()
        )

    def disable_adapters(self) -> None:
        """Disable adapters for final migration phase"""
        self._adapters_enabled = False

    def _get_plc_manager_adapter(self) -> Type:
        """Get PLC manager adapter implementation"""
        from ..compatibility.adapters.plc_manager_adapter import PLCManagerAdapter
        return PLCManagerAdapter

    def _get_data_collection_adapter(self) -> Type:
        """Get data collection service adapter implementation"""
        from ..compatibility.adapters.data_collection_adapter import DataCollectionServiceAdapter
        return DataCollectionServiceAdapter

    def _get_configuration_adapter(self) -> Type:
        """Get configuration adapter implementation"""
        from ..compatibility.adapters.configuration_adapter import ConfigurationAdapter
        return ConfigurationAdapter

class FeatureFlagRegistry:
    """Registry for feature flag-based service activation"""

    def __init__(self, container: DIContainer, config_service: IConfigurationService):
        self._container = container
        self._config = config_service

    def register_feature_flagged_services(self) -> None:
        """Register services based on feature flags"""

        if self._config.get_bool('ENABLE_DI_CONTAINER', False):
            self._register_di_services()

        if self._config.get_bool('ENABLE_NEW_DATABASE_POOL', False):
            self._register_new_database_services()

        if self._config.get_bool('ENABLE_HIGH_PERFORMANCE_LOGGING', False):
            self._register_high_performance_logging()

        if self._config.get_bool('ENABLE_CLEAN_ARCHITECTURE', False):
            self._register_clean_architecture_services()

    def _register_di_services(self) -> None:
        """Register dependency injection services"""
        # Enable DI container functionality
        pass

    def _register_new_database_services(self) -> None:
        """Register new database services"""
        # Switch to connection pooling
        pass

    def _register_high_performance_logging(self) -> None:
        """Register high-performance logging services"""
        # Switch to async pipeline
        pass

    def _register_clean_architecture_services(self) -> None:
        """Register clean architecture services"""
        # Enable full clean architecture
        pass

class ServiceBootstrapper:
    """Main service bootstrapper for application startup"""

    def __init__(self):
        self._container = DIContainer()
        self._registry = ServiceRegistry(self._container)
        self._compatibility_registry = BackwardCompatibilityRegistry(self._container)

    async def bootstrap_services(self, config: Dict[str, Any]) -> DIContainer:
        """Bootstrap all application services"""

        # Register core services
        self._registry.register_all_services(config)

        # Register compatibility adapters for migration
        self._compatibility_registry.register_compatibility_adapters()

        # Configure feature flags
        config_service = await self._container.resolve(IConfigurationService)
        feature_flag_registry = FeatureFlagRegistry(self._container, config_service)
        feature_flag_registry.register_feature_flagged_services()

        return self._container

    def get_container(self) -> DIContainer:
        """Get the configured DI container"""
        return self._container