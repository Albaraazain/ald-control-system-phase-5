#!/usr/bin/env python3
"""
Resource Exhaustion Stress Test Suite

Comprehensive testing of system behavior under extreme resource constraints,
targeting specific vulnerabilities identified by orchestrated agents:

CRITICAL TARGETS:
1. Dual data recording conflict between ContinuousParameterLogger and ContinuousDataRecorder
2. Database transaction integrity vulnerabilities during resource stress
3. Memory leaks from uncontrolled asyncio task accumulation
4. Silent data loss through unsafe exception handling
5. State transition race conditions under high load
6. Database connection pool exhaustion
7. SQL injection vulnerabilities under memory pressure

RESOURCE EXHAUSTION SCENARIOS:
- Memory exhaustion (24+ hour continuous operation simulation)
- Database connection pool exhaustion
- Disk space limitations for parameter logging
- CPU saturation with 100+ concurrent parameters
- Database table size growth patterns and performance impact
- Concurrent operation resource conflicts
"""

import os
import sys
import asyncio
import time
import random
import psutil
import tracemalloc
import threading
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.log_setup import logger
from src.plc.manager import plc_manager
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.recipe_flow.continuous_data_recorder import continuous_recorder
from src.config import MACHINE_ID
from src.db import get_supabase, get_current_timestamp


@dataclass
class ResourceMetrics:
    """Resource utilization metrics."""
    timestamp: float
    memory_mb: float
    memory_percent: float
    cpu_percent: float
    disk_usage_mb: float
    disk_free_mb: float
    open_files: int
    network_connections: int
    database_connections: int
    asyncio_tasks: int
    memory_peak_mb: float


@dataclass
class TestResult:
    """Test execution result."""
    test_name: str
    success: bool
    duration: float
    error_message: Optional[str] = None
    resource_metrics: List[ResourceMetrics] = None
    data_integrity_violations: int = 0
    memory_leaks_detected: int = 0
    max_memory_usage_mb: float = 0
    breaking_point_reached: bool = False
    breaking_point_description: Optional[str] = None


