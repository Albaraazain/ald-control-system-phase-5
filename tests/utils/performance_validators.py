"""
Performance validation utilities for ALD control system testing.

Provides tools for measuring latency, throughput, and performance regression.

Usage:
    from tests.utils.performance_validators import (
        assert_latency_within,
        assert_throughput_met,
        measure_collection_timing,
        PerformanceRegression
    )
"""

import time
import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics


@dataclass
class PerformanceMetrics:
    """Performance measurement results."""
    operation_name: str
    sample_count: int
    min_latency_ms: float
    max_latency_ms: float
    mean_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    std_dev_ms: float


async def assert_latency_within(
    operation: Callable,
    max_latency_ms: float,
    percentile: int = 95,
    sample_count: int = 10,
    operation_name: str = "operation"
) -> None:
    """
    Assert operation latency meets threshold.

    Args:
        operation: Async or sync callable to measure
        max_latency_ms: Maximum acceptable latency in milliseconds
        percentile: Percentile to check (50, 95, 99)
        sample_count: Number of samples to collect
        operation_name: Name for error messages

    Raises:
        AssertionError: If latency exceeds threshold
    """
    latencies = []

    for _ in range(sample_count):
        start = time.perf_counter()

        if asyncio.iscoroutinefunction(operation):
            await operation()
        else:
            operation()

        duration_ms = (time.perf_counter() - start) * 1000
        latencies.append(duration_ms)

    latencies.sort()

    if percentile == 50:
        measured_latency = statistics.median(latencies)
    elif percentile == 95:
        idx = int(len(latencies) * 0.95)
        measured_latency = latencies[idx]
    elif percentile == 99:
        idx = int(len(latencies) * 0.99)
        measured_latency = latencies[idx]
    else:
        measured_latency = max(latencies)

    if measured_latency > max_latency_ms:
        raise AssertionError(
            f"{operation_name} latency exceeds threshold\n"
            f"Percentile: p{percentile}\n"
            f"Expected: <{max_latency_ms}ms\n"
            f"Actual: {measured_latency:.2f}ms\n"
            f"Sample count: {sample_count}\n"
            f"Min: {min(latencies):.2f}ms\n"
            f"Max: {max(latencies):.2f}ms\n"
            f"Mean: {statistics.mean(latencies):.2f}ms"
        )


async def assert_throughput_met(
    operation: Callable,
    min_ops_per_sec: float,
    duration_seconds: int = 10,
    operation_name: str = "operation"
) -> None:
    """
    Assert operation throughput meets threshold.

    Args:
        operation: Async or sync callable to measure
        min_ops_per_sec: Minimum required operations per second
        duration_seconds: Test duration
        operation_name: Name for error messages

    Raises:
        AssertionError: If throughput below threshold
    """
    start = time.perf_counter()
    deadline = start + duration_seconds
    count = 0

    while time.perf_counter() < deadline:
        if asyncio.iscoroutinefunction(operation):
            await operation()
        else:
            operation()
        count += 1

    actual_duration = time.perf_counter() - start
    throughput = count / actual_duration

    if throughput < min_ops_per_sec:
        raise AssertionError(
            f"{operation_name} throughput below threshold\n"
            f"Expected: ≥{min_ops_per_sec} ops/sec\n"
            f"Actual: {throughput:.2f} ops/sec\n"
            f"Duration: {actual_duration:.1f}s\n"
            f"Operations: {count}"
        )


