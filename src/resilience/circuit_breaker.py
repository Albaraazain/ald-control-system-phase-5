"""
Circuit breaker pattern implementation for preventing cascade failures.

A circuit breaker monitors operation failures and "opens" the circuit
when failures exceed a threshold, preventing further attempts until
the service recovers.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail immediately
- HALF_OPEN: Testing if service recovered
"""
import asyncio
import time
from enum import Enum
from typing import Callable, TypeVar, Optional, Dict
from dataclasses import dataclass, field
import functools

T = TypeVar('T')

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Circuit open, failing fast
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: float = 60.0  # Seconds to wait before half-open
    window_size: int = 10  # Number of recent calls to track

class CircuitBreaker:
    """
    Circuit breaker for protecting against cascade failures.

    Usage:
        breaker = CircuitBreaker(name='database')

        @breaker
        async def query_database():
            return await supabase.table('data').select('*').execute()
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

        # Track recent calls for failure rate
        self.recent_calls: list[bool] = []  # True = success, False = failure

        from src.log_setup import logger
        self.logger = logger

    def _record_success(self):
        """Record a successful operation"""
        self.recent_calls.append(True)
        if len(self.recent_calls) > self.config.window_size:
            self.recent_calls.pop(0)

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._close_circuit()
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _record_failure(self):
        """Record a failed operation"""
        self.recent_calls.append(False)
        if len(self.recent_calls) > self.config.window_size:
            self.recent_calls.pop(0)

        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failed while testing - go back to open
            self._open_circuit()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self._open_circuit()

    def _open_circuit(self):
        """Open the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.failure_count = 0
        self.success_count = 0
        self.logger.error(
            f"🔴 Circuit breaker '{self.name}' OPENED - "
            f"Too many failures. Will retry after {self.config.timeout}s"
        )

    def _close_circuit(self):
        """Close the circuit breaker"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.logger.info(
            f"🟢 Circuit breaker '{self.name}' CLOSED - Service recovered"
        )

    def _half_open_circuit(self):
        """Set circuit to half-open (testing recovery)"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self.logger.warning(
            f"🟡 Circuit breaker '{self.name}' HALF-OPEN - Testing service recovery"
        )

    def _should_attempt(self) -> bool:
        """Check if operation should be attempted"""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.HALF_OPEN:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if timeout elapsed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.config.timeout:
                    self._half_open_circuit()
                    return True

            return False

        return False

    def get_failure_rate(self) -> float:
        """Calculate current failure rate"""
        if not self.recent_calls:
            return 0.0
        failures = sum(1 for call in self.recent_calls if not call)
        return failures / len(self.recent_calls)

    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_rate': self.get_failure_rate(),
            'recent_calls': len(self.recent_calls),
        }

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator that applies circuit breaker to async function"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not self._should_attempt():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable. Will retry after timeout."
                )

            try:
                result = await func(*args, **kwargs)
                self._record_success()
                return result

            except Exception as e:
                self._record_failure()
                raise

        return wrapper

# Global circuit breakers for common operations
database_circuit_breaker = CircuitBreaker(
    name='database',
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=30.0,
        window_size=10
    )
)

plc_circuit_breaker = CircuitBreaker(
    name='plc',
    config=CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=10.0,
        window_size=5
    )
)
