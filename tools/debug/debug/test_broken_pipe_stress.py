"""
High-frequency operation stress test for broken pipe error validation.
This test performs rapid, concurrent operations to trigger broken pipe conditions
and validate the retry/recovery mechanisms in PLCCommunicator.
"""
import os
import sys
import asyncio
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Add parent directory to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_setup import logger
from plc.manager import plc_manager


class BrokenPipeStressTest:
    """High-frequency stress test to validate broken pipe error handling."""

    def __init__(self):
        self.test_results = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'broken_pipe_errors': 0,
            'connection_errors': 0,
            'retry_attempts': 0,
            'timeout_errors': 0,
            'automatic_reconnections': 0,
            'test_duration': 0,
            'operations_per_second': 0,
            'error_rate': 0,
            'recovery_rate': 0
        }
        self.operation_log = []
        self.error_patterns = []

    async def setup_test(self):
        """Setup test environment."""
        logger.info("🔧 Setting up stress test environment...")

        success = await plc_manager.initialize()
        if not success:
            logger.error("❌ Failed to establish initial PLC connection")
            return False

        logger.info("✅ Stress test environment ready")
        return True

    async def single_read_operation(self, operation_id, address=0):
        """Perform a single read operation with error tracking."""
        operation_start = time.time()
        result = {
            'id': operation_id,
            'type': 'read_float',
            'address': address,
            'start_time': operation_start,
            'success': False,
            'error': None,
            'duration': 0,
            'retry_detected': False
        }

        try:
            # Perform the actual read operation
            value = plc_manager.plc.communicator.read_float(address)

            result['duration'] = time.time() - operation_start

            if value is not None:
                result['success'] = True
                result['value'] = value
                self.test_results['successful_operations'] += 1
            else:
                result['error'] = 'returned_none'
                self.test_results['failed_operations'] += 1

        except Exception as e:
            result['duration'] = time.time() - operation_start
            result['error'] = str(e)
            result['success'] = False
            self.test_results['failed_operations'] += 1

            # Categorize the error
            error_str = str(e).lower()
            if 'broken pipe' in error_str or 'errno 32' in error_str:
                self.test_results['broken_pipe_errors'] += 1
                result['error_type'] = 'broken_pipe'
            elif 'connection' in error_str or 'connect' in error_str:
                self.test_results['connection_errors'] += 1
                result['error_type'] = 'connection'
            elif 'timeout' in error_str:
                self.test_results['timeout_errors'] += 1
                result['error_type'] = 'timeout'
            elif 'attempt' in error_str or 'retry' in error_str:
                self.test_results['retry_attempts'] += 1
                result['retry_detected'] = True
                result['error_type'] = 'retry'
            else:
                result['error_type'] = 'other'

        self.test_results['total_operations'] += 1
        self.operation_log.append(result)
        return result

    async def single_write_operation(self, operation_id, address=1, value=None):
        """Perform a single write operation with error tracking."""
        if value is None:
            value = random.uniform(0.0, 100.0)  # Random test value

        operation_start = time.time()
        result = {
            'id': operation_id,
            'type': 'write_float',
            'address': address,
            'value': value,
            'start_time': operation_start,
            'success': False,
            'error': None,
            'duration': 0,
            'retry_detected': False
        }

        try:
            # Perform the actual write operation
            success = plc_manager.plc.communicator.write_float(address, value)

            result['duration'] = time.time() - operation_start

            if success:
                result['success'] = True
                self.test_results['successful_operations'] += 1
            else:
                result['error'] = 'write_failed'
                self.test_results['failed_operations'] += 1

        except Exception as e:
            result['duration'] = time.time() - operation_start
            result['error'] = str(e)
            result['success'] = False
            self.test_results['failed_operations'] += 1

            # Categorize the error
            error_str = str(e).lower()
            if 'broken pipe' in error_str or 'errno 32' in error_str:
                self.test_results['broken_pipe_errors'] += 1
                result['error_type'] = 'broken_pipe'
            elif 'connection' in error_str or 'connect' in error_str:
                self.test_results['connection_errors'] += 1
                result['error_type'] = 'connection'
            elif 'timeout' in error_str:
                self.test_results['timeout_errors'] += 1
                result['error_type'] = 'timeout'
            elif 'attempt' in error_str or 'retry' in error_str:
                self.test_results['retry_attempts'] += 1
                result['retry_detected'] = True
                result['error_type'] = 'retry'
            else:
                result['error_type'] = 'other'

        self.test_results['total_operations'] += 1
        self.operation_log.append(result)
        return result

    async def burst_operations_test(self, burst_size=20, burst_delay=0.1):
        """Perform rapid burst of operations to stress the connection."""
        logger.info(f"🚀 Starting burst test: {burst_size} operations with {burst_delay}s delay")

        tasks = []
        for i in range(burst_size):
            # Mix read and write operations
            if i % 3 == 0:  # Every 3rd operation is a write
                address = random.randint(1, 10)  # Random write address
                task = self.single_write_operation(f"burst_{i}", address)
            else:
                address = random.randint(0, 10)  # Random read address
                task = self.single_read_operation(f"burst_{i}", address)

            tasks.append(task)

            # Small delay to create burst pattern
            if burst_delay > 0:
                await asyncio.sleep(burst_delay)

        # Wait for all operations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful operations in this burst
        burst_success = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
        logger.info(f"📊 Burst complete: {burst_success}/{burst_size} operations successful")

        return results

    async def concurrent_operations_test(self, concurrent_count=10, duration=30):
        """Run concurrent operations for a specified duration."""
        logger.info(f"⚡ Starting concurrent test: {concurrent_count} concurrent operations for {duration}s")

        start_time = time.time()
        operation_counter = 0

        async def operation_worker(worker_id):
            """Worker function for concurrent operations."""
            nonlocal operation_counter
            while time.time() - start_time < duration:
                operation_counter += 1
                operation_id = f"concurrent_{worker_id}_{operation_counter}"

                # Randomly choose operation type
                if random.random() < 0.7:  # 70% reads, 30% writes
                    address = random.randint(0, 20)
                    await self.single_read_operation(operation_id, address)
                else:
                    address = random.randint(1, 20)
                    value = random.uniform(0.0, 1000.0)
                    await self.single_write_operation(operation_id, address, value)

                # Random delay between operations (0-500ms)
                await asyncio.sleep(random.uniform(0, 0.5))

        # Start concurrent workers
        workers = [operation_worker(i) for i in range(concurrent_count)]
        await asyncio.gather(*workers, return_exceptions=True)

        duration_actual = time.time() - start_time
        logger.info(f"📊 Concurrent test complete: {duration_actual:.2f}s duration")

    async def escalating_load_test(self):
        """Test with escalating load to find breaking point."""
        logger.info("📈 Starting escalating load test...")

        load_levels = [1, 3, 5, 10, 15, 20]  # Concurrent operations
        for level in load_levels:
            logger.info(f"🔄 Testing load level: {level} concurrent operations")

            # Record state before this load level
            ops_before = self.test_results['total_operations']
            errors_before = self.test_results['failed_operations']

            # Run concurrent test at this level for 15 seconds
            await self.concurrent_operations_test(level, 15)

            # Analyze results for this level
            ops_this_level = self.test_results['total_operations'] - ops_before
            errors_this_level = self.test_results['failed_operations'] - errors_before
            error_rate = errors_this_level / ops_this_level if ops_this_level > 0 else 0

            logger.info(f"📊 Load level {level}: {ops_this_level} ops, {error_rate:.2%} error rate")

            # Brief pause between load levels
            await asyncio.sleep(2)

    async def connection_resilience_test(self):
        """Test connection resilience by forcing reconnections."""
        logger.info("🔄 Starting connection resilience test...")

        for cycle in range(3):
            logger.info(f"🔄 Resilience cycle {cycle + 1}/3")

            # Perform some operations
            await self.burst_operations_test(burst_size=10, burst_delay=0.2)

            # Force disconnect and reconnect
            try:
                await plc_manager.disconnect()
                await asyncio.sleep(1)  # Brief disconnect

                reconnect_success = await plc_manager.initialize()
                if reconnect_success:
                    self.test_results['automatic_reconnections'] += 1
                    logger.info("✅ Manual reconnection successful")
                else:
                    logger.warning("⚠️ Manual reconnection failed")

            except Exception as e:
                logger.warning(f"⚠️ Reconnection cycle error: {e}")

            # Test operations after reconnection
            await self.burst_operations_test(burst_size=5, burst_delay=0.1)

            await asyncio.sleep(2)  # Pause between cycles

    async def run_comprehensive_stress_test(self, total_duration=120):
        """Run comprehensive stress test suite."""
        start_time = time.time()

        logger.info("🚀 Starting comprehensive broken pipe stress test...")
        logger.info(f"⏱️ Total test duration: {total_duration} seconds")

        try:
            # Setup
            if not await self.setup_test():
                return False

            remaining_time = total_duration

            # Phase 1: Burst operations (25% of time)
            phase_duration = remaining_time * 0.25
            logger.info(f"📊 Phase 1: Burst operations ({phase_duration:.0f}s)")
            phase_start = time.time()

            while time.time() - phase_start < phase_duration:
                await self.burst_operations_test(burst_size=15, burst_delay=0.05)
                await asyncio.sleep(1)

            # Phase 2: Concurrent operations (40% of time)
            phase_duration = remaining_time * 0.40
            logger.info(f"📊 Phase 2: Concurrent operations ({phase_duration:.0f}s)")
            await self.concurrent_operations_test(concurrent_count=8, duration=phase_duration)

            # Phase 3: Escalating load (25% of time)
            phase_duration = remaining_time * 0.25
            logger.info(f"📊 Phase 3: Escalating load test ({phase_duration:.0f}s)")
            await self.escalating_load_test()

            # Phase 4: Connection resilience (10% of time)
            logger.info("📊 Phase 4: Connection resilience test")
            await self.connection_resilience_test()

            # Calculate final metrics
            self.test_results['test_duration'] = time.time() - start_time
            if self.test_results['test_duration'] > 0:
                self.test_results['operations_per_second'] = (
                    self.test_results['total_operations'] / self.test_results['test_duration']
                )

            if self.test_results['total_operations'] > 0:
                self.test_results['error_rate'] = (
                    self.test_results['failed_operations'] / self.test_results['total_operations']
                )

            if self.test_results['failed_operations'] > 0:
                self.test_results['recovery_rate'] = (
                    self.test_results['successful_operations'] /
                    (self.test_results['successful_operations'] + self.test_results['failed_operations'])
                )

            # Report results
            self.report_stress_test_results()
            self.analyze_error_patterns()

            return True

        except Exception as e:
            logger.error(f"❌ Stress test failed: {e}", exc_info=True)
            return False

        finally:
            if plc_manager.is_connected():
                await plc_manager.disconnect()

    def report_stress_test_results(self):
        """Report comprehensive stress test results."""
        logger.info("📊 BROKEN PIPE STRESS TEST RESULTS")
        logger.info("=" * 60)

        r = self.test_results

        logger.info("🔢 OPERATION STATISTICS:")
        logger.info(f"  Total operations: {r['total_operations']}")
        logger.info(f"  Successful operations: {r['successful_operations']}")
        logger.info(f"  Failed operations: {r['failed_operations']}")
        logger.info(f"  Operations per second: {r['operations_per_second']:.2f}")
        logger.info(f"  Overall error rate: {r['error_rate']:.2%}")

        logger.info("\n🚫 ERROR BREAKDOWN:")
        logger.info(f"  Broken pipe errors: {r['broken_pipe_errors']}")
        logger.info(f"  Connection errors: {r['connection_errors']}")
        logger.info(f"  Timeout errors: {r['timeout_errors']}")
        logger.info(f"  Retry attempts logged: {r['retry_attempts']}")

        logger.info("\n🔄 RECOVERY STATISTICS:")
        logger.info(f"  Automatic reconnections: {r['automatic_reconnections']}")
        logger.info(f"  Recovery rate: {r['recovery_rate']:.2%}")
        logger.info(f"  Test duration: {r['test_duration']:.2f} seconds")

        # Performance evaluation
        logger.info("\n🎯 PERFORMANCE EVALUATION:")

        if r['operations_per_second'] > 5:
            logger.info("✅ Good throughput maintained under stress")
        elif r['operations_per_second'] > 2:
            logger.warning("⚠️ Moderate throughput - acceptable but could be improved")
        else:
            logger.error("❌ Low throughput - performance issues detected")

        if r['error_rate'] < 0.05:  # Less than 5% error rate
            logger.info("✅ Low error rate - system handling stress well")
        elif r['error_rate'] < 0.15:  # Less than 15% error rate
            logger.warning("⚠️ Moderate error rate - some issues under stress")
        else:
            logger.error("❌ High error rate - significant issues under stress")

        if r['broken_pipe_errors'] == 0:
            logger.info("✅ No broken pipe errors - fixes are working effectively")
        elif r['broken_pipe_errors'] < r['total_operations'] * 0.02:  # Less than 2%
            logger.warning("⚠️ Few broken pipe errors detected - mostly handled by retry logic")
        else:
            logger.error("❌ Significant broken pipe errors - fixes may need improvement")

        if r['retry_attempts'] > 0:
            logger.info("✅ Retry logic is active and attempting recovery")
        else:
            logger.warning("⚠️ No retry attempts logged - retry logic may not be working")

    def analyze_error_patterns(self):
        """Analyze error patterns from the operation log."""
        logger.info("\n🔍 ERROR PATTERN ANALYSIS:")

        if not self.operation_log:
            logger.warning("No operation log data available for analysis")
            return

        # Group errors by type
        error_types = {}
        successful_ops = 0

        for op in self.operation_log:
            if op['success']:
                successful_ops += 1
            else:
                error_type = op.get('error_type', 'unknown')
                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append(op)

        # Report error patterns
        for error_type, errors in error_types.items():
            avg_duration = sum(e['duration'] for e in errors) / len(errors)
            logger.info(f"  {error_type}: {len(errors)} occurrences, avg duration: {avg_duration:.3f}s")

        # Temporal analysis
        error_times = [op['start_time'] for op in self.operation_log if not op['success']]
        if len(error_times) > 1:
            error_intervals = [error_times[i] - error_times[i-1] for i in range(1, len(error_times))]
            avg_interval = sum(error_intervals) / len(error_intervals)
            logger.info(f"  Average time between errors: {avg_interval:.2f}s")

        # Success rate over time
        total_ops = len(self.operation_log)
        if total_ops > 0:
            success_rate = successful_ops / total_ops
            logger.info(f"  Overall success rate: {success_rate:.2%}")


async def main():
    """Main test execution function."""
    load_dotenv()

    test = BrokenPipeStressTest()
    success = await test.run_comprehensive_stress_test(total_duration=90)  # 90 second test

    if success:
        logger.info("🎉 Stress test completed successfully")
    else:
        logger.error("💥 Stress test failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())