#!/usr/bin/env python3
"""
Parameter Synchronization Integration Test Runner

Coordinates and executes all parameter synchronization integration tests:
1. Main integration test suite
2. Cross-component integration tests
3. Transaction integrity tests
4. Generates comprehensive reports and metrics
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
import argparse

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger

# Import test suites
from test_parameter_synchronization import ParameterSynchronizationIntegrationTest
from test_parameter_cross_component import CrossComponentIntegrationTest
from test_parameter_transaction_integrity import TransactionIntegrityTest

# Set up logging
logger = setup_logger(__name__)


class ParameterSyncTestRunner:
    """Comprehensive test runner for parameter synchronization integration tests."""

    def __init__(self, include_performance: bool = True, include_slow_tests: bool = False):
        self.include_performance = include_performance
        self.include_slow_tests = include_slow_tests
        self.test_results = {
            "runner_id": f"param_sync_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "start_time": datetime.now().isoformat(),
            "test_suites": {},
            "summary": {},
            "environment": {
                "python_version": sys.version,
                "test_mode": "integration",
                "performance_tests_included": include_performance,
                "slow_tests_included": include_slow_tests
            }
        }

    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all parameter synchronization integration test suites."""
        logger.info("🚀 Starting Comprehensive Parameter Synchronization Integration Tests")
        logger.info(f"Runner ID: {self.test_results['runner_id']}")
        logger.info("=" * 80)

        try:
            # Test Suite 1: Main Parameter Synchronization Integration Tests
            await self._run_main_integration_tests()

            # Test Suite 2: Cross-Component Integration Tests
            await self._run_cross_component_tests()

            # Test Suite 3: Transaction Integrity Tests
            await self._run_transaction_integrity_tests()

            # Generate final summary
            await self._generate_final_summary()

        except Exception as e:
            logger.error(f"💥 Critical failure in test runner: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.test_results["critical_error"] = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat()
            }

        self.test_results["end_time"] = datetime.now().isoformat()
        return self.test_results

    async def _run_main_integration_tests(self):
        """Run main parameter synchronization integration tests."""
        suite_name = "main_parameter_synchronization"
        logger.info(f"📋 Running {suite_name} test suite")

        suite_start_time = datetime.now()

        try:
            test_framework = ParameterSynchronizationIntegrationTest()

            # Execute all main integration tests
            logger.info("  🔍 Testing current state parameter read flow...")
            result1 = await test_framework.test_current_state_parameter_read_flow()

            logger.info("  🔍 Testing current state parameter write flow...")
            result2 = await test_framework.test_current_state_parameter_write_flow()

            logger.info("  🔍 Testing dual-mode operation integration...")
            result3 = await test_framework.test_dual_mode_operation_integration()

            logger.info("  🔍 Testing enhanced current_value synchronization...")
            result4 = await test_framework.test_enhanced_current_value_synchronization()

            logger.info("  🔍 Testing enhanced set_value synchronization...")
            result5 = await test_framework.test_enhanced_set_value_synchronization()

            logger.info("  🔍 Testing recipe execution parameter integration...")
            result6 = await test_framework.test_recipe_execution_parameter_integration()

            logger.info("  🔍 Testing parameter control listener integration...")
            result7 = await test_framework.test_parameter_control_listener_integration()

            logger.info("  🔍 Testing concurrent parameter operations...")
            result8 = await test_framework.test_concurrent_parameter_operations()

            logger.info("  🔍 Testing transaction rollback scenarios...")
            result9 = await test_framework.test_transaction_rollback_scenarios()

            if self.include_performance:
                logger.info("  🔍 Testing performance with 84 parameters per second...")
                result10 = await test_framework.test_performance_84_parameters_per_second()
            else:
                result10 = None

            # Collect results
            all_results = [result1, result2, result3, result4, result5, result6, result7, result8, result9]
            if result10:
                all_results.append(result10)

            # Generate suite report
            suite_report = test_framework.generate_test_report()

            self.test_results["test_suites"][suite_name] = {
                "suite_report": suite_report,
                "duration_seconds": (datetime.now() - suite_start_time).total_seconds(),
                "tests_executed": len(all_results),
                "individual_results": [
                    {
                        "test_name": r.test_name,
                        "success": r.success,
                        "current_value_updated": r.current_value_updated,
                        "set_value_updated": r.set_value_updated,
                        "performance_metrics": r.performance_metrics,
                        "error_message": r.error_message
                    } for r in all_results
                ]
            }

            logger.info(f"  ✅ {suite_name} completed: {suite_report['summary']['passed']}/{suite_report['summary']['total_tests']} passed")

        except Exception as e:
            logger.error(f"  ❌ {suite_name} failed: {str(e)}")
            self.test_results["test_suites"][suite_name] = {
                "error": str(e),
                "duration_seconds": (datetime.now() - suite_start_time).total_seconds()
            }

    async def _run_cross_component_tests(self):
        """Run cross-component integration tests."""
        suite_name = "cross_component_integration"
        logger.info(f"📋 Running {suite_name} test suite")

        suite_start_time = datetime.now()

        try:
            test_framework = CrossComponentIntegrationTest()

            # Execute cross-component tests
            results = []

            logger.info("  🔍 Testing parameter control listener command flow...")
            results.append(await test_framework.test_parameter_control_listener_command_flow())

            logger.info("  🔍 Testing recipe execution parameter steps integration...")
            results.append(await test_framework.test_recipe_execution_parameter_steps_integration())

            logger.info("  🔍 Testing manual parameter commands integration...")
            results.append(await test_framework.test_manual_parameter_commands_integration())

            logger.info("  🔍 Testing PLC simulation vs real consistency...")
            results.append(await test_framework.test_plc_simulation_vs_real_consistency())

            logger.info("  🔍 Testing valve operations parameter synchronization...")
            results.append(await test_framework.test_valve_operations_parameter_synchronization())

            logger.info("  🔍 Testing continuous logging integration...")
            results.append(await test_framework.test_continuous_logging_integration())

            # Calculate summary
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r)
            failed_tests = total_tests - passed_tests

            self.test_results["test_suites"][suite_name] = {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "duration_seconds": (datetime.now() - suite_start_time).total_seconds(),
                "test_results": results
            }

            logger.info(f"  ✅ {suite_name} completed: {passed_tests}/{total_tests} passed")

        except Exception as e:
            logger.error(f"  ❌ {suite_name} failed: {str(e)}")
            self.test_results["test_suites"][suite_name] = {
                "error": str(e),
                "duration_seconds": (datetime.now() - suite_start_time).total_seconds()
            }

    async def _run_transaction_integrity_tests(self):
        """Run transaction integrity tests."""
        suite_name = "transaction_integrity"
        logger.info(f"📋 Running {suite_name} test suite")

        suite_start_time = datetime.now()

        try:
            test_framework = TransactionIntegrityTest()

            # Execute transaction integrity tests
            results = []

            logger.info("  🔍 Testing ACID compliance for parameter updates...")
            results.append(await test_framework.test_acid_compliance_parameter_updates())

            logger.info("  🔍 Testing transaction rollback scenarios...")
            results.append(await test_framework.test_transaction_rollback_scenarios())

            logger.info("  🔍 Testing concurrent transaction handling...")
            results.append(await test_framework.test_concurrent_transaction_handling())

            logger.info("  🔍 Testing compensation actions and recovery...")
            results.append(await test_framework.test_compensation_actions_and_recovery())

            logger.info("  🔍 Testing consistency across multiple tables...")
            results.append(await test_framework.test_consistency_across_multiple_tables())

            # Calculate summary
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r)
            failed_tests = total_tests - passed_tests

            self.test_results["test_suites"][suite_name] = {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "duration_seconds": (datetime.now() - suite_start_time).total_seconds(),
                "test_results": results
            }

            logger.info(f"  ✅ {suite_name} completed: {passed_tests}/{total_tests} passed")

        except Exception as e:
            logger.error(f"  ❌ {suite_name} failed: {str(e)}")
            self.test_results["test_suites"][suite_name] = {
                "error": str(e),
                "duration_seconds": (datetime.now() - suite_start_time).total_seconds()
            }

    async def _generate_final_summary(self):
        """Generate final comprehensive summary."""
        logger.info("📊 Generating final test summary...")

        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_duration = 0

        suite_summaries = {}

        for suite_name, suite_data in self.test_results["test_suites"].items():
            if "error" in suite_data:
                suite_summaries[suite_name] = {
                    "status": "error",
                    "error": suite_data["error"],
                    "duration": suite_data.get("duration_seconds", 0)
                }
                total_failed += 1  # Count failed suite as one failure
            else:
                # Extract test counts from different suite formats
                if "suite_report" in suite_data:
                    # Main integration test format
                    summary = suite_data["suite_report"]["summary"]
                    suite_tests = summary["total_tests"]
                    suite_passed = summary["passed"]
                    suite_failed = summary["failed"]
                else:
                    # Cross-component and transaction integrity format
                    suite_tests = suite_data["total_tests"]
                    suite_passed = suite_data["passed"]
                    suite_failed = suite_data["failed"]

                total_tests += suite_tests
                total_passed += suite_passed
                total_failed += suite_failed
                total_duration += suite_data.get("duration_seconds", 0)

                suite_summaries[suite_name] = {
                    "status": "completed",
                    "total_tests": suite_tests,
                    "passed": suite_passed,
                    "failed": suite_failed,
                    "success_rate": (suite_passed / suite_tests * 100) if suite_tests > 0 else 0,
                    "duration": suite_data.get("duration_seconds", 0)
                }

        self.test_results["summary"] = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "overall_success_rate": (total_passed / total_tests * 100) if total_tests > 0 else 0,
            "total_duration_seconds": total_duration,
            "suite_summaries": suite_summaries
        }

    def save_report(self, filename: str = None) -> str:
        """Save comprehensive test report to file."""
        if filename is None:
            filename = f"parameter_sync_integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        return filename

    def print_summary(self):
        """Print comprehensive test summary."""
        summary = self.test_results.get("summary", {})

        logger.info("=" * 80)
        logger.info("🏁 PARAMETER SYNCHRONIZATION INTEGRATION TEST FINAL RESULTS")
        logger.info("=" * 80)
        logger.info(f"Runner ID: {self.test_results['runner_id']}")
        logger.info(f"Total Tests: {summary.get('total_tests', 0)}")
        logger.info(f"Passed: {summary.get('total_passed', 0)}")
        logger.info(f"Failed: {summary.get('total_failed', 0)}")
        logger.info(f"Overall Success Rate: {summary.get('overall_success_rate', 0):.1f}%")
        logger.info(f"Total Duration: {summary.get('total_duration_seconds', 0):.2f} seconds")
        logger.info("=" * 80)

        # Print suite summaries
        suite_summaries = summary.get("suite_summaries", {})
        for suite_name, suite_summary in suite_summaries.items():
            if suite_summary["status"] == "error":
                logger.info(f"❌ {suite_name}: ERROR - {suite_summary['error']}")
            else:
                status_emoji = "✅" if suite_summary["failed"] == 0 else "⚠️"
                logger.info(
                    f"{status_emoji} {suite_name}: "
                    f"{suite_summary['passed']}/{suite_summary['total_tests']} passed "
                    f"({suite_summary['success_rate']:.1f}%) "
                    f"in {suite_summary['duration']:.2f}s"
                )

        logger.info("=" * 80)

        # Test recommendations based on results
        if summary.get('total_failed', 0) > 0:
            logger.warning("🔧 RECOMMENDATIONS:")
            if summary.get('overall_success_rate', 0) < 50:
                logger.warning("  • Major integration issues detected - review architecture")
            elif summary.get('overall_success_rate', 0) < 80:
                logger.warning("  • Some integration gaps found - address failing tests")
            else:
                logger.warning("  • Minor issues detected - review failed test details")
        else:
            logger.info("🎉 ALL INTEGRATION TESTS PASSED! Parameter synchronization is ready.")


