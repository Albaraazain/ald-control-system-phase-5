# File: src/di/integration_adapter.py
"""
Integration adapter for seamless service integration with existing ALD control system.
Provides backward compatibility while enabling gradual migration to new architecture.
"""
import asyncio
import time
from typing import Dict, Any, Optional, Callable, List, Union, Type
from contextlib import asynccontextmanager
import weakref

from .container import ServiceContainer, ServiceLifetime
from .service_locator import ServiceLocator
from .migration import FeatureFlag, MigrationPhase, get_migration_helper, initialize_migration
from .deployment import (
    get_health_registry, get_deployment_manager, get_lifecycle_manager,
    register_default_health_checks, DeploymentConfiguration
)
from ..abstractions.interfaces import IPLCInterface, IDatabaseService, IParameterLogger
from src.log_setup import logger

class ServiceIntegrationAdapter:
    """
    Adapter for integrating new DI-based services with existing legacy system.
    Provides seamless migration and backward compatibility.
    """

    def __init__(self):
        self._container: Optional[ServiceContainer] = None
        self._legacy_services: Dict[str, Any] = {}
        self._integration_hooks: Dict[str, List[Callable]] = {}
        self._migration_status: Dict[str, bool] = {}
        self._is_initialized = False

    async def initialize(
        self,
        container: Optional[ServiceContainer] = None,
        enable_legacy_compatibility: bool = True
    ) -> ServiceContainer:
        """
        Initialize the integration adapter with a service container.

        Args:
            container: Optional pre-configured container
            enable_legacy_compatibility: Whether to enable legacy service compatibility

        Returns:
            Configured service container
        """
        if self._is_initialized:
            logger.warning("Integration adapter already initialized")
            return self._container

        # Create or use provided container
        if container is None:
            self._container = ServiceContainer()
            logger.info("Created new service container for integration")
        else:
            self._container = container
            logger.info("Using provided service container for integration")

        # Initialize migration helper
        migration_helper = initialize_migration(self._container)

        # Register legacy services if compatibility enabled
        if enable_legacy_compatibility:
            await self._register_legacy_services(migration_helper)

        # Configure service locator
        ServiceLocator.configure(self._container)

        # Register default health checks
        register_default_health_checks()

        # Initialize deployment manager
        deployment_manager = get_deployment_manager()
        deployment_manager.initialize_environments(self._container)

        self._is_initialized = True
        logger.info("Service integration adapter initialized successfully")

        return self._container

    async def _register_legacy_services(self, migration_helper):
        """Register existing legacy services for backward compatibility"""
        try:
            # Register PLC manager
            await self._register_plc_manager(migration_helper)

            # Register data collection service
            await self._register_data_collection_service(migration_helper)

            # Register database service
            await self._register_database_service(migration_helper)

            logger.info("Legacy services registered successfully")

        except Exception as e:
            logger.error(f"Failed to register legacy services: {str(e)}")

    async def _register_plc_manager(self, migration_helper):
        """Register legacy PLC manager"""
        try:
            # Import legacy PLC manager
            from src.plc.manager import plc_manager

            if plc_manager:
                # Register with migration helper
                migration_helper.register_legacy_singleton(
                    'plc_manager',
                    plc_manager,
                    IPLCInterface
                )

                # Create adapter for backward compatibility
                adapter = migration_helper.create_adapter(IPLCInterface, 'plc_manager')

                # Register health check hook
                self._integration_hooks.setdefault('plc_health_check', []).append(
                    lambda: self._check_plc_health(plc_manager)
                )

                logger.info("PLC manager registered with integration adapter")

        except ImportError as e:
            logger.warning(f"Could not import legacy PLC manager: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to register PLC manager: {str(e)}")

    async def _register_data_collection_service(self, migration_helper):
        """Register legacy data collection service"""
        try:
            # Import legacy data collection service
            from src.data_collection.service import data_collection_service

            if data_collection_service:
                # Register with migration helper
                migration_helper.register_legacy_singleton(
                    'data_collection_service',
                    data_collection_service,
                    IParameterLogger
                )

                # Create adapter for backward compatibility
                adapter = migration_helper.create_adapter(IParameterLogger, 'data_collection_service')

                # Register health check hook
                self._integration_hooks.setdefault('data_collection_health_check', []).append(
                    lambda: self._check_data_collection_health(data_collection_service)
                )

                logger.info("Data collection service registered with integration adapter")

        except ImportError as e:
            logger.warning(f"Could not import legacy data collection service: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to register data collection service: {str(e)}")

    async def _register_database_service(self, migration_helper):
        """Register legacy database service"""
        try:
            # Import legacy database functions
            from src.db import get_supabase

            db_instance = get_supabase()
            if db_instance:
                # Register with migration helper
                migration_helper.register_legacy_singleton(
                    'database_service',
                    db_instance,
                    IDatabaseService
                )

                # Create adapter for backward compatibility
                adapter = migration_helper.create_adapter(IDatabaseService, 'database_service')

                # Register health check hook
                self._integration_hooks.setdefault('database_health_check', []).append(
                    lambda: self._check_database_health(db_instance)
                )

                logger.info("Database service registered with integration adapter")

        except ImportError as e:
            logger.warning(f"Could not import legacy database service: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to register database service: {str(e)}")

    async def _check_plc_health(self, plc_manager) -> Dict[str, Any]:
        """Check PLC manager health"""
        try:
            if hasattr(plc_manager, 'connected'):
                connected = plc_manager.connected
                if callable(connected):
                    connected = connected()

                return {
                    'status': 'healthy' if connected else 'unhealthy',
                    'message': 'PLC connected' if connected else 'PLC disconnected',
                    'connected': connected
                }
            else:
                return {
                    'status': 'unknown',
                    'message': 'PLC connection status unknown'
                }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'PLC health check failed: {str(e)}'
            }

    async def _check_data_collection_health(self, data_collection_service) -> Dict[str, Any]:
        """Check data collection service health"""
        try:
            if hasattr(data_collection_service, 'get_status'):
                status = data_collection_service.get_status()
                running = status.get('service_running', False)

                return {
                    'status': 'healthy' if running else 'unhealthy',
                    'message': 'Data collection running' if running else 'Data collection stopped',
                    'running': running,
                    'details': status
                }
            else:
                return {
                    'status': 'unknown',
                    'message': 'Data collection status unknown'
                }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Data collection health check failed: {str(e)}'
            }

    async def _check_database_health(self, db_instance) -> Dict[str, Any]:
        """Check database service health"""
        try:
            # Simple connectivity test
            # For Supabase, we could try a simple query
            if hasattr(db_instance, 'table'):
                # Try to access a table (this doesn't execute a query)
                table = db_instance.table('machines')
                if table:
                    return {
                        'status': 'healthy',
                        'message': 'Database connection available'
                    }

            return {
                'status': 'unknown',
                'message': 'Database status unknown'
            }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Database health check failed: {str(e)}'
            }

    async def register_new_service(
        self,
        service_type: Type,
        implementation_type: Optional[Type] = None,
        factory: Optional[Callable] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
        replace_legacy: bool = False
    ) -> bool:
        """
        Register a new service with the container.

        Args:
            service_type: Service interface type
            implementation_type: Concrete implementation type
            factory: Optional factory function
            lifetime: Service lifetime
            replace_legacy: Whether to replace legacy service

        Returns:
            True if registration successful
        """
        if not self._is_initialized:
            logger.error("Integration adapter not initialized")
            return False

        try:
            # Register with container
            self._container.register(
                service_type,
                implementation_type,
                factory,
                lifetime
            )

            # If replacing legacy service, update migration status
            if replace_legacy:
                service_name = service_type.__name__
                self._migration_status[service_name] = True

                # Remove from legacy services if present
                legacy_name = self._find_legacy_service_name(service_type)
                if legacy_name and legacy_name in self._legacy_services:
                    del self._legacy_services[legacy_name]

                logger.info(f"Replaced legacy service: {service_name}")

            logger.info(f"Registered new service: {service_type.__name__}")
            return True

        except Exception as e:
            logger.error(f"Failed to register service {service_type.__name__}: {str(e)}")
            return False

    def _find_legacy_service_name(self, service_type: Type) -> Optional[str]:
        """Find legacy service name for a given service type"""
        type_mapping = {
            IPLCInterface: 'plc_manager',
            IParameterLogger: 'data_collection_service',
            IDatabaseService: 'database_service'
        }
        return type_mapping.get(service_type)

    async def perform_gradual_migration(
        self,
        migration_plan: Dict[str, Any],
        rollback_on_failure: bool = True
    ) -> bool:
        """
        Perform gradual migration from legacy to new services.

        Args:
            migration_plan: Dictionary describing migration steps
            rollback_on_failure: Whether to rollback on failure

        Returns:
            True if migration successful
        """
        if not self._is_initialized:
            logger.error("Integration adapter not initialized")
            return False

        logger.info("Starting gradual migration...")

        backup_state = self._migration_status.copy()

        try:
            # Enable feature flags for migration
            for flag_name in migration_plan.get('feature_flags', []):
                FeatureFlag.enable(flag_name)

            # Migrate services one by one
            for service_config in migration_plan.get('services', []):
                service_name = service_config['name']
                service_type = service_config['type']

                logger.info(f"Migrating service: {service_name}")

                if not await self._migrate_single_service(service_config):
                    if rollback_on_failure:
                        logger.error(f"Migration failed for {service_name}, rolling back...")
                        await self._rollback_migration(backup_state)
                        return False
                    else:
                        logger.warning(f"Migration failed for {service_name}, continuing...")

            # Update migration phase
            if 'migration_phase' in migration_plan:
                MigrationPhase.set_phase(migration_plan['migration_phase'])

            logger.info("Gradual migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            if rollback_on_failure:
                await self._rollback_migration(backup_state)
            return False

    async def _migrate_single_service(self, service_config: Dict[str, Any]) -> bool:
        """Migrate a single service from legacy to new implementation"""
        try:
            service_name = service_config['name']
            service_type = service_config.get('type')
            implementation = service_config.get('implementation')

            # Register new implementation
            if implementation:
                self._container.register_singleton(service_type, implementation)
                logger.info(f"Registered new implementation for {service_name}")

            # Mark as migrated
            self._migration_status[service_name] = True

            # Perform health check to ensure migration successful
            if service_type in [IPLCInterface, IParameterLogger, IDatabaseService]:
                health_registry = get_health_registry()
                health_result = await health_registry.check_service_health(service_name.lower())
                if health_result.status.value != 'healthy':
                    logger.warning(f"Health check failed for migrated service {service_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to migrate service {service_config['name']}: {str(e)}")
            return False

    async def _rollback_migration(self, backup_state: Dict[str, bool]):
        """Rollback migration to previous state"""
        logger.info("Rolling back migration...")

        try:
            # Restore migration status
            self._migration_status = backup_state

            # Disable feature flags that were enabled
            for flag_name in FeatureFlag.get_all_flags():
                if flag_name.startswith('ENABLE_'):
                    FeatureFlag.disable(flag_name)

            logger.info("Migration rollback completed")

        except Exception as e:
            logger.error(f"Migration rollback failed: {str(e)}")

    async def perform_blue_green_deployment(
        self,
        deployment_config: Dict[str, Any],
        deployment_function: Callable[[ServiceContainer], None]
    ) -> bool:
        """
        Perform zero-downtime blue-green deployment.

        Args:
            deployment_config: Deployment configuration
            deployment_function: Function to configure new environment

        Returns:
            True if deployment successful
        """
        if not self._is_initialized:
            logger.error("Integration adapter not initialized")
            return False

        try:
            deployment_manager = get_deployment_manager()

            # Create deployment configuration
            config = DeploymentConfiguration(
                rollback_timeout_seconds=deployment_config.get('rollback_timeout', 300),
                health_check_timeout_seconds=deployment_config.get('health_check_timeout', 30),
                health_check_retries=deployment_config.get('health_check_retries', 3),
                enable_automated_rollback=deployment_config.get('enable_rollback', True),
                require_manual_approval=deployment_config.get('require_approval', False)
            )

            # Perform deployment
            success = await deployment_manager.deploy(deployment_function, config)

            if success:
                logger.info("Blue-green deployment completed successfully")
            else:
                logger.error("Blue-green deployment failed")

            return success

        except Exception as e:
            logger.error(f"Blue-green deployment failed: {str(e)}")
            return False

    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            'initialized': self._is_initialized,
            'container_services': len(self._container.get_all_services()) if self._container else 0,
            'legacy_services': len(self._legacy_services),
            'migration_status': self._migration_status.copy(),
            'feature_flags': FeatureFlag.get_all_flags(),
            'current_migration_phase': MigrationPhase.get_current_phase()
        }

    @asynccontextmanager
    async def service_scope(self, scope_name: str = None):
        """
        Create a service scope for scoped services.

        Args:
            scope_name: Optional scope name

        Yields:
            scope_id: Scope identifier
        """
        if not self._is_initialized or not self._container:
            raise RuntimeError("Integration adapter not initialized")

        async with self._container.create_scope(scope_name) as scope_id:
            try:
                logger.debug(f"Created service scope: {scope_id}")
                yield scope_id
            finally:
                logger.debug(f"Disposing service scope: {scope_id}")

    async def dispose(self):
        """Clean up integration adapter resources"""
        if not self._is_initialized:
            return

        try:
            logger.info("Disposing integration adapter...")

            # Stop lifecycle manager
            lifecycle_manager = get_lifecycle_manager(self._container)
            await lifecycle_manager.stop_all_services()

            # Dispose container
            if self._container:
                await self._container.dispose()

            # Clear legacy services
            self._legacy_services.clear()
            self._migration_status.clear()
            self._integration_hooks.clear()

            self._is_initialized = False
            logger.info("Integration adapter disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing integration adapter: {str(e)}")

