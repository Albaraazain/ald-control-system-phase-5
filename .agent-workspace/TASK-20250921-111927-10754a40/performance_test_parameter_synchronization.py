#!/usr/bin/env python3
"""
Performance Test Suite for Parameter Synchronization

This module provides comprehensive performance testing for the parameter table
synchronization feature, measuring the impact of adding component_parameters
current_value and set_value updates to the existing dual-mode logging system.

Test Categories:
1. Baseline Performance Measurement
2. Synchronization Performance Impact
3. Stress Testing and Scalability
4. Transaction Deadlock Prevention
5. Memory Usage Analysis
"""

import asyncio
import time
import statistics
import threading
import psutil
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import random

from src.log_setup import logger
from src.db import get_supabase
from src.data_collection.transactional.interfaces import ParameterData, MachineState
from src.data_collection.transactional.dual_mode_repository import dual_mode_repository


@dataclass
class PerformanceMetrics:
    """Performance metrics for a test run."""
    operation_name: str
    total_operations: int
    total_duration_seconds: float
    operations_per_second: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_count: int
    success_rate: float


@dataclass
class TestConfiguration:
    """Configuration for performance tests."""
    test_name: str
    parameter_count: int
    batch_size: int
    test_duration_seconds: int
    concurrent_operations: int
    with_synchronization: bool
    stress_test_multiplier: float = 1.0


