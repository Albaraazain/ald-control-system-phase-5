#!/usr/bin/env python3
"""
Resource Exhaustion Test Runner

Executes comprehensive resource exhaustion stress tests with detailed reporting.
This runner provides a convenient interface for executing specific test scenarios
and analyzing results.

Usage:
    python run_resource_exhaustion_tests.py [--test TEST_NAME] [--duration SECONDS] [--report-only]

Available Tests:
    - all: Run complete test suite (default)
    - memory: 24-hour memory exhaustion simulation
    - database: Database connection pool exhaustion
    - dual_recording: Dual recording conflict stress test
    - cpu_saturation: High parameter count CPU saturation
    - memory_leaks: Asyncio task accumulation memory leak test
    - data_loss: Silent data loss detection test
"""

import argparse
import asyncio
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_resource_exhaustion_stress import ResourceExhaustionTester, TestResult
from src.log_setup import logger


class TestRunner:
    """Manages execution and reporting of resource exhaustion tests."""

    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.output_dir = "test_results"

    def setup_output_directory(self):
        """Create output directory for test results."""
        Path(self.output_dir).mkdir(exist_ok=True)

    async def run_single_test(self, test_name: str, tester: ResourceExhaustionTester) -> TestResult:
        """Run a single test by name."""
        test_mapping = {
            'memory': tester.test_memory_exhaustion_24_hour_simulation,
            'database': tester.test_database_connection_pool_exhaustion,
            'dual_recording': tester.test_dual_recording_conflict_stress,
            'cpu_saturation': tester.test_high_parameter_count_cpu_saturation,
            'memory_leaks': tester.test_asyncio_task_accumulation_memory_leak,
            'data_loss': tester.test_silent_data_loss_under_stress,
        }

        if test_name not in test_mapping:
            raise ValueError(f"Unknown test: {test_name}. Available tests: {list(test_mapping.keys())}")

        logger.info(f"🧪 Running single test: {test_name}")
        return await test_mapping[test_name]()

    async def run_test_suite(self, test_name: str = None, duration: int = None) -> dict:
        """Run test suite with optional filtering."""
        logger.info("🚀 Starting Resource Exhaustion Test Runner")

        tester = ResourceExhaustionTester()

        # Initialize test environment
        if not await tester.initialize_test_environment():
            logger.error("❌ Failed to initialize test environment")
            return {}

        try:
            if test_name == "all" or test_name is None:
                # Run complete test suite
                results = await tester.run_comprehensive_resource_exhaustion_suite()
            else:
                # Run single test
                result = await self.run_single_test(test_name, tester)
                results = {test_name: result}

            self.test_results = results
            return results

        except Exception as e:
            logger.error(f"💥 Test execution failed: {e}")
            return {}

    def save_results_to_file(self, results: dict):
        """Save test results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"{self.output_dir}/resource_exhaustion_results_{timestamp}.json"

        # Convert TestResult objects to dictionaries for JSON serialization
        json_results = {}
        for test_name, result in results.items():
            json_results[test_name] = {
                'test_name': result.test_name,
                'success': result.success,
                'duration': result.duration,
                'error_message': result.error_message,
                'data_integrity_violations': result.data_integrity_violations,
                'memory_leaks_detected': result.memory_leaks_detected,
                'max_memory_usage_mb': result.max_memory_usage_mb,
                'breaking_point_reached': result.breaking_point_reached,
                'breaking_point_description': result.breaking_point_description,
                'resource_metrics_count': len(result.resource_metrics) if result.resource_metrics else 0
            }

        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'test_duration': time.time() - self.start_time if self.start_time else 0,
                'results': json_results
            }, f, indent=2)

        logger.info(f"📄 Results saved to: {results_file}")

    def generate_summary_report(self, results: dict):
        """Generate summary report of test results."""
        logger.info("📊 RESOURCE EXHAUSTION TEST SUMMARY REPORT")
        logger.info("=" * 60)

        if not results:
            logger.error("❌ No test results to report")
            return

        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r.success)
        failed_tests = total_tests - passed_tests

        # Overall summary
        logger.info(f"🎯 OVERALL RESULTS:")
        logger.info(f"  Total Tests: {total_tests}")
        logger.info(f"  Passed: {passed_tests}")
        logger.info(f"  Failed: {failed_tests}")
        logger.info(f"  Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        # Critical findings
        critical_issues = []
        memory_leaks = 0
        data_corruption = 0
        breaking_points = 0

        for result in results.values():
            if result.breaking_point_reached:
                breaking_points += 1
                critical_issues.append(f"Breaking point in {result.test_name}: {result.breaking_point_description}")

            memory_leaks += result.memory_leaks_detected
            data_corruption += result.data_integrity_violations

        logger.info(f"\n🚨 CRITICAL ISSUES SUMMARY:")
        logger.info(f"  Breaking Points Reached: {breaking_points}")
        logger.info(f"  Memory Leaks Detected: {memory_leaks}")
        logger.info(f"  Data Integrity Violations: {data_corruption}")

        if critical_issues:
            logger.info(f"\n📋 CRITICAL ISSUES DETAILS:")
            for issue in critical_issues:
                logger.error(f"  🚨 {issue}")
        else:
            logger.info("  ✅ No critical issues detected")

        # Test-specific results
        logger.info(f"\n📊 DETAILED TEST RESULTS:")
        for test_name, result in results.items():
            status = "✅ PASS" if result.success else "❌ FAIL"
            logger.info(f"  {status} {test_name}:")
            logger.info(f"    Duration: {result.duration:.2f}s")

            if result.max_memory_usage_mb > 0:
                logger.info(f"    Peak Memory: {result.max_memory_usage_mb:.2f}MB")

            if result.error_message:
                logger.info(f"    Error: {result.error_message}")

        # Recommendations based on results
        logger.info(f"\n💡 RECOMMENDATIONS:")

        if breaking_points > 0:
            logger.info("  🔧 URGENT: Implement resource limits and circuit breakers")
            logger.info("  🔧 URGENT: Add system monitoring and alerting")

        if memory_leaks > 0:
            logger.info("  🔧 Fix asyncio task lifecycle management")
            logger.info("  🔧 Implement memory monitoring and leak detection")

        if data_corruption > 0:
            logger.info("  🔧 CRITICAL: Implement database transaction boundaries")
            logger.info("  🔧 CRITICAL: Add data integrity validation")

        if failed_tests > 0:
            logger.info("  🔧 Review failed tests and implement fixes")
            logger.info("  🔧 Consider architecture redesign for failed components")

        logger.info("  🔧 Implement comprehensive monitoring and observability")
        logger.info("  🔧 Add performance testing to CI/CD pipeline")

    def generate_detailed_report(self, results: dict):
        """Generate detailed technical report for each test."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{self.output_dir}/detailed_report_{timestamp}.md"

        with open(report_file, 'w') as f:
            f.write("# Resource Exhaustion Stress Test - Detailed Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## Executive Summary\n\n")

            total_tests = len(results)
            passed_tests = sum(1 for r in results.values() if r.success)

            f.write(f"- **Total Tests:** {total_tests}\n")
            f.write(f"- **Success Rate:** {(passed_tests/total_tests)*100:.1f}%\n")
            f.write(f"- **Critical Issues:** {sum(1 for r in results.values() if r.breaking_point_reached)}\n\n")

            # Individual test reports
            for test_name, result in results.items():
                f.write(f"## Test: {test_name}\n\n")
                f.write(f"**Status:** {'✅ PASSED' if result.success else '❌ FAILED'}\n")
                f.write(f"**Duration:** {result.duration:.2f} seconds\n\n")

                if result.breaking_point_reached:
                    f.write(f"**⚠️ Breaking Point Reached:** {result.breaking_point_description}\n\n")

                if result.memory_leaks_detected > 0:
                    f.write(f"**🚨 Memory Leaks:** {result.memory_leaks_detected} detected\n\n")

                if result.data_integrity_violations > 0:
                    f.write(f"**⚠️ Data Integrity Issues:** {result.data_integrity_violations} violations\n\n")

                if result.error_message:
                    f.write(f"**Error Details:**\n```\n{result.error_message}\n```\n\n")

                f.write("---\n\n")

        logger.info(f"📄 Detailed report saved to: {report_file}")


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Resource Exhaustion Stress Test Runner")
    parser.add_argument('--test', choices=['all', 'memory', 'database', 'dual_recording', 'cpu_saturation', 'memory_leaks', 'data_loss'],
                       default='all', help='Specific test to run (default: all)')
    parser.add_argument('--duration', type=int, help='Test duration override in seconds')
    parser.add_argument('--report-only', action='store_true', help='Generate report from latest results only')
    parser.add_argument('--output-dir', default='test_results', help='Output directory for results')

    args = parser.parse_args()

    runner = TestRunner()
    runner.output_dir = args.output_dir
    runner.setup_output_directory()

    if args.report_only:
        logger.info("📊 Report-only mode: Looking for latest test results...")
        # In a real implementation, you'd load the latest results file
        logger.info("💡 Run tests first to generate reports")
        return

    runner.start_time = time.time()

    try:
        # Run the tests
        results = await runner.run_test_suite(test_name=args.test, duration=args.duration)

        if results:
            # Save results to file
            runner.save_results_to_file(results)

            # Generate reports
            runner.generate_summary_report(results)
            runner.generate_detailed_report(results)

            # Exit code based on results
            if all(result.success for result in results.values()):
                logger.info("🎉 All tests passed!")
                sys.exit(0)
            else:
                logger.error("💥 Some tests failed!")
                sys.exit(1)
        else:
            logger.error("❌ No test results generated")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⚠️ Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())