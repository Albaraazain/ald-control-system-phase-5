#!/usr/bin/env python3
"""
Comprehensive Real PLC Hardware Testing Suite
============================================

This script tests the critical performance bottleneck identified by the performance_implementation_lead:
- Individual parameter reads vs bulk Modbus operations
- Real hardware connection validation
- Broken pipe recovery mechanisms
- Dual-mode logging performance
- 1-second interval accuracy with real hardware

Run with: python test_real_plc_comprehensive.py
"""

import asyncio
import time
import json
import statistics
from typing import Dict, List, Optional, Tuple
import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.log_setup import logger
from src.plc.manager import plc_manager
from src.plc.real_plc import RealPLC
from src.plc.communicator import PLCCommunicator
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.config import PLC_CONFIG
from pymodbus.client import ModbusTcpClient

class RealPLCHardwareTester:
    """Comprehensive real PLC hardware testing suite."""

    def __init__(self):
        self.results = {
            'connection_tests': {},
            'performance_tests': {},
            'error_recovery_tests': {},
            'dual_mode_tests': {},
            'bulk_vs_individual_tests': {},
            'timing_accuracy_tests': {}
        }
        self.plc_ip = PLC_CONFIG['ip_address']
        self.plc_port = PLC_CONFIG['port']

    async def run_comprehensive_test_suite(self):
        """Execute the complete test suite."""
        logger.info("🔥 STARTING COMPREHENSIVE REAL PLC HARDWARE TESTING 🔥")
        logger.info(f"Target PLC: {self.plc_ip}:{self.plc_port}")

        try:
            # Test 1: Basic Connection Validation
            await self._test_connection_validation()

            # Test 2: Critical Performance Bottleneck Testing
            await self._test_bulk_vs_individual_reads()

            # Test 3: Broken Pipe Recovery
            await self._test_broken_pipe_recovery()

            # Test 4: Dual-Mode Logging Performance
            await self._test_dual_mode_logging_performance()

            # Test 5: 1-Second Interval Accuracy
            await self._test_timing_accuracy()

            # Test 6: Real Hardware Stress Testing
            await self._test_real_hardware_stress()

            # Generate comprehensive report
            self._generate_test_report()

        except Exception as e:
            logger.error(f"Critical test suite failure: {e}", exc_info=True)

    async def _test_connection_validation(self):
        """Test PLC connection establishment and validation."""
        logger.info("🔌 Testing PLC Connection Validation...")

        test_results = {
            'connection_time': None,
            'discovery_method': None,
            'modbus_functions': {},
            'health_check': False
        }

        try:
            # Test connection time
            start_time = time.time()
            connected = await plc_manager.initialize()
            connection_time = time.time() - start_time

            test_results['connection_time'] = connection_time
            test_results['connection_success'] = connected

            if connected:
                logger.info(f"✅ PLC Connected in {connection_time:.3f}s")

                # Test basic Modbus functions
                await self._test_modbus_functions(test_results)

                # Test connection health check
                test_results['health_check'] = plc_manager.is_connected()

            else:
                logger.error("❌ Failed to connect to PLC")

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            test_results['error'] = str(e)

        self.results['connection_tests'] = test_results

    async def _test_modbus_functions(self, test_results: dict):
        """Test various Modbus function codes."""
        logger.info("📡 Testing Modbus Functions...")

        # Get direct access to PLCCommunicator
        if hasattr(plc_manager, 'plc') and hasattr(plc_manager.plc, 'communicator'):
            communicator = plc_manager.plc.communicator

            modbus_tests = [
                ('read_holding_registers', lambda: communicator.client.read_holding_registers(0, 5, slave=1)),
                ('read_coils', lambda: communicator.read_coils(0, 5)),
                ('read_input_registers', lambda: communicator.client.read_input_registers(0, 5, slave=1)),
                ('read_discrete_inputs', lambda: communicator.client.read_discrete_inputs(0, 5, slave=1)),
            ]

            for test_name, test_func in modbus_tests:
                try:
                    start_time = time.time()
                    result = test_func()
                    elapsed = time.time() - start_time

                    success = result is not None and (not hasattr(result, 'isError') or not result.isError())
                    test_results['modbus_functions'][test_name] = {
                        'success': success,
                        'response_time': elapsed,
                        'result': str(result)[:100] if result else None
                    }

                    logger.info(f"  {test_name}: {'✅' if success else '❌'} ({elapsed:.3f}s)")

                except Exception as e:
                    test_results['modbus_functions'][test_name] = {
                        'success': False,
                        'error': str(e)
                    }
                    logger.warning(f"  {test_name}: ❌ {e}")

    async def _test_bulk_vs_individual_reads(self):
        """Test the critical performance bottleneck: bulk vs individual parameter reads."""
        logger.info("⚡ Testing CRITICAL PERFORMANCE BOTTLENECK: Bulk vs Individual Reads...")

        test_results = {
            'individual_reads': {},
            'bulk_reads': {},
            'performance_improvement': None
        }

        if not plc_manager.is_connected():
            logger.warning("PLC not connected, skipping performance test")
            return

        try:
            # Get parameter cache for testing
            if hasattr(plc_manager.plc, '_parameter_cache'):
                param_cache = plc_manager.plc._parameter_cache
                if not param_cache:
                    logger.warning("No parameter cache available for testing")
                    return

                # Take first 10 parameters for testing
                test_params = list(param_cache.keys())[:10]
                logger.info(f"Testing with {len(test_params)} parameters")

                # Test 1: Individual reads (current implementation)
                logger.info("  Testing individual parameter reads...")
                individual_times = []

                for run in range(5):  # 5 test runs
                    start_time = time.time()

                    for param_id in test_params:
                        try:
                            await plc_manager.read_parameter(param_id)
                        except Exception as e:
                            logger.warning(f"Failed to read parameter {param_id}: {e}")

                    elapsed = time.time() - start_time
                    individual_times.append(elapsed)
                    logger.info(f"    Run {run+1}: {elapsed:.3f}s for {len(test_params)} parameters")

                test_results['individual_reads'] = {
                    'times': individual_times,
                    'avg_time': statistics.mean(individual_times),
                    'min_time': min(individual_times),
                    'max_time': max(individual_times),
                    'params_per_second': len(test_params) / statistics.mean(individual_times)
                }

                # Test 2: Bulk reads (if available)
                logger.info("  Testing bulk parameter reads...")
                bulk_times = []

                for run in range(5):  # 5 test runs
                    start_time = time.time()

                    # Test bulk read via read_all_parameters
                    try:
                        all_params = await plc_manager.read_all_parameters()
                        # Filter to our test parameters
                        test_results_bulk = {k: v for k, v in all_params.items() if k in test_params}
                    except Exception as e:
                        logger.warning(f"Bulk read failed: {e}")
                        test_results_bulk = {}

                    elapsed = time.time() - start_time
                    bulk_times.append(elapsed)
                    logger.info(f"    Run {run+1}: {elapsed:.3f}s for {len(test_results_bulk)} parameters")

                test_results['bulk_reads'] = {
                    'times': bulk_times,
                    'avg_time': statistics.mean(bulk_times),
                    'min_time': min(bulk_times),
                    'max_time': max(bulk_times),
                    'params_per_second': len(test_params) / statistics.mean(bulk_times)
                }

                # Calculate performance improvement
                if individual_times and bulk_times:
                    improvement_factor = statistics.mean(individual_times) / statistics.mean(bulk_times)
                    test_results['performance_improvement'] = improvement_factor

                    logger.info(f"🚀 PERFORMANCE IMPROVEMENT: {improvement_factor:.1f}x faster with bulk reads!")
                    logger.info(f"   Individual: {statistics.mean(individual_times):.3f}s avg")
                    logger.info(f"   Bulk: {statistics.mean(bulk_times):.3f}s avg")

                    if improvement_factor < 2.0:
                        logger.warning("⚠️  Expected >2x improvement, actual optimization may be needed")
                    elif improvement_factor > 5.0:
                        logger.info("🎉 Excellent performance improvement achieved!")

        except Exception as e:
            logger.error(f"Performance test failed: {e}", exc_info=True)
            test_results['error'] = str(e)

        self.results['bulk_vs_individual_tests'] = test_results

    async def _test_broken_pipe_recovery(self):
        """Test broken pipe error recovery mechanisms."""
        logger.info("🔧 Testing Broken Pipe Recovery...")

        test_results = {
            'recovery_attempts': [],
            'recovery_success': False,
            'total_recovery_time': None
        }

        try:
            if plc_manager.is_connected():
                # Force disconnect to simulate broken pipe
                logger.info("  Simulating broken pipe by disconnecting...")
                await plc_manager.disconnect()

                # Wait a moment
                await asyncio.sleep(1)

                # Test recovery
                start_time = time.time()
                for attempt in range(3):
                    logger.info(f"  Recovery attempt {attempt + 1}...")

                    attempt_start = time.time()
                    success = await plc_manager.initialize()
                    attempt_time = time.time() - attempt_start

                    test_results['recovery_attempts'].append({
                        'attempt': attempt + 1,
                        'success': success,
                        'time': attempt_time
                    })

                    if success:
                        test_results['recovery_success'] = True
                        test_results['total_recovery_time'] = time.time() - start_time
                        logger.info(f"  ✅ Recovery successful in {attempt_time:.3f}s")
                        break
                    else:
                        logger.warning(f"  ❌ Recovery attempt {attempt + 1} failed")
                        await asyncio.sleep(2)  # Wait before retry

                if not test_results['recovery_success']:
                    logger.error("❌ All recovery attempts failed")

        except Exception as e:
            logger.error(f"Recovery test failed: {e}")
            test_results['error'] = str(e)

        self.results['error_recovery_tests'] = test_results

    async def _test_dual_mode_logging_performance(self):
        """Test dual-mode logging performance with real hardware."""
        logger.info("📊 Testing Dual-Mode Logging Performance...")

        test_results = {
            'idle_mode': {},
            'process_mode': {},
            'mode_switching': {}
        }

        try:
            if not plc_manager.is_connected():
                logger.warning("PLC not connected, skipping dual-mode test")
                return

            # Test idle mode logging
            logger.info("  Testing idle mode logging...")
            start_time = time.time()

            # Start continuous logger
            await continuous_parameter_logger.start()
            await asyncio.sleep(5)  # Log for 5 seconds

            idle_time = time.time() - start_time
            await continuous_parameter_logger.stop()

            test_results['idle_mode'] = {
                'duration': idle_time,
                'status': 'completed'
            }

            logger.info(f"  ✅ Idle mode logging completed in {idle_time:.3f}s")

            # Note: Process mode testing would require actual process setup
            # which is beyond scope of hardware validation
            test_results['process_mode'] = {
                'status': 'requires_process_setup',
                'note': 'Full process mode testing requires recipe execution'
            }

        except Exception as e:
            logger.error(f"Dual-mode test failed: {e}")
            test_results['error'] = str(e)

        self.results['dual_mode_tests'] = test_results

    async def _test_timing_accuracy(self):
        """Test 1-second interval accuracy with real hardware."""
        logger.info("⏱️  Testing 1-Second Interval Accuracy...")

        test_results = {
            'intervals': [],
            'avg_interval': None,
            'jitter': None,
            'accuracy_percent': None
        }

        try:
            if not plc_manager.is_connected():
                logger.warning("PLC not connected, skipping timing test")
                return

            logger.info("  Measuring parameter read intervals...")
            intervals = []
            last_time = time.time()

            # Test 10 intervals
            for i in range(10):
                await asyncio.sleep(1.0)  # Target 1-second interval

                # Read parameters
                try:
                    await plc_manager.read_all_parameters()
                except Exception as e:
                    logger.warning(f"Parameter read failed: {e}")

                current_time = time.time()
                interval = current_time - last_time
                intervals.append(interval)
                last_time = current_time

                logger.info(f"    Interval {i+1}: {interval:.3f}s")

            test_results['intervals'] = intervals
            test_results['avg_interval'] = statistics.mean(intervals)
            test_results['jitter'] = statistics.stdev(intervals) if len(intervals) > 1 else 0

            # Calculate accuracy (how close to 1.0 second)
            accuracy = 100 * (1.0 - abs(statistics.mean(intervals) - 1.0))
            test_results['accuracy_percent'] = accuracy

            logger.info(f"  📈 Average interval: {test_results['avg_interval']:.3f}s")
            logger.info(f"  📊 Jitter (stdev): {test_results['jitter']:.3f}s")
            logger.info(f"  🎯 Accuracy: {accuracy:.1f}%")

            if accuracy > 95:
                logger.info("🎉 Excellent timing accuracy!")
            elif accuracy > 90:
                logger.info("✅ Good timing accuracy")
            else:
                logger.warning("⚠️  Timing accuracy below expectations")

        except Exception as e:
            logger.error(f"Timing test failed: {e}")
            test_results['error'] = str(e)

        self.results['timing_accuracy_tests'] = test_results

    async def _test_real_hardware_stress(self):
        """Test real hardware under stress conditions."""
        logger.info("💪 Testing Real Hardware Stress Conditions...")

        test_results = {
            'rapid_operations': {},
            'concurrent_access': {},
            'sustained_load': {}
        }

        try:
            if not plc_manager.is_connected():
                logger.warning("PLC not connected, skipping stress test")
                return

            # Test rapid operations
            logger.info("  Testing rapid operations...")
            start_time = time.time()
            success_count = 0

            for i in range(50):  # 50 rapid operations
                try:
                    await plc_manager.read_all_parameters()
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Rapid operation {i+1} failed: {e}")

            elapsed = time.time() - start_time
            test_results['rapid_operations'] = {
                'total_operations': 50,
                'successful_operations': success_count,
                'success_rate': success_count / 50 * 100,
                'total_time': elapsed,
                'ops_per_second': success_count / elapsed
            }

            logger.info(f"  📊 Success rate: {success_count}/50 ({success_count/50*100:.1f}%)")
            logger.info(f"  ⚡ Operations per second: {success_count/elapsed:.1f}")

            # Test sustained load (simplified)
            logger.info("  Testing sustained load (30 seconds)...")
            sustained_start = time.time()
            sustained_success = 0

            while time.time() - sustained_start < 30:  # 30 seconds
                try:
                    await plc_manager.read_all_parameters()
                    sustained_success += 1
                    await asyncio.sleep(0.5)  # 2 ops per second
                except Exception as e:
                    logger.warning(f"Sustained operation failed: {e}")

            sustained_elapsed = time.time() - sustained_start
            test_results['sustained_load'] = {
                'duration': sustained_elapsed,
                'successful_operations': sustained_success,
                'avg_ops_per_second': sustained_success / sustained_elapsed
            }

            logger.info(f"  📈 Sustained performance: {sustained_success/sustained_elapsed:.1f} ops/s")

        except Exception as e:
            logger.error(f"Stress test failed: {e}")
            test_results['error'] = str(e)

        self.results['performance_tests'] = test_results

    def _generate_test_report(self):
        """Generate comprehensive test report."""
        logger.info("📋 GENERATING COMPREHENSIVE TEST REPORT...")

        print("\n" + "="*80)
        print("🔥 REAL PLC HARDWARE TESTING COMPREHENSIVE REPORT 🔥")
        print("="*80)

        # Connection Tests
        print("\n🔌 CONNECTION VALIDATION:")
        conn_tests = self.results.get('connection_tests', {})
        if conn_tests.get('connection_success'):
            print(f"  ✅ Connection: SUCCESS in {conn_tests.get('connection_time', 0):.3f}s")
            for func, result in conn_tests.get('modbus_functions', {}).items():
                status = "✅" if result.get('success') else "❌"
                print(f"  {status} {func}: {result.get('response_time', 0):.3f}s")
        else:
            print("  ❌ Connection: FAILED")

        # Performance Tests
        print("\n⚡ CRITICAL PERFORMANCE BOTTLENECK ANALYSIS:")
        perf_tests = self.results.get('bulk_vs_individual_tests', {})
        if 'performance_improvement' in perf_tests:
            improvement = perf_tests['performance_improvement']
            print(f"  🚀 Performance Improvement: {improvement:.1f}x faster with bulk reads")

            individual = perf_tests.get('individual_reads', {})
            bulk = perf_tests.get('bulk_reads', {})

            print(f"  📊 Individual reads: {individual.get('avg_time', 0):.3f}s avg")
            print(f"  📊 Bulk reads: {bulk.get('avg_time', 0):.3f}s avg")
            print(f"  📈 Throughput improvement: {bulk.get('params_per_second', 0) - individual.get('params_per_second', 0):.1f} params/s")

            if improvement >= 5.0:
                print("  🎉 EXCELLENT: Performance improvement exceeds expectations!")
            elif improvement >= 2.0:
                print("  ✅ GOOD: Significant performance improvement achieved")
            else:
                print("  ⚠️  WARNING: Performance improvement below expectations")
        else:
            print("  ❌ Performance test incomplete or failed")

        # Recovery Tests
        print("\n🔧 ERROR RECOVERY VALIDATION:")
        recovery_tests = self.results.get('error_recovery_tests', {})
        if recovery_tests.get('recovery_success'):
            recovery_time = recovery_tests.get('total_recovery_time', 0)
            print(f"  ✅ Recovery: SUCCESS in {recovery_time:.3f}s")
            for attempt in recovery_tests.get('recovery_attempts', []):
                status = "✅" if attempt.get('success') else "❌"
                print(f"    {status} Attempt {attempt.get('attempt')}: {attempt.get('time', 0):.3f}s")
        else:
            print("  ❌ Recovery: FAILED or incomplete")

        # Timing Tests
        print("\n⏱️  TIMING ACCURACY VALIDATION:")
        timing_tests = self.results.get('timing_accuracy_tests', {})
        if 'accuracy_percent' in timing_tests:
            accuracy = timing_tests['accuracy_percent']
            avg_interval = timing_tests.get('avg_interval', 0)
            jitter = timing_tests.get('jitter', 0)

            print(f"  📊 Average interval: {avg_interval:.3f}s (target: 1.000s)")
            print(f"  📈 Accuracy: {accuracy:.1f}%")
            print(f"  📊 Jitter (stdev): {jitter:.3f}s")

            if accuracy >= 95:
                print("  🎉 EXCELLENT: Timing accuracy within specifications")
            elif accuracy >= 90:
                print("  ✅ GOOD: Acceptable timing accuracy")
            else:
                print("  ⚠️  WARNING: Timing accuracy below expectations")
        else:
            print("  ❌ Timing test incomplete or failed")

        # Overall Assessment
        print("\n🎯 OVERALL HARDWARE VALIDATION ASSESSMENT:")

        success_indicators = [
            conn_tests.get('connection_success', False),
            perf_tests.get('performance_improvement', 0) >= 2.0,
            recovery_tests.get('recovery_success', False),
            timing_tests.get('accuracy_percent', 0) >= 90
        ]

        success_rate = sum(success_indicators) / len(success_indicators) * 100

        if success_rate >= 75:
            print("  🎉 OVERALL: EXCELLENT - Real PLC hardware validation successful!")
        elif success_rate >= 50:
            print("  ✅ OVERALL: GOOD - Most tests passed, minor issues identified")
        else:
            print("  ⚠️  OVERALL: ISSUES DETECTED - Significant problems require attention")

        print(f"  📊 Success Rate: {success_rate:.1f}%")

        # Save results to file
        results_file = f"real_plc_test_results_{int(time.time())}.json"
        try:
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n💾 Detailed results saved to: {results_file}")
        except Exception as e:
            logger.warning(f"Failed to save results to file: {e}")

        print("="*80)

async def main():
    """Main test execution."""
    load_dotenv()

    print("🔥 REAL PLC HARDWARE COMPREHENSIVE TESTING SUITE 🔥")
    print("Testing critical performance bottleneck and hardware validation")
    print("-" * 60)

    tester = RealPLCHardwareTester()
    await tester.run_comprehensive_test_suite()

if __name__ == "__main__":
    asyncio.run(main())