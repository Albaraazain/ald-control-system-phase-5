"""
Integration adapter for transitioning from legacy continuous parameter logger
to the new transactional data access layer.

This adapter provides a drop-in replacement that maintains backward compatibility
while enabling the bulletproof transactional guarantees.
"""
import asyncio
from typing import Dict, Any, Optional
from src.log_setup import logger
from src.config import MACHINE_ID
from .transactional import transactional_logger
from .continuous_parameter_logger import ContinuousParameterLogger


class TransactionalParameterLoggerAdapter:
    """
    Adapter that bridges the legacy ContinuousParameterLogger interface
    with the new transactional data access layer.

    Provides:
    - Backward compatible API
    - Gradual migration capability
    - Feature flag support
    - Performance monitoring
    """

    def __init__(self, interval_seconds: float = 1.0, use_transactional: bool = True):
        """
        Initialize the adapter with fallback support.

        Args:
            interval_seconds: Time between readings (for legacy compatibility)
            use_transactional: Whether to use the new transactional layer
        """
        self.interval = interval_seconds
        self.is_running = False
        self.use_transactional = use_transactional
        self._task: Optional[asyncio.Task] = None
        self._error_count = 0
        self._max_consecutive_errors = 5
        self._last_successful_read = None

        # Initialize the appropriate backend
        if self.use_transactional:
            self._backend = None  # Will use transactional_logger directly
            logger.info("Initialized with transactional data access layer")
        else:
            self._backend = ContinuousParameterLogger(interval_seconds)
            logger.info("Initialized with legacy continuous parameter logger")

    async def start(self):
        """Start continuous parameter logging with transactional guarantees."""
        if self.is_running:
            logger.warning("Transactional parameter logger adapter is already running")
            return

        try:
            if self.use_transactional:
                # Initialize transactional logger
                await transactional_logger.initialize()

                # Start our own logging loop with transactional backend
                self.is_running = True
                self._error_count = 0
                self._task = asyncio.create_task(self._transactional_logging_loop())
                logger.info("Started transactional parameter logging service")
            else:
                # Delegate to legacy backend
                await self._backend.start()
                self.is_running = self._backend.is_running

        except Exception as e:
            logger.error(f"Failed to start parameter logging: {e}")
            self.is_running = False
            raise

    async def stop(self):
        """Stop the continuous parameter logging."""
        if not self.is_running:
            return

        try:
            if self.use_transactional:
                self.is_running = False
                if self._task:
                    self._task.cancel()
                    try:
                        await self._task
                    except asyncio.CancelledError:
                        pass
                    self._task = None

                # Cleanup transactional logger if needed
                await transactional_logger.cleanup()
                logger.info("Stopped transactional parameter logging service")
            else:
                await self._backend.stop()
                self.is_running = False

        except Exception as e:
            logger.error(f"Error stopping parameter logging: {e}")

    async def _transactional_logging_loop(self):
        """Internal loop using the new transactional data access layer."""
        try:
            while self.is_running:
                start_time = asyncio.get_event_loop().time()

                try:
                    # Use the transactional logger for atomic operations
                    await self._read_and_log_parameters_transactional()
                    self._error_count = 0  # Reset error count on success
                    self._last_successful_read = start_time

                except Exception as e:
                    self._error_count += 1
                    logger.error(
                        f"Error in transactional parameter logging (attempt {self._error_count}): {str(e)}",
                        exc_info=True
                    )

                    # If too many consecutive errors, pause longer
                    if self._error_count >= self._max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive errors ({self._error_count}), "
                            f"pausing for 30 seconds"
                        )
                        await asyncio.sleep(30)
                        self._error_count = 0  # Reset after pause

                # Calculate sleep time to maintain consistent interval
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.interval - elapsed)

                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("Transactional parameter logging loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in transactional parameter logging loop: {str(e)}", exc_info=True)
            self.is_running = False

    async def _read_and_log_parameters_transactional(self):
        """
        Read parameters and log using the transactional data access layer.

        This method eliminates race conditions and provides atomic guarantees.
        """
        from src.plc.manager import plc_manager

        try:
            # Check if PLC is connected
            if not plc_manager.is_connected():
                logger.debug("PLC not connected, skipping parameter reading")
                return

            # Read all parameters from PLC
            parameter_values = await plc_manager.read_all_parameters()
            if not parameter_values:
                logger.debug("No parameters read from PLC")
                return

            # Use the transactional logger for atomic dual-mode logging
            result = await transactional_logger.log_parameters_atomic(
                parameter_values, MACHINE_ID
            )

            if result.success:
                logger.debug(
                    f"Transactional logging completed: history={result.history_count}, "
                    f"process={result.process_count}, transaction_id={result.transaction_id}"
                )
            else:
                logger.error(f"Transactional logging failed: {result.error_message}")

        except Exception as e:
            logger.error(f"Failed to read and log parameters transactionally: {str(e)}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the parameter logger.

        Returns:
            Dict with status information
        """
        if self.use_transactional:
            # Get status from transactional logger
            base_status = {
                'is_running': self.is_running,
                'interval_seconds': self.interval,
                'error_count': self._error_count,
                'last_successful_read': self._last_successful_read,
                'backend': 'transactional',
                'use_transactional': True
            }

            try:
                # Add transactional logger health status
                health_status = asyncio.create_task(transactional_logger.get_health_status())
                # Note: In production, you might want to cache this or make it sync
                base_status['transactional_health'] = 'checking...'
            except Exception as e:
                base_status['transactional_health'] = f'error: {str(e)}'

            return base_status
        else:
            # Delegate to legacy backend
            status = self._backend.get_status()
            status['backend'] = 'legacy'
            status['use_transactional'] = False
            return status

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status including transactional layer."""
        if self.use_transactional:
            return await transactional_logger.get_health_status()
        else:
            return {
                'overall_status': 'healthy' if self.is_running else 'stopped',
                'backend': 'legacy',
                'adapter_status': self.get_status()
            }

    async def test_atomic_operation(self) -> Dict[str, Any]:
        """Test the atomic operation capability."""
        if self.use_transactional:
            return await transactional_logger.test_atomic_operation(MACHINE_ID)
        else:
            return {
                'test_successful': False,
                'error': 'Atomic operations not available in legacy mode'
            }

    def switch_to_transactional(self) -> bool:
        """
        Switch from legacy to transactional mode.

        Returns:
            bool: True if switch was successful
        """
        if self.use_transactional:
            logger.info("Already using transactional mode")
            return True

        try:
            # This would require restarting the service
            if self.is_running:
                logger.warning("Cannot switch mode while running. Stop service first.")
                return False

            self.use_transactional = True
            self._backend = None
            logger.info("Switched to transactional mode")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to transactional mode: {e}")
            return False

    def switch_to_legacy(self) -> bool:
        """
        Switch from transactional to legacy mode (emergency fallback).

        Returns:
            bool: True if switch was successful
        """
        if not self.use_transactional:
            logger.info("Already using legacy mode")
            return True

        try:
            # This would require restarting the service
            if self.is_running:
                logger.warning("Cannot switch mode while running. Stop service first.")
                return False

            self.use_transactional = False
            self._backend = ContinuousParameterLogger(self.interval)
            logger.warning("Switched to legacy mode (emergency fallback)")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to legacy mode: {e}")
            return False


# Global instance that can replace the existing continuous_parameter_logger
# This enables gradual migration with feature flags
transactional_parameter_logger_adapter = TransactionalParameterLoggerAdapter()