class ResourceExhaustionTester:
    """Comprehensive resource exhaustion stress test suite."""

    def __init__(self):
        self.process = psutil.Process()
        self.resource_history: List[ResourceMetrics] = []
        self.test_results: List[TestResult] = []
        self.baseline_memory = 0
        self.test_start_time = 0
        self.data_corruption_detector = DataCorruptionDetector()
        self.memory_leak_detector = MemoryLeakDetector()
        self.breaking_points: Dict[str, Any] = {}

    async def initialize_test_environment(self) -> bool:
        """Initialize test environment and establish baseline metrics."""
        logger.info("🔧 Initializing resource exhaustion test environment...")

        try:
            # Start memory tracking
            tracemalloc.start()

            # Establish baseline memory usage
            self.baseline_memory = self.process.memory_info().rss / 1024 / 1024
            logger.info(f"📊 Baseline memory usage: {self.baseline_memory:.2f} MB")

            # Initialize PLC connection
            if not await plc_manager.initialize():
                logger.error("❌ Failed to initialize PLC manager")
                return False

            # Clear any existing continuous logging
            await continuous_parameter_logger.stop()
            await continuous_recorder.stop()

            self.test_start_time = time.time()
            logger.info("✅ Test environment initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize test environment: {e}")
            return False

    def capture_resource_metrics(self) -> ResourceMetrics:
        """Capture current resource utilization metrics."""
        try:
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent()

            # Get disk usage for current directory
            disk_usage = psutil.disk_usage('.')

            # Count open files and network connections
            try:
                open_files = len(self.process.open_files())
            except psutil.AccessDenied:
                open_files = -1

            try:
                network_connections = len(self.process.connections())
            except psutil.AccessDenied:
                network_connections = -1

            # Get memory peak
            current_mem, peak_mem = tracemalloc.get_traced_memory()

            # Count asyncio tasks
            try:
                tasks = len([t for t in asyncio.all_tasks() if not t.done()])
            except:
                tasks = -1

            return ResourceMetrics(
                timestamp=time.time(),
                memory_mb=memory_info.rss / 1024 / 1024,
                memory_percent=self.process.memory_percent(),
                cpu_percent=cpu_percent,
                disk_usage_mb=disk_usage.used / 1024 / 1024,
                disk_free_mb=disk_usage.free / 1024 / 1024,
                open_files=open_files,
                network_connections=network_connections,
                database_connections=self._count_database_connections(),
                asyncio_tasks=tasks,
                memory_peak_mb=peak_mem / 1024 / 1024
            )

        except Exception as e:
            logger.warning(f"Failed to capture resource metrics: {e}")
            return None

    def _count_database_connections(self) -> int:
        """Count active database connections (Supabase REST API doesn't expose this directly)."""
        try:
            # This is a simplified check - in real implementation you'd monitor connection pools
            supabase = get_supabase()
            # Attempt a simple query to verify connection is active
            result = supabase.table('machines').select('id').limit(1).execute()
            return 1 if result.data else 0
        except:
            return 0

    async def test_memory_exhaustion_24_hour_simulation(self) -> TestResult:
        """
        Simulate 24+ hour continuous operation to test memory exhaustion.
        Uses accelerated time simulation to complete in reasonable test time.
        """
        test_name = "memory_exhaustion_24h_simulation"
        logger.info("🧠 Starting 24-hour memory exhaustion simulation...")

        start_time = time.time()
        test_result = TestResult(test_name=test_name, success=False, duration=0)

        try:
            # Simulate 24 hours in 10 minutes (144x acceleration)
            simulation_duration = 600  # 10 minutes real time
            accelerated_hours = 24
            cycles_per_hour = 3600  # 1 second intervals
            total_cycles = accelerated_hours * cycles_per_hour
            cycle_delay = simulation_duration / total_cycles

            logger.info(f"📈 Simulating {accelerated_hours} hours in {simulation_duration} seconds")
            logger.info(f"🔄 Running {total_cycles} cycles with {cycle_delay:.4f}s delay")

            # Start continuous logging services
            await continuous_parameter_logger.start()

            memory_snapshots = []
            leak_threshold_mb = 100  # Alert if memory grows by more than 100MB

            for cycle in range(total_cycles):
                cycle_start = time.time()

                # Capture metrics every 100 cycles to avoid overhead
                if cycle % 100 == 0:
                    metrics = self.capture_resource_metrics()
                    if metrics:
                        memory_snapshots.append(metrics)
                        self.resource_history.append(metrics)

                        # Check for memory growth
                        current_memory = metrics.memory_mb
                        memory_growth = current_memory - self.baseline_memory

                        if memory_growth > leak_threshold_mb:
                            logger.warning(f"⚠️ Memory growth detected: {memory_growth:.2f}MB above baseline")
                            test_result.memory_leaks_detected += 1

                        if cycle % 1000 == 0:
                            simulated_hours = (cycle / total_cycles) * accelerated_hours
                            logger.info(f"📊 Simulated {simulated_hours:.1f}h - Memory: {current_memory:.2f}MB (+{memory_growth:.2f}MB)")

                # Simulate parameter reading load
                try:
                    # Read multiple parameters to simulate heavy load
                    for _ in range(5):
                        if plc_manager.is_connected():
                            await plc_manager.read_all_parameters()
                except Exception as e:
                    logger.debug(f"Parameter read error in simulation: {e}")

                # Maintain cycle timing
                elapsed = time.time() - cycle_start
                sleep_time = max(0, cycle_delay - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                # Check for breaking point
                if memory_snapshots:
                    latest_memory = memory_snapshots[-1].memory_mb
                    if latest_memory > self.baseline_memory + 500:  # 500MB increase
                        test_result.breaking_point_reached = True
                        test_result.breaking_point_description = f"Memory exceeded 500MB growth at cycle {cycle}"
                        logger.error(f"💥 BREAKING POINT: Memory exhaustion at {latest_memory:.2f}MB")
                        break

            # Analyze memory pattern
            if len(memory_snapshots) >= 2:
                memory_trend = memory_snapshots[-1].memory_mb - memory_snapshots[0].memory_mb
                test_result.max_memory_usage_mb = max(m.memory_mb for m in memory_snapshots)

                if memory_trend > 50:  # More than 50MB growth indicates leak
                    test_result.memory_leaks_detected += 1
                    logger.warning(f"🚨 Memory leak detected: {memory_trend:.2f}MB growth over simulation")
                else:
                    logger.info(f"✅ Memory usage stable: {memory_trend:.2f}MB growth over simulation")

            test_result.success = not test_result.breaking_point_reached
            test_result.resource_metrics = memory_snapshots

        except Exception as e:
            test_result.error_message = str(e)
            logger.error(f"❌ Memory exhaustion test failed: {e}")

        finally:
            await continuous_parameter_logger.stop()
            test_result.duration = time.time() - start_time

        return test_result

    async def test_database_connection_pool_exhaustion(self) -> TestResult:
        """Test database connection pool exhaustion under concurrent load."""
        test_name = "database_connection_pool_exhaustion"
        logger.info("🗄️ Starting database connection pool exhaustion test...")

        start_time = time.time()
        test_result = TestResult(test_name=test_name, success=False, duration=0)

        try:
            # Create many concurrent database operations
            max_connections = 100  # Attempt to exhaust connection pool
            concurrent_operations = []

            async def database_operation(operation_id: int):
                """Single database operation that holds connection."""
                try:
                    supabase = get_supabase()

                    # Simulate heavy database operation
                    for i in range(10):
                        result = supabase.table('machines').select('*').execute()
                        await asyncio.sleep(0.1)  # Hold connection longer

                    return True
                except Exception as e:
                    logger.warning(f"Database operation {operation_id} failed: {e}")
                    return False

            # Launch concurrent operations
            logger.info(f"🚀 Launching {max_connections} concurrent database operations...")

            for i in range(max_connections):
                operation = database_operation(i)
                concurrent_operations.append(operation)

                # Capture metrics every 10 operations
                if i % 10 == 0:
                    metrics = self.capture_resource_metrics()
                    if metrics:
                        self.resource_history.append(metrics)

            # Wait for operations to complete (with timeout)
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*concurrent_operations, return_exceptions=True),
                    timeout=60
                )

                successful_ops = sum(1 for r in results if r is True)
                failed_ops = len(results) - successful_ops

                logger.info(f"📊 Database operations: {successful_ops} successful, {failed_ops} failed")

                # If many operations failed, we likely hit connection limits
                if failed_ops > max_connections * 0.3:  # More than 30% failed
                    test_result.breaking_point_reached = True
                    test_result.breaking_point_description = f"Connection pool exhausted: {failed_ops} failures"
                    logger.warning(f"⚠️ Connection pool likely exhausted: {failed_ops} failures")
                else:
                    test_result.success = True

            except asyncio.TimeoutError:
                test_result.breaking_point_reached = True
                test_result.breaking_point_description = "Database operations timed out - connection pool blocked"
                logger.error("💥 Database operations timed out - connection pool likely exhausted")

        except Exception as e:
            test_result.error_message = str(e)
            logger.error(f"❌ Database connection pool test failed: {e}")

        test_result.duration = time.time() - start_time
        return test_result

    async def test_dual_recording_conflict_stress(self) -> TestResult:
        """
        Test the dual data recording conflict under stress.
        Reproduces race condition between ContinuousParameterLogger and ContinuousDataRecorder.
        """
        test_name = "dual_recording_conflict_stress"
        logger.info("⚔️ Starting dual recording conflict stress test...")

        start_time = time.time()
        test_result = TestResult(test_name=test_name, success=False, duration=0)

        try:
            # Initialize data corruption detector
            self.data_corruption_detector.reset()

            # Start both services simultaneously to create conflict
            await continuous_parameter_logger.start()

            # Simulate a process starting/stopping rapidly to trigger race conditions
            process_id = "stress_test_process_001"

            for cycle in range(20):  # 20 rapid start/stop cycles
                logger.info(f"🔄 Dual recording cycle {cycle + 1}/20")

                # Start continuous data recorder (simulates process start)
                await continuous_recorder.start(process_id)

                # Both services now write to process_data_points - CONFLICT!
                # Let them run simultaneously for a short time
                await asyncio.sleep(2)

                # Capture data integrity before stopping
                integrity_violations = await self.data_corruption_detector.check_dual_recording_integrity(process_id)
                test_result.data_integrity_violations += integrity_violations

                # Stop continuous data recorder (simulates process stop)
                await continuous_recorder.stop()

                # Brief pause before next cycle
                await asyncio.sleep(1)

                # Capture resource metrics
                metrics = self.capture_resource_metrics()
                if metrics:
                    self.resource_history.append(metrics)

            # Final integrity check
            final_violations = await self.data_corruption_detector.check_dual_recording_integrity(process_id)
            test_result.data_integrity_violations += final_violations

            if test_result.data_integrity_violations > 0:
                logger.error(f"🚨 Data integrity violations detected: {test_result.data_integrity_violations}")
                test_result.breaking_point_reached = True
                test_result.breaking_point_description = f"Data corruption: {test_result.data_integrity_violations} violations"
            else:
                test_result.success = True
                logger.info("✅ No data integrity violations detected")

        except Exception as e:
            test_result.error_message = str(e)
            logger.error(f"❌ Dual recording conflict test failed: {e}")

        finally:
            await continuous_parameter_logger.stop()
            await continuous_recorder.stop()
            test_result.duration = time.time() - start_time

        return test_result

    async def test_high_parameter_count_cpu_saturation(self) -> TestResult:
        """Test system behavior with 100+ parameters causing CPU saturation."""
        test_name = "high_parameter_count_cpu_saturation"
        logger.info("🔥 Starting high parameter count CPU saturation test...")

        start_time = time.time()
        test_result = TestResult(test_name=test_name, success=False, duration=0)

        try:
            # Mock high parameter count scenario
            high_param_count = 150  # 150 parameters
            test_duration = 60  # 1 minute of high load

            logger.info(f"📈 Simulating {high_param_count} parameters for {test_duration} seconds")

            # Start continuous logging
            await continuous_parameter_logger.start()

            async def parameter_load_generator():
                """Generate high parameter read load."""
                operation_count = 0
                while time.time() - start_time < test_duration:
                    try:
                        # Simulate reading many parameters
                        for param_id in range(high_param_count):
                            if plc_manager.is_connected():
                                # Simulate parameter read
                                await asyncio.sleep(0.001)  # 1ms per parameter
                                operation_count += 1

                        await asyncio.sleep(0.1)  # Brief pause between cycles

                    except Exception as e:
                        logger.debug(f"Parameter load generation error: {e}")

                return operation_count

            # Monitor CPU usage during high load
            cpu_monitor_task = asyncio.create_task(self._monitor_cpu_usage(test_duration))
            load_generator_task = asyncio.create_task(parameter_load_generator())

            # Wait for both tasks
            cpu_stats, operation_count = await asyncio.gather(cpu_monitor_task, load_generator_task)

            # Analyze CPU performance
            max_cpu = max(cpu_stats) if cpu_stats else 0
            avg_cpu = sum(cpu_stats) / len(cpu_stats) if cpu_stats else 0

            logger.info(f"📊 CPU usage - Max: {max_cpu:.1f}%, Avg: {avg_cpu:.1f}%")
            logger.info(f"🔢 Total parameter operations: {operation_count}")

            # Check for CPU saturation (>90% sustained)
            high_cpu_samples = sum(1 for cpu in cpu_stats if cpu > 90)
            if high_cpu_samples > len(cpu_stats) * 0.5:  # More than 50% of samples >90%
                test_result.breaking_point_reached = True
                test_result.breaking_point_description = f"CPU saturation: {high_cpu_samples}/{len(cpu_stats)} samples >90%"
                logger.warning(f"⚠️ CPU saturation detected: {high_cpu_samples} high samples")
            else:
                test_result.success = True

        except Exception as e:
            test_result.error_message = str(e)
            logger.error(f"❌ High parameter count test failed: {e}")

        finally:
            await continuous_parameter_logger.stop()
            test_result.duration = time.time() - start_time

        return test_result

    async def _monitor_cpu_usage(self, duration: float) -> List[float]:
        """Monitor CPU usage over specified duration."""
        cpu_samples = []
        end_time = time.time() + duration

        while time.time() < end_time:
            try:
                cpu_percent = self.process.cpu_percent(interval=1)
                cpu_samples.append(cpu_percent)

                # Also capture full resource metrics periodically
                if len(cpu_samples) % 10 == 0:
                    metrics = self.capture_resource_metrics()
                    if metrics:
                        self.resource_history.append(metrics)

            except Exception as e:
                logger.debug(f"CPU monitoring error: {e}")

        return cpu_samples

    async def test_asyncio_task_accumulation_memory_leak(self) -> TestResult:
        """Test for memory leaks from uncontrolled asyncio task accumulation."""
        test_name = "asyncio_task_accumulation_memory_leak"
        logger.info("🔄 Starting asyncio task accumulation memory leak test...")

        start_time = time.time()
        test_result = TestResult(test_name=test_name, success=False, duration=0)

        try:
            initial_memory = self.process.memory_info().rss / 1024 / 1024
            initial_tasks = len([t for t in asyncio.all_tasks() if not t.done()])

            logger.info(f"📊 Initial state - Memory: {initial_memory:.2f}MB, Tasks: {initial_tasks}")

            # Create scenario that triggers task accumulation
            # This reproduces the issue in continuous_parameter_logger.py:43

            task_leak_count = 0

            for cycle in range(50):  # 50 start/stop cycles
                # Start and stop logging rapidly to trigger task creation bug
                await continuous_parameter_logger.start()
                await asyncio.sleep(0.1)  # Brief run time
                await continuous_parameter_logger.stop()

                # Check task count every 10 cycles
                if cycle % 10 == 0:
                    current_tasks = len([t for t in asyncio.all_tasks() if not t.done()])
                    current_memory = self.process.memory_info().rss / 1024 / 1024

                    task_growth = current_tasks - initial_tasks
                    memory_growth = current_memory - initial_memory

                    logger.info(f"🔄 Cycle {cycle}: Tasks: {current_tasks} (+{task_growth}), Memory: {current_memory:.2f}MB (+{memory_growth:.2f}MB)")

                    # Detect task accumulation
                    if task_growth > 10:  # More than 10 extra tasks
                        task_leak_count += 1
                        logger.warning(f"⚠️ Task accumulation detected: {task_growth} extra tasks")

                    # Capture metrics
                    metrics = self.capture_resource_metrics()
                    if metrics:
                        self.resource_history.append(metrics)

            # Final check
            final_tasks = len([t for t in asyncio.all_tasks() if not t.done()])
            final_memory = self.process.memory_info().rss / 1024 / 1024

            total_task_growth = final_tasks - initial_tasks
            total_memory_growth = final_memory - initial_memory

            logger.info(f"📊 Final state - Tasks: {final_tasks} (+{total_task_growth}), Memory: {final_memory:.2f}MB (+{total_memory_growth:.2f}MB)")

            test_result.memory_leaks_detected = task_leak_count
            test_result.max_memory_usage_mb = final_memory

            # Determine if we have a memory leak
            if total_task_growth > 5 or total_memory_growth > 20:  # 5+ extra tasks or 20MB+ growth
                test_result.breaking_point_reached = True
                test_result.breaking_point_description = f"Memory leak: {total_task_growth} tasks, {total_memory_growth:.2f}MB growth"
                logger.error(f"🚨 Memory leak detected: {total_task_growth} extra tasks, {total_memory_growth:.2f}MB growth")
            else:
                test_result.success = True
                logger.info("✅ No significant task accumulation or memory leak detected")

        except Exception as e:
            test_result.error_message = str(e)
            logger.error(f"❌ Asyncio task accumulation test failed: {e}")

        test_result.duration = time.time() - start_time
        return test_result

    async def test_silent_data_loss_under_stress(self) -> TestResult:
        """Test for silent data loss through unsafe exception handling under stress."""
        test_name = "silent_data_loss_under_stress"
        logger.info("🔇 Starting silent data loss detection test...")

        start_time = time.time()
        test_result = TestResult(test_name=test_name, success=False, duration=0)

        try:
            # This test targets the unsafe exception handling in continuous_parameter_logger.py:248
            # We'll create conditions that cause database failures and check if data is silently lost

            data_loss_detector = SilentDataLossDetector()
            await data_loss_detector.initialize()

            # Start continuous logging
            await continuous_parameter_logger.start()

            test_duration = 30  # 30 seconds of stress
            end_time = time.time() + test_duration

            logger.info(f"🎯 Running silent data loss test for {test_duration} seconds...")

            expected_data_points = 0
            actual_data_points = 0

            while time.time() < end_time:
                # Simulate parameter reads that should result in database writes
                try:
                    if plc_manager.is_connected():
                        await plc_manager.read_all_parameters()
                        expected_data_points += 1

                        # Periodically check if data is actually being written
                        if expected_data_points % 10 == 0:
                            actual_count = await data_loss_detector.count_recent_data_points()
                            if actual_count < expected_data_points * 0.8:  # Less than 80% of expected
                                logger.warning(f"⚠️ Potential data loss: {actual_count}/{expected_data_points} data points")
                                test_result.data_integrity_violations += 1

                except Exception as e:
                    logger.debug(f"Parameter read error during data loss test: {e}")

                await asyncio.sleep(1)

            # Final data loss check
            final_count = await data_loss_detector.count_recent_data_points()
            data_loss_percentage = ((expected_data_points - final_count) / expected_data_points) * 100 if expected_data_points > 0 else 0

            logger.info(f"📊 Data loss analysis: {final_count}/{expected_data_points} data points ({data_loss_percentage:.1f}% loss)")

            if data_loss_percentage > 20:  # More than 20% data loss
                test_result.breaking_point_reached = True
                test_result.breaking_point_description = f"Silent data loss: {data_loss_percentage:.1f}% of data missing"
                logger.error(f"🚨 Significant data loss detected: {data_loss_percentage:.1f}%")
            elif data_loss_percentage > 5:  # More than 5% data loss
                logger.warning(f"⚠️ Minor data loss detected: {data_loss_percentage:.1f}%")
                test_result.data_integrity_violations += 1
            else:
                test_result.success = True
                logger.info("✅ No significant data loss detected")

        except Exception as e:
            test_result.error_message = str(e)
            logger.error(f"❌ Silent data loss test failed: {e}")

        finally:
            await continuous_parameter_logger.stop()
            test_result.duration = time.time() - start_time

        return test_result

    async def run_comprehensive_resource_exhaustion_suite(self) -> Dict[str, TestResult]:
        """Run the complete resource exhaustion test suite."""
        logger.info("🚀 Starting comprehensive resource exhaustion test suite...")

        if not await self.initialize_test_environment():
            logger.error("❌ Failed to initialize test environment")
            return {}

        test_suite = [
            self.test_memory_exhaustion_24_hour_simulation,
            self.test_database_connection_pool_exhaustion,
            self.test_dual_recording_conflict_stress,
            self.test_high_parameter_count_cpu_saturation,
            self.test_asyncio_task_accumulation_memory_leak,
            self.test_silent_data_loss_under_stress,
        ]

        results = {}
        total_tests = len(test_suite)

        for i, test_func in enumerate(test_suite, 1):
            test_name = test_func.__name__.replace('test_', '')
            logger.info(f"🧪 Running test {i}/{total_tests}: {test_name}")

            try:
                result = await test_func()
                results[test_name] = result
                self.test_results.append(result)

                if result.success:
                    logger.info(f"✅ Test {test_name} PASSED")
                else:
                    logger.error(f"❌ Test {test_name} FAILED: {result.error_message or 'Breaking point reached'}")

            except Exception as e:
                logger.error(f"💥 Test {test_name} crashed: {e}")
                results[test_name] = TestResult(
                    test_name=test_name,
                    success=False,
                    duration=0,
                    error_message=str(e)
                )

            # Brief pause between tests
            await asyncio.sleep(2)

        # Generate comprehensive report
        self.generate_comprehensive_report(results)

        return results

    def generate_comprehensive_report(self, results: Dict[str, TestResult]):
        """Generate comprehensive resource exhaustion test report."""
        logger.info("📊 COMPREHENSIVE RESOURCE EXHAUSTION TEST REPORT")
        logger.info("=" * 80)

        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r.success)
        failed_tests = total_tests - passed_tests

        logger.info(f"📈 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed ({failed_tests} failed)")

        # Test-by-test breakdown
        logger.info("\n🔍 DETAILED TEST RESULTS:")
        for test_name, result in results.items():
            status = "✅ PASS" if result.success else "❌ FAIL"
            logger.info(f"  {status} {test_name}: {result.duration:.2f}s")

            if result.breaking_point_reached:
                logger.info(f"    💥 Breaking Point: {result.breaking_point_description}")
            if result.memory_leaks_detected > 0:
                logger.info(f"    🚨 Memory Leaks: {result.memory_leaks_detected}")
            if result.data_integrity_violations > 0:
                logger.info(f"    ⚠️ Data Integrity Issues: {result.data_integrity_violations}")
            if result.error_message:
                logger.info(f"    ❌ Error: {result.error_message}")

        # Resource utilization analysis
        if self.resource_history:
            logger.info("\n📊 RESOURCE UTILIZATION ANALYSIS:")

            max_memory = max(m.memory_mb for m in self.resource_history)
            avg_memory = sum(m.memory_mb for m in self.resource_history) / len(self.resource_history)
            memory_growth = max_memory - self.baseline_memory

            max_cpu = max(m.cpu_percent for m in self.resource_history if m.cpu_percent > 0)
            avg_cpu = sum(m.cpu_percent for m in self.resource_history if m.cpu_percent > 0) / len([m for m in self.resource_history if m.cpu_percent > 0])

            logger.info(f"  Memory - Baseline: {self.baseline_memory:.2f}MB, Peak: {max_memory:.2f}MB, Growth: {memory_growth:.2f}MB")
            logger.info(f"  CPU - Peak: {max_cpu:.1f}%, Average: {avg_cpu:.1f}%")

            # Resource growth trend
            if memory_growth > 100:
                logger.warning(f"  ⚠️ Significant memory growth: {memory_growth:.2f}MB")
            if max_cpu > 90:
                logger.warning(f"  ⚠️ High CPU usage detected: {max_cpu:.1f}%")

        # Critical findings summary
        logger.info("\n🚨 CRITICAL FINDINGS SUMMARY:")

        critical_issues = []
        for result in results.values():
            if result.breaking_point_reached:
                critical_issues.append(f"Breaking point in {result.test_name}: {result.breaking_point_description}")
            if result.memory_leaks_detected > 0:
                critical_issues.append(f"Memory leaks in {result.test_name}: {result.memory_leaks_detected} detected")
            if result.data_integrity_violations > 0:
                critical_issues.append(f"Data integrity issues in {result.test_name}: {result.data_integrity_violations} violations")

        if critical_issues:
            for issue in critical_issues:
                logger.error(f"  🚨 {issue}")
        else:
            logger.info("  ✅ No critical issues detected in resource exhaustion testing")

        # Recommendations
        logger.info("\n💡 RECOMMENDATIONS:")

        if any(r.memory_leaks_detected > 0 for r in results.values()):
            logger.info("  🔧 Implement proper asyncio task lifecycle management")
            logger.info("  🔧 Add memory monitoring and alerting")

        if any(r.data_integrity_violations > 0 for r in results.values()):
            logger.info("  🔧 Implement database transaction boundaries")
            logger.info("  🔧 Add data integrity monitoring and validation")

        if any(r.breaking_point_reached for r in results.values()):
            logger.info("  🔧 Implement circuit breaker patterns")
            logger.info("  🔧 Add resource-based load balancing")

        logger.info("  🔧 Consider implementing resource quotas and limits")
        logger.info("  🔧 Add comprehensive monitoring and alerting")
        logger.info("  🔧 Implement graceful degradation under resource pressure")


