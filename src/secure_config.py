"""
Secure Configuration Module

This module provides secure configuration loading using the security framework.
Replaces the legacy config.py with secure credential management.
"""

from typing import Set, Optional, Dict, Any
from src.security import get_secure_credentials, get_database_config, get_plc_config
from src.security.input_validator import InputValidator
from src.log_setup import logger


class SecureConfig:
    """Secure configuration manager using the security framework."""

    def __init__(self):
        """Initialize secure configuration."""
        self._credentials = None
        self._loaded = False

    def load(self) -> None:
        """Load secure credentials and validate configuration."""
        try:
            self._credentials = get_secure_credentials()
            self._loaded = True
            logger.info("Secure configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load secure configuration: {e}")
            raise

    @property
    def supabase_url(self) -> str:
        """Get validated Supabase URL."""
        if not self._loaded:
            self.load()
        return self._credentials.supabase_url

    @property
    def supabase_key(self) -> str:
        """Get validated Supabase key."""
        if not self._loaded:
            self.load()
        return self._credentials.supabase_key

    @property
    def machine_id(self) -> str:
        """Get validated machine ID."""
        if not self._loaded:
            self.load()
        return self._credentials.machine_id

    @property
    def test_operator_id(self) -> Optional[str]:
        """Get validated test operator ID."""
        if not self._loaded:
            self.load()
        return self._credentials.test_operator_id

    @property
    def plc_type(self) -> str:
        """Get validated PLC type."""
        if not self._loaded:
            self.load()
        return self._credentials.plc_type

    @property
    def plc_ip(self) -> str:
        """Get validated PLC IP address."""
        if not self._loaded:
            self.load()
        return self._credentials.plc_ip

    @property
    def plc_port(self) -> int:
        """Get validated PLC port."""
        if not self._loaded:
            self.load()
        return self._credentials.plc_port

    @property
    def plc_byte_order(self) -> str:
        """Get validated PLC byte order."""
        if not self._loaded:
            self.load()
        return self._credentials.plc_byte_order

    def get_database_config(self) -> Dict[str, str]:
        """Get secure database configuration."""
        return get_database_config()

    def get_plc_config(self) -> Dict[str, Any]:
        """Get secure PLC configuration."""
        config = get_plc_config()
        return {
            'ip_address': config['ip'],
            'port': config['port'],
            'byte_order': config['byte_order'],
            'type': config['type']
        }

    def missing_required_keys(self) -> list:
        """Return a list of missing critical configuration keys."""
        missing = []
        try:
            if not self._loaded:
                self.load()
            # If we get here, all required keys are present
            return []
        except Exception as e:
            # Parse the error to identify missing keys
            error_str = str(e).lower()
            if 'supabase_url' in error_str:
                missing.append('SUPABASE_URL')
            if 'supabase_key' in error_str:
                missing.append('SUPABASE_KEY')
            if 'machine_id' in error_str:
                missing.append('MACHINE_ID')
            return missing

    def is_supabase_config_present(self) -> bool:
        """Check if Supabase configuration is present and valid."""
        try:
            config = self.get_database_config()
            return bool(config.get('url') and config.get('key'))
        except Exception:
            return False

    def is_core_config_ready(self) -> bool:
        """Check if all critical configuration is present and valid."""
        try:
            if not self._loaded:
                self.load()
            return bool(self._credentials.supabase_url and
                       self._credentials.supabase_key and
                       self._credentials.machine_id)
        except Exception:
            return False


# Global secure configuration instance
_secure_config: Optional[SecureConfig] = None


def get_secure_config() -> SecureConfig:
    """Get the global secure configuration instance."""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfig()
    return _secure_config


# Legacy compatibility layer for existing code
def get_legacy_config_vars():
    """Get configuration variables in legacy format for backward compatibility."""
    config = get_secure_config()

    return {
        'SUPABASE_URL': config.supabase_url,
        'SUPABASE_KEY': config.supabase_key,
        'MACHINE_ID': config.machine_id,
        'PLC_TYPE': config.plc_type,
        'PLC_IP': config.plc_ip,
        'PLC_PORT': config.plc_port,
        'PLC_BYTE_ORDER': config.plc_byte_order,
    }


# Command status constants (unchanged for compatibility)
class CommandStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


# Machine state constants (unchanged for compatibility)
class MachineState:
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    OFFLINE = "offline"


# Legacy compatibility functions
def missing_required_keys() -> list:
    """Return a list of missing critical configuration env keys."""
    return get_secure_config().missing_required_keys()


def is_supabase_config_present() -> bool:
    """Check if Supabase URL and KEY exist."""
    return get_secure_config().is_supabase_config_present()


def is_core_config_ready() -> bool:
    """Check if all critical config (Supabase + Machine ID) is present."""
    return get_secure_config().is_core_config_ready()


# Legacy variable access with secure loading
def _get_legacy_var(var_name: str):
    """Get a legacy configuration variable with secure loading."""
    config = get_secure_config()
    vars_map = {
        'SUPABASE_URL': lambda: config.supabase_url,
        'SUPABASE_KEY': lambda: config.supabase_key,
        'MACHINE_ID': lambda: config.machine_id,
        'PLC_TYPE': lambda: config.plc_type,
        'PLC_IP': lambda: config.plc_ip,
        'PLC_PORT': lambda: config.plc_port,
        'PLC_BYTE_ORDER': lambda: config.plc_byte_order,
    }

    if var_name in vars_map:
        try:
            return vars_map[var_name]()
        except Exception:
            return None
    return None


# Legacy variables for backward compatibility
SUPABASE_URL = _get_legacy_var('SUPABASE_URL')
SUPABASE_KEY = _get_legacy_var('SUPABASE_KEY')
MACHINE_ID = _get_legacy_var('MACHINE_ID')
PLC_TYPE = _get_legacy_var('PLC_TYPE')
PLC_IP = _get_legacy_var('PLC_IP')
PLC_PORT = _get_legacy_var('PLC_PORT')
PLC_BYTE_ORDER = _get_legacy_var('PLC_BYTE_ORDER')

# PLC configuration with secure loading
def get_plc_config_legacy():
    """Get PLC configuration in legacy format."""
    config = get_secure_config()
    plc_config = config.get_plc_config()

    return {
        'ip_address': plc_config['ip_address'],
        'port': plc_config['port'],
        'byte_order': plc_config['byte_order'],
        'hostname': None,  # Not supported in secure config yet
        'auto_discover': False,  # Not supported in secure config yet
    }

PLC_CONFIG = get_plc_config_legacy()

# Feature flags (preserved for compatibility)
_DEFAULT_FILTER_IDS = {
    "e3e6e280-0794-459f-84d5-5e468f60746e",
}

def _parse_csv_ids(value: str) -> Set[str]:
    items = [x.strip() for x in value.split(",") if x and x.strip()]
    return set(items)

# Note: For secure implementation, feature flags should be moved to secure configuration
# For now, maintaining legacy behavior
import os
ESSENTIALS_FILTER_MACHINE_IDS: Set[str] = (
    _parse_csv_ids(os.getenv("ESSENTIALS_FILTER_MACHINE_IDS", "")) or _DEFAULT_FILTER_IDS
)

def is_essentials_filter_enabled() -> bool:
    """Return True if the essentials filter is enabled for this MACHINE_ID."""
    config = get_secure_config()
    try:
        machine_id = config.machine_id
        return bool(machine_id and machine_id in ESSENTIALS_FILTER_MACHINE_IDS)
    except Exception:
        return False