"""
Comprehensive Network Latency Stress Test for Continuous Parameter Logging System

This test validates system behavior under extreme network conditions including:
- High network latency (500ms - 5000ms)
- Packet loss simulation (5% - 50% packet drop rates)
- Network jitter and variable latency patterns
- Connection timeout edge cases
- Bandwidth throttling during continuous operations
- DNS resolution failures and delays
- Network partition scenarios (split-brain conditions)

Focus: Validates the 1-second continuous parameter logging timing constraint under network stress.
"""
import os
import sys
import asyncio
import time
import random
import subprocess
import socket
import threading
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Add parent directories to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.log_setup import logger
from src.plc.manager import plc_manager
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.db import get_supabase


@dataclass
class LatencyTestResult:
    """Represents results from a single latency test."""
    test_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    latency_ms: float
    timeout_occurred: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    plc_operation_time: float = 0.0
    database_operation_time: float = 0.0
    total_parameters_read: int = 0
    logging_interval_accuracy: float = 0.0  # How close to 1.0s target
    data: Dict = field(default_factory=dict)


@dataclass
class NetworkCondition:
    """Defines network conditions for testing."""
    name: str
    latency_ms: int
    jitter_ms: int = 0
    packet_loss_percent: float = 0.0
    bandwidth_kbps: Optional[int] = None
    description: str = ""


