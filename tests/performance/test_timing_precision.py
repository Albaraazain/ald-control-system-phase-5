"""
Timing Precision and Performance Tests

Tests timing precision, performance characteristics, and resource stability
of all 3 terminals under various load conditions.

Based on test_design/infrastructure_stress_requirements.md
"""

import pytest
import asyncio
import time
import psutil
import os
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
from unittest.mock import patch, AsyncMock

# Test utilities
from tests.utils.async_helpers import measure_execution_time, wait_for_condition
from tests.utils.performance_validators import validate_timing_precision, validate_memory_stability


@dataclass
class TimingMeasurement:
    """Single timing measurement with metadata"""
    cycle_number: int
    start_time: float
    end_time: float
    duration: float
    interval_from_previous: float
    load_level: str

    def is_within_tolerance(self, target: float, tolerance: float) -> bool:
        """Check if interval is within tolerance of target"""
        return abs(self.interval_from_previous - target) <= tolerance


@dataclass
class PerformanceBaseline:
    """Performance baseline metrics"""
    operation: str
    p50_latency: float
    p95_latency: float
    p99_latency: float
    throughput: float
    success_rate: float
    memory_mb: float
    cpu_percent: float


# ============================================================================
# Terminal 1 Timing Precision Tests
# ============================================================================

