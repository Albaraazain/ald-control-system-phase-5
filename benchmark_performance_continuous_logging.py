#!/usr/bin/env python3
"""
Comprehensive Performance Benchmark Suite for Continuous Parameter Logging System

This benchmark suite tests performance characteristics of the ALD control system's
continuous parameter logging implementation, focusing on critical bottlenecks
identified by system analysis.

Performance Areas Tested:
1. Database operations (batch inserts, connection pooling)
2. PLC communication (individual vs bulk operations)
3. System integration (end-to-end logging cycles)
4. Dual-mode logging performance impact
5. Error recovery mechanism performance
6. Memory and resource utilization patterns

Usage:
    python benchmark_performance_continuous_logging.py
    python benchmark_performance_continuous_logging.py --test database
    python benchmark_performance_continuous_logging.py --test plc
    python benchmark_performance_continuous_logging.py --test integration
    python benchmark_performance_continuous_logging.py --test stress
"""

import asyncio
import time
import statistics
import psutil
import gc
import sys
import argparse
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import tracemalloc

# System imports
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.plc.manager import plc_manager
from src.plc.factory import PLCFactory
from src.data_collection.continuous_parameter_logger import ContinuousParameterLogger
from src.config import MACHINE_ID, PLC_TYPE, PLC_CONFIG