async def measure_collection_timing(
    db,
    terminal_id: int,
    start_time: datetime,
    end_time: datetime,
    expected_interval_seconds: float = 1.0
) -> Dict:
    """
    Analyze Terminal 1 timing precision from database records.

    Returns metrics about timing violations and jitter.
    """
    query = """
        SELECT timestamp
        FROM parameter_value_history
        WHERE timestamp BETWEEN $1 AND $2
        ORDER BY timestamp
    """

    result = await db.execute_query(query, start_time, end_time)

    if len(result) < 2:
        return {
            "valid": False,
            "reason": "Insufficient data points",
            "record_count": len(result)
        }

    timestamps = [row['timestamp'] for row in result]
    intervals = []

    for i in range(1, len(timestamps)):
        interval = (timestamps[i] - timestamps[i-1]).total_seconds()
        intervals.append(interval)

    violations = [
        interval for interval in intervals
        if abs(interval - expected_interval_seconds) > 0.1
    ]

    jitter_values = [
        abs(interval - expected_interval_seconds) * 1000  # Convert to ms
        for interval in intervals
    ]

    return {
        "valid": len(violations) / len(intervals) < 0.05,  # <5% violations
        "terminal_id": terminal_id,
        "record_count": len(result),
        "interval_count": len(intervals),
        "expected_interval_seconds": expected_interval_seconds,
        "mean_interval_seconds": statistics.mean(intervals),
        "median_interval_seconds": statistics.median(intervals),
        "std_dev_seconds": statistics.stdev(intervals) if len(intervals) > 1 else 0,
        "violation_count": len(violations),
        "violation_percent": (len(violations) / len(intervals) * 100) if intervals else 0,
        "jitter_mean_ms": statistics.mean(jitter_values) if jitter_values else 0,
        "jitter_p95_ms": sorted(jitter_values)[int(len(jitter_values) * 0.95)] if jitter_values else 0,
        "worst_interval_seconds": max(intervals) if intervals else 0
    }


async def measure_recipe_duration(
    db,
    recipe_id: int
) -> Dict:
    """
    Measure recipe execution duration and compare to expected.

    Returns timing analysis with overhead calculation.
    """
    query = """
        SELECT created_at, completed_at
        FROM process_executions
        WHERE recipe_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """

    result = await db.execute_query(query, recipe_id)

    if not result or not result[0].get('completed_at'):
        return {
            "valid": False,
            "reason": "Recipe not completed"
        }

    execution = result[0]
    duration = (execution['completed_at'] - execution['created_at']).total_seconds()

    return {
        "valid": True,
        "recipe_id": recipe_id,
        "duration_seconds": duration,
        "created_at": execution['created_at'].isoformat(),
        "completed_at": execution['completed_at'].isoformat()
    }


async def measure_parameter_write_latency(
    db,
    command_id: int
) -> Dict:
    """
    Track Terminal 3 parameter write E2E latency.

    Measures time from command insertion to completion.
    """
    query = """
        SELECT
            created_at,
            executed_at,
            completed_at
        FROM parameter_control_commands
        WHERE id = $1
    """

    result = await db.execute_query(query, command_id)

    if not result:
        return {
            "valid": False,
            "reason": "Command not found"
        }

    command = result[0]

    if not command.get('completed_at'):
        return {
            "valid": False,
            "reason": "Command not completed",
            "executed_at": command.get('executed_at')
        }

    detection_latency = (command['executed_at'] - command['created_at']).total_seconds() if command['executed_at'] else None
    execution_latency = (command['completed_at'] - command['executed_at']).total_seconds() if command['executed_at'] else None
    e2e_latency = (command['completed_at'] - command['created_at']).total_seconds()

    return {
        "valid": True,
        "command_id": command_id,
        "detection_latency_seconds": detection_latency,
        "execution_latency_seconds": execution_latency,
        "e2e_latency_seconds": e2e_latency,
        "created_at": command['created_at'].isoformat(),
        "executed_at": command['executed_at'].isoformat() if command['executed_at'] else None,
        "completed_at": command['completed_at'].isoformat()
    }


