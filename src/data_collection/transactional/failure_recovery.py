"""
Comprehensive failure recovery and resilience implementation for transactional data integrity.

This module implements sophisticated failure recovery mechanisms including:
- Idempotent operations with deduplication
- Retry mechanisms with exponential backoff
- Dead letter queues for failed operations
- Data repair and consistency restoration
- Circuit breaker patterns for stability
"""
import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from .interfaces import IFailureRecovery


class OperationStatus(Enum):
    """Status of a recoverable operation."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class RecoverableOperation:
    """Represents an operation that can be recovered."""
    operation_id: str
    operation_type: str
    operation_data: Dict[str, Any]
    status: OperationStatus = OperationStatus.PENDING
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_attempt_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    error_message: Optional[str] = None
    backoff_factor: float = 1.5

    def calculate_next_retry(self) -> datetime:
        """Calculate the next retry time using exponential backoff."""
        base_delay = 2.0  # Base delay in seconds
        delay = base_delay * (self.backoff_factor ** self.attempt_count)
        # Cap at 5 minutes
        delay = min(delay, 300.0)
        return datetime.now(timezone.utc) + timedelta(seconds=delay)

    def should_retry(self) -> bool:
        """Check if operation should be retried."""
        return (
            self.status == OperationStatus.FAILED and
            self.attempt_count < self.max_attempts and
            (
                self.next_retry_at is None or
                datetime.now(timezone.utc) >= self.next_retry_at
            )
        )

    def to_dead_letter(self) -> None:
        """Move operation to dead letter status."""
        self.status = OperationStatus.DEAD_LETTER
        logger.error(
            f"Operation {self.operation_id} moved to dead letter after "
            f"{self.attempt_count} attempts: {self.error_message}"
        )


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting external services."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    reset_timeout: float = 10.0    # seconds

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None

    def call_succeeded(self) -> None:
        """Record a successful call."""
        self.failure_count = 0
        self.last_success_time = datetime.now(timezone.utc)
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            logger.info("Circuit breaker reset to CLOSED")

    def call_failed(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if (self.state == CircuitBreakerState.CLOSED and
            self.failure_count >= self.failure_threshold):
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker returned to OPEN from HALF_OPEN")

    def can_execute(self) -> bool:
        """Check if calls can be executed."""
        now = datetime.now(timezone.utc)

        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if (self.last_failure_time and
                (now - self.last_failure_time).total_seconds() >= self.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker moved to HALF_OPEN")
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False


class ComprehensiveFailureRecovery(IFailureRecovery):
    """
    Comprehensive failure recovery implementation with advanced resilience patterns.

    Features:
    - Idempotent operations with deduplication
    - Exponential backoff retry mechanism
    - Dead letter queue for failed operations
    - Circuit breaker protection
    - Data consistency repair
    - Compensating transactions
    """

    def __init__(self, cleanup_interval: float = 300.0):
        """Initialize the failure recovery system."""
        self.cleanup_interval = cleanup_interval
        self._operations: Dict[str, RecoverableOperation] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._deduplication_cache: Dict[str, str] = {}  # hash -> operation_id
        self._compensation_registry: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._is_running = False
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the failure recovery service."""
        if self._is_running:
            return

        self._is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Failure recovery service started")

    async def stop(self) -> None:
        """Stop the failure recovery service."""
        if not self._is_running:
            return

        self._is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Failure recovery service stopped")

    async def execute_with_retry(
        self,
        operation: Callable,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        operation_type: str = "generic",
        idempotency_key: Optional[str] = None
    ) -> Any:
        """
        Execute operation with retry logic and optional idempotency.

        Args:
            operation: The operation to execute
            max_retries: Maximum number of retry attempts
            backoff_factor: Multiplier for exponential backoff
            operation_type: Type of operation for circuit breaker grouping
            idempotency_key: Optional key for idempotent operations
        """
        # Check for idempotency
        if idempotency_key:
            async with self._lock:
                if idempotency_key in self._deduplication_cache:
                    existing_op_id = self._deduplication_cache[idempotency_key]
                    existing_op = self._operations.get(existing_op_id)
                    if existing_op and existing_op.status == OperationStatus.COMPLETED:
                        logger.info(f"Idempotent operation {idempotency_key} already completed")
                        return existing_op.operation_data.get('result')

        # Get or create circuit breaker for this operation type
        circuit_breaker = self._get_circuit_breaker(operation_type)

        if not circuit_breaker.can_execute():
            raise RuntimeError(f"Circuit breaker is OPEN for {operation_type}")

        operation_id = str(uuid.uuid4())
        recoverable_op = RecoverableOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            operation_data={'idempotency_key': idempotency_key},
            max_attempts=max_retries + 1,
            backoff_factor=backoff_factor
        )

        async with self._lock:
            self._operations[operation_id] = recoverable_op
            if idempotency_key:
                self._deduplication_cache[idempotency_key] = operation_id

        for attempt in range(max_retries + 1):
            recoverable_op.attempt_count = attempt + 1
            recoverable_op.last_attempt_at = datetime.now(timezone.utc)
            recoverable_op.status = OperationStatus.PROCESSING

            try:
                logger.debug(f"Executing operation {operation_id}, attempt {attempt + 1}")
                result = await operation()

                # Success
                recoverable_op.status = OperationStatus.COMPLETED
                recoverable_op.operation_data['result'] = result
                circuit_breaker.call_succeeded()

                logger.debug(f"Operation {operation_id} completed successfully")
                return result

            except Exception as e:
                error_msg = str(e)
                recoverable_op.error_message = error_msg
                circuit_breaker.call_failed()

                logger.warning(
                    f"Operation {operation_id} failed on attempt {attempt + 1}: {error_msg}"
                )

                if attempt < max_retries:
                    # Calculate backoff delay
                    delay = 2.0 * (backoff_factor ** attempt)
                    delay = min(delay, 300.0)  # Cap at 5 minutes

                    recoverable_op.next_retry_at = recoverable_op.calculate_next_retry()
                    recoverable_op.status = OperationStatus.FAILED

                    logger.info(f"Retrying operation {operation_id} in {delay:.2f} seconds")
                    await asyncio.sleep(delay)
                else:
                    # Final failure
                    recoverable_op.to_dead_letter()
                    raise RuntimeError(
                        f"Operation {operation_id} failed after {max_retries + 1} attempts: {error_msg}"
                    )

    async def create_compensating_action(
        self,
        operation_id: str,
        operation_data: Dict[str, Any]
    ) -> None:
        """Create compensating action for rollback."""
        async with self._lock:
            if operation_id not in self._compensation_registry:
                self._compensation_registry[operation_id] = []

        # Create compensation based on operation type
        if operation_data.get('type') == 'dual_mode_insert':
            compensation = self._create_dual_mode_compensation(operation_data)
            async with self._lock:
                self._compensation_registry[operation_id].append(compensation)

        logger.debug(f"Created compensating action for operation {operation_id}")

    async def execute_compensating_actions(self, transaction_id: str) -> None:
        """Execute all compensating actions for a transaction."""
        compensations = []
        async with self._lock:
            compensations = self._compensation_registry.get(transaction_id, []).copy()

        if not compensations:
            logger.debug(f"No compensating actions found for transaction {transaction_id}")
            return

        logger.info(f"Executing {len(compensations)} compensating actions for {transaction_id}")

        # Execute compensations in reverse order
        for i, compensation in enumerate(reversed(compensations)):
            try:
                await compensation()
                logger.debug(f"Compensation {i+1}/{len(compensations)} executed successfully")
            except Exception as e:
                logger.error(f"Compensation {i+1} failed: {e}")
                # Continue with other compensations

        # Clean up
        async with self._lock:
            self._compensation_registry.pop(transaction_id, None)

    def _create_dual_mode_compensation(self, operation_data: Dict[str, Any]) -> Callable:
        """Create compensation for dual-mode insert operation."""
        async def compensate():
            try:
                supabase = get_supabase()
                transaction_id = operation_data.get('transaction_id')

                if not transaction_id:
                    logger.warning("No transaction_id for compensation")
                    return

                # Remove records with this transaction_id
                history_result = supabase.table('parameter_value_history').delete().eq(
                    'transaction_id', transaction_id
                ).execute()

                process_result = supabase.table('process_data_points').delete().eq(
                    'transaction_id', transaction_id
                ).execute()

                logger.info(
                    f"Compensated transaction {transaction_id}: "
                    f"removed {len(history_result.data or [])} history records, "
                    f"{len(process_result.data or [])} process records"
                )

            except Exception as e:
                logger.error(f"Compensation failed for transaction {transaction_id}: {e}")
                raise

        return compensate

    def _get_circuit_breaker(self, operation_type: str) -> CircuitBreaker:
        """Get or create circuit breaker for operation type."""
        if operation_type not in self._circuit_breakers:
            self._circuit_breakers[operation_type] = CircuitBreaker()
        return self._circuit_breakers[operation_type]

    async def _cleanup_loop(self) -> None:
        """Background cleanup of old operations and expired data."""
        try:
            while self._is_running:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_operations()
                await self._cleanup_deduplication_cache()
        except asyncio.CancelledError:
            logger.info("Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_old_operations(self) -> None:
        """Clean up old completed or dead letter operations."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        operations_to_remove = []

        async with self._lock:
            for op_id, operation in self._operations.items():
                if (operation.status in [OperationStatus.COMPLETED, OperationStatus.DEAD_LETTER] and
                    operation.created_at < cutoff_time):
                    operations_to_remove.append(op_id)

            for op_id in operations_to_remove:
                del self._operations[op_id]

        if operations_to_remove:
            logger.debug(f"Cleaned up {len(operations_to_remove)} old operations")

    async def _cleanup_deduplication_cache(self) -> None:
        """Clean up old deduplication cache entries."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        keys_to_remove = []

        async with self._lock:
            for key, op_id in self._deduplication_cache.items():
                operation = self._operations.get(op_id)
                if (not operation or
                    (operation.created_at < cutoff_time and
                     operation.status == OperationStatus.COMPLETED)):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._deduplication_cache[key]

        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} deduplication cache entries")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the failure recovery system."""
        async with self._lock:
            operation_stats = {
                'total': len(self._operations),
                'pending': sum(1 for op in self._operations.values()
                              if op.status == OperationStatus.PENDING),
                'processing': sum(1 for op in self._operations.values()
                                 if op.status == OperationStatus.PROCESSING),
                'completed': sum(1 for op in self._operations.values()
                               if op.status == OperationStatus.COMPLETED),
                'failed': sum(1 for op in self._operations.values()
                             if op.status == OperationStatus.FAILED),
                'dead_letter': sum(1 for op in self._operations.values()
                                  if op.status == OperationStatus.DEAD_LETTER)
            }

            circuit_breaker_stats = {
                cb_type: {
                    'state': cb.state.value,
                    'failure_count': cb.failure_count,
                    'last_failure': cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for cb_type, cb in self._circuit_breakers.items()
            }

        return {
            'status': 'healthy',
            'is_running': self._is_running,
            'operations': operation_stats,
            'circuit_breakers': circuit_breaker_stats,
            'deduplication_cache_size': len(self._deduplication_cache),
            'compensation_registry_size': len(self._compensation_registry),
            'timestamp': get_current_timestamp()
        }

    async def repair_data_consistency(self, machine_id: str) -> Dict[str, Any]:
        """Repair data consistency issues for a machine."""
        logger.info(f"Starting data consistency repair for machine {machine_id}")
        repair_results = {
            'orphaned_process_records': 0,
            'missing_history_records': 0,
            'invalid_machine_states': 0,
            'repaired': False
        }

        try:
            supabase = get_supabase()

            # Find orphaned process_data_points (process doesn't exist)
            orphaned_query = """
                SELECT DISTINCT p.process_id
                FROM process_data_points p
                LEFT JOIN process_executions pe ON p.process_id = pe.id
                WHERE pe.id IS NULL
            """

            # Note: This would need to be implemented with proper Supabase RPC calls
            # For now, we'll implement basic consistency checks

            # Check for invalid machine states
            machine_result = supabase.table('machines').select(
                'status, current_process_id'
            ).eq('id', machine_id).single().execute()

            if machine_result.data:
                status = machine_result.data.get('status')
                process_id = machine_result.data.get('current_process_id')

                # Validate state consistency
                if status == 'processing' and not process_id:
                    # Fix: set status to idle
                    supabase.table('machines').update({
                        'status': 'idle',
                        'current_process_id': None,
                        'updated_at': get_current_timestamp()
                    }).eq('id', machine_id).execute()
                    repair_results['invalid_machine_states'] += 1
                    repair_results['repaired'] = True

                elif status == 'idle' and process_id:
                    # Fix: clear process_id
                    supabase.table('machines').update({
                        'current_process_id': None,
                        'updated_at': get_current_timestamp()
                    }).eq('id', machine_id).execute()
                    repair_results['invalid_machine_states'] += 1
                    repair_results['repaired'] = True

            logger.info(f"Data consistency repair completed for machine {machine_id}: {repair_results}")
            return repair_results

        except Exception as e:
            logger.error(f"Data consistency repair failed for machine {machine_id}: {e}")
            repair_results['error'] = str(e)
            return repair_results


# Global failure recovery instance
failure_recovery = ComprehensiveFailureRecovery()