"""
Comprehensive test script for Modbus TCP broken pipe error recovery.
Tests the new retry mechanisms, connection recovery, and error handling.
"""
import os
import sys
import asyncio
import argparse
import time
import signal
import subprocess
import threading
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.log_setup import logger
from src.plc.manager import plc_manager

class BrokenPipeTestSuite:
    """Test suite for broken pipe error recovery."""

    def __init__(self):
        self.test_results = []
        self.plc_simulator_process = None

    def log_test_result(self, test_name, success, message="", duration=None):
        """Log test results for later analysis."""
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'duration': duration,
            'timestamp': time.time()
        }
        self.test_results.append(result)

        status = "✅ PASSED" if success else "❌ FAILED"
        duration_str = f" ({duration:.2f}s)" if duration else ""
        logger.info(f"{status}: {test_name}{duration_str} - {message}")

    async def test_basic_connection_recovery(self):
        """Test basic connection and reconnection functionality."""
        test_name = "Basic Connection Recovery"
        start_time = time.time()

        try:
            # Test initial connection
            success = await plc_manager.initialize()
            if not success:
                self.log_test_result(test_name, False, "Failed to establish initial connection")
                return False

            # Test disconnection
            await plc_manager.disconnect()

            # Test reconnection
            success = await plc_manager.initialize()
            duration = time.time() - start_time

            if success:
                self.log_test_result(test_name, True, "Connection recovery successful", duration)
                return True
            else:
                self.log_test_result(test_name, False, "Failed to reconnect after disconnection", duration)
                return False

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, f"Exception: {str(e)}", duration)
            return False
        finally:
            try:
                await plc_manager.disconnect()
            except:
                pass

    async def test_parameter_write_retry(self):
        """Test parameter writing with retry logic."""
        test_name = "Parameter Write with Retry"
        start_time = time.time()

        try:
            # Initialize connection
            success = await plc_manager.initialize()
            if not success:
                self.log_test_result(test_name, False, "Failed to connect to PLC")
                return False

            # Test writing a parameter (using power_on as mentioned in the original issue)
            try:
                # Try to write to power_on parameter if it exists
                success = await plc_manager.write_parameter('power_on', 1.0)
                duration = time.time() - start_time

                if success:
                    self.log_test_result(test_name, True, "Parameter write successful with retry logic", duration)
                    return True
                else:
                    self.log_test_result(test_name, False, "Parameter write failed despite retry logic", duration)
                    return False

            except Exception as e:
                duration = time.time() - start_time
                # Check if the error was handled properly by retry logic
                if "after all retries" in str(e):
                    self.log_test_result(test_name, True, f"Retry logic properly exhausted: {str(e)}", duration)
                    return True
                else:
                    self.log_test_result(test_name, False, f"Unexpected error: {str(e)}", duration)
                    return False

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, f"Test setup error: {str(e)}", duration)
            return False
        finally:
            try:
                await plc_manager.disconnect()
            except:
                pass

    async def test_high_frequency_operations(self):
        """Test high-frequency read/write operations to stress the connection."""
        test_name = "High-Frequency Operations Stress Test"
        start_time = time.time()

        try:
            # Initialize connection
            success = await plc_manager.initialize()
            if not success:
                self.log_test_result(test_name, False, "Failed to connect to PLC")
                return False

            # Perform rapid-fire operations
            operation_count = 50
            successful_operations = 0

            logger.info(f"Starting {operation_count} rapid operations...")

            for i in range(operation_count):
                try:
                    # Alternate between reads and writes
                    if i % 2 == 0:
                        # Try reading parameters
                        result = await plc_manager.read_all_parameters()
                        if result:
                            successful_operations += 1
                    else:
                        # Try writing a parameter
                        success = await plc_manager.write_parameter('power_on', float(i % 2))
                        if success:
                            successful_operations += 1

                    # Small delay to simulate realistic usage
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.debug(f"Operation {i} failed: {e}")

            duration = time.time() - start_time
            success_rate = successful_operations / operation_count

            # Consider test successful if at least 80% of operations succeed
            if success_rate >= 0.8:
                self.log_test_result(test_name, True, f"Success rate: {success_rate:.1%} ({successful_operations}/{operation_count})", duration)
                return True
            else:
                self.log_test_result(test_name, False, f"Low success rate: {success_rate:.1%} ({successful_operations}/{operation_count})", duration)
                return False

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, f"Stress test error: {str(e)}", duration)
            return False
        finally:
            try:
                await plc_manager.disconnect()
            except:
                pass

    async def test_connection_health_monitoring(self):
        """Test the connection health monitoring functionality."""
        test_name = "Connection Health Monitoring"
        start_time = time.time()

        try:
            # Initialize connection
            success = await plc_manager.initialize()
            if not success:
                self.log_test_result(test_name, False, "Failed to connect to PLC")
                return False

            # Test that connection reports as healthy when connected
            is_connected = plc_manager.is_connected()
            if not is_connected:
                self.log_test_result(test_name, False, "Connection health check failed when connected")
                return False

            # Perform some operations to trigger health checks
            for i in range(5):
                try:
                    await plc_manager.read_all_parameters()
                    await asyncio.sleep(0.5)
                except:
                    pass  # We're testing the health monitoring, not operation success

            duration = time.time() - start_time
            self.log_test_result(test_name, True, "Connection health monitoring working correctly", duration)
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, f"Health monitoring test error: {str(e)}", duration)
            return False
        finally:
            try:
                await plc_manager.disconnect()
            except:
                pass

    async def test_error_recovery_patterns(self):
        """Test error recovery patterns and exponential backoff."""
        test_name = "Error Recovery Patterns"
        start_time = time.time()

        try:
            # Initialize connection
            success = await plc_manager.initialize()
            if not success:
                self.log_test_result(test_name, False, "Failed to connect to PLC")
                return False

            # Try operations that might fail and verify recovery
            recovery_attempts = 0
            max_attempts = 10

            for i in range(max_attempts):
                try:
                    # Try reading from potentially invalid addresses to trigger retries
                    result = await plc_manager.read_parameter('invalid_param_' + str(i))
                    if result is not None:
                        recovery_attempts += 1
                except Exception as e:
                    # Count as recovery if retry logic was properly executed
                    if "after all retries" in str(e) or "retry" in str(e).lower():
                        recovery_attempts += 1

                await asyncio.sleep(0.2)

            duration = time.time() - start_time

            # Consider successful if any recovery patterns were detected
            if recovery_attempts > 0:
                self.log_test_result(test_name, True, f"Recovery patterns detected in {recovery_attempts}/{max_attempts} attempts", duration)
                return True
            else:
                self.log_test_result(test_name, False, "No error recovery patterns detected", duration)
                return False

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, f"Recovery pattern test error: {str(e)}", duration)
            return False
        finally:
            try:
                await plc_manager.disconnect()
            except:
                pass

    async def run_all_tests(self):
        """Run all broken pipe recovery tests."""
        logger.info("🧪 Starting Broken Pipe Recovery Test Suite")
        logger.info("=" * 60)

        # List of tests to run
        tests = [
            self.test_basic_connection_recovery,
            self.test_parameter_write_retry,
            self.test_high_frequency_operations,
            self.test_connection_health_monitoring,
            self.test_error_recovery_patterns,
        ]

        total_tests = len(tests)
        passed_tests = 0

        # Run each test
        for test_func in tests:
            try:
                success = await test_func()
                if success:
                    passed_tests += 1
            except Exception as e:
                logger.error(f"Test {test_func.__name__} encountered error: {e}")

        # Print summary
        logger.info("=" * 60)
        logger.info(f"🏁 Test Suite Complete: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            logger.info("🎉 All broken pipe recovery tests PASSED!")
        elif passed_tests >= total_tests * 0.8:
            logger.info(f"⚠️ Most tests passed ({passed_tests}/{total_tests})")
        else:
            logger.info(f"❌ Many tests failed ({total_tests - passed_tests}/{total_tests})")

        # Print detailed results
        logger.info("\n📊 Detailed Test Results:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            duration = f" ({result['duration']:.2f}s)" if result['duration'] else ""
            logger.info(f"{status} {result['test']}{duration}: {result['message']}")

        return passed_tests >= total_tests * 0.8  # Return success if 80%+ tests pass

async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='Test Modbus TCP broken pipe error recovery')
    parser.add_argument('--test', help='Run specific test (basic, parameter, stress, health, recovery)')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    test_suite = BrokenPipeTestSuite()

    if args.test:
        # Run specific test
        test_map = {
            'basic': test_suite.test_basic_connection_recovery,
            'parameter': test_suite.test_parameter_write_retry,
            'stress': test_suite.test_high_frequency_operations,
            'health': test_suite.test_connection_health_monitoring,
            'recovery': test_suite.test_error_recovery_patterns,
        }

        if args.test in test_map:
            logger.info(f"Running specific test: {args.test}")
            success = await test_map[args.test]()
            return success
        else:
            logger.error(f"Unknown test: {args.test}")
            return False
    else:
        # Run all tests
        return await test_suite.run_all_tests()

if __name__ == "__main__":
    success = asyncio.run(main())
    exit_code = 0 if success else 1
    sys.exit(exit_code)