class PerformanceRegression:
    """
    Detect performance regressions by comparing against baseline.
    """

    def __init__(self, baseline_metrics: Dict[str, float], tolerance_percent: float = 10.0):
        """
        Initialize with baseline metrics.

        Args:
            baseline_metrics: Dict of metric_name -> baseline_value
            tolerance_percent: Acceptable regression percentage
        """
        self.baseline = baseline_metrics
        self.tolerance = tolerance_percent / 100.0

    def check_regression(self, current_metrics: Dict[str, float]) -> Dict:
        """
        Check for performance regression.

        Returns dict with regression status and details.
        """
        regressions = {}

        for metric_name, baseline_value in self.baseline.items():
            if metric_name not in current_metrics:
                continue

            current_value = current_metrics[metric_name]
            change_percent = ((current_value - baseline_value) / baseline_value) * 100

            if change_percent > (self.tolerance * 100):
                regressions[metric_name] = {
                    "baseline": baseline_value,
                    "current": current_value,
                    "change_percent": change_percent,
                    "threshold_percent": self.tolerance * 100
                }

        return {
            "regressed": len(regressions) > 0,
            "regression_count": len(regressions),
            "regressions": regressions
        }


async def collect_performance_metrics(
    operation: Callable,
    operation_name: str,
    sample_count: int = 100
) -> PerformanceMetrics:
    """
    Collect comprehensive performance metrics for an operation.

    Args:
        operation: Async or sync callable to measure
        operation_name: Name of operation
        sample_count: Number of samples

    Returns:
        PerformanceMetrics with detailed statistics
    """
    latencies_ms = []

    for _ in range(sample_count):
        start = time.perf_counter()

        if asyncio.iscoroutinefunction(operation):
            await operation()
        else:
            operation()

        duration_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(duration_ms)

    latencies_ms.sort()

    return PerformanceMetrics(
        operation_name=operation_name,
        sample_count=sample_count,
        min_latency_ms=min(latencies_ms),
        max_latency_ms=max(latencies_ms),
        mean_latency_ms=statistics.mean(latencies_ms),
        median_latency_ms=statistics.median(latencies_ms),
        p95_latency_ms=latencies_ms[int(sample_count * 0.95)],
        p99_latency_ms=latencies_ms[int(sample_count * 0.99)],
        std_dev_ms=statistics.stdev(latencies_ms) if sample_count > 1 else 0
    )


async def validate_timing_precision(
    timestamps: List[datetime],
    expected_interval_seconds: float = 1.0,
    tolerance_ms: float = 100.0,
    max_violations_percent: float = 5.0
) -> Dict:
    """
    Validate timing precision of timestamp series.

    Checks that intervals between consecutive timestamps match expected
    interval within tolerance, used for validating Terminal 1 collection timing.

    Args:
        timestamps: List of timestamps in chronological order
        expected_interval_seconds: Expected interval between timestamps
        tolerance_ms: Acceptable deviation in milliseconds (default ±100ms)
        max_violations_percent: Maximum acceptable violation rate (default 5%)

    Returns:
        Dict with validation result and timing statistics

    Example:
        >>> result = await validate_timing_precision(
        ...     timestamps,
        ...     expected_interval_seconds=1.0,
        ...     tolerance_ms=100.0
        ... )
        >>> assert result['valid'], f"Timing precision failed: {result}"
    """
    if len(timestamps) < 2:
        return {
            "valid": False,
            "reason": "Need at least 2 timestamps",
            "count": len(timestamps)
        }

    intervals_seconds = []
    violations = []

    for i in range(1, len(timestamps)):
        interval = (timestamps[i] - timestamps[i-1]).total_seconds()
        intervals_seconds.append(interval)

        deviation_ms = abs(interval - expected_interval_seconds) * 1000
        if deviation_ms > tolerance_ms:
            violations.append({
                "index": i,
                "expected_seconds": expected_interval_seconds,
                "actual_seconds": interval,
                "deviation_ms": deviation_ms
            })

    violation_percent = (len(violations) / len(intervals_seconds)) * 100 if intervals_seconds else 0
    is_valid = violation_percent <= max_violations_percent

    jitter_ms = [abs(interval - expected_interval_seconds) * 1000 for interval in intervals_seconds]

    return {
        "valid": is_valid,
        "timestamp_count": len(timestamps),
        "interval_count": len(intervals_seconds),
        "expected_interval_seconds": expected_interval_seconds,
        "tolerance_ms": tolerance_ms,
        "mean_interval_seconds": statistics.mean(intervals_seconds) if intervals_seconds else 0,
        "median_interval_seconds": statistics.median(intervals_seconds) if intervals_seconds else 0,
        "min_interval_seconds": min(intervals_seconds) if intervals_seconds else 0,
        "max_interval_seconds": max(intervals_seconds) if intervals_seconds else 0,
        "jitter_mean_ms": statistics.mean(jitter_ms) if jitter_ms else 0,
        "jitter_max_ms": max(jitter_ms) if jitter_ms else 0,
        "jitter_p95_ms": sorted(jitter_ms)[int(len(jitter_ms) * 0.95)] if jitter_ms else 0,
        "violation_count": len(violations),
        "violation_percent": violation_percent,
        "max_violations_percent": max_violations_percent,
        "violations": violations[:5]  # First 5 violations for debugging
    }