async def main():
    """Main entry point for the parameter synchronization integration test runner."""
    parser = argparse.ArgumentParser(description="Parameter Synchronization Integration Test Runner")
    parser.add_argument("--no-performance", action="store_true", help="Skip performance tests")
    parser.add_argument("--include-slow", action="store_true", help="Include slow tests")
    parser.add_argument("--save-report", help="Save report to specific filename")

    args = parser.parse_args()

    try:
        logger.info("🚀 Starting Parameter Synchronization Integration Test Runner")

        # Initialize test runner
        runner = ParameterSyncTestRunner(
            include_performance=not args.no_performance,
            include_slow_tests=args.include_slow
        )

        # Run all tests
        results = await runner.run_all_tests()

        # Print summary
        runner.print_summary()

        # Save report
        report_filename = runner.save_report(args.save_report)
        logger.info(f"📄 Detailed report saved: {report_filename}")

        # Determine exit code
        summary = results.get("summary", {})
        total_failed = summary.get("total_failed", 0)

        if "critical_error" in results:
            logger.error("💥 Critical error occurred during test execution")
            return 2
        elif total_failed > 0:
            logger.error(f"💥 {total_failed} tests failed")
            return 1
        else:
            logger.info("🎉 All tests passed successfully!")
            return 0

    except Exception as e:
        logger.error(f"💥 Critical failure in test runner: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)