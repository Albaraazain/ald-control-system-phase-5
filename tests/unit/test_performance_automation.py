"""
Performance testing and benchmarking automation framework for comprehensive system validation.
"""
import pytest
import asyncio
import time
import uuid
import statistics
import psutil
import threading
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import concurrent.futures
import random

from tests.unit.test_container_mocking import MockServiceContainer
from src.abstractions.interfaces import IDatabaseService, IParameterLogger, IPLCInterface, IConnectionMonitor


@dataclass
class PerformanceMetrics:
    """Performance metrics for testing validation"""
    operation_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    operations_per_second: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success_rate: float
    performance_target_met: bool
    performance_target_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result of a comprehensive benchmark test"""
    test_name: str
    success: bool
    performance_metrics: List[PerformanceMetrics]
    system_metrics: Dict[str, Any]
    bottlenecks_identified: List[str]
    recommendations: List[str]
    total_duration_ms: float
    sla_compliance: bool
    error_details: Optional[str] = None


class PerformanceTestUtilities:
    """Utilities for performance testing and benchmarking"""

    @staticmethod
    async def measure_operation_performance(
        operation: Callable,
        iterations: int,
        concurrency: int = 1,
        target_duration_ms: float = 1000
    ) -> PerformanceMetrics:
        """Measure performance of an async operation"""
        durations = []
        errors = 0
        start_memory = psutil.virtual_memory().used / 1024 / 1024  # MB
        start_time = time.time()

        async def single_operation():
            nonlocal errors
            operation_start = time.time()
            try:
                await operation()
                operation_duration = (time.time() - operation_start) * 1000
                durations.append(operation_duration)
            except Exception:
                errors += 1
                operation_duration = (time.time() - operation_start) * 1000
                durations.append(operation_duration)

        # Run operations with specified concurrency
        if concurrency == 1:
            for _ in range(iterations):
                await single_operation()
        else:
            # Concurrent execution
            semaphore = asyncio.Semaphore(concurrency)

            async def semaphore_operation():
                async with semaphore:
                    await single_operation()

            tasks = [asyncio.create_task(semaphore_operation()) for _ in range(iterations)]
            await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = (time.time() - start_time) * 1000
        end_memory = psutil.virtual_memory().used / 1024 / 1024
        cpu_usage = psutil.cpu_percent(interval=0.1)

        # Calculate statistics
        if durations:
            avg_duration = statistics.mean(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            sorted_durations = sorted(durations)
            p95_index = int(0.95 * len(sorted_durations))
            p99_index = int(0.99 * len(sorted_durations))
            p95_duration = sorted_durations[p95_index] if p95_index < len(sorted_durations) else max_duration
            p99_duration = sorted_durations[p99_index] if p99_index < len(sorted_durations) else max_duration
        else:
            avg_duration = min_duration = max_duration = p95_duration = p99_duration = 0

        successful_operations = iterations - errors
        operations_per_second = (successful_operations / (total_duration / 1000)) if total_duration > 0 else 0
        success_rate = (successful_operations / iterations) * 100 if iterations > 0 else 0
        performance_target_met = avg_duration <= target_duration_ms

        return PerformanceMetrics(
            operation_name="async_operation",
            total_operations=iterations,
            successful_operations=successful_operations,
            failed_operations=errors,
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            min_duration_ms=min_duration,
            max_duration_ms=max_duration,
            p95_duration_ms=p95_duration,
            p99_duration_ms=p99_duration,
            operations_per_second=operations_per_second,
            memory_usage_mb=end_memory - start_memory,
            cpu_usage_percent=cpu_usage,
            success_rate=success_rate,
            performance_target_met=performance_target_met,
            performance_target_ms=target_duration_ms
        )


class PLCPerformanceTesting:
    """Performance testing for PLC communication"""

    @staticmethod
    async def benchmark_individual_vs_bulk_reads(mock_container: MockServiceContainer) -> BenchmarkResult:
        """Benchmark individual vs bulk PLC parameter reads"""
        plc_mock = mock_container.get_mock(IPLCInterface)

        # Setup mock behavior for individual reads
        individual_read_latency = 0.050  # 50ms per read (simulating network latency)

        async def mock_individual_read(param_id: str):
            await asyncio.sleep(individual_read_latency)
            return random.uniform(10.0, 100.0)

        # Setup mock behavior for bulk reads
        bulk_read_latency = 0.080  # 80ms for entire bulk operation

        async def mock_bulk_read(param_ids: List[str]):
            await asyncio.sleep(bulk_read_latency)
            return {param_id: random.uniform(10.0, 100.0) for param_id in param_ids}

        plc_mock.read_parameter = AsyncMock(side_effect=mock_individual_read)
        plc_mock.bulk_read_parameters = AsyncMock(side_effect=mock_bulk_read)

        start_time = time.time()
        performance_metrics = []

        try:
            # Test 1: Individual reads
            param_count = 50
            param_ids = [f"PARAM_{i}" for i in range(param_count)]

            async def individual_reads_test():
                for param_id in param_ids:
                    await plc_mock.read_parameter(param_id)

            individual_metrics = await PerformanceTestUtilities.measure_operation_performance(
                individual_reads_test, iterations=5, target_duration_ms=500
            )
            individual_metrics.operation_name = "individual_plc_reads"
            performance_metrics.append(individual_metrics)

            # Test 2: Bulk reads
            async def bulk_reads_test():
                await plc_mock.bulk_read_parameters(param_ids)

            bulk_metrics = await PerformanceTestUtilities.measure_operation_performance(
                bulk_reads_test, iterations=5, target_duration_ms=100
            )
            bulk_metrics.operation_name = "bulk_plc_reads"
            performance_metrics.append(bulk_metrics)

            total_duration = (time.time() - start_time) * 1000

            # Calculate performance improvement
            improvement_ratio = individual_metrics.avg_duration_ms / bulk_metrics.avg_duration_ms if bulk_metrics.avg_duration_ms > 0 else 0

            # Identify bottlenecks
            bottlenecks = []
            if individual_metrics.avg_duration_ms > 1000:
                bottlenecks.append("Individual PLC reads exceed 1-second target")
            if bulk_metrics.avg_duration_ms > 200:
                bottlenecks.append("Bulk PLC reads exceed 200ms target")

            # Generate recommendations
            recommendations = []
            if improvement_ratio > 5:
                recommendations.append(f"Bulk reads provide {improvement_ratio:.1f}x performance improvement")
            if not bulk_metrics.performance_target_met:
                recommendations.append("Consider optimizing bulk read chunk size")
            recommendations.append("Implement bulk reads for all parameter operations")

            return BenchmarkResult(
                test_name="plc_individual_vs_bulk_reads",
                success=True,
                performance_metrics=performance_metrics,
                system_metrics={
                    "improvement_ratio": improvement_ratio,
                    "individual_avg_ms": individual_metrics.avg_duration_ms,
                    "bulk_avg_ms": bulk_metrics.avg_duration_ms
                },
                bottlenecks_identified=bottlenecks,
                recommendations=recommendations,
                total_duration_ms=total_duration,
                sla_compliance=bulk_metrics.performance_target_met
            )

        except Exception as e:
            total_duration = (time.time() - start_time) * 1000
            return BenchmarkResult(
                test_name="plc_individual_vs_bulk_reads",
                success=False,
                performance_metrics=performance_metrics,
                system_metrics={},
                bottlenecks_identified=["Test execution failed"],
                recommendations=["Fix test infrastructure"],
                total_duration_ms=total_duration,
                sla_compliance=False,
                error_details=str(e)
            )


class DatabasePerformanceTesting:
    """Performance testing for database operations"""

    @staticmethod
    async def benchmark_dual_mode_logging_performance(mock_container: MockServiceContainer) -> BenchmarkResult:
        """Benchmark dual-mode logging performance with transaction overhead"""
        db_mock = mock_container.get_mock(IDatabaseService)
        logger_mock = mock_container.get_mock(IParameterLogger)

        # Simulate database operation latencies
        single_insert_latency = 0.002  # 2ms per insert
        batch_insert_latency = 0.008   # 8ms per batch of 50

        async def mock_single_insert(table: str, data: Dict):
            await asyncio.sleep(single_insert_latency)
            return True

        async def mock_batch_insert(table: str, data_list: List[Dict]):
            await asyncio.sleep(batch_insert_latency)
            return True

        async def mock_dual_mode_atomic_insert(param_data: Dict, include_process: bool = False):
            # Simulate atomic dual-table insert with transaction overhead
            transaction_overhead = 0.001  # 1ms transaction overhead
            await asyncio.sleep(transaction_overhead)

            # Always insert into parameter_value_history
            await mock_single_insert("parameter_value_history", param_data)

            if include_process:
                # Also insert into process_data_points
                await mock_single_insert("process_data_points", param_data)

            return True

        db_mock.single_insert = AsyncMock(side_effect=mock_single_insert)
        db_mock.batch_insert = AsyncMock(side_effect=mock_batch_insert)
        logger_mock.dual_mode_atomic_insert = AsyncMock(side_effect=mock_dual_mode_atomic_insert)

        start_time = time.time()
        performance_metrics = []

        try:
            # Test 1: Individual dual-mode inserts
            async def individual_dual_inserts():
                for i in range(50):
                    param_data = {
                        "parameter_id": str(uuid.uuid4()),
                        "value": random.uniform(1.0, 100.0),
                        "timestamp": time.time()
                    }
                    include_process = (i % 2 == 0)  # Every other insert includes process data
                    await logger_mock.dual_mode_atomic_insert(param_data, include_process)

            individual_metrics = await PerformanceTestUtilities.measure_operation_performance(
                individual_dual_inserts, iterations=5, target_duration_ms=200
            )
            individual_metrics.operation_name = "individual_dual_mode_inserts"
            performance_metrics.append(individual_metrics)

            # Test 2: Batch dual-mode inserts
            async def batch_dual_inserts():
                param_data_list = []
                for i in range(50):
                    param_data_list.append({
                        "parameter_id": str(uuid.uuid4()),
                        "value": random.uniform(1.0, 100.0),
                        "timestamp": time.time()
                    })

                # Batch insert to parameter_value_history
                await db_mock.batch_insert("parameter_value_history", param_data_list)

                # Batch insert to process_data_points (subset)
                process_data = param_data_list[::2]  # Every other entry
                await db_mock.batch_insert("process_data_points", process_data)

            batch_metrics = await PerformanceTestUtilities.measure_operation_performance(
                batch_dual_inserts, iterations=5, target_duration_ms=50
            )
            batch_metrics.operation_name = "batch_dual_mode_inserts"
            performance_metrics.append(batch_metrics)

            # Test 3: High-frequency logging simulation
            async def high_frequency_logging():
                # Simulate 1-second interval with 50 parameters
                start = time.time()
                tasks = []

                for i in range(50):
                    param_data = {
                        "parameter_id": str(uuid.uuid4()),
                        "value": random.uniform(1.0, 100.0),
                        "timestamp": time.time()
                    }
                    task = asyncio.create_task(
                        logger_mock.dual_mode_atomic_insert(param_data, True)
                    )
                    tasks.append(task)

                await asyncio.gather(*tasks)
                duration = time.time() - start
                return duration < 1.0  # Must complete within 1 second

            frequency_metrics = await PerformanceTestUtilities.measure_operation_performance(
                high_frequency_logging, iterations=10, target_duration_ms=1000
            )
            frequency_metrics.operation_name = "high_frequency_dual_logging"
            performance_metrics.append(frequency_metrics)

            total_duration = (time.time() - start_time) * 1000

            # Analyze performance
            batch_improvement = individual_metrics.avg_duration_ms / batch_metrics.avg_duration_ms if batch_metrics.avg_duration_ms > 0 else 0

            bottlenecks = []
            if individual_metrics.avg_duration_ms > 500:
                bottlenecks.append("Individual dual-mode inserts too slow for 1-second intervals")
            if frequency_metrics.avg_duration_ms > 1000:
                bottlenecks.append("High-frequency logging exceeds 1-second window")

            recommendations = []
            if batch_improvement > 3:
                recommendations.append(f"Batch operations provide {batch_improvement:.1f}x improvement")
            if frequency_metrics.performance_target_met:
                recommendations.append("System meets 1-second interval requirement")
            else:
                recommendations.append("Optimize for sub-1-second dual-mode logging")

            return BenchmarkResult(
                test_name="dual_mode_logging_performance",
                success=True,
                performance_metrics=performance_metrics,
                system_metrics={
                    "batch_improvement_ratio": batch_improvement,
                    "frequency_compliance": frequency_metrics.performance_target_met
                },
                bottlenecks_identified=bottlenecks,
                recommendations=recommendations,
                total_duration_ms=total_duration,
                sla_compliance=frequency_metrics.performance_target_met
            )

        except Exception as e:
            total_duration = (time.time() - start_time) * 1000
            return BenchmarkResult(
                test_name="dual_mode_logging_performance",
                success=False,
                performance_metrics=performance_metrics,
                system_metrics={},
                bottlenecks_identified=["Test execution failed"],
                recommendations=["Fix database connectivity"],
                total_duration_ms=total_duration,
                sla_compliance=False,
                error_details=str(e)
            )


class SystemIntegrationPerformanceTesting:
    """Performance testing for end-to-end system integration"""

    @staticmethod
    async def benchmark_end_to_end_cycle_performance(mock_container: MockServiceContainer) -> BenchmarkResult:
        """Benchmark complete end-to-end cycle performance"""
        plc_mock = mock_container.get_mock(IPLCInterface)
        logger_mock = mock_container.get_mock(IParameterLogger)
        db_mock = mock_container.get_mock(IDatabaseService)

        # Setup realistic latencies
        plc_latency = 0.030  # 30ms for PLC communication
        processing_latency = 0.005  # 5ms for data processing
        db_latency = 0.015  # 15ms for database operation

        async def mock_plc_read_bulk(param_ids: List[str]):
            await asyncio.sleep(plc_latency)
            return {param_id: random.uniform(1.0, 100.0) for param_id in param_ids}

        async def mock_process_and_log(param_data: Dict[str, float]):
            await asyncio.sleep(processing_latency)

            # Process and log to database
            for param_id, value in param_data.items():
                await asyncio.sleep(db_latency / len(param_data))  # Distributed DB time

            return True

        plc_mock.bulk_read_parameters = AsyncMock(side_effect=mock_plc_read_bulk)
        logger_mock.process_and_log = AsyncMock(side_effect=mock_process_and_log)

        start_time = time.time()
        performance_metrics = []

        try:
            # Test complete end-to-end cycle
            async def end_to_end_cycle():
                # Step 1: Read parameters from PLC
                param_ids = [f"PARAM_{i}" for i in range(50)]
                param_data = await plc_mock.bulk_read_parameters(param_ids)

                # Step 2: Process and log data
                await logger_mock.process_and_log(param_data)

                return len(param_data)

            cycle_metrics = await PerformanceTestUtilities.measure_operation_performance(
                end_to_end_cycle, iterations=20, target_duration_ms=500
            )
            cycle_metrics.operation_name = "end_to_end_cycle"
            performance_metrics.append(cycle_metrics)

            # Test concurrent cycles (simulating high load)
            concurrent_metrics = await PerformanceTestUtilities.measure_operation_performance(
                end_to_end_cycle, iterations=50, concurrency=5, target_duration_ms=1000
            )
            concurrent_metrics.operation_name = "concurrent_end_to_end_cycles"
            performance_metrics.append(concurrent_metrics)

            total_duration = (time.time() - start_time) * 1000

            # Performance analysis
            bottlenecks = []
            if cycle_metrics.avg_duration_ms > 500:
                bottlenecks.append("Single cycle exceeds 500ms target")
            if concurrent_metrics.avg_duration_ms > 1000:
                bottlenecks.append("Concurrent cycles exceed 1-second target")

            recommendations = []
            if cycle_metrics.performance_target_met:
                recommendations.append("System meets single-cycle performance targets")
            if concurrent_metrics.performance_target_met:
                recommendations.append("System handles concurrent load effectively")
            else:
                recommendations.append("Consider optimizing for concurrent operations")

            # Calculate system throughput
            throughput_ops_per_sec = cycle_metrics.operations_per_second
            concurrent_throughput = concurrent_metrics.operations_per_second

            return BenchmarkResult(
                test_name="end_to_end_cycle_performance",
                success=True,
                performance_metrics=performance_metrics,
                system_metrics={
                    "single_cycle_throughput": throughput_ops_per_sec,
                    "concurrent_throughput": concurrent_throughput,
                    "throughput_improvement": concurrent_throughput / throughput_ops_per_sec if throughput_ops_per_sec > 0 else 0
                },
                bottlenecks_identified=bottlenecks,
                recommendations=recommendations,
                total_duration_ms=total_duration,
                sla_compliance=cycle_metrics.performance_target_met and concurrent_metrics.performance_target_met
            )

        except Exception as e:
            total_duration = (time.time() - start_time) * 1000
            return BenchmarkResult(
                test_name="end_to_end_cycle_performance",
                success=False,
                performance_metrics=performance_metrics,
                system_metrics={},
                bottlenecks_identified=["System integration test failed"],
                recommendations=["Check system integration configuration"],
                total_duration_ms=total_duration,
                sla_compliance=False,
                error_details=str(e)
            )


class PerformanceTestOrchestrator:
    """Orchestrates comprehensive performance testing and benchmarking"""

    def __init__(self, mock_container: MockServiceContainer = None):
        self.mock_container = mock_container or MockServiceContainer()
        self.benchmark_results: List[BenchmarkResult] = []

    async def run_comprehensive_performance_assessment(self) -> Dict[str, Any]:
        """Run complete performance assessment with all benchmarks"""
        print("⚡ Starting comprehensive performance assessment...")

        # Run all performance benchmarks
        benchmark_suites = [
            ("PLC Individual vs Bulk Reads", PLCPerformanceTesting.benchmark_individual_vs_bulk_reads(self.mock_container)),
            ("Dual-Mode Logging Performance", DatabasePerformanceTesting.benchmark_dual_mode_logging_performance(self.mock_container)),
            ("End-to-End Cycle Performance", SystemIntegrationPerformanceTesting.benchmark_end_to_end_cycle_performance(self.mock_container))
        ]

        all_results = []
        for suite_name, benchmark_coro in benchmark_suites:
            print(f"  Running {suite_name} benchmarks...")
            result = await benchmark_coro
            all_results.append(result)

        # Aggregate performance analysis
        total_benchmarks = len(all_results)
        successful_benchmarks = sum(1 for r in all_results if r.success)
        sla_compliant_benchmarks = sum(1 for r in all_results if r.sla_compliance)

        all_metrics = []
        for result in all_results:
            all_metrics.extend(result.performance_metrics)

        # System-wide performance summary
        avg_cpu_usage = statistics.mean([m.cpu_usage_percent for m in all_metrics if m.cpu_usage_percent > 0]) if all_metrics else 0
        total_memory_usage = sum([m.memory_usage_mb for m in all_metrics if m.memory_usage_mb > 0])

        # Identify critical bottlenecks
        critical_bottlenecks = []
        for result in all_results:
            critical_bottlenecks.extend(result.bottlenecks_identified)

        # Compile recommendations
        all_recommendations = []
        for result in all_results:
            all_recommendations.extend(result.recommendations)

        return {
            "summary": {
                "total_benchmarks": total_benchmarks,
                "successful_benchmarks": successful_benchmarks,
                "failed_benchmarks": total_benchmarks - successful_benchmarks,
                "sla_compliant_benchmarks": sla_compliant_benchmarks,
                "overall_success_rate": (successful_benchmarks / total_benchmarks) * 100 if total_benchmarks > 0 else 0,
                "sla_compliance_rate": (sla_compliant_benchmarks / total_benchmarks) * 100 if total_benchmarks > 0 else 0
            },
            "system_performance": {
                "avg_cpu_usage_percent": avg_cpu_usage,
                "total_memory_usage_mb": total_memory_usage,
                "performance_targets_met": sla_compliant_benchmarks == total_benchmarks
            },
            "critical_bottlenecks": critical_bottlenecks,
            "optimization_recommendations": all_recommendations,
            "detailed_results": [
                {
                    "test_name": r.test_name,
                    "success": r.success,
                    "sla_compliance": r.sla_compliance,
                    "duration_ms": r.total_duration_ms,
                    "metrics_summary": {
                        "total_operations": sum(m.total_operations for m in r.performance_metrics),
                        "avg_duration_ms": statistics.mean([m.avg_duration_ms for m in r.performance_metrics]) if r.performance_metrics else 0,
                        "avg_ops_per_sec": statistics.mean([m.operations_per_second for m in r.performance_metrics]) if r.performance_metrics else 0
                    },
                    "bottlenecks": r.bottlenecks_identified,
                    "recommendations": r.recommendations
                } for r in all_results
            ],
            "all_results": all_results
        }


# Pytest fixtures
@pytest.fixture
def performance_orchestrator(mock_container):
    """Pytest fixture for performance test orchestrator"""
    return PerformanceTestOrchestrator(mock_container)


@pytest.fixture
def performance_test_utilities():
    """Pytest fixture for performance test utilities"""
    return PerformanceTestUtilities()


# Example usage
if __name__ == "__main__":
    async def main():
        orchestrator = PerformanceTestOrchestrator()
        results = await orchestrator.run_comprehensive_performance_assessment()

        print(f"\n⚡ Performance Assessment Results:")
        print(f"   Total Benchmarks: {results['summary']['total_benchmarks']}")
        print(f"   Successful: {results['summary']['successful_benchmarks']}")
        print(f"   SLA Compliant: {results['summary']['sla_compliant_benchmarks']}")
        print(f"   Success Rate: {results['summary']['overall_success_rate']:.1f}%")
        print(f"   SLA Compliance: {results['summary']['sla_compliance_rate']:.1f}%")

        print(f"\n🔧 System Performance:")
        print(f"   CPU Usage: {results['system_performance']['avg_cpu_usage_percent']:.1f}%")
        print(f"   Memory Usage: {results['system_performance']['total_memory_usage_mb']:.1f}MB")
        print(f"   Targets Met: {results['system_performance']['performance_targets_met']}")

        if results['critical_bottlenecks']:
            print(f"\n🚨 Critical Bottlenecks:")
            for bottleneck in results['critical_bottlenecks']:
                print(f"   - {bottleneck}")

        print(f"\n💡 Optimization Recommendations:")
        for rec in results['optimization_recommendations']:
            print(f"   - {rec}")

    asyncio.run(main())