#!/usr/bin/env python3
"""
Optimization Validation Tool for Continuous Parameter Logging System

This tool validates performance improvements by comparing current performance
against established baselines and measuring the impact of specific optimizations.

Validation Areas:
1. Performance regression detection
2. Optimization impact measurement
3. Scalability improvement validation
4. Resource efficiency improvements
5. Error handling optimization validation

Usage:
    python optimization_validation_tool.py --baseline baseline_results.json
    python optimization_validation_tool.py --baseline baseline_results.json --test-optimization connection_pooling
    python optimization_validation_tool.py --compare-before before.json --compare-after after.json
"""

import asyncio
import json
import time
import statistics
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Import baseline measurement tool
from baseline_performance_measurement import BaselinePerformanceMeasurement, BaselineMetric
from src.log_setup import logger


@dataclass
class OptimizationResult:
    """Result of optimization validation."""
    optimization_name: str
    metric_name: str
    baseline_value: float
    current_value: float
    improvement_percent: float
    improvement_absolute: float
    unit: str
    validation_status: str  # 'improved', 'degraded', 'no_change'
    notes: str = ""


@dataclass
class ValidationSummary:
    """Summary of validation results."""
    total_metrics: int
    improved_metrics: int
    degraded_metrics: int
    unchanged_metrics: int
    critical_regressions: List[str]
    significant_improvements: List[str]
    overall_assessment: str


