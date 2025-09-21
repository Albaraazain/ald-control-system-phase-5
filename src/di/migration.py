# File: src/di/migration.py
"""
Migration helpers for transitioning from singleton pattern to dependency injection.
Provides backward compatibility and gradual migration support.
"""
from typing import Any, Dict, Type, Optional, Callable, TypeVar
from .container import ServiceContainer
from .service_locator import ServiceLocator
from ..abstractions.interfaces import IPLCInterface, IDatabaseService, IParameterLogger

from src.log_setup import logger

T = TypeVar('T')

class MigrationHelper:
    """Helper for migrating from singleton pattern to DI"""

    def __init__(self, container: ServiceContainer):
        self.container = container
        self._legacy_instances: Dict[str, Any] = {}
        self._migration_status: Dict[str, bool] = {}
        self._adapter_instances: Dict[Type, Any] = {}

    def register_legacy_singleton(self, name: str, instance: Any, service_type: Optional[Type] = None):
        """
        Register a legacy singleton instance for gradual migration.

        Args:
            name: Legacy name of the singleton
            instance: The singleton instance
            service_type: Optional service type for DI registration
        """
        self._legacy_instances[name] = instance
        self._migration_status[name] = False

        # Also register in DI container if service type provided
        if service_type:
            self.container.register_instance(service_type, instance)
            logger.info(f"Registered legacy singleton '{name}' in DI container as {service_type.__name__}")
        else:
            logger.info(f"Registered legacy singleton '{name}' for migration tracking")

    def get_legacy_instance(self, name: str) -> Any:
        """
        Get a legacy singleton instance.

        Args:
            name: Legacy name of the singleton

        Returns:
            The singleton instance or None if not found
        """
        return self._legacy_instances.get(name)

    async def migrate_to_di(self, legacy_name: str, service_type: Type) -> bool:
        """
        Migrate a legacy singleton to DI-managed service.

        Args:
            legacy_name: Name of the legacy singleton
            service_type: Service type to register in DI container

        Returns:
            True if migration successful, False otherwise
        """
        if legacy_name not in self._legacy_instances:
            logger.warning(f"Legacy singleton '{legacy_name}' not found for migration")
            return False

        try:
            instance = self._legacy_instances[legacy_name]

            # Register with DI container
            self.container.register_instance(service_type, instance)

            # Mark as migrated
            self._migration_status[legacy_name] = True

            logger.info(f"Successfully migrated '{legacy_name}' to DI container as {service_type.__name__}")
            return True

        except Exception as e:
            logger.error(f"Failed to migrate '{legacy_name}': {str(e)}")
            return False

    def create_adapter(self, service_type: Type[T], legacy_name: str) -> T:
        """
        Create an adapter that bridges legacy singleton access and DI.

        Args:
            service_type: The service interface type
            legacy_name: Name of the legacy singleton

        Returns:
            Adapter instance
        """
        if service_type in self._adapter_instances:
            return self._adapter_instances[service_type]

        # Create dynamic adapter class
        class LegacyAdapter:
            def __init__(self, migration_helper: MigrationHelper):
                self._migration_helper = migration_helper
                self._legacy_name = legacy_name
                self._service_type = service_type

            def __getattr__(self, name):
                # Try to get from DI container first
                try:
                    if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(self._service_type):
                        service = ServiceLocator.try_get(self._service_type)
                        if service and hasattr(service, name):
                            return getattr(service, name)
                except Exception:
                    pass

                # Fallback to legacy singleton
                legacy_instance = self._migration_helper.get_legacy_instance(self._legacy_name)
                if legacy_instance and hasattr(legacy_instance, name):
                    return getattr(legacy_instance, name)

                raise AttributeError(f"'{self._service_type.__name__}' has no attribute '{name}'")

        adapter = LegacyAdapter(self)
        self._adapter_instances[service_type] = adapter

        logger.debug(f"Created adapter for {service_type.__name__} -> {legacy_name}")
        return adapter

    def get_migration_status(self) -> Dict[str, bool]:
        """Get migration status for all registered singletons"""
        return self._migration_status.copy()

    def is_migrated(self, legacy_name: str) -> bool:
        """Check if a legacy singleton has been migrated"""
        return self._migration_status.get(legacy_name, False)

    def cleanup_migrated(self, legacy_name: str) -> bool:
        """
        Clean up a migrated singleton from legacy registry.

        Args:
            legacy_name: Name of the legacy singleton

        Returns:
            True if cleaned up, False if not migrated or not found
        """
        if not self.is_migrated(legacy_name):
            logger.warning(f"Cannot cleanup '{legacy_name}' - not yet migrated")
            return False

        if legacy_name in self._legacy_instances:
            del self._legacy_instances[legacy_name]
            logger.info(f"Cleaned up migrated singleton '{legacy_name}'")
            return True

        return False

# Global migration helper instance
_migration_helper: Optional[MigrationHelper] = None

def get_migration_helper() -> MigrationHelper:
    """Get the global migration helper instance"""
    global _migration_helper
    if _migration_helper is None:
        raise RuntimeError("Migration helper not initialized. Call initialize_migration() first.")
    return _migration_helper

def initialize_migration(container: ServiceContainer) -> MigrationHelper:
    """
    Initialize the global migration helper.

    Args:
        container: DI container to use for migration

    Returns:
        Migration helper instance
    """
    global _migration_helper
    _migration_helper = MigrationHelper(container)
    logger.info("Migration helper initialized")
    return _migration_helper

