"""
Secure Credential Management Module

This module provides secure credential loading, validation, and management
for the ALD control system. It implements security best practices including:
- Environment variable validation
- Credential rotation support
- Secure defaults
- Input sanitization
"""

import os
import sys
import re
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from cryptography.fernet import Fernet
import base64
import hashlib
from src.log_setup import logger


@dataclass
class SecureCredentials:
    """Secure container for application credentials."""
    supabase_url: str
    supabase_key: str
    machine_id: str
    test_operator_id: Optional[str] = None
    plc_type: str = "simulation"
    plc_ip: str = "127.0.0.1"
    plc_port: int = 502
    plc_byte_order: str = "badc"
    encryption_key: Optional[str] = None
    jwt_secret: Optional[str] = None
    log_level: str = "INFO"
    log_file: str = "ald_control.log"

    def __post_init__(self):
        """Validate credentials after initialization."""
        self._validate_credentials()

    def _validate_credentials(self):
        """Validate all credentials meet security requirements."""
        # Validate Supabase URL
        if not self._is_valid_url(self.supabase_url):
            raise ValueError("Invalid Supabase URL format")

        # Validate Supabase key (should be JWT format)
        if not self._is_valid_jwt_token(self.supabase_key):
            raise ValueError("Invalid Supabase key format")

        # Validate UUIDs
        if not self._is_valid_uuid(self.machine_id):
            raise ValueError("Invalid machine ID format")

        if self.test_operator_id and not self._is_valid_uuid(self.test_operator_id):
            raise ValueError("Invalid test operator ID format")

        # Validate PLC configuration
        if self.plc_type not in ["simulation", "real"]:
            raise ValueError("PLC type must be 'simulation' or 'real'")

        if not self._is_valid_ip(self.plc_ip):
            raise ValueError("Invalid PLC IP address")

        if not (1 <= self.plc_port <= 65535):
            raise ValueError("PLC port must be between 1 and 65535")

        if self.plc_byte_order not in ["abcd", "badc", "cdab", "dcba"]:
            raise ValueError("Invalid PLC byte order")

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(url))

    def _is_valid_jwt_token(self, token: str) -> bool:
        """Validate JWT token format."""
        parts = token.split('.')
        return len(parts) == 3 and all(len(part) > 0 for part in parts)

    def _is_valid_uuid(self, uuid_str: str) -> bool:
        """Validate UUID format."""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(uuid_str))

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except (ValueError, AttributeError):
            return False


