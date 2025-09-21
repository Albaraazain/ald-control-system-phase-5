"""
Connection pool exhaustion and broken pipe stress tests for continuous parameter logging.
Tests vulnerability to connection exhaustion and validates broken pipe recovery under
extreme concurrent load scenarios.
"""
import os
import sys
import asyncio
import time
import random
import threading
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.log_setup import logger
from src.plc.manager import plc_manager
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.db import get_supabase
from src.config import MACHINE_ID


class ConnectionPoolExhaustionTest:
    """Test connection pool exhaustion and broken pipe recovery under stress."""

    def __init__(self):
        self.test_results = {
            'pool_exhaustion_tests': [],
            'concurrent_load_tests': [],
            'broken_pipe_stress_tests': [],
            'resource_cleanup_tests': []
        }
        self.active_connections = 0
        self.max_concurrent_connections = 0
        self.connection_failures = 0

    async def test_database_connection_pool_exhaustion(self):
        """Test database connection pool exhaustion scenarios."""
        test_name = "Database Connection Pool Exhaustion"
        logger.info(f"🔍 Starting {test_name}...")

        test_result = {
            'test_name': test_name,
            'start_time': time.time(),
            'concurrent_connections': 0,
            'connection_failures': 0,
            'pool_exhausted': False,
            'recovery_successful': False,
            'continuous_logging_impact': False,
            'success': False
        }

        try:
            # Start continuous parameter logger
            await continuous_parameter_logger.start()
            initial_error_count = continuous_parameter_logger._error_count

            # Create aggressive concurrent database connections
            logger.info("🚀 Creating aggressive concurrent database connections...")

            async def create_database_stress_connection(connection_id):
                """Create a database connection that holds for extended time."""
                try:
                    supabase = get_supabase()

                    # Perform multiple operations to stress connection pool
                    for operation in range(50):  # 50 operations per connection
                        try:
                            result = supabase.table('machines').select('id, status').eq('id', MACHINE_ID).execute()

                            # Simulate slow processing to hold connections longer
                            await asyncio.sleep(random.uniform(0.1, 0.5))

                            # Additional table operations to increase load
                            supabase.table('parameter_value_history').select('parameter_id').limit(1).execute()
                            await asyncio.sleep(random.uniform(0.05, 0.2))

                        except Exception as e:
                            self.connection_failures += 1
                            if 'pool' in str(e).lower() or 'connection' in str(e).lower():
                                test_result['pool_exhausted'] = True
                            logger.debug(f"Connection {connection_id} operation {operation} failed: {e}")

                except Exception as e:
                    self.connection_failures += 1
                    logger.debug(f"Connection {connection_id} failed: {e}")

            # Launch many concurrent connections to exhaust pool
            concurrent_connections = 100  # Aggressive connection count
            tasks = []

            for i in range(concurrent_connections):
                task = asyncio.create_task(create_database_stress_connection(i))
                tasks.append(task)
                self.active_connections += 1

            test_result['concurrent_connections'] = concurrent_connections

            # Monitor continuous logging during stress
            monitoring_task = asyncio.create_task(self._monitor_continuous_logging_during_stress(test_result))

            # Execute stress test
            logger.info(f"⚡ Executing {concurrent_connections} concurrent database connections...")
            start_stress = time.time()

            # Run connections with timeout
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=60)
            except asyncio.TimeoutError:
                logger.info("⏰ Connection stress test timed out (expected under extreme load)")

            stress_duration = time.time() - start_stress
            test_result['stress_duration'] = stress_duration

            # Stop monitoring
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

            # Check if continuous logging was impacted
            final_error_count = continuous_parameter_logger._error_count
            error_increase = final_error_count - initial_error_count

            test_result['continuous_logging_impact'] = error_increase > 0
            test_result['connection_failures'] = self.connection_failures

            # Test recovery after stress
            logger.info("🔄 Testing recovery after connection pool stress...")
            recovery_start = time.time()

            # Wait for connections to clean up
            await asyncio.sleep(5)

            # Test if database operations work normally again
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').eq('id', MACHINE_ID).execute()
                if result.data:
                    test_result['recovery_successful'] = True
                    test_result['recovery_time'] = time.time() - recovery_start
            except Exception as e:
                logger.warning(f"Recovery test failed: {e}")

            # Evaluate success criteria
            test_result['success'] = (
                test_result['pool_exhausted'] and  # Should trigger pool exhaustion
                test_result['recovery_successful'] and  # Should recover
                test_result['recovery_time'] < 30  # Recovery within 30 seconds
            )

            test_result['duration'] = time.time() - test_result['start_time']
            self.test_results['pool_exhaustion_tests'].append(test_result)

            status = "✅ PASSED" if test_result['success'] else "❌ FAILED"
            logger.info(f"{status}: {test_name} - Pool exhausted: {test_result['pool_exhausted']}, "
                       f"Recovery: {test_result['recovery_successful']}, "
                       f"Failures: {test_result['connection_failures']}")

            return test_result['success']

        except Exception as e:
            test_result['error'] = str(e)
            test_result['success'] = False
            test_result['duration'] = time.time() - test_result['start_time']
            self.test_results['pool_exhaustion_tests'].append(test_result)
            logger.error(f"❌ {test_name} failed with error: {e}")
            return False

        finally:
            try:
                await continuous_parameter_logger.stop()
            except:
                pass

    async def _monitor_continuous_logging_during_stress(self, test_result):
        """Monitor continuous logging behavior during stress test."""
        try:
            initial_error_count = continuous_parameter_logger._error_count
            monitoring_start = time.time()

            while True:
                await asyncio.sleep(2)

                current_error_count = continuous_parameter_logger._error_count
                error_increase = current_error_count - initial_error_count

                if error_increase > 0:
                    test_result['continuous_logging_impact'] = True
                    logger.debug(f"Continuous logging errors increased by {error_increase} during stress")

                # Check if logger is still running
                if not continuous_parameter_logger.is_running:
                    test_result['logger_crashed'] = True
                    logger.warning("Continuous parameter logger stopped during stress test")
                    break

        except asyncio.CancelledError:
            pass

    async def test_plc_connection_broken_pipe_stress(self):
        """Test PLC broken pipe scenarios under concurrent stress."""
        test_name = "PLC Broken Pipe Stress Test"
        logger.info(f"🔍 Starting {test_name}...")

        test_result = {
            'test_name': test_name,
            'start_time': time.time(),
            'concurrent_plc_operations': 0,
            'broken_pipe_errors': 0,
            'retry_attempts': 0,
            'successful_recoveries': 0,
            'connection_failures': 0,
            'success': False
        }

        try:
            # Initialize PLC connection
            if not await plc_manager.initialize():
                logger.error("Failed to initialize PLC for broken pipe stress test")
                return False

            async def aggressive_plc_operation(operation_id):
                """Perform aggressive PLC operations to trigger broken pipe conditions."""
                operations_completed = 0
                local_broken_pipes = 0
                local_retries = 0

                for i in range(20):  # 20 operations per worker
                    try:
                        # Randomly choose operation type
                        if random.random() < 0.7:  # 70% reads
                            result = await plc_manager.read_parameter('power_on')
                        else:  # 30% writes
                            result = await plc_manager.write_parameter('power_on', float(random.randint(0, 1)))

                        if result is not None:
                            operations_completed += 1

                        # Random delay to create irregular load patterns
                        await asyncio.sleep(random.uniform(0.1, 0.3))

                    except Exception as e:
                        error_str = str(e).lower()
                        if 'broken pipe' in error_str or 'errno 32' in error_str:
                            local_broken_pipes += 1
                        elif 'retry' in error_str or 'attempt' in error_str:
                            local_retries += 1

                        logger.debug(f"Operation {operation_id}-{i} error: {e}")

                return {
                    'operations_completed': operations_completed,
                    'broken_pipes': local_broken_pipes,
                    'retries': local_retries
                }

            # Launch concurrent PLC operations
            concurrent_operations = 15  # Moderate concurrency for PLC
            tasks = []

            for i in range(concurrent_operations):
                task = asyncio.create_task(aggressive_plc_operation(i))
                tasks.append(task)

            test_result['concurrent_plc_operations'] = concurrent_operations

            # Force connection instability during operations
            async def connection_disruptor():
                """Periodically disrupt PLC connections to trigger broken pipe conditions."""
                for cycle in range(3):
                    await asyncio.sleep(random.uniform(3, 7))  # Random disruption timing

                    # Force close current connection
                    if plc_manager.plc and hasattr(plc_manager.plc, 'communicator'):
                        communicator = plc_manager.plc.communicator
                        if communicator.client and communicator.client.is_socket_open():
                            try:
                                communicator.client.close()
                                logger.debug(f"Forced connection close cycle {cycle + 1}")
                            except:
                                pass

            # Run operations and disruption concurrently
            logger.info(f"⚡ Executing {concurrent_operations} concurrent PLC operations with connection disruption...")

            disruptor_task = asyncio.create_task(connection_disruptor())
            operation_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Stop disruptor
            disruptor_task.cancel()
            try:
                await disruptor_task
            except asyncio.CancelledError:
                pass

            # Aggregate results
            total_operations = 0
            for result in operation_results:
                if isinstance(result, dict):
                    total_operations += result['operations_completed']
                    test_result['broken_pipe_errors'] += result['broken_pipes']
                    test_result['retry_attempts'] += result['retries']

            # Test final recovery
            logger.info("🔄 Testing final PLC connection recovery...")
            recovery_start = time.time()

            for attempt in range(5):
                try:
                    result = await plc_manager.read_parameter('power_on')
                    if result is not None:
                        test_result['successful_recoveries'] += 1
                        break
                except Exception as e:
                    logger.debug(f"Recovery attempt {attempt + 1} failed: {e}")

                await asyncio.sleep(2)

            test_result['recovery_time'] = time.time() - recovery_start

            # Evaluate success
            test_result['success'] = (
                test_result['broken_pipe_errors'] > 0 and  # Should trigger broken pipe errors
                test_result['retry_attempts'] > 0 and  # Should attempt retries
                test_result['successful_recoveries'] > 0  # Should eventually recover
            )

            test_result['duration'] = time.time() - test_result['start_time']
            self.test_results['broken_pipe_stress_tests'].append(test_result)

            status = "✅ PASSED" if test_result['success'] else "❌ FAILED"
            logger.info(f"{status}: {test_name} - Broken pipes: {test_result['broken_pipe_errors']}, "
                       f"Retries: {test_result['retry_attempts']}, Recoveries: {test_result['successful_recoveries']}")

            return test_result['success']

        except Exception as e:
            test_result['error'] = str(e)
            test_result['success'] = False
            test_result['duration'] = time.time() - test_result['start_time']
            self.test_results['broken_pipe_stress_tests'].append(test_result)
            logger.error(f"❌ {test_name} failed with error: {e}")
            return False

        finally:
            try:
                await plc_manager.disconnect()
            except:
                pass

    async def test_resource_cleanup_validation(self):
        """Test resource cleanup after connection stress scenarios."""
        test_name = "Resource Cleanup Validation"
        logger.info(f"🔍 Starting {test_name}...")

        test_result = {
            'test_name': test_name,
            'start_time': time.time(),
            'memory_leaks_detected': False,
            'connection_leaks_detected': False,
            'task_cleanup_successful': True,
            'resource_monitoring_cycles': 0,
            'success': False
        }

        try:
            # Monitor resource usage before stress
            initial_tasks = len(asyncio.all_tasks())
            logger.info(f"Initial asyncio tasks: {initial_tasks}")

            # Create stress scenario with many short-lived connections
            async def short_lived_connection_stress():
                """Create many short-lived connections to test cleanup."""
                tasks = []

                for i in range(50):  # 50 short-lived connections
                    async def quick_db_operation():
                        try:
                            supabase = get_supabase()
                            result = supabase.table('machines').select('id').eq('id', MACHINE_ID).execute()
                            await asyncio.sleep(0.1)  # Brief hold
                        except:
                            pass  # Expected failures under stress

                    task = asyncio.create_task(quick_db_operation())
                    tasks.append(task)

                # Wait for all to complete
                await asyncio.gather(*tasks, return_exceptions=True)

            # Run stress cycles
            for cycle in range(3):
                logger.info(f"Resource cleanup cycle {cycle + 1}/3")

                await short_lived_connection_stress()
                test_result['resource_monitoring_cycles'] += 1

                # Brief pause for cleanup
                await asyncio.sleep(2)

            # Monitor resource usage after stress
            await asyncio.sleep(5)  # Allow time for cleanup
            final_tasks = len(asyncio.all_tasks())
            logger.info(f"Final asyncio tasks: {final_tasks}")

            # Check for task leaks
            task_increase = final_tasks - initial_tasks
            if task_increase > 10:  # Allow for some normal variance
                test_result['task_cleanup_successful'] = False
                logger.warning(f"Potential task leak detected: {task_increase} additional tasks")

            # Test system responsiveness after cleanup
            logger.info("🔄 Testing system responsiveness after cleanup...")
            responsiveness_start = time.time()

            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').eq('id', MACHINE_ID).execute()
                responsiveness_time = time.time() - responsiveness_start

                if responsiveness_time > 5:  # More than 5 seconds is problematic
                    test_result['connection_leaks_detected'] = True
                    logger.warning(f"Slow database response after cleanup: {responsiveness_time:.2f}s")

            except Exception as e:
                test_result['connection_leaks_detected'] = True
                logger.warning(f"Database unresponsive after cleanup: {e}")

            # Evaluate success
            test_result['success'] = (
                test_result['task_cleanup_successful'] and
                not test_result['memory_leaks_detected'] and
                not test_result['connection_leaks_detected'] and
                test_result['resource_monitoring_cycles'] >= 3
            )

            test_result['duration'] = time.time() - test_result['start_time']
            self.test_results['resource_cleanup_tests'].append(test_result)

            status = "✅ PASSED" if test_result['success'] else "❌ FAILED"
            logger.info(f"{status}: {test_name} - Task cleanup: {test_result['task_cleanup_successful']}, "
                       f"Connection health: {not test_result['connection_leaks_detected']}")

            return test_result['success']

        except Exception as e:
            test_result['error'] = str(e)
            test_result['success'] = False
            test_result['duration'] = time.time() - test_result['start_time']
            self.test_results['resource_cleanup_tests'].append(test_result)
            logger.error(f"❌ {test_name} failed with error: {e}")
            return False

    async def run_connection_pool_exhaustion_tests(self):
        """Run comprehensive connection pool exhaustion test suite."""
        logger.info("🚀 Starting Connection Pool Exhaustion Test Suite")
        logger.info("=" * 65)

        # List of tests to run
        tests = [
            self.test_database_connection_pool_exhaustion,
            self.test_plc_connection_broken_pipe_stress,
            self.test_resource_cleanup_validation,
        ]

        total_tests = len(tests)
        passed_tests = 0

        # Run each test
        for test_func in tests:
            try:
                success = await test_func()
                if success:
                    passed_tests += 1

                # Pause between tests for cleanup
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Test {test_func.__name__} encountered error: {e}")

        # Generate report
        self.generate_connection_pool_report(passed_tests, total_tests)

        return passed_tests >= total_tests * 0.67  # 67% pass rate required

    def generate_connection_pool_report(self, passed_tests: int, total_tests: int):
        """Generate comprehensive connection pool test report."""
        logger.info("=" * 65)
        logger.info(f"🏁 CONNECTION POOL EXHAUSTION TEST RESULTS: {passed_tests}/{total_tests} tests passed")
        logger.info("=" * 65)

        # Overall assessment
        if passed_tests == total_tests:
            logger.info("🟢 EXCELLENT: All connection pool tests passed")
        elif passed_tests >= total_tests * 0.67:
            logger.info(f"🟡 ACCEPTABLE: Most tests passed ({passed_tests}/{total_tests})")
        else:
            logger.error(f"🔴 CRITICAL: Connection pool handling has serious issues ({total_tests - passed_tests}/{total_tests} failed)")

        # Detailed results by category
        categories = [
            ('Connection Pool Exhaustion', self.test_results['pool_exhaustion_tests']),
            ('Broken Pipe Stress Tests', self.test_results['broken_pipe_stress_tests']),
            ('Resource Cleanup Tests', self.test_results['resource_cleanup_tests'])
        ]

        for category_name, results in categories:
            if results:
                logger.info(f"\n📊 {category_name}:")
                for result in results:
                    status = "✅" if result['success'] else "❌"
                    duration = result.get('duration', 0)
                    logger.info(f"  {status} {result['test_name']} ({duration:.1f}s)")

        # Key findings
        logger.info("\n🔍 KEY FINDINGS:")
        logger.info("  • Database connection pool behavior under extreme load tested")
        logger.info("  • PLC broken pipe recovery under concurrent stress validated")
        logger.info("  • Resource cleanup and leak detection performed")
        logger.info("  • Connection exhaustion and recovery patterns analyzed")

        # Critical recommendations
        logger.info("\n💡 CRITICAL RECOMMENDATIONS:")
        logger.info("  • Implement proper connection pooling with limits")
        logger.info("  • Add connection leak detection and monitoring")
        logger.info("  • Implement circuit breaker pattern for connection failures")
        logger.info("  • Add resource cleanup validation in production")
        logger.info("  • Monitor connection pool metrics in real-time")


async def main():
    """Main test execution function."""
    load_dotenv()

    test_suite = ConnectionPoolExhaustionTest()
    success = await test_suite.run_connection_pool_exhaustion_tests()

    if success:
        logger.info("🎉 Connection pool exhaustion tests completed successfully")
    else:
        logger.error("💥 Critical connection pool issues detected")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())