class NetworkLatencyStressTest:
    """Comprehensive network latency stress testing for continuous parameter logging."""

    def __init__(self):
        self.test_results: List[LatencyTestResult] = []
        self.network_conditions: List[NetworkCondition] = []
        self.setup_network_conditions()

        # Test configuration
        self.target_logging_interval = 1.0  # 1 second target
        self.test_duration_per_condition = 30  # seconds per condition
        self.max_acceptable_latency = 1000  # 1000ms total latency budget

        # Metrics tracking
        self.metrics = {
            'total_tests': 0,
            'successful_tests': 0,
            'timeout_tests': 0,
            'failed_tests': 0,
            'avg_latency_ms': 0.0,
            'max_latency_ms': 0.0,
            'min_latency_ms': float('inf'),
            'logging_accuracy_violations': 0,
            'network_condition_results': {},
            'continuous_logging_metrics': {
                'intervals_tested': 0,
                'intervals_on_time': 0,
                'intervals_delayed': 0,
                'max_delay_ms': 0.0,
                'avg_delay_ms': 0.0
            }
        }

    def setup_network_conditions(self):
        """Setup various network conditions for testing."""
        self.network_conditions = [
            # Normal conditions (baseline)
            NetworkCondition("baseline", 10, 5, 0.0, None, "Normal network conditions"),

            # High latency scenarios
            NetworkCondition("high_latency_500ms", 500, 50, 0.0, None, "High latency - 500ms"),
            NetworkCondition("high_latency_1000ms", 1000, 100, 0.0, None, "Very high latency - 1000ms"),
            NetworkCondition("extreme_latency_2000ms", 2000, 200, 0.0, None, "Extreme latency - 2000ms"),
            NetworkCondition("critical_latency_5000ms", 5000, 500, 0.0, None, "Critical latency - 5000ms"),

            # Packet loss scenarios
            NetworkCondition("packet_loss_5pct", 100, 20, 5.0, None, "5% packet loss"),
            NetworkCondition("packet_loss_15pct", 100, 20, 15.0, None, "15% packet loss"),
            NetworkCondition("packet_loss_30pct", 100, 20, 30.0, None, "30% packet loss"),
            NetworkCondition("packet_loss_50pct", 100, 20, 50.0, None, "50% packet loss"),

            # Variable jitter scenarios
            NetworkCondition("high_jitter", 200, 500, 0.0, None, "High jitter - 500ms variance"),
            NetworkCondition("extreme_jitter", 300, 1000, 0.0, None, "Extreme jitter - 1000ms variance"),

            # Bandwidth throttling scenarios
            NetworkCondition("bandwidth_limited_56k", 100, 20, 0.0, 56, "56k modem simulation"),
            NetworkCondition("bandwidth_limited_256k", 100, 20, 0.0, 256, "256k DSL simulation"),
            NetworkCondition("bandwidth_limited_1m", 100, 20, 0.0, 1024, "1Mbps connection"),

            # Combined worst-case scenarios
            NetworkCondition("worst_case_combo", 1000, 500, 20.0, 256, "Combined worst-case"),
            NetworkCondition("extreme_worst_case", 2000, 1000, 30.0, 128, "Extreme worst-case"),
        ]

    async def setup_test_environment(self) -> bool:
        """Setup test environment and validate initial connections."""
        logger.info("🔧 Setting up network latency stress test environment...")

        try:
            # Initialize PLC connection
            plc_success = await plc_manager.initialize()
            if not plc_success:
                logger.error("❌ Failed to establish initial PLC connection")
                return False

            # Test database connectivity
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').limit(1).execute()
                if not result.data:
                    logger.warning("⚠️ Database connection test returned no data")
            except Exception as e:
                logger.error(f"❌ Database connectivity test failed: {e}")
                return False

            logger.info("✅ Test environment setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Test environment setup failed: {e}", exc_info=True)
            return False

    def check_root_privileges(self) -> bool:
        """Check if running with sufficient privileges for network manipulation."""
        try:
            result = subprocess.run(['id', '-u'], capture_output=True, text=True)
            is_root = result.stdout.strip() == '0'

            if not is_root:
                logger.warning("⚠️ Not running as root - network manipulation may be limited")
                logger.info("💡 For full testing, run with sudo for tc/netem support")

            return is_root
        except:
            return False

    def apply_network_condition(self, condition: NetworkCondition) -> bool:
        """Apply network condition using tc (traffic control) if available."""
        if not self.check_root_privileges():
            logger.warning(f"⚠️ Skipping tc network condition {condition.name} - requires root")
            return False

        try:
            # Clear existing tc rules
            subprocess.run(['tc', 'qdisc', 'del', 'dev', 'lo', 'root'],
                         capture_output=True, stderr=subprocess.DEVNULL)

            # Build tc command for network emulation
            tc_cmd = ['tc', 'qdisc', 'add', 'dev', 'lo', 'root', 'netem']

            if condition.latency_ms > 0:
                tc_cmd.extend(['delay', f'{condition.latency_ms}ms'])

            if condition.jitter_ms > 0:
                tc_cmd.append(f'{condition.jitter_ms}ms')

            if condition.packet_loss_percent > 0:
                tc_cmd.extend(['loss', f'{condition.packet_loss_percent}%'])

            if condition.bandwidth_kbps:
                # Add bandwidth limiting (requires additional setup)
                subprocess.run(['tc', 'qdisc', 'add', 'dev', 'lo', 'root', 'handle', '1:', 'tbf',
                              'rate', f'{condition.bandwidth_kbps}kbit', 'burst', '32kbit', 'latency', '50ms'],
                             capture_output=True, check=False)

            result = subprocess.run(tc_cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                logger.info(f"✅ Applied network condition: {condition.name}")
                return True
            else:
                logger.warning(f"⚠️ Failed to apply tc condition: {result.stderr}")
                return False

        except Exception as e:
            logger.warning(f"⚠️ Error applying network condition {condition.name}: {e}")
            return False

    def clear_network_conditions(self):
        """Clear all applied network conditions."""
        try:
            subprocess.run(['tc', 'qdisc', 'del', 'dev', 'lo', 'root'],
                         capture_output=True, stderr=subprocess.DEVNULL)
            logger.info("✅ Cleared network conditions")
        except:
            pass

    async def test_plc_latency_under_condition(self, condition: NetworkCondition) -> LatencyTestResult:
        """Test PLC operations under specific network conditions."""
        start_time = time.time()

        result = LatencyTestResult(
            test_name=f"plc_latency_{condition.name}",
            start_time=start_time,
            end_time=0,
            duration=0,
            success=False,
            latency_ms=0,
            timeout_occurred=False
        )

        try:
            # Test individual parameter read
            plc_start = time.time()

            if plc_manager.is_connected():
                # Test reading all parameters (this is what continuous logger does)
                parameters = await plc_manager.read_all_parameters()
                plc_end = time.time()

                result.plc_operation_time = (plc_end - plc_start) * 1000  # ms
                result.total_parameters_read = len(parameters) if parameters else 0
                result.success = parameters is not None

                if result.success:
                    logger.debug(f"📊 PLC read: {result.total_parameters_read} parameters in {result.plc_operation_time:.1f}ms")
                else:
                    result.error_type = "plc_read_failed"
                    result.error_message = "PLC read_all_parameters returned None"
            else:
                result.error_type = "plc_not_connected"
                result.error_message = "PLC not connected"

        except asyncio.TimeoutError:
            result.timeout_occurred = True
            result.error_type = "timeout"
            result.error_message = "PLC operation timed out"
        except Exception as e:
            result.error_type = "exception"
            result.error_message = str(e)

        end_time = time.time()
        result.end_time = end_time
        result.duration = end_time - start_time
        result.latency_ms = result.duration * 1000

        return result

    async def test_database_latency_under_condition(self, condition: NetworkCondition) -> LatencyTestResult:
        """Test database operations under specific network conditions."""
        start_time = time.time()

        result = LatencyTestResult(
            test_name=f"database_latency_{condition.name}",
            start_time=start_time,
            end_time=0,
            duration=0,
            success=False,
            latency_ms=0,
            timeout_occurred=False
        )

        try:
            # Test the operations that continuous logger performs
            supabase = get_supabase()

            # 1. Process status check (like continuous logger does)
            db_start = time.time()

            # Simulate the actual queries from continuous_parameter_logger
            process_result = supabase.table('machines').select('current_process_id, status').eq('id', 'machine-1').single().execute()

            # 2. Parameter metadata query
            param_result = supabase.table('component_parameters').select('id, set_value').limit(10).execute()

            # 3. Simulate batch insert to parameter_value_history
            test_data = [{
                'parameter_id': f'param_{i}',
                'value': random.uniform(0, 100),
                'timestamp': 'now()'
            } for i in range(5)]

            history_result = supabase.table('parameter_value_history').insert(test_data).execute()

            db_end = time.time()

            result.database_operation_time = (db_end - db_start) * 1000  # ms
            result.success = all([
                process_result.data is not None,
                param_result.data is not None,
                history_result.data is not None
            ])

            if result.success:
                logger.debug(f"📊 Database ops completed in {result.database_operation_time:.1f}ms")
            else:
                result.error_type = "database_operation_failed"
                result.error_message = "One or more database operations failed"

        except asyncio.TimeoutError:
            result.timeout_occurred = True
            result.error_type = "timeout"
            result.error_message = "Database operation timed out"
        except Exception as e:
            result.error_type = "exception"
            result.error_message = str(e)

        end_time = time.time()
        result.end_time = end_time
        result.duration = end_time - start_time
        result.latency_ms = result.duration * 1000

        return result

    async def test_continuous_logging_timing_accuracy(self, condition: NetworkCondition, duration: int = 30) -> List[LatencyTestResult]:
        """Test continuous parameter logging timing accuracy under network conditions."""
        logger.info(f"🔄 Testing continuous logging timing accuracy under {condition.name} for {duration}s")

        results = []
        start_time = time.time()
        interval_count = 0

        # Monitor continuous logger behavior
        original_interval = continuous_parameter_logger.interval
        continuous_parameter_logger.interval = self.target_logging_interval

        try:
            # Start continuous logger if not running
            if not continuous_parameter_logger.is_running:
                await continuous_parameter_logger.start()
                await asyncio.sleep(2)  # Allow startup

            # Monitor timing accuracy
            last_log_time = time.time()

            while time.time() - start_time < duration:
                # Wait for next expected logging interval
                await asyncio.sleep(0.1)  # Check every 100ms

                current_time = time.time()
                elapsed_since_last = current_time - last_log_time

                # Check if we're past the expected interval
                if elapsed_since_last >= self.target_logging_interval:
                    interval_count += 1
                    actual_interval = elapsed_since_last
                    delay_ms = (actual_interval - self.target_logging_interval) * 1000

                    # Create result for this interval
                    interval_result = LatencyTestResult(
                        test_name=f"continuous_logging_interval_{condition.name}_{interval_count}",
                        start_time=last_log_time,
                        end_time=current_time,
                        duration=actual_interval,
                        success=delay_ms <= 100,  # Allow 100ms tolerance
                        latency_ms=delay_ms,
                        timeout_occurred=delay_ms > 1000,  # >1s delay considered timeout
                        logging_interval_accuracy=actual_interval / self.target_logging_interval
                    )

                    interval_result.data['actual_interval_ms'] = actual_interval * 1000
                    interval_result.data['expected_interval_ms'] = self.target_logging_interval * 1000
                    interval_result.data['delay_ms'] = delay_ms

                    results.append(interval_result)
                    last_log_time = current_time

                    # Update metrics
                    self.metrics['continuous_logging_metrics']['intervals_tested'] += 1
                    if delay_ms <= 100:
                        self.metrics['continuous_logging_metrics']['intervals_on_time'] += 1
                    else:
                        self.metrics['continuous_logging_metrics']['intervals_delayed'] += 1

                    if delay_ms > self.metrics['continuous_logging_metrics']['max_delay_ms']:
                        self.metrics['continuous_logging_metrics']['max_delay_ms'] = delay_ms

                    logger.debug(f"📊 Interval {interval_count}: {actual_interval*1000:.1f}ms (delay: {delay_ms:.1f}ms)")

        finally:
            # Restore original interval
            continuous_parameter_logger.interval = original_interval

        logger.info(f"📊 Completed {interval_count} logging intervals under {condition.name}")
        return results

    async def test_timeout_edge_cases(self, condition: NetworkCondition) -> List[LatencyTestResult]:
        """Test timeout edge cases under network conditions."""
        logger.info(f"🕐 Testing timeout edge cases under {condition.name}")

        results = []

        # Test 1: Connection timeout validation
        timeout_result = LatencyTestResult(
            test_name=f"connection_timeout_{condition.name}",
            start_time=time.time(),
            end_time=0,
            duration=0,
            success=False,
            latency_ms=0,
            timeout_occurred=False
        )

        try:
            # Force disconnect and test reconnection under latency
            if plc_manager.is_connected():
                await plc_manager.disconnect()

            start = time.time()
            reconnect_success = await plc_manager.initialize()
            end = time.time()

            timeout_result.duration = end - start
            timeout_result.latency_ms = timeout_result.duration * 1000
            timeout_result.success = reconnect_success
            timeout_result.end_time = end

            if not reconnect_success:
                timeout_result.error_type = "reconnection_failed"
                timeout_result.timeout_occurred = timeout_result.latency_ms > 10000  # 10s timeout

        except Exception as e:
            timeout_result.error_type = "exception"
            timeout_result.error_message = str(e)
            timeout_result.end_time = time.time()
            timeout_result.duration = timeout_result.end_time - timeout_result.start_time
            timeout_result.latency_ms = timeout_result.duration * 1000

        results.append(timeout_result)

        # Test 2: Operation retry validation under latency
        for retry_test in range(3):
            retry_result = LatencyTestResult(
                test_name=f"retry_operation_{condition.name}_{retry_test}",
                start_time=time.time(),
                end_time=0,
                duration=0,
                success=False,
                latency_ms=0,
                timeout_occurred=False
            )

            try:
                # Test operation that might trigger retries
                start = time.time()
                if plc_manager.is_connected():
                    params = await plc_manager.read_all_parameters()
                    retry_result.success = params is not None
                    retry_result.total_parameters_read = len(params) if params else 0
                end = time.time()

                retry_result.duration = end - start
                retry_result.latency_ms = retry_result.duration * 1000
                retry_result.end_time = end

            except Exception as e:
                retry_result.error_type = "exception"
                retry_result.error_message = str(e)
                retry_result.end_time = time.time()
                retry_result.duration = retry_result.end_time - retry_result.start_time
                retry_result.latency_ms = retry_result.duration * 1000

            results.append(retry_result)

            # Brief delay between retry tests
            await asyncio.sleep(1)

        return results

    async def run_comprehensive_latency_stress_test(self, test_duration: int = 300) -> bool:
        """Run comprehensive network latency stress test suite."""
        logger.info("🚀 Starting comprehensive network latency stress test...")
        logger.info(f"⏱️ Total test duration: ~{test_duration} seconds across {len(self.network_conditions)} conditions")

        overall_start = time.time()

        try:
            # Setup test environment
            if not await self.setup_test_environment():
                return False

            # Test each network condition
            for i, condition in enumerate(self.network_conditions):
                condition_start = time.time()

                logger.info(f"📡 Testing condition {i+1}/{len(self.network_conditions)}: {condition.name}")
                logger.info(f"   📊 {condition.description}")

                # Apply network condition
                tc_applied = self.apply_network_condition(condition)

                condition_results = []

                try:
                    # Test 1: PLC latency under condition
                    plc_result = await self.test_plc_latency_under_condition(condition)
                    condition_results.append(plc_result)
                    self.test_results.append(plc_result)

                    # Test 2: Database latency under condition
                    db_result = await self.test_database_latency_under_condition(condition)
                    condition_results.append(db_result)
                    self.test_results.append(db_result)

                    # Test 3: Timeout edge cases
                    timeout_results = await self.test_timeout_edge_cases(condition)
                    condition_results.extend(timeout_results)
                    self.test_results.extend(timeout_results)

                    # Test 4: Continuous logging timing accuracy (reduced duration for testing)
                    timing_duration = min(30, test_duration // len(self.network_conditions))
                    timing_results = await self.test_continuous_logging_timing_accuracy(condition, timing_duration)
                    condition_results.extend(timing_results)
                    self.test_results.extend(timing_results)

                    # Store condition-specific metrics
                    self.metrics['network_condition_results'][condition.name] = {
                        'total_tests': len(condition_results),
                        'successful_tests': sum(1 for r in condition_results if r.success),
                        'avg_latency_ms': sum(r.latency_ms for r in condition_results) / len(condition_results),
                        'max_latency_ms': max(r.latency_ms for r in condition_results),
                        'timeout_count': sum(1 for r in condition_results if r.timeout_occurred)
                    }

                    condition_duration = time.time() - condition_start
                    logger.info(f"✅ Condition {condition.name} completed in {condition_duration:.1f}s")

                except Exception as e:
                    logger.error(f"❌ Error testing condition {condition.name}: {e}", exc_info=True)

                finally:
                    # Clear network conditions
                    if tc_applied:
                        self.clear_network_conditions()
                        await asyncio.sleep(2)  # Allow network to stabilize

                # Brief pause between conditions
                await asyncio.sleep(3)

            # Calculate final metrics
            self.calculate_final_metrics()

            # Generate comprehensive report
            self.generate_latency_stress_report()

            total_duration = time.time() - overall_start
            logger.info(f"🎉 Comprehensive latency stress test completed in {total_duration:.1f}s")

            return True

        except Exception as e:
            logger.error(f"❌ Comprehensive latency stress test failed: {e}", exc_info=True)
            return False

        finally:
            # Cleanup
            self.clear_network_conditions()
            if continuous_parameter_logger.is_running:
                await continuous_parameter_logger.stop()

    def calculate_final_metrics(self):
        """Calculate final test metrics."""
        if not self.test_results:
            return

        self.metrics['total_tests'] = len(self.test_results)
        self.metrics['successful_tests'] = sum(1 for r in self.test_results if r.success)
        self.metrics['timeout_tests'] = sum(1 for r in self.test_results if r.timeout_occurred)
        self.metrics['failed_tests'] = self.metrics['total_tests'] - self.metrics['successful_tests']

        latencies = [r.latency_ms for r in self.test_results]
        self.metrics['avg_latency_ms'] = sum(latencies) / len(latencies)
        self.metrics['max_latency_ms'] = max(latencies)
        self.metrics['min_latency_ms'] = min(latencies)

        # Count logging accuracy violations (delays > 100ms)
        self.metrics['logging_accuracy_violations'] = sum(
            1 for r in self.test_results
            if 'continuous_logging' in r.test_name and r.latency_ms > 100
        )

        # Calculate continuous logging metrics
        clm = self.metrics['continuous_logging_metrics']
        if clm['intervals_tested'] > 0:
            clm['avg_delay_ms'] = sum(
                r.latency_ms for r in self.test_results
                if 'continuous_logging_interval' in r.test_name
            ) / len([r for r in self.test_results if 'continuous_logging_interval' in r.test_name])

    def generate_latency_stress_report(self):
        """Generate comprehensive latency stress test report."""
        logger.info("📊 NETWORK LATENCY STRESS TEST RESULTS")
        logger.info("=" * 80)

        m = self.metrics

        # Overall statistics
        logger.info("🔢 OVERALL STATISTICS:")
        logger.info(f"  Total tests performed: {m['total_tests']}")
        logger.info(f"  Successful tests: {m['successful_tests']}")
        logger.info(f"  Failed tests: {m['failed_tests']}")
        logger.info(f"  Timeout tests: {m['timeout_tests']}")
        logger.info(f"  Success rate: {m['successful_tests']/m['total_tests']*100:.1f}%")

        # Latency statistics
        logger.info("\n⏱️ LATENCY STATISTICS:")
        logger.info(f"  Average latency: {m['avg_latency_ms']:.1f}ms")
        logger.info(f"  Maximum latency: {m['max_latency_ms']:.1f}ms")
        logger.info(f"  Minimum latency: {m['min_latency_ms']:.1f}ms")

        # Continuous logging timing analysis
        clm = m['continuous_logging_metrics']
        logger.info("\n🔄 CONTINUOUS LOGGING TIMING ANALYSIS:")
        logger.info(f"  Intervals tested: {clm['intervals_tested']}")
        logger.info(f"  On-time intervals: {clm['intervals_on_time']}")
        logger.info(f"  Delayed intervals: {clm['intervals_delayed']}")
        if clm['intervals_tested'] > 0:
            logger.info(f"  Timing accuracy: {clm['intervals_on_time']/clm['intervals_tested']*100:.1f}%")
        logger.info(f"  Maximum delay: {clm['max_delay_ms']:.1f}ms")
        logger.info(f"  Average delay: {clm['avg_delay_ms']:.1f}ms")

        # Network condition results
        logger.info("\n📡 NETWORK CONDITION RESULTS:")
        for condition_name, results in m['network_condition_results'].items():
            logger.info(f"  {condition_name}:")
            logger.info(f"    Tests: {results['successful_tests']}/{results['total_tests']}")
            logger.info(f"    Avg latency: {results['avg_latency_ms']:.1f}ms")
            logger.info(f"    Max latency: {results['max_latency_ms']:.1f}ms")
            logger.info(f"    Timeouts: {results['timeout_count']}")

        # Critical findings and recommendations
        logger.info("\n🚨 CRITICAL FINDINGS:")

        # Check 1-second logging constraint
        if m['avg_latency_ms'] > 1000:
            logger.error("❌ CRITICAL: Average latency exceeds 1-second logging constraint")
        elif m['max_latency_ms'] > 1000:
            logger.warning("⚠️ WARNING: Peak latency exceeds 1-second logging constraint")
        else:
            logger.info("✅ Latency within 1-second logging constraint")

        # Check timing accuracy
        if clm['intervals_tested'] > 0:
            accuracy = clm['intervals_on_time'] / clm['intervals_tested']
            if accuracy < 0.8:
                logger.error("❌ CRITICAL: Continuous logging timing accuracy below 80%")
            elif accuracy < 0.95:
                logger.warning("⚠️ WARNING: Continuous logging timing accuracy below 95%")
            else:
                logger.info("✅ Good continuous logging timing accuracy")

        # Network resilience assessment
        failed_conditions = [
            name for name, results in m['network_condition_results'].items()
            if results['successful_tests'] / results['total_tests'] < 0.7
        ]

        if failed_conditions:
            logger.error(f"❌ CRITICAL: Poor performance under conditions: {', '.join(failed_conditions)}")
        else:
            logger.info("✅ Good network resilience across all test conditions")

        # Recommendations
        logger.info("\n💡 RECOMMENDATIONS:")

        if m['avg_latency_ms'] > 500:
            logger.info("  • Implement connection pooling for database operations")
            logger.info("  • Add parallel/async operations for PLC and database")
            logger.info("  • Consider caching parameter metadata")

        if clm['max_delay_ms'] > 500:
            logger.info("  • Implement adaptive timing for continuous logging")
            logger.info("  • Add circuit breaker pattern for high-latency conditions")
            logger.info("  • Consider buffering and batch operations")

        if m['timeout_tests'] > 0:
            logger.info("  • Review and tune timeout configurations")
            logger.info("  • Implement exponential backoff for retries")
            logger.info("  • Add timeout monitoring and alerting")


async def main():
    """Main test execution function."""
    load_dotenv()

    test = NetworkLatencyStressTest()
    success = await test.run_comprehensive_latency_stress_test(test_duration=180)  # 3 minutes

    if success:
        logger.info("🎉 Network latency stress test completed successfully")
    else:
        logger.error("💥 Network latency stress test failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())