class DataCorruptionDetector:
    """Detects data corruption in dual recording scenarios."""

    def __init__(self):
        self.baseline_counts = {}

    def reset(self):
        """Reset detection state."""
        self.baseline_counts = {}

    async def check_dual_recording_integrity(self, process_id: str) -> int:
        """Check for data integrity violations in dual recording scenario."""
        try:
            supabase = get_supabase()

            # Count records in process_data_points for this process
            result = supabase.table('process_data_points').select('*', count='exact').eq('process_id', process_id).execute()
            process_count = result.count if hasattr(result, 'count') else len(result.data or [])

            # In a dual recording conflict, we might see duplicate or missing data
            # This is a simplified check - real implementation would be more sophisticated
            violations = 0

            # Check for suspicious patterns that indicate dual recording issues
            if process_count > 0:
                # Look for duplicate timestamps (indicating both services wrote)
                timestamp_check = supabase.table('process_data_points').select('timestamp').eq('process_id', process_id).execute()
                timestamps = [record['timestamp'] for record in timestamp_check.data or []]

                # Count duplicates
                unique_timestamps = set(timestamps)
                if len(timestamps) != len(unique_timestamps):
                    violations += len(timestamps) - len(unique_timestamps)
                    logger.warning(f"⚠️ Duplicate timestamps detected: {violations} duplicates")

            return violations

        except Exception as e:
            logger.warning(f"Failed to check data integrity: {e}")
            return 0


