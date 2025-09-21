"""
Integration Adapter for High-Performance Parameter Logging.

This module provides backward compatibility adapters and integration patterns
for migrating from the current parameter logging system to the high-performance
async pipeline while maintaining zero-downtime operation.
"""
import asyncio
from typing import Dict, Any, Optional
from src.log_setup import logger
from src.performance import (
    HighPerformanceParameterLogger,
    get_async_database_pool,
    close_global_pool
)


class ParameterLoggerAdapter:
    """
    Adapter that provides backward compatibility while enabling high-performance pipeline.

    This adapter can be used as a drop-in replacement for ContinuousParameterLogger
    during the migration period, providing both the existing interface and new
    high-performance capabilities.
    """

    def __init__(self, interval_seconds: float = 1.0, use_high_performance: bool = False):
        """
        Initialize parameter logger adapter.

        Args:
            interval_seconds: Logging interval in seconds
            use_high_performance: Whether to use high-performance pipeline
        """
        self.interval = interval_seconds
        self.use_high_performance = use_high_performance
        self.is_running = False

        # Legacy logger (existing implementation)
        self._legacy_logger = None

        # High-performance logger
        self._hp_logger = None
        self._db_pool = None

        # Adapter state
        self._task = None
        self._initialization_complete = False

    async def start(self):
        """Start parameter logging using appropriate implementation."""
        if self.is_running:
            logger.warning("Parameter logger adapter is already running")
            return

        logger.info(f"Starting parameter logger adapter (high_performance={self.use_high_performance})")

        if self.use_high_performance:
            await self._start_high_performance()
        else:
            await self._start_legacy()

        self.is_running = True
        logger.info("Parameter logger adapter started")

    async def stop(self):
        """Stop parameter logging."""
        if not self.is_running:
            return

        logger.info("Stopping parameter logger adapter")

        if self._hp_logger:
            await self._hp_logger.stop()

        if self._legacy_logger:
            await self._legacy_logger.stop()

        if self._db_pool:
            await close_global_pool()

        self.is_running = False
        logger.info("Parameter logger adapter stopped")

    async def _start_high_performance(self):
        """Start high-performance parameter logging pipeline."""
        try:
            # Initialize database pool
            self._db_pool = await get_async_database_pool()

            # Get PLC manager (assumes global singleton pattern for compatibility)
            from src.plc.manager import plc_manager

            # Initialize high-performance logger
            self._hp_logger = HighPerformanceParameterLogger(
                plc_manager=plc_manager,
                db_pool=self._db_pool,
                interval_seconds=self.interval,
                batch_size=200,
                max_workers=4
            )

            await self._hp_logger.start()

        except Exception as e:
            logger.error(f"Failed to start high-performance logger: {e}")
            # Fallback to legacy implementation
            logger.info("Falling back to legacy parameter logger")
            await self._start_legacy()

    async def _start_legacy(self):
        """Start legacy parameter logging implementation."""
        try:
            # Import and use existing implementation
            from src.data_collection.continuous_parameter_logger import continuous_parameter_logger

            self._legacy_logger = continuous_parameter_logger
            await self._legacy_logger.start()

        except Exception as e:
            logger.error(f"Failed to start legacy logger: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the parameter logger."""
        if self._hp_logger:
            status = self._hp_logger.get_status()
            status['implementation'] = 'high_performance'
            return status

        elif self._legacy_logger:
            status = self._legacy_logger.get_status()
            status['implementation'] = 'legacy'
            return status

        else:
            return {
                'is_running': self.is_running,
                'implementation': 'none',
                'interval_seconds': self.interval
            }

    async def switch_to_high_performance(self) -> bool:
        """
        Switch from legacy to high-performance implementation at runtime.

        This enables zero-downtime migration during operation.

        Returns:
            True if switch successful, False otherwise
        """
        if self.use_high_performance:
            logger.info("Already using high-performance implementation")
            return True

        if not self.is_running:
            logger.error("Cannot switch implementation while not running")
            return False

        logger.info("Switching to high-performance parameter logging")

        try:
            # Stop legacy logger
            if self._legacy_logger:
                await self._legacy_logger.stop()
                self._legacy_logger = None

            # Start high-performance logger
            await self._start_high_performance()

            self.use_high_performance = True
            logger.info("Successfully switched to high-performance implementation")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to high-performance implementation: {e}")

            # Attempt to restart legacy logger
            try:
                await self._start_legacy()
                logger.info("Reverted to legacy implementation")
            except Exception as fallback_error:
                logger.error(f"Failed to revert to legacy implementation: {fallback_error}")
                self.is_running = False

            return False

    async def switch_to_legacy(self) -> bool:
        """
        Switch from high-performance to legacy implementation at runtime.

        Returns:
            True if switch successful, False otherwise
        """
        if not self.use_high_performance:
            logger.info("Already using legacy implementation")
            return True

        if not self.is_running:
            logger.error("Cannot switch implementation while not running")
            return False

        logger.info("Switching to legacy parameter logging")

        try:
            # Stop high-performance logger
            if self._hp_logger:
                await self._hp_logger.stop()
                self._hp_logger = None

            if self._db_pool:
                await close_global_pool()
                self._db_pool = None

            # Start legacy logger
            await self._start_legacy()

            self.use_high_performance = False
            logger.info("Successfully switched to legacy implementation")
            return True

        except Exception as e:
            logger.error(f"Failed to switch to legacy implementation: {e}")
            self.is_running = False
            return False


class PerformanceMonitoringService:
    """
    Service for monitoring parameter logging performance and health.

    Provides real-time monitoring, alerting, and performance analysis
    for both legacy and high-performance implementations.
    """

    def __init__(self, adapter: ParameterLoggerAdapter):
        """
        Initialize performance monitoring service.

        Args:
            adapter: Parameter logger adapter to monitor
        """
        self.adapter = adapter
        self.is_monitoring = False
        self._monitoring_task = None
        self._performance_history = []
        self._alert_thresholds = {
            'max_jitter_ms': 100.0,
            'max_cycle_time': 2.0,
            'min_success_rate': 0.95
        }

    async def start_monitoring(self, interval_seconds: float = 10.0):
        """
        Start performance monitoring.

        Args:
            interval_seconds: Monitoring interval
        """
        if self.is_monitoring:
            logger.warning("Performance monitoring already running")
            return

        logger.info("Starting performance monitoring service")
        self.is_monitoring = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )

    async def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.is_monitoring:
            return

        logger.info("Stopping performance monitoring service")
        self.is_monitoring = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self, interval: float):
        """Main monitoring loop."""
        try:
            while self.is_monitoring:
                await self._collect_and_analyze_performance()
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Performance monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in performance monitoring loop: {e}")

    async def _collect_and_analyze_performance(self):
        """Collect and analyze performance metrics."""
        try:
            status = self.adapter.get_status()

            # Extract performance metrics
            performance_data = {
                'timestamp': asyncio.get_event_loop().time(),
                'implementation': status.get('implementation', 'unknown'),
                'is_running': status.get('is_running', False),
                'cycle_count': status.get('cycle_count', 0),
                'error_count': status.get('error_count', 0)
            }

            # Add high-performance specific metrics
            if 'performance' in status:
                perf = status['performance']
                performance_data.update({
                    'avg_jitter_ms': perf.get('avg_jitter_ms', 0.0),
                    'max_jitter_ms': perf.get('max_jitter_ms', 0.0),
                    'avg_cycle_time': perf.get('avg_cycle_time', 0.0),
                    'error_rate': perf.get('error_rate', 0.0)
                })

            # Store performance history
            self._performance_history.append(performance_data)

            # Keep only recent history (last 100 samples)
            if len(self._performance_history) > 100:
                self._performance_history.pop(0)

            # Check for performance issues
            await self._check_performance_alerts(performance_data)

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")

    async def _check_performance_alerts(self, performance_data: Dict[str, Any]):
        """Check performance data against alert thresholds."""
        alerts = []

        # Check jitter
        max_jitter = performance_data.get('max_jitter_ms', 0.0)
        if max_jitter > self._alert_thresholds['max_jitter_ms']:
            alerts.append(f"High jitter detected: {max_jitter:.1f}ms")

        # Check cycle time
        avg_cycle_time = performance_data.get('avg_cycle_time', 0.0)
        if avg_cycle_time > self._alert_thresholds['max_cycle_time']:
            alerts.append(f"Slow cycle time: {avg_cycle_time:.3f}s")

        # Check success rate
        error_rate = performance_data.get('error_rate', 0.0)
        success_rate = 1.0 - error_rate
        if success_rate < self._alert_thresholds['min_success_rate']:
            alerts.append(f"Low success rate: {success_rate:.1%}")

        # Log alerts
        for alert in alerts:
            logger.warning(f"Performance Alert: {alert}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        if not self._performance_history:
            return {}

        recent_data = self._performance_history[-10:]  # Last 10 samples

        return {
            'samples_collected': len(self._performance_history),
            'current_implementation': recent_data[-1].get('implementation', 'unknown'),
            'avg_jitter_ms': sum(d.get('avg_jitter_ms', 0) for d in recent_data) / len(recent_data),
            'avg_cycle_time': sum(d.get('avg_cycle_time', 0) for d in recent_data) / len(recent_data),
            'avg_error_rate': sum(d.get('error_rate', 0) for d in recent_data) / len(recent_data),
            'alert_thresholds': self._alert_thresholds.copy()
        }


# Global adapter instance for backward compatibility
_global_adapter = None


def get_parameter_logger_adapter(use_high_performance: bool = False) -> ParameterLoggerAdapter:
    """
    Get global parameter logger adapter.

    This provides a migration-friendly way to access parameter logging
    functionality while supporting both legacy and high-performance modes.

    Args:
        use_high_performance: Whether to use high-performance implementation

    Returns:
        ParameterLoggerAdapter instance
    """
    global _global_adapter

    if _global_adapter is None:
        _global_adapter = ParameterLoggerAdapter(use_high_performance=use_high_performance)

    return _global_adapter


async def shutdown_global_adapter():
    """Shutdown the global parameter logger adapter."""
    global _global_adapter

    if _global_adapter:
        await _global_adapter.stop()
        _global_adapter = None