class OptimizationValidationTool:
    """Tool for validating performance optimizations."""

    def __init__(self, baseline_file: Optional[str] = None):
        """
        Initialize optimization validation tool.

        Args:
            baseline_file: Path to baseline results JSON file
        """
        self.baseline_data = None
        self.baseline_metrics = {}

        if baseline_file:
            self.load_baseline(baseline_file)

    def load_baseline(self, baseline_file: str):
        """Load baseline data from file."""
        try:
            with open(baseline_file, 'r') as f:
                self.baseline_data = json.load(f)

            # Create lookup dictionary for baseline metrics
            for metric_data in self.baseline_data.get('baseline_metrics', []):
                self.baseline_metrics[metric_data['name']] = metric_data

            logger.info(f"Loaded baseline with {len(self.baseline_metrics)} metrics from {baseline_file}")

        except Exception as e:
            logger.error(f"Failed to load baseline from {baseline_file}: {e}")
            raise

    async def validate_current_performance(self, measurement_duration: int = 60) -> Dict[str, Any]:
        """
        Validate current performance against baseline.

        Args:
            measurement_duration: Duration for current performance measurement

        Returns:
            Validation results including comparisons and assessments
        """
        if not self.baseline_data:
            raise ValueError("No baseline data loaded. Use load_baseline() first.")

        logger.info("Measuring current performance for optimization validation...")

        # Measure current performance
        baseline_tool = BaselinePerformanceMeasurement(measurement_duration)
        current_data = await baseline_tool.establish_baseline()

        # Compare against baseline
        validation_results = self._compare_performance(
            self.baseline_data,
            current_data,
            "Current vs Baseline"
        )

        return validation_results

    async def validate_optimization(self, optimization_name: str, test_duration: int = 60) -> Dict[str, Any]:
        """
        Validate a specific optimization by comparing before/after performance.

        Args:
            optimization_name: Name of the optimization being tested
            test_duration: Duration for performance measurement

        Returns:
            Optimization validation results
        """
        logger.info(f"Validating optimization: {optimization_name}")

        # Get current performance as "after" optimization
        baseline_tool = BaselinePerformanceMeasurement(test_duration)
        after_data = await baseline_tool.establish_baseline()

        # Compare against baseline as "before"
        if not self.baseline_data:
            logger.warning("No baseline loaded - measuring new baseline as 'before' state")
            # Use current measurement as both baseline and comparison
            before_data = after_data
        else:
            before_data = self.baseline_data

        validation_results = self._compare_performance(
            before_data,
            after_data,
            optimization_name
        )

        return validation_results

    def compare_performance_files(self, before_file: str, after_file: str, comparison_name: str = "Optimization") -> Dict[str, Any]:
        """
        Compare performance between two measurement files.

        Args:
            before_file: Path to "before" performance data
            after_file: Path to "after" performance data
            comparison_name: Name for this comparison

        Returns:
            Comparison results
        """
        try:
            with open(before_file, 'r') as f:
                before_data = json.load(f)

            with open(after_file, 'r') as f:
                after_data = json.load(f)

            return self._compare_performance(before_data, after_data, comparison_name)

        except Exception as e:
            logger.error(f"Failed to compare performance files: {e}")
            raise

    def _compare_performance(self, before_data: Dict[str, Any], after_data: Dict[str, Any], comparison_name: str) -> Dict[str, Any]:
        """
        Compare performance between two datasets.

        Args:
            before_data: Before optimization performance data
            after_data: After optimization performance data
            comparison_name: Name for this comparison

        Returns:
            Detailed comparison results
        """
        # Create metric lookups
        before_metrics = {}
        for metric_data in before_data.get('baseline_metrics', []):
            before_metrics[metric_data['name']] = metric_data

        after_metrics = {}
        for metric_data in after_data.get('baseline_metrics', []):
            after_metrics[metric_data['name']] = metric_data

        # Compare metrics
        optimization_results = []
        critical_regressions = []
        significant_improvements = []

        for metric_name in before_metrics:
            if metric_name not in after_metrics:
                logger.warning(f"Metric {metric_name} missing in after measurement")
                continue

            before_metric = before_metrics[metric_name]
            after_metric = after_metrics[metric_name]

            result = self._compare_metric(before_metric, after_metric, comparison_name)
            optimization_results.append(result)

            # Track significant changes
            if result.validation_status == 'degraded' and abs(result.improvement_percent) > 20:
                critical_regressions.append(f"{metric_name}: {result.improvement_percent:.1f}% worse")

            if result.validation_status == 'improved' and result.improvement_percent > 20:
                significant_improvements.append(f"{metric_name}: {result.improvement_percent:.1f}% better")

        # Check for new metrics in after measurement
        new_metrics = []
        for metric_name in after_metrics:
            if metric_name not in before_metrics:
                new_metrics.append(metric_name)

        # Generate summary
        summary = self._generate_validation_summary(optimization_results, critical_regressions, significant_improvements)

        return {
            'comparison_name': comparison_name,
            'comparison_timestamp': datetime.now().isoformat(),
            'before_measurement': before_data.get('measurement_start', 'unknown'),
            'after_measurement': after_data.get('measurement_start', 'unknown'),
            'optimization_results': [asdict(result) for result in optimization_results],
            'new_metrics': new_metrics,
            'validation_summary': asdict(summary),
            'recommendations': self._generate_recommendations(summary, optimization_results)
        }

    def _compare_metric(self, before_metric: Dict[str, Any], after_metric: Dict[str, Any], optimization_name: str) -> OptimizationResult:
        """Compare a single metric between before and after."""
        before_value = before_metric['value']
        after_value = after_metric['value']
        unit = before_metric['unit']

        # Calculate improvement
        improvement_absolute = before_value - after_value
        improvement_percent = (improvement_absolute / before_value) * 100 if before_value != 0 else 0

        # Determine validation status
        status = 'no_change'
        if abs(improvement_percent) > 5:  # 5% threshold for significance
            if improvement_percent > 0:
                status = 'improved'  # Lower values are better for time/latency metrics
            else:
                status = 'degraded'

            # For metrics where higher is better (like throughput), reverse the logic
            if any(term in before_metric['name'].lower() for term in ['throughput', 'rate', 'efficiency']):
                status = 'degraded' if improvement_percent > 0 else 'improved'

        # Generate notes
        notes = []
        if after_metric['std_dev'] > before_metric['std_dev'] * 1.5:
            notes.append("Increased variance - less consistent performance")
        elif after_metric['std_dev'] < before_metric['std_dev'] * 0.5:
            notes.append("Decreased variance - more consistent performance")

        if after_metric['max_value'] > before_metric['max_value'] * 1.5:
            notes.append("Increased maximum value")

        return OptimizationResult(
            optimization_name=optimization_name,
            metric_name=before_metric['name'],
            baseline_value=before_value,
            current_value=after_value,
            improvement_percent=improvement_percent,
            improvement_absolute=improvement_absolute,
            unit=unit,
            validation_status=status,
            notes="; ".join(notes)
        )

    def _generate_validation_summary(self, results: List[OptimizationResult],
                                   critical_regressions: List[str],
                                   significant_improvements: List[str]) -> ValidationSummary:
        """Generate summary of validation results."""
        total_metrics = len(results)
        improved_metrics = len([r for r in results if r.validation_status == 'improved'])
        degraded_metrics = len([r for r in results if r.validation_status == 'degraded'])
        unchanged_metrics = len([r for r in results if r.validation_status == 'no_change'])

        # Determine overall assessment
        if critical_regressions:
            overall_assessment = "CRITICAL_REGRESSION"
        elif degraded_metrics > improved_metrics:
            overall_assessment = "PERFORMANCE_DEGRADED"
        elif improved_metrics > degraded_metrics * 2:
            overall_assessment = "SIGNIFICANT_IMPROVEMENT"
        elif improved_metrics > degraded_metrics:
            overall_assessment = "MINOR_IMPROVEMENT"
        else:
            overall_assessment = "NO_SIGNIFICANT_CHANGE"

        return ValidationSummary(
            total_metrics=total_metrics,
            improved_metrics=improved_metrics,
            degraded_metrics=degraded_metrics,
            unchanged_metrics=unchanged_metrics,
            critical_regressions=critical_regressions,
            significant_improvements=significant_improvements,
            overall_assessment=overall_assessment
        )

    def _generate_recommendations(self, summary: ValidationSummary, results: List[OptimizationResult]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        if summary.overall_assessment == "CRITICAL_REGRESSION":
            recommendations.append("❌ CRITICAL: Revert changes immediately - significant performance regression detected")
            recommendations.append("🔍 Investigate root cause of performance degradation")

        elif summary.overall_assessment == "PERFORMANCE_DEGRADED":
            recommendations.append("⚠️  Performance degraded - review optimization implementation")
            recommendations.append("🔍 Profile specific degraded metrics for optimization opportunities")

        elif summary.overall_assessment == "SIGNIFICANT_IMPROVEMENT":
            recommendations.append("✅ Optimization successful - significant performance improvement achieved")
            recommendations.append("📊 Monitor performance in production to confirm sustained improvement")

        elif summary.overall_assessment == "MINOR_IMPROVEMENT":
            recommendations.append("✅ Minor performance improvement achieved")
            recommendations.append("🎯 Consider additional optimizations for greater impact")

        else:
            recommendations.append("ℹ️  No significant performance change detected")
            recommendations.append("🔍 Verify optimization was properly implemented and activated")

        # Specific metric recommendations
        high_impact_metrics = ['end_to_end_logging_cycle', 'database_batch_insert', 'plc_bulk_parameter_read']

        for result in results:
            if result.metric_name in high_impact_metrics:
                if result.validation_status == 'degraded':
                    recommendations.append(f"🚨 Critical metric '{result.metric_name}' degraded by {abs(result.improvement_percent):.1f}%")
                elif result.validation_status == 'improved' and result.improvement_percent > 30:
                    recommendations.append(f"🎉 Major improvement in '{result.metric_name}': {result.improvement_percent:.1f}% better")

        # General recommendations
        recommendations.extend([
            "📈 Continue monitoring these metrics in production",
            "🔄 Re-run validation after additional optimizations",
            "📋 Document successful optimization techniques for future use"
        ])

        return recommendations

    def generate_validation_report(self, validation_data: Dict[str, Any]) -> str:
        """Generate human-readable validation report."""
        report = []
        report.append("=" * 80)
        report.append("OPTIMIZATION VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Optimization: {validation_data['comparison_name']}")
        report.append(f"Validation Date: {validation_data['comparison_timestamp']}")
        report.append(f"Before Measurement: {validation_data['before_measurement']}")
        report.append(f"After Measurement: {validation_data['after_measurement']}")
        report.append("")

        # Summary
        summary = validation_data['validation_summary']
        report.append("VALIDATION SUMMARY")
        report.append("-" * 40)
        report.append(f"Overall Assessment: {summary['overall_assessment']}")
        report.append(f"Total Metrics: {summary['total_metrics']}")
        report.append(f"Improved: {summary['improved_metrics']}")
        report.append(f"Degraded: {summary['degraded_metrics']}")
        report.append(f"Unchanged: {summary['unchanged_metrics']}")
        report.append("")

        # Critical issues
        if summary['critical_regressions']:
            report.append("CRITICAL REGRESSIONS:")
            for regression in summary['critical_regressions']:
                report.append(f"  ❌ {regression}")
            report.append("")

        # Significant improvements
        if summary['significant_improvements']:
            report.append("SIGNIFICANT IMPROVEMENTS:")
            for improvement in summary['significant_improvements']:
                report.append(f"  ✅ {improvement}")
            report.append("")

        # Detailed results
        report.append("DETAILED METRIC COMPARISON")
        report.append("-" * 50)

        for result_data in validation_data['optimization_results']:
            status_icon = {
                'improved': '✅',
                'degraded': '❌',
                'no_change': '➖'
            }.get(result_data['validation_status'], '❓')

            report.append(f"\n{status_icon} {result_data['metric_name']}:")
            report.append(f"  Before: {result_data['baseline_value']:.2f} {result_data['unit']}")
            report.append(f"  After:  {result_data['current_value']:.2f} {result_data['unit']}")
            report.append(f"  Change: {result_data['improvement_percent']:+.1f}% ({result_data['improvement_absolute']:+.2f} {result_data['unit']})")

            if result_data['notes']:
                report.append(f"  Notes: {result_data['notes']}")

        # New metrics
        if validation_data['new_metrics']:
            report.append("\nNEW METRICS:")
            for metric in validation_data['new_metrics']:
                report.append(f"  📊 {metric}")

        # Recommendations
        report.append("\nRECOMMENDATIONS")
        report.append("-" * 30)
        for rec in validation_data['recommendations']:
            report.append(rec)

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    async def continuous_validation(self, measurement_interval: int = 300, duration: int = 3600):
        """
        Perform continuous validation over time to detect performance drift.

        Args:
            measurement_interval: Seconds between measurements
            duration: Total duration for continuous validation
        """
        logger.info(f"Starting continuous validation for {duration} seconds")

        measurements = []
        start_time = time.time()

        while time.time() - start_time < duration:
            try:
                # Take measurement
                baseline_tool = BaselinePerformanceMeasurement(60)  # 1-minute measurements
                measurement_data = await baseline_tool.establish_baseline()

                # Store with timestamp
                measurement_data['measurement_sequence'] = len(measurements)
                measurements.append(measurement_data)

                logger.info(f"Continuous validation measurement {len(measurements)} completed")

                # Compare with baseline if available
                if self.baseline_data and len(measurements) % 5 == 0:  # Every 5th measurement
                    validation = self._compare_performance(
                        self.baseline_data,
                        measurement_data,
                        f"Continuous_Validation_{len(measurements)}"
                    )

                    # Check for drift
                    summary = validation['validation_summary']
                    if summary['overall_assessment'] in ['CRITICAL_REGRESSION', 'PERFORMANCE_DEGRADED']:
                        logger.warning(f"Performance drift detected at measurement {len(measurements)}")

                # Wait for next interval
                await asyncio.sleep(measurement_interval)

            except Exception as e:
                logger.error(f"Continuous validation measurement failed: {e}")

        # Generate drift analysis
        return self._analyze_performance_drift(measurements)

    def _analyze_performance_drift(self, measurements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance drift across multiple measurements."""
        drift_analysis = {
            'total_measurements': len(measurements),
            'measurement_duration': measurements[-1]['measurement_start'] if measurements else None,
            'drift_metrics': {},
            'stability_assessment': 'STABLE'
        }

        if len(measurements) < 2:
            return drift_analysis

        # Analyze each metric for drift
        metric_names = set()
        for measurement in measurements:
            for metric in measurement.get('baseline_metrics', []):
                metric_names.add(metric['name'])

        for metric_name in metric_names:
            values = []
            timestamps = []

            for measurement in measurements:
                for metric in measurement.get('baseline_metrics', []):
                    if metric['name'] == metric_name:
                        values.append(metric['value'])
                        timestamps.append(measurement['measurement_start'])

            if len(values) >= 3:
                # Calculate drift statistics
                drift_stats = {
                    'initial_value': values[0],
                    'final_value': values[-1],
                    'drift_percent': ((values[-1] - values[0]) / values[0]) * 100 if values[0] != 0 else 0,
                    'coefficient_of_variation': (statistics.stdev(values) / statistics.mean(values)) * 100,
                    'trend': 'increasing' if values[-1] > values[0] else 'decreasing' if values[-1] < values[0] else 'stable'
                }

                drift_analysis['drift_metrics'][metric_name] = drift_stats

                # Check stability
                if abs(drift_stats['drift_percent']) > 50:
                    drift_analysis['stability_assessment'] = 'UNSTABLE'
                elif abs(drift_stats['drift_percent']) > 20:
                    drift_analysis['stability_assessment'] = 'MODERATE_DRIFT'

        return drift_analysis


async def main():
    """Main optimization validation execution."""
    parser = argparse.ArgumentParser(description='Optimization Validation Tool')
    parser.add_argument('--baseline', help='Baseline performance file (JSON)')
    parser.add_argument('--test-optimization', help='Test specific optimization')
    parser.add_argument('--compare-before', help='Before optimization file')
    parser.add_argument('--compare-after', help='After optimization file')
    parser.add_argument('--duration', type=int, default=60, help='Measurement duration (seconds)')
    parser.add_argument('--output', help='Output file for validation results')
    parser.add_argument('--report', help='Output file for validation report')
    parser.add_argument('--continuous', action='store_true', help='Run continuous validation')

    args = parser.parse_args()

    try:
        if args.compare_before and args.compare_after:
            # Compare two files
            tool = OptimizationValidationTool()
            validation_data = tool.compare_performance_files(
                args.compare_before,
                args.compare_after,
                "File_Comparison"
            )

        elif args.baseline and args.test_optimization:
            # Test specific optimization
            tool = OptimizationValidationTool(args.baseline)
            validation_data = await tool.validate_optimization(args.test_optimization, args.duration)

        elif args.baseline:
            # Validate current performance vs baseline
            tool = OptimizationValidationTool(args.baseline)

            if args.continuous:
                validation_data = await tool.continuous_validation()
            else:
                validation_data = await tool.validate_current_performance(args.duration)

        else:
            print("Error: Must specify --baseline or both --compare-before and --compare-after")
            sys.exit(1)

        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(validation_data, f, indent=2, default=str)
            logger.info(f"Validation results saved to {args.output}")

        # Generate and output report
        tool = OptimizationValidationTool()
        report = tool.generate_validation_report(validation_data)

        if args.report:
            with open(args.report, 'w') as f:
                f.write(report)
            logger.info(f"Validation report saved to {args.report}")
        else:
            print(report)

        # Log summary
        summary = validation_data.get('validation_summary', {})
        logger.info(f"Validation completed: {summary.get('overall_assessment', 'unknown')}")

    except Exception as e:
        logger.error(f"Optimization validation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())