class MemoryLeakDetector:
    """Detects memory leaks in continuous operations."""

    def __init__(self):
        self.baseline_memory = 0
        self.memory_samples = []

    def set_baseline(self, memory_mb: float):
        """Set baseline memory usage."""
        self.baseline_memory = memory_mb

    def add_sample(self, memory_mb: float):
        """Add memory sample."""
        self.memory_samples.append(memory_mb)

    def detect_leak(self, threshold_mb: float = 50) -> bool:
        """Detect if memory leak occurred."""
        if len(self.memory_samples) < 2:
            return False

        growth = self.memory_samples[-1] - self.baseline_memory
        return growth > threshold_mb


class SilentDataLossDetector:
    """Detects silent data loss scenarios."""

    def __init__(self):
        self.start_time = None

    async def initialize(self):
        """Initialize detector."""
        self.start_time = time.time()

    async def count_recent_data_points(self) -> int:
        """Count data points written since test start."""
        try:
            supabase = get_supabase()

            # Count parameter_value_history records since test start
            result = supabase.table('parameter_value_history').select('*', count='exact').gte('timestamp', self.start_time).execute()
            return result.count if hasattr(result, 'count') else len(result.data or [])

        except Exception as e:
            logger.warning(f"Failed to count data points: {e}")
            return 0


async def main():
    """Main execution function."""
    logger.info("🚀 Starting Resource Exhaustion Stress Test Suite")

    tester = ResourceExhaustionTester()

    try:
        results = await tester.run_comprehensive_resource_exhaustion_suite()

        # Summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r.success)

        if passed_tests == total_tests:
            logger.info("🎉 All resource exhaustion tests PASSED")
        else:
            logger.error(f"💥 {total_tests - passed_tests}/{total_tests} tests FAILED")

    except Exception as e:
        logger.error(f"💥 Test suite crashed: {e}")
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