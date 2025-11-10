"""
Resilience utilities for robust service operation.

Provides retry logic, circuit breakers, and error handling
for network, database, and PLC operations.
"""

from .retry_handler import (
    RetryConfig,
    RetryableError,
    NonRetryableError,
    retry_async,
    retry_network,
    retry_database,
    retry_plc,
    retry_heartbeat,
    is_retryable_error
)

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    database_circuit_breaker,
    plc_circuit_breaker
)

from .error_handlers import (
    setup_global_exception_handler,
    setup_asyncio_exception_handler,
    with_error_logging,
    safe_operation,
    ErrorThresholdMonitor
)

__all__ = [
    'RetryConfig',
    'RetryableError',
    'NonRetryableError',
    'retry_async',
    'retry_network',
    'retry_database',
    'retry_plc',
    'retry_heartbeat',
    'is_retryable_error',
    'CircuitBreaker',
    'CircuitBreakerState',
    'CircuitBreakerOpenError',
    'database_circuit_breaker',
    'plc_circuit_breaker',
    'setup_global_exception_handler',
    'setup_asyncio_exception_handler',
    'with_error_logging',
    'safe_operation',
    'ErrorThresholdMonitor',
]
