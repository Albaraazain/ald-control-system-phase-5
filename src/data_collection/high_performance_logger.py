# File: data_collection/high_performance_logger.py
"""
High-performance continuous parameter logging system with strict 1-second interval requirements.

This module provides an optimized implementation with:
- Bulk PLC parameter reading with address range optimization
- Async database connection pooling with prepared statements
- Concurrent processing with worker pools
- Real-time performance monitoring and jitter reduction
- Memory-efficient bulk operations
"""
import asyncio
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics
from src.log_setup import logger
from src.plc.manager import plc_manager
from src.performance.sla_monitor import performance_sla_monitor
from src.performance.distributed_manager import distributed_parameter_manager
from src.db import get_current_timestamp
from src.config import MACHINE_ID


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring system performance."""
    interval_start: float
    plc_read_time: float
    database_write_time: float
    total_cycle_time: float
    parameters_processed: int
    jitter_ms: float
    errors: List[str]


@dataclass
class ParameterGroup:
    """Grouped parameters for bulk reading optimization."""
    data_type: str
    address_range: Tuple[int, int]  # (start_address, end_address)
    parameter_ids: List[str]
    read_addresses: List[int]


class HighPerformanceParameterLogger:
    """
    High-performance parameter logger with bulk operations and connection pooling.

    Designed to meet strict 1-second interval requirements with <10ms jitter.
    """

    def __init__(self, interval_seconds: float = 1.0, max_workers: int = 4):
        """
        Initialize the high-performance parameter logger.

        Args:
            interval_seconds: Time between readings in seconds (default: 1.0)
            max_workers: Maximum number of concurrent workers for processing
        """
        self.interval = interval_seconds
        self.max_workers = max_workers
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._error_count = 0
        self._max_consecutive_errors = 3
        self._last_successful_read = None

        # Performance monitoring
        self._performance_metrics: List[PerformanceMetrics] = []
        self._max_metrics_history = 300  # 5 minutes of history

        # Distributed processing capabilities
        self._enable_distributed = True
        self._distributed_threshold = 50  # Use distributed processing for 50+ parameters
        self._worker_semaphore = asyncio.Semaphore(max_workers)

        # Parameter grouping cache
        self._parameter_groups: List[ParameterGroup] = []
        self._parameter_metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_refresh_interval = 300  # 5 minutes
        self._last_cache_refresh = 0

        # Worker pool
        self._worker_semaphore: Optional[asyncio.Semaphore] = None

    async def start(self):
        """Start high-performance parameter logging."""
        if self.is_running:
            logger.warning("High-performance parameter logger is already running")
            return

        self.is_running = True
        self._error_count = 0
        self._worker_semaphore = asyncio.Semaphore(self.max_workers)

        # Initialize parameter cache
        await self._refresh_parameter_cache()

        # Start SLA monitoring
        await performance_sla_monitor.start_monitoring()

        # Enable distributed processing if configured
        if self._enable_distributed:
            await self.enable_distributed_processing()

        self._task = asyncio.create_task(self._high_performance_logging_loop())
        logger.info(f"Started high-performance parameter logging service with {self.max_workers} workers and SLA monitoring")

    async def stop(self):
        """Stop the high-performance parameter logging."""
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Stop SLA monitoring
        await performance_sla_monitor.stop_monitoring()

        # Stop distributed processing if running
        if distributed_parameter_manager._is_running:
            await distributed_parameter_manager.stop()

        logger.info("Stopped high-performance parameter logging service")

    async def _high_performance_logging_loop(self):
        """High-performance loop with precise timing and minimal jitter."""
        try:
            while self.is_running:
                cycle_start = time.time()
                target_next_cycle = cycle_start + self.interval

                try:
                    # Execute high-performance logging cycle
                    metrics = await self._execute_logging_cycle(cycle_start)

                    # Update performance tracking
                    self._update_performance_metrics(metrics)
                    self._error_count = 0
                    self._last_successful_read = cycle_start

                    # Record SLA metrics for performance monitoring
                    await self._record_sla_metrics(metrics)

                except Exception as e:
                    self._error_count += 1
                    logger.error(
                        f"Error in high-performance logging cycle (attempt {self._error_count}): {str(e)}",
                        exc_info=True
                    )

                    # If too many consecutive errors, pause briefly
                    if self._error_count >= self._max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive errors ({self._error_count}), "
                            f"pausing for 10 seconds"
                        )
                        await asyncio.sleep(10)
                        self._error_count = 0

                # Precise timing to maintain 1-second intervals
                current_time = time.time()
                sleep_time = target_next_cycle - current_time

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                elif sleep_time < -0.01:  # More than 10ms late
                    logger.warning(f"Logging cycle exceeded target by {-sleep_time*1000:.1f}ms")

        except asyncio.CancelledError:
            logger.info("High-performance parameter logging loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in high-performance logging loop: {str(e)}", exc_info=True)
            self.is_running = False

    async def _execute_logging_cycle(self, cycle_start: float) -> PerformanceMetrics:
        """Execute a single high-performance logging cycle."""
        errors = []

        # Check if PLC is connected
        if not plc_manager.is_connected():
            logger.debug("PLC not connected, skipping parameter reading")
            return PerformanceMetrics(
                interval_start=cycle_start,
                plc_read_time=0,
                database_write_time=0,
                total_cycle_time=0,
                parameters_processed=0,
                jitter_ms=0,
                errors=["PLC not connected"]
            )

        # Refresh parameter cache if needed
        if time.time() - self._last_cache_refresh > self._cache_refresh_interval:
            await self._refresh_parameter_cache()

        # Get current process state
        process_start = time.time()
        current_process_id = await self._get_current_process_id()

        # Execute bulk parameter reading with optional distributed processing
        plc_start = time.time()
        parameter_values = await self._smart_bulk_read_parameters()
        plc_time = time.time() - plc_start

        if not parameter_values:
            return PerformanceMetrics(
                interval_start=cycle_start,
                plc_read_time=plc_time,
                database_write_time=0,
                total_cycle_time=time.time() - cycle_start,
                parameters_processed=0,
                jitter_ms=0,
                errors=["No parameters read from PLC"]
            )

        # Prepare data for bulk database operations
        db_start = time.time()
        timestamp = get_current_timestamp()

        history_records, process_records = await self._prepare_bulk_records(
            parameter_values, current_process_id, timestamp
        )

        # Execute bulk database writes
        await self._bulk_insert_records(history_records, process_records, current_process_id)
        db_time = time.time() - db_start

        total_time = time.time() - cycle_start
        jitter_ms = abs((total_time - self.interval) * 1000)

        logger.debug(
            f"High-performance cycle: {len(parameter_values)} parameters, "
            f"PLC: {plc_time*1000:.1f}ms, DB: {db_time*1000:.1f}ms, "
            f"Total: {total_time*1000:.1f}ms, Jitter: {jitter_ms:.1f}ms"
        )

        return PerformanceMetrics(
            interval_start=cycle_start,
            plc_read_time=plc_time,
            database_write_time=db_time,
            total_cycle_time=total_time,
            parameters_processed=len(parameter_values),
            jitter_ms=jitter_ms,
            errors=errors
        )

    async def _bulk_read_parameters(self) -> Dict[str, float]:
        """
        Execute bulk parameter reading using optimized Modbus bulk operations.

        Returns:
            Dict mapping parameter_id to value
        """
        if not self._parameter_metadata_cache:
            logger.warning("No parameter metadata available for bulk reading")
            return {}

        # Prepare parameter addresses for optimization
        parameter_addresses = []
        for param_id, metadata in self._parameter_metadata_cache.items():
            read_addr = metadata.get('read_modbus_address')
            data_type = metadata.get('data_type')
            read_type = metadata.get('read_modbus_type', '').lower()

            if read_addr is not None:
                parameter_addresses.append((param_id, read_addr, data_type, read_type))

        if not parameter_addresses:
            logger.warning("No parameters with valid read addresses found")
            return {}

        # Optimize address ranges for bulk reading
        optimized_ranges = plc_manager.plc.communicator.optimize_address_ranges(
            parameter_addresses, max_gap=2, max_range_size=50
        )

        all_parameter_values = {}

        # Execute bulk reads for holding registers
        if optimized_ranges['holding_registers']:
            holding_results = await self._bulk_read_holding_registers(
                optimized_ranges['holding_registers']
            )
            all_parameter_values.update(holding_results)

        # Execute bulk reads for coils
        if optimized_ranges['coils']:
            coil_results = await self._bulk_read_coils(
                optimized_ranges['coils']
            )
            all_parameter_values.update(coil_results)

        # Fallback to individual reads for any failed bulk operations
        if len(all_parameter_values) < len(parameter_addresses):
            missing_params = [
                param_id for param_id, _, _, _ in parameter_addresses
                if param_id not in all_parameter_values
            ]

            if missing_params:
                logger.info(f"Falling back to individual reads for {len(missing_params)} parameters")
                individual_results = await self._fallback_individual_reads(missing_params)
                all_parameter_values.update(individual_results)

        return all_parameter_values

    async def _bulk_read_holding_registers(self, register_ranges) -> Dict[str, float]:
        """
        Execute bulk reads for holding register ranges.

        Args:
            register_ranges: List of optimized register ranges

        Returns:
            Dict mapping parameter_id to value
        """
        results = {}

        for range_info in register_ranges:
            try:
                start_addr = range_info['start_address']
                count = range_info['count']
                data_type = range_info['data_type']
                parameters = range_info['parameters']

                # Execute bulk read using PLCCommunicator
                bulk_results = plc_manager.plc.communicator.bulk_read_holding_registers([
                    (start_addr, count, data_type)
                ])

                if start_addr in bulk_results:
                    values = bulk_results[start_addr]

                    # Map values back to parameter IDs
                    for i, (param_id, param_addr, param_data_type) in enumerate(parameters):
                        if i < len(values):
                            results[param_id] = float(values[i])

                    logger.debug(f"Bulk read {len(values)} values from registers {start_addr}-{start_addr + count - 1}")

            except Exception as e:
                logger.error(f"Error in bulk register read for range {start_addr}: {e}")
                # Fallback will handle individual reads

        return results

    async def _bulk_read_coils(self, coil_ranges) -> Dict[str, float]:
        """
        Execute bulk reads for coil ranges.

        Args:
            coil_ranges: List of optimized coil ranges

        Returns:
            Dict mapping parameter_id to value
        """
        results = {}

        for range_info in coil_ranges:
            try:
                start_addr = range_info['start_address']
                count = range_info['count']
                parameters = range_info['parameters']

                # Execute bulk read using PLCCommunicator
                bulk_results = plc_manager.plc.communicator.bulk_read_coils([
                    (start_addr, count)
                ])

                if start_addr in bulk_results:
                    bits = bulk_results[start_addr]

                    # Map coil states back to parameter IDs
                    for param_id, param_addr, _ in parameters:
                        coil_index = param_addr - start_addr
                        if 0 <= coil_index < len(bits):
                            results[param_id] = 1.0 if bits[coil_index] else 0.0

                    logger.debug(f"Bulk read {len(bits)} coils from addresses {start_addr}-{start_addr + count - 1}")

            except Exception as e:
                logger.error(f"Error in bulk coil read for range {start_addr}: {e}")
                # Fallback will handle individual reads

        return results

    async def _fallback_individual_reads(self, parameter_ids) -> Dict[str, float]:
        """
        Fallback to individual parameter reads when bulk operations fail.

        Args:
            parameter_ids: List of parameter IDs to read individually

        Returns:
            Dict mapping parameter_id to value
        """
        results = {}

        # Create tasks for concurrent individual reads (limited by semaphore)
        async def read_single_param(param_id):
            async with self._worker_semaphore:
                try:
                    value = await plc_manager.read_parameter(param_id)
                    if value is not None:
                        return param_id, float(value)
                except Exception as e:
                    logger.error(f"Error in fallback read for parameter {param_id}: {e}")
                return param_id, None

        # Execute individual reads with concurrency control
        tasks = [read_single_param(param_id) for param_id in parameter_ids]
        individual_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in individual_results:
            if isinstance(result, Exception):
                logger.error(f"Exception in individual parameter read: {result}")
                continue

            param_id, value = result
            if value is not None:
                results[param_id] = value

        logger.debug(f"Fallback individual reads: {len(results)}/{len(parameter_ids)} successful")
        return results

    async def _prepare_bulk_records(
        self,
        parameter_values: Dict[str, float],
        current_process_id: Optional[str],
        timestamp: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Prepare bulk records for database insertion.

        Args:
            parameter_values: Parameter values to log
            current_process_id: Current process ID if running
            timestamp: Current timestamp

        Returns:
            Tuple of (history_records, process_records)
        """
        history_records = []
        process_records = []

        for parameter_id, current_value in parameter_values.items():
            if current_value is None:
                continue

            # Get set_point from metadata cache
            param_meta = self._parameter_metadata_cache.get(parameter_id, {})
            set_point = param_meta.get('set_value')

            # Always add to parameter_value_history
            history_record = {
                'parameter_id': parameter_id,
                'value': current_value,
                'set_point': set_point,
                'timestamp': timestamp
            }
            history_records.append(history_record)

            # Additionally add to process_data_points if process is running
            if current_process_id:
                process_record = {
                    'process_id': current_process_id,
                    'parameter_id': parameter_id,
                    'value': current_value,
                    'set_point': set_point,
                    'timestamp': timestamp
                }
                process_records.append(process_record)

        return history_records, process_records

    async def _bulk_insert_records(
        self,
        history_records: List[Dict],
        process_records: List[Dict],
        current_process_id: Optional[str]
    ):
        """
        Execute bulk database insertions with optimized batch sizes.

        Args:
            history_records: Records for parameter_value_history
            process_records: Records for process_data_points
            current_process_id: Current process ID for logging
        """
        try:
            # Import here to avoid circular imports
            from src.db import get_supabase
            supabase = get_supabase()

            # Insert into parameter_value_history (always)
            if history_records:
                # Use larger batch sizes for better performance
                batch_size = 100
                for i in range(0, len(history_records), batch_size):
                    batch = history_records[i:i+batch_size]
                    supabase.table('parameter_value_history').insert(batch).execute()

            # Insert into process_data_points (only if process running)
            if process_records and current_process_id:
                batch_size = 100
                for i in range(0, len(process_records), batch_size):
                    batch = process_records[i:i+batch_size]
                    supabase.table('process_data_points').insert(batch).execute()

        except Exception as e:
            logger.error(f"Error in bulk database insertion: {str(e)}")
            raise

    async def _get_current_process_id(self) -> Optional[str]:
        """
        Get the current process ID if a process is running.

        Returns:
            str: Process ID if running, None if idle
        """
        try:
            from src.db import get_supabase
            supabase = get_supabase()
            result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()

            if result.data and result.data.get('status') == 'processing':
                return result.data.get('current_process_id')

            return None

        except Exception as e:
            logger.error(f"Error checking current process status: {str(e)}")
            return None

    async def _refresh_parameter_cache(self):
        """Refresh parameter metadata cache and rebuild parameter groups."""
        try:
            from src.db import get_supabase
            supabase = get_supabase()

            # Get parameter metadata
            result = supabase.table('component_parameters_full').select('*').execute()

            if result.data:
                # Update metadata cache
                self._parameter_metadata_cache = {}
                parameter_address_map = defaultdict(list)

                for param in result.data:
                    parameter_id = param['id']
                    read_addr = param.get('read_modbus_address')
                    data_type = param.get('data_type')

                    # Cache metadata
                    self._parameter_metadata_cache[parameter_id] = {
                        'set_value': param.get('set_value'),
                        'read_modbus_address': read_addr,
                        'data_type': data_type,
                        'name': param.get('parameter_name') or param.get('name'),
                        'component_name': param.get('component_name')
                    }

                    # Group by data type for bulk operations
                    if read_addr is not None:
                        parameter_address_map[data_type].append((parameter_id, read_addr))

                # Build parameter groups for bulk reading
                self._parameter_groups = []
                for data_type, param_list in parameter_address_map.items():
                    if param_list:
                        # Sort by address for potential range optimization
                        param_list.sort(key=lambda x: x[1])

                        # For now, create one group per data type
                        # TODO: Split into address ranges for true bulk reading
                        addresses = [addr for _, addr in param_list]
                        param_ids = [pid for pid, _ in param_list]

                        group = ParameterGroup(
                            data_type=data_type,
                            address_range=(min(addresses), max(addresses)),
                            parameter_ids=param_ids,
                            read_addresses=addresses
                        )
                        self._parameter_groups.append(group)

                self._last_cache_refresh = time.time()
                logger.info(f"Refreshed parameter cache: {len(self._parameter_metadata_cache)} parameters, {len(self._parameter_groups)} groups")

        except Exception as e:
            logger.error(f"Error refreshing parameter cache: {str(e)}")

    def _update_performance_metrics(self, metrics: PerformanceMetrics):
        """Update performance metrics history."""
        self._performance_metrics.append(metrics)

        # Keep only recent metrics
        if len(self._performance_metrics) > self._max_metrics_history:
            self._performance_metrics = self._performance_metrics[-self._max_metrics_history:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics.

        Returns:
            Dict with performance statistics
        """
        if not self._performance_metrics:
            return {}

        recent_metrics = self._performance_metrics[-60:]  # Last minute

        plc_times = [m.plc_read_time * 1000 for m in recent_metrics]
        db_times = [m.database_write_time * 1000 for m in recent_metrics]
        total_times = [m.total_cycle_time * 1000 for m in recent_metrics]
        jitters = [m.jitter_ms for m in recent_metrics]
        parameters_counts = [m.parameters_processed for m in recent_metrics]

        return {
            'is_running': self.is_running,
            'interval_seconds': self.interval,
            'max_workers': self.max_workers,
            'error_count': self._error_count,
            'last_successful_read': self._last_successful_read,
            'plc_connected': plc_manager.is_connected(),
            'recent_performance': {
                'cycles_analyzed': len(recent_metrics),
                'plc_read_time_ms': {
                    'avg': statistics.mean(plc_times) if plc_times else 0,
                    'min': min(plc_times) if plc_times else 0,
                    'max': max(plc_times) if plc_times else 0,
                    'p95': statistics.quantiles(plc_times, n=20)[18] if len(plc_times) > 20 else (max(plc_times) if plc_times else 0)
                },
                'database_write_time_ms': {
                    'avg': statistics.mean(db_times) if db_times else 0,
                    'min': min(db_times) if db_times else 0,
                    'max': max(db_times) if db_times else 0,
                    'p95': statistics.quantiles(db_times, n=20)[18] if len(db_times) > 20 else (max(db_times) if db_times else 0)
                },
                'total_cycle_time_ms': {
                    'avg': statistics.mean(total_times) if total_times else 0,
                    'min': min(total_times) if total_times else 0,
                    'max': max(total_times) if total_times else 0,
                    'p95': statistics.quantiles(total_times, n=20)[18] if len(total_times) > 20 else (max(total_times) if total_times else 0)
                },
                'jitter_ms': {
                    'avg': statistics.mean(jitters) if jitters else 0,
                    'min': min(jitters) if jitters else 0,
                    'max': max(jitters) if jitters else 0,
                    'p95': statistics.quantiles(jitters, n=20)[18] if len(jitters) > 20 else (max(jitters) if jitters else 0)
                },
                'parameters_processed': {
                    'avg': statistics.mean(parameters_counts) if parameters_counts else 0,
                    'min': min(parameters_counts) if parameters_counts else 0,
                    'max': max(parameters_counts) if parameters_counts else 0,
                    'total_last_minute': sum(parameters_counts)
                }
            },
            'parameter_groups': len(self._parameter_groups),
            'cached_parameters': len(self._parameter_metadata_cache),
            'cache_age_seconds': time.time() - self._last_cache_refresh
        }

    async def _record_sla_metrics(self, metrics: 'PerformanceMetrics'):
        """
        Record performance metrics for SLA monitoring.

        Args:
            metrics: Performance metrics from the logging cycle
        """
        try:
            # Record parameter logging interval (should be ~1000ms)
            interval_ms = metrics.total_cycle_time * 1000
            await performance_sla_monitor.record_measurement(
                'parameter_logging_interval',
                interval_ms,
                context={'parameters_processed': metrics.parameters_processed}
            )

            # Record parameter logging jitter
            await performance_sla_monitor.record_measurement(
                'parameter_logging_jitter',
                metrics.jitter_ms,
                context={'cycle_start_time': metrics.cycle_start_time}
            )

            # Record bulk read latency
            bulk_read_latency_ms = metrics.plc_read_time * 1000
            await performance_sla_monitor.record_measurement(
                'bulk_read_latency',
                bulk_read_latency_ms,
                context={'bulk_operations_used': True}
            )

            # Record database batch latency
            db_latency_ms = metrics.database_write_time * 1000
            await performance_sla_monitor.record_measurement(
                'database_batch_latency',
                db_latency_ms,
                context={'parameters_written': metrics.parameters_processed}
            )

            # Record end-to-end cycle time
            cycle_time_ms = metrics.total_cycle_time * 1000
            await performance_sla_monitor.record_measurement(
                'end_to_end_cycle_time',
                cycle_time_ms,
                context={'full_pipeline': True}
            )

            # Calculate and record parameter throughput
            if metrics.total_cycle_time > 0:
                throughput = metrics.parameters_processed / metrics.total_cycle_time
                await performance_sla_monitor.record_measurement(
                    'parameter_throughput',
                    throughput,
                    context={'cycle_duration_s': metrics.total_cycle_time}
                )

        except Exception as e:
            logger.error(f"Error recording SLA metrics: {e}")

    async def _smart_bulk_read_parameters(self) -> Dict[str, float]:
        """
        Smart parameter reading that can use distributed processing for large parameter sets.

        Returns:
            Dict mapping parameter_id to value
        """
        try:
            # Get all parameter IDs to read
            all_parameter_ids = list(self._parameter_metadata_cache.keys())

            if not all_parameter_ids:
                logger.warning("No parameters configured for reading")
                return {}

            # Use distributed processing for large parameter sets if enabled
            if (self._enable_distributed and
                len(all_parameter_ids) >= self._distributed_threshold and
                distributed_parameter_manager._is_running):

                logger.debug(f"Using distributed processing for {len(all_parameter_ids)} parameters")
                return await distributed_parameter_manager.distribute_parameter_reading(
                    all_parameter_ids, priority=1
                )
            else:
                # Use local bulk read optimization
                return await self._bulk_read_parameters()

        except Exception as e:
            logger.error(f"Error in smart bulk read: {e}")
            # Fallback to individual reads
            return await self._fallback_individual_reads(list(self._parameter_metadata_cache.keys()))

    async def enable_distributed_processing(self):
        """Enable distributed processing for high-scale operations."""
        if not distributed_parameter_manager._is_running:
            await distributed_parameter_manager.start()

            # Register ourselves as a local worker with bulk read capabilities
            await distributed_parameter_manager.register_worker(
                instance_type="local_process",
                capabilities={"bulk_read", "real_plc"},
                max_concurrent=self.max_workers
            )

            logger.info("Distributed processing enabled for high-performance logger")

    async def disable_distributed_processing(self):
        """Disable distributed processing and use only local operations."""
        self._enable_distributed = False
        logger.info("Distributed processing disabled - using local operations only")


# Global instance for compatibility
high_performance_parameter_logger = HighPerformanceParameterLogger()