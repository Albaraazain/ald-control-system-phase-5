"""
Logging configuration for the machine control application.

Adds:
- Service-specific loggers with dedicated log files and formatters
- Env/CLI-driven log level selection via `LOG_LEVEL` and `set_log_level()`
- Standard operator markers for success/warn/failure (✅, ⚠️, ❌) with ASCII fallback
- Log rotation and independent log level configuration per service
"""
import logging
import logging.handlers
import os
import threading
from pathlib import Path
from typing import Dict, Optional

# Operator-facing log markers (emojis), with optional ASCII fallback via LOG_MARKERS_ASCII=true
ASCII_FALLBACK = os.getenv("LOG_MARKERS_ASCII", "false").lower() in {"1", "true", "yes"}
OK_MARK = "OK" if ASCII_FALLBACK else "✅"
WARN_MARK = "WARN" if ASCII_FALLBACK else "⚠️"
FAIL_MARK = "FAIL" if ASCII_FALLBACK else "❌"

# Log directory setup
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(exist_ok=True)

# Service-specific logger registry with thread safety
_service_loggers: Dict[str, logging.Logger] = {}
_logger_lock = threading.RLock()  # Re-entrant lock for nested calls

# Service definitions with their log file names and default levels
SERVICE_CONFIGS = {
    "machine_control": {"file": "machine_control.log", "level": "INFO"},
    "command_flow": {"file": "command_flow.log", "level": "INFO"},
    "recipe_flow": {"file": "recipe_flow.log", "level": "INFO"},
    "step_flow": {"file": "step_flow.log", "level": "INFO"},
    "plc": {"file": "plc.log", "level": "INFO"},
    "plc_read": {"file": "plc_read.log", "level": "INFO"},
    "data_collection": {"file": "data_collection.log", "level": "INFO"},
    "security": {"file": "security.log", "level": "WARNING"},
    "performance": {"file": "performance.log", "level": "INFO"},
    "agents": {"file": "agents.log", "level": "INFO"},
    "realtime": {"file": "realtime.log", "level": "INFO"},
    "connection_monitor": {"file": "connection_monitor.log", "level": "INFO"},
    "idle": {"file": "idle.log", "level": "INFO"},
    "di": {"file": "dependency_injection.log", "level": "INFO"},
    "domain": {"file": "domain.log", "level": "INFO"},
    "abstractions": {"file": "abstractions.log", "level": "INFO"},
    "utils": {"file": "utils.log", "level": "INFO"},
}


def _get_log_level_from_env(level_str: Optional[str] = None) -> int:
    """Map LOG_LEVEL env var to logging level."""
    if level_str is None:
        level_str = os.getenv("LOG_LEVEL", "INFO")
    level_str = level_str.upper()
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(level_str, logging.INFO)


