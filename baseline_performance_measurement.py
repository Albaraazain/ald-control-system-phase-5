#!/usr/bin/env python3
"""
Baseline Performance Measurement Tool for Continuous Parameter Logging System

This tool establishes current performance baselines for the continuous parameter
logging system, providing reference measurements against which optimizations
can be evaluated.

Key Performance Indicators Measured:
1. End-to-end logging cycle latency
2. Database operation performance
3. PLC communication timing
4. Memory and CPU utilization patterns
5. Error recovery timing
6. Dual-mode logging overhead

Usage:
    python baseline_performance_measurement.py
    python baseline_performance_measurement.py --duration 300  # 5-minute baseline
    python baseline_performance_measurement.py --output baseline_results.json
"""

import asyncio
import time
import json
import psutil
import statistics
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# System imports
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.plc.manager import plc_manager
from src.data_collection.continuous_parameter_logger import ContinuousParameterLogger
from src.config import MACHINE_ID, PLC_TYPE, PLC_CONFIG


@dataclass
class BaselineMetric:
    """Baseline measurement data structure."""
    name: str
    value: float
    unit: str
    samples: int
    std_dev: float
    min_value: float
    max_value: float
    timestamp: datetime
    notes: str = ""


class BaselinePerformanceMeasurement:
    """Tool for establishing performance baselines."""

    def __init__(self, measurement_duration: int = 120):
        """
        Initialize baseline measurement tool.

        Args:
            measurement_duration: Duration in seconds for baseline measurements
        """
        self.duration = measurement_duration
        self.process = psutil.Process()
        self.baseline_metrics: List[BaselineMetric] = []
        self.test_data_cleanup: List[str] = []

    async def establish_baseline(self) -> Dict[str, Any]:
        """Establish comprehensive performance baseline."""
        logger.info(f"Starting {self.duration}-second baseline performance measurement")
        start_time = datetime.now()

        try:
            # Initialize system connections
            await self._initialize_connections()

            # Parallel baseline measurements
            baseline_tasks = [
                self._measure_database_baseline(),
                self._measure_plc_baseline(),
                self._measure_system_resource_baseline(),
                self._measure_logging_cycle_baseline(),
                self._measure_dual_mode_baseline()
            ]

            # Run measurements concurrently
            await asyncio.gather(*baseline_tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Baseline measurement failed: {e}", exc_info=True)
        finally:
            await self._cleanup()

        end_time = datetime.now()
        measurement_duration = (end_time - start_time).total_seconds()

        return {
            'baseline_metrics': [asdict(metric) for metric in self.baseline_metrics],
            'measurement_start': start_time.isoformat(),
            'measurement_end': end_time.isoformat(),
            'actual_duration_seconds': measurement_duration,
            'target_duration_seconds': self.duration,
            'system_info': self._get_system_info()
        }

    async def _initialize_connections(self):
        """Initialize necessary connections for baseline measurement."""
        # Ensure PLC connection
        if not plc_manager.is_connected():
            success = await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)
            if not success:
                logger.warning("PLC not available for baseline measurement")

        # Test database connection
        try:
            supabase = get_supabase()
            result = supabase.table('machines').select('id').limit(1).execute()
            logger.info("Database connection verified for baseline measurement")
        except Exception as e:
            logger.warning(f"Database connection issues during baseline: {e}")

    async def _measure_database_baseline(self):
        """Measure database operation baseline performance."""
        logger.info("Measuring database operation baseline...")

        # Connection establishment timing
        connection_times = []
        for i in range(10):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').limit(1).execute()
                connection_times.append((time.perf_counter() - start_time) * 1000)
            except Exception as e:
                logger.error(f"Database connection test failed: {e}")

        if connection_times:
            self._add_baseline_metric(
                "database_connection_latency",
                connection_times,
                "ms",
                "Time to establish database connection and execute simple query"
            )

        # Batch insert performance baseline
        batch_sizes = [1, 10, 50]
        for batch_size in batch_sizes:
            insert_times = []
            timestamp = get_current_timestamp()

            for iteration in range(5):
                test_records = []
                for i in range(batch_size):
                    test_records.append({
                        'parameter_id': f'BASELINE_TEST_{iteration}_{i}',
                        'value': float(i * 1.1),
                        'set_point': float(i),
                        'timestamp': timestamp
                    })

                start_time = time.perf_counter()
                try:
                    supabase = get_supabase()
                    result = supabase.table('parameter_value_history').insert(test_records).execute()
                    insert_times.append((time.perf_counter() - start_time) * 1000)

                    # Track for cleanup
                    if result.data:
                        self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

                except Exception as e:
                    logger.error(f"Batch insert baseline failed for size {batch_size}: {e}")

            if insert_times:
                self._add_baseline_metric(
                    f"database_batch_insert_{batch_size}",
                    insert_times,
                    "ms",
                    f"Batch insert performance for {batch_size} records"
                )

        # Machine status query baseline
        status_times = []
        for i in range(20):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()
                status_times.append((time.perf_counter() - start_time) * 1000)
            except Exception as e:
                logger.error(f"Machine status query failed: {e}")

        if status_times:
            self._add_baseline_metric(
                "database_status_query",
                status_times,
                "ms",
                "Machine status query for dual-mode decision"
            )

    async def _measure_plc_baseline(self):
        """Measure PLC communication baseline performance."""
        logger.info("Measuring PLC communication baseline...")

        if not plc_manager.is_connected():
            logger.warning("PLC not connected - skipping PLC baseline measurements")
            return

        # Individual parameter read baseline
        if hasattr(plc_manager.plc, '_parameter_cache'):
            parameter_ids = list(plc_manager.plc._parameter_cache.keys())[:5]  # Test first 5
            individual_read_times = []

            for param_id in parameter_ids:
                for iteration in range(3):  # 3 reads per parameter
                    start_time = time.perf_counter()
                    try:
                        value = await plc_manager.read_parameter(param_id)
                        individual_read_times.append((time.perf_counter() - start_time) * 1000)
                    except Exception as e:
                        logger.error(f"Individual parameter read failed for {param_id}: {e}")

            if individual_read_times:
                self._add_baseline_metric(
                    "plc_individual_parameter_read",
                    individual_read_times,
                    "ms",
                    "Individual parameter read from PLC"
                )

        # Bulk parameter read baseline
        bulk_read_times = []
        for iteration in range(10):
            start_time = time.perf_counter()
            try:
                parameter_values = await plc_manager.read_all_parameters()
                read_time = (time.perf_counter() - start_time) * 1000
                bulk_read_times.append(read_time)

                if parameter_values:
                    param_count = len(parameter_values)
                    logger.debug(f"Bulk read baseline {iteration}: {read_time:.2f}ms for {param_count} parameters")

            except Exception as e:
                logger.error(f"Bulk parameter read baseline failed: {e}")

        if bulk_read_times:
            self._add_baseline_metric(
                "plc_bulk_parameter_read",
                bulk_read_times,
                "ms",
                "Bulk read of all parameters from PLC"
            )

    async def _measure_system_resource_baseline(self):
        """Measure system resource utilization baseline."""
        logger.info("Measuring system resource baseline...")

        memory_samples = []
        cpu_samples = []
        sample_count = self.duration // 2  # Sample every 2 seconds

        for i in range(sample_count):
            # Memory measurement
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)

            # CPU measurement
            cpu_percent = self.process.cpu_percent()
            cpu_samples.append(cpu_percent)

            await asyncio.sleep(2)

        if memory_samples:
            self._add_baseline_metric(
                "system_memory_usage",
                memory_samples,
                "MB",
                "Process memory usage during normal operation"
            )

        if cpu_samples:
            self._add_baseline_metric(
                "system_cpu_usage",
                cpu_samples,
                "percent",
                "Process CPU usage during normal operation"
            )

    async def _measure_logging_cycle_baseline(self):
        """Measure end-to-end logging cycle baseline performance."""
        logger.info("Measuring logging cycle baseline...")

        cycle_times = []
        cycle_count = min(10, self.duration // 10)  # 10 cycles or duration/10

        for iteration in range(cycle_count):
            start_time = time.perf_counter()

            try:
                # Simulate complete logging cycle
                # 1. Check machine status (dual-mode decision)
                supabase = get_supabase()
                status_result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()

                process_id = None
                if status_result.data and status_result.data.get('status') == 'processing':
                    process_id = status_result.data.get('current_process_id')

                # 2. Read parameters from PLC (if connected)
                parameter_values = {}
                if plc_manager.is_connected():
                    try:
                        parameter_values = await plc_manager.read_all_parameters()
                    except Exception as e:
                        logger.debug(f"PLC read failed in cycle baseline: {e}")

                # 3. Prepare and insert data
                if parameter_values:
                    timestamp = get_current_timestamp()
                    history_records = []

                    # Limit to 5 parameters for baseline test
                    limited_params = dict(list(parameter_values.items())[:5])

                    for param_id, value in limited_params.items():
                        if value is not None:
                            history_records.append({
                                'parameter_id': param_id,
                                'value': value,
                                'set_point': None,
                                'timestamp': timestamp
                            })

                    if history_records:
                        result = supabase.table('parameter_value_history').insert(history_records).execute()

                        # Track for cleanup
                        if result.data:
                            self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

                cycle_time = (time.perf_counter() - start_time) * 1000
                cycle_times.append(cycle_time)

            except Exception as e:
                logger.error(f"Logging cycle baseline failed: {e}")

            # Wait before next cycle
            await asyncio.sleep(1)

        if cycle_times:
            self._add_baseline_metric(
                "end_to_end_logging_cycle",
                cycle_times,
                "ms",
                "Complete logging cycle from status check to data insertion"
            )

    async def _measure_dual_mode_baseline(self):
        """Measure dual-mode logging overhead baseline."""
        logger.info("Measuring dual-mode logging baseline...")

        # Single table insert timing
        single_times = []
        dual_times = []

        timestamp = get_current_timestamp()
        test_record = {
            'parameter_id': 'DUAL_MODE_BASELINE_TEST',
            'value': 123.45,
            'set_point': 100.0,
            'timestamp': timestamp
        }

        process_record = {
            'process_id': 'BASELINE_PROCESS_ID',
            'parameter_id': 'DUAL_MODE_BASELINE_TEST',
            'value': 123.45,
            'set_point': 100.0,
            'timestamp': timestamp
        }

        # Measure single table inserts
        for i in range(10):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('parameter_value_history').insert([test_record]).execute()
                single_times.append((time.perf_counter() - start_time) * 1000)

                # Track for cleanup
                if result.data:
                    self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

            except Exception as e:
                logger.error(f"Single table baseline failed: {e}")

        # Measure dual table inserts
        for i in range(10):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                # Insert to both tables
                result1 = supabase.table('parameter_value_history').insert([test_record]).execute()
                result2 = supabase.table('process_data_points').insert([process_record]).execute()
                dual_times.append((time.perf_counter() - start_time) * 1000)

                # Track for cleanup
                if result1.data:
                    self.test_data_cleanup.extend([r['id'] for r in result1.data if 'id' in r])

            except Exception as e:
                logger.error(f"Dual table baseline failed: {e}")

        if single_times:
            self._add_baseline_metric(
                "single_table_insert",
                single_times,
                "ms",
                "Single table insert (idle mode baseline)"
            )

        if dual_times:
            self._add_baseline_metric(
                "dual_table_insert",
                dual_times,
                "ms",
                "Dual table insert (process mode baseline)"
            )

        # Calculate overhead
        if single_times and dual_times:
            single_avg = statistics.mean(single_times)
            dual_avg = statistics.mean(dual_times)
            overhead_percent = ((dual_avg - single_avg) / single_avg) * 100 if single_avg > 0 else 0

            self._add_baseline_metric(
                "dual_mode_overhead",
                [overhead_percent],
                "percent",
                "Dual-mode logging overhead vs single-mode"
            )

    def _add_baseline_metric(self, name: str, values: List[float], unit: str, notes: str = ""):
        """Add a baseline metric to the results."""
        if not values:
            return

        metric = BaselineMetric(
            name=name,
            value=statistics.mean(values),
            unit=unit,
            samples=len(values),
            std_dev=statistics.stdev(values) if len(values) > 1 else 0.0,
            min_value=min(values),
            max_value=max(values),
            timestamp=datetime.now(),
            notes=notes
        )

        self.baseline_metrics.append(metric)
        logger.info(f"Baseline metric '{name}': {metric.value:.2f}{unit} (±{metric.std_dev:.2f}, n={metric.samples})")

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for baseline context."""
        return {
            'python_version': sys.version.split()[0],
            'platform': sys.platform,
            'cpu_count': psutil.cpu_count(),
            'total_memory_mb': psutil.virtual_memory().total / 1024 / 1024,
            'available_memory_mb': psutil.virtual_memory().available / 1024 / 1024,
            'plc_connected': plc_manager.is_connected(),
            'machine_id': MACHINE_ID
        }

    async def _cleanup(self):
        """Clean up test data created during baseline measurement."""
        if not self.test_data_cleanup:
            return

        logger.info(f"Cleaning up {len(self.test_data_cleanup)} baseline test records")

        try:
            supabase = get_supabase()
            # Delete in batches
            batch_size = 50
            for i in range(0, len(self.test_data_cleanup), batch_size):
                batch_ids = self.test_data_cleanup[i:i+batch_size]
                supabase.table('parameter_value_history').delete().in_('id', batch_ids).execute()

        except Exception as e:
            logger.error(f"Failed to cleanup baseline test data: {e}")

    def generate_baseline_report(self, baseline_data: Dict[str, Any]) -> str:
        """Generate a human-readable baseline report."""
        report = []
        report.append("=" * 80)
        report.append("CONTINUOUS PARAMETER LOGGING SYSTEM - BASELINE PERFORMANCE REPORT")
        report.append("=" * 80)
        report.append(f"Measurement Period: {baseline_data['measurement_start']} to {baseline_data['measurement_end']}")
        report.append(f"Duration: {baseline_data['actual_duration_seconds']:.1f} seconds")
        report.append("")

        # System Information
        system_info = baseline_data['system_info']
        report.append("SYSTEM CONFIGURATION")
        report.append("-" * 30)
        report.append(f"Python Version: {system_info['python_version']}")
        report.append(f"Platform: {system_info['platform']}")
        report.append(f"CPU Cores: {system_info['cpu_count']}")
        report.append(f"Total Memory: {system_info['total_memory_mb']:.0f} MB")
        report.append(f"Available Memory: {system_info['available_memory_mb']:.0f} MB")
        report.append(f"PLC Connected: {system_info['plc_connected']}")
        report.append(f"Machine ID: {system_info['machine_id']}")
        report.append("")

        # Performance Baselines
        report.append("PERFORMANCE BASELINES")
        report.append("-" * 40)

        # Organize metrics by category
        categories = {
            'Database Operations': [],
            'PLC Communication': [],
            'System Resources': [],
            'Integration': [],
            'Dual-Mode': []
        }

        for metric_data in baseline_data['baseline_metrics']:
            metric_name = metric_data['name']

            if 'database' in metric_name:
                categories['Database Operations'].append(metric_data)
            elif 'plc' in metric_name:
                categories['PLC Communication'].append(metric_data)
            elif 'system' in metric_name:
                categories['System Resources'].append(metric_data)
            elif 'cycle' in metric_name:
                categories['Integration'].append(metric_data)
            elif 'dual' in metric_name or 'single' in metric_name:
                categories['Dual-Mode'].append(metric_data)

        for category, metrics in categories.items():
            if metrics:
                report.append(f"\n{category}:")
                for metric in metrics:
                    report.append(f"  {metric['name']}:")
                    report.append(f"    Average: {metric['value']:.2f} {metric['unit']}")
                    report.append(f"    Range: {metric['min_value']:.2f} - {metric['max_value']:.2f} {metric['unit']}")
                    report.append(f"    Std Dev: ±{metric['std_dev']:.2f} {metric['unit']}")
                    report.append(f"    Samples: {metric['samples']}")
                    if metric['notes']:
                        report.append(f"    Notes: {metric['notes']}")
                    report.append("")

        # Performance Analysis
        report.append("BASELINE ANALYSIS")
        report.append("-" * 30)

        # Find critical metrics
        critical_issues = []
        performance_notes = []

        for metric_data in baseline_data['baseline_metrics']:
            name = metric_data['name']
            value = metric_data['value']
            unit = metric_data['unit']

            # Check for performance issues
            if name == 'end_to_end_logging_cycle' and value > 1000:
                critical_issues.append(f"❌ End-to-end cycle ({value:.1f}ms) exceeds 1-second logging window")
            elif name == 'end_to_end_logging_cycle' and value > 500:
                performance_notes.append(f"⚠️  End-to-end cycle ({value:.1f}ms) approaching 1-second limit")

            if 'database' in name and value > 500:
                performance_notes.append(f"⚠️  Database operation '{name}' is slow ({value:.1f}ms)")

            if 'memory' in name and value > 1000:
                performance_notes.append(f"⚠️  High memory usage: {value:.1f}MB")

        if critical_issues:
            report.append("Critical Performance Issues:")
            for issue in critical_issues:
                report.append(f"  {issue}")
            report.append("")

        if performance_notes:
            report.append("Performance Observations:")
            for note in performance_notes:
                report.append(f"  {note}")
            report.append("")

        # Recommendations
        report.append("BASELINE-DRIVEN RECOMMENDATIONS")
        report.append("-" * 40)
        recommendations = [
            "1. Use this baseline as reference for optimization validation",
            "2. Monitor key metrics: end-to-end cycle time, database latency, memory usage",
            "3. Target <500ms for end-to-end logging cycle to maintain 1-second intervals",
            "4. Implement connection pooling if database latency >100ms",
            "5. Add bulk operations if PLC read time >200ms",
            "6. Monitor memory growth during extended operation",
            "7. Re-run baseline after implementing optimizations"
        ]

        for rec in recommendations:
            report.append(rec)

        report.append("")
        report.append("=" * 80)
        report.append("End of Baseline Report")

        return "\n".join(report)


async def main():
    """Main baseline measurement execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Establish Performance Baseline for Continuous Parameter Logging')
    parser.add_argument('--duration', type=int, default=120,
                       help='Measurement duration in seconds (default: 120)')
    parser.add_argument('--output', help='Output file for baseline results (JSON format)')
    parser.add_argument('--report', help='Output file for human-readable report')

    args = parser.parse_args()

    baseline_tool = BaselinePerformanceMeasurement(args.duration)

    try:
        baseline_data = await baseline_tool.establish_baseline()

        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                # Convert datetime objects to strings for JSON serialization
                json_data = json.loads(json.dumps(baseline_data, default=str))
                json.dump(json_data, f, indent=2)
            logger.info(f"Baseline results saved to {args.output}")

        # Generate and output report
        report = baseline_tool.generate_baseline_report(baseline_data)

        if args.report:
            with open(args.report, 'w') as f:
                f.write(report)
            logger.info(f"Baseline report saved to {args.report}")
        else:
            print(report)

        # Log summary
        metric_count = len(baseline_data['baseline_metrics'])
        logger.info(f"Baseline measurement completed: {metric_count} metrics established")

        return baseline_data

    except Exception as e:
        logger.error(f"Baseline measurement failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())