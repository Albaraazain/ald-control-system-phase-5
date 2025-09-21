"""
High-Performance Parameter Logger for ALD Control System.

This module implements an async pipeline for continuous parameter logging with strict
1-second interval requirements, bulk operations, and connection pooling.
"""
import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import logging
from enum import Enum

from src.log_setup import logger
from src.config import MACHINE_ID


class LoggingMode(Enum):
    """Parameter logging modes."""
    IDLE = "idle"
    PROCESS = "process"


@dataclass
class ParameterGroup:
    """Groups parameters by data type and address ranges for bulk operations."""
    data_type: str
    addresses: List[int]
    parameter_ids: List[str]
    read_type: str  # 'holding', 'coil', 'input', 'discrete_input'


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring pipeline health."""
    cycle_start_time: float
    plc_read_duration: float
    database_write_duration: float
    total_cycle_duration: float
    parameters_processed: int
    jitter_ms: float
    errors: List[str]


class BulkParameterReader:
    """Optimized bulk PLC parameter reading with address range grouping."""

    def __init__(self, plc_communicator):
        """
        Initialize bulk reader.

        Args:
            plc_communicator: PLC communicator instance
        """
        self.communicator = plc_communicator
        self.parameter_groups = {}
        self._initialize_parameter_groups()

    def _initialize_parameter_groups(self):
        """Initialize parameter groups based on address ranges and data types."""
        # This will be populated from parameter metadata
        # Groups parameters by data type and creates contiguous address ranges
        logger.info("Initializing parameter groups for bulk reads")

    async def group_parameters_by_type_and_address(self, parameter_metadata: Dict[str, Dict[str, Any]]) -> Dict[str, List[ParameterGroup]]:
        """
        Group parameters by data type and address ranges for bulk operations.

        Args:
            parameter_metadata: Dictionary of parameter metadata

        Returns:
            Dictionary mapping data types to parameter groups
        """
        groups = defaultdict(list)

        # Group by data type
        type_groups = defaultdict(list)
        for param_id, metadata in parameter_metadata.items():
            data_type = metadata.get('data_type', 'unknown')
            read_addr = metadata.get('read_modbus_address')
            read_type = metadata.get('read_modbus_type', '').lower()

            if read_addr is not None:
                type_groups[data_type].append({
                    'param_id': param_id,
                    'address': read_addr,
                    'read_type': read_type or self._infer_read_type(data_type),
                    'metadata': metadata
                })

        # Create address-contiguous groups within each data type
        for data_type, params in type_groups.items():
            # Sort by address
            params.sort(key=lambda x: x['address'])

            # Group contiguous addresses
            current_group = []
            last_address = None

            for param in params:
                address = param['address']

                # Start new group if addresses aren't contiguous or different read types
                if (last_address is not None and
                    (address != last_address + 1 or
                     param['read_type'] != current_group[-1]['read_type'])):

                    if current_group:
                        groups[data_type].append(self._create_parameter_group(current_group))
                    current_group = []

                current_group.append(param)
                last_address = address

            # Add final group
            if current_group:
                groups[data_type].append(self._create_parameter_group(current_group))

        return dict(groups)

    def _infer_read_type(self, data_type: str) -> str:
        """Infer Modbus read type from data type."""
        if data_type == 'binary':
            return 'coil'
        else:
            return 'holding'

    def _create_parameter_group(self, params: List[Dict]) -> ParameterGroup:
        """Create a ParameterGroup from a list of parameters."""
        return ParameterGroup(
            data_type=params[0]['metadata']['data_type'],
            addresses=[p['address'] for p in params],
            parameter_ids=[p['param_id'] for p in params],
            read_type=params[0]['read_type']
        )

    async def bulk_read_parameters(self, parameter_groups: Dict[str, List[ParameterGroup]]) -> Dict[str, float]:
        """
        Perform bulk PLC reads using grouped parameters.

        Args:
            parameter_groups: Grouped parameters by data type

        Returns:
            Dictionary mapping parameter IDs to values
        """
        results = {}

        # Process groups concurrently by data type
        tasks = []
        for data_type, groups in parameter_groups.items():
            task = asyncio.create_task(self._read_data_type_groups(data_type, groups))
            tasks.append(task)

        # Wait for all bulk reads to complete
        group_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        for group_result in group_results:
            if isinstance(group_result, Exception):
                logger.error(f"Bulk read failed: {group_result}")
                continue
            results.update(group_result)

        return results

    async def _read_data_type_groups(self, data_type: str, groups: List[ParameterGroup]) -> Dict[str, float]:
        """Read all groups of a specific data type."""
        results = {}

        for group in groups:
            try:
                group_values = await self._read_parameter_group(group)
                results.update(group_values)
            except Exception as e:
                logger.error(f"Failed to read parameter group {group.data_type}: {e}")
                # Continue with other groups

        return results

    async def _read_parameter_group(self, group: ParameterGroup) -> Dict[str, float]:
        """Read a single parameter group using bulk Modbus operations."""
        results = {}

        if not group.addresses:
            return results

        start_addr = min(group.addresses)
        end_addr = max(group.addresses)
        count = end_addr - start_addr + 1

        try:
            if group.read_type == 'coil':
                # Bulk read coils
                raw_values = await asyncio.get_event_loop().run_in_executor(
                    None, self.communicator.read_coils, start_addr, count
                )
                if raw_values:
                    for i, param_id in enumerate(group.parameter_ids):
                        addr_offset = group.addresses[i] - start_addr
                        results[param_id] = 1.0 if raw_values[addr_offset] else 0.0

            elif group.read_type in ('holding', 'input'):
                # Bulk read holding registers
                if group.data_type == 'float':
                    # Float requires 2 registers per value
                    values = await self._bulk_read_floats(start_addr, len(group.parameter_ids))
                    for i, param_id in enumerate(group.parameter_ids):
                        if i < len(values) and values[i] is not None:
                            results[param_id] = values[i]

                elif group.data_type == 'int32':
                    # int32 requires 2 registers per value
                    values = await self._bulk_read_int32s(start_addr, len(group.parameter_ids))
                    for i, param_id in enumerate(group.parameter_ids):
                        if i < len(values) and values[i] is not None:
                            results[param_id] = float(values[i])

                elif group.data_type == 'int16':
                    # int16 requires 1 register per value
                    raw_values = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.communicator.client.read_holding_registers(
                            start_addr, count, slave=self.communicator.slave_id
                        )
                    )
                    if raw_values and not raw_values.isError():
                        for i, param_id in enumerate(group.parameter_ids):
                            addr_offset = group.addresses[i] - start_addr
                            if addr_offset < len(raw_values.registers):
                                results[param_id] = float(raw_values.registers[addr_offset])

        except Exception as e:
            logger.error(f"Error reading parameter group: {e}")
            # Fall back to individual reads for this group
            for param_id in group.parameter_ids:
                try:
                    # This would use the existing individual read method as fallback
                    results[param_id] = None
                except Exception:
                    pass

        return results

    async def _bulk_read_floats(self, start_addr: int, count: int) -> List[Optional[float]]:
        """Bulk read float values from contiguous addresses."""
        register_count = count * 2  # 2 registers per float

        try:
            raw_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.communicator.client.read_holding_registers(
                    start_addr, register_count, slave=self.communicator.slave_id
                )
            )

            if raw_result.isError():
                logger.error(f"Bulk float read failed: {raw_result}")
                return [None] * count

            # Convert register pairs to floats
            values = []
            for i in range(count):
                reg_offset = i * 2
                if reg_offset + 1 < len(raw_result.registers):
                    # Use communicator's byte order logic
                    float_val = self._registers_to_float(
                        raw_result.registers[reg_offset],
                        raw_result.registers[reg_offset + 1]
                    )
                    values.append(float_val)
                else:
                    values.append(None)

            return values

        except Exception as e:
            logger.error(f"Exception in bulk float read: {e}")
            return [None] * count

    async def _bulk_read_int32s(self, start_addr: int, count: int) -> List[Optional[int]]:
        """Bulk read int32 values from contiguous addresses."""
        register_count = count * 2  # 2 registers per int32

        try:
            raw_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.communicator.client.read_holding_registers(
                    start_addr, register_count, slave=self.communicator.slave_id
                )
            )

            if raw_result.isError():
                logger.error(f"Bulk int32 read failed: {raw_result}")
                return [None] * count

            # Convert register pairs to int32
            values = []
            for i in range(count):
                reg_offset = i * 2
                if reg_offset + 1 < len(raw_result.registers):
                    int_val = self._registers_to_int32(
                        raw_result.registers[reg_offset],
                        raw_result.registers[reg_offset + 1]
                    )
                    values.append(int_val)
                else:
                    values.append(None)

            return values

        except Exception as e:
            logger.error(f"Exception in bulk int32 read: {e}")
            return [None] * count

    def _registers_to_float(self, reg1: int, reg2: int) -> float:
        """Convert two registers to float using communicator's byte order."""
        import struct

        byte_order = getattr(self.communicator, 'byte_order', 'badc')

        if byte_order == 'abcd':  # Big-endian
            raw_data = struct.pack('>HH', reg1, reg2)
            return struct.unpack('>f', raw_data)[0]
        elif byte_order == 'badc':  # Big-byte/little-word
            raw_data = struct.pack('>HH', reg2, reg1)
            return struct.unpack('>f', raw_data)[0]
        elif byte_order == 'cdab':  # Little-byte/big-word
            raw_data = struct.pack('<HH', reg1, reg2)
            return struct.unpack('<f', raw_data)[0]
        elif byte_order == 'dcba':  # Little-endian
            raw_data = struct.pack('<HH', reg2, reg1)
            return struct.unpack('<f', raw_data)[0]
        else:
            # Default to 'badc'
            raw_data = struct.pack('>HH', reg2, reg1)
            return struct.unpack('>f', raw_data)[0]

    def _registers_to_int32(self, reg1: int, reg2: int) -> int:
        """Convert two registers to int32 using communicator's byte order."""
        import struct

        byte_order = getattr(self.communicator, 'byte_order', 'badc')

        if byte_order == 'abcd':  # Big-endian
            raw_data = struct.pack('>HH', reg1, reg2)
            return struct.unpack('>i', raw_data)[0]
        elif byte_order == 'badc':  # Big-byte/little-word
            raw_data = struct.pack('>HH', reg2, reg1)
            return struct.unpack('>i', raw_data)[0]
        elif byte_order == 'cdab':  # Little-byte/big-word
            raw_data = struct.pack('<HH', reg1, reg2)
            return struct.unpack('<i', raw_data)[0]
        elif byte_order == 'dcba':  # Little-endian
            raw_data = struct.pack('<HH', reg2, reg1)
            return struct.unpack('<i', raw_data)[0]
        else:
            # Default to 'badc'
            raw_data = struct.pack('>HH', reg2, reg1)
            return struct.unpack('>i', raw_data)[0]