def is_migration_initialized() -> bool:
    """Check if migration helper is initialized"""
    return _migration_helper is not None

# Legacy compatibility functions
def get_plc_manager():
    """
    Legacy function to get PLC manager - redirects to DI.

    This provides backward compatibility during migration.
    """
    try:
        # Try DI container first
        if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(IPLCInterface):
            return ServiceLocator.try_get(IPLCInterface)
    except Exception:
        pass

    # Fallback to legacy singleton during migration
    if is_migration_initialized():
        helper = get_migration_helper()
        return helper.get_legacy_instance('plc_manager')

    # Last resort - import legacy singleton
    try:
        from src.plc.manager import plc_manager
        return plc_manager
    except ImportError:
        logger.error("Cannot access PLC manager - migration not initialized and legacy import failed")
        return None

def get_data_collection_service():
    """
    Legacy function to get data collection service - redirects to DI.

    This provides backward compatibility during migration.
    """
    try:
        # Try DI container first
        if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(IParameterLogger):
            return ServiceLocator.try_get(IParameterLogger)
    except Exception:
        pass

    # Fallback to legacy singleton during migration
    if is_migration_initialized():
        helper = get_migration_helper()
        return helper.get_legacy_instance('data_collection_service')

    # Last resort - import legacy singleton
    try:
        from src.data_collection.service import data_collection_service
        return data_collection_service
    except ImportError:
        logger.error("Cannot access data collection service - migration not initialized and legacy import failed")
        return None

def get_database_service():
    """
    Legacy function to get database service - redirects to DI.

    This provides backward compatibility during migration.
    """
    try:
        # Try DI container first
        if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(IDatabaseService):
            return ServiceLocator.try_get(IDatabaseService)
    except Exception:
        pass

    # Fallback to legacy singleton during migration
    if is_migration_initialized():
        helper = get_migration_helper()
        return helper.get_legacy_instance('database_service')

    # Last resort - import legacy functions
    try:
        from src.db import get_supabase
        return get_supabase()
    except ImportError:
        logger.error("Cannot access database service - migration not initialized and legacy import failed")
        return None

class FeatureFlag:
    """Simple feature flag implementation for gradual migration"""

    _flags: Dict[str, bool] = {
        'ENABLE_DI_CONTAINER': False,
        'ENABLE_NEW_DATABASE_POOL': False,
        'ENABLE_HIGH_PERFORMANCE_LOGGING': False,
        'ENABLE_CLEAN_ARCHITECTURE': False,
        'ENABLE_ADAPTER_PATTERN': True,  # Enable adapters by default
    }

    @classmethod
    def is_enabled(cls, flag_name: str) -> bool:
        """Check if a feature flag is enabled"""
        import os
        # Check environment variable first
        env_value = os.getenv(flag_name)
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')

        # Fall back to default value
        return cls._flags.get(flag_name, False)

    @classmethod
    def enable(cls, flag_name: str):
        """Enable a feature flag"""
        cls._flags[flag_name] = True
        logger.info(f"Feature flag '{flag_name}' enabled")

    @classmethod
    def disable(cls, flag_name: str):
        """Disable a feature flag"""
        cls._flags[flag_name] = False
        logger.info(f"Feature flag '{flag_name}' disabled")

    @classmethod
    def get_all_flags(cls) -> Dict[str, bool]:
        """Get all feature flags and their status"""
        import os
        flags = {}
        for flag_name, default_value in cls._flags.items():
            env_value = os.getenv(flag_name)
            if env_value is not None:
                flags[flag_name] = env_value.lower() in ('true', '1', 'yes', 'on')
            else:
                flags[flag_name] = default_value
        return flags

# Migration phase helper
class MigrationPhase:
    """Helper for managing migration phases"""

    PHASE_1_SECURITY = "phase_1_security"
    PHASE_2_FOUNDATION = "phase_2_foundation"
    PHASE_3_MIGRATION = "phase_3_migration"
    PHASE_4_CLEANUP = "phase_4_cleanup"

    _current_phase = PHASE_1_SECURITY

    @classmethod
    def get_current_phase(cls) -> str:
        """Get the current migration phase"""
        import os
        return os.getenv('MIGRATION_PHASE', cls._current_phase)

    @classmethod
    def set_phase(cls, phase: str):
        """Set the current migration phase"""
        cls._current_phase = phase
        logger.info(f"Migration phase set to: {phase}")

    @classmethod
    def is_phase_active(cls, phase: str) -> bool:
        """Check if a specific phase is active"""
        current = cls.get_current_phase()
        phase_order = [
            cls.PHASE_1_SECURITY,
            cls.PHASE_2_FOUNDATION,
            cls.PHASE_3_MIGRATION,
            cls.PHASE_4_CLEANUP
        ]

        try:
            current_index = phase_order.index(current)
            phase_index = phase_order.index(phase)
            return phase_index <= current_index
        except ValueError:
            return False

    @classmethod
    def require_phase(cls, required_phase: str, feature_name: str):
        """Require a specific migration phase for a feature"""
        if not cls.is_phase_active(required_phase):
            raise RuntimeError(
                f"Feature '{feature_name}' requires migration phase '{required_phase}' "
                f"but current phase is '{cls.get_current_phase()}'"
            )