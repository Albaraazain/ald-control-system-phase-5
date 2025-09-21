"""
Main transactional parameter logger with atomic operations and failure recovery.

This module provides the primary interface for bulletproof parameter logging
with full ACID guarantees and sophisticated failure recovery mechanisms.
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.log_setup import logger
from src.db import get_current_timestamp
from src.config import MACHINE_ID

from .interfaces import (
    ITransactionalParameterLogger,
    ParameterData,
    DualModeResult
)
from .transaction_manager import transaction_manager
from .state_repository import state_repository
from .dual_mode_repository import dual_mode_repository


class TransactionalParameterLogger(ITransactionalParameterLogger):
    """
    Main transactional parameter logger with atomic operations.

    Provides:
    - Atomic state query + parameter logging
    - Full ACID transaction guarantees
    - Sophisticated failure recovery
    - Performance monitoring and health checks
    - Race condition elimination
    """

    def __init__(self):
        """Initialize the transactional parameter logger."""
        self._is_initialized = False
        self._health_status = {}
        self._performance_metrics = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'average_latency_ms': 0.0,
            'last_operation_time': None
        }

    async def initialize(self) -> None:
        """Initialize all components."""
        try:
            await transaction_manager.initialize()
            self._is_initialized = True
            logger.info("Transactional parameter logger initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize transactional parameter logger: {e}")
            raise

    async def log_parameters_atomic(
        self,
        parameters: Dict[str, Any],
        machine_id: str = MACHINE_ID
    ) -> DualModeResult:
        """
        Log parameters with full atomicity and consistency guarantees.

        This is the main entry point that coordinates:
        - Atomic state query
        - Parameter validation
        - Dual-mode logging decision
        - Transaction management
        - Failure recovery

        Args:
            parameters: Dictionary of parameter_id -> value mappings
            machine_id: Machine ID (defaults to configured MACHINE_ID)

        Returns:
            DualModeResult with operation details and success status
        """
        start_time = time.time()
        self._performance_metrics['total_operations'] += 1

        try:
            if not self._is_initialized:
                await self.initialize()

            # Convert parameters to ParameterData objects
            parameter_data = await self._prepare_parameter_data(parameters)

            if not parameter_data:
                logger.debug("No valid parameters to log")
                return DualModeResult(
                    history_count=0,
                    process_count=0,
                    machine_state=None,
                    transaction_id="empty",
                    success=True
                )

            # Core atomic operation
            result = await self._execute_atomic_logging(parameter_data, machine_id)

            # Update performance metrics
            latency_ms = (time.time() - start_time) * 1000
            await self._update_performance_metrics(latency_ms, result.success)

            if result.success:
                logger.debug(
                    f"Atomic logging completed: history={result.history_count}, "
                    f"process={result.process_count}, latency={latency_ms:.2f}ms"
                )
            else:
                logger.error(f"Atomic logging failed: {result.error_message}")

            return result

        except Exception as e:
            logger.error(f"Critical error in atomic parameter logging: {e}", exc_info=True)
            self._performance_metrics['failed_operations'] += 1

            # Return failure result
            return DualModeResult(
                history_count=0,
                process_count=0,
                machine_state=None,
                transaction_id="error",
                success=False,
                error_message=str(e)
            )

    async def _execute_atomic_logging(
        self,
        parameter_data: List[ParameterData],
        machine_id: str
    ) -> DualModeResult:
        """Execute the core atomic logging operation."""
        try:
            async with transaction_manager.begin_transaction() as tx:
                # Step 1: Get current machine state atomically
                machine_state = await state_repository.get_machine_state_with_validation(
                    machine_id, validate_process=True
                )

                logger.debug(
                    f"Machine state: status={machine_state.status}, "
                    f"process_id={machine_state.current_process_id}, "
                    f"is_processing={machine_state.is_processing}"
                )

                # Step 2: Execute atomic dual-mode insert
                result = await dual_mode_repository.insert_dual_mode_atomic(
                    parameter_data, machine_state
                )

                # Step 3: Validate result and commit or rollback
                if not result.success:
                    logger.error(f"Dual-mode insert failed: {result.error_message}")
                    # Transaction will auto-rollback on context exit
                    return result

                # Transaction will auto-commit on successful context exit
                return result

        except Exception as e:
            logger.error(f"Atomic logging transaction failed: {e}")
            raise

    async def _prepare_parameter_data(
        self,
        parameters: Dict[str, Any]
    ) -> List[ParameterData]:
        """Prepare and validate parameter data."""
        parameter_data = []
        timestamp = datetime.now(timezone.utc)

        for param_id, value in parameters.items():
            if value is None:
                logger.debug(f"Skipping parameter {param_id} with None value")
                continue

            # Create ParameterData object
            param_data = ParameterData(
                parameter_id=param_id,
                value=value,
                timestamp=timestamp
            )

            # Validate
            if param_data.validate():
                parameter_data.append(param_data)
            else:
                logger.warning(f"Invalid parameter data: {param_data}")

        return parameter_data

    async def _update_performance_metrics(
        self,
        latency_ms: float,
        success: bool
    ) -> None:
        """Update performance metrics."""
        try:
            if success:
                self._performance_metrics['successful_operations'] += 1

            # Update average latency (simple moving average)
            current_avg = self._performance_metrics['average_latency_ms']
            total_ops = self._performance_metrics['total_operations']

            if total_ops > 0:
                self._performance_metrics['average_latency_ms'] = (
                    (current_avg * (total_ops - 1) + latency_ms) / total_ops
                )

            self._performance_metrics['last_operation_time'] = get_current_timestamp()

        except Exception as e:
            logger.warning(f"Failed to update performance metrics: {e}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the transactional logging system."""
        try:
            # Get component health statuses
            tx_manager_health = await self._get_transaction_manager_health()
            state_repo_health = await state_repository.get_health_status()
            dual_mode_repo_health = await dual_mode_repository.get_health_status()

            # Calculate overall health
            all_healthy = all([
                tx_manager_health.get('status') == 'healthy',
                state_repo_health.get('status') == 'healthy',
                dual_mode_repo_health.get('status') == 'healthy'
            ])

            overall_status = 'healthy' if all_healthy else 'unhealthy'

            return {
                'overall_status': overall_status,
                'initialized': self._is_initialized,
                'components': {
                    'transaction_manager': tx_manager_health,
                    'state_repository': state_repo_health,
                    'dual_mode_repository': dual_mode_repo_health
                },
                'performance_metrics': self._performance_metrics.copy(),
                'timestamp': get_current_timestamp()
            }

        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {
                'overall_status': 'unhealthy',
                'error': str(e),
                'timestamp': get_current_timestamp()
            }

    async def _get_transaction_manager_health(self) -> Dict[str, Any]:
        """Get transaction manager health status."""
        try:
            active_transactions = await transaction_manager.get_active_transactions()

            return {
                'status': 'healthy',
                'active_transaction_count': len(active_transactions),
                'initialized': self._is_initialized
            }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    async def cleanup(self) -> None:
        """Cleanup resources and shutdown gracefully."""
        try:
            logger.info("Shutting down transactional parameter logger")

            # Cleanup transaction manager
            await transaction_manager.cleanup()

            self._is_initialized = False
            logger.info("Transactional parameter logger shutdown completed")

        except Exception as e:
            logger.error(f"Error during transactional logger cleanup: {e}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self._performance_metrics.copy()

    async def test_atomic_operation(self, machine_id: str = MACHINE_ID) -> Dict[str, Any]:
        """Test atomic operation with dummy data for validation."""
        try:
            test_parameters = {
                'test_param_1': 42.0,
                'test_param_2': 100,
                'test_param_3': True
            }

            result = await self.log_parameters_atomic(test_parameters, machine_id)

            return {
                'test_successful': result.success,
                'transaction_id': result.transaction_id,
                'history_count': result.history_count,
                'process_count': result.process_count,
                'error_message': result.error_message
            }

        except Exception as e:
            logger.error(f"Atomic operation test failed: {e}")
            return {
                'test_successful': False,
                'error': str(e)
            }


# Global transactional parameter logger instance
transactional_logger = TransactionalParameterLogger()