class AsyncBatchProcessor:
    """Async database batch processor with transaction management."""

    def __init__(self, db_pool, batch_size: int = 200):
        """
        Initialize batch processor.

        Args:
            db_pool: Async database connection pool
            batch_size: Maximum batch size for operations
        """
        self.db_pool = db_pool
        self.batch_size = batch_size

    async def batch_insert_parameters(
        self,
        history_records: List[Dict[str, Any]],
        process_records: List[Dict[str, Any]] = None
    ) -> bool:
        """
        Batch insert parameter data with transaction management.

        Args:
            history_records: Records for parameter_value_history table
            process_records: Records for process_data_points table (if process running)

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    # Insert history records in batches
                    if history_records:
                        await self._batch_insert_table(
                            conn, 'parameter_value_history', history_records
                        )

                    # Insert process records in batches (if any)
                    if process_records:
                        await self._batch_insert_table(
                            conn, 'process_data_points', process_records
                        )

                    return True

        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            return False

    async def _batch_insert_table(
        self,
        conn,
        table_name: str,
        records: List[Dict[str, Any]]
    ):
        """Insert records into a table using batched operations."""
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]

            # Use prepared statement for better performance
            if table_name == 'parameter_value_history':
                await self._insert_history_batch(conn, batch)
            elif table_name == 'process_data_points':
                await self._insert_process_batch(conn, batch)

    async def _insert_history_batch(self, conn, batch: List[Dict[str, Any]]):
        """Insert batch into parameter_value_history table."""
        # Prepare bulk insert query
        values = []
        for record in batch:
            values.extend([
                record['parameter_id'],
                record['value'],
                record.get('set_point'),
                record['timestamp']
            ])

        # Use asyncpg's executemany for optimal performance
        query = """
            INSERT INTO parameter_value_history
            (parameter_id, value, set_point, timestamp)
            VALUES ($1, $2, $3, $4)
        """

        # Prepare data as list of tuples
        data = [
            (r['parameter_id'], r['value'], r.get('set_point'), r['timestamp'])
            for r in batch
        ]

        await conn.executemany(query, data)

    async def _insert_process_batch(self, conn, batch: List[Dict[str, Any]]):
        """Insert batch into process_data_points table."""
        query = """
            INSERT INTO process_data_points
            (process_id, parameter_id, value, set_point, timestamp)
            VALUES ($1, $2, $3, $4, $5)
        """

        data = [
            (r['process_id'], r['parameter_id'], r['value'], r.get('set_point'), r['timestamp'])
            for r in batch
        ]

        await conn.executemany(query, data)


class PerformanceMonitor:
    """Real-time performance monitoring for pipeline health."""

    def __init__(self, target_interval: float = 1.0):
        """
        Initialize performance monitor.

        Args:
            target_interval: Target interval in seconds
        """
        self.target_interval = target_interval
        self.metrics_history = []
        self.max_history = 100  # Keep last 100 cycles

    def start_cycle(self) -> float:
        """Start timing a logging cycle."""
        return time.time()

    def record_metrics(self, metrics: PerformanceMetrics):
        """Record performance metrics for a cycle."""
        self.metrics_history.append(metrics)

        # Keep only recent history
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)

        # Log performance issues
        if metrics.jitter_ms > 50:  # More than 50ms jitter
            logger.warning(f"High jitter detected: {metrics.jitter_ms:.1f}ms")

        if metrics.total_cycle_duration > self.target_interval * 1.5:
            logger.warning(f"Slow cycle: {metrics.total_cycle_duration:.3f}s")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        if not self.metrics_history:
            return {}

        recent_metrics = self.metrics_history[-10:]  # Last 10 cycles

        jitters = [m.jitter_ms for m in recent_metrics]
        cycle_times = [m.total_cycle_duration for m in recent_metrics]
        plc_times = [m.plc_read_duration for m in recent_metrics]
        db_times = [m.database_write_duration for m in recent_metrics]

        return {
            'avg_jitter_ms': sum(jitters) / len(jitters),
            'max_jitter_ms': max(jitters),
            'avg_cycle_time': sum(cycle_times) / len(cycle_times),
            'avg_plc_time': sum(plc_times) / len(plc_times),
            'avg_db_time': sum(db_times) / len(db_times),
            'cycles_processed': len(self.metrics_history),
            'error_rate': sum(1 for m in recent_metrics if m.errors) / len(recent_metrics)
        }


class HighPerformanceParameterLogger:
    """
    High-performance async parameter logger with bulk operations and strict timing.

    This class implements the main async pipeline for continuous parameter logging
    with performance optimizations for meeting 1-second interval requirements.
    """

    def __init__(
        self,
        plc_manager,
        db_pool,
        interval_seconds: float = 1.0,
        batch_size: int = 200,
        max_workers: int = 4
    ):
        """
        Initialize high-performance parameter logger.

        Args:
            plc_manager: PLC manager instance
            db_pool: Async database connection pool
            interval_seconds: Logging interval in seconds
            batch_size: Database batch size
            max_workers: Maximum concurrent workers
        """
        self.plc_manager = plc_manager
        self.db_pool = db_pool
        self.interval = interval_seconds
        self.batch_size = batch_size
        self.max_workers = max_workers

        # Components
        self.bulk_reader = None  # Will be initialized when PLC is available
        self.batch_processor = AsyncBatchProcessor(db_pool, batch_size)
        self.performance_monitor = PerformanceMonitor(interval_seconds)

        # State
        self.is_running = False
        self._task = None
        self._parameter_groups = {}
        self._parameter_metadata = {}

        # Performance tracking
        self._cycle_count = 0
        self._error_count = 0
        self._last_successful_read = None

    async def start(self):
        """Start high-performance parameter logging."""
        if self.is_running:
            logger.warning("High-performance parameter logger is already running")
            return

        logger.info("Starting high-performance parameter logging pipeline")

        # Initialize bulk reader if PLC is available
        if self.plc_manager.is_connected() and self.plc_manager.plc:
            self.bulk_reader = BulkParameterReader(self.plc_manager.plc.communicator)
            await self._initialize_parameter_groups()

        self.is_running = True
        self._task = asyncio.create_task(self._high_performance_logging_loop())

        logger.info("High-performance parameter logging pipeline started")

    async def stop(self):
        """Stop the high-performance parameter logging."""
        if not self.is_running:
            return

        logger.info("Stopping high-performance parameter logging pipeline")

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("High-performance parameter logging pipeline stopped")

    async def _initialize_parameter_groups(self):
        """Initialize parameter groups for bulk operations."""
        try:
            # Get parameter metadata from PLC
            if hasattr(self.plc_manager.plc, '_parameter_cache'):
                self._parameter_metadata = self.plc_manager.plc._parameter_cache.copy()

                # Group parameters for bulk operations
                self._parameter_groups = await self.bulk_reader.group_parameters_by_type_and_address(
                    self._parameter_metadata
                )

                logger.info(f"Initialized {len(self._parameter_groups)} parameter groups for bulk operations")

        except Exception as e:
            logger.error(f"Failed to initialize parameter groups: {e}")

    async def _high_performance_logging_loop(self):
        """High-performance logging loop with timing precision."""
        try:
            while self.is_running:
                cycle_start = self.performance_monitor.start_cycle()

                try:
                    # Execute logging cycle
                    metrics = await self._execute_logging_cycle(cycle_start)

                    # Record performance metrics
                    self.performance_monitor.record_metrics(metrics)

                    self._cycle_count += 1
                    self._error_count = 0  # Reset on success
                    self._last_successful_read = time.time()

                except Exception as e:
                    self._error_count += 1
                    logger.error(f"Error in logging cycle {self._cycle_count}: {e}", exc_info=True)

                    # Record error metrics
                    error_metrics = PerformanceMetrics(
                        cycle_start_time=cycle_start,
                        plc_read_duration=0.0,
                        database_write_duration=0.0,
                        total_cycle_duration=time.time() - cycle_start,
                        parameters_processed=0,
                        jitter_ms=0.0,
                        errors=[str(e)]
                    )
                    self.performance_monitor.record_metrics(error_metrics)

                # Calculate sleep time for precise interval
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("High-performance logging loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in high-performance logging loop: {e}", exc_info=True)
            self.is_running = False

    async def _execute_logging_cycle(self, cycle_start: float) -> PerformanceMetrics:
        """Execute a single high-performance logging cycle."""
        errors = []

        # Check PLC connection
        if not self.plc_manager.is_connected():
            raise RuntimeError("PLC not connected")

        # Get current process state
        plc_start = time.time()
        current_process_id, logging_mode = await self._get_machine_state()

        # Perform bulk parameter reads
        parameter_values = {}
        if self.bulk_reader and self._parameter_groups:
            try:
                parameter_values = await self.bulk_reader.bulk_read_parameters(self._parameter_groups)
            except Exception as e:
                errors.append(f"Bulk read failed: {e}")
                # Fallback to individual reads
                parameter_values = await self._fallback_individual_reads()
        else:
            # Fallback if bulk reader not available
            parameter_values = await self._fallback_individual_reads()

        plc_duration = time.time() - plc_start

        if not parameter_values:
            raise RuntimeError("No parameters read from PLC")

        # Prepare database records
        db_start = time.time()
        history_records, process_records = await self._prepare_database_records(
            parameter_values, current_process_id, logging_mode
        )

        # Batch insert to database
        success = await self.batch_processor.batch_insert_parameters(
            history_records, process_records
        )

        if not success:
            errors.append("Database batch insert failed")

        db_duration = time.time() - db_start

        # Calculate metrics
        total_duration = time.time() - cycle_start
        target_end_time = cycle_start + self.interval
        jitter_ms = abs(time.time() - target_end_time) * 1000

        return PerformanceMetrics(
            cycle_start_time=cycle_start,
            plc_read_duration=plc_duration,
            database_write_duration=db_duration,
            total_cycle_duration=total_duration,
            parameters_processed=len(parameter_values),
            jitter_ms=jitter_ms,
            errors=errors
        )

    async def _get_machine_state(self) -> Tuple[Optional[str], LoggingMode]:
        """Get current machine state for logging mode determination."""
        try:
            # This would integrate with the transactional state management
            # For now, using the existing approach but optimized

            # Use connection pool for state query
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT current_process_id, status FROM machines WHERE id = $1",
                    MACHINE_ID
                )

                if result and result['status'] == 'processing':
                    return result['current_process_id'], LoggingMode.PROCESS
                else:
                    return None, LoggingMode.IDLE

        except Exception as e:
            logger.error(f"Error checking machine state: {e}")
            return None, LoggingMode.IDLE

    async def _fallback_individual_reads(self) -> Dict[str, float]:
        """Fallback to individual parameter reads if bulk operations fail."""
        try:
            return await self.plc_manager.read_all_parameters()
        except Exception as e:
            logger.error(f"Fallback individual reads failed: {e}")
            return {}

    async def _prepare_database_records(
        self,
        parameter_values: Dict[str, float],
        current_process_id: Optional[str],
        logging_mode: LoggingMode
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Prepare database records for batch insertion."""
        from src.db import get_current_timestamp

        timestamp = get_current_timestamp()
        history_records = []
        process_records = []

        # Get parameter metadata efficiently
        metadata_map = await self._get_parameter_metadata_batch(list(parameter_values.keys()))

        for parameter_id, current_value in parameter_values.items():
            if current_value is None:
                continue

            set_point = metadata_map.get(parameter_id, {}).get('set_value')

            # Always add to parameter_value_history
            history_record = {
                'parameter_id': parameter_id,
                'value': current_value,
                'set_point': set_point,
                'timestamp': timestamp
            }
            history_records.append(history_record)

            # Add to process_data_points if in process mode
            if logging_mode == LoggingMode.PROCESS and current_process_id:
                process_record = {
                    'process_id': current_process_id,
                    'parameter_id': parameter_id,
                    'value': current_value,
                    'set_point': set_point,
                    'timestamp': timestamp
                }
                process_records.append(process_record)

        return history_records, process_records

    async def _get_parameter_metadata_batch(self, parameter_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get parameter metadata in batch for efficiency."""
        try:
            async with self.db_pool.acquire() as conn:
                results = await conn.fetch(
                    "SELECT id, set_value FROM component_parameters WHERE id = ANY($1)",
                    parameter_ids
                )

                metadata = {}
                for row in results:
                    metadata[row['id']] = {'set_value': row['set_value']}

                return metadata

        except Exception as e:
            logger.error(f"Error getting parameter metadata: {e}")
            return {}

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the high-performance logger."""
        performance_summary = self.performance_monitor.get_performance_summary()

        return {
            'is_running': self.is_running,
            'interval_seconds': self.interval,
            'cycle_count': self._cycle_count,
            'error_count': self._error_count,
            'last_successful_read': self._last_successful_read,
            'plc_connected': self.plc_manager.is_connected(),
            'parameter_groups': len(self._parameter_groups),
            'parameters_cached': len(self._parameter_metadata),
            'performance': performance_summary
        }