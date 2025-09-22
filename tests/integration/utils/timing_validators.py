"""
Timing Validation Utilities for 3-Terminal Safety Testing

Provides precise timing measurement and validation for critical
timing requirements in the ALD control system.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import pytest


@dataclass
class TimingMeasurement:
    """Individual timing measurement."""
    operation_id: str
    operation_type: str
    scheduled_time: float
    actual_time: float
    timing_error: float
    precision_met: bool
    metadata: Dict[str, Any]


@dataclass
class TimingBenchmark:
    """Timing benchmark results."""
    test_name: str
    total_measurements: int
    precision_target_ms: float
    measurements_within_target: int
    success_rate: float
    avg_timing_error: float
    max_timing_error: float
    min_timing_error: float
    std_dev_timing_error: float


class TimingValidator:
    """Advanced timing validation for safety-critical operations."""

    def __init__(self, precision_target_ms: float = 100.0):
        self.precision_target_ms = precision_target_ms
        self.precision_target_s = precision_target_ms / 1000.0
        self.measurements = []
        self.benchmarks = []

    async def measure_operation_timing(
        self,
        operation_id: str,
        operation_type: str,
        operation_func: Callable,
        scheduled_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TimingMeasurement:
        """Measure timing of a single operation."""
        if metadata is None:
            metadata = {}

        # Wait until scheduled time
        wait_time = scheduled_time - time.time()
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        # Execute operation and measure actual time
        actual_start = time.time()
        try:
            result = await operation_func()
            metadata['operation_result'] = result
            metadata['operation_success'] = True
        except Exception as e:
            metadata['operation_error'] = str(e)
            metadata['operation_success'] = False

        actual_time = actual_start

        # Calculate timing error
        timing_error = abs(actual_time - scheduled_time)
        precision_met = timing_error <= self.precision_target_s

        measurement = TimingMeasurement(
            operation_id=operation_id,
            operation_type=operation_type,
            scheduled_time=scheduled_time,
            actual_time=actual_time,
            timing_error=timing_error,
            precision_met=precision_met,
            metadata=metadata
        )

        self.measurements.append(measurement)
        return measurement

    async def measure_coordination_timing(
        self,
        terminal_cluster,
        coordination_plan: List[Dict[str, Any]]
    ) -> List[TimingMeasurement]:
        """Measure timing of coordinated operations across terminals."""
        terminal_1, terminal_2, terminal_3 = terminal_cluster
        terminals = {
            'terminal_1': terminal_1,
            'terminal_2': terminal_2,
            'terminal_3': terminal_3
        }

        measurement_tasks = []

        for step in coordination_plan:
            terminal_id = step['terminal']
            operation = step['operation']
            scheduled_time = step['scheduled_time']
            operation_id = step.get('operation_id', f"{terminal_id}_{operation}_{scheduled_time}")

            terminal = terminals[terminal_id]

            # Create operation function based on terminal and operation
            async def create_operation_func(t, op):
                if op == "data_collection_start":
                    return await t.schedule_timed_operation("data_collection", scheduled_time)
                elif op == "data_collection_stop":
                    return await t.schedule_timed_operation("stop_data_collection", scheduled_time)
                elif op == "valve_operation":
                    return await t.schedule_timed_operation("valve_operation", scheduled_time)
                elif op == "parameter_update":
                    return await t.schedule_timed_operation("parameter_update", scheduled_time)
                else:
                    return {"status": "unknown_operation"}

            operation_func = lambda t=terminal, op=operation: create_operation_func(t, op)

            # Schedule timing measurement
            task = asyncio.create_task(
                self.measure_operation_timing(
                    operation_id=operation_id,
                    operation_type=operation,
                    operation_func=operation_func,
                    scheduled_time=scheduled_time,
                    metadata={'terminal': terminal_id, 'step': step}
                )
            )

            measurement_tasks.append(task)

        # Wait for all measurements to complete
        measurements = await asyncio.gather(*measurement_tasks)

        return measurements

    async def validate_emergency_propagation_timing(
        self,
        terminal_cluster,
        trigger_terminal_id: str,
        max_propagation_ms: float = 500.0
    ) -> Dict[str, Any]:
        """Validate emergency signal propagation timing."""
        terminal_1, terminal_2, terminal_3 = terminal_cluster
        terminals = {
            'terminal_1': terminal_1,
            'terminal_2': terminal_2,
            'terminal_3': terminal_3
        }

        trigger_terminal = terminals[trigger_terminal_id]

        # Record emergency trigger time
        emergency_start = time.time()

        # Trigger emergency
        await trigger_terminal.trigger_emergency_shutdown("TIMING_VALIDATION_TEST")

        # Monitor all terminals for emergency response
        response_times = {}
        max_propagation_s = max_propagation_ms / 1000.0

        async def monitor_terminal_response(terminal_id: str, terminal):
            while True:
                current_time = time.time()
                elapsed = current_time - emergency_start

                if await terminal.is_in_emergency_state():
                    response_times[terminal_id] = elapsed
                    break

                if elapsed > max_propagation_s * 2:  # Timeout at 2x max time
                    response_times[terminal_id] = float('inf')
                    break

                await asyncio.sleep(0.001)  # 1ms polling

        # Monitor all terminals concurrently
        monitor_tasks = [
            asyncio.create_task(monitor_terminal_response(tid, terminal))
            for tid, terminal in terminals.items()
        ]

        await asyncio.gather(*monitor_tasks)

        # Analyze results
        validation_result = {
            'trigger_terminal': trigger_terminal_id,
            'emergency_start_time': emergency_start,
            'max_allowed_ms': max_propagation_ms,
            'response_times_ms': {tid: rt * 1000 for tid, rt in response_times.items()},
            'all_within_limit': True,
            'violations': []
        }

        for terminal_id, response_time in response_times.items():
            response_time_ms = response_time * 1000

            measurement = TimingMeasurement(
                operation_id=f"emergency_response_{terminal_id}",
                operation_type="emergency_propagation",
                scheduled_time=emergency_start,
                actual_time=emergency_start + response_time,
                timing_error=response_time,
                precision_met=response_time <= max_propagation_s,
                metadata={
                    'terminal': terminal_id,
                    'trigger_terminal': trigger_terminal_id,
                    'response_time_ms': response_time_ms
                }
            )

            self.measurements.append(measurement)

            if response_time > max_propagation_s:
                validation_result['all_within_limit'] = False
                validation_result['violations'].append({
                    'terminal': terminal_id,
                    'response_time_ms': response_time_ms,
                    'exceeded_by_ms': response_time_ms - max_propagation_ms
                })

        return validation_result

    async def benchmark_timing_under_load(
        self,
        terminal_cluster,
        load_generator,
        benchmark_operations: List[Dict[str, Any]],
        load_duration: float = 30.0
    ) -> TimingBenchmark:
        """Benchmark timing precision under system load."""
        benchmark_start = time.time()

        # Start load generation
        load_task = asyncio.create_task(
            load_generator.generate_load(duration=load_duration)
        )

        # Execute benchmark operations
        benchmark_measurements = []

        for i, operation in enumerate(benchmark_operations):
            scheduled_time = benchmark_start + operation['delay']

            measurement = await self.measure_operation_timing(
                operation_id=f"benchmark_{i}",
                operation_type=operation['type'],
                operation_func=operation['function'],
                scheduled_time=scheduled_time,
                metadata={'benchmark_test': True, 'load_active': True}
            )

            benchmark_measurements.append(measurement)

            # Add small delay between operations
            await asyncio.sleep(0.1)

        # Stop load generation
        load_task.cancel()
        try:
            await load_task
        except asyncio.CancelledError:
            pass

        # Analyze benchmark results
        timing_errors = [m.timing_error for m in benchmark_measurements]
        measurements_within_target = sum(1 for m in benchmark_measurements if m.precision_met)

        benchmark = TimingBenchmark(
            test_name=f"load_benchmark_{int(benchmark_start)}",
            total_measurements=len(benchmark_measurements),
            precision_target_ms=self.precision_target_ms,
            measurements_within_target=measurements_within_target,
            success_rate=measurements_within_target / len(benchmark_measurements) if benchmark_measurements else 0.0,
            avg_timing_error=statistics.mean(timing_errors) if timing_errors else 0.0,
            max_timing_error=max(timing_errors) if timing_errors else 0.0,
            min_timing_error=min(timing_errors) if timing_errors else 0.0,
            std_dev_timing_error=statistics.stdev(timing_errors) if len(timing_errors) > 1 else 0.0
        )

        self.benchmarks.append(benchmark)
        return benchmark

    async def validate_plc_hardware_timing(
        self,
        terminal_1,
        hardware_simulator,
        test_operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate PLC hardware timing precision."""
        hardware_timing_results = []

        for operation in test_operations:
            operation_type = operation['type']
            scheduled_time = time.time() + operation['delay']

            # Execute PLC operation with timing measurement
            if operation_type == "read_parameter":
                async def plc_operation():
                    return await terminal_1.read_parameter(operation['parameter'])

            elif operation_type == "write_parameter":
                async def plc_operation():
                    return await terminal_1.write_parameter(
                        operation['parameter'],
                        operation['value']
                    )

            elif operation_type == "valve_control":
                async def plc_operation():
                    return await terminal_1.control_valve(
                        operation['valve_id'],
                        operation['state'],
                        operation.get('duration_ms')
                    )

            else:
                continue  # Skip unknown operations

            measurement = await self.measure_operation_timing(
                operation_id=f"plc_{operation_type}_{scheduled_time}",
                operation_type=f"plc_{operation_type}",
                operation_func=plc_operation,
                scheduled_time=scheduled_time,
                metadata={'hardware_test': True, 'operation': operation}
            )

            hardware_timing_results.append(measurement)

            await asyncio.sleep(0.05)  # Small delay between operations

        # Analyze hardware timing
        timing_errors = [m.timing_error for m in hardware_timing_results]
        precision_met_count = sum(1 for m in hardware_timing_results if m.precision_met)

        validation_result = {
            'test_type': 'plc_hardware_timing',
            'total_operations': len(hardware_timing_results),
            'precision_target_ms': self.precision_target_ms,
            'operations_within_target': precision_met_count,
            'success_rate': precision_met_count / len(hardware_timing_results) if hardware_timing_results else 0.0,
            'avg_error_ms': statistics.mean(timing_errors) * 1000 if timing_errors else 0.0,
            'max_error_ms': max(timing_errors) * 1000 if timing_errors else 0.0,
            'detailed_measurements': [
                {
                    'operation_id': m.operation_id,
                    'operation_type': m.operation_type,
                    'timing_error_ms': m.timing_error * 1000,
                    'precision_met': m.precision_met
                }
                for m in hardware_timing_results
            ]
        }

        return validation_result

    def get_timing_results(self) -> List[Dict[str, Any]]:
        """Get all timing measurement results."""
        return [
            {
                'operation_id': m.operation_id,
                'operation_type': m.operation_type,
                'scheduled_time': m.scheduled_time,
                'actual_time': m.actual_time,
                'timing_error': m.timing_error,
                'timing_error_ms': m.timing_error * 1000,
                'precision_met': m.precision_met,
                'metadata': m.metadata
            }
            for m in self.measurements
        ]

    def get_timing_statistics(self) -> Dict[str, Any]:
        """Get timing statistics summary."""
        if not self.measurements:
            return {
                'total_measurements': 0,
                'precision_target_ms': self.precision_target_ms,
                'success_rate': 0.0
            }

        timing_errors = [m.timing_error for m in self.measurements]
        precision_met_count = sum(1 for m in self.measurements if m.precision_met)

        return {
            'total_measurements': len(self.measurements),
            'precision_target_ms': self.precision_target_ms,
            'measurements_within_target': precision_met_count,
            'success_rate': precision_met_count / len(self.measurements),
            'avg_error_ms': statistics.mean(timing_errors) * 1000,
            'max_error_ms': max(timing_errors) * 1000,
            'min_error_ms': min(timing_errors) * 1000,
            'std_dev_error_ms': statistics.stdev(timing_errors) * 1000 if len(timing_errors) > 1 else 0.0,
            'percentile_95_ms': sorted([e * 1000 for e in timing_errors])[int(0.95 * len(timing_errors))] if timing_errors else 0.0,
            'percentile_99_ms': sorted([e * 1000 for e in timing_errors])[int(0.99 * len(timing_errors))] if timing_errors else 0.0
        }

    def validate_timing_requirements(
        self,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate timing against specific requirements."""
        stats = self.get_timing_statistics()

        validation_result = {
            'requirements_met': True,
            'violations': [],
            'statistics': stats
        }

        # Check success rate requirement
        if 'min_success_rate' in requirements:
            required_rate = requirements['min_success_rate']
            if stats['success_rate'] < required_rate:
                validation_result['requirements_met'] = False
                validation_result['violations'].append({
                    'requirement': 'min_success_rate',
                    'required': required_rate,
                    'actual': stats['success_rate'],
                    'violation': f"Success rate {stats['success_rate']:.3f} below required {required_rate}"
                })

        # Check maximum error requirement
        if 'max_error_ms' in requirements:
            required_max = requirements['max_error_ms']
            if stats['max_error_ms'] > required_max:
                validation_result['requirements_met'] = False
                validation_result['violations'].append({
                    'requirement': 'max_error_ms',
                    'required': required_max,
                    'actual': stats['max_error_ms'],
                    'violation': f"Maximum error {stats['max_error_ms']:.3f}ms exceeds required {required_max}ms"
                })

        # Check average error requirement
        if 'max_avg_error_ms' in requirements:
            required_avg = requirements['max_avg_error_ms']
            if stats['avg_error_ms'] > required_avg:
                validation_result['requirements_met'] = False
                validation_result['violations'].append({
                    'requirement': 'max_avg_error_ms',
                    'required': required_avg,
                    'actual': stats['avg_error_ms'],
                    'violation': f"Average error {stats['avg_error_ms']:.3f}ms exceeds required {required_avg}ms"
                })

        # Check 99th percentile requirement
        if 'max_p99_error_ms' in requirements:
            required_p99 = requirements['max_p99_error_ms']
            if stats['percentile_99_ms'] > required_p99:
                validation_result['requirements_met'] = False
                validation_result['violations'].append({
                    'requirement': 'max_p99_error_ms',
                    'required': required_p99,
                    'actual': stats['percentile_99_ms'],
                    'violation': f"99th percentile error {stats['percentile_99_ms']:.3f}ms exceeds required {required_p99}ms"
                })

        return validation_result


class LoadGenerator:
    """Generate system load for timing validation under stress."""

    def __init__(self):
        self.load_active = False
        self.load_tasks = []

    async def generate_load(self, duration: float) -> Dict[str, Any]:
        """Generate system load for specified duration."""
        self.load_active = True
        load_start = time.time()

        # CPU load task
        cpu_task = asyncio.create_task(self._cpu_load())

        # I/O load task
        io_task = asyncio.create_task(self._io_load())

        # Memory allocation task
        memory_task = asyncio.create_task(self._memory_load())

        # Network simulation task
        network_task = asyncio.create_task(self._network_load())

        self.load_tasks = [cpu_task, io_task, memory_task, network_task]

        # Run load for specified duration
        await asyncio.sleep(duration)

        # Stop load generation
        self.load_active = False
        for task in self.load_tasks:
            task.cancel()

        # Wait for tasks to complete cancellation
        await asyncio.gather(*self.load_tasks, return_exceptions=True)

        load_duration = time.time() - load_start

        return {
            'load_type': 'combined',
            'duration': load_duration,
            'tasks_executed': len(self.load_tasks),
            'status': 'completed'
        }

    async def _cpu_load(self):
        """Generate CPU load."""
        while self.load_active:
            # CPU-intensive calculation
            sum(i * i for i in range(1000))
            await asyncio.sleep(0.001)  # Brief yield

    async def _io_load(self):
        """Generate I/O load."""
        import tempfile
        import os

        while self.load_active:
            try:
                # Create temporary file operations
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write(b"load_test_data" * 100)
                    temp_path = f.name

                # Read file back
                with open(temp_path, 'rb') as f:
                    f.read()

                # Clean up
                os.unlink(temp_path)

                await asyncio.sleep(0.01)
            except Exception:
                break  # Exit on error

    async def _memory_load(self):
        """Generate memory allocation load."""
        memory_blocks = []

        while self.load_active:
            try:
                # Allocate memory blocks
                block = bytearray(10000)  # 10KB blocks
                memory_blocks.append(block)

                # Limit memory usage
                if len(memory_blocks) > 100:  # Limit to ~1MB
                    memory_blocks.pop(0)

                await asyncio.sleep(0.005)
            except Exception:
                break

    async def _network_load(self):
        """Simulate network load."""
        while self.load_active:
            try:
                # Simulate network requests with sleep
                await asyncio.sleep(0.002)  # Simulate network latency

                # Simulate data processing
                data = {"timestamp": time.time(), "data": list(range(100))}
                serialized = str(data)  # Simulate serialization

                await asyncio.sleep(0.003)
            except Exception:
                break


@pytest.fixture
def timing_validator():
    """Provide timing validator with default precision target."""
    return TimingValidator(precision_target_ms=100.0)


@pytest.fixture
def high_precision_timing_validator():
    """Provide timing validator with high precision target."""
    return TimingValidator(precision_target_ms=50.0)


@pytest.fixture
def load_generator():
    """Provide load generator for stress testing."""
    return LoadGenerator()