# Global integration adapter instance
_integration_adapter: Optional[ServiceIntegrationAdapter] = None

def get_integration_adapter() -> ServiceIntegrationAdapter:
    """Get the global integration adapter instance"""
    global _integration_adapter
    if _integration_adapter is None:
        _integration_adapter = ServiceIntegrationAdapter()
    return _integration_adapter

async def initialize_service_integration(
    container: Optional[ServiceContainer] = None,
    enable_legacy_compatibility: bool = True
) -> ServiceContainer:
    """
    Initialize service integration with the existing system.

    Args:
        container: Optional pre-configured container
        enable_legacy_compatibility: Whether to enable legacy compatibility

    Returns:
        Configured service container
    """
    adapter = get_integration_adapter()
    return await adapter.initialize(container, enable_legacy_compatibility)

# Integration helper functions for backward compatibility
async def migrate_to_di_architecture(
    migration_config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Migrate the entire system to dependency injection architecture.

    Args:
        migration_config: Optional migration configuration

    Returns:
        True if migration successful
    """
    adapter = get_integration_adapter()

    if not migration_config:
        # Default migration configuration
        migration_config = {
            'feature_flags': [
                'ENABLE_DI_CONTAINER',
                'ENABLE_CLEAN_ARCHITECTURE',
                'ENABLE_ADAPTER_PATTERN'
            ],
            'services': [
                {
                    'name': 'plc_manager',
                    'type': IPLCInterface,
                    'legacy_name': 'plc_manager'
                },
                {
                    'name': 'data_collection_service',
                    'type': IParameterLogger,
                    'legacy_name': 'data_collection_service'
                },
                {
                    'name': 'database_service',
                    'type': IDatabaseService,
                    'legacy_name': 'database_service'
                }
            ],
            'migration_phase': MigrationPhase.PHASE_3_MIGRATION
        }

    return await adapter.perform_gradual_migration(migration_config)

async def perform_zero_downtime_deployment(
    deployment_function: Callable[[ServiceContainer], None],
    config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Perform zero-downtime deployment of new services.

    Args:
        deployment_function: Function to configure new environment
        config: Optional deployment configuration

    Returns:
        True if deployment successful
    """
    adapter = get_integration_adapter()

    if not config:
        config = {
            'rollback_timeout': 300,
            'health_check_timeout': 30,
            'health_check_retries': 3,
            'enable_rollback': True,
            'require_approval': False
        }

    return await adapter.perform_blue_green_deployment(config, deployment_function)