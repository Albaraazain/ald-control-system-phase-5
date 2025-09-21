#!/usr/bin/env python3
"""
Focused Performance Benchmark for Component Parameters Synchronization

This script provides targeted performance benchmarks specifically for the new
component_parameters.current_value synchronization feature, measuring:

1. Baseline vs Enhanced Performance
2. Bulk Update Efficiency
3. Transaction Overhead Analysis
4. Concurrent Operation Impact
5. Database Load Simulation

Quick benchmark for immediate feedback during development.
"""

import asyncio
import time
import statistics
import psutil
import uuid
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
import json

from src.log_setup import logger
from src.db import get_supabase
from src.data_collection.transactional.interfaces import ParameterData, MachineState
from src.data_collection.transactional.dual_mode_repository import dual_mode_repository


class SynchronizationPerformanceBenchmark:
    """Quick performance benchmark for synchronization features."""

    def __init__(self):
        """Initialize the benchmark."""
        self.results = {}

    async def run_quick_benchmark(self, parameter_count: int = 84, duration_seconds: int = 30) -> Dict[str, Any]:
        """
        Run a quick performance benchmark comparing before/after synchronization.

        Args:
            parameter_count: Number of parameters to simulate (default: 84, current system spec)
            duration_seconds: How long to run each test (default: 30 seconds)

        Returns:
            Dict with benchmark results and analysis
        """
        logger.info(f"🚀 Starting Quick Synchronization Performance Benchmark")
        logger.info(f"Parameters: {parameter_count}, Duration: {duration_seconds}s")

        start_time = time.time()

        try:
            # 1. Baseline Performance (history-only)
            logger.info("📊 Phase 1: Baseline Performance (History Only)")
            baseline_metrics = await self._benchmark_history_only(parameter_count, duration_seconds)

            # 2. Enhanced Performance (with synchronization)
            logger.info("🔄 Phase 2: Enhanced Performance (With Synchronization)")
            enhanced_metrics = await self._benchmark_with_synchronization(parameter_count, duration_seconds)

            # 3. Bulk Update Efficiency Test
            logger.info("💪 Phase 3: Bulk Update Efficiency Analysis")
            bulk_efficiency = await self._benchmark_bulk_update_efficiency()

            # 4. Quick Concurrent Test
            logger.info("🔀 Phase 4: Concurrent Operations Test")
            concurrent_metrics = await self._benchmark_concurrent_operations(parameter_count, 15)

            # Calculate performance impact
            performance_impact = self._calculate_impact(baseline_metrics, enhanced_metrics)

            total_duration = time.time() - start_time

            results = {
                'benchmark_summary': {
                    'total_duration_seconds': total_duration,
                    'parameter_count': parameter_count,
                    'test_duration_seconds': duration_seconds,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                'baseline_performance': baseline_metrics,
                'enhanced_performance': enhanced_metrics,
                'bulk_update_efficiency': bulk_efficiency,
                'concurrent_performance': concurrent_metrics,
                'performance_impact': performance_impact,
                'recommendations': self._generate_quick_recommendations(performance_impact)
            }

            self.results = results

            # Print quick summary
            self._print_quick_summary(results)

            return results

        except Exception as e:
            logger.error(f"❌ Benchmark failed: {e}", exc_info=True)
            raise
        finally:
            await self._cleanup_test_data()

    async def _benchmark_history_only(self, parameter_count: int, duration_seconds: int) -> Dict[str, Any]:
        """Benchmark the baseline history-only performance."""

        logger.info("Testing baseline performance (history-only logging)")

        parameters = self._generate_test_parameters(parameter_count)

        operations_completed = 0
        latencies = []
        error_count = 0

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        start_time = time.time()
        end_time = start_time + duration_seconds

        while time.time() < end_time:
            operation_start = time.time()

            try:
                # Use history-only mode (baseline)
                batch = parameters[:50]  # Standard batch size
                result_count = await dual_mode_repository.insert_history_only(batch)

                operations_completed += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Baseline operation failed: {e}")

            operation_end = time.time()
            latency_ms = (operation_end - operation_start) * 1000
            latencies.append(latency_ms)

        total_duration = time.time() - start_time
        current_memory = process.memory_info().rss / 1024 / 1024

        return {
            'operations_completed': operations_completed,
            'operations_per_second': operations_completed / total_duration,
            'avg_latency_ms': statistics.mean(latencies) if latencies else 0,
            'p95_latency_ms': statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else 0,
            'error_count': error_count,
            'success_rate': (operations_completed - error_count) / operations_completed if operations_completed > 0 else 0,
            'memory_usage_mb': current_memory,
            'memory_increase_mb': current_memory - initial_memory
        }

    async def _benchmark_with_synchronization(self, parameter_count: int, duration_seconds: int) -> Dict[str, Any]:
        """Benchmark the enhanced performance with synchronization."""

        logger.info("Testing enhanced performance (with component_parameters synchronization)")

        parameters = self._generate_test_parameters(parameter_count)

        operations_completed = 0
        latencies = []
        error_count = 0
        total_component_updates = 0

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        start_time = time.time()
        end_time = start_time + duration_seconds

        while time.time() < end_time:
            operation_start = time.time()

            try:
                # Create machine state for processing mode
                machine_state = MachineState(
                    is_processing=True,
                    current_process_id=str(uuid.uuid4())
                )

                # Use enhanced dual-mode with synchronization
                batch = parameters[:50]  # Standard batch size
                result = await dual_mode_repository.insert_dual_mode_atomic(batch, machine_state)

                if result.success:
                    operations_completed += 1
                    total_component_updates += result.component_updates_count
                else:
                    error_count += 1
                    logger.warning(f"Enhanced operation failed: {result.error_message}")

            except Exception as e:
                error_count += 1
                logger.error(f"Enhanced operation failed: {e}")

            operation_end = time.time()
            latency_ms = (operation_end - operation_start) * 1000
            latencies.append(latency_ms)

        total_duration = time.time() - start_time
        current_memory = process.memory_info().rss / 1024 / 1024

        return {
            'operations_completed': operations_completed,
            'operations_per_second': operations_completed / total_duration,
            'avg_latency_ms': statistics.mean(latencies) if latencies else 0,
            'p95_latency_ms': statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else 0,
            'error_count': error_count,
            'success_rate': (operations_completed - error_count) / operations_completed if operations_completed > 0 else 0,
            'memory_usage_mb': current_memory,
            'memory_increase_mb': current_memory - initial_memory,
            'total_component_updates': total_component_updates,
            'avg_component_updates_per_operation': total_component_updates / operations_completed if operations_completed > 0 else 0
        }

    async def _benchmark_bulk_update_efficiency(self) -> Dict[str, Any]:
        """Test the efficiency of bulk update operations."""

        logger.info("Testing bulk update efficiency")

        batch_sizes = [10, 25, 50, 100, 200]
        results = []

        for batch_size in batch_sizes:
            logger.info(f"Testing batch size: {batch_size}")

            parameters = self._generate_test_parameters(batch_size)
            machine_state = MachineState(
                is_processing=True,
                current_process_id=str(uuid.uuid4())
            )

            # Run 5 iterations for each batch size
            latencies = []
            for i in range(5):
                start_time = time.time()

                try:
                    result = await dual_mode_repository.insert_dual_mode_atomic(parameters, machine_state)

                    duration_ms = (time.time() - start_time) * 1000
                    latencies.append(duration_ms)

                    if not result.success:
                        logger.warning(f"Batch operation failed: {result.error_message}")

                except Exception as e:
                    logger.error(f"Batch test failed: {e}")

            if latencies:
                avg_latency = statistics.mean(latencies)
                throughput = batch_size / (avg_latency / 1000)  # parameters per second

                results.append({
                    'batch_size': batch_size,
                    'avg_latency_ms': avg_latency,
                    'throughput_parameters_per_second': throughput,
                    'efficiency_ratio': throughput / batch_size  # efficiency per parameter
                })

        # Find optimal batch size
        if results:
            optimal_batch = max(results, key=lambda x: x['efficiency_ratio'])

            return {
                'batch_size_analysis': results,
                'optimal_batch_size': optimal_batch['batch_size'],
                'optimal_efficiency_ratio': optimal_batch['efficiency_ratio'],
                'recommendations': self._analyze_batch_efficiency(results)
            }
        else:
            return {'error': 'No successful batch operations'}

    async def _benchmark_concurrent_operations(self, parameter_count: int, duration_seconds: int) -> Dict[str, Any]:
        """Test performance under concurrent load."""

        logger.info("Testing concurrent operation performance")

        async def concurrent_task(task_id: int) -> Dict[str, Any]:
            parameters = self._generate_test_parameters(parameter_count)
            machine_state = MachineState(
                is_processing=True,
                current_process_id=f"concurrent_test_{task_id}"
            )

            operations = 0
            errors = 0
            start_time = time.time()
            end_time = start_time + duration_seconds

            while time.time() < end_time:
                try:
                    batch = parameters[:50]
                    result = await dual_mode_repository.insert_dual_mode_atomic(batch, machine_state)

                    if result.success:
                        operations += 1
                    else:
                        errors += 1

                except Exception as e:
                    errors += 1

            total_duration = time.time() - start_time

            return {
                'task_id': task_id,
                'operations': operations,
                'errors': errors,
                'duration': total_duration,
                'ops_per_second': operations / total_duration if total_duration > 0 else 0
            }

        # Run 3 concurrent tasks
        tasks = [concurrent_task(i) for i in range(3)]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_tasks = [r for r in task_results if isinstance(r, dict)]

        if successful_tasks:
            total_operations = sum(r['operations'] for r in successful_tasks)
            total_errors = sum(r['errors'] for r in successful_tasks)
            avg_ops_per_second = statistics.mean([r['ops_per_second'] for r in successful_tasks])

            return {
                'concurrent_tasks': len(successful_tasks),
                'total_operations': total_operations,
                'total_errors': total_errors,
                'avg_ops_per_second': avg_ops_per_second,
                'success_rate': total_operations / (total_operations + total_errors) if (total_operations + total_errors) > 0 else 0,
                'task_results': successful_tasks
            }
        else:
            return {'error': 'All concurrent tasks failed'}

    def _calculate_impact(self, baseline: Dict[str, Any], enhanced: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate the performance impact of synchronization."""

        if not baseline or not enhanced:
            return {'error': 'Missing baseline or enhanced metrics'}

        throughput_impact = ((enhanced['operations_per_second'] - baseline['operations_per_second'])
                           / baseline['operations_per_second'] * 100)

        latency_impact = ((enhanced['avg_latency_ms'] - baseline['avg_latency_ms'])
                         / baseline['avg_latency_ms'] * 100)

        memory_impact = ((enhanced['memory_increase_mb'] - baseline['memory_increase_mb'])
                        / baseline['memory_increase_mb'] * 100) if baseline['memory_increase_mb'] > 0 else 0

        return {
            'throughput_change_percent': throughput_impact,
            'latency_change_percent': latency_impact,
            'memory_change_percent': memory_impact,
            'component_updates_per_operation': enhanced.get('avg_component_updates_per_operation', 0),
            'performance_acceptable': abs(throughput_impact) < 25 and abs(latency_impact) < 40,
            'impact_severity': self._classify_impact_severity(throughput_impact, latency_impact)
        }

    def _classify_impact_severity(self, throughput_impact: float, latency_impact: float) -> str:
        """Classify the severity of performance impact."""

        if abs(throughput_impact) < 10 and abs(latency_impact) < 15:
            return "LOW"
        elif abs(throughput_impact) < 25 and abs(latency_impact) < 40:
            return "MEDIUM"
        else:
            return "HIGH"

    def _analyze_batch_efficiency(self, results: List[Dict[str, Any]]) -> List[str]:
        """Analyze batch efficiency results and provide recommendations."""

        recommendations = []

        if len(results) < 2:
            return ["Insufficient data for batch efficiency analysis"]

        # Find efficiency trends
        max_efficiency = max(r['efficiency_ratio'] for r in results)
        min_efficiency = min(r['efficiency_ratio'] for r in results)

        if max_efficiency / min_efficiency > 2.0:
            recommendations.append("Significant efficiency variation detected across batch sizes")

        # Check for sweet spot
        sorted_by_efficiency = sorted(results, key=lambda x: x['efficiency_ratio'], reverse=True)
        top_performers = sorted_by_efficiency[:2]

        if len(top_performers) >= 2:
            recommendations.append(
                f"Top performing batch sizes: {top_performers[0]['batch_size']} and {top_performers[1]['batch_size']}"
            )

        # Memory vs performance trade-off
        large_batches = [r for r in results if r['batch_size'] >= 100]
        if large_batches:
            avg_large_efficiency = statistics.mean([r['efficiency_ratio'] for r in large_batches])
            small_batches = [r for r in results if r['batch_size'] < 100]
            if small_batches:
                avg_small_efficiency = statistics.mean([r['efficiency_ratio'] for r in small_batches])

                if avg_large_efficiency > avg_small_efficiency * 1.2:
                    recommendations.append("Large batches show significantly better efficiency")
                elif avg_small_efficiency > avg_large_efficiency * 1.2:
                    recommendations.append("Smaller batches are more efficient - consider memory constraints")

        return recommendations

    def _generate_quick_recommendations(self, impact: Dict[str, Any]) -> List[str]:
        """Generate quick recommendations based on performance impact."""

        recommendations = []

        if 'error' in impact:
            recommendations.append("Performance analysis failed - investigate test setup")
            return recommendations

        severity = impact.get('impact_severity', 'UNKNOWN')
        throughput_change = impact.get('throughput_change_percent', 0)
        latency_change = impact.get('latency_change_percent', 0)

        if severity == "LOW":
            recommendations.append("✅ Performance impact is minimal - synchronization can be deployed")
        elif severity == "MEDIUM":
            recommendations.append("⚠️ Moderate performance impact detected - consider optimization")
        else:
            recommendations.append("🚨 High performance impact - optimization required before deployment")

        if throughput_change < -20:
            recommendations.append(f"Significant throughput reduction ({throughput_change:.1f}%) - investigate bulk update efficiency")

        if latency_change > 50:
            recommendations.append(f"High latency increase ({latency_change:.1f}%) - consider connection pooling or async optimization")

        if impact.get('component_updates_per_operation', 0) > 0:
            recommendations.append(f"Component parameters are being updated ({impact['component_updates_per_operation']:.1f} per operation)")

        # General recommendations
        recommendations.extend([
            "Monitor transaction log growth in production",
            "Consider implementing parameter update batching",
            "Set up performance alerts for ops/second degradation"
        ])

        return recommendations

    def _generate_test_parameters(self, count: int) -> List[ParameterData]:
        """Generate test parameter data."""

        import random

        parameters = []
        for i in range(count):
            param = ParameterData(
                parameter_id=f"benchmark_param_{i:03d}",
                value=round(random.uniform(0, 100), 2),
                set_point=round(random.uniform(0, 100), 2),
                timestamp=datetime.now(timezone.utc)
            )
            parameters.append(param)

        return parameters

    def _print_quick_summary(self, results: Dict[str, Any]):
        """Print a quick summary of benchmark results."""

        print("\n" + "="*60)
        print("🎯 SYNCHRONIZATION PERFORMANCE BENCHMARK SUMMARY")
        print("="*60)

        baseline = results.get('baseline_performance', {})
        enhanced = results.get('enhanced_performance', {})
        impact = results.get('performance_impact', {})

        if baseline and enhanced:
            print(f"Baseline Throughput:  {baseline.get('operations_per_second', 0):.2f} ops/sec")
            print(f"Enhanced Throughput:  {enhanced.get('operations_per_second', 0):.2f} ops/sec")
            print(f"Throughput Impact:    {impact.get('throughput_change_percent', 0):+.1f}%")

            print(f"\nBaseline Latency:     {baseline.get('avg_latency_ms', 0):.2f} ms")
            print(f"Enhanced Latency:     {enhanced.get('avg_latency_ms', 0):.2f} ms")
            print(f"Latency Impact:       {impact.get('latency_change_percent', 0):+.1f}%")

            print(f"\nComponent Updates:    {enhanced.get('avg_component_updates_per_operation', 0):.1f} per operation")
            print(f"Impact Severity:      {impact.get('impact_severity', 'UNKNOWN')}")

        bulk_analysis = results.get('bulk_update_efficiency', {})
        if bulk_analysis and 'optimal_batch_size' in bulk_analysis:
            print(f"\nOptimal Batch Size:   {bulk_analysis['optimal_batch_size']}")

        concurrent = results.get('concurrent_performance', {})
        if concurrent:
            print(f"Concurrent Performance: {concurrent.get('avg_ops_per_second', 0):.2f} ops/sec (3 tasks)")

        recommendations = results.get('recommendations', [])
        if recommendations:
            print(f"\n📋 KEY RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations[:3], 1):  # Show top 3
                print(f"  {i}. {rec}")

        print("="*60)

    async def _cleanup_test_data(self):
        """Clean up benchmark test data."""

        try:
            logger.info("Cleaning up benchmark test data")

            supabase = get_supabase()

            # Clean up test records
            supabase.table('parameter_value_history').delete().like(
                'parameter_id', 'benchmark_param_%'
            ).execute()

            supabase.table('process_data_points').delete().like(
                'parameter_id', 'benchmark_param_%'
            ).execute()

            logger.info("Benchmark test data cleanup completed")

        except Exception as e:
            logger.error(f"Benchmark cleanup failed: {e}")


async def main():
    """Main function to run the quick benchmark."""

    import argparse

    parser = argparse.ArgumentParser(description="Quick performance benchmark for parameter synchronization")
    parser.add_argument('--parameters', type=int, default=84, help='Number of parameters to simulate (default: 84)')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds (default: 30)')
    parser.add_argument('--output', type=str, help='Output file for results (optional)')

    args = parser.parse_args()

    benchmark = SynchronizationPerformanceBenchmark()

    try:
        results = await benchmark.run_quick_benchmark(
            parameter_count=args.parameters,
            duration_seconds=args.duration
        )

        # Save results if output file specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to: {args.output}")

        return results

    except Exception as e:
        logger.error(f"Benchmark failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())