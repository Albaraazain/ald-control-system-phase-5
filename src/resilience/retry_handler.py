"""
Network retry handler with exponential backoff and jitter.

Provides decorators and utilities for retrying network operations with
intelligent backoff strategies, timeout handling, and error classification.
"""
import asyncio
import functools
import random
from typing import Callable, TypeVar, Any, Optional
from dataclasses import dataclass
import time

T = TypeVar('T')

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    timeout: Optional[float] = None

class RetryableError(Exception):
    """Errors that should trigger a retry"""
    pass

class NonRetryableError(Exception):
    """Errors that should NOT be retried"""
    pass

def is_retryable_error(error: Exception) -> bool:
    """
    Classify if error is retryable.

    Retryable errors are typically transient network/connectivity issues.
    Non-retryable errors are auth failures, validation errors, etc.
    """
    # Network/connectivity errors - RETRY
    retryable_types = (
        ConnectionError,
        ConnectionRefusedError,
        ConnectionResetError,
        TimeoutError,
        asyncio.TimeoutError,
        OSError,  # Network errors
    )

    # Check by type
    if isinstance(error, retryable_types):
        return True

    # Check Supabase/HTTP specific errors
    error_str = str(error).lower()
    retryable_patterns = [
        'connection refused',
        'connection reset',
        'connection timeout',
        'network unreachable',
        'temporarily unavailable',
        'service unavailable',
        '502 bad gateway',
        '503 service unavailable',
        '504 gateway timeout',
        'timeout',
        'timed out',
        'connection error',
        'network error',
    ]

    # Non-retryable patterns (auth, validation)
    non_retryable_patterns = [
        'unauthorized',
        '401',
        '403 forbidden',
        'invalid api key',
        'authentication failed',
        'permission denied',
        'invalid input',
        'validation error',
    ]

    # Check non-retryable first (more specific)
    if any(pattern in error_str for pattern in non_retryable_patterns):
        return False

    return any(pattern in error_str for pattern in retryable_patterns)

def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for next retry with exponential backoff"""
    delay = min(
        config.initial_delay * (config.exponential_base ** attempt),
        config.max_delay
    )

    if config.jitter:
        # Add jitter ±25% to prevent thundering herd
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)

def retry_async(config: Optional[RetryConfig] = None):
    """
    Decorator for async functions with retry logic.

    Example:
        @retry_async(RetryConfig(max_attempts=5))
        async def fetch_data():
            return await supabase.table('data').select('*').execute()
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error = None

            for attempt in range(config.max_attempts):
                try:
                    if config.timeout:
                        return await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=config.timeout
                        )
                    else:
                        return await func(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        break

                    # Check if error is retryable
                    if not is_retryable_error(e):
                        raise NonRetryableError(f"Non-retryable error: {e}") from e

                    # Calculate delay
                    delay = calculate_delay(attempt, config)

                    # Log retry attempt
                    from src.log_setup import logger
                    logger.warning(
                        f"🔄 Retry {attempt + 1}/{config.max_attempts} for {func.__name__} "
                        f"after error: {type(e).__name__}: {e}. Waiting {delay:.2f}s"
                    )

                    await asyncio.sleep(delay)

            # All retries exhausted
            from src.log_setup import logger
            logger.error(
                f"❌ All {config.max_attempts} retry attempts exhausted for {func.__name__}. "
                f"Last error: {type(last_error).__name__}: {last_error}"
            )
            raise last_error

        return wrapper
    return decorator

# Convenience decorators for common scenarios

retry_network = retry_async(RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    jitter=True,
    timeout=30.0
))
"""Retry decorator for general network operations (3 attempts, max 10s delay)"""

retry_database = retry_async(RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    timeout=30.0
))
"""Retry decorator for database operations (5 attempts, max 30s delay)"""

retry_plc = retry_async(RetryConfig(
    max_attempts=3,
    initial_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=False,  # PLC timing sensitive - no jitter
    timeout=10.0
))
"""Retry decorator for PLC operations (3 attempts, max 5s delay, no jitter)"""

retry_heartbeat = retry_async(RetryConfig(
    max_attempts=2,
    initial_delay=1.0,
    max_delay=3.0,
    jitter=False,
    timeout=10.0
))
"""Retry decorator for heartbeat operations (2 attempts, max 3s delay)"""
