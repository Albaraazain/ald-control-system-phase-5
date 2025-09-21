#!/usr/bin/env python3
"""
Quick Performance Check Tool for Continuous Parameter Logging System

A lightweight tool for rapid performance assessment that can be run regularly
to monitor system health and detect performance issues quickly.

This tool runs essential performance checks in under 30 seconds and provides
immediate feedback on critical performance metrics.

Usage:
    python quick_performance_check.py
    python quick_performance_check.py --verbose
    python quick_performance_check.py --output health_check.json
"""

import asyncio
import time
import json
import sys
from datetime import datetime
from typing import Dict, List, Any

# System imports
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.plc.manager import plc_manager
from src.config import MACHINE_ID, PLC_TYPE, PLC_CONFIG


class QuickPerformanceCheck:
    """Lightweight performance monitoring tool."""

    def __init__(self, verbose: bool = False):
        """Initialize quick performance check."""
        self.verbose = verbose
        self.results = {}
        self.issues = []
        self.warnings = []

    async def run_quick_check(self) -> Dict[str, Any]:
        """Run quick performance check."""
        logger.info("Starting quick performance check...")
        start_time = time.perf_counter()

        # Core performance checks
        await self._check_database_response()
        await self._check_plc_connectivity()
        await self._check_logging_cycle_timing()
        await self._check_system_resources()

        # Analyze results
        total_time = (time.perf_counter() - start_time) * 1000
        overall_status = self._determine_overall_status()

        return {
            'timestamp': datetime.now().isoformat(),
            'check_duration_ms': total_time,
            'overall_status': overall_status,
            'performance_metrics': self.results,
            'issues': self.issues,
            'warnings': self.warnings,
            'recommendations': self._generate_quick_recommendations()
        }

    async def _check_database_response(self):
        """Check database response time."""
        if self.verbose:
            logger.info("Checking database response time...")

        try:
            # Simple query timing
            start_time = time.perf_counter()
            supabase = get_supabase()
            result = supabase.table('machines').select('id').limit(1).execute()
            db_latency = (time.perf_counter() - start_time) * 1000

            self.results['database_latency_ms'] = db_latency

            if db_latency > 500:
                self.issues.append(f"Database latency high: {db_latency:.1f}ms")
            elif db_latency > 200:
                self.warnings.append(f"Database latency elevated: {db_latency:.1f}ms")

            # Check machine status query
            start_time = time.perf_counter()
            status_result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()
            status_latency = (time.perf_counter() - start_time) * 1000

            self.results['status_query_latency_ms'] = status_latency

            if status_latency > 200:
                self.warnings.append(f"Status query slow: {status_latency:.1f}ms")

        except Exception as e:
            self.issues.append(f"Database connectivity failed: {str(e)}")
            self.results['database_latency_ms'] = None

    async def _check_plc_connectivity(self):
        """Check PLC connectivity and response."""
        if self.verbose:
            logger.info("Checking PLC connectivity...")

        try:
            # Check if PLC is connected
            plc_connected = plc_manager.is_connected()
            self.results['plc_connected'] = plc_connected

            if not plc_connected:
                # Try to connect
                start_time = time.perf_counter()
                success = await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)
                connection_time = (time.perf_counter() - start_time) * 1000

                self.results['plc_connection_time_ms'] = connection_time

                if not success:
                    self.issues.append("PLC connection failed")
                    return
                elif connection_time > 5000:
                    self.warnings.append(f"PLC connection slow: {connection_time:.1f}ms")

            # Test parameter read if connected
            if plc_manager.is_connected():
                if hasattr(plc_manager.plc, '_parameter_cache'):
                    parameter_ids = list(plc_manager.plc._parameter_cache.keys())
                    if parameter_ids:
                        # Test reading first parameter
                        test_param = parameter_ids[0]
                        start_time = time.perf_counter()
                        try:
                            value = await plc_manager.read_parameter(test_param)
                            read_time = (time.perf_counter() - start_time) * 1000
                            self.results['plc_parameter_read_ms'] = read_time

                            if read_time > 1000:
                                self.warnings.append(f"PLC parameter read slow: {read_time:.1f}ms")

                        except Exception as e:
                            self.issues.append(f"PLC parameter read failed: {str(e)}")

        except Exception as e:
            self.issues.append(f"PLC connectivity check failed: {str(e)}")
            self.results['plc_connected'] = False

    async def _check_logging_cycle_timing(self):
        """Check end-to-end logging cycle timing."""
        if self.verbose:
            logger.info("Checking logging cycle timing...")

        try:
            start_time = time.perf_counter()

            # Simulate logging cycle
            # 1. Status check
            supabase = get_supabase()
            status_result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()

            # 2. Parameter read (if PLC connected)
            if plc_manager.is_connected():
                try:
                    # Read a few parameters for timing
                    if hasattr(plc_manager.plc, '_parameter_cache'):
                        parameter_ids = list(plc_manager.plc._parameter_cache.keys())[:3]  # Test 3 parameters
                        for param_id in parameter_ids:
                            await plc_manager.read_parameter(param_id)
                except Exception as e:
                    logger.debug(f"Parameter read in cycle test failed: {e}")

            # 3. Database insert simulation
            timestamp = get_current_timestamp()
            test_record = {
                'parameter_id': 'QUICK_CHECK_TEST',
                'value': 42.0,
                'set_point': 40.0,
                'timestamp': timestamp
            }

            result = supabase.table('parameter_value_history').insert([test_record]).execute()

            # Clean up test record
            if result.data and len(result.data) > 0:
                record_id = result.data[0].get('id')
                if record_id:
                    supabase.table('parameter_value_history').delete().eq('id', record_id).execute()

            cycle_time = (time.perf_counter() - start_time) * 1000
            self.results['logging_cycle_ms'] = cycle_time

            # Check against 1-second logging window
            if cycle_time > 1000:
                self.issues.append(f"Logging cycle too slow: {cycle_time:.1f}ms (exceeds 1-second window)")
            elif cycle_time > 500:
                self.warnings.append(f"Logging cycle approaching limit: {cycle_time:.1f}ms")

        except Exception as e:
            self.issues.append(f"Logging cycle test failed: {str(e)}")
            self.results['logging_cycle_ms'] = None

    async def _check_system_resources(self):
        """Check basic system resource usage."""
        if self.verbose:
            logger.info("Checking system resources...")

        try:
            import psutil
            process = psutil.Process()

            # Memory usage
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.results['memory_usage_mb'] = memory_mb

            if memory_mb > 1000:
                self.warnings.append(f"High memory usage: {memory_mb:.1f}MB")

            # CPU usage (averaged over short period)
            cpu_percent = process.cpu_percent(interval=0.1)
            self.results['cpu_usage_percent'] = cpu_percent

            if cpu_percent > 80:
                self.warnings.append(f"High CPU usage: {cpu_percent:.1f}%")

            # System memory
            system_memory = psutil.virtual_memory()
            self.results['system_memory_available_mb'] = system_memory.available / 1024 / 1024
            self.results['system_memory_percent_used'] = system_memory.percent

            if system_memory.percent > 90:
                self.issues.append(f"System memory critically low: {system_memory.percent:.1f}% used")
            elif system_memory.percent > 80:
                self.warnings.append(f"System memory high: {system_memory.percent:.1f}% used")

        except Exception as e:
            self.warnings.append(f"System resource check failed: {str(e)}")

    def _determine_overall_status(self) -> str:
        """Determine overall system status."""
        if self.issues:
            return "CRITICAL"
        elif len(self.warnings) > 3:
            return "DEGRADED"
        elif self.warnings:
            return "WARNING"
        else:
            return "HEALTHY"

    def _generate_quick_recommendations(self) -> List[str]:
        """Generate quick recommendations based on findings."""
        recommendations = []

        # Database recommendations
        db_latency = self.results.get('database_latency_ms')
        if db_latency and db_latency > 300:
            recommendations.append("Consider implementing database connection pooling")

        # PLC recommendations
        if not self.results.get('plc_connected', False):
            recommendations.append("Check PLC network connectivity and configuration")

        plc_read_time = self.results.get('plc_parameter_read_ms')
        if plc_read_time and plc_read_time > 500:
            recommendations.append("Investigate PLC communication latency - consider bulk reads")

        # Logging cycle recommendations
        cycle_time = self.results.get('logging_cycle_ms')
        if cycle_time and cycle_time > 800:
            recommendations.append("Optimize logging cycle - implement parallel operations")

        # Resource recommendations
        memory_usage = self.results.get('memory_usage_mb')
        if memory_usage and memory_usage > 500:
            recommendations.append("Monitor for memory leaks - consider resource cleanup")

        # General recommendations
        if self.issues:
            recommendations.append("Address critical issues immediately before production use")

        if not recommendations:
            recommendations.append("System performance within acceptable parameters")

        return recommendations

    def generate_quick_report(self, check_data: Dict[str, Any]) -> str:
        """Generate quick performance report."""
        status = check_data['overall_status']
        status_icon = {
            'HEALTHY': '✅',
            'WARNING': '⚠️',
            'DEGRADED': '🔶',
            'CRITICAL': '❌'
        }.get(status, '❓')

        report = []
        report.append("=" * 60)
        report.append("QUICK PERFORMANCE CHECK REPORT")
        report.append("=" * 60)
        report.append(f"Status: {status_icon} {status}")
        report.append(f"Check Time: {check_data['timestamp']}")
        report.append(f"Duration: {check_data['check_duration_ms']:.1f}ms")
        report.append("")

        # Performance metrics
        metrics = check_data['performance_metrics']
        report.append("PERFORMANCE METRICS:")
        report.append("-" * 30)

        if 'database_latency_ms' in metrics:
            value = metrics['database_latency_ms']
            if value is not None:
                report.append(f"Database Response: {value:.1f}ms")
            else:
                report.append("Database Response: FAILED")

        if 'plc_connected' in metrics:
            connected = metrics['plc_connected']
            report.append(f"PLC Connected: {'YES' if connected else 'NO'}")

            if 'plc_parameter_read_ms' in metrics:
                read_time = metrics['plc_parameter_read_ms']
                report.append(f"PLC Parameter Read: {read_time:.1f}ms")

        if 'logging_cycle_ms' in metrics:
            cycle_time = metrics['logging_cycle_ms']
            if cycle_time is not None:
                status_text = "GOOD" if cycle_time < 500 else "SLOW" if cycle_time < 1000 else "CRITICAL"
                report.append(f"Logging Cycle: {cycle_time:.1f}ms ({status_text})")
            else:
                report.append("Logging Cycle: FAILED")

        if 'memory_usage_mb' in metrics:
            memory = metrics['memory_usage_mb']
            report.append(f"Memory Usage: {memory:.1f}MB")

        # Issues
        if check_data['issues']:
            report.append("\nCRITICAL ISSUES:")
            for issue in check_data['issues']:
                report.append(f"  ❌ {issue}")

        # Warnings
        if check_data['warnings']:
            report.append("\nWARNINGS:")
            for warning in check_data['warnings']:
                report.append(f"  ⚠️  {warning}")

        # Recommendations
        if check_data['recommendations']:
            report.append("\nRECOMMENDATIONS:")
            for rec in check_data['recommendations']:
                report.append(f"  💡 {rec}")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


async def main():
    """Main quick check execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Quick Performance Check for Continuous Parameter Logging')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    parser.add_argument('--report', help='Output file for report')

    args = parser.parse_args()

    quick_check = QuickPerformanceCheck(verbose=args.verbose)

    try:
        check_data = await quick_check.run_quick_check()

        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(check_data, f, indent=2, default=str)
            logger.info(f"Quick check results saved to {args.output}")

        # Generate and output report
        report = quick_check.generate_quick_report(check_data)

        if args.report:
            with open(args.report, 'w') as f:
                f.write(report)
            logger.info(f"Quick check report saved to {args.report}")
        else:
            print(report)

        # Exit with appropriate code
        status = check_data['overall_status']
        if status == 'CRITICAL':
            sys.exit(2)
        elif status in ['DEGRADED', 'WARNING']:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        logger.error(f"Quick performance check failed: {e}", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())