@dataclass
class BenchmarkResult:
    """Benchmark test result data structure."""
    test_name: str
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    additional_data: Dict[str, Any] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics collected during benchmarks."""
    latency_ms: float
    throughput_ops_per_sec: float
    memory_mb: float
    cpu_percent: float
    success_rate: float
    error_count: int


class PerformanceBenchmarkSuite:
    """Comprehensive performance benchmark suite for continuous parameter logging."""

    def __init__(self):
        """Initialize benchmark suite."""
        self.results: List[BenchmarkResult] = []
        self.process = psutil.Process()
        self.baseline_memory = None
        self.test_data_cleanup = []

    async def run_all_benchmarks(self) -> Dict[str, List[BenchmarkResult]]:
        """Run all performance benchmarks."""
        logger.info("Starting comprehensive performance benchmark suite")

        # Start memory tracking
        tracemalloc.start()
        self.baseline_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        try:
            # Database Performance Benchmarks
            logger.info("Running database performance benchmarks...")
            await self.benchmark_database_performance()

            # PLC Communication Benchmarks
            logger.info("Running PLC communication benchmarks...")
            await self.benchmark_plc_communication()

            # System Integration Benchmarks
            logger.info("Running system integration benchmarks...")
            await self.benchmark_system_integration()

            # Stress and Load Testing
            logger.info("Running stress test benchmarks...")
            await self.benchmark_stress_scenarios()

            # Resource Utilization Benchmarks
            logger.info("Running resource utilization benchmarks...")
            await self.benchmark_resource_utilization()

        finally:
            # Cleanup test data
            await self.cleanup_test_data()
            tracemalloc.stop()

        # Organize results by category
        categorized_results = {}
        for result in self.results:
            category = result.test_name.split('_')[0]
            if category not in categorized_results:
                categorized_results[category] = []
            categorized_results[category].append(result)

        return categorized_results

    async def benchmark_database_performance(self):
        """Benchmark database operation performance."""
        logger.info("Testing database performance characteristics")

        # Test 1: Supabase Connection Establishment Time
        await self._benchmark_db_connection_time()

        # Test 2: Parameter Metadata Query Performance
        await self._benchmark_parameter_metadata_query()

        # Test 3: Batch Insert Performance (varying sizes)
        for batch_size in [1, 10, 50, 100, 200]:
            await self._benchmark_batch_insert_performance(batch_size)

        # Test 4: Dual-Mode Insert Performance Impact
        await self._benchmark_dual_mode_insert_performance()

        # Test 5: Database Transaction Overhead
        await self._benchmark_transaction_overhead()

        # Test 6: Connection Pool Impact (simulated)
        await self._benchmark_connection_pooling_impact()

    async def _benchmark_db_connection_time(self):
        """Benchmark database connection establishment time."""
        connection_times = []

        for i in range(10):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                # Simple query to ensure connection is established
                result = supabase.table('machines').select('id').limit(1).execute()
                end_time = time.perf_counter()
                connection_times.append((end_time - start_time) * 1000)  # Convert to ms
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                connection_times.append(None)

        # Filter out failed connections
        valid_times = [t for t in connection_times if t is not None]

        if valid_times:
            avg_time = statistics.mean(valid_times)
            median_time = statistics.median(valid_times)
            max_time = max(valid_times)

            self.results.append(BenchmarkResult(
                test_name="database_connection_establishment",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "median_ms": median_time,
                    "max_ms": max_time,
                    "success_rate": len(valid_times) / len(connection_times),
                    "sample_size": len(connection_times)
                }
            ))

    async def _benchmark_parameter_metadata_query(self):
        """Benchmark parameter metadata query performance."""
        query_times = []

        for i in range(20):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('component_parameters_full').select('*').execute()
                end_time = time.perf_counter()
                query_times.append((end_time - start_time) * 1000)
            except Exception as e:
                logger.error(f"Parameter metadata query failed: {e}")
                query_times.append(None)

        valid_times = [t for t in query_times if t is not None]

        if valid_times:
            avg_time = statistics.mean(valid_times)

            self.results.append(BenchmarkResult(
                test_name="database_parameter_metadata_query",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "max_ms": max(valid_times),
                    "min_ms": min(valid_times),
                    "std_dev": statistics.stdev(valid_times) if len(valid_times) > 1 else 0
                }
            ))

    async def _benchmark_batch_insert_performance(self, batch_size: int):
        """Benchmark batch insert performance for given batch size."""
        insert_times = []
        timestamp = get_current_timestamp()

        # Generate test data
        test_records = []
        for i in range(batch_size):
            test_records.append({
                'parameter_id': f'BENCHMARK_PARAM_{i}',
                'value': float(i * 1.1),
                'set_point': float(i * 1.2),
                'timestamp': timestamp
            })

        # Perform multiple insert tests
        for iteration in range(10):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('parameter_value_history').insert(test_records).execute()
                end_time = time.perf_counter()
                insert_times.append((end_time - start_time) * 1000)

                # Track for cleanup
                if result.data:
                    self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

            except Exception as e:
                logger.error(f"Batch insert failed for size {batch_size}: {e}")
                insert_times.append(None)

        valid_times = [t for t in insert_times if t is not None]

        if valid_times:
            avg_time = statistics.mean(valid_times)
            throughput = batch_size / (avg_time / 1000) if avg_time > 0 else 0

            self.results.append(BenchmarkResult(
                test_name=f"database_batch_insert_size_{batch_size}",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "batch_size": batch_size,
                    "throughput_records_per_sec": throughput,
                    "records_per_ms": batch_size / avg_time if avg_time > 0 else 0
                }
            ))

    async def _benchmark_dual_mode_insert_performance(self):
        """Benchmark the performance impact of dual-mode (history + process) inserts."""
        timestamp = get_current_timestamp()

        # Test single table insert vs dual table insert
        single_times = []
        dual_times = []

        test_records = [{
            'parameter_id': 'BENCHMARK_DUAL_TEST',
            'value': 123.45,
            'set_point': 100.0,
            'timestamp': timestamp
        }]

        process_records = [{
            'process_id': 'BENCHMARK_PROCESS_ID',
            'parameter_id': 'BENCHMARK_DUAL_TEST',
            'value': 123.45,
            'set_point': 100.0,
            'timestamp': timestamp
        }]

        # Test single table inserts
        for i in range(20):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('parameter_value_history').insert(test_records).execute()
                end_time = time.perf_counter()
                single_times.append((end_time - start_time) * 1000)
            except Exception as e:
                logger.error(f"Single table insert failed: {e}")

        # Test dual table inserts
        for i in range(20):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                # Insert to both tables (like dual-mode logging)
                result1 = supabase.table('parameter_value_history').insert(test_records).execute()
                result2 = supabase.table('process_data_points').insert(process_records).execute()
                end_time = time.perf_counter()
                dual_times.append((end_time - start_time) * 1000)
            except Exception as e:
                logger.error(f"Dual table insert failed: {e}")

        if single_times and dual_times:
            single_avg = statistics.mean(single_times)
            dual_avg = statistics.mean(dual_times)
            overhead_percent = ((dual_avg - single_avg) / single_avg) * 100 if single_avg > 0 else 0

            self.results.append(BenchmarkResult(
                test_name="database_dual_mode_overhead",
                metric_name="overhead_percentage",
                value=overhead_percent,
                unit="percent",
                timestamp=datetime.now(),
                additional_data={
                    "single_table_avg_ms": single_avg,
                    "dual_table_avg_ms": dual_avg,
                    "absolute_overhead_ms": dual_avg - single_avg
                }
            ))

    async def _benchmark_transaction_overhead(self):
        """Benchmark transaction overhead vs individual operations."""
        # This would require implementing transaction support
        # For now, log that this is a missing capability
        self.results.append(BenchmarkResult(
            test_name="database_transaction_overhead",
            metric_name="capability_missing",
            value=0,
            unit="none",
            timestamp=datetime.now(),
            additional_data={
                "note": "Transaction support not implemented in current system",
                "risk": "Data consistency issues during failures"
            }
        ))

    async def _benchmark_connection_pooling_impact(self):
        """Benchmark the impact of missing connection pooling."""
        # Test rapid successive database calls (simulating high load)
        rapid_times = []

        for i in range(50):
            start_time = time.perf_counter()
            try:
                # Create new Supabase client each time (simulating no pooling)
                supabase = get_supabase()
                result = supabase.table('machines').select('id').limit(1).execute()
                end_time = time.perf_counter()
                rapid_times.append((end_time - start_time) * 1000)
            except Exception as e:
                logger.error(f"Rapid connection test failed: {e}")

        if rapid_times:
            avg_time = statistics.mean(rapid_times)
            max_time = max(rapid_times)

            self.results.append(BenchmarkResult(
                test_name="database_connection_pooling_impact",
                metric_name="rapid_connection_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "max_latency_ms": max_time,
                    "connections_tested": len(rapid_times),
                    "note": "No connection pooling implemented"
                }
            ))

    async def benchmark_plc_communication(self):
        """Benchmark PLC communication performance."""
        logger.info("Testing PLC communication performance")

        # Test 1: PLC Connection Establishment
        await self._benchmark_plc_connection_time()

        # Test 2: Individual Parameter Read Performance
        await self._benchmark_individual_parameter_reads()

        # Test 3: Bulk Parameter Read Performance
        await self._benchmark_bulk_parameter_reads()

        # Test 4: Network Round-Trip Time
        await self._benchmark_plc_network_roundtrip()

        # Test 5: Connection Recovery Performance
        await self._benchmark_plc_connection_recovery()

    async def _benchmark_plc_connection_time(self):
        """Benchmark PLC connection establishment time."""
        connection_times = []

        for i in range(5):  # Fewer iterations due to potential hardware impact
            start_time = time.perf_counter()
            try:
                # Initialize PLC (includes connection)
                success = await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)
                end_time = time.perf_counter()

                if success:
                    connection_times.append((end_time - start_time) * 1000)
                else:
                    logger.warning(f"PLC connection failed on iteration {i}")

                # Disconnect for next test
                await plc_manager.disconnect()

            except Exception as e:
                logger.error(f"PLC connection benchmark failed: {e}")

        if connection_times:
            avg_time = statistics.mean(connection_times)

            self.results.append(BenchmarkResult(
                test_name="plc_connection_establishment",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "max_ms": max(connection_times),
                    "min_ms": min(connection_times),
                    "success_rate": len(connection_times) / 5
                }
            ))

    async def _benchmark_individual_parameter_reads(self):
        """Benchmark individual parameter read performance."""
        if not plc_manager.is_connected():
            await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)

        if not plc_manager.is_connected():
            logger.warning("Cannot benchmark parameter reads - PLC not connected")
            return

        # Get available parameters from cache
        if hasattr(plc_manager.plc, '_parameter_cache'):
            parameter_ids = list(plc_manager.plc._parameter_cache.keys())[:10]  # Test first 10
        else:
            logger.warning("No parameter cache available for benchmark")
            return

        read_times = []

        for param_id in parameter_ids:
            for iteration in range(5):  # 5 reads per parameter
                start_time = time.perf_counter()
                try:
                    value = await plc_manager.read_parameter(param_id)
                    end_time = time.perf_counter()
                    read_times.append((end_time - start_time) * 1000)
                except Exception as e:
                    logger.error(f"Failed to read parameter {param_id}: {e}")

        if read_times:
            avg_time = statistics.mean(read_times)

            self.results.append(BenchmarkResult(
                test_name="plc_individual_parameter_read",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "parameters_tested": len(parameter_ids),
                    "total_reads": len(read_times),
                    "max_ms": max(read_times),
                    "min_ms": min(read_times)
                }
            ))

    async def _benchmark_bulk_parameter_reads(self):
        """Benchmark bulk parameter read performance."""
        if not plc_manager.is_connected():
            await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)

        if not plc_manager.is_connected():
            logger.warning("Cannot benchmark bulk reads - PLC not connected")
            return

        bulk_read_times = []

        for iteration in range(10):
            start_time = time.perf_counter()
            try:
                parameter_values = await plc_manager.read_all_parameters()
                end_time = time.perf_counter()

                read_time = (end_time - start_time) * 1000
                bulk_read_times.append(read_time)

                param_count = len(parameter_values) if parameter_values else 0
                logger.debug(f"Bulk read {iteration}: {read_time:.2f}ms for {param_count} parameters")

            except Exception as e:
                logger.error(f"Bulk parameter read failed: {e}")

        if bulk_read_times:
            avg_time = statistics.mean(bulk_read_times)

            self.results.append(BenchmarkResult(
                test_name="plc_bulk_parameter_read",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "iterations": len(bulk_read_times),
                    "max_ms": max(bulk_read_times),
                    "min_ms": min(bulk_read_times)
                }
            ))

    async def _benchmark_plc_network_roundtrip(self):
        """Benchmark basic network round-trip time to PLC."""
        # This would require implementing a ping-like operation
        # For now, use connection health check as proxy
        roundtrip_times = []

        if plc_manager.is_connected():
            for i in range(20):
                start_time = time.perf_counter()
                try:
                    # Use a simple read operation as roundtrip test
                    connected = plc_manager.is_connected()
                    if connected and hasattr(plc_manager.plc, 'communicator'):
                        # Attempt a minimal read operation
                        result = plc_manager.plc.communicator.client.read_holding_registers(0, 1, slave=1)
                        end_time = time.perf_counter()
                        roundtrip_times.append((end_time - start_time) * 1000)
                    else:
                        break
                except Exception as e:
                    logger.debug(f"Network roundtrip test failed: {e}")

        if roundtrip_times:
            avg_time = statistics.mean(roundtrip_times)

            self.results.append(BenchmarkResult(
                test_name="plc_network_roundtrip",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "measurements": len(roundtrip_times),
                    "max_ms": max(roundtrip_times),
                    "min_ms": min(roundtrip_times)
                }
            ))

    async def _benchmark_plc_connection_recovery(self):
        """Benchmark PLC connection recovery time."""
        if not plc_manager.is_connected():
            await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)

        recovery_times = []

        # Test connection recovery
        for i in range(3):  # Limited iterations to avoid hardware impact
            try:
                # Disconnect
                await plc_manager.disconnect()

                # Attempt reconnection
                start_time = time.perf_counter()
                success = await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)
                end_time = time.perf_counter()

                if success:
                    recovery_times.append((end_time - start_time) * 1000)
                else:
                    logger.warning(f"PLC recovery failed on iteration {i}")

            except Exception as e:
                logger.error(f"PLC recovery benchmark failed: {e}")

        if recovery_times:
            avg_time = statistics.mean(recovery_times)

            self.results.append(BenchmarkResult(
                test_name="plc_connection_recovery",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "recovery_attempts": len(recovery_times),
                    "max_ms": max(recovery_times),
                    "success_rate": len(recovery_times) / 3
                }
            ))

    async def benchmark_system_integration(self):
        """Benchmark end-to-end system integration performance."""
        logger.info("Testing system integration performance")

        # Test 1: End-to-End Logging Cycle Performance
        await self._benchmark_end_to_end_logging_cycle()

        # Test 2: Dual-Mode Switching Overhead
        await self._benchmark_dual_mode_switching()

        # Test 3: Error Handling Performance Impact
        await self._benchmark_error_handling_performance()

        # Test 4: Concurrent Operation Performance
        await self._benchmark_concurrent_operations()

    async def _benchmark_end_to_end_logging_cycle(self):
        """Benchmark complete logging cycle from PLC read to database insert."""
        cycle_times = []

        # Ensure PLC is connected
        if not plc_manager.is_connected():
            await plc_manager.initialize(PLC_TYPE, PLC_CONFIG)

        if not plc_manager.is_connected():
            logger.warning("Cannot benchmark end-to-end cycle - PLC not connected")
            return

        for iteration in range(10):
            start_time = time.perf_counter()
            try:
                # Simulate the continuous logger cycle
                # 1. Read all parameters
                parameter_values = await plc_manager.read_all_parameters()

                if parameter_values:
                    # 2. Prepare data
                    timestamp = get_current_timestamp()
                    history_records = []

                    for param_id, value in parameter_values.items():
                        if value is not None:
                            history_records.append({
                                'parameter_id': param_id,
                                'value': value,
                                'set_point': None,
                                'timestamp': timestamp
                            })

                    # 3. Insert to database
                    if history_records:
                        supabase = get_supabase()
                        result = supabase.table('parameter_value_history').insert(history_records[:5]).execute()  # Limit to 5 for test

                        # Track for cleanup
                        if result.data:
                            self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

                end_time = time.perf_counter()
                cycle_times.append((end_time - start_time) * 1000)

            except Exception as e:
                logger.error(f"End-to-end cycle failed: {e}")

        if cycle_times:
            avg_time = statistics.mean(cycle_times)

            self.results.append(BenchmarkResult(
                test_name="integration_end_to_end_cycle",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "cycles_tested": len(cycle_times),
                    "max_ms": max(cycle_times),
                    "min_ms": min(cycle_times),
                    "target_interval_ms": 1000,
                    "exceeds_target": avg_time > 1000
                }
            ))

    async def _benchmark_dual_mode_switching(self):
        """Benchmark the overhead of dual-mode logging decisions."""
        switching_times = []

        # Simulate checking process status (key part of dual-mode logic)
        for iteration in range(50):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()

                # Simulate dual-mode decision logic
                if result.data and result.data.get('status') == 'processing':
                    process_id = result.data.get('current_process_id')
                    dual_mode = process_id is not None
                else:
                    dual_mode = False

                end_time = time.perf_counter()
                switching_times.append((end_time - start_time) * 1000)

            except Exception as e:
                logger.error(f"Dual-mode switching test failed: {e}")

        if switching_times:
            avg_time = statistics.mean(switching_times)

            self.results.append(BenchmarkResult(
                test_name="integration_dual_mode_switching",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "decision_cycles": len(switching_times),
                    "max_ms": max(switching_times),
                    "min_ms": min(switching_times)
                }
            ))

    async def _benchmark_error_handling_performance(self):
        """Benchmark performance impact of error handling mechanisms."""
        # Test error handling overhead
        normal_times = []
        error_times = []

        # Normal operation timing
        for i in range(20):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').limit(1).execute()
                end_time = time.perf_counter()
                normal_times.append((end_time - start_time) * 1000)
            except Exception:
                pass

        # Error handling timing (simulate by querying non-existent table)
        for i in range(20):
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('nonexistent_table').select('id').limit(1).execute()
            except Exception:
                end_time = time.perf_counter()
                error_times.append((end_time - start_time) * 1000)

        if normal_times and error_times:
            normal_avg = statistics.mean(normal_times)
            error_avg = statistics.mean(error_times)
            overhead = error_avg - normal_avg

            self.results.append(BenchmarkResult(
                test_name="integration_error_handling_overhead",
                metric_name="error_overhead",
                value=overhead,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "normal_avg_ms": normal_avg,
                    "error_avg_ms": error_avg,
                    "overhead_percent": (overhead / normal_avg) * 100 if normal_avg > 0 else 0
                }
            ))

    async def _benchmark_concurrent_operations(self):
        """Benchmark performance under concurrent operations."""
        # Simulate multiple concurrent database operations
        async def concurrent_operation():
            start_time = time.perf_counter()
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').limit(1).execute()
                end_time = time.perf_counter()
                return (end_time - start_time) * 1000
            except Exception:
                return None

        # Test different concurrency levels
        for concurrency in [1, 5, 10, 20]:
            concurrent_times = []

            for batch in range(5):  # 5 batches of concurrent operations
                start_time = time.perf_counter()

                # Run concurrent operations
                tasks = [concurrent_operation() for _ in range(concurrency)]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                end_time = time.perf_counter()
                batch_time = (end_time - start_time) * 1000

                # Calculate success rate
                successful_results = [r for r in results if isinstance(r, float)]
                success_rate = len(successful_results) / len(results)

                concurrent_times.append({
                    'batch_time_ms': batch_time,
                    'success_rate': success_rate,
                    'avg_operation_time': statistics.mean(successful_results) if successful_results else None
                })

            if concurrent_times:
                avg_batch_time = statistics.mean([ct['batch_time_ms'] for ct in concurrent_times])
                avg_success_rate = statistics.mean([ct['success_rate'] for ct in concurrent_times])

                self.results.append(BenchmarkResult(
                    test_name=f"integration_concurrent_operations_{concurrency}",
                    metric_name="batch_latency",
                    value=avg_batch_time,
                    unit="ms",
                    timestamp=datetime.now(),
                    additional_data={
                        "concurrency_level": concurrency,
                        "success_rate": avg_success_rate,
                        "batches_tested": len(concurrent_times)
                    }
                ))

    async def benchmark_stress_scenarios(self):
        """Benchmark performance under stress conditions."""
        logger.info("Testing stress scenario performance")

        # Test 1: High-Frequency Logging Simulation
        await self._benchmark_high_frequency_logging()

        # Test 2: Large Parameter Set Performance
        await self._benchmark_large_parameter_sets()

        # Test 3: Memory Pressure Performance
        await self._benchmark_memory_pressure_performance()

        # Test 4: Error Recovery Performance
        await self._benchmark_error_recovery_performance()

    async def _benchmark_high_frequency_logging(self):
        """Benchmark performance under high-frequency logging conditions."""
        high_freq_times = []

        # Simulate logging every 100ms instead of 1000ms
        for iteration in range(50):
            start_time = time.perf_counter()

            # Simulate rapid logging cycle
            timestamp = get_current_timestamp()
            test_record = {
                'parameter_id': f'HIGH_FREQ_TEST_{iteration}',
                'value': float(iteration),
                'set_point': None,
                'timestamp': timestamp
            }

            try:
                supabase = get_supabase()
                result = supabase.table('parameter_value_history').insert([test_record]).execute()
                end_time = time.perf_counter()

                high_freq_times.append((end_time - start_time) * 1000)

                # Track for cleanup
                if result.data:
                    self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

                # Short delay to simulate high frequency
                await asyncio.sleep(0.05)  # 50ms

            except Exception as e:
                logger.error(f"High frequency logging failed: {e}")

        if high_freq_times:
            avg_time = statistics.mean(high_freq_times)

            self.results.append(BenchmarkResult(
                test_name="stress_high_frequency_logging",
                metric_name="average_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "frequency_tested": "50ms intervals",
                    "operations": len(high_freq_times),
                    "max_ms": max(high_freq_times),
                    "sustainable": avg_time < 50  # Can it keep up with 50ms interval?
                }
            ))

    async def _benchmark_large_parameter_sets(self):
        """Benchmark performance with large parameter sets."""
        for param_count in [50, 100, 200, 500]:
            large_set_times = []

            # Generate large parameter set
            timestamp = get_current_timestamp()
            large_records = []
            for i in range(param_count):
                large_records.append({
                    'parameter_id': f'LARGE_SET_PARAM_{i}',
                    'value': float(i * 1.5),
                    'set_point': float(i * 1.2),
                    'timestamp': timestamp
                })

            # Test insertion performance
            for iteration in range(5):
                start_time = time.perf_counter()
                try:
                    supabase = get_supabase()
                    # Use batching like the real system
                    batch_size = 50
                    total_time = 0

                    for i in range(0, len(large_records), batch_size):
                        batch = large_records[i:i+batch_size]
                        batch_start = time.perf_counter()
                        result = supabase.table('parameter_value_history').insert(batch).execute()
                        batch_end = time.perf_counter()
                        total_time += (batch_end - batch_start) * 1000

                        # Track for cleanup
                        if result.data:
                            self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

                    large_set_times.append(total_time)

                except Exception as e:
                    logger.error(f"Large parameter set test failed for {param_count} params: {e}")

            if large_set_times:
                avg_time = statistics.mean(large_set_times)
                throughput = param_count / (avg_time / 1000) if avg_time > 0 else 0

                self.results.append(BenchmarkResult(
                    test_name=f"stress_large_parameter_set_{param_count}",
                    metric_name="total_latency",
                    value=avg_time,
                    unit="ms",
                    timestamp=datetime.now(),
                    additional_data={
                        "parameter_count": param_count,
                        "throughput_params_per_sec": throughput,
                        "exceeds_1sec_window": avg_time > 1000
                    }
                ))

    async def _benchmark_memory_pressure_performance(self):
        """Benchmark performance under memory pressure."""
        # Monitor memory usage during operations
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        memory_intensive_times = []
        memory_readings = []

        # Create memory pressure by accumulating data
        accumulated_data = []

        for iteration in range(20):
            start_time = time.perf_counter()

            # Accumulate some data to increase memory pressure
            large_data = [f"memory_test_data_{i}" * 1000 for i in range(1000)]
            accumulated_data.extend(large_data)

            # Perform operation under memory pressure
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('id').limit(1).execute()
                end_time = time.perf_counter()

                memory_intensive_times.append((end_time - start_time) * 1000)
                current_memory = self.process.memory_info().rss / 1024 / 1024
                memory_readings.append(current_memory)

            except Exception as e:
                logger.error(f"Memory pressure test failed: {e}")

        # Clean up accumulated data
        del accumulated_data
        gc.collect()

        if memory_intensive_times and memory_readings:
            avg_time = statistics.mean(memory_intensive_times)
            avg_memory = statistics.mean(memory_readings)
            memory_increase = avg_memory - initial_memory

            self.results.append(BenchmarkResult(
                test_name="stress_memory_pressure",
                metric_name="performance_under_pressure",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "avg_memory_mb": avg_memory,
                    "memory_increase_mb": memory_increase,
                    "max_memory_mb": max(memory_readings),
                    "performance_degradation": avg_time > 100  # Arbitrary threshold
                }
            ))

    async def _benchmark_error_recovery_performance(self):
        """Benchmark error recovery mechanism performance."""
        # Simulate the continuous logger error recovery logic
        recovery_times = []

        class MockContinuousLogger:
            def __init__(self):
                self._error_count = 0
                self._max_consecutive_errors = 5

        mock_logger = MockContinuousLogger()

        # Test error recovery cycle timing
        for iteration in range(10):
            start_time = time.perf_counter()

            # Simulate error accumulation and recovery
            for error_num in range(6):  # Trigger max errors + 1
                mock_logger._error_count += 1

                if mock_logger._error_count >= mock_logger._max_consecutive_errors:
                    # Simulate 30-second pause (reduced for testing)
                    await asyncio.sleep(0.1)  # 100ms instead of 30s
                    mock_logger._error_count = 0  # Reset after pause
                    break

            end_time = time.perf_counter()
            recovery_times.append((end_time - start_time) * 1000)

        if recovery_times:
            avg_time = statistics.mean(recovery_times)

            self.results.append(BenchmarkResult(
                test_name="stress_error_recovery_cycle",
                metric_name="recovery_latency",
                value=avg_time,
                unit="ms",
                timestamp=datetime.now(),
                additional_data={
                    "recovery_cycles": len(recovery_times),
                    "simulated_pause_ms": 100,
                    "actual_pause_would_be_ms": 30000,
                    "note": "Error recovery creates 30-second service interruptions"
                }
            ))

    async def benchmark_resource_utilization(self):
        """Benchmark resource utilization patterns."""
        logger.info("Testing resource utilization patterns")

        # Test 1: Memory Usage Patterns
        await self._benchmark_memory_usage_patterns()

        # Test 2: CPU Usage Patterns
        await self._benchmark_cpu_usage_patterns()

        # Test 3: Asyncio Task Accumulation
        await self._benchmark_asyncio_task_patterns()

    async def _benchmark_memory_usage_patterns(self):
        """Benchmark memory usage patterns during continuous operation."""
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        memory_samples = []

        # Simulate continuous operation
        for minute in range(5):  # 5 minute simulation
            for cycle in range(10):  # 10 cycles per minute (6-second intervals)
                # Simulate a logging cycle
                timestamp = get_current_timestamp()
                test_data = {
                    'parameter_id': f'MEMORY_TEST_{minute}_{cycle}',
                    'value': float(cycle),
                    'timestamp': timestamp
                }

                try:
                    supabase = get_supabase()
                    result = supabase.table('parameter_value_history').insert([test_data]).execute()

                    # Track for cleanup
                    if result.data:
                        self.test_data_cleanup.extend([r['id'] for r in result.data if 'id' in r])

                except Exception as e:
                    logger.error(f"Memory usage test failed: {e}")

                # Sample memory usage
                current_memory = self.process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)

                await asyncio.sleep(0.1)  # Short delay

        if memory_samples:
            avg_memory = statistics.mean(memory_samples)
            max_memory = max(memory_samples)
            memory_growth = max_memory - initial_memory

            self.results.append(BenchmarkResult(
                test_name="resource_memory_usage_pattern",
                metric_name="average_memory_usage",
                value=avg_memory,
                unit="MB",
                timestamp=datetime.now(),
                additional_data={
                    "initial_memory_mb": initial_memory,
                    "max_memory_mb": max_memory,
                    "memory_growth_mb": memory_growth,
                    "samples": len(memory_samples),
                    "potential_leak": memory_growth > 50  # Arbitrary threshold
                }
            ))

    async def _benchmark_cpu_usage_patterns(self):
        """Benchmark CPU usage patterns during operations."""
        cpu_samples = []

        # Monitor CPU during database operations
        for iteration in range(30):
            cpu_before = self.process.cpu_percent()

            # Perform some database operations
            try:
                supabase = get_supabase()
                result = supabase.table('machines').select('*').limit(10).execute()
            except Exception:
                pass

            await asyncio.sleep(0.1)  # Allow CPU measurement
            cpu_after = self.process.cpu_percent()
            cpu_samples.append(cpu_after)

        if cpu_samples:
            avg_cpu = statistics.mean(cpu_samples)
            max_cpu = max(cpu_samples)

            self.results.append(BenchmarkResult(
                test_name="resource_cpu_usage_pattern",
                metric_name="average_cpu_percent",
                value=avg_cpu,
                unit="percent",
                timestamp=datetime.now(),
                additional_data={
                    "max_cpu_percent": max_cpu,
                    "samples": len(cpu_samples),
                    "high_usage": avg_cpu > 50  # Arbitrary threshold
                }
            ))

    async def _benchmark_asyncio_task_patterns(self):
        """Benchmark asyncio task accumulation patterns."""
        initial_tasks = len(asyncio.all_tasks())
        task_counts = []

        # Create tasks like the continuous logger might
        created_tasks = []

        for iteration in range(20):
            # Simulate background task creation (like update_parameter_value)
            async def mock_background_task():
                await asyncio.sleep(0.01)
                return f"task_{iteration}"

            task = asyncio.create_task(mock_background_task())
            created_tasks.append(task)

            current_tasks = len(asyncio.all_tasks())
            task_counts.append(current_tasks)

            await asyncio.sleep(0.05)

        # Wait for created tasks to complete
        await asyncio.gather(*created_tasks, return_exceptions=True)

        final_tasks = len(asyncio.all_tasks())

        if task_counts:
            max_tasks = max(task_counts)
            task_growth = max_tasks - initial_tasks

            self.results.append(BenchmarkResult(
                test_name="resource_asyncio_task_pattern",
                metric_name="max_concurrent_tasks",
                value=max_tasks,
                unit="count",
                timestamp=datetime.now(),
                additional_data={
                    "initial_tasks": initial_tasks,
                    "final_tasks": final_tasks,
                    "task_growth": task_growth,
                    "potential_leak": final_tasks > initial_tasks + 5  # Some tolerance
                }
            ))

    async def cleanup_test_data(self):
        """Clean up test data created during benchmarks."""
        if not self.test_data_cleanup:
            return

        logger.info(f"Cleaning up {len(self.test_data_cleanup)} test records")

        try:
            supabase = get_supabase()
            # Delete in batches
            batch_size = 50
            for i in range(0, len(self.test_data_cleanup), batch_size):
                batch_ids = self.test_data_cleanup[i:i+batch_size]
                supabase.table('parameter_value_history').delete().in_('id', batch_ids).execute()

        except Exception as e:
            logger.error(f"Failed to cleanup test data: {e}")

    def generate_performance_report(self, results: Dict[str, List[BenchmarkResult]]) -> str:
        """Generate a comprehensive performance report."""
        report = []
        report.append("=" * 80)
        report.append("CONTINUOUS PARAMETER LOGGING SYSTEM - PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Executive Summary
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 40)

        critical_issues = []
        performance_warnings = []

        for category, category_results in results.items():
            for result in category_results:
                # Check for critical performance issues
                if result.test_name.endswith("end_to_end_cycle"):
                    if result.value > 1000:  # Exceeds 1-second window
                        critical_issues.append(f"End-to-end cycle ({result.value:.1f}ms) exceeds 1-second logging window")

                if "memory" in result.test_name and result.additional_data:
                    if result.additional_data.get("potential_leak", False):
                        critical_issues.append("Potential memory leak detected during continuous operation")

                if "error_recovery" in result.test_name:
                    if result.additional_data and result.additional_data.get("actual_pause_would_be_ms", 0) > 10000:
                        critical_issues.append("Error recovery causes 30-second service interruptions")

        if critical_issues:
            report.append("CRITICAL ISSUES IDENTIFIED:")
            for issue in critical_issues:
                report.append(f"  ❌ {issue}")
        else:
            report.append("✅ No critical performance issues detected")

        report.append("")

        # Detailed Results by Category
        for category, category_results in results.items():
            report.append(f"{category.upper()} PERFORMANCE RESULTS")
            report.append("-" * 50)

            for result in category_results:
                report.append(f"Test: {result.test_name}")
                report.append(f"  Metric: {result.metric_name}")
                report.append(f"  Value: {result.value:.2f} {result.unit}")

                if result.additional_data:
                    for key, value in result.additional_data.items():
                        if isinstance(value, float):
                            report.append(f"  {key}: {value:.2f}")
                        else:
                            report.append(f"  {key}: {value}")

                report.append("")

        # Performance Recommendations
        report.append("PERFORMANCE RECOMMENDATIONS")
        report.append("-" * 50)
        recommendations = [
            "1. Implement connection pooling for database operations",
            "2. Add bulk PLC parameter reading operations",
            "3. Implement proper transaction boundaries for dual-mode logging",
            "4. Add circuit breaker pattern for error handling",
            "5. Implement performance monitoring and alerting",
            "6. Add caching layer for parameter metadata",
            "7. Optimize error recovery to avoid 30-second service interruptions",
            "8. Implement proper asyncio task lifecycle management"
        ]

        for rec in recommendations:
            report.append(rec)

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)


async def main():
    """Main benchmark execution function."""
    parser = argparse.ArgumentParser(description='Performance Benchmark Suite for Continuous Parameter Logging')
    parser.add_argument('--test', choices=['database', 'plc', 'integration', 'stress', 'resource', 'all'],
                       default='all', help='Specific test category to run')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    parser.add_argument('--report', help='Output file for human-readable report')

    args = parser.parse_args()

    benchmark_suite = PerformanceBenchmarkSuite()

    try:
        if args.test == 'all':
            results = await benchmark_suite.run_all_benchmarks()
        elif args.test == 'database':
            await benchmark_suite.benchmark_database_performance()
            results = {'database': benchmark_suite.results}
        elif args.test == 'plc':
            await benchmark_suite.benchmark_plc_communication()
            results = {'plc': benchmark_suite.results}
        elif args.test == 'integration':
            await benchmark_suite.benchmark_system_integration()
            results = {'integration': benchmark_suite.results}
        elif args.test == 'stress':
            await benchmark_suite.benchmark_stress_scenarios()
            results = {'stress': benchmark_suite.results}
        elif args.test == 'resource':
            await benchmark_suite.benchmark_resource_utilization()
            results = {'resource': benchmark_suite.results}

        # Output results
        if args.output:
            # Convert results to JSON-serializable format
            json_results = {}
            for category, category_results in results.items():
                json_results[category] = []
                for result in category_results:
                    json_results[category].append({
                        'test_name': result.test_name,
                        'metric_name': result.metric_name,
                        'value': result.value,
                        'unit': result.unit,
                        'timestamp': result.timestamp.isoformat(),
                        'additional_data': result.additional_data
                    })

            with open(args.output, 'w') as f:
                json.dump(json_results, f, indent=2)
            logger.info(f"Benchmark results saved to {args.output}")

        # Generate and output report
        report = benchmark_suite.generate_performance_report(results)

        if args.report:
            with open(args.report, 'w') as f:
                f.write(report)
            logger.info(f"Performance report saved to {args.report}")
        else:
            print(report)

        # Log summary
        total_tests = sum(len(category_results) for category_results in results.values())
        logger.info(f"Performance benchmark completed: {total_tests} tests executed")

    except Exception as e:
        logger.error(f"Benchmark suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())