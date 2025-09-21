"""
Comprehensive network failure stress test orchestrator.
Executes all network failure tests and provides detailed analysis and recommendations.
"""
import os
import sys
import asyncio
import time
import json
import subprocess
from typing import Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.log_setup import logger


class NetworkStressTestOrchestrator:
    """Orchestrate comprehensive network failure stress tests."""

    def __init__(self):
        self.test_results = {
            'execution_summary': {},
            'test_suites': [],
            'failure_analysis': {},
            'recommendations': [],
            'execution_metadata': {}
        }
        self.start_time = None

    async def run_test_suite(self, test_script: str, test_name: str) -> Dict[str, Any]:
        """Run a specific test suite and capture results."""
        logger.info(f"🚀 Executing {test_name}...")

        test_result = {
            'name': test_name,
            'script': test_script,
            'start_time': time.time(),
            'success': False,
            'duration': 0,
            'output': '',
            'error': None
        }

        try:
            # Execute test script
            process = await asyncio.create_subprocess_exec(
                sys.executable, test_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=os.path.dirname(test_script)
            )

            stdout, _ = await process.communicate()
            test_result['output'] = stdout.decode() if stdout else ''
            test_result['success'] = process.returncode == 0

        except Exception as e:
            test_result['error'] = str(e)
            logger.error(f"Failed to execute {test_name}: {e}")

        test_result['duration'] = time.time() - test_result['start_time']

        status = "✅ PASSED" if test_result['success'] else "❌ FAILED"
        logger.info(f"{status}: {test_name} completed in {test_result['duration']:.1f}s")

        return test_result

    def analyze_test_outputs(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze test outputs for patterns and failures."""
        analysis = {
            'total_tests': len(test_results),
            'passed_tests': 0,
            'failed_tests': 0,
            'critical_issues': [],
            'warning_issues': [],
            'performance_metrics': {},
            'network_resilience_assessment': 'unknown'
        }

        for test in test_results:
            if test['success']:
                analysis['passed_tests'] += 1
            else:
                analysis['failed_tests'] += 1

            # Analyze output for specific patterns
            output = test.get('output', '').lower()

            # Look for critical issues
            if 'broken pipe' in output and 'failed' in output:
                analysis['critical_issues'].append(f"{test['name']}: Broken pipe recovery failure")

            if 'data loss' in output or 'corruption' in output:
                analysis['critical_issues'].append(f"{test['name']}: Data integrity issues detected")

            if 'pool exhausted' in output and 'failed' in output:
                analysis['critical_issues'].append(f"{test['name']}: Connection pool exhaustion handling failure")

            if 'timeout' in output and 'recovery' in output:
                analysis['warning_issues'].append(f"{test['name']}: Slow recovery times detected")

            # Extract performance metrics
            if 'recovery time:' in output:
                # Extract recovery time information
                lines = output.split('\n')
                for line in lines:
                    if 'recovery time:' in line:
                        try:
                            time_part = line.split('recovery time:')[1].strip()
                            recovery_time = float(time_part.replace('s', '').strip())
                            analysis['performance_metrics'][f"{test['name']}_recovery_time"] = recovery_time
                        except:
                            pass

        # Overall assessment
        pass_rate = analysis['passed_tests'] / analysis['total_tests'] if analysis['total_tests'] > 0 else 0

        if pass_rate >= 0.9:
            analysis['network_resilience_assessment'] = 'excellent'
        elif pass_rate >= 0.75:
            analysis['network_resilience_assessment'] = 'good'
        elif pass_rate >= 0.5:
            analysis['network_resilience_assessment'] = 'concerning'
        else:
            analysis['network_resilience_assessment'] = 'critical'

        return analysis

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate specific recommendations based on test analysis."""
        recommendations = []

        # Based on pass rate
        if analysis['network_resilience_assessment'] == 'critical':
            recommendations.extend([
                "URGENT: Network failure handling is critically insufficient",
                "Implement comprehensive connection retry logic with exponential backoff",
                "Add circuit breaker patterns for all network operations",
                "Review and redesign error handling architecture"
            ])

        elif analysis['network_resilience_assessment'] == 'concerning':
            recommendations.extend([
                "Improve network failure recovery mechanisms",
                "Add monitoring and alerting for network issues",
                "Implement proper connection pooling"
            ])

        # Based on specific issues
        if any('broken pipe' in issue for issue in analysis['critical_issues']):
            recommendations.extend([
                "Fix broken pipe error handling in PLC communication",
                "Validate PLCCommunicator retry logic is working correctly",
                "Add more robust connection health checks"
            ])

        if any('data' in issue for issue in analysis['critical_issues']):
            recommendations.extend([
                "CRITICAL: Implement transaction boundaries for dual-mode logging",
                "Add data integrity validation and monitoring",
                "Review database operation error handling"
            ])

        if any('pool' in issue for issue in analysis['critical_issues']):
            recommendations.extend([
                "Implement proper database connection pooling",
                "Add connection leak detection and monitoring",
                "Review resource cleanup in error scenarios"
            ])

        # Performance-based recommendations
        recovery_times = [v for k, v in analysis['performance_metrics'].items() if 'recovery_time' in k]
        if recovery_times:
            avg_recovery = sum(recovery_times) / len(recovery_times)
            if avg_recovery > 20:
                recommendations.append(f"Optimize recovery times (current average: {avg_recovery:.1f}s)")

        # Default recommendations if no specific issues
        if not recommendations:
            recommendations.extend([
                "Network failure handling appears functional",
                "Consider adding more comprehensive monitoring",
                "Regular testing of failure scenarios recommended"
            ])

        return recommendations

    def generate_comprehensive_report(self):
        """Generate comprehensive test report with analysis and recommendations."""
        logger.info("=" * 80)
        logger.info("🏁 COMPREHENSIVE NETWORK FAILURE STRESS TEST REPORT")
        logger.info("=" * 80)

        # Execution summary
        summary = self.test_results['execution_summary']
        logger.info(f"📊 EXECUTION SUMMARY:")
        logger.info(f"  Total test suites executed: {summary.get('total_suites', 0)}")
        logger.info(f"  Successful test suites: {summary.get('successful_suites', 0)}")
        logger.info(f"  Failed test suites: {summary.get('failed_suites', 0)}")
        logger.info(f"  Total execution time: {summary.get('total_duration', 0):.1f} seconds")

        # Test suite details
        logger.info(f"\n📋 TEST SUITE RESULTS:")
        for test in self.test_results['test_suites']:
            status = "✅" if test['success'] else "❌"
            logger.info(f"  {status} {test['name']} ({test['duration']:.1f}s)")
            if test.get('error'):
                logger.info(f"    Error: {test['error']}")

        # Failure analysis
        analysis = self.test_results['failure_analysis']
        logger.info(f"\n🔍 FAILURE ANALYSIS:")
        logger.info(f"  Network resilience assessment: {analysis.get('network_resilience_assessment', 'unknown').upper()}")
        logger.info(f"  Pass rate: {analysis.get('passed_tests', 0)}/{analysis.get('total_tests', 0)}")

        if analysis.get('critical_issues'):
            logger.info(f"\n🚨 CRITICAL ISSUES:")
            for issue in analysis['critical_issues']:
                logger.info(f"    • {issue}")

        if analysis.get('warning_issues'):
            logger.info(f"\n⚠️ WARNING ISSUES:")
            for issue in analysis['warning_issues']:
                logger.info(f"    • {issue}")

        # Performance metrics
        if analysis.get('performance_metrics'):
            logger.info(f"\n📈 PERFORMANCE METRICS:")
            for metric, value in analysis['performance_metrics'].items():
                logger.info(f"    {metric}: {value:.2f}s")

        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(self.test_results['recommendations'], 1):
            logger.info(f"  {i}. {rec}")

        # Overall verdict
        logger.info(f"\n🎯 OVERALL VERDICT:")
        assessment = analysis.get('network_resilience_assessment', 'unknown')

        if assessment == 'excellent':
            logger.info("🟢 EXCELLENT: Network failure handling is robust and well-implemented")
        elif assessment == 'good':
            logger.info("🟡 GOOD: Network failure handling is functional with room for improvement")
        elif assessment == 'concerning':
            logger.info("🟠 CONCERNING: Network failure handling has significant issues requiring attention")
        else:
            logger.info("🔴 CRITICAL: Network failure handling is inadequate and requires immediate action")

        # Save detailed report to file
        self.save_detailed_report()

    def save_detailed_report(self):
        """Save detailed report to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"network_stress_test_report_{timestamp}.json"
        report_path = os.path.join(os.path.dirname(__file__), report_file)

        try:
            with open(report_path, 'w') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            logger.info(f"📄 Detailed report saved to: {report_path}")
        except Exception as e:
            logger.warning(f"Failed to save detailed report: {e}")

    async def run_comprehensive_network_stress_tests(self):
        """Run all comprehensive network failure stress tests."""
        self.start_time = time.time()

        logger.info("🚀 STARTING COMPREHENSIVE NETWORK FAILURE STRESS TESTS")
        logger.info("=" * 80)
        logger.info("This test suite validates network resilience and failure recovery")
        logger.info("across PLC communication, database connectivity, and system integration.")
        logger.info("=" * 80)

        # Define test suites to execute
        test_suites = [
            {
                'script': 'test_continuous_logging_network_failures.py',
                'name': 'Continuous Logging Network Failures'
            },
            {
                'script': 'test_connection_pool_exhaustion.py',
                'name': 'Connection Pool Exhaustion'
            },
            {
                'script': 'test_broken_pipe_stress.py',
                'name': 'Broken Pipe Stress Test'
            },
            {
                'script': 'test_network_disconnection.py',
                'name': 'Network Disconnection Recovery'
            }
        ]

        # Execute each test suite
        test_results = []
        debug_dir = os.path.dirname(__file__)

        for suite in test_suites:
            script_path = os.path.join(debug_dir, suite['script'])

            if os.path.exists(script_path):
                result = await self.run_test_suite(script_path, suite['name'])
                test_results.append(result)
                self.test_results['test_suites'].append(result)

                # Brief pause between test suites
                await asyncio.sleep(3)
            else:
                logger.warning(f"Test script not found: {script_path}")

        # Analyze results
        analysis = self.analyze_test_outputs(test_results)
        self.test_results['failure_analysis'] = analysis

        # Generate recommendations
        recommendations = self.generate_recommendations(analysis)
        self.test_results['recommendations'] = recommendations

        # Execution metadata
        total_duration = time.time() - self.start_time
        self.test_results['execution_metadata'] = {
            'start_time': self.start_time,
            'end_time': time.time(),
            'total_duration': total_duration,
            'python_version': sys.version,
            'test_environment': 'development'
        }

        # Execution summary
        self.test_results['execution_summary'] = {
            'total_suites': len(test_results),
            'successful_suites': sum(1 for t in test_results if t['success']),
            'failed_suites': sum(1 for t in test_results if not t['success']),
            'total_duration': total_duration
        }

        # Generate comprehensive report
        self.generate_comprehensive_report()

        # Return overall success
        return analysis['network_resilience_assessment'] in ['excellent', 'good']


async def main():
    """Main execution function."""
    load_dotenv()

    orchestrator = NetworkStressTestOrchestrator()
    success = await orchestrator.run_comprehensive_network_stress_tests()

    if success:
        logger.info("🎉 Comprehensive network stress tests completed with acceptable results")
        sys.exit(0)
    else:
        logger.error("💥 Comprehensive network stress tests revealed critical issues")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())