"""
Logging configuration for the machine control application.

Adds:
- Env/CLI-driven log level selection via `LOG_LEVEL` and `set_log_level()`
- Standard operator markers for success/warn/failure (✅, ⚠️, ❌) with ASCII fallback
"""
import logging
import os

# Operator-facing log markers (emojis), with optional ASCII fallback via LOG_MARKERS_ASCII=true
ASCII_FALLBACK = os.getenv("LOG_MARKERS_ASCII", "false").lower() in {"1", "true", "yes"}
OK_MARK = "OK" if ASCII_FALLBACK else "✅"
WARN_MARK = "WARN" if ASCII_FALLBACK else "⚠️"
FAIL_MARK = "FAIL" if ASCII_FALLBACK else "❌"


def _get_log_level_from_env(default: str = "INFO") -> int:
    """Map LOG_LEVEL env var to logging level."""
    level_str = os.getenv("LOG_LEVEL", default).upper()
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(level_str, logging.INFO)


def setup_logger(name: str = "machine_control"):
    """Configure and return a logger with console and file handlers."""
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


def set_log_level(level_str: str) -> None:
    """Programmatically adjust log level at runtime."""
    level = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(level_str.upper(), logging.INFO)
    logger = logging.getLogger("machine_control")
    logger.setLevel(level)
    for h in logger.handlers:
        h.setLevel(level)


# Create a default logger instance for import
logger = setup_logger()