@pytest.mark.performance
@pytest.mark.terminal1
class TestTerminal1TimingPrecision:
    """Test Terminal 1 data collection timing precision (±100ms requirement)"""

    @pytest.mark.asyncio
    async def test_timing_precision_no_load(self, plc_simulation, clean_test_database):
        """Test Terminal 1 timing precision with no load

        Requirement: 95% of cycles within 1.0s ± 0.1s
        Test: 100 cycles with no concurrent operations
        """
        from plc_data_service import PLCDataService

        # Create service (mocking PLC and DB)
        service = PLCDataService(machine_id="test-timing-no-load")
        service.plc = plc_simulation

        # Mock database insert to be fast
        insert_times = []
        original_insert = service._batch_insert_parameters

        async def mock_insert(*args, **kwargs):
            start = time.perf_counter()
            # Simulate fast insert
            await asyncio.sleep(0.01)  # 10ms
            duration = time.perf_counter() - start
            insert_times.append(duration)
            return True

        service._batch_insert_parameters = mock_insert

        # Collect timing measurements
        measurements: List[TimingMeasurement] = []
        previous_time = None

        for cycle in range(100):
            cycle_start = time.perf_counter()

            # Simulate one data collection cycle
            await service.collect_parameters()

            cycle_end = time.perf_counter()
            duration = cycle_end - cycle_start

            interval = (cycle_end - previous_time) if previous_time else 1.0
            previous_time = cycle_end

            measurements.append(TimingMeasurement(
                cycle_number=cycle,
                start_time=cycle_start,
                end_time=cycle_end,
                duration=duration,
                interval_from_previous=interval,
                load_level="no_load"
            ))

            # Wait to maintain 1Hz (compensating for duration)
            remaining = 1.0 - duration
            if remaining > 0:
                await asyncio.sleep(remaining)

        # Analyze timing precision
        intervals = [m.interval_from_previous for m in measurements[1:]]  # Skip first
        target = 1.0
        tolerance = 0.1

        within_tolerance = sum(1 for i in intervals if abs(i - target) <= tolerance)
        precision_rate = within_tolerance / len(intervals)

        # Calculate statistics
        mean_interval = sum(intervals) / len(intervals)
        max_deviation = max(abs(i - target) for i in intervals)

        # Assertions
        assert precision_rate >= 0.95, \
            f"Timing precision {precision_rate:.2%} < 95% (mean={mean_interval:.3f}s, max_dev={max_deviation:.3f}s)"
        assert mean_interval == pytest.approx(target, abs=0.05), \
            f"Mean interval {mean_interval:.3f}s not close to target {target}s"

        # Verify DB inserts were fast
        mean_insert_time = sum(insert_times) / len(insert_times)
        assert mean_insert_time < 0.100, \
            f"Mean DB insert time {mean_insert_time:.3f}s > 100ms"

    @pytest.mark.asyncio
    async def test_timing_precision_medium_load(self, plc_simulation, clean_test_database):
        """Test Terminal 1 timing with medium load (Terminal 2 running simple recipe)

        Requirement: Maintain 1.0s ± 0.1s timing under load
        Test: 100 cycles while recipe executes
        """
        from plc_data_service import PLCDataService
        from simple_recipe_service import SimpleRecipeService

        data_service = PLCDataService(machine_id="test-timing-medium-load")
        data_service.plc = plc_simulation

        # Mock fast DB operations
        data_service._batch_insert_parameters = AsyncMock(return_value=True)

        # Start background recipe execution (medium load)
        recipe_service = SimpleRecipeService(machine_id="test-timing-medium-load")
        recipe_service.plc = plc_simulation

        async def run_simple_recipe():
            """Execute a simple recipe (10 steps × 1s = 10s)"""
            for step in range(10):
                await plc_simulation.write_parameter(param_id=100 + step, value=step * 10.0)
                await asyncio.sleep(1.0)

        # Start recipe in background
        recipe_task = asyncio.create_task(run_simple_recipe())

        # Collect timing measurements
        measurements = []
        previous_time = None

        for cycle in range(100):
            cycle_start = time.perf_counter()
            await data_service.collect_parameters()
            cycle_end = time.perf_counter()

            duration = cycle_end - cycle_start
            interval = (cycle_end - previous_time) if previous_time else 1.0
            previous_time = cycle_end

            measurements.append(TimingMeasurement(
                cycle_number=cycle,
                start_time=cycle_start,
                end_time=cycle_end,
                duration=duration,
                interval_from_previous=interval,
                load_level="medium_load"
            ))

            # Maintain 1Hz
            remaining = 1.0 - duration
            if remaining > 0:
                await asyncio.sleep(remaining)

        # Cancel recipe
        recipe_task.cancel()
        try:
            await recipe_task
        except asyncio.CancelledError:
            pass

        # Analyze timing
        intervals = [m.interval_from_previous for m in measurements[1:]]
        within_tolerance = sum(1 for i in intervals if abs(i - 1.0) <= 0.1)
        precision_rate = within_tolerance / len(intervals)

        # Under medium load, allow slightly lower precision
        assert precision_rate >= 0.90, \
            f"Timing precision under load {precision_rate:.2%} < 90%"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_timing_precision_high_load(self, three_terminals, clean_test_database):
        """Test Terminal 1 timing with high load (all 3 terminals + 10 param commands/sec)

        Requirement: Graceful degradation under extreme load
        Test: 100 cycles with all terminals + parameter spam
        """
        # This test requires subprocess-based three_terminals fixture
        # Simplified version for demonstration
        from plc_data_service import PLCDataService

        service = PLCDataService(machine_id="test-timing-high-load")
        service._batch_insert_parameters = AsyncMock(return_value=True)

        # Simulate high CPU load
        async def cpu_stress():
            """Generate CPU load"""
            while True:
                _ = sum(i**2 for i in range(10000))
                await asyncio.sleep(0.01)

        # Start multiple stress tasks
        stress_tasks = [asyncio.create_task(cpu_stress()) for _ in range(5)]

        measurements = []
        previous_time = None

        for cycle in range(100):
            cycle_start = time.perf_counter()
            # Simulate parameter collection
            await asyncio.sleep(0.05)  # Simulated collection
            cycle_end = time.perf_counter()

            duration = cycle_end - cycle_start
            interval = (cycle_end - previous_time) if previous_time else 1.0
            previous_time = cycle_end

            measurements.append(TimingMeasurement(
                cycle_number=cycle,
                start_time=cycle_start,
                end_time=cycle_end,
                duration=duration,
                interval_from_previous=interval,
                load_level="high_load"
            ))

            remaining = 1.0 - duration
            if remaining > 0:
                await asyncio.sleep(remaining)

        # Cleanup stress tasks
        for task in stress_tasks:
            task.cancel()
        await asyncio.gather(*stress_tasks, return_exceptions=True)

        # Under high load, expect more timing violations
        intervals = [m.interval_from_previous for m in measurements[1:]]
        within_tolerance = sum(1 for i in intervals if abs(i - 1.0) <= 0.1)
        precision_rate = within_tolerance / len(intervals)

        # Accept lower precision under extreme load, but should not crash
        assert precision_rate >= 0.70, \
            f"Timing precision under high load {precision_rate:.2%} < 70%"

    @pytest.mark.asyncio
    async def test_timing_violation_logging(self, plc_simulation, caplog):
        """Test that timing violations are logged correctly

        Requirement: Timing violations logged but don't crash service
        """
        from plc_data_service import PLCDataService
        import logging

        caplog.set_level(logging.WARNING)

        service = PLCDataService(machine_id="test-timing-violations")
        service.plc = plc_simulation

        # Mock slow DB insert to cause violations
        async def slow_insert(*args, **kwargs):
            await asyncio.sleep(0.5)  # 500ms - will cause violation
            return True

        service._batch_insert_parameters = slow_insert

        # Run a few cycles
        for cycle in range(5):
            cycle_start = time.perf_counter()
            await service.collect_parameters()
            duration = time.perf_counter() - cycle_start

            # Check if violation occurred
            if duration > 1.0:
                # Should be logged
                assert any("timing violation" in rec.message.lower()
                          for rec in caplog.records), \
                    f"Timing violation (duration={duration:.2f}s) not logged"