class ParameterSynchronizationPerformanceTester:
    """
    Comprehensive performance tester for parameter synchronization.

    Tests the performance impact of adding component_parameters.current_value
    updates to the existing dual-mode parameter logging system.
    """

    def __init__(self):
        """Initialize the performance tester."""
        self.test_results: List[PerformanceMetrics] = []
        self.test_data_cleanup_ids: List[str] = []
        self.baseline_metrics: Optional[PerformanceMetrics] = None

    async def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """
        Run the complete performance test suite.

        Returns:
            Dict with all test results and analysis
        """
        logger.info("🚀 Starting Comprehensive Parameter Synchronization Performance Test Suite")

        start_time = time.time()

        try:
            # 1. Baseline Performance Testing
            logger.info("📊 Phase 1: Baseline Performance Testing")
            baseline_results = await self._run_baseline_tests()

            # 2. Synchronization Impact Testing
            logger.info("🔄 Phase 2: Synchronization Performance Impact Testing")
            sync_results = await self._run_synchronization_impact_tests()

            # 3. Stress Testing
            logger.info("💪 Phase 3: Stress Testing and Scalability")
            stress_results = await self._run_stress_tests()

            # 4. Concurrent Operations Testing
            logger.info("🔀 Phase 4: Concurrent Operations Testing")
            concurrent_results = await self._run_concurrent_tests()

            # 5. Transaction Deadlock Testing
            logger.info("🔒 Phase 5: Transaction Deadlock Prevention Testing")
            deadlock_results = await self._run_deadlock_prevention_tests()

            # 6. Memory Usage Analysis
            logger.info("💾 Phase 6: Memory Usage Analysis")
            memory_results = await self._run_memory_analysis_tests()

            # Compile final results
            total_duration = time.time() - start_time

            final_results = {
                'test_suite_summary': {
                    'total_duration_seconds': total_duration,
                    'total_tests_run': len(self.test_results),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                'baseline_performance': baseline_results,
                'synchronization_impact': sync_results,
                'stress_testing': stress_results,
                'concurrent_operations': concurrent_results,
                'deadlock_prevention': deadlock_results,
                'memory_analysis': memory_results,
                'performance_analysis': self._analyze_performance_impact(),
                'recommendations': self._generate_recommendations()
            }

            logger.info("✅ Performance test suite completed successfully")
            return final_results

        except Exception as e:
            logger.error(f"❌ Performance test suite failed: {e}", exc_info=True)
            raise
        finally:
            # Cleanup test data
            await self._cleanup_test_data()

    async def _run_baseline_tests(self) -> Dict[str, Any]:
        """Run baseline performance tests without synchronization."""

        test_configs = [
            TestConfiguration(
                test_name="baseline_normal_load",
                parameter_count=84,  # Current system spec
                batch_size=50,
                test_duration_seconds=60,
                concurrent_operations=1,
                with_synchronization=False
            ),
            TestConfiguration(
                test_name="baseline_high_frequency",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=False,
                stress_test_multiplier=2.0
            ),
            TestConfiguration(
                test_name="baseline_large_batch",
                parameter_count=200,
                batch_size=100,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=False
            )
        ]

        results = {}
        for config in test_configs:
            logger.info(f"Running baseline test: {config.test_name}")
            metrics = await self._run_single_performance_test(config)
            results[config.test_name] = metrics.__dict__

            # Store the normal load as baseline for comparison
            if config.test_name == "baseline_normal_load":
                self.baseline_metrics = metrics

        return results

    async def _run_synchronization_impact_tests(self) -> Dict[str, Any]:
        """Test performance impact of adding synchronization."""

        test_configs = [
            TestConfiguration(
                test_name="sync_normal_load",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=60,
                concurrent_operations=1,
                with_synchronization=True
            ),
            TestConfiguration(
                test_name="sync_high_frequency",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=True,
                stress_test_multiplier=2.0
            ),
            TestConfiguration(
                test_name="sync_large_batch",
                parameter_count=200,
                batch_size=100,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=True
            )
        ]

        results = {}
        for config in test_configs:
            logger.info(f"Running synchronization test: {config.test_name}")
            metrics = await self._run_single_performance_test(config)
            results[config.test_name] = metrics.__dict__

        return results

    async def _run_stress_tests(self) -> Dict[str, Any]:
        """Run stress tests to find breaking points."""

        stress_configs = [
            TestConfiguration(
                test_name="stress_high_parameter_count",
                parameter_count=500,
                batch_size=50,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=True,
                stress_test_multiplier=3.0
            ),
            TestConfiguration(
                test_name="stress_large_batches",
                parameter_count=84,
                batch_size=200,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=True,
                stress_test_multiplier=2.0
            ),
            TestConfiguration(
                test_name="stress_sustained_load",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=300,  # 5 minutes
                concurrent_operations=1,
                with_synchronization=True
            )
        ]

        results = {}
        for config in stress_configs:
            logger.info(f"Running stress test: {config.test_name}")
            try:
                metrics = await self._run_single_performance_test(config)
                results[config.test_name] = metrics.__dict__
            except Exception as e:
                logger.error(f"Stress test {config.test_name} failed: {e}")
                results[config.test_name] = {"error": str(e), "failed": True}

        return results

    async def _run_concurrent_tests(self) -> Dict[str, Any]:
        """Test concurrent operations and potential race conditions."""

        concurrent_configs = [
            TestConfiguration(
                test_name="concurrent_2_operations",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=60,
                concurrent_operations=2,
                with_synchronization=True
            ),
            TestConfiguration(
                test_name="concurrent_5_operations",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=60,
                concurrent_operations=5,
                with_synchronization=True
            ),
            TestConfiguration(
                test_name="concurrent_10_operations",
                parameter_count=84,
                batch_size=50,
                test_duration_seconds=30,
                concurrent_operations=10,
                with_synchronization=True
            )
        ]

        results = {}
        for config in concurrent_configs:
            logger.info(f"Running concurrent test: {config.test_name}")
            try:
                metrics = await self._run_concurrent_performance_test(config)
                results[config.test_name] = metrics.__dict__
            except Exception as e:
                logger.error(f"Concurrent test {config.test_name} failed: {e}")
                results[config.test_name] = {"error": str(e), "failed": True}

        return results

    async def _run_deadlock_prevention_tests(self) -> Dict[str, Any]:
        """Test transaction deadlock scenarios."""

        logger.info("Testing transaction deadlock prevention scenarios")

        results = {
            "deadlock_test_summary": "Transaction deadlock prevention testing",
            "test_scenarios": []
        }

        # Scenario 1: Concurrent updates to same parameters
        scenario_1_result = await self._test_concurrent_parameter_updates()
        results["test_scenarios"].append({
            "name": "concurrent_same_parameters",
            "result": scenario_1_result
        })

        # Scenario 2: Mixed read/write operations
        scenario_2_result = await self._test_mixed_read_write_operations()
        results["test_scenarios"].append({
            "name": "mixed_read_write_operations",
            "result": scenario_2_result
        })

        return results

    async def _run_memory_analysis_tests(self) -> Dict[str, Any]:
        """Analyze memory usage patterns."""

        logger.info("Running memory usage analysis")

        # Test with increasing batch sizes
        batch_sizes = [10, 50, 100, 200, 500]
        memory_results = []

        for batch_size in batch_sizes:
            config = TestConfiguration(
                test_name=f"memory_test_batch_{batch_size}",
                parameter_count=84,
                batch_size=batch_size,
                test_duration_seconds=30,
                concurrent_operations=1,
                with_synchronization=True
            )

            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
            metrics = await self._run_single_performance_test(config)
            peak_memory = metrics.memory_usage_mb

            memory_results.append({
                "batch_size": batch_size,
                "initial_memory_mb": initial_memory,
                "peak_memory_mb": peak_memory,
                "memory_increase_mb": peak_memory - initial_memory,
                "operations_per_second": metrics.operations_per_second
            })

        return {
            "memory_scaling_analysis": memory_results,
            "memory_efficiency_recommendations": self._analyze_memory_efficiency(memory_results)
        }

    async def _run_single_performance_test(self, config: TestConfiguration) -> PerformanceMetrics:
        """Run a single performance test with the given configuration."""

        logger.info(f"Starting performance test: {config.test_name}")

        # Generate test parameters
        test_parameters = self._generate_test_parameters(config.parameter_count)

        # Track performance metrics
        latencies = []
        error_count = 0
        operations_completed = 0

        # Monitor system resources
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        start_time = time.time()
        end_time = start_time + config.test_duration_seconds

        while time.time() < end_time:
            operation_start = time.time()

            try:
                # Create machine state
                machine_state = MachineState(
                    is_processing=True,
                    current_process_id=str(uuid.uuid4())
                )

                # Simulate parameter logging operation
                batch = test_parameters[:config.batch_size]

                if config.with_synchronization:
                    # Use the new synchronization-enabled dual mode repository
                    result = await dual_mode_repository.insert_dual_mode_atomic(
                        batch, machine_state
                    )

                    if not result.success:
                        error_count += 1
                        logger.warning(f"Operation failed: {result.error_message}")
                else:
                    # Use history-only mode (baseline)
                    await dual_mode_repository.insert_history_only(batch)

                operations_completed += 1

                # Apply stress test multiplier
                if config.stress_test_multiplier > 1.0:
                    await asyncio.sleep(1.0 / config.stress_test_multiplier)

            except Exception as e:
                error_count += 1
                logger.error(f"Test operation failed: {e}")

            operation_end = time.time()
            latency_ms = (operation_end - operation_start) * 1000
            latencies.append(latency_ms)

        total_duration = time.time() - start_time

        # Calculate system resource usage
        current_memory = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent()

        # Calculate performance metrics
        if latencies:
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max_latency
            p99_latency = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max_latency
        else:
            avg_latency = min_latency = max_latency = p95_latency = p99_latency = 0

        operations_per_second = operations_completed / total_duration if total_duration > 0 else 0
        success_rate = (operations_completed - error_count) / operations_completed if operations_completed > 0 else 0

        metrics = PerformanceMetrics(
            operation_name=config.test_name,
            total_operations=operations_completed,
            total_duration_seconds=total_duration,
            operations_per_second=operations_per_second,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            memory_usage_mb=current_memory,
            cpu_usage_percent=cpu_percent,
            error_count=error_count,
            success_rate=success_rate
        )

        self.test_results.append(metrics)

        logger.info(f"Test {config.test_name} completed: {operations_per_second:.2f} ops/sec, "
                   f"{avg_latency:.2f}ms avg latency, {success_rate:.2%} success rate")

        return metrics

    async def _run_concurrent_performance_test(self, config: TestConfiguration) -> PerformanceMetrics:
        """Run concurrent performance test with multiple async tasks."""

        logger.info(f"Starting concurrent test: {config.test_name} with {config.concurrent_operations} operations")

        # Create tasks for concurrent execution
        tasks = []
        for i in range(config.concurrent_operations):
            # Create a modified config for each concurrent task
            task_config = TestConfiguration(
                test_name=f"{config.test_name}_task_{i}",
                parameter_count=config.parameter_count,
                batch_size=config.batch_size,
                test_duration_seconds=config.test_duration_seconds,
                concurrent_operations=1,
                with_synchronization=config.with_synchronization
            )

            task = asyncio.create_task(self._run_single_performance_test(task_config))
            tasks.append(task)

        # Run all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time

        # Aggregate results
        successful_results = [r for r in results if isinstance(r, PerformanceMetrics)]
        failed_count = len(results) - len(successful_results)

        if successful_results:
            # Aggregate metrics
            total_operations = sum(r.total_operations for r in successful_results)
            total_errors = sum(r.error_count for r in successful_results)
            avg_ops_per_sec = sum(r.operations_per_second for r in successful_results) / len(successful_results)
            avg_latency = sum(r.avg_latency_ms for r in successful_results) / len(successful_results)
            max_memory = max(r.memory_usage_mb for r in successful_results)
            avg_cpu = sum(r.cpu_usage_percent for r in successful_results) / len(successful_results)

            return PerformanceMetrics(
                operation_name=config.test_name,
                total_operations=total_operations,
                total_duration_seconds=total_duration,
                operations_per_second=avg_ops_per_sec,
                avg_latency_ms=avg_latency,
                min_latency_ms=min(r.min_latency_ms for r in successful_results),
                max_latency_ms=max(r.max_latency_ms for r in successful_results),
                p95_latency_ms=statistics.mean([r.p95_latency_ms for r in successful_results]),
                p99_latency_ms=statistics.mean([r.p99_latency_ms for r in successful_results]),
                memory_usage_mb=max_memory,
                cpu_usage_percent=avg_cpu,
                error_count=total_errors + failed_count,
                success_rate=(total_operations - total_errors) / total_operations if total_operations > 0 else 0
            )
        else:
            raise RuntimeError(f"All concurrent tasks failed for test {config.test_name}")

    async def _test_concurrent_parameter_updates(self) -> Dict[str, Any]:
        """Test concurrent updates to the same parameters for deadlock detection."""

        logger.info("Testing concurrent updates to same parameters")

        # Use same parameter IDs across all operations
        shared_parameters = self._generate_test_parameters(10)  # Small set for collision

        async def concurrent_update_task(task_id: int) -> Dict[str, Any]:
            try:
                machine_state = MachineState(
                    is_processing=True,
                    current_process_id=f"test_process_{task_id}"
                )

                start_time = time.time()
                result = await dual_mode_repository.insert_dual_mode_atomic(
                    shared_parameters, machine_state
                )
                duration = time.time() - start_time

                return {
                    "task_id": task_id,
                    "success": result.success,
                    "duration_ms": duration * 1000,
                    "error": result.error_message if not result.success else None
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "success": False,
                    "duration_ms": -1,
                    "error": str(e)
                }

        # Run 10 concurrent tasks
        tasks = [concurrent_update_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        successful_tasks = [r for r in results if r["success"]]
        failed_tasks = [r for r in results if not r["success"]]

        return {
            "total_tasks": len(tasks),
            "successful_tasks": len(successful_tasks),
            "failed_tasks": len(failed_tasks),
            "success_rate": len(successful_tasks) / len(tasks),
            "avg_duration_ms": statistics.mean([r["duration_ms"] for r in successful_tasks]) if successful_tasks else 0,
            "deadlocks_detected": len([r for r in failed_tasks if "deadlock" in r.get("error", "").lower()]),
            "task_results": results
        }

    async def _test_mixed_read_write_operations(self) -> Dict[str, Any]:
        """Test mixed read/write operations for race condition detection."""

        logger.info("Testing mixed read/write operations")

        parameters = self._generate_test_parameters(50)

        async def read_operation(task_id: int) -> Dict[str, Any]:
            try:
                # Simulate reading parameter values
                supabase = get_supabase()
                start_time = time.time()

                result = supabase.table('component_parameters').select(
                    'id, current_value, set_value'
                ).limit(50).execute()

                duration = time.time() - start_time

                return {
                    "task_id": task_id,
                    "operation_type": "read",
                    "success": True,
                    "duration_ms": duration * 1000,
                    "records_read": len(result.data) if result.data else 0
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "operation_type": "read",
                    "success": False,
                    "duration_ms": -1,
                    "error": str(e)
                }

        async def write_operation(task_id: int) -> Dict[str, Any]:
            try:
                machine_state = MachineState(
                    is_processing=True,
                    current_process_id=f"mixed_test_process_{task_id}"
                )

                start_time = time.time()
                result = await dual_mode_repository.insert_dual_mode_atomic(
                    parameters[:10], machine_state
                )
                duration = time.time() - start_time

                return {
                    "task_id": task_id,
                    "operation_type": "write",
                    "success": result.success,
                    "duration_ms": duration * 1000,
                    "error": result.error_message if not result.success else None
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "operation_type": "write",
                    "success": False,
                    "duration_ms": -1,
                    "error": str(e)
                }

        # Mix of read and write operations
        tasks = []
        for i in range(20):
            if i % 2 == 0:
                tasks.append(read_operation(i))
            else:
                tasks.append(write_operation(i))

        results = await asyncio.gather(*tasks)

        read_results = [r for r in results if r["operation_type"] == "read"]
        write_results = [r for r in results if r["operation_type"] == "write"]

        return {
            "total_operations": len(results),
            "read_operations": {
                "count": len(read_results),
                "successful": len([r for r in read_results if r["success"]]),
                "avg_duration_ms": statistics.mean([r["duration_ms"] for r in read_results if r["success"]]) if read_results else 0
            },
            "write_operations": {
                "count": len(write_results),
                "successful": len([r for r in write_results if r["success"]]),
                "avg_duration_ms": statistics.mean([r["duration_ms"] for r in write_results if r["success"]]) if write_results else 0
            },
            "race_conditions_detected": len([r for r in results if not r["success"] and "race" in r.get("error", "").lower()])
        }

    def _generate_test_parameters(self, count: int) -> List[ParameterData]:
        """Generate test parameter data."""

        parameters = []
        for i in range(count):
            param = ParameterData(
                parameter_id=f"test_param_{i:03d}",
                value=round(random.uniform(0, 100), 2),
                set_point=round(random.uniform(0, 100), 2),
                timestamp=datetime.now(timezone.utc)
            )
            parameters.append(param)

        return parameters

    def _analyze_performance_impact(self) -> Dict[str, Any]:
        """Analyze the performance impact of synchronization."""

        if not self.baseline_metrics:
            return {"error": "No baseline metrics available for comparison"}

        # Find corresponding sync test
        sync_metrics = None
        for metrics in self.test_results:
            if "sync_normal_load" in metrics.operation_name:
                sync_metrics = metrics
                break

        if not sync_metrics:
            return {"error": "No synchronization metrics available for comparison"}

        # Calculate impact
        throughput_impact = ((sync_metrics.operations_per_second - self.baseline_metrics.operations_per_second)
                           / self.baseline_metrics.operations_per_second * 100)

        latency_impact = ((sync_metrics.avg_latency_ms - self.baseline_metrics.avg_latency_ms)
                         / self.baseline_metrics.avg_latency_ms * 100)

        memory_impact = ((sync_metrics.memory_usage_mb - self.baseline_metrics.memory_usage_mb)
                        / self.baseline_metrics.memory_usage_mb * 100)

        return {
            "performance_comparison": {
                "baseline_throughput_ops_per_sec": self.baseline_metrics.operations_per_second,
                "sync_throughput_ops_per_sec": sync_metrics.operations_per_second,
                "throughput_impact_percent": throughput_impact,

                "baseline_latency_ms": self.baseline_metrics.avg_latency_ms,
                "sync_latency_ms": sync_metrics.avg_latency_ms,
                "latency_impact_percent": latency_impact,

                "baseline_memory_mb": self.baseline_metrics.memory_usage_mb,
                "sync_memory_mb": sync_metrics.memory_usage_mb,
                "memory_impact_percent": memory_impact
            },
            "impact_assessment": {
                "throughput_acceptable": abs(throughput_impact) < 20,  # < 20% impact acceptable
                "latency_acceptable": abs(latency_impact) < 30,  # < 30% impact acceptable
                "memory_acceptable": abs(memory_impact) < 40,  # < 40% impact acceptable
                "overall_assessment": "PASS" if (abs(throughput_impact) < 20 and
                                               abs(latency_impact) < 30 and
                                               abs(memory_impact) < 40) else "REQUIRES_OPTIMIZATION"
            }
        }

    def _analyze_memory_efficiency(self, memory_results: List[Dict[str, Any]]) -> List[str]:
        """Analyze memory efficiency and provide recommendations."""

        recommendations = []

        # Check memory scaling
        max_memory_increase = max(r["memory_increase_mb"] for r in memory_results)
        if max_memory_increase > 100:  # More than 100MB increase
            recommendations.append(
                f"High memory usage detected: {max_memory_increase:.1f}MB increase. "
                "Consider implementing memory pooling or reducing batch sizes."
            )

        # Check efficiency vs batch size
        efficiency_ratios = []
        for result in memory_results:
            if result["memory_increase_mb"] > 0:
                efficiency = result["operations_per_second"] / result["memory_increase_mb"]
                efficiency_ratios.append((result["batch_size"], efficiency))

        if efficiency_ratios:
            best_efficiency = max(efficiency_ratios, key=lambda x: x[1])
            recommendations.append(
                f"Optimal batch size for memory efficiency: {best_efficiency[0]} "
                f"(efficiency ratio: {best_efficiency[1]:.2f} ops/sec/MB)"
            )

        return recommendations

    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations."""

        recommendations = []

        # Analyze all test results
        if self.test_results:
            avg_success_rate = statistics.mean([m.success_rate for m in self.test_results])
            if avg_success_rate < 0.95:
                recommendations.append(
                    f"Low success rate detected: {avg_success_rate:.2%}. "
                    "Investigate error handling and retry mechanisms."
                )

            # Check for high latency operations
            high_latency_tests = [m for m in self.test_results if m.avg_latency_ms > 1000]
            if high_latency_tests:
                recommendations.append(
                    f"High latency detected in {len(high_latency_tests)} tests. "
                    "Consider implementing connection pooling, async optimizations, or batch size tuning."
                )

            # Check for memory issues
            high_memory_tests = [m for m in self.test_results if m.memory_usage_mb > 500]
            if high_memory_tests:
                recommendations.append(
                    f"High memory usage in {len(high_memory_tests)} tests. "
                    "Implement memory optimization strategies."
                )

        # General recommendations
        recommendations.extend([
            "Implement database connection pooling if not already present",
            "Consider implementing parameter value caching for frequently read parameters",
            "Monitor transaction log size and implement regular cleanup",
            "Set up performance monitoring alerts for production deployment"
        ])

        return recommendations

    async def _cleanup_test_data(self):
        """Clean up test data from database."""

        try:
            logger.info("Cleaning up test data")

            supabase = get_supabase()

            # Clean up test records (those with transaction_id starting with test data patterns)
            # This is a simplified cleanup - in production you'd want more sophisticated cleanup

            # Clean parameter_value_history
            supabase.table('parameter_value_history').delete().like(
                'parameter_id', 'test_param_%'
            ).execute()

            # Clean process_data_points
            supabase.table('process_data_points').delete().like(
                'parameter_id', 'test_param_%'
            ).execute()

            logger.info("Test data cleanup completed")

        except Exception as e:
            logger.error(f"Test data cleanup failed: {e}")


async def main():
    """Main function to run the performance test suite."""

    tester = ParameterSynchronizationPerformanceTester()

    try:
        results = await tester.run_comprehensive_test_suite()

        # Save results to file
        output_file = f"/Users/albaraa/ald-control-system-phase-5/.agent-workspace/TASK-20250921-111927-10754a40/performance_test_results_{int(time.time())}.json"

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Performance test results saved to: {output_file}")

        # Print summary
        print("\n🎯 PERFORMANCE TEST SUMMARY")
        print("=" * 50)

        analysis = results.get('performance_analysis', {})
        if 'performance_comparison' in analysis:
            comp = analysis['performance_comparison']
            print(f"Throughput Impact: {comp.get('throughput_impact_percent', 0):.1f}%")
            print(f"Latency Impact: {comp.get('latency_impact_percent', 0):.1f}%")
            print(f"Memory Impact: {comp.get('memory_impact_percent', 0):.1f}%")

            assessment = analysis.get('impact_assessment', {})
            print(f"Overall Assessment: {assessment.get('overall_assessment', 'UNKNOWN')}")

        print(f"\nTotal Tests Run: {results['test_suite_summary']['total_tests_run']}")
        print(f"Test Duration: {results['test_suite_summary']['total_duration_seconds']:.1f} seconds")

        return results

    except Exception as e:
        logger.error(f"Performance test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())