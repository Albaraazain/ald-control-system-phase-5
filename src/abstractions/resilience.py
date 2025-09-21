# File: src/abstractions/resilience.py
"""
Resilience patterns for fault tolerance and system stability.
Includes Circuit Breaker, Retry, Timeout, and Bulkhead patterns.
"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar, Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import functools

from src.log_setup import logger

T = TypeVar('T')

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered

class RetryStrategy(Enum):
    """Retry strategy types"""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    success_threshold: int = 3  # for half-open state
    timeout: float = 30.0  # operation timeout
    monitored_exceptions: List[type] = field(default_factory=list)

@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    jitter: bool = True
    retryable_exceptions: List[type] = field(default_factory=list)

@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring"""
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[datetime]
    total_requests: int
    successful_requests: int
    failed_requests: int
    rejected_requests: int
    average_response_time: float

class CircuitBreakerException(Exception):
    """Exception thrown when circuit breaker is open"""
    pass

class TimeoutException(Exception):
    """Exception thrown when operation times out"""
    pass

class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.

    Monitors failures and automatically opens/closes the circuit
    to prevent cascading failures and allow system recovery.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

        # Metrics
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._rejected_requests = 0
        self._response_times: List[float] = []

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker"""
        async with self._lock:
            # Check if circuit should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                else:
                    self._rejected_requests += 1
                    raise CircuitBreakerException(f"Circuit breaker '{self.name}' is OPEN")

        self._total_requests += 1
        start_time = time.perf_counter()

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_function(func, *args, **kwargs),
                timeout=self.config.timeout
            )

            # Record success
            execution_time = time.perf_counter() - start_time
            await self._record_success(execution_time)
            return result

        except asyncio.TimeoutError:
            execution_time = time.perf_counter() - start_time
            await self._record_failure(TimeoutException(f"Operation timed out after {self.config.timeout}s"))
            raise TimeoutException(f"Operation timed out after {self.config.timeout}s")

        except Exception as e:
            execution_time = time.perf_counter() - start_time
            if self._should_record_failure(e):
                await self._record_failure(e)
            else:
                # Don't count as failure for circuit breaker
                self._response_times.append(execution_time)
            raise

    async def _execute_function(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute the actual function"""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def _should_record_failure(self, exception: Exception) -> bool:
        """Check if exception should be recorded as a failure"""
        if not self.config.monitored_exceptions:
            return True  # Record all exceptions if none specified

        return any(isinstance(exception, exc_type) for exc_type in self.config.monitored_exceptions)

    async def _record_success(self, execution_time: float):
        """Record successful execution"""
        async with self._lock:
            self._successful_requests += 1
            self._response_times.append(execution_time)

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")

    async def _record_failure(self, exception: Exception):
        """Record failed execution"""
        async with self._lock:
            self._failed_requests += 1
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.CLOSED and self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' transitioning to OPEN due to {self._failure_count} failures")

            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' transitioning back to OPEN")

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset"""
        if not self._last_failure_time:
            return True

        time_since_failure = datetime.utcnow() - self._last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics"""
        avg_response_time = 0.0
        if self._response_times:
            avg_response_time = sum(self._response_times) / len(self._response_times)

        return CircuitBreakerMetrics(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            total_requests=self._total_requests,
            successful_requests=self._successful_requests,
            failed_requests=self._failed_requests,
            rejected_requests=self._rejected_requests,
            average_response_time=avg_response_time
        )

    async def reset(self):
        """Manually reset circuit breaker"""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}' manually reset")

class RetryManager:
    """
    Retry manager with different retry strategies.
    """

    def __init__(self, config: RetryConfig):
        self.config = config

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with retry logic"""
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable(e):
                    raise e

                # Don't delay on last attempt
                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    logger.debug(f"Retry attempt {attempt + 1} failed, waiting {delay:.2f}s before retry")
                    await asyncio.sleep(delay)

        # All attempts failed
        logger.error(f"All {self.config.max_attempts} retry attempts failed")
        raise last_exception

    def _is_retryable(self, exception: Exception) -> bool:
        """Check if exception is retryable"""
        if not self.config.retryable_exceptions:
            return True  # Retry all exceptions if none specified

        return any(isinstance(exception, exc_type) for exc_type in self.config.retryable_exceptions)

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay

        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (2 ** attempt)

        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * (attempt + 1)

        else:
            delay = self.config.base_delay

        # Apply max delay limit
        delay = min(delay, self.config.max_delay)

        # Add jitter if enabled
        if self.config.jitter:
            import random
            jitter = random.uniform(0.0, 0.1) * delay
            delay += jitter

        return delay

class BulkheadPool:
    """
    Bulkhead pattern implementation for resource isolation.
    """

    def __init__(self, name: str, max_concurrent: int):
        self.name = name
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._total_requests = 0
        self._rejected_requests = 0

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function within bulkhead constraints"""
        self._total_requests += 1

        if self._semaphore.locked():
            self._rejected_requests += 1
            raise Exception(f"Bulkhead '{self.name}' is at capacity ({self.max_concurrent})")

        async with self._semaphore:
            self._active_count += 1
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            finally:
                self._active_count -= 1

    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead statistics"""
        return {
            'name': self.name,
            'max_concurrent': self.max_concurrent,
            'active_count': self._active_count,
            'available_slots': self.max_concurrent - self._active_count,
            'total_requests': self._total_requests,
            'rejected_requests': self._rejected_requests
        }

# Decorators for easy use
def circuit_breaker(name: str, config: CircuitBreakerConfig):
    """Decorator to apply circuit breaker to a function"""
    breaker = CircuitBreaker(name, config)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        # Attach breaker for external access
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator

def retry(config: RetryConfig):
    """Decorator to apply retry logic to a function"""
    retry_manager = RetryManager(config)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_manager.execute(func, *args, **kwargs)

        return wrapper

    return decorator

def bulkhead(name: str, max_concurrent: int):
    """Decorator to apply bulkhead pattern to a function"""
    bulkhead_pool = BulkheadPool(name, max_concurrent)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await bulkhead_pool.execute(func, *args, **kwargs)

        # Attach pool for external access
        wrapper.bulkhead_pool = bulkhead_pool
        return wrapper

    return decorator

# Combined resilience decorator
def resilient(circuit_config: CircuitBreakerConfig = None,
              retry_config: RetryConfig = None,
              bulkhead_config: tuple = None):
    """
    Combined resilience decorator with circuit breaker, retry, and bulkhead.

    Args:
        circuit_config: Circuit breaker configuration
        retry_config: Retry configuration
        bulkhead_config: Tuple of (name, max_concurrent)
    """
    def decorator(func):
        result_func = func

        # Apply bulkhead first (outermost)
        if bulkhead_config:
            name, max_concurrent = bulkhead_config
            result_func = bulkhead(name, max_concurrent)(result_func)

        # Apply circuit breaker
        if circuit_config:
            name = func.__name__
            result_func = circuit_breaker(name, circuit_config)(result_func)

        # Apply retry (innermost)
        if retry_config:
            result_func = retry(retry_config)(result_func)

        return result_func

    return decorator