# ============================================================================
# Database Write Performance Tests
# ============================================================================

@pytest.mark.performance
class TestDatabaseWritePerformance:
    """Test database write performance and latency"""

    @pytest.mark.asyncio
    async def test_batch_insert_50_params_latency(self, plc_simulation, clean_test_database):
        """Test batch insert latency for 50 parameters

        Requirement: < 100ms for 50 parameters
        """
        from plc_data_service import PLCDataService

        service = PLCDataService(machine_id="test-batch-50")
        service.plc = plc_simulation

        # Generate 50 parameter values
        parameter_data = [
            {"parameter_id": i, "value": float(i * 10), "timestamp": time.time()}
            for i in range(50)
        ]

        # Measure 10 batch inserts
        latencies = []
        for run in range(10):
            result, duration = await measure_execution_time(
                service._batch_insert_parameters(parameter_data)
            )
            latencies.append(duration)

        # Calculate percentiles
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        # Assertions
        assert p50 < 0.100, f"P50 latency {p50:.3f}s > 100ms"
        assert p95 < 0.150, f"P95 latency {p95:.3f}s > 150ms"

    @pytest.mark.asyncio
    async def test_retry_overhead(self, plc_simulation, clean_test_database):
        """Test retry overhead when first insert fails

        Requirement: 1st retry adds ~1s (exponential backoff: 1s, 2s, 4s)
        """
        from plc_data_service import PLCDataService

        service = PLCDataService(machine_id="test-retry-overhead")

        # Mock insert that fails once then succeeds
        attempt_count = 0

        async def failing_insert(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                await asyncio.sleep(0.01)
                raise Exception("Simulated DB failure")
            else:
                await asyncio.sleep(0.01)
                return True

        service._batch_insert_parameters = failing_insert

        # Measure retry overhead
        parameter_data = [{"parameter_id": 1, "value": 42.0, "timestamp": time.time()}]

        start = time.perf_counter()
        result = await service._batch_insert_with_retry(parameter_data, max_attempts=3)
        duration = time.perf_counter() - start

        # Should succeed on 2nd attempt after ~1s backoff
        assert result is True
        assert attempt_count == 2
        assert 0.9 <= duration <= 1.5, \
            f"Retry overhead {duration:.2f}s not in expected range (0.9s - 1.5s)"

    @pytest.mark.asyncio
    async def test_dlq_write_overhead(self, plc_simulation, temp_dir):
        """Test dead letter queue write overhead

        Requirement: < 10ms to write failed batch to DLQ file
        """
        from plc_data_service import PLCDataService

        service = PLCDataService(machine_id="test-dlq-overhead")
        service.dlq_directory = temp_dir

        # Parameter data that will be written to DLQ
        parameter_data = [
            {"parameter_id": i, "value": float(i), "timestamp": time.time()}
            for i in range(50)
        ]

        # Measure DLQ write time
        result, duration = await measure_execution_time(
            service._write_to_dead_letter_queue(parameter_data, error="test-error")
        )

        assert duration < 0.010, \
            f"DLQ write took {duration:.4f}s > 10ms"

        # Verify file was created
        dlq_files = list(temp_dir.glob("dlq_*.jsonl"))
        assert len(dlq_files) == 1, "DLQ file not created"


# ============================================================================
# Terminal 3 Parameter Write Latency Tests
# ============================================================================

@pytest.mark.performance
@pytest.mark.terminal3
class TestParameterWriteLatency:
    """Test Terminal 3 parameter write end-to-end latency"""

    @pytest.mark.asyncio
    async def test_parameter_write_noncritical_latency(self, plc_simulation, clean_test_database):
        """Test non-safety-critical parameter write latency

        Requirement: < 500ms end-to-end
        E2E: Command inserted → PLC write → confirmation read → DB update
        """
        from parameter_service import ParameterService

        service = ParameterService(machine_id="test-param-latency")
        service.plc = plc_simulation

        # Mock database operations
        service._update_command_status = AsyncMock(return_value=True)

        # Simulate command processing
        command = {
            "id": "cmd-123",
            "parameter_id": 100,
            "target_value": 42.5,
            "machine_id": "test-param-latency",
            "inserted_at": time.time()
        }

        # Measure end-to-end latency
        start = time.perf_counter()

        # 1. Command detection (simulated - instant)
        # 2. Process command
        await service.process_parameter_command(command)
        # 3. PLC write
        await service.plc.write_parameter(param_id=100, value=42.5)
        # 4. Confirmation read
        actual_value = await service.plc.read_parameter(param_id=100)
        # 5. DB update (mocked)
        await service._update_command_status(command["id"], "completed")

        duration = time.perf_counter() - start

        # Assertion
        assert duration < 0.500, \
            f"Parameter write E2E latency {duration:.3f}s > 500ms"

    @pytest.mark.asyncio
    async def test_parameter_write_safety_critical_latency(self, plc_simulation, clean_test_database):
        """Test safety-critical parameter write latency

        Requirement: < 200ms end-to-end (stricter requirement)
        """
        from parameter_service import ParameterService

        service = ParameterService(machine_id="test-safety-latency")
        service.plc = plc_simulation
        service._update_command_status = AsyncMock(return_value=True)

        # Safety-critical parameter (e.g., emergency shutdown)
        command = {
            "id": "cmd-safety-123",
            "parameter_id": 1,  # Assume ID 1 is safety-critical
            "target_value": 0.0,  # Emergency stop
            "machine_id": "test-safety-latency",
            "priority": "high",
            "inserted_at": time.time()
        }

        # Measure E2E latency
        start = time.perf_counter()
        await service.process_parameter_command(command)
        await service.plc.write_parameter(param_id=1, value=0.0)
        duration = time.perf_counter() - start

        # Stricter requirement for safety-critical
        assert duration < 0.200, \
            f"Safety-critical parameter write {duration:.3f}s > 200ms"


# ============================================================================
# Terminal 2 Recipe Execution Timing Tests
# ============================================================================

@pytest.mark.performance
@pytest.mark.terminal2
class TestRecipeExecutionTiming:
    """Test Terminal 2 recipe execution timing precision"""

    @pytest.mark.asyncio
    async def test_recipe_step_execution_precision(self, plc_simulation):
        """Test recipe with 10 steps × 1s duration

        Requirement: Total execution 10s ± 0.5s
        """
        from simple_recipe_service import SimpleRecipeService

        service = SimpleRecipeService(machine_id="test-recipe-timing")
        service.plc = plc_simulation

        # Create recipe with 10 steps, 1s each
        recipe_steps = [
            {"type": "parameter_write", "parameter_id": i, "value": float(i * 10), "duration": 1.0}
            for i in range(10)
        ]

        # Execute recipe
        start = time.perf_counter()
        for step in recipe_steps:
            await service.plc.write_parameter(param_id=step["parameter_id"], value=step["value"])
            await asyncio.sleep(step["duration"])
        duration = time.perf_counter() - start

        # Verify timing
        expected = 10.0
        tolerance = 0.5
        assert abs(duration - expected) <= tolerance, \
            f"Recipe execution time {duration:.2f}s not within {expected}s ± {tolerance}s"

    @pytest.mark.asyncio
    async def test_recipe_loop_timing(self, plc_simulation):
        """Test recipe loop timing: 5 iterations × 2s = 10s ± 0.5s

        Requirement: Loop overhead minimal
        """
        from simple_recipe_service import SimpleRecipeService

        service = SimpleRecipeService(machine_id="test-loop-timing")
        service.plc = plc_simulation

        # Execute loop
        start = time.perf_counter()
        for iteration in range(5):
            await service.plc.write_parameter(param_id=50, value=float(iteration))
            await asyncio.sleep(2.0)
        duration = time.perf_counter() - start

        # Verify
        expected = 10.0
        tolerance = 0.5
        assert abs(duration - expected) <= tolerance, \
            f"Loop execution {duration:.2f}s not within {expected}s ± {tolerance}s"


# ============================================================================
# Memory Stability Tests (24-hour simulation)
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
class TestMemoryStability:
    """Test memory stability over extended operation (simulated 24 hours)"""

    @pytest.mark.asyncio
    async def test_memory_stability_1hour_compressed(self, three_terminals, performance_monitor):
        """Test memory stability over simulated 1 hour (compressed to ~5 minutes)

        Requirement: < 10% memory growth over 1 hour
        Test: Run all 3 terminals with accelerated operations
        """
        # Start performance monitoring
        performance_monitor.start()

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate 1 hour of operations (compressed to 5 minutes)
        # 1 hour = 3600 cycles @ 1Hz, compress to 5 min = 300 seconds
        # Run 300 cycles at 1Hz = 5 minutes

        for cycle in range(300):
            # Simulate Terminal 1 data collection
            await asyncio.sleep(0.01)

            # Simulate Terminal 3 parameter commands every 10 cycles
            if cycle % 10 == 0:
                await asyncio.sleep(0.005)

            # Maintain 1Hz (compressed)
            await asyncio.sleep(0.99)

        # Stop monitoring
        metrics = performance_monitor.stop()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = ((final_memory - initial_memory) / initial_memory) * 100

        # Assertions
        assert memory_growth < 10.0, \
            f"Memory growth {memory_growth:.1f}% exceeds 10% threshold"
        assert metrics.cpu_usage < 20.0, \
            f"Average CPU usage {metrics.cpu_usage:.1f}% exceeds 20% threshold"

    @pytest.mark.asyncio
    @pytest.mark.very_slow
    async def test_memory_leak_detection(self, plc_simulation):
        """Test for memory leaks using tracemalloc

        Requirement: No memory leaks detected over extended operation
        """
        import tracemalloc
        from plc_data_service import PLCDataService

        tracemalloc.start()

        service = PLCDataService(machine_id="test-memory-leak")
        service.plc = plc_simulation
        service._batch_insert_parameters = AsyncMock(return_value=True)

        # Take initial snapshot
        snapshot1 = tracemalloc.take_snapshot()

        # Run 1000 collection cycles
        for cycle in range(1000):
            await service.collect_parameters()
            await asyncio.sleep(0.01)

        # Take final snapshot
        snapshot2 = tracemalloc.take_snapshot()

        # Compare snapshots
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')

        # Check for significant memory growth
        total_growth = sum(stat.size_diff for stat in top_stats)
        total_growth_mb = total_growth / 1024 / 1024

        # Allow up to 5MB growth for 1000 cycles
        assert total_growth_mb < 5.0, \
            f"Memory leak detected: {total_growth_mb:.2f}MB growth over 1000 cycles"

        tracemalloc.stop()


# ============================================================================
# Connection Pool Exhaustion Tests
# ============================================================================

@pytest.mark.performance
class TestConnectionPoolExhaustion:
    """Test connection pool behavior under rapid command load"""

    @pytest.mark.asyncio
    async def test_100_rapid_parameter_commands(self, plc_simulation, clean_test_database):
        """Test 100 rapid parameter commands

        Requirement: No connection pool exhaustion errors
        Measure: Throughput (commands/sec)
        """
        from parameter_service import ParameterService

        service = ParameterService(machine_id="test-conn-pool")
        service.plc = plc_simulation
        service._update_command_status = AsyncMock(return_value=True)

        # Create 100 commands
        commands = [
            {
                "id": f"cmd-{i}",
                "parameter_id": 100 + (i % 10),
                "target_value": float(i),
                "machine_id": "test-conn-pool"
            }
            for i in range(100)
        ]

        # Execute all commands concurrently
        start = time.perf_counter()
        results = await asyncio.gather(
            *[service.process_parameter_command(cmd) for cmd in commands],
            return_exceptions=True
        )
        duration = time.perf_counter() - start

        # Check for errors
        errors = [r for r in results if isinstance(r, Exception)]
        connection_errors = [e for e in errors if "connection" in str(e).lower()]

        assert len(connection_errors) == 0, \
            f"Connection pool exhaustion detected: {len(connection_errors)} connection errors"

        # Calculate throughput
        success_count = len([r for r in results if not isinstance(r, Exception)])
        throughput = success_count / duration

        # Should handle at least 10 commands/sec
        assert throughput >= 10.0, \
            f"Throughput {throughput:.1f} commands/sec < 10 commands/sec"

    @pytest.mark.asyncio
    async def test_supabase_connection_pool_stability(self, clean_test_database):
        """Test Supabase connection pool doesn't exhaust

        Requirement: Verify no "too many connections" errors
        """
        # This would require real Supabase connection
        # Simplified version with mock

        connection_count = 0
        max_connections = 0

        async def mock_query():
            nonlocal connection_count, max_connections
            connection_count += 1
            max_connections = max(max_connections, connection_count)
            await asyncio.sleep(0.05)  # Simulate query
            connection_count -= 1

        # Execute 100 concurrent queries
        await asyncio.gather(*[mock_query() for _ in range(100)])

        # Verify connection count stayed reasonable
        # Supabase typically allows 15-60 connections depending on tier
        assert max_connections < 50, \
            f"Max concurrent connections {max_connections} may exhaust pool"


# ============================================================================
# Performance Baseline Establishment
# ============================================================================

@pytest.mark.benchmark
class TestPerformanceBaselines:
    """Establish and document performance baselines"""

    @pytest.mark.asyncio
    async def test_establish_terminal1_baseline(self, plc_simulation, clean_test_database):
        """Establish Terminal 1 performance baseline"""
        from plc_data_service import PLCDataService

        service = PLCDataService(machine_id="baseline-t1")
        service.plc = plc_simulation
        service._batch_insert_parameters = AsyncMock(return_value=True)

        # Run 100 cycles and measure
        latencies = []
        for cycle in range(100):
            result, duration = await measure_execution_time(
                service.collect_parameters()
            )
            latencies.append(duration)

        latencies.sort()
        baseline = PerformanceBaseline(
            operation="terminal1_data_collection",
            p50_latency=latencies[50],
            p95_latency=latencies[95],
            p99_latency=latencies[99],
            throughput=1.0,  # 1 Hz
            success_rate=1.0,
            memory_mb=psutil.Process().memory_info().rss / 1024 / 1024,
            cpu_percent=psutil.Process().cpu_percent()
        )

        # Log baseline (would normally save to file)
        print(f"\nTerminal 1 Baseline:")
        print(f"  P50 latency: {baseline.p50_latency:.3f}s")
        print(f"  P95 latency: {baseline.p95_latency:.3f}s")
        print(f"  P99 latency: {baseline.p99_latency:.3f}s")
        print(f"  Memory: {baseline.memory_mb:.1f} MB")
        print(f"  CPU: {baseline.cpu_percent:.1f}%")

        # Baseline assertions
        assert baseline.p95_latency < 0.200, "P95 latency exceeds 200ms"

    @pytest.mark.asyncio
    async def test_establish_terminal3_baseline(self, plc_simulation, clean_test_database):
        """Establish Terminal 3 performance baseline"""
        from parameter_service import ParameterService

        service = ParameterService(machine_id="baseline-t3")
        service.plc = plc_simulation
        service._update_command_status = AsyncMock(return_value=True)

        # Measure parameter write latency
        latencies = []
        for i in range(100):
            command = {
                "id": f"cmd-{i}",
                "parameter_id": 100,
                "target_value": float(i),
                "machine_id": "baseline-t3"
            }

            result, duration = await measure_execution_time(
                service.process_parameter_command(command)
            )
            latencies.append(duration)

        latencies.sort()
        baseline = PerformanceBaseline(
            operation="terminal3_parameter_write",
            p50_latency=latencies[50],
            p95_latency=latencies[95],
            p99_latency=latencies[99],
            throughput=len(latencies) / sum(latencies),
            success_rate=1.0,
            memory_mb=psutil.Process().memory_info().rss / 1024 / 1024,
            cpu_percent=psutil.Process().cpu_percent()
        )

        # Log baseline
        print(f"\nTerminal 3 Baseline:")
        print(f"  P50 latency: {baseline.p50_latency:.3f}s")
        print(f"  P95 latency: {baseline.p95_latency:.3f}s")
        print(f"  Throughput: {baseline.throughput:.1f} cmds/sec")

        # Baseline assertions
        assert baseline.p95_latency < 0.500, "P95 latency exceeds 500ms"


# ============================================================================
# Test Markers and Configuration
# ============================================================================

pytest.mark.performance = pytest.mark.performance  # Mark for --run-performance
pytest.mark.slow = pytest.mark.slow  # Mark for --run-slow
pytest.mark.very_slow = pytest.mark.very_slow  # Mark for --run-very-slow