async def validate_memory_stability(
    memory_samples_mb: List[float],
    max_growth_mb: float = 50.0,
    max_std_dev_mb: float = 20.0
) -> Dict:
    """
    Validate memory usage remains stable over time.

    Checks for memory leaks by analyzing memory growth and variance
    over test duration.

    Args:
        memory_samples_mb: List of memory usage samples in MB
        max_growth_mb: Maximum acceptable memory growth (default 50MB)
        max_std_dev_mb: Maximum acceptable standard deviation (default 20MB)

    Returns:
        Dict with validation result and memory statistics

    Example:
        >>> memory_samples = [45.2, 46.1, 45.8, 47.3, 46.5]  # MB
        >>> result = await validate_memory_stability(
        ...     memory_samples,
        ...     max_growth_mb=50.0
        ... )
        >>> assert result['valid'], f"Memory instability: {result}"
    """
    if len(memory_samples_mb) < 2:
        return {
            "valid": False,
            "reason": "Need at least 2 memory samples",
            "count": len(memory_samples_mb)
        }

    initial_mb = memory_samples_mb[0]
    final_mb = memory_samples_mb[-1]
    growth_mb = final_mb - initial_mb

    mean_mb = statistics.mean(memory_samples_mb)
    std_dev_mb = statistics.stdev(memory_samples_mb) if len(memory_samples_mb) > 1 else 0

    # Check for monotonic growth (potential leak)
    growth_trend = sum(
        1 for i in range(1, len(memory_samples_mb))
        if memory_samples_mb[i] > memory_samples_mb[i-1]
    )
    growth_trend_percent = (growth_trend / (len(memory_samples_mb) - 1)) * 100

    is_stable_growth = growth_mb <= max_growth_mb
    is_stable_variance = std_dev_mb <= max_std_dev_mb
    no_leak_detected = growth_trend_percent < 80  # Less than 80% monotonic growth

    is_valid = is_stable_growth and is_stable_variance and no_leak_detected

    return {
        "valid": is_valid,
        "sample_count": len(memory_samples_mb),
        "initial_mb": initial_mb,
        "final_mb": final_mb,
        "growth_mb": growth_mb,
        "max_growth_mb": max_growth_mb,
        "mean_mb": mean_mb,
        "median_mb": statistics.median(memory_samples_mb),
        "min_mb": min(memory_samples_mb),
        "max_mb": max(memory_samples_mb),
        "std_dev_mb": std_dev_mb,
        "max_std_dev_mb": max_std_dev_mb,
        "growth_trend_percent": growth_trend_percent,
        "leak_suspected": growth_trend_percent >= 80,
        "stable_growth": is_stable_growth,
        "stable_variance": is_stable_variance
    }
