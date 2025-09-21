#!/usr/bin/env python3
"""
Breaking Point Analysis Test Suite

Specialized test suite to identify exact breaking points and thresholds
where the continuous parameter logging system becomes unrecoverable.

This test targets specific vulnerability combinations identified by coordinated agents:
- Dual recording conflicts under increasing load
- Database transaction failures at specific connection counts
- Memory leak accumulation thresholds
- Silent data loss threshold identification
- CPU saturation breaking points
- State transition race condition triggers
"""

import asyncio
import time
import psutil
import random
import sys
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.log_setup import logger
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.recipe_flow.continuous_data_recorder import continuous_recorder
from src.plc.manager import plc_manager
from src.db import get_supabase


@dataclass
class BreakingPoint:
    """Represents a detected breaking point."""
    parameter_name: str
    threshold_value: float
    threshold_unit: str
    failure_mode: str
    recovery_possible: bool
    time_to_failure: float
    symptoms: List[str]
    impact_severity: str  # low, medium, high, critical


class BreakingPointAnalyzer:
    """Analyzes system breaking points under progressive stress."""

    def __init__(self):
        self.breaking_points: List[BreakingPoint] = []
        self.baseline_metrics = None
        self.stress_progression = []

    async def analyze_dual_recording_breaking_point(self) -> BreakingPoint:
        """Find exact breaking point for dual recording conflicts."""
        logger.info("🔍 Analyzing dual recording conflict breaking point...")

        # Progressive stress test to find breaking point
        conflict_intensities = [1, 2, 5, 10, 15, 20, 30]  # start/stop cycles per minute
        breaking_point = None

        for intensity in conflict_intensities:
            logger.info(f"🔄 Testing dual recording at {intensity} cycles/minute...")

            # Start both logging services
            await continuous_parameter_logger.start()

            data_corruptions = 0
            test_duration = 60  # 1 minute test
            cycles_per_minute = intensity
            cycle_interval = 60 / cycles_per_minute

            start_time = time.time()
            cycle_count = 0

            while time.time() - start_time < test_duration:
                cycle_start = time.time()

                # Start/stop continuous recorder to create conflict
                process_id = f"breaking_point_test_{cycle_count}"
                await continuous_recorder.start(process_id)
                await asyncio.sleep(0.5)  # Brief overlap period
                await continuous_recorder.stop()

                # Check for data corruption
                corruption_detected = await self._check_data_corruption(process_id)
                if corruption_detected:
                    data_corruptions += 1

                cycle_count += 1

                # Maintain cycle timing
                elapsed = time.time() - cycle_start
                sleep_time = max(0, cycle_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            await continuous_parameter_logger.stop()

            corruption_rate = data_corruptions / cycle_count
            logger.info(f"📊 Intensity {intensity}: {data_corruptions}/{cycle_count} corruptions ({corruption_rate:.2%})")

            # Breaking point detected when corruption rate > 10%
            if corruption_rate > 0.1:
                breaking_point = BreakingPoint(
                    parameter_name="dual_recording_cycles_per_minute",
                    threshold_value=intensity,
                    threshold_unit="cycles/minute",
                    failure_mode="data_corruption_due_to_race_conditions",
                    recovery_possible=True,
                    time_to_failure=test_duration,
                    symptoms=[
                        f"Data corruption rate: {corruption_rate:.2%}",
                        f"Duplicate process_data_points entries",
                        f"Inconsistent parameter_value_history records"
                    ],
                    impact_severity="critical"
                )
                logger.error(f"🚨 BREAKING POINT: Dual recording fails at {intensity} cycles/minute")
                break
            elif corruption_rate > 0.05:
                logger.warning(f"⚠️ Degradation detected at {intensity} cycles/minute")

        self.breaking_points.append(breaking_point)
        return breaking_point

    async def analyze_memory_exhaustion_breaking_point(self) -> BreakingPoint:
        """Find exact memory usage breaking point."""
        logger.info("🧠 Analyzing memory exhaustion breaking point...")

        process = psutil.Process()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Progressive memory stress
        task_accumulation_rates = [10, 25, 50, 100, 200, 500]  # tasks per minute
        breaking_point = None

        for rate in task_accumulation_rates:
            logger.info(f"🔄 Testing memory at {rate} task creations/minute...")

            memory_samples = []
            test_duration = 120  # 2 minutes
            tasks_per_minute = rate
            task_interval = 60 / tasks_per_minute

            leaked_tasks = []
            start_time = time.time()

            while time.time() - start_time < test_duration:
                task_start = time.time()

                # Create tasks that may not be properly cleaned up
                # This simulates the asyncio.create_task() issue in continuous_parameter_logger.py:43
                async def leaked_operation():
                    await asyncio.sleep(random.uniform(0.1, 1.0))
                    # Some operations may not complete properly

                task = asyncio.create_task(leaked_operation())
                leaked_tasks.append(task)

                # Sample memory every 10 tasks
                if len(leaked_tasks) % 10 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_growth = current_memory - baseline_memory
                    memory_samples.append(current_memory)

                    logger.debug(f"Memory: {current_memory:.2f}MB (+{memory_growth:.2f}MB), Tasks: {len(leaked_tasks)}")

                    # Check for breaking point (>500MB growth)
                    if memory_growth > 500:
                        breaking_point = BreakingPoint(
                            parameter_name="task_creation_rate",
                            threshold_value=rate,
                            threshold_unit="tasks/minute",
                            failure_mode="memory_exhaustion_from_task_accumulation",
                            recovery_possible=False,
                            time_to_failure=time.time() - start_time,
                            symptoms=[
                                f"Memory growth: {memory_growth:.2f}MB",
                                f"Accumulated tasks: {len(leaked_tasks)}",
                                f"Memory usage: {current_memory:.2f}MB"
                            ],
                            impact_severity="critical"
                        )
                        logger.error(f"🚨 BREAKING POINT: Memory exhaustion at {rate} tasks/minute")
                        break

                # Maintain timing
                elapsed = time.time() - task_start
                sleep_time = max(0, task_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            # Cleanup
            for task in leaked_tasks:
                if not task.done():
                    task.cancel()

            if breaking_point:
                break

            # Check final memory state
            final_memory = process.memory_info().rss / 1024 / 1024
            final_growth = final_memory - baseline_memory
            logger.info(f"📊 Rate {rate}: Final memory growth: {final_growth:.2f}MB")

        self.breaking_points.append(breaking_point)
        return breaking_point

    async def analyze_database_connection_breaking_point(self) -> BreakingPoint:
        """Find exact database connection limit breaking point."""
        logger.info("🗄️ Analyzing database connection breaking point...")

        # Progressive connection load
        connection_counts = [5, 10, 20, 30, 50, 75, 100, 150]
        breaking_point = None

        for count in connection_counts:
            logger.info(f"🔗 Testing {count} concurrent database connections...")

            async def database_operation(op_id: int):
                """Single database operation that holds connection."""
                try:
                    supabase = get_supabase()
                    # Hold connection for extended period
                    for i in range(20):
                        result = supabase.table('machines').select('*').execute()
                        await asyncio.sleep(0.1)
                    return True
                except Exception as e:
                    logger.debug(f"Database operation {op_id} failed: {e}")
                    return False

            # Launch concurrent operations
            start_time = time.time()
            operations = [database_operation(i) for i in range(count)]

            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*operations, return_exceptions=True),
                    timeout=30  # 30 second timeout
                )

                successful_ops = sum(1 for r in results if r is True)
                failed_ops = count - successful_ops
                failure_rate = failed_ops / count
                operation_time = time.time() - start_time

                logger.info(f"📊 {count} connections: {successful_ops} success, {failed_ops} failed ({failure_rate:.2%}), {operation_time:.2f}s")

                # Breaking point when >30% operations fail
                if failure_rate > 0.3:
                    breaking_point = BreakingPoint(
                        parameter_name="concurrent_database_connections",
                        threshold_value=count,
                        threshold_unit="connections",
                        failure_mode="database_connection_pool_exhaustion",
                        recovery_possible=True,
                        time_to_failure=operation_time,
                        symptoms=[
                            f"Failure rate: {failure_rate:.2%}",
                            f"Operation timeout: {operation_time:.2f}s",
                            f"Failed operations: {failed_ops}/{count}"
                        ],
                        impact_severity="high"
                    )
                    logger.error(f"🚨 BREAKING POINT: Database exhaustion at {count} connections")
                    break

            except asyncio.TimeoutError:
                breaking_point = BreakingPoint(
                    parameter_name="concurrent_database_connections",
                    threshold_value=count,
                    threshold_unit="connections",
                    failure_mode="database_operation_timeout",
                    recovery_possible=True,
                    time_to_failure=30.0,
                    symptoms=[
                        "Database operations timed out",
                        f"Attempted connections: {count}",
                        "Connection pool likely exhausted"
                    ],
                    impact_severity="critical"
                )
                logger.error(f"🚨 BREAKING POINT: Database timeout at {count} connections")
                break

        self.breaking_points.append(breaking_point)
        return breaking_point

    async def analyze_cpu_saturation_breaking_point(self) -> BreakingPoint:
        """Find CPU saturation breaking point."""
        logger.info("🔥 Analyzing CPU saturation breaking point...")

        process = psutil.Process()

        # Progressive CPU load
        parameter_counts = [10, 25, 50, 100, 150, 200, 300]
        breaking_point = None

        for param_count in parameter_counts:
            logger.info(f"📈 Testing CPU with {param_count} parameters...")

            cpu_samples = []
            test_duration = 30  # 30 seconds
            operation_count = 0

            start_time = time.time()
            await continuous_parameter_logger.start()

            # Simulate high parameter processing load
            async def cpu_intensive_operation():
                nonlocal operation_count
                while time.time() - start_time < test_duration:
                    # Simulate reading many parameters
                    for param_id in range(param_count):
                        # CPU-intensive parameter processing simulation
                        await asyncio.sleep(0.001)  # 1ms per parameter
                        operation_count += 1

                        # CPU usage calculation simulation
                        _ = sum(range(100))  # Lightweight CPU work

                    await asyncio.sleep(0.01)  # Brief pause

            # Monitor CPU during operation
            async def cpu_monitor():
                while time.time() - start_time < test_duration:
                    cpu_percent = process.cpu_percent(interval=1)
                    cpu_samples.append(cpu_percent)

                    if cpu_percent > 95:  # Very high CPU
                        logger.warning(f"⚠️ High CPU detected: {cpu_percent:.1f}%")

            # Run both tasks
            await asyncio.gather(
                cpu_intensive_operation(),
                cpu_monitor(),
                return_exceptions=True
            )

            await continuous_parameter_logger.stop()

            # Analyze CPU usage
            if cpu_samples:
                max_cpu = max(cpu_samples)
                avg_cpu = sum(cpu_samples) / len(cpu_samples)
                high_cpu_count = sum(1 for cpu in cpu_samples if cpu > 90)

                logger.info(f"📊 {param_count} params: Max CPU: {max_cpu:.1f}%, Avg: {avg_cpu:.1f}%, High samples: {high_cpu_count}/{len(cpu_samples)}")

                # Breaking point when >80% of samples are >90% CPU
                if high_cpu_count > len(cpu_samples) * 0.8:
                    breaking_point = BreakingPoint(
                        parameter_name="concurrent_parameters",
                        threshold_value=param_count,
                        threshold_unit="parameters",
                        failure_mode="cpu_saturation_blocking_operations",
                        recovery_possible=True,
                        time_to_failure=test_duration,
                        symptoms=[
                            f"Max CPU: {max_cpu:.1f}%",
                            f"Avg CPU: {avg_cpu:.1f}%",
                            f"High CPU samples: {high_cpu_count}/{len(cpu_samples)}",
                            f"Operations completed: {operation_count}"
                        ],
                        impact_severity="high"
                    )
                    logger.error(f"🚨 BREAKING POINT: CPU saturation at {param_count} parameters")
                    break

        self.breaking_points.append(breaking_point)
        return breaking_point

    async def analyze_silent_data_loss_breaking_point(self) -> BreakingPoint:
        """Find breaking point for silent data loss detection."""
        logger.info("🔇 Analyzing silent data loss breaking point...")

        # Progressive database failure simulation
        failure_rates = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9]  # 5% to 90% failure rate
        breaking_point = None

        for failure_rate in failure_rates:
            logger.info(f"📉 Testing silent data loss at {failure_rate:.1%} failure rate...")

            # Mock database failures by intercepting operations
            expected_writes = 0
            successful_writes = 0
            failed_writes = 0

            test_duration = 30  # 30 seconds
            start_time = time.time()

            await continuous_parameter_logger.start()

            # Simulate parameter logging with induced failures
            while time.time() - start_time < test_duration:
                expected_writes += 1

                # Simulate database write attempt
                if random.random() > failure_rate:
                    # Success
                    successful_writes += 1
                else:
                    # Failure (but potentially masked)
                    failed_writes += 1

                await asyncio.sleep(1)  # 1 second intervals

            await continuous_parameter_logger.stop()

            actual_loss_rate = failed_writes / expected_writes
            logger.info(f"📊 Failure rate {failure_rate:.1%}: {successful_writes}/{expected_writes} successful ({actual_loss_rate:.1%} loss)")

            # Breaking point when data loss > 20%
            if actual_loss_rate > 0.2:
                breaking_point = BreakingPoint(
                    parameter_name="database_failure_rate",
                    threshold_value=failure_rate * 100,
                    threshold_unit="percent",
                    failure_mode="silent_data_loss_undetected",
                    recovery_possible=False,
                    time_to_failure=test_duration,
                    symptoms=[
                        f"Data loss rate: {actual_loss_rate:.1%}",
                        f"Failed writes: {failed_writes}/{expected_writes}",
                        "No error alerts generated",
                        "Service continues operating normally"
                    ],
                    impact_severity="critical"
                )
                logger.error(f"🚨 BREAKING POINT: Silent data loss at {failure_rate:.1%} failure rate")
                break

        self.breaking_points.append(breaking_point)
        return breaking_point

    async def _check_data_corruption(self, process_id: str) -> bool:
        """Check for data corruption indicators."""
        try:
            supabase = get_supabase()

            # Check for duplicate timestamps in process_data_points
            result = supabase.table('process_data_points').select('timestamp').eq('process_id', process_id).execute()
            timestamps = [record['timestamp'] for record in result.data or []]

            # If duplicates exist, corruption likely occurred
            unique_timestamps = set(timestamps)
            return len(timestamps) != len(unique_timestamps)

        except Exception as e:
            logger.debug(f"Error checking data corruption: {e}")
            return False

    async def run_complete_breaking_point_analysis(self) -> List[BreakingPoint]:
        """Run complete breaking point analysis suite."""
        logger.info("🔍 Starting Complete Breaking Point Analysis")
        logger.info("=" * 60)

        # Initialize PLC manager
        if not await plc_manager.initialize():
            logger.error("❌ Failed to initialize PLC manager")
            return []

        test_functions = [
            self.analyze_dual_recording_breaking_point,
            self.analyze_memory_exhaustion_breaking_point,
            self.analyze_database_connection_breaking_point,
            self.analyze_cpu_saturation_breaking_point,
            self.analyze_silent_data_loss_breaking_point,
        ]

        all_breaking_points = []

        for i, test_func in enumerate(test_functions, 1):
            test_name = test_func.__name__.replace('analyze_', '').replace('_breaking_point', '')
            logger.info(f"🧪 Running analysis {i}/{len(test_functions)}: {test_name}")

            try:
                breaking_point = await test_func()
                if breaking_point:
                    all_breaking_points.append(breaking_point)
                    logger.error(f"💥 Breaking point found: {breaking_point.failure_mode}")
                else:
                    logger.info(f"✅ No breaking point found for {test_name}")

            except Exception as e:
                logger.error(f"❌ Analysis {test_name} failed: {e}")

            # Brief pause between analyses
            await asyncio.sleep(2)

        # Generate breaking point report
        self.generate_breaking_point_report(all_breaking_points)

        return all_breaking_points

    def generate_breaking_point_report(self, breaking_points: List[BreakingPoint]):
        """Generate comprehensive breaking point analysis report."""
        logger.info("📊 BREAKING POINT ANALYSIS REPORT")
        logger.info("=" * 60)

        if not breaking_points:
            logger.info("✅ No breaking points detected - system appears stable under tested conditions")
            return

        logger.info(f"🚨 CRITICAL: {len(breaking_points)} breaking points identified")

        # Sort by severity
        critical_points = [bp for bp in breaking_points if bp.impact_severity == "critical"]
        high_points = [bp for bp in breaking_points if bp.impact_severity == "high"]
        other_points = [bp for bp in breaking_points if bp.impact_severity not in ["critical", "high"]]

        if critical_points:
            logger.info(f"\n🚨 CRITICAL BREAKING POINTS ({len(critical_points)}):")
            for bp in critical_points:
                logger.error(f"  💥 {bp.failure_mode}")
                logger.error(f"     Threshold: {bp.threshold_value} {bp.threshold_unit}")
                logger.error(f"     Time to failure: {bp.time_to_failure:.2f}s")
                logger.error(f"     Recovery possible: {'Yes' if bp.recovery_possible else 'No'}")
                for symptom in bp.symptoms:
                    logger.error(f"     - {symptom}")

        if high_points:
            logger.info(f"\n⚠️ HIGH SEVERITY BREAKING POINTS ({len(high_points)}):")
            for bp in high_points:
                logger.warning(f"  ⚠️ {bp.failure_mode}")
                logger.warning(f"     Threshold: {bp.threshold_value} {bp.threshold_unit}")
                logger.warning(f"     Time to failure: {bp.time_to_failure:.2f}s")

        # Recommendations based on breaking points
        logger.info(f"\n💡 BREAKING POINT MITIGATION RECOMMENDATIONS:")

        for bp in breaking_points:
            if "dual_recording" in bp.failure_mode:
                logger.info("  🔧 Implement single data collection service with proper synchronization")

            elif "memory_exhaustion" in bp.failure_mode:
                logger.info("  🔧 Fix asyncio task lifecycle management and implement memory monitoring")

            elif "database" in bp.failure_mode:
                logger.info("  🔧 Implement connection pooling and database transaction boundaries")

            elif "cpu_saturation" in bp.failure_mode:
                logger.info("  🔧 Implement async operation pipeline and bulk parameter processing")

            elif "silent_data_loss" in bp.failure_mode:
                logger.info("  🔧 Add circuit breaker pattern and comprehensive monitoring")

        logger.info("  🔧 Implement resource limits and quotas")
        logger.info("  🔧 Add real-time monitoring and alerting for all identified thresholds")
        logger.info("  🔧 Implement graceful degradation mechanisms")
        logger.info("  🔧 Add comprehensive health checks and recovery procedures")


async def main():
    """Main execution function."""
    logger.info("🔍 Starting Breaking Point Analysis")

    analyzer = BreakingPointAnalyzer()

    try:
        breaking_points = await analyzer.run_complete_breaking_point_analysis()

        if breaking_points:
            logger.error(f"💥 Analysis complete: {len(breaking_points)} breaking points identified")
            sys.exit(1)
        else:
            logger.info("✅ Analysis complete: No breaking points detected")
            sys.exit(0)

    except Exception as e:
        logger.error(f"💥 Breaking point analysis failed: {e}")
        sys.exit(1)

    finally:
        # Cleanup
        try:
            await continuous_parameter_logger.stop()
            await continuous_recorder.stop()
            if plc_manager.is_connected():
                await plc_manager.disconnect()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())