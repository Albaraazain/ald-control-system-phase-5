"""
Rate Limiting and Security Controls Module

This module provides rate limiting and security controls to prevent
DoS attacks and abuse of the ALD control system.
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import hashlib
from src.log_setup import logger


class SecurityLevel(Enum):
    """Security level definitions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: int
    burst_size: int
    window_size: int = 60  # seconds
    block_duration: int = 300  # 5 minutes


class RateLimiter:
    """Token bucket rate limiter with sliding window."""

    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.buckets: Dict[str, Dict] = defaultdict(lambda: {
            'tokens': config.burst_size,
            'last_refill': time.time(),
            'requests': deque(),
            'blocked_until': 0
        })
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    async def is_allowed(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """
        Check if request is allowed.

        Args:
            identifier: Unique identifier for rate limiting (IP, user, etc.)

        Returns:
            Tuple of (is_allowed, reason)
        """
        await self._cleanup_old_entries()

        bucket = self.buckets[identifier]
        current_time = time.time()

        # Check if currently blocked
        if current_time < bucket['blocked_until']:
            return False, f"Rate limited until {bucket['blocked_until']}"

        # Refill tokens based on elapsed time
        time_passed = current_time - bucket['last_refill']
        tokens_to_add = int(time_passed * self.config.requests_per_second)
        bucket['tokens'] = min(
            self.config.burst_size,
            bucket['tokens'] + tokens_to_add
        )
        bucket['last_refill'] = current_time

        # Check sliding window
        self._update_sliding_window(bucket, current_time)

        # Check if request can proceed
        if bucket['tokens'] > 0:
            bucket['tokens'] -= 1
            bucket['requests'].append(current_time)
            return True, None
        else:
            # Block if too many requests
            bucket['blocked_until'] = current_time + self.config.block_duration
            logger.warning(f"Rate limit exceeded for {identifier}, blocked for {self.config.block_duration}s")
            return False, "Rate limit exceeded"

    def _update_sliding_window(self, bucket: Dict, current_time: float):
        """Update sliding window by removing old requests."""
        window_start = current_time - self.config.window_size
        while bucket['requests'] and bucket['requests'][0] < window_start:
            bucket['requests'].popleft()

    async def _cleanup_old_entries(self):
        """Clean up old bucket entries."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, bucket in self.buckets.items():
            # Remove buckets with no recent activity
            if (current_time - bucket['last_refill'] > self._cleanup_interval and
                current_time > bucket['blocked_until']):
                expired_keys.append(key)

        for key in expired_keys:
            del self.buckets[key]

        self._last_cleanup = current_time

    def get_stats(self, identifier: str) -> Dict:
        """Get rate limiting stats for identifier."""
        bucket = self.buckets.get(identifier)
        if not bucket:
            return {"status": "no_data"}

        current_time = time.time()
        return {
            "tokens_remaining": bucket['tokens'],
            "blocked_until": bucket['blocked_until'] if current_time < bucket['blocked_until'] else None,
            "recent_requests": len(bucket['requests']),
            "last_request": bucket['last_refill']
        }


class SecurityController:
    """Comprehensive security control system."""

    def __init__(self):
        """Initialize security controller."""
        # Different rate limits for different operations
        self.rate_limiters = {
            SecurityLevel.LOW: RateLimiter(RateLimitConfig(
                requests_per_second=10,
                burst_size=20,
                window_size=60,
                block_duration=60
            )),
            SecurityLevel.MEDIUM: RateLimiter(RateLimitConfig(
                requests_per_second=5,
                burst_size=10,
                window_size=60,
                block_duration=300
            )),
            SecurityLevel.HIGH: RateLimiter(RateLimitConfig(
                requests_per_second=2,
                burst_size=5,
                window_size=60,
                block_duration=600
            )),
            SecurityLevel.CRITICAL: RateLimiter(RateLimitConfig(
                requests_per_second=1,
                burst_size=2,
                window_size=60,
                block_duration=1800
            ))
        }

        # Security monitoring
        self.failed_attempts: Dict[str, int] = defaultdict(int)
        self.suspicious_activity: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

    async def check_access(self, identifier: str, operation: str,
                          security_level: SecurityLevel = SecurityLevel.MEDIUM) -> Tuple[bool, Optional[str]]:
        """
        Check if access is allowed for operation.

        Args:
            identifier: Client identifier (IP, user ID, etc.)
            operation: Operation being performed
            security_level: Security level for the operation

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Create composite identifier for operation-specific limiting
        composite_id = self._create_identifier(identifier, operation)

        # Check rate limiting
        rate_limiter = self.rate_limiters[security_level]
        allowed, reason = await rate_limiter.is_allowed(composite_id)

        if not allowed:
            self._log_security_event(identifier, operation, "rate_limited", reason)
            self.failed_attempts[identifier] += 1

        return allowed, reason

    def _create_identifier(self, identifier: str, operation: str) -> str:
        """Create composite identifier for rate limiting."""
        return hashlib.md5(f"{identifier}:{operation}".encode()).hexdigest()

    def _log_security_event(self, identifier: str, operation: str,
                           event_type: str, details: str):
        """Log security events."""
        event = {
            'timestamp': time.time(),
            'identifier': identifier,
            'operation': operation,
            'event_type': event_type,
            'details': details
        }

        self.suspicious_activity[identifier].append(event)
        logger.warning(f"Security event: {event_type} for {identifier} on {operation}: {details}")

    async def validate_plc_operation(self, identifier: str, address: int,
                                   value: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate PLC operations with security checks.

        Args:
            identifier: Client identifier
            address: PLC address being accessed
            value: Value being written (if write operation)

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Determine security level based on address ranges
        if address < 1000:
            security_level = SecurityLevel.CRITICAL  # Critical control registers
        elif address < 5000:
            security_level = SecurityLevel.HIGH      # Important parameters
        elif address < 10000:
            security_level = SecurityLevel.MEDIUM    # Regular parameters
        else:
            security_level = SecurityLevel.LOW       # Read-only data

        # Check if write operation
        operation = "plc_write" if value is not None else "plc_read"
        if operation == "plc_write":
            security_level = SecurityLevel.CRITICAL  # All writes are critical

        return await self.check_access(identifier, operation, security_level)

    async def validate_database_operation(self, identifier: str,
                                        operation: str, table: str) -> Tuple[bool, Optional[str]]:
        """
        Validate database operations with security checks.

        Args:
            identifier: Client identifier
            operation: Database operation (select, insert, update, delete)
            table: Table being accessed

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Determine security level
        critical_tables = ['machines', 'machine_state', 'process_executions']
        sensitive_tables = ['parameter_value_history', 'process_data_points']

        if table in critical_tables:
            security_level = SecurityLevel.CRITICAL
        elif table in sensitive_tables:
            security_level = SecurityLevel.HIGH
        else:
            security_level = SecurityLevel.MEDIUM

        # Writes are more restricted
        if operation in ['insert', 'update', 'delete']:
            if security_level == SecurityLevel.MEDIUM:
                security_level = SecurityLevel.HIGH
            elif security_level == SecurityLevel.HIGH:
                security_level = SecurityLevel.CRITICAL

        return await self.check_access(identifier, f"db_{operation}_{table}", security_level)

    def get_security_status(self, identifier: str) -> Dict:
        """Get security status for identifier."""
        status = {
            'failed_attempts': self.failed_attempts.get(identifier, 0),
            'recent_events': list(self.suspicious_activity.get(identifier, [])),
            'rate_limits': {}
        }

        # Get rate limit status for each security level
        for level, limiter in self.rate_limiters.items():
            composite_id = self._create_identifier(identifier, "general")
            status['rate_limits'][level.value] = limiter.get_stats(composite_id)

        return status

    def reset_security_status(self, identifier: str):
        """Reset security status for identifier (admin function)."""
        self.failed_attempts.pop(identifier, None)
        self.suspicious_activity.pop(identifier, None)

        # Reset rate limit buckets
        for limiter in self.rate_limiters.values():
            keys_to_remove = [k for k in limiter.buckets.keys() if identifier in k]
            for key in keys_to_remove:
                del limiter.buckets[key]

        logger.info(f"Security status reset for {identifier}")


# Global security controller instance
_security_controller: Optional[SecurityController] = None


def get_security_controller() -> SecurityController:
    """Get the global security controller instance."""
    global _security_controller
    if _security_controller is None:
        _security_controller = SecurityController()
    return _security_controller


async def check_plc_access(identifier: str, address: int,
                          value: Optional[float] = None) -> Tuple[bool, Optional[str]]:
    """Convenience function for PLC access checking."""
    controller = get_security_controller()
    return await controller.validate_plc_operation(identifier, address, value)


async def check_database_access(identifier: str, operation: str,
                               table: str) -> Tuple[bool, Optional[str]]:
    """Convenience function for database access checking."""
    controller = get_security_controller()
    return await controller.validate_database_operation(identifier, operation, table)


# Decorator for automatic security checking
def require_security_check(security_level: SecurityLevel = SecurityLevel.MEDIUM,
                          operation: str = "general"):
    """
    Decorator for automatic security checking.

    Args:
        security_level: Required security level
        operation: Operation name for rate limiting
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Try to extract identifier from function arguments
            identifier = kwargs.get('identifier') or kwargs.get('client_id') or 'unknown'

            controller = get_security_controller()
            allowed, reason = await controller.check_access(identifier, operation, security_level)

            if not allowed:
                raise SecurityError(f"Security check failed: {reason}")

            return await func(*args, **kwargs)
        return wrapper
    return decorator


class SecurityError(Exception):
    """Security-related error."""
    pass