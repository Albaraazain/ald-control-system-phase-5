# File: src/di/integration_example.py
"""
Example of zero-downtime integration with the ALD control system.
Demonstrates backward compatibility, blue-green deployment, and gradual migration.
"""
import asyncio
from typing import Optional

from .integration_adapter import (
    get_integration_adapter, initialize_service_integration,
    migrate_to_di_architecture, perform_zero_downtime_deployment
)
from .container import ServiceContainer, ServiceLifetime
from .deployment import DeploymentConfiguration, get_health_registry
from .migration import FeatureFlag, MigrationPhase
from .database_migration import get_migration_manager, execute_system_migrations
from ..abstractions.interfaces import IPLCInterface, IDatabaseService, IParameterLogger
from src.log_setup import logger

async def example_zero_downtime_integration():
    """
    Complete example of zero-downtime integration with the ALD control system.
    """
    logger.info("Starting zero-downtime integration example...")

    try:
        # Step 1: Initialize service integration with backward compatibility
        logger.info("Step 1: Initializing service integration...")
        container = await initialize_service_integration(
            container=None,  # Let it create a new container
            enable_legacy_compatibility=True
        )

        # Step 2: Register health checks and verify system status
        logger.info("Step 2: Verifying system health...")
        health_registry = get_health_registry()
        health_status = await health_registry.check_all_services()

        for service_name, health_result in health_status.items():
            logger.info(f"Service {service_name}: {health_result.status.value} - {health_result.message}")

        # Step 3: Perform database migrations if needed
        logger.info("Step 3: Executing database migrations...")
        from src.db import create_async_supabase

        async def db_factory():
            return await create_async_supabase()

        migration_success = await execute_system_migrations(db_factory)
        if not migration_success:
            logger.error("Database migrations failed, aborting integration")
            return False

        # Step 4: Gradual migration to DI architecture
        logger.info("Step 4: Performing gradual migration to DI architecture...")
        migration_success = await migrate_to_di_architecture()
        if not migration_success:
            logger.error("DI architecture migration failed")
            return False

        # Step 5: Blue-green deployment of new services (example)
        logger.info("Step 5: Performing blue-green deployment...")

        def configure_new_environment(new_container: ServiceContainer):
            """Configure the new environment with updated services"""
            # Example: Register improved PLC interface
            # new_container.register_singleton(IPLCInterface, ImprovedPLCInterface)

            # Example: Register high-performance parameter logger
            # new_container.register_singleton(IParameterLogger, HighPerformanceParameterLogger)

            logger.info("New environment configured with updated services")

        deployment_config = {
            'rollback_timeout': 300,
            'health_check_timeout': 30,
            'health_check_retries': 3,
            'enable_rollback': True,
            'require_approval': False
        }

        deployment_success = await perform_zero_downtime_deployment(
            configure_new_environment,
            deployment_config
        )

        if deployment_success:
            logger.info("Zero-downtime integration completed successfully!")
            return True
        else:
            logger.error("Zero-downtime deployment failed")
            return False

    except Exception as e:
        logger.error(f"Integration example failed: {str(e)}")
        return False

async def example_backward_compatibility():
    """
    Example demonstrating backward compatibility with legacy services.
    """
    logger.info("Demonstrating backward compatibility...")

    # Initialize integration with legacy compatibility
    container = await initialize_service_integration(enable_legacy_compatibility=True)

    # Legacy code can still access services using old methods
    from src.di.migration import get_plc_manager, get_data_collection_service

    # These functions automatically redirect to DI container if available,
    # otherwise fall back to legacy singletons
    plc = get_plc_manager()
    data_collection = get_data_collection_service()

    logger.info(f"PLC manager accessible: {plc is not None}")
    logger.info(f"Data collection service accessible: {data_collection is not None}")

    # New code can use DI container directly
    from .service_locator import ServiceLocator

    if ServiceLocator.is_configured():
        # Try to get services from DI container
        plc_from_di = ServiceLocator.try_get(IPLCInterface)
        logger_from_di = ServiceLocator.try_get(IParameterLogger)

        logger.info(f"PLC from DI: {plc_from_di is not None}")
        logger.info(f"Logger from DI: {logger_from_di is not None}")