def _create_service_logger(service_name: str, config: dict) -> logging.Logger:
    """Create a service-specific logger with its own file handler and rotation."""
    logger = logging.getLogger(f"machine_control.{service_name}")

    # Check if handlers are already properly configured
    if logger.handlers:
        # Verify we have both console and file handlers
        has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers)
        has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers)
        if has_console and has_file:
            return logger
        # If incomplete handler setup, clear and recreate
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()

    # Determine level from environment or service config
    level_env_var = f"LOG_LEVEL_{service_name.upper()}"
    level_str = os.getenv(level_env_var, config.get("level", "INFO"))
    level = _get_log_level_from_env(level_str)
    logger.setLevel(level)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    # Create service-specific formatter
    formatter = logging.Formatter(
        f"%(asctime)s - [{service_name.upper()}] - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # Rotating file handler for service-specific logs
    log_file_path = LOG_DIR / config["file"]

    # Safe environment variable parsing with validation
    try:
        max_bytes = int(os.getenv(f"LOG_MAX_BYTES_{service_name.upper()}", "10485760"))
        if max_bytes <= 0:
            max_bytes = 10485760  # 10MB default
    except (ValueError, TypeError):
        max_bytes = 10485760  # 10MB default

    try:
        backup_count = int(os.getenv(f"LOG_BACKUP_COUNT_{service_name.upper()}", "5"))
        if backup_count < 0:
            backup_count = 5  # 5 files default
    except (ValueError, TypeError):
        backup_count = 5  # 5 files default

    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    return logger

def get_service_logger(service_name: str) -> logging.Logger:
    """Get or create a service-specific logger (thread-safe)."""
    with _logger_lock:
        # Check again inside the lock (double-checked locking pattern)
        if service_name in _service_loggers:
            return _service_loggers[service_name]

        if service_name not in SERVICE_CONFIGS:
            # For unknown services, create a generic logger
            logger = logging.getLogger(f"machine_control.{service_name}")
            _service_loggers[service_name] = logger
            return logger

        # Create service-specific logger
        config = SERVICE_CONFIGS[service_name]
        logger = _create_service_logger(service_name, config)
        _service_loggers[service_name] = logger
        return logger

def setup_logger(name: str = "machine_control"):
    """Configure and return a logger with console and file handlers (legacy compatibility)."""
    # For backward compatibility, map the default logger to machine_control service
    if name == "machine_control":
        return get_service_logger("machine_control")

    # For other names, create a generic logger
    logger = logging.getLogger(name)

    # Determine level from environment
    level = _get_log_level_from_env()

    # Only set up handlers if they haven't been set up already
    if not logger.handlers:
        logger.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler (allow override via LOG_FILE)
        log_file = os.getenv("LOG_FILE", "machine_control.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        # Update level dynamically if handlers already exist
        logger.setLevel(level)
        for h in logger.handlers:
            h.setLevel(level)

    return logger


def set_log_level(level_str: str, service_name: Optional[str] = None) -> None:
    """Programmatically adjust log level at runtime for a service or all services (thread-safe)."""
    level = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(level_str.upper(), logging.INFO)

    with _logger_lock:
        if service_name:
            # Set level for specific service
            if service_name in _service_loggers:
                logger = _service_loggers[service_name]
                logger.setLevel(level)
                for h in logger.handlers:
                    h.setLevel(level)
        else:
            # Set level for all service loggers (backward compatibility)
            for logger in _service_loggers.values():
                logger.setLevel(level)
                for h in logger.handlers:
                    h.setLevel(level)

            # Also set for default machine_control logger
            logger = logging.getLogger("machine_control")
            logger.setLevel(level)
            for h in logger.handlers:
                h.setLevel(level)

def list_service_loggers() -> Dict[str, str]:
    """List all available service loggers and their current levels (thread-safe)."""
    with _logger_lock:
        return {
            service: logging.getLevelName(logger.level)
            for service, logger in _service_loggers.items()
        }


# Create service-specific logger instances for common services
def _initialize_common_loggers():
    """Initialize commonly used service loggers."""
    for service_name in ["machine_control", "command_flow", "plc", "data_collection"]:
        get_service_logger(service_name)

_initialize_common_loggers()

# Create a default logger instance for backward compatibility
logger = get_service_logger("machine_control")

# Convenience functions for common services
def get_command_flow_logger() -> logging.Logger:
    """Get the command flow logger."""
    return get_service_logger("command_flow")

def get_recipe_flow_logger() -> logging.Logger:
    """Get the recipe flow logger."""
    return get_service_logger("recipe_flow")

def get_step_flow_logger() -> logging.Logger:
    """Get the step flow logger."""
    return get_service_logger("step_flow")

def get_plc_logger() -> logging.Logger:
    """Get the PLC logger."""
    return get_service_logger("plc")

def get_plc_read_logger() -> logging.Logger:
    """Get the PLC read service logger."""
    return get_service_logger("plc_read")

def get_data_collection_logger() -> logging.Logger:
    """Get the data collection logger."""
    return get_service_logger("data_collection")

def get_security_logger() -> logging.Logger:
    """Get the security logger."""
    return get_service_logger("security")

def get_performance_logger() -> logging.Logger:
    """Get the performance logger."""
    return get_service_logger("performance")

def get_agents_logger() -> logging.Logger:
    """Get the agents logger."""
    return get_service_logger("agents")

def get_realtime_logger() -> logging.Logger:
    """Get the realtime logger."""
    return get_service_logger("realtime")

def get_connection_monitor_logger() -> logging.Logger:
    """Get the connection monitor logger."""
    return get_service_logger("connection_monitor")