class SecureCredentialManager:
    """Secure credential management with validation and rotation support."""

    def __init__(self, env_file: str = ".env"):
        """
        Initialize credential manager.

        Args:
            env_file: Path to environment file (optional)
        """
        self.env_file = env_file
        self._credentials: Optional[SecureCredentials] = None
        self._encryption_key: Optional[bytes] = None

    def load_credentials(self, force_reload: bool = False) -> SecureCredentials:
        """
        Load and validate credentials from environment.

        Args:
            force_reload: Force reload of credentials even if already loaded

        Returns:
            SecureCredentials object with validated credentials

        Raises:
            ValueError: If required credentials are missing or invalid
            SecurityError: If credential security validation fails
        """
        if self._credentials and not force_reload:
            return self._credentials

        logger.info("Loading secure credentials from environment")

        # Load from environment file if it exists
        if os.path.exists(self.env_file):
            self._load_env_file()

        # Extract and validate credentials
        try:
            credentials = SecureCredentials(
                supabase_url=self._get_required_env("SUPABASE_URL"),
                supabase_key=self._get_required_env("SUPABASE_KEY"),
                machine_id=self._get_required_env("MACHINE_ID"),
                test_operator_id=self._get_optional_env("TEST_OPERATOR_ID"),
                plc_type=self._get_optional_env("PLC_TYPE", "simulation"),
                plc_ip=self._get_optional_env("PLC_IP", "127.0.0.1"),
                plc_port=int(self._get_optional_env("PLC_PORT", "502")),
                plc_byte_order=self._get_optional_env("PLC_BYTE_ORDER", "badc"),
                encryption_key=self._get_optional_env("ENCRYPTION_KEY"),
                jwt_secret=self._get_optional_env("JWT_SECRET"),
                log_level=self._get_optional_env("LOG_LEVEL", "INFO"),
                log_file=self._get_optional_env("LOG_FILE", "ald_control.log")
            )

            self._credentials = credentials
            logger.info("Credentials loaded and validated successfully")
            return credentials

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            raise SecurityError(f"Credential loading failed: {e}")

    def _load_env_file(self):
        """Load environment variables from .env file."""
        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception as e:
            logger.warning(f"Could not load .env file {self.env_file}: {e}")

    def _get_required_env(self, key: str) -> str:
        """Get required environment variable."""
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return self._sanitize_input(value)

    def _get_optional_env(self, key: str, default: str = None) -> Optional[str]:
        """Get optional environment variable."""
        value = os.environ.get(key, default)
        return self._sanitize_input(value) if value else None

    def _sanitize_input(self, value: str) -> str:
        """Sanitize input to prevent injection attacks."""
        if not isinstance(value, str):
            raise ValueError("Input must be a string")

        # Remove null bytes and control characters
        sanitized = value.replace('\x00', '').replace('\r', '').replace('\n', '')

        # Limit length to prevent buffer overflow
        if len(sanitized) > 1024:
            raise ValueError("Input value too long")

        return sanitized

    def rotate_credentials(self, new_credentials: Dict[str, str]) -> bool:
        """
        Rotate credentials with validation.

        Args:
            new_credentials: Dictionary of new credential values

        Returns:
            True if rotation successful, False otherwise
        """
        try:
            # Backup current credentials
            backup = dict(os.environ)

            # Update environment with new credentials
            for key, value in new_credentials.items():
                os.environ[key] = self._sanitize_input(value)

            # Validate new credentials
            new_creds = self.load_credentials(force_reload=True)

            logger.info("Credential rotation completed successfully")
            return True

        except Exception as e:
            # Restore backup on failure
            os.environ.clear()
            os.environ.update(backup)
            logger.error(f"Credential rotation failed: {e}")
            return False

    def get_secure_config(self) -> Dict[str, Any]:
        """
        Get configuration dictionary with sensitive values redacted for logging.

        Returns:
            Configuration dictionary safe for logging
        """
        if not self._credentials:
            self.load_credentials()

        config = {
            "supabase_url": self._redact_url(self._credentials.supabase_url),
            "machine_id": self._credentials.machine_id,
            "plc_type": self._credentials.plc_type,
            "plc_ip": self._credentials.plc_ip,
            "plc_port": self._credentials.plc_port,
            "plc_byte_order": self._credentials.plc_byte_order,
            "log_level": self._credentials.log_level,
            "log_file": self._credentials.log_file,
            "has_encryption_key": bool(self._credentials.encryption_key),
            "has_jwt_secret": bool(self._credentials.jwt_secret)
        }

        return config

    def _redact_url(self, url: str) -> str:
        """Redact sensitive parts of URL for logging."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.scheme}://***{parsed.netloc[-10:]}"
        except Exception:
            return "***redacted***"

    def get_database_config(self) -> Dict[str, str]:
        """Get database configuration for Supabase client."""
        if not self._credentials:
            self.load_credentials()

        return {
            "url": self._credentials.supabase_url,
            "key": self._credentials.supabase_key
        }

    def get_plc_config(self) -> Dict[str, Union[str, int]]:
        """Get PLC configuration."""
        if not self._credentials:
            self.load_credentials()

        return {
            "type": self._credentials.plc_type,
            "ip": self._credentials.plc_ip,
            "port": self._credentials.plc_port,
            "byte_order": self._credentials.plc_byte_order
        }


class SecurityError(Exception):
    """Security-related error."""
    pass


# Global credential manager instance
_credential_manager: Optional[SecureCredentialManager] = None


def get_credential_manager() -> SecureCredentialManager:
    """Get the global credential manager instance."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = SecureCredentialManager()
    return _credential_manager


def get_secure_credentials() -> SecureCredentials:
    """Get secure credentials using the global manager."""
    return get_credential_manager().load_credentials()


def get_database_config() -> Dict[str, str]:
    """Get database configuration."""
    return get_credential_manager().get_database_config()


def get_plc_config() -> Dict[str, Union[str, int]]:
    """Get PLC configuration."""
    return get_credential_manager().get_plc_config()