"""
Security Configuration Module

This module provides centralized security configuration
for the ALD control system.
"""

import os
from typing import Dict, Any
from dataclasses import dataclass
from .rate_limiter import SecurityLevel


@dataclass
class SecurityConfig:
    """Security configuration settings."""

    # Rate limiting settings
    enable_rate_limiting: bool = True
    default_security_level: SecurityLevel = SecurityLevel.MEDIUM

    # Input validation settings
    enable_input_validation: bool = True
    max_string_length: int = 1024
    max_json_size: int = 10240  # 10KB

    # Credential security settings
    credential_rotation_interval: int = 86400  # 24 hours
    require_credential_encryption: bool = True

    # File security settings
    secure_file_permissions: int = 0o600
    enable_file_validation: bool = True

    # PLC security settings
    plc_rate_limit_enabled: bool = True
    plc_critical_address_threshold: int = 1000
    plc_max_write_frequency: int = 10  # per minute

    # Database security settings
    database_rate_limit_enabled: bool = True
    database_connection_timeout: int = 30
    database_max_connections: int = 20

    # Monitoring settings
    enable_security_monitoring: bool = True
    security_log_level: str = "WARNING"
    alert_on_rate_limit_exceeded: bool = True

    # Network security settings
    allowed_plc_networks: list = None
    deny_private_networks: bool = False

    def __post_init__(self):
        """Initialize default values."""
        if self.allowed_plc_networks is None:
            self.allowed_plc_networks = ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]


def load_security_config() -> SecurityConfig:
    """
    Load security configuration from environment variables.

    Returns:
        SecurityConfig object with values from environment
    """
    config = SecurityConfig()

    # Load from environment variables with secure defaults
    config.enable_rate_limiting = _get_bool_env("SECURITY_ENABLE_RATE_LIMITING", True)
    config.enable_input_validation = _get_bool_env("SECURITY_ENABLE_INPUT_VALIDATION", True)
    config.require_credential_encryption = _get_bool_env("SECURITY_REQUIRE_CREDENTIAL_ENCRYPTION", True)
    config.enable_file_validation = _get_bool_env("SECURITY_ENABLE_FILE_VALIDATION", True)
    config.plc_rate_limit_enabled = _get_bool_env("SECURITY_PLC_RATE_LIMIT_ENABLED", True)
    config.database_rate_limit_enabled = _get_bool_env("SECURITY_DATABASE_RATE_LIMIT_ENABLED", True)
    config.enable_security_monitoring = _get_bool_env("SECURITY_ENABLE_MONITORING", True)
    config.alert_on_rate_limit_exceeded = _get_bool_env("SECURITY_ALERT_ON_RATE_LIMIT", True)
    config.deny_private_networks = _get_bool_env("SECURITY_DENY_PRIVATE_NETWORKS", False)

    # Load numeric settings
    config.max_string_length = _get_int_env("SECURITY_MAX_STRING_LENGTH", 1024)
    config.max_json_size = _get_int_env("SECURITY_MAX_JSON_SIZE", 10240)
    config.credential_rotation_interval = _get_int_env("SECURITY_CREDENTIAL_ROTATION_INTERVAL", 86400)
    config.plc_critical_address_threshold = _get_int_env("SECURITY_PLC_CRITICAL_THRESHOLD", 1000)
    config.plc_max_write_frequency = _get_int_env("SECURITY_PLC_MAX_WRITE_FREQUENCY", 10)
    config.database_connection_timeout = _get_int_env("SECURITY_DATABASE_TIMEOUT", 30)
    config.database_max_connections = _get_int_env("SECURITY_DATABASE_MAX_CONNECTIONS", 20)

    # Load string settings
    config.security_log_level = os.environ.get("SECURITY_LOG_LEVEL", "WARNING")

    # Load security level
    security_level_str = os.environ.get("SECURITY_DEFAULT_LEVEL", "MEDIUM").upper()
    try:
        config.default_security_level = SecurityLevel(security_level_str.lower())
    except ValueError:
        config.default_security_level = SecurityLevel.MEDIUM

    # Load allowed networks
    networks_str = os.environ.get("SECURITY_ALLOWED_PLC_NETWORKS")
    if networks_str:
        config.allowed_plc_networks = [net.strip() for net in networks_str.split(",")]

    return config


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_security_recommendations() -> Dict[str, Any]:
    """
    Get security recommendations for production deployment.

    Returns:
        Dictionary of security recommendations
    """
    return {
        "environment_variables": {
            "SECURITY_ENABLE_RATE_LIMITING": "true",
            "SECURITY_ENABLE_INPUT_VALIDATION": "true",
            "SECURITY_REQUIRE_CREDENTIAL_ENCRYPTION": "true",
            "SECURITY_DEFAULT_LEVEL": "HIGH",
            "SECURITY_PLC_CRITICAL_THRESHOLD": "500",
            "SECURITY_MAX_STRING_LENGTH": "512",
            "SECURITY_ENABLE_MONITORING": "true"
        },
        "file_permissions": {
            ".env": "0o600",
            "*.key": "0o600",
            "*.pem": "0o600",
            "logs/*.log": "0o640"
        },
        "network_security": {
            "plc_networks": "Restrict to known PLC network ranges",
            "firewall": "Block unnecessary ports and protocols",
            "tls": "Enable TLS for all external communications"
        },
        "monitoring": {
            "log_aggregation": "Centralized security logging",
            "intrusion_detection": "Monitor for suspicious patterns",
            "alerting": "Real-time alerts for security events"
        },
        "operational_security": {
            "credential_rotation": "Rotate credentials every 24 hours",
            "access_review": "Regular review of access permissions",
            "security_updates": "Keep all dependencies updated",
            "backup_security": "Secure backup and recovery procedures"
        }
    }


# Global security configuration
_security_config: SecurityConfig = None


def get_security_config() -> SecurityConfig:
    """Get the global security configuration."""
    global _security_config
    if _security_config is None:
        _security_config = load_security_config()
    return _security_config


def reload_security_config() -> SecurityConfig:
    """Reload security configuration from environment."""
    global _security_config
    _security_config = load_security_config()
    return _security_config