async def example_feature_flag_rollout():
    """
    Example of gradual feature rollout using feature flags.
    """
    logger.info("Demonstrating feature flag rollout...")

    # Check current feature flags
    flags = FeatureFlag.get_all_flags()
    logger.info(f"Current feature flags: {flags}")

    # Enable features gradually
    FeatureFlag.enable('ENABLE_DI_CONTAINER')
    logger.info("Enabled DI container")

    # Simulate some time passing...
    await asyncio.sleep(1)

    # Enable more features
    FeatureFlag.enable('ENABLE_HIGH_PERFORMANCE_LOGGING')
    logger.info("Enabled high-performance logging")

    # Check if features are enabled
    if FeatureFlag.is_enabled('ENABLE_DI_CONTAINER'):
        logger.info("DI container feature is enabled")

    if FeatureFlag.is_enabled('ENABLE_HIGH_PERFORMANCE_LOGGING'):
        logger.info("High-performance logging feature is enabled")

async def example_health_monitoring():
    """
    Example of comprehensive health monitoring during integration.
    """
    logger.info("Demonstrating health monitoring...")

    # Get health registry
    health_registry = get_health_registry()

    # Custom health check example
    async def custom_system_health_check():
        from src.di.deployment import HealthCheckResult, ServiceHealth
        try:
            # Check multiple system components
            checks = []

            # Memory usage check
            import psutil
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 90:
                return HealthCheckResult(
                    service_name="system_memory",
                    status=ServiceHealth.UNHEALTHY,
                    message=f"High memory usage: {memory_percent}%",
                    response_time_ms=0.0
                )

            # Disk space check
            disk_percent = psutil.disk_usage('/').percent
            if disk_percent > 90:
                return HealthCheckResult(
                    service_name="system_disk",
                    status=ServiceHealth.DEGRADED,
                    message=f"Low disk space: {disk_percent}% used",
                    response_time_ms=0.0
                )

            return HealthCheckResult(
                service_name="system_resources",
                status=ServiceHealth.HEALTHY,
                message=f"Memory: {memory_percent}%, Disk: {disk_percent}%",
                response_time_ms=0.0
            )

        except Exception as e:
            return HealthCheckResult(
                service_name="system_resources",
                status=ServiceHealth.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=0.0
            )

    # Register custom health check
    health_registry.register_health_check("system_resources", custom_system_health_check)

    # Perform health checks
    health_results = await health_registry.check_all_services()

    # Display results
    for service_name, result in health_results.items():
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌',
            'unknown': '❓'
        }.get(result.status.value, '❓')

        logger.info(
            f"{status_emoji} {service_name}: {result.message} "
            f"({result.response_time_ms:.2f}ms)"
        )

async def example_migration_phases():
    """
    Example of migration phase management.
    """
    logger.info("Demonstrating migration phase management...")

    # Check current phase
    current_phase = MigrationPhase.get_current_phase()
    logger.info(f"Current migration phase: {current_phase}")

    # Progress through phases
    phases = [
        MigrationPhase.PHASE_1_SECURITY,
        MigrationPhase.PHASE_2_FOUNDATION,
        MigrationPhase.PHASE_3_MIGRATION,
        MigrationPhase.PHASE_4_CLEANUP
    ]

    for phase in phases:
        MigrationPhase.set_phase(phase)
        logger.info(f"Advanced to phase: {phase}")

        # Check if phase is active
        if MigrationPhase.is_phase_active(phase):
            logger.info(f"Phase {phase} is now active")

        # Simulate work in this phase
        await asyncio.sleep(0.5)

async def run_complete_integration_example():
    """
    Run the complete integration example demonstrating all features.
    """
    logger.info("="*60)
    logger.info("COMPLETE ZERO-DOWNTIME INTEGRATION EXAMPLE")
    logger.info("="*60)

    try:
        # Run all examples
        await example_migration_phases()
        await example_backward_compatibility()
        await example_feature_flag_rollout()
        await example_health_monitoring()
        await example_zero_downtime_integration()

        logger.info("="*60)
        logger.info("INTEGRATION EXAMPLE COMPLETED SUCCESSFULLY")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Integration example failed: {str(e)}")
        logger.info("="*60)
        logger.info("INTEGRATION EXAMPLE FAILED")
        logger.info("="*60)

if __name__ == "__main__":
    # Run the complete example
    asyncio.run(run_complete_integration_example())