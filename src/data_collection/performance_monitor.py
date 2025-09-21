# File: data_collection/performance_monitor.py
"""
Real-time performance monitoring and optimization framework for continuous parameter logging.

This module provides:
- Real-time performance metrics collection and analysis
- Automatic performance optimization and tuning
- Alerting and notification system for performance degradation
- Historical performance analysis and trending
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics
import json
from src.log_setup import logger


@dataclass
class PerformanceAlert:
    """Performance alert definition."""
    name: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    metric_name: str
    threshold_value: float
    current_value: float
    timestamp: datetime
    resolution_suggestions: List[str] = field(default_factory=list)


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str  # 'gt', 'lt', 'eq'
    enabled: bool = True


class PerformanceOptimizer:
    """Automatic performance optimization engine."""

    def __init__(self):
        self.optimization_history: List[Dict] = []
        self.current_optimizations: Dict[str, Any] = {}

    async def analyze_and_optimize(self, metrics: Dict[str, Any]) -> List[str]:
        """
        Analyze performance metrics and apply automatic optimizations.

        Args:
            metrics: Current performance metrics

        Returns:
            List of optimization actions taken
        """
        actions_taken = []

        # Analyze PLC read performance
        plc_optimization = await self._optimize_plc_performance(metrics)
        if plc_optimization:
            actions_taken.extend(plc_optimization)

        # Analyze database performance
        db_optimization = await self._optimize_database_performance(metrics)
        if db_optimization:
            actions_taken.extend(db_optimization)

        # Analyze worker pool efficiency
        worker_optimization = await self._optimize_worker_pools(metrics)
        if worker_optimization:
            actions_taken.extend(worker_optimization)

        # Log optimization actions
        if actions_taken:
            logger.info(f"Performance optimization actions taken: {actions_taken}")
            self.optimization_history.append({
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'actions': actions_taken
            })

        return actions_taken

    async def _optimize_plc_performance(self, metrics: Dict) -> List[str]:
        """Optimize PLC read performance based on metrics."""
        actions = []
        recent_perf = metrics.get('recent_performance', {})
        plc_times = recent_perf.get('plc_read_time_ms', {})

        avg_plc_time = plc_times.get('avg', 0)
        p95_plc_time = plc_times.get('p95', 0)

        # If PLC reads are consistently slow, suggest grouping optimization
        if avg_plc_time > 500:  # More than 500ms average
            actions.append("PLC reads are slow - consider implementing address range grouping")

        # If there's high variance in PLC read times, suggest connection optimization
        if p95_plc_time > avg_plc_time * 2:
            actions.append("High PLC read time variance - consider connection pooling optimization")

        return actions

    async def _optimize_database_performance(self, metrics: Dict) -> List[str]:
        """Optimize database performance based on metrics."""
        actions = []
        recent_perf = metrics.get('recent_performance', {})
        db_times = recent_perf.get('database_write_time_ms', {})

        avg_db_time = db_times.get('avg', 0)
        p95_db_time = db_times.get('p95', 0)

        # If database writes are slow, suggest batch size optimization
        if avg_db_time > 100:  # More than 100ms average
            actions.append("Database writes are slow - consider increasing batch sizes")

        # If high database variance, suggest connection pooling
        if p95_db_time > avg_db_time * 2:
            actions.append("High database write time variance - implement connection pooling")

        return actions

    async def _optimize_worker_pools(self, metrics: Dict) -> List[str]:
        """Optimize worker pool configuration based on metrics."""
        actions = []
        recent_perf = metrics.get('recent_performance', {})
        total_times = recent_perf.get('total_cycle_time_ms', {})

        avg_total_time = total_times.get('avg', 0)
        max_workers = metrics.get('max_workers', 4)

        # If total cycle time is high and we have few workers, suggest increasing workers
        if avg_total_time > 800 and max_workers < 8:  # More than 800ms with few workers
            actions.append(f"High cycle time with {max_workers} workers - consider increasing to {max_workers * 2}")

        return actions


class PerformanceMonitor:
    """
    Real-time performance monitoring system for continuous parameter logging.

    Provides comprehensive monitoring, alerting, and optimization capabilities.
    """

    def __init__(self):
        self.is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._alert_callbacks: List[Callable[[PerformanceAlert], None]] = []
        self._optimizer = PerformanceOptimizer()

        # Performance thresholds
        self._thresholds = self._initialize_default_thresholds()

        # Alert history
        self._alert_history: List[PerformanceAlert] = []
        self._max_alert_history = 1000

        # Performance trends
        self._performance_history: List[Dict] = []
        self._max_history_entries = 1440  # 24 hours at 1-minute intervals

    def _initialize_default_thresholds(self) -> List[PerformanceThreshold]:
        """Initialize default performance thresholds."""
        return [
            # Timing thresholds
            PerformanceThreshold("plc_read_time_ms.avg", 200.0, 500.0, "gt"),
            PerformanceThreshold("database_write_time_ms.avg", 100.0, 300.0, "gt"),
            PerformanceThreshold("total_cycle_time_ms.avg", 800.0, 950.0, "gt"),
            PerformanceThreshold("jitter_ms.avg", 10.0, 50.0, "gt"),

            # P95 thresholds for tail latency
            PerformanceThreshold("plc_read_time_ms.p95", 500.0, 1000.0, "gt"),
            PerformanceThreshold("database_write_time_ms.p95", 200.0, 500.0, "gt"),
            PerformanceThreshold("total_cycle_time_ms.p95", 950.0, 1000.0, "gt"),
            PerformanceThreshold("jitter_ms.p95", 50.0, 100.0, "gt"),

            # Throughput thresholds
            PerformanceThreshold("parameters_processed.avg", 50, 10, "lt"),

            # Error thresholds
            PerformanceThreshold("error_count", 0, 3, "gt"),
        ]

    async def start_monitoring(self, target_logger, monitor_interval: float = 60.0):
        """
        Start performance monitoring.

        Args:
            target_logger: The logger instance to monitor
            monitor_interval: Monitoring interval in seconds
        """
        if self.is_monitoring:
            logger.warning("Performance monitoring is already running")
            return

        self.is_monitoring = True
        self.target_logger = target_logger
        self.monitor_interval = monitor_interval

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Started performance monitoring with {monitor_interval}s interval")

    async def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        logger.info("Stopped performance monitoring")

    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """Add a callback function to be called when alerts are triggered."""
        self._alert_callbacks.append(callback)

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        try:
            while self.is_monitoring:
                try:
                    # Get current performance metrics
                    metrics = self.target_logger.get_performance_stats()

                    # Store performance history
                    self._store_performance_history(metrics)

                    # Check for performance alerts
                    alerts = self._check_performance_thresholds(metrics)

                    # Process alerts
                    for alert in alerts:
                        await self._process_alert(alert)

                    # Run automatic optimization
                    optimizations = await self._optimizer.analyze_and_optimize(metrics)

                    # Log monitoring summary
                    if alerts or optimizations:
                        logger.info(
                            f"Performance monitoring: {len(alerts)} alerts, "
                            f"{len(optimizations)} optimizations applied"
                        )

                except Exception as e:
                    logger.error(f"Error in performance monitoring loop: {e}", exc_info=True)

                # Wait for next monitoring cycle
                await asyncio.sleep(self.monitor_interval)

        except asyncio.CancelledError:
            logger.info("Performance monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in performance monitoring loop: {e}", exc_info=True)
            self.is_monitoring = False

    def _store_performance_history(self, metrics: Dict):
        """Store performance metrics in history."""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics
        }

        self._performance_history.append(history_entry)

        # Keep only recent history
        if len(self._performance_history) > self._max_history_entries:
            self._performance_history = self._performance_history[-self._max_history_entries:]

    def _check_performance_thresholds(self, metrics: Dict) -> List[PerformanceAlert]:
        """Check performance metrics against defined thresholds."""
        alerts = []

        for threshold in self._thresholds:
            if not threshold.enabled:
                continue

            # Extract metric value using dot notation
            metric_value = self._get_nested_metric_value(metrics, threshold.metric_name)
            if metric_value is None:
                continue

            # Check threshold conditions
            alert = self._evaluate_threshold(threshold, metric_value)
            if alert:
                alerts.append(alert)

        return alerts

    def _get_nested_metric_value(self, metrics: Dict, metric_path: str) -> Optional[float]:
        """Extract nested metric value using dot notation."""
        try:
            keys = metric_path.split('.')
            value = metrics

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None

            return float(value) if value is not None else None

        except (ValueError, TypeError):
            return None

    def _evaluate_threshold(self, threshold: PerformanceThreshold, value: float) -> Optional[PerformanceAlert]:
        """Evaluate a single threshold condition."""
        violated = False
        severity = "low"

        if threshold.comparison == "gt":
            if value > threshold.critical_threshold:
                violated = True
                severity = "critical"
            elif value > threshold.warning_threshold:
                violated = True
                severity = "warning"
        elif threshold.comparison == "lt":
            if value < threshold.critical_threshold:
                violated = True
                severity = "critical"
            elif value < threshold.warning_threshold:
                violated = True
                severity = "warning"
        elif threshold.comparison == "eq":
            if abs(value - threshold.critical_threshold) < 0.001:
                violated = True
                severity = "critical"
            elif abs(value - threshold.warning_threshold) < 0.001:
                violated = True
                severity = "warning"

        if violated:
            # Generate resolution suggestions
            suggestions = self._generate_resolution_suggestions(threshold.metric_name, value, severity)

            return PerformanceAlert(
                name=f"{threshold.metric_name}_threshold_violation",
                severity=severity,
                message=f"{threshold.metric_name} is {value}, exceeds {severity} threshold",
                metric_name=threshold.metric_name,
                threshold_value=threshold.critical_threshold if severity == "critical" else threshold.warning_threshold,
                current_value=value,
                timestamp=datetime.now(),
                resolution_suggestions=suggestions
            )

        return None

    def _generate_resolution_suggestions(self, metric_name: str, value: float, severity: str) -> List[str]:
        """Generate resolution suggestions for specific performance issues."""
        suggestions = []

        if "plc_read_time" in metric_name:
            suggestions.extend([
                "Check PLC network connectivity and latency",
                "Implement bulk parameter reading with address range optimization",
                "Consider increasing PLC connection timeout values",
                "Review parameter grouping strategy for efficiency"
            ])

        elif "database_write_time" in metric_name:
            suggestions.extend([
                "Implement async database connection pooling",
                "Increase database batch sizes for bulk operations",
                "Check database server performance and connectivity",
                "Consider using prepared statements for repeated queries"
            ])

        elif "jitter" in metric_name:
            suggestions.extend([
                "Review system CPU and memory usage",
                "Check for competing processes affecting timing",
                "Consider increasing worker pool size for concurrent processing",
                "Optimize async task scheduling and priorities"
            ])

        elif "parameters_processed" in metric_name:
            suggestions.extend([
                "Check PLC connectivity and parameter configuration",
                "Review parameter filtering and caching strategies",
                "Verify parameter metadata cache is up to date",
                "Check for parameter reading errors in logs"
            ])

        return suggestions

    async def _process_alert(self, alert: PerformanceAlert):
        """Process a performance alert."""
        # Add to alert history
        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_alert_history:
            self._alert_history = self._alert_history[-self._max_alert_history:]

        # Log the alert
        logger.warning(
            f"Performance Alert [{alert.severity.upper()}]: {alert.message} "
            f"(current: {alert.current_value}, threshold: {alert.threshold_value})"
        )

        if alert.resolution_suggestions:
            logger.info(f"Resolution suggestions: {', '.join(alert.resolution_suggestions)}")

        # Call registered alert callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status and statistics."""
        recent_alerts = [
            alert for alert in self._alert_history
            if alert.timestamp > datetime.now() - timedelta(hours=1)
        ]

        return {
            'is_monitoring': self.is_monitoring,
            'monitor_interval': getattr(self, 'monitor_interval', 60.0),
            'active_thresholds': len([t for t in self._thresholds if t.enabled]),
            'total_thresholds': len(self._thresholds),
            'alert_callbacks': len(self._alert_callbacks),
            'recent_alerts': {
                'total': len(recent_alerts),
                'by_severity': {
                    severity: len([a for a in recent_alerts if a.severity == severity])
                    for severity in ['low', 'warning', 'critical']
                }
            },
            'performance_history_size': len(self._performance_history),
            'optimization_history_size': len(self._optimizer.optimization_history)
        }

    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Filter recent history
        recent_history = [
            entry for entry in self._performance_history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_time
        ]

        if not recent_history:
            return {'message': 'No performance history available'}

        # Extract trend data
        trends = {}
        metric_paths = [
            'recent_performance.plc_read_time_ms.avg',
            'recent_performance.database_write_time_ms.avg',
            'recent_performance.total_cycle_time_ms.avg',
            'recent_performance.jitter_ms.avg',
            'recent_performance.parameters_processed.avg'
        ]

        for metric_path in metric_paths:
            values = []
            timestamps = []

            for entry in recent_history:
                value = self._get_nested_metric_value(entry['metrics'], metric_path)
                if value is not None:
                    values.append(value)
                    timestamps.append(entry['timestamp'])

            if values:
                trends[metric_path] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'avg': statistics.mean(values),
                    'latest': values[-1],
                    'trend': 'improving' if values[-1] < statistics.mean(values[:len(values)//2]) else 'degrading' if len(values) > 10 else 'stable'
                }

        return trends


# Global performance monitor instance
performance_monitor = PerformanceMonitor()