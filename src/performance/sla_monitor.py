"""
Performance SLA monitoring and alerting system for strict timing requirements.

This module provides comprehensive monitoring of performance Service Level Agreements (SLAs)
for the ALD control system, with particular focus on the critical 1-second parameter logging interval.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import statistics
from src.log_setup import logger


@dataclass
class SLAThreshold:
    """Definition of an SLA performance threshold."""
    name: str
    description: str
    target_value: float
    warning_threshold: float
    critical_threshold: float
    unit: str
    measurement_type: str  # "latency", "throughput", "availability", "jitter"
    evaluation_window_seconds: float = 60.0
    enabled: bool = True


@dataclass
class SLAViolation:
    """Record of an SLA violation."""
    threshold_name: str
    violation_type: str  # "warning", "critical"
    measured_value: float
    threshold_value: float
    timestamp: datetime
    duration_seconds: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAMetrics:
    """Current SLA metrics and status."""
    threshold_name: str
    current_value: float
    target_value: float
    compliance_percentage: float
    violations_last_hour: int
    violations_last_24h: int
    last_violation: Optional[datetime] = None
    trend: str = "stable"  # "improving", "degrading", "stable"


class PerformanceSLAMonitor:
    """
    Performance SLA monitoring system for critical timing requirements.

    Features:
    - Real-time SLA compliance monitoring
    - Automated alerting for violations
    - Performance trend analysis
    - Detailed violation tracking and reporting
    - Configurable thresholds and evaluation windows
    - Integration with external monitoring systems
    """

    def __init__(self):
        self.thresholds = self._initialize_default_thresholds()
        self.measurements: Dict[str, deque] = {}  # threshold_name -> deque of (timestamp, value)
        self.violations: List[SLAViolation] = []
        self.alert_callbacks: List[Callable] = []

        # Monitoring state
        self.is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = 1.0  # Check every second for critical SLAs

        # Performance optimization
        self.max_measurements_per_threshold = 3600  # 1 hour of 1-second measurements
        self.violation_history_limit = 1000

        # SLA compliance tracking
        self.compliance_window_hours = 24
        self.availability_targets = {}  # threshold_name -> target percentage

    def _initialize_default_thresholds(self) -> Dict[str, SLAThreshold]:
        """Initialize default SLA thresholds for ALD control system."""
        return {
            "parameter_logging_interval": SLAThreshold(
                name="parameter_logging_interval",
                description="Parameter logging must occur every 1 second",
                target_value=1000.0,  # 1000ms = 1 second
                warning_threshold=1050.0,  # 5% tolerance
                critical_threshold=1100.0,  # 10% tolerance
                unit="milliseconds",
                measurement_type="latency",
                evaluation_window_seconds=60.0
            ),
            "parameter_logging_jitter": SLAThreshold(
                name="parameter_logging_jitter",
                description="Parameter logging jitter must be <10ms",
                target_value=10.0,
                warning_threshold=15.0,
                critical_threshold=25.0,
                unit="milliseconds",
                measurement_type="jitter",
                evaluation_window_seconds=60.0
            ),
            "bulk_read_latency": SLAThreshold(
                name="bulk_read_latency",
                description="Bulk PLC reads must complete in <200ms",
                target_value=200.0,
                warning_threshold=250.0,
                critical_threshold=300.0,
                unit="milliseconds",
                measurement_type="latency",
                evaluation_window_seconds=60.0
            ),
            "database_batch_latency": SLAThreshold(
                name="database_batch_latency",
                description="Database batch operations must complete in <100ms",
                target_value=100.0,
                warning_threshold=150.0,
                critical_threshold=200.0,
                unit="milliseconds",
                measurement_type="latency",
                evaluation_window_seconds=60.0
            ),
            "end_to_end_cycle_time": SLAThreshold(
                name="end_to_end_cycle_time",
                description="Complete logging cycle must finish in <800ms",
                target_value=800.0,
                warning_threshold=900.0,
                critical_threshold=1000.0,
                unit="milliseconds",
                measurement_type="latency",
                evaluation_window_seconds=60.0
            ),
            "parameter_throughput": SLAThreshold(
                name="parameter_throughput",
                description="System must process 100+ parameters per second",
                target_value=100.0,
                warning_threshold=80.0,
                critical_threshold=50.0,
                unit="parameters/second",
                measurement_type="throughput",
                evaluation_window_seconds=60.0
            ),
            "system_availability": SLAThreshold(
                name="system_availability",
                description="System must be available 99.9% of the time",
                target_value=99.9,
                warning_threshold=99.5,
                critical_threshold=99.0,
                unit="percentage",
                measurement_type="availability",
                evaluation_window_seconds=3600.0  # 1 hour window
            )
        }

    async def start_monitoring(self):
        """Start SLA monitoring."""
        if self.is_monitoring:
            logger.warning("SLA monitoring is already running")
            return

        self.is_monitoring = True

        # Initialize measurement queues
        for threshold_name in self.thresholds:
            self.measurements[threshold_name] = deque(maxlen=self.max_measurements_per_threshold)

        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("Performance SLA monitoring started")

    async def stop_monitoring(self):
        """Stop SLA monitoring."""
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

        logger.info("Performance SLA monitoring stopped")

    def add_alert_callback(self, callback: Callable[[SLAViolation], None]):
        """Add callback function for SLA violations."""
        self.alert_callbacks.append(callback)

    async def record_measurement(self, threshold_name: str, value: float, context: Optional[Dict] = None):
        """
        Record a performance measurement for SLA evaluation.

        Args:
            threshold_name: Name of the SLA threshold to check
            value: Measured value
            context: Optional context information
        """
        if threshold_name not in self.thresholds:
            logger.warning(f"Unknown SLA threshold: {threshold_name}")
            return

        current_time = time.time()

        # Add measurement to queue
        if threshold_name not in self.measurements:
            self.measurements[threshold_name] = deque(maxlen=self.max_measurements_per_threshold)

        self.measurements[threshold_name].append((current_time, value))

        # Check for immediate violations (real-time)
        await self._check_threshold_violation(threshold_name, value, context or {})

    async def _monitoring_loop(self):
        """Main monitoring loop for SLA compliance."""
        while self.is_monitoring:
            try:
                # Evaluate all thresholds
                for threshold_name in self.thresholds:
                    await self._evaluate_threshold_compliance(threshold_name)

                # Clean up old violations
                self._cleanup_old_violations()

                await asyncio.sleep(self.monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SLA monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(self.monitoring_interval)

    async def _check_threshold_violation(self, threshold_name: str, value: float, context: Dict):
        """Check if a single measurement violates SLA thresholds."""
        threshold = self.thresholds[threshold_name]

        if not threshold.enabled:
            return

        violation_type = None
        threshold_value = None

        # Determine violation type based on measurement type
        if threshold.measurement_type in ["latency", "jitter"]:
            # Higher values are worse
            if value > threshold.critical_threshold:
                violation_type = "critical"
                threshold_value = threshold.critical_threshold
            elif value > threshold.warning_threshold:
                violation_type = "warning"
                threshold_value = threshold.warning_threshold

        elif threshold.measurement_type == "throughput":
            # Lower values are worse
            if value < threshold.critical_threshold:
                violation_type = "critical"
                threshold_value = threshold.critical_threshold
            elif value < threshold.warning_threshold:
                violation_type = "warning"
                threshold_value = threshold.warning_threshold

        elif threshold.measurement_type == "availability":
            # Lower percentages are worse
            if value < threshold.critical_threshold:
                violation_type = "critical"
                threshold_value = threshold.critical_threshold
            elif value < threshold.warning_threshold:
                violation_type = "warning"
                threshold_value = threshold.warning_threshold

        if violation_type:
            await self._record_violation(threshold_name, violation_type, value, threshold_value, context)

    async def _record_violation(
        self,
        threshold_name: str,
        violation_type: str,
        measured_value: float,
        threshold_value: float,
        context: Dict
    ):
        """Record an SLA violation and trigger alerts."""
        violation = SLAViolation(
            threshold_name=threshold_name,
            violation_type=violation_type,
            measured_value=measured_value,
            threshold_value=threshold_value,
            timestamp=datetime.now(),
            context=context
        )

        self.violations.append(violation)

        # Limit violation history
        if len(self.violations) > self.violation_history_limit:
            self.violations = self.violations[-self.violation_history_limit:]

        # Log violation
        logger.warning(
            f"SLA VIOLATION [{violation_type.upper()}]: {threshold_name} = {measured_value:.2f} "
            f"(threshold: {threshold_value:.2f})"
        )

        # Trigger alert callbacks
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(violation)
                else:
                    callback(violation)
            except Exception as e:
                logger.error(f"Error in SLA alert callback: {e}")

    async def _evaluate_threshold_compliance(self, threshold_name: str):
        """Evaluate SLA compliance for a threshold over its evaluation window."""
        if threshold_name not in self.measurements:
            return

        threshold = self.thresholds[threshold_name]
        measurements = self.measurements[threshold_name]

        if not measurements:
            return

        current_time = time.time()
        window_start = current_time - threshold.evaluation_window_seconds

        # Filter measurements within evaluation window
        recent_measurements = [
            (timestamp, value) for timestamp, value in measurements
            if timestamp >= window_start
        ]

        if not recent_measurements:
            return

        values = [value for _, value in recent_measurements]

        # Calculate compliance metrics based on measurement type
        if threshold.measurement_type in ["latency", "jitter"]:
            # For latency/jitter, calculate percentage of measurements within target
            compliant_count = sum(1 for value in values if value <= threshold.target_value)
            compliance_percentage = (compliant_count / len(values)) * 100

        elif threshold.measurement_type == "throughput":
            # For throughput, calculate percentage of measurements meeting target
            compliant_count = sum(1 for value in values if value >= threshold.target_value)
            compliance_percentage = (compliant_count / len(values)) * 100

        elif threshold.measurement_type == "availability":
            # For availability, calculate average percentage
            compliance_percentage = statistics.mean(values)

        else:
            compliance_percentage = 100.0  # Default for unknown types

        # Store availability targets for reporting
        self.availability_targets[threshold_name] = compliance_percentage

    def _cleanup_old_violations(self):
        """Clean up old violation records."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.violations = [
            violation for violation in self.violations
            if violation.timestamp > cutoff_time
        ]

    def get_sla_metrics(self, threshold_name: str) -> Optional[SLAMetrics]:
        """
        Get current SLA metrics for a specific threshold.

        Args:
            threshold_name: Name of the threshold

        Returns:
            SLAMetrics object or None if threshold not found
        """
        if threshold_name not in self.thresholds:
            return None

        threshold = self.thresholds[threshold_name]
        measurements = self.measurements.get(threshold_name, deque())

        if not measurements:
            return SLAMetrics(
                threshold_name=threshold_name,
                current_value=0.0,
                target_value=threshold.target_value,
                compliance_percentage=100.0,
                violations_last_hour=0,
                violations_last_24h=0
            )

        # Get recent measurements
        current_time = time.time()
        recent_values = [
            value for timestamp, value in measurements
            if current_time - timestamp <= 300  # Last 5 minutes
        ]

        current_value = statistics.mean(recent_values) if recent_values else 0.0

        # Count violations
        current_time_dt = datetime.now()
        violations_1h = len([
            v for v in self.violations
            if v.threshold_name == threshold_name and
            current_time_dt - v.timestamp <= timedelta(hours=1)
        ])
        violations_24h = len([
            v for v in self.violations
            if v.threshold_name == threshold_name and
            current_time_dt - v.timestamp <= timedelta(hours=24)
        ])

        # Calculate compliance percentage
        compliance_percentage = self.availability_targets.get(threshold_name, 100.0)

        # Find last violation
        threshold_violations = [
            v for v in self.violations
            if v.threshold_name == threshold_name
        ]
        last_violation = max(threshold_violations, key=lambda v: v.timestamp).timestamp \
            if threshold_violations else None

        # Determine trend (simplified)
        trend = "stable"
        if len(recent_values) >= 10:
            first_half = recent_values[:len(recent_values)//2]
            second_half = recent_values[len(recent_values)//2:]
            if statistics.mean(second_half) < statistics.mean(first_half):
                trend = "improving"
            elif statistics.mean(second_half) > statistics.mean(first_half):
                trend = "degrading"

        return SLAMetrics(
            threshold_name=threshold_name,
            current_value=current_value,
            target_value=threshold.target_value,
            compliance_percentage=compliance_percentage,
            violations_last_hour=violations_1h,
            violations_last_24h=violations_24h,
            last_violation=last_violation,
            trend=trend
        )

    def get_comprehensive_sla_report(self) -> Dict[str, Any]:
        """Get comprehensive SLA compliance report."""
        report = {
            "monitoring_status": {
                "is_active": self.is_monitoring,
                "monitoring_interval": self.monitoring_interval,
                "active_thresholds": len([t for t in self.thresholds.values() if t.enabled])
            },
            "overall_compliance": {},
            "threshold_metrics": {},
            "recent_violations": [],
            "compliance_summary": {}
        }

        # Calculate overall compliance
        all_compliances = []
        for threshold_name in self.thresholds:
            metrics = self.get_sla_metrics(threshold_name)
            if metrics:
                all_compliances.append(metrics.compliance_percentage)
                report["threshold_metrics"][threshold_name] = {
                    "current_value": metrics.current_value,
                    "target_value": metrics.target_value,
                    "compliance_percentage": metrics.compliance_percentage,
                    "violations_last_hour": metrics.violations_last_hour,
                    "violations_last_24h": metrics.violations_last_24h,
                    "trend": metrics.trend,
                    "status": "compliant" if metrics.compliance_percentage >= 95 else
                             "degraded" if metrics.compliance_percentage >= 90 else "critical"
                }

        if all_compliances:
            report["overall_compliance"] = {
                "average_compliance": statistics.mean(all_compliances),
                "minimum_compliance": min(all_compliances),
                "compliant_thresholds": len([c for c in all_compliances if c >= 95]),
                "total_thresholds": len(all_compliances)
            }

        # Recent violations (last hour)
        recent_violations = [
            {
                "threshold_name": v.threshold_name,
                "violation_type": v.violation_type,
                "measured_value": v.measured_value,
                "threshold_value": v.threshold_value,
                "timestamp": v.timestamp.isoformat(),
                "context": v.context
            }
            for v in self.violations
            if datetime.now() - v.timestamp <= timedelta(hours=1)
        ]
        report["recent_violations"] = recent_violations[-10:]  # Last 10 violations

        # Compliance summary
        critical_thresholds = [
            name for name, metrics in report["threshold_metrics"].items()
            if metrics.get("status") == "critical"
        ]
        degraded_thresholds = [
            name for name, metrics in report["threshold_metrics"].items()
            if metrics.get("status") == "degraded"
        ]

        report["compliance_summary"] = {
            "overall_status": "critical" if critical_thresholds else
                             "degraded" if degraded_thresholds else "compliant",
            "critical_thresholds": critical_thresholds,
            "degraded_thresholds": degraded_thresholds,
            "total_violations_24h": len([v for v in self.violations
                                        if datetime.now() - v.timestamp <= timedelta(hours=24)])
        }

        return report


# Global SLA monitor instance
performance_sla_monitor = PerformanceSLAMonitor()