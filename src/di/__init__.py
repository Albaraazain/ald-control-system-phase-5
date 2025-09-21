# Dependency Injection Framework
"""
Comprehensive dependency injection framework with zero-downtime deployment capabilities.

This package provides:
- High-performance async-compatible IoC container
- Legacy system migration utilities with backward compatibility
- Blue-green deployment with automated rollback
- Database migration tools with zero-downtime strategies
- Service health monitoring and lifecycle management
- Feature flags for gradual rollout
"""

# Core DI components
from .container import ServiceContainer, ServiceLifetime, ServiceDescriptor
from .service_locator import ServiceLocator
from .factories import ServiceFactory

# Migration and compatibility
from .migration import (
    MigrationHelper, FeatureFlag, MigrationPhase,
    get_migration_helper, initialize_migration, is_migration_initialized,
    get_plc_manager, get_data_collection_service, get_database_service
)

# Zero-downtime deployment
from .deployment import (
    DeploymentState, ServiceHealth, HealthCheckResult, DeploymentConfiguration,
    HealthCheckRegistry, BlueGreenDeploymentManager, ServiceLifecycleManager,
    get_health_registry, get_deployment_manager, get_lifecycle_manager,
    register_default_health_checks
)

# Service integration
from .integration_adapter import (
    ServiceIntegrationAdapter, get_integration_adapter,
    initialize_service_integration, migrate_to_di_architecture,
    perform_zero_downtime_deployment
)

# Database migration
from .database_migration import (
    MigrationState as DBMigrationState, ValidationResult, MigrationStep, MigrationPlan,
    MigrationResult, DatabaseMigrationManager, get_migration_manager,
    execute_system_migrations, create_component_parameter_id_migration,
    create_step_execution_history_migration
)

# Configuration
from .configuration import DIConfiguration, ConfigurationBasedContainerBuilder, create_default_container

__all__ = [
    # Core DI
    'ServiceContainer', 'ServiceLifetime', 'ServiceDescriptor',
    'ServiceLocator', 'ServiceFactory',

    # Migration and compatibility
    'MigrationHelper', 'FeatureFlag', 'MigrationPhase',
    'get_migration_helper', 'initialize_migration', 'is_migration_initialized',
    'get_plc_manager', 'get_data_collection_service', 'get_database_service',

    # Deployment
    'DeploymentState', 'ServiceHealth', 'HealthCheckResult', 'DeploymentConfiguration',
    'HealthCheckRegistry', 'BlueGreenDeploymentManager', 'ServiceLifecycleManager',
    'get_health_registry', 'get_deployment_manager', 'get_lifecycle_manager',
    'register_default_health_checks',

    # Integration
    'ServiceIntegrationAdapter', 'get_integration_adapter',
    'initialize_service_integration', 'migrate_to_di_architecture',
    'perform_zero_downtime_deployment',

    # Database migration
    'DBMigrationState', 'ValidationResult', 'MigrationStep', 'MigrationPlan',
    'MigrationResult', 'DatabaseMigrationManager', 'get_migration_manager',
    'execute_system_migrations', 'create_component_parameter_id_migration',
    'create_step_execution_history_migration',

    # Configuration
    'DIConfiguration', 'ConfigurationBasedContainerBuilder', 'create_default_container'
]