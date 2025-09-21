"""
Network failure recovery metrics and validation test.
Measures and validates recovery characteristics, timing, and effectiveness
of network failure handling in the continuous parameter logging system.
"""
import os
import sys
import asyncio
import time
import json
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.log_setup import logger
from src.plc.manager import plc_manager
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.db import get_supabase
from src.config import MACHINE_ID


class NetworkFailureRecoveryMetrics:
    """Comprehensive metrics collection for network failure recovery validation."""

    def __init__(self):
        self.metrics = {
            'recovery_times': [],
            'data_loss_measurements': [],
            'error_rate_analysis': [],
            'system_stability_metrics': [],
            'performance_degradation': [],
            'quality_metrics': {}
        }
        self.baseline_performance = {}
        self.test_metadata = {}

    async def establish_baseline_performance(self) -> Dict[str, float]:
        """Establish baseline performance metrics for comparison."""
        logger.info("📊 Establishing baseline performance metrics...")

        baseline = {
            'normal_logging_interval': 0,
            'parameter_read_latency': 0,
            'database_write_latency': 0,
            'memory_usage_baseline': 0,
            'error_rate_baseline': 0
        }

        try:
            # Start continuous logging and measure normal operation
            await continuous_parameter_logger.start()
            initial_error_count = continuous_parameter_logger._error_count

            # Measure normal logging intervals
            intervals = []
            for cycle in range(10):  # 10 measurement cycles
                cycle_start = time.time()

                # Wait for one logging cycle
                await asyncio.sleep(1.1)  # Slightly more than expected interval

                cycle_duration = time.time() - cycle_start
                intervals.append(cycle_duration)

            baseline['normal_logging_interval'] = statistics.mean(intervals)

            # Measure parameter read latency
            read_times = []
            for measurement in range(5):
                read_start = time.time()
                await plc_manager.read_all_parameters()
                read_duration = time.time() - read_start
                read_times.append(read_duration)

            baseline['parameter_read_latency'] = statistics.mean(read_times)

            # Measure database write latency
            write_times = []
            supabase = get_supabase()
            for measurement in range(5):
                write_start = time.time()
                test_data = [{
                    'parameter_id': 'test_baseline',
                    'value': 1.0,
                    'timestamp': datetime.now().isoformat()
                }]
                supabase.table('parameter_value_history').insert(test_data).execute()
                write_duration = time.time() - write_start
                write_times.append(write_duration)

            baseline['database_write_latency'] = statistics.mean(write_times)

            # Check error rate
            final_error_count = continuous_parameter_logger._error_count
            baseline['error_rate_baseline'] = final_error_count - initial_error_count

            await continuous_parameter_logger.stop()

            logger.info(f"✅ Baseline established: "
                       f"Logging: {baseline['normal_logging_interval']:.2f}s, "
                       f"PLC: {baseline['parameter_read_latency']:.3f}s, "
                       f"DB: {baseline['database_write_latency']:.3f}s")

            self.baseline_performance = baseline
            return baseline

        except Exception as e:
            logger.error(f"Failed to establish baseline: {e}")
            return baseline

    async def measure_recovery_time_precision(self, failure_duration: int = 10) -> Dict[str, float]:
        """Measure precise recovery timing characteristics."""
        logger.info(f"⏱️ Measuring recovery time precision (failure duration: {failure_duration}s)...")

        recovery_metrics = {
            'failure_detection_time': 0,
            'reconnection_attempt_time': 0,
            'first_successful_operation_time': 0,
            'full_recovery_time': 0,
            'recovery_accuracy': 0
        }

        try:
            # Start continuous logging
            await continuous_parameter_logger.start()
            await asyncio.sleep(2)  # Stabilize

            # Force connection failure
            failure_start = time.time()
            if plc_manager.plc and hasattr(plc_manager.plc, 'communicator'):
                communicator = plc_manager.plc.communicator
                if communicator.client:
                    communicator.client.close()

            logger.info(f"🚫 Simulated connection failure at {failure_start}")

            # Monitor for failure detection
            failure_detected = False
            detection_time = 0

            for check in range(50):  # Check for 25 seconds
                await asyncio.sleep(0.5)

                error_count = continuous_parameter_logger._error_count
                if error_count > 0 and not failure_detected:
                    detection_time = time.time() - failure_start
                    failure_detected = True
                    logger.info(f"🔍 Failure detected after {detection_time:.2f}s")
                    break

            recovery_metrics['failure_detection_time'] = detection_time

            # Wait for failure duration
            await asyncio.sleep(max(0, failure_duration - detection_time))

            # Monitor recovery process
            recovery_start = time.time()

            # Check for reconnection attempts
            reconnection_detected = False
            first_success = False
            full_recovery = False

            for attempt in range(60):  # Monitor for 30 seconds
                await asyncio.sleep(0.5)

                # Check if last successful read indicates recovery
                if continuous_parameter_logger._last_successful_read:
                    if continuous_parameter_logger._last_successful_read > recovery_start:
                        if not first_success:
                            recovery_metrics['first_successful_operation_time'] = time.time() - recovery_start
                            first_success = True
                            logger.info(f"✅ First successful operation after {recovery_metrics['first_successful_operation_time']:.2f}s")

                        # Check for sustained recovery (3 consecutive successes)
                        if not full_recovery and time.time() - continuous_parameter_logger._last_successful_read < 5:
                            # Test sustained operations
                            sustained_success = True
                            for test in range(3):
                                try:
                                    result = await plc_manager.read_parameter('power_on')
                                    if result is None:
                                        sustained_success = False
                                        break
                                    await asyncio.sleep(1)
                                except:
                                    sustained_success = False
                                    break

                            if sustained_success:
                                recovery_metrics['full_recovery_time'] = time.time() - recovery_start
                                full_recovery = True
                                logger.info(f"🎯 Full recovery achieved after {recovery_metrics['full_recovery_time']:.2f}s")
                                break

            # Calculate recovery accuracy
            if recovery_metrics['full_recovery_time'] > 0:
                # Good recovery is within 30 seconds
                accuracy = max(0, (30 - recovery_metrics['full_recovery_time']) / 30)
                recovery_metrics['recovery_accuracy'] = accuracy

            return recovery_metrics

        except Exception as e:
            logger.error(f"Recovery time measurement failed: {e}")
            return recovery_metrics

        finally:
            try:
                await continuous_parameter_logger.stop()
            except:
                pass

    async def measure_data_loss_during_failures(self) -> Dict[str, Any]:
        """Measure data loss characteristics during network failures."""
        logger.info("📉 Measuring data loss during network failures...")

        data_loss_metrics = {
            'expected_data_points': 0,
            'actual_data_points': 0,
            'data_loss_percentage': 0,
            'silent_failures': 0,
            'integrity_violations': 0,
            'dual_mode_consistency': 0
        }

        try:
            # Clear any existing test data
            supabase = get_supabase()
            test_start_time = datetime.now().isoformat()

            # Start continuous logging
            await continuous_parameter_logger.start()

            # Set process mode for dual-mode testing
            supabase.table('machines').update({
                'status': 'processing',
                'current_process_id': 'test_data_loss_measurement'
            }).eq('id', MACHINE_ID).execute()

            await asyncio.sleep(2)  # Let dual-mode stabilize

            # Start data counting
            measurement_start = time.time()

            # Let it run normally for 5 seconds
            await asyncio.sleep(5)

            # Simulate failure for 10 seconds
            if plc_manager.plc and hasattr(plc_manager.plc, 'communicator'):
                communicator = plc_manager.plc.communicator
                if communicator.client:
                    communicator.client.close()

            await asyncio.sleep(10)  # Failure period

            # Let it recover for 5 seconds
            await asyncio.sleep(5)

            measurement_duration = time.time() - measurement_start
            data_loss_metrics['expected_data_points'] = int(measurement_duration)  # Roughly 1 per second

            # Count actual data points
            end_time = datetime.now().isoformat()

            # Count parameter_value_history entries
            history_result = supabase.table('parameter_value_history').select('*').gte('timestamp', test_start_time).lte('timestamp', end_time).execute()
            history_count = len(history_result.data) if history_result.data else 0

            # Count process_data_points entries
            process_result = supabase.table('process_data_points').select('*').eq('process_id', 'test_data_loss_measurement').gte('timestamp', test_start_time).lte('timestamp', end_time).execute()
            process_count = len(process_result.data) if process_result.data else 0

            data_loss_metrics['actual_data_points'] = history_count
            data_loss_metrics['data_loss_percentage'] = max(0, (data_loss_metrics['expected_data_points'] - history_count) / data_loss_metrics['expected_data_points'] * 100)

            # Check dual-mode consistency
            if history_count > 0 and process_count > 0:
                consistency_ratio = process_count / history_count
                data_loss_metrics['dual_mode_consistency'] = consistency_ratio
            else:
                data_loss_metrics['integrity_violations'] += 1

            # Clean up test process
            supabase.table('machines').update({
                'status': 'idle',
                'current_process_id': None
            }).eq('id', MACHINE_ID).execute()

            logger.info(f"📊 Data loss analysis: Expected {data_loss_metrics['expected_data_points']}, "
                       f"Got {data_loss_metrics['actual_data_points']}, "
                       f"Loss: {data_loss_metrics['data_loss_percentage']:.1f}%")

            return data_loss_metrics

        except Exception as e:
            logger.error(f"Data loss measurement failed: {e}")
            return data_loss_metrics

        finally:
            try:
                await continuous_parameter_logger.stop()
            except:
                pass

    async def measure_system_stability_under_stress(self) -> Dict[str, Any]:
        """Measure system stability characteristics under network stress."""
        logger.info("🎯 Measuring system stability under network stress...")

        stability_metrics = {
            'service_crashes': 0,
            'memory_leaks_detected': 0,
            'resource_exhaustion': 0,
            'performance_degradation': 0,
            'error_recovery_success_rate': 0,
            'sustained_operation_capability': 0
        }

        try:
            initial_error_count = 0

            # Run multiple stress cycles
            stress_cycles = 5
            successful_recoveries = 0

            for cycle in range(stress_cycles):
                logger.info(f"🔄 Stress cycle {cycle + 1}/{stress_cycles}")

                try:
                    # Start service
                    await continuous_parameter_logger.start()
                    if cycle == 0:
                        initial_error_count = continuous_parameter_logger._error_count

                    # Normal operation
                    await asyncio.sleep(2)

                    # Stress scenario
                    if plc_manager.plc and hasattr(plc_manager.plc, 'communicator'):
                        communicator = plc_manager.plc.communicator
                        if communicator.client:
                            communicator.client.close()

                    # Wait during stress
                    await asyncio.sleep(5)

                    # Check if service survived
                    if continuous_parameter_logger.is_running:
                        successful_recoveries += 1
                    else:
                        stability_metrics['service_crashes'] += 1

                    await continuous_parameter_logger.stop()
                    await asyncio.sleep(1)  # Brief pause

                except Exception as e:
                    logger.warning(f"Stress cycle {cycle + 1} error: {e}")
                    stability_metrics['service_crashes'] += 1

            stability_metrics['error_recovery_success_rate'] = successful_recoveries / stress_cycles if stress_cycles > 0 else 0

            # Test sustained operation capability
            logger.info("🔄 Testing sustained operation capability...")
            try:
                await continuous_parameter_logger.start()
                sustained_start = time.time()

                # Run for extended period with occasional disruptions
                for disruption in range(3):
                    await asyncio.sleep(10)  # Normal operation

                    # Brief disruption
                    if plc_manager.plc and hasattr(plc_manager.plc, 'communicator'):
                        communicator = plc_manager.plc.communicator
                        if communicator.client:
                            communicator.client.close()

                    await asyncio.sleep(3)  # Recovery time

                sustained_duration = time.time() - sustained_start
                stability_metrics['sustained_operation_capability'] = sustained_duration

                logger.info(f"✅ Sustained operation for {sustained_duration:.1f}s with disruptions")

            except Exception as e:
                logger.warning(f"Sustained operation test failed: {e}")

            return stability_metrics

        except Exception as e:
            logger.error(f"Stability measurement failed: {e}")
            return stability_metrics

        finally:
            try:
                await continuous_parameter_logger.stop()
            except:
                pass

    def calculate_network_resilience_score(self) -> float:
        """Calculate overall network resilience score based on all metrics."""
        scores = []

        # Recovery time score (0-100)
        if self.metrics['recovery_times']:
            avg_recovery = statistics.mean(self.metrics['recovery_times'])
            recovery_score = max(0, (30 - avg_recovery) / 30 * 100)  # 30s is max acceptable
            scores.append(recovery_score)

        # Data loss score (0-100)
        if self.metrics['data_loss_measurements']:
            avg_data_loss = statistics.mean([m['data_loss_percentage'] for m in self.metrics['data_loss_measurements']])
            data_loss_score = max(0, (100 - avg_data_loss))  # Lower loss is better
            scores.append(data_loss_score)

        # Stability score (0-100)
        if self.metrics['system_stability_metrics']:
            stability_metrics = self.metrics['system_stability_metrics'][-1]
            recovery_rate = stability_metrics.get('error_recovery_success_rate', 0)
            crashes = stability_metrics.get('service_crashes', 0)
            stability_score = (recovery_rate * 80) + max(0, (5 - crashes) / 5 * 20)  # Weight recovery more
            scores.append(stability_score)

        # Overall score
        if scores:
            overall_score = statistics.mean(scores)
            return min(100, max(0, overall_score))
        else:
            return 0

    async def run_comprehensive_recovery_metrics_validation(self):
        """Run comprehensive network failure recovery metrics validation."""
        logger.info("🚀 Starting Comprehensive Network Failure Recovery Metrics Validation")
        logger.info("=" * 80)

        start_time = time.time()

        try:
            # Establish baseline
            baseline = await self.establish_baseline_performance()

            # Test 1: Recovery time precision
            logger.info("\n🔬 Test 1: Recovery Time Precision Analysis")
            for duration in [5, 10, 15]:  # Different failure durations
                recovery_metrics = await self.measure_recovery_time_precision(duration)
                self.metrics['recovery_times'].append(recovery_metrics['full_recovery_time'])

                logger.info(f"  Duration {duration}s: Recovery {recovery_metrics['full_recovery_time']:.2f}s "
                           f"(Accuracy: {recovery_metrics['recovery_accuracy']:.1%})")

            # Test 2: Data loss measurement
            logger.info("\n📉 Test 2: Data Loss Measurement")
            data_loss_metrics = await self.measure_data_loss_during_failures()
            self.metrics['data_loss_measurements'].append(data_loss_metrics)

            # Test 3: System stability under stress
            logger.info("\n🎯 Test 3: System Stability Under Stress")
            stability_metrics = await self.measure_system_stability_under_stress()
            self.metrics['system_stability_metrics'].append(stability_metrics)

            # Calculate overall resilience score
            resilience_score = self.calculate_network_resilience_score()

            # Generate comprehensive report
            self.generate_metrics_report(resilience_score, time.time() - start_time)

            # Return success based on resilience score
            return resilience_score >= 70  # 70% is acceptable threshold

        except Exception as e:
            logger.error(f"Metrics validation failed: {e}")
            return False

    def generate_metrics_report(self, resilience_score: float, total_duration: float):
        """Generate comprehensive metrics report."""
        logger.info("=" * 80)
        logger.info("🏁 NETWORK FAILURE RECOVERY METRICS REPORT")
        logger.info("=" * 80)

        # Overall assessment
        logger.info(f"📊 OVERALL NETWORK RESILIENCE SCORE: {resilience_score:.1f}/100")

        if resilience_score >= 90:
            logger.info("🟢 EXCELLENT: Network failure recovery is highly robust")
        elif resilience_score >= 80:
            logger.info("🟡 GOOD: Network failure recovery is acceptable with minor issues")
        elif resilience_score >= 70:
            logger.info("🟠 MARGINAL: Network failure recovery needs improvement")
        else:
            logger.info("🔴 CRITICAL: Network failure recovery is inadequate")

        # Recovery time analysis
        if self.metrics['recovery_times']:
            avg_recovery = statistics.mean(self.metrics['recovery_times'])
            min_recovery = min(self.metrics['recovery_times'])
            max_recovery = max(self.metrics['recovery_times'])

            logger.info(f"\n⏱️ RECOVERY TIME ANALYSIS:")
            logger.info(f"  Average recovery time: {avg_recovery:.2f}s")
            logger.info(f"  Fastest recovery: {min_recovery:.2f}s")
            logger.info(f"  Slowest recovery: {max_recovery:.2f}s")

            if avg_recovery <= 10:
                logger.info("  ✅ Recovery times are excellent")
            elif avg_recovery <= 20:
                logger.info("  ⚠️ Recovery times are acceptable")
            else:
                logger.info("  ❌ Recovery times are too slow")

        # Data loss analysis
        if self.metrics['data_loss_measurements']:
            data_loss = self.metrics['data_loss_measurements'][-1]
            logger.info(f"\n📉 DATA LOSS ANALYSIS:")
            logger.info(f"  Expected data points: {data_loss['expected_data_points']}")
            logger.info(f"  Actual data points: {data_loss['actual_data_points']}")
            logger.info(f"  Data loss percentage: {data_loss['data_loss_percentage']:.1f}%")
            logger.info(f"  Dual-mode consistency: {data_loss['dual_mode_consistency']:.2f}")

            if data_loss['data_loss_percentage'] <= 5:
                logger.info("  ✅ Data loss is minimal")
            elif data_loss['data_loss_percentage'] <= 15:
                logger.info("  ⚠️ Data loss is moderate")
            else:
                logger.info("  ❌ Data loss is excessive")

        # Stability analysis
        if self.metrics['system_stability_metrics']:
            stability = self.metrics['system_stability_metrics'][-1]
            logger.info(f"\n🎯 SYSTEM STABILITY ANALYSIS:")
            logger.info(f"  Error recovery success rate: {stability['error_recovery_success_rate']:.1%}")
            logger.info(f"  Service crashes: {stability['service_crashes']}")
            logger.info(f"  Sustained operation: {stability['sustained_operation_capability']:.1f}s")

        # Baseline comparison
        if self.baseline_performance:
            logger.info(f"\n📊 BASELINE PERFORMANCE:")
            logger.info(f"  Normal logging interval: {self.baseline_performance['normal_logging_interval']:.3f}s")
            logger.info(f"  PLC read latency: {self.baseline_performance['parameter_read_latency']:.3f}s")
            logger.info(f"  Database write latency: {self.baseline_performance['database_write_latency']:.3f}s")

        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        if resilience_score < 70:
            logger.info("  • URGENT: Implement circuit breaker patterns")
            logger.info("  • URGENT: Add proper transaction boundaries")
            logger.info("  • URGENT: Implement exponential backoff retry logic")

        if self.metrics['recovery_times'] and statistics.mean(self.metrics['recovery_times']) > 15:
            logger.info("  • Optimize connection recovery mechanisms")
            logger.info("  • Add connection pooling for faster recovery")

        if self.metrics['data_loss_measurements'] and self.metrics['data_loss_measurements'][-1]['data_loss_percentage'] > 10:
            logger.info("  • Implement data buffering during failures")
            logger.info("  • Add integrity validation mechanisms")

        logger.info(f"\n📄 Test completed in {total_duration:.1f} seconds")

        # Save metrics to file
        self.save_metrics_report()

    def save_metrics_report(self):
        """Save detailed metrics to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"network_recovery_metrics_{timestamp}.json"
        report_path = os.path.join(os.path.dirname(__file__), report_file)

        try:
            report_data = {
                'metrics': self.metrics,
                'baseline_performance': self.baseline_performance,
                'resilience_score': self.calculate_network_resilience_score(),
                'timestamp': timestamp,
                'test_metadata': self.test_metadata
            }

            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            logger.info(f"📄 Detailed metrics saved to: {report_path}")

        except Exception as e:
            logger.warning(f"Failed to save metrics report: {e}")


async def main():
    """Main test execution function."""
    load_dotenv()

    metrics_validator = NetworkFailureRecoveryMetrics()
    success = await metrics_validator.run_comprehensive_recovery_metrics_validation()

    if success:
        logger.info("🎉 Network failure recovery metrics validation completed successfully")
    else:
        logger.error("💥 Network failure recovery metrics reveal critical issues")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())