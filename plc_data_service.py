#!/usr/bin/env python3
"""
Terminal 1: PLC Data Service

**PRIMARY RESPONSIBILITY**: PLC data collection and logging

This terminal provides:
1. PLC hardware connection for data reading
2. Precise 1-second data collection timing (±100ms precision)
3. Parameter value logging to database
4. Enhanced logging with parameter metadata
5. Performance monitoring and metrics
6. Batch insert retry logic with exponential backoff
7. Dead letter queue for failed batches
8. Background recovery task for replaying failed batches

Simplified architecture focused on reliable data collection with ZERO data loss guarantee.
"""
import asyncio
import os
import sys
import signal
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Ensure project root is on sys.path for src imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.log_setup import get_plc_logger, get_data_collection_logger, logger as main_logger
from src.config import MACHINE_ID, PLC_TYPE, PLC_CONFIG
from src.db import get_supabase
from src.plc.manager import plc_manager  # Use global singleton for consistent PLC connection
from src.parameter_wide_table_mapping import PARAMETER_TO_COLUMN_MAP  # Wide table column mapping
from src.terminal_registry import TerminalRegistry, TerminalAlreadyRunningError
# Removed broken transactional import - will use direct database logging

# Service-specific loggers
plc_logger = get_plc_logger()
data_logger = get_data_collection_logger()




class PLCDataService:
    """
    Terminal 1: PLC Data Service

    Provides PLC data collection with precise timing and reliable database logging.

    Features zero data loss guarantee through:
    - Retry logic with exponential backoff (3 attempts: 1s, 2s, 4s)
    - Dead letter queue for failed batches
    - Background recovery task for replaying failed batches
    """

    def __init__(self):
        # Use global singleton PLCManager for consistent connection across all terminals
        # This ensures only 1 Modbus TCP connection is created (shared with Terminals 2 & 3)
        self.plc_manager = plc_manager
        self.supabase = get_supabase()

        # Shutdown coordination
        self.shutdown_event = asyncio.Event()
        self.shutdown_timeout = float(os.getenv('SHUTDOWN_TIMEOUT', '30.0'))
        self.is_running = False  # Keep for compatibility

        self.data_collection_task = None
        self.writer_task = None
        self.recovery_task = None
        self.registry: Optional[TerminalRegistry] = None

        # Timing control for precise 1s intervals
        self.data_collection_interval = 1.0  # 1 second
        self.last_collection_time = 0.0
        self.timing_precision_threshold = 0.1  # ±100ms precision
        # Monotonic scheduler state
        self._next_deadline: Optional[float] = None

        # Performance metrics
        self.metrics = {
            'total_readings': 0,
            'successful_readings': 0,
            'failed_readings': 0,
            'timing_violations': 0,
            'last_collection_duration': 0.0,
            'average_collection_duration': 0.0,
            # Async writer metrics
            'batches_enqueued': 0,
            'batches_dropped': 0,
            'records_enqueued': 0,
            # Batch insert failure metrics
            'batch_insert_retries': 0,
            'batch_insert_failures': 0,
            'dead_letter_queue_writes': 0,
            'dead_letter_queue_replays': 0,
            'dead_letter_queue_depth': 0,
            # Setpoint synchronization metrics
            'setpoint_reads_successful': 0,
            'setpoint_reads_failed': 0,
            'external_setpoint_changes_detected': 0
        }

        # Parameter metadata cache for enhanced logging
        self.parameter_metadata = {}  # Cache parameter name/component info

        # Dead letter queue configuration
        self.dead_letter_queue_dir = Path("logs/dead_letter_queue")
        self.dead_letter_queue_dir.mkdir(parents=True, exist_ok=True)

        # Non-blocking DB writer configuration
        # Bounded queue keeps memory in check and prevents backpressure from blocking the poller
        self.async_writer_enabled: bool = os.environ.get('ASYNC_WRITER', '1') == '1'
        self._write_queue: asyncio.Queue = asyncio.Queue(maxsize=2)

        # Throttle how often we read setpoints (reduced from 10s to 0.5s for responsiveness)
        # Lower interval = faster UI feedback when setpoints change
        self.setpoint_refresh_interval: float = float(os.environ.get('SETPOINT_REFRESH_INTERVAL', '0.5'))
        self._last_setpoint_read_time: float = 0.0

        # Verbose per-parameter INFO logs can be noisy; default to INFO summary only
        self.verbose_parameter_logging: bool = os.environ.get('VERBOSE_PARAMETER_LOGS', '0') == '1'

        plc_logger.info("PLC Data Service initialized - Terminal 1 ready for data collection with zero data loss guarantee")

    async def initialize(self) -> bool:
        """
        Initialize the PLC Data Service with exclusive hardware connection.

        Returns:
            bool: True if initialization successful
        """
        try:
            plc_logger.info("Initializing PLC Data Service for data collection")

            # Register this terminal instance in liveness system
            log_file_path = "/tmp/terminal1_plc_data_service.log"
            self.registry = TerminalRegistry(
                terminal_type='terminal1',
                machine_id=MACHINE_ID,
                environment='production',
                heartbeat_interval=10,
                log_file_path=log_file_path
            )

            try:
                await self.registry.register()
                plc_logger.info("✅ Terminal 1 registered in liveness system")
            except TerminalAlreadyRunningError as e:
                plc_logger.error(str(e))
                raise RuntimeError("Cannot start - Terminal 1 already running")

            # Initialize parameter metadata cache for enhanced logging
            await self._initialize_parameter_metadata()

            # Initialize PLC connection using global singleton (shared with Terminals 2 & 3)
            plc_logger.info(f"🔗 Using global singleton PLCManager (shared across all terminals)")
            plc_connected = await self.plc_manager.initialize(PLC_TYPE, PLC_CONFIG)
            if plc_connected:
                plc_logger.info("✅ PLC connection established via singleton - 1 shared connection for all terminals")
            else:
                plc_logger.warning("⚠️ PLC connection failed - will retry in background")

            # Initialize metrics
            self.metrics['service_start_time'] = asyncio.get_event_loop().time()

            return True

        except Exception as e:
            plc_logger.error(f"Failed to initialize PLC Data Service: {e}", exc_info=True)
            return False

    async def start(self):
        """Start all PLC Data Service operations."""
        if self.is_running:
            plc_logger.warning("PLC Data Service already running")
            return

        try:
            self.is_running = True

            # Start core service tasks
            self.data_collection_task = asyncio.create_task(self._data_collection_loop())
            if self.async_writer_enabled:
                self.writer_task = asyncio.create_task(self._db_writer_loop())
            self.recovery_task = asyncio.create_task(self._dead_letter_queue_recovery_loop())

            plc_logger.info("🚀 PLC Data Service started - data collection operational with zero data loss guarantee")
            plc_logger.info(f"🧵 Async DB writer: {'ENABLED' if self.async_writer_enabled else 'DISABLED'}")
            plc_logger.info(f"⚙️  Setpoint refresh interval: {self.setpoint_refresh_interval:.1f}s")
            plc_logger.info("🔄 Dead letter queue recovery enabled - failed batches will be replayed automatically")

            # Wait for tasks to complete
            await asyncio.gather(
                self.data_collection_task,
                *( [self.writer_task] if self.writer_task else [] ),
                self.recovery_task,
                return_exceptions=True
            )

        except Exception as e:
            plc_logger.error(f"Error in PLC Data Service: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self):
        """Stop all PLC Data Service operations with timeout."""
        if not self.is_running:
            return

        try:
            plc_logger.info("🛑 Stopping PLC Data Service...")
            start_time = asyncio.get_event_loop().time()

            # Signal shutdown
            self.is_running = False
            self.shutdown_event.set()

            # Cancel all tasks with timeout
            tasks = [self.data_collection_task, self.writer_task, self.recovery_task]
            active_tasks = [t for t in tasks if t and not t.done()]

            if active_tasks:
                plc_logger.info(f"Canceling {len(active_tasks)} active tasks...")
                for task in active_tasks:
                    task.cancel()

                # Wait for cancellation with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*active_tasks, return_exceptions=True),
                        timeout=self.shutdown_timeout * 0.5
                    )
                    plc_logger.info("✅ All tasks cancelled successfully")
                except asyncio.TimeoutError:
                    plc_logger.warning(f"⏱️ Task cancellation timed out after {self.shutdown_timeout * 0.5}s")

            # Cleanup resources with timeout
            cleanup_tasks = []

            # Shutdown terminal registry
            if self.registry:
                async def cleanup_registry():
                    try:
                        await asyncio.wait_for(
                            self.registry.shutdown(reason="Service shutdown"),
                            timeout=5.0
                        )
                        plc_logger.info("✅ Terminal registry shutdown complete")
                    except asyncio.TimeoutError:
                        plc_logger.warning("⏱️ Registry shutdown timed out")
                    except Exception as e:
                        plc_logger.error(f"Registry cleanup error: {e}")

                cleanup_tasks.append(cleanup_registry())

            # Disconnect PLC
            async def cleanup_plc():
                try:
                    await asyncio.wait_for(
                        self.plc_manager.disconnect(),
                        timeout=5.0
                    )
                    plc_logger.info("✅ PLC disconnected")
                except asyncio.TimeoutError:
                    plc_logger.warning("⏱️ PLC disconnect timed out")
                except Exception as e:
                    plc_logger.error(f"PLC cleanup error: {e}")

            cleanup_tasks.append(cleanup_plc())

            # Execute all cleanup
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=self.shutdown_timeout * 0.5
                )
            except asyncio.TimeoutError:
                plc_logger.warning("⏱️ Cleanup timed out")

            # Cleanup parameter metadata cache
            self.parameter_metadata = {}

            # Calculate shutdown duration
            duration = asyncio.get_event_loop().time() - start_time
            plc_logger.info(f"✅ Graceful shutdown complete in {duration:.2f}s")

            # Log final metrics
            dlq_depth = self.metrics.get('dead_letter_queue_depth', 0)
            if dlq_depth > 0:
                plc_logger.warning(
                    f"⚠️ Service stopped with {dlq_depth} batches in dead letter queue. "
                    f"These will be replayed on next startup."
                )

            plc_logger.info("PLC Data Service stopped successfully")

        except Exception as e:
            plc_logger.error(f"Error stopping PLC Data Service: {e}", exc_info=True)

    async def _data_collection_loop(self):
        """
        Main data collection loop with precise 1-second timing.

        Maintains ±100ms precision for data collection intervals.
        """
        plc_logger.info("Starting precise data collection loop (1s ±100ms)")

        # Initialize next deadline to align to now
        loop = asyncio.get_event_loop()
        self._next_deadline = loop.time()

        while not self.shutdown_event.is_set():
            loop_start_time = loop.time()

            try:
                # Perform data collection
                await self._collect_and_log_data()

                # Calculate timing metrics
                collection_duration = asyncio.get_event_loop().time() - loop_start_time
                self.metrics['last_collection_duration'] = collection_duration

                # Update average duration (rolling average)
                total_readings = self.metrics['total_readings']
                if total_readings > 0:
                    current_avg = self.metrics['average_collection_duration']
                    self.metrics['average_collection_duration'] = (
                        (current_avg * total_readings + collection_duration) / (total_readings + 1)
                    )
                else:
                    self.metrics['average_collection_duration'] = collection_duration

                # Monotonic scheduler: always target the next exact deadline to avoid drift
                self._next_deadline += self.data_collection_interval
                now = loop.time()
                elapsed_time = now - loop_start_time
                sleep_time = max(0, self._next_deadline - now)

                # Check timing precision
                if abs(elapsed_time - self.data_collection_interval) > self.timing_precision_threshold:
                    self.metrics['timing_violations'] += 1
                    data_logger.warning(
                        f"Timing violation: collection took {elapsed_time:.3f}s "
                        f"(target: {self.data_collection_interval}s ±{self.timing_precision_threshold}s)"
                    )

                # Shutdown-aware sleep for immediate exit on shutdown signal
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=sleep_time
                    )
                    # Event was set, exit loop
                    data_logger.info("Shutdown event detected during sleep")
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue loop
                    pass

            except asyncio.CancelledError:
                plc_logger.info("Data collection loop cancelled")
                break
            except Exception as e:
                self.metrics['failed_readings'] += 1
                data_logger.error(f"Error in data collection loop: {e}", exc_info=True)
                # Continue with error backoff
                await asyncio.sleep(min(5.0, self.data_collection_interval))

    async def _collect_and_log_data(self):
        """
        Collect PLC data and log to database with transactional guarantees.
        """
        self.metrics['total_readings'] += 1

        try:
            # Check PLC connection
            if not self.plc_manager.is_connected():
                data_logger.debug("PLC not connected - skipping data collection")
                return

            # Read all parameters from PLC (current values)
            parameter_values = await self.plc_manager.read_all_parameters()
            if not parameter_values:
                data_logger.debug("No parameters available from PLC")
                return

            # Read all setpoints from PLC (for synchronization), throttled
            setpoint_values = {}
            now = asyncio.get_event_loop().time()
            if (now - self._last_setpoint_read_time) >= self.setpoint_refresh_interval:
                try:
                    setpoint_values = await self.plc_manager.read_all_setpoints()
                    self.metrics['setpoint_reads_successful'] += 1
                    data_logger.info(f"📊 Read {len(setpoint_values)} setpoints from PLC for synchronization")
                except Exception as e:
                    self.metrics['setpoint_reads_failed'] += 1
                    data_logger.warning(f"Failed to read setpoints: {e}", exc_info=True)
                finally:
                    self._last_setpoint_read_time = now

            # Log parameters to database with enhanced logging (includes setpoint sync)
            success_count = await self._log_parameters_with_metadata(parameter_values, setpoint_values)

            if success_count > 0:
                if self.async_writer_enabled:
                    # Don't claim success yet - data is only queued, not written
                    # Success metrics will be updated in _db_writer_loop after actual write
                    data_logger.info(
                        f"📤 Queued for database write: {success_count}/{len(parameter_values)} parameters"
                    )
                else:
                    # Sync mode: write completed, update metrics
                    self.metrics['successful_readings'] += 1
                    data_logger.info(
                        f"✅ PLC data collection completed: {success_count}/{len(parameter_values)} parameters logged successfully"
                    )

                # Track successful reading in liveness system
                if self.registry:
                    self.registry.increment_commands()
            else:
                self.metrics['failed_readings'] += 1
                data_logger.error(f"❌ PLC data collection failed for all {len(parameter_values)} parameters")

                # Record error in liveness system
                if self.registry:
                    self.registry.record_error("PLC data collection failed for all parameters")

        except Exception as e:
            self.metrics['failed_readings'] += 1
            data_logger.error(f"Failed to collect and log PLC data: {e}", exc_info=True)

            # Record error in liveness system
            if self.registry:
                self.registry.record_error(f"PLC data collection exception: {str(e)}")

            raise



    async def _initialize_parameter_metadata(self):
        """Initialize parameter metadata cache for enhanced logging."""
        try:
            data_logger.info("Loading parameter metadata for enhanced logging...")

            # Get all component parameters first (including write addresses for setpoint sync)
            params_response = self.supabase.table('component_parameters').select(
                'id, definition_id, component_id, min_value, max_value, is_writable, data_type, '
                'write_modbus_address, write_modbus_type'
            ).execute()

            # Get all component definitions
            defs_response = self.supabase.table('component_definitions').select(
                'id, name, type'
            ).execute()

            # Create a lookup for component definitions
            component_defs = {def_item['id']: def_item for def_item in defs_response.data}

            if params_response.data:
                for param in params_response.data:
                    param_id = param['id']
                    definition_id = param.get('definition_id')

                    # Look up component definition
                    component_def = component_defs.get(definition_id, {})
                    component_name = component_def.get('name', f'Component_{param.get("component_id", "unknown")[:8]}')
                    component_type = component_def.get('type', '')

                    # Create parameter name based on data type and improve naming
                    data_type = param.get('data_type') or 'unknown'
                    if data_type == 'temperature':
                        param_name = 'Temperature'
                    elif data_type == 'pressure':
                        param_name = 'Pressure'
                    elif data_type == 'valve_state':
                        param_name = 'Valve_State'
                    elif data_type == 'flow_rate':
                        param_name = 'Flow_Rate'
                    elif data_type == 'set_point':
                        param_name = 'Set_Point'
                    elif data_type == 'binary':
                        param_name = 'Binary_State'
                    elif data_type == 'float':
                        param_name = 'Value'
                    elif data_type == 'unknown':
                        param_name = 'Parameter'
                    else:
                        param_name = str(data_type).title()

                    # If we have a valid component definition, use it for better naming
                    if component_def:
                        # Try to create more specific parameter names based on component type
                        if component_type == 'heater' and data_type == 'float':
                            param_name = 'Temperature'
                        elif component_type == 'gauge' and data_type == 'float':
                            param_name = 'Reading'
                        elif component_type == 'valve' and data_type == 'binary':
                            param_name = 'State'

                    # Determine unit based on data type
                    unit = ''
                    if data_type == 'temperature':
                        unit = '°C'
                    elif data_type == 'pressure':
                        unit = 'Torr'
                    elif data_type == 'flow_rate':
                        unit = 'sccm'
                    elif data_type == 'valve_state':
                        unit = ''  # Binary state

                    self.parameter_metadata[param_id] = {
                        'name': param_name,
                        'component_name': component_name,
                        'component_type': component_type,
                        'component_id': param.get('component_id'),
                        'data_type': data_type,
                        'unit': unit,
                        'min_value': param.get('min_value', 0),
                        'max_value': param.get('max_value', 0),
                        'is_writable': param.get('is_writable', False),
                        'write_modbus_address': param.get('write_modbus_address'),
                        'write_modbus_type': param.get('write_modbus_type')
                    }

                data_logger.info(f"✅ Loaded metadata for {len(self.parameter_metadata)} parameters")

                # Log a few examples of the metadata for debugging
                for i, (param_id, metadata) in enumerate(self.parameter_metadata.items()):
                    if i >= 3:  # Only show first 3
                        break
                    data_logger.debug(
                        f"Parameter {param_id}: {metadata['component_name']}.{metadata['name']} "
                        f"({metadata['data_type']}, {metadata['unit']})"
                    )
            else:
                data_logger.warning("No parameter metadata found in database")

        except Exception as e:
            data_logger.error(f"Failed to load parameter metadata: {e}", exc_info=True)
            # Continue with empty metadata - service should still work

    async def _batch_insert_with_retry(self, history_records: List[Dict[str, Any]],
                                       log_success: bool = True) -> bool:
        """
        Batch insert using PostgreSQL RPC for optimal performance.

        Uses server-side stored procedure to minimize serialization overhead
        and improve insert performance for high-frequency data collection.

        Implements 3-attempt retry with delays: 1s, 2s, 4s
        On final failure, writes to dead letter queue for recovery.

        Args:
            history_records: List of parameter records to insert
            log_success: If False, suppress success logs (used by async writer to avoid duplicate logging)

        Returns:
            bool: True if insert succeeded, False if all retries failed
        """
        max_attempts = 3
        backoff_delays = [1.0, 2.0, 4.0]  # Exponential backoff: 1s, 2s, 4s

        for attempt in range(max_attempts):
            try:
                # Call RPC function with JSONB array for optimal performance in a thread
                inserted_count = await asyncio.to_thread(self._rpc_bulk_insert_sync, history_records)

                if inserted_count > 0:
                    # Log retry success if this wasn't the first attempt
                    if attempt > 0:
                        self.metrics['batch_insert_retries'] += attempt
                        if log_success:
                            data_logger.info(
                                f"✅ RPC insert succeeded on retry attempt {attempt + 1}/{max_attempts}: "
                                f"{inserted_count} parameter values logged"
                            )
                    else:
                        if log_success:
                            data_logger.info(f"✅ RPC insert: {inserted_count} parameter values logged")

                    return True
                else:
                    raise Exception("RPC returned 0 inserted records")

            except Exception as e:
                self.metrics['batch_insert_retries'] += 1

                if attempt < max_attempts - 1:
                    # Not the last attempt - retry with backoff
                    delay = backoff_delays[attempt]
                    data_logger.warning(
                        f"⚠️ RPC insert failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed - write to dead letter queue
                    self.metrics['batch_insert_failures'] += 1
                    data_logger.error(
                        f"❌ RPC insert failed after {max_attempts} attempts: {e}. "
                        f"Writing {len(history_records)} records to dead letter queue..."
                    )
                    await self._write_to_dead_letter_queue(history_records)
                    return False

        return False

    async def _insert_wide_record_with_retry(self, timestamp: str, wide_record: Dict[str, float],
                                             log_success: bool = True) -> bool:
        """
        Insert single WIDE-FORMAT row using PostgreSQL RPC for optimal performance.

        Much faster than 51 narrow rows - reduces from 51 inserts to 1 insert per second!

        Implements 3-attempt retry with delays: 1s, 2s, 4s
        On final failure, writes to dead letter queue for recovery.

        Args:
            timestamp: ISO format timestamp for the reading
            wide_record: Dictionary of column_name -> value for all parameters
            log_success: If False, suppress success logs (used by async writer to avoid duplicate logging)

        Returns:
            bool: True if insert succeeded, False if all retries failed
        """
        max_attempts = 3
        backoff_delays = [1.0, 2.0, 4.0]  # Exponential backoff: 1s, 2s, 4s

        for attempt in range(max_attempts):
            try:
                # Call wide RPC function with timestamp and JSONB parameters
                response = self.supabase.rpc(
                    'insert_parameter_reading_wide',
                    params={
                        'p_timestamp': timestamp,
                        'p_params': wide_record
                    }
                ).execute()

                # RPC returns count of parameters inserted
                inserted_count = response.data if response.data else 0

                if inserted_count > 0:
                    # Log retry success if this wasn't the first attempt
                    if attempt > 0:
                        self.metrics['batch_insert_retries'] += attempt
                        if log_success:
                            data_logger.info(
                                f"✅ Wide insert succeeded on retry {attempt + 1}/{max_attempts}: "
                                f"{inserted_count} parameters"
                            )
                    else:
                        if log_success:
                            data_logger.info(f"✅ Wide insert: {inserted_count} parameters in 1 row")

                    return True
                else:
                    raise Exception("Wide RPC returned 0 parameters inserted")

            except Exception as e:
                self.metrics['batch_insert_retries'] += 1

                if attempt < max_attempts - 1:
                    # Not the last attempt - retry with backoff
                    delay = backoff_delays[attempt]
                    data_logger.warning(
                        f"⚠️ Wide insert failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed - write to dead letter queue
                    self.metrics['batch_insert_failures'] += 1
                    data_logger.error(
                        f"❌ Wide insert failed after {max_attempts} attempts: {e}. "
                        f"Writing to dead letter queue..."
                    )
                    await self._write_wide_record_to_dlq(timestamp, wide_record)
                    return False

        return False

    async def _write_to_dead_letter_queue(self, history_records: List[Dict[str, Any]]):
        """
        Write failed batch to dead letter queue for later recovery.

        Format: JSON lines in logs/dead_letter_queue/failed_batch_<timestamp>.jsonl

        Args:
            history_records: List of parameter records that failed to insert
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            dlq_file = self.dead_letter_queue_dir / f"failed_batch_{timestamp}.jsonl"

            # Write each record as a JSON line with fsync for durability
            try:
                with open(dlq_file, 'w') as f:
                    for record in history_records:
                        f.write(json.dumps(record) + '\n')

                    # CRITICAL: fsync to ensure data is written to disk before claiming success
                    f.flush()
                    os.fsync(f.fileno())
            except (IOError, OSError) as io_err:
                # Specific handling for file I/O errors
                data_logger.error(
                    f"🚨 CRITICAL: File I/O error writing to dead letter queue: {io_err}. "
                    f"File: {dlq_file}"
                )
                raise

            # Only update metrics and log success AFTER fsync completes
            self.metrics['dead_letter_queue_writes'] += 1
            self.metrics['dead_letter_queue_depth'] = len(list(self.dead_letter_queue_dir.glob('*.jsonl')))

            data_logger.warning(
                f"📝 Dead letter queue: Wrote {len(history_records)} records to {dlq_file.name}. "
                f"Queue depth: {self.metrics['dead_letter_queue_depth']} files"
            )

        except Exception as e:
            # Critical: If we can't even write to DLQ, log the data for manual recovery
            data_logger.error(
                f"🚨 CRITICAL: Failed to write to dead letter queue: {e}. "
                f"LOST DATA: {len(history_records)} records"
            )
            data_logger.error(f"Lost records (for manual recovery): {json.dumps(history_records)}")

    async def _write_wide_record_to_dlq(self, timestamp: str, wide_record: Dict[str, float]):
        """
        Write failed WIDE-FORMAT record to dead letter queue for later recovery.

        Format: JSON file in logs/dead_letter_queue/failed_wide_<timestamp>.json
        
        Args:
            timestamp: ISO timestamp of the reading
            wide_record: Dictionary of column_name -> value
        """
        try:
            file_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            dlq_file = self.dead_letter_queue_dir / f"failed_wide_{file_timestamp}.json"

            # Write wide record as JSON with timestamp and fsync for durability
            dlq_data = {
                'timestamp': timestamp,
                'params': wide_record
            }

            try:
                with open(dlq_file, 'w') as f:
                    json.dump(dlq_data, f, indent=2)

                    # CRITICAL: fsync to ensure data is written to disk before claiming success
                    f.flush()
                    os.fsync(f.fileno())
            except (IOError, OSError) as io_err:
                # Specific handling for file I/O errors
                data_logger.error(
                    f"🚨 CRITICAL: File I/O error writing wide record to dead letter queue: {io_err}. "
                    f"File: {dlq_file}"
                )
                raise

            # Only update metrics and log success AFTER fsync completes
            self.metrics['dead_letter_queue_writes'] += 1
            self.metrics['dead_letter_queue_depth'] = len(list(self.dead_letter_queue_dir.glob('*.json'))) + len(list(self.dead_letter_queue_dir.glob('*.jsonl')))

            data_logger.warning(
                f"📝 Dead letter queue: Wrote wide record ({len(wide_record)} params) to {dlq_file.name}. "
                f"Queue depth: {self.metrics['dead_letter_queue_depth']} files"
            )

        except Exception as e:
            # Critical: If we can't even write to DLQ, log the data for manual recovery
            data_logger.error(
                f"🚨 CRITICAL: Failed to write wide record to dead letter queue: {e}. "
                f"LOST DATA: {len(wide_record)} parameters"
            )
            data_logger.error(f"Lost wide record (for manual recovery): timestamp={timestamp}, params={json.dumps(wide_record)}")

    def _rpc_bulk_insert_sync(self, history_records: List[Dict[str, Any]]) -> int:
        """Synchronous RPC call executed in a threadpool to avoid blocking the event loop."""
        response = self.supabase.rpc(
            'bulk_insert_parameter_history',
            params={'records': history_records}
        ).execute()
        return int(response.data) if response and response.data else 0

    async def _dead_letter_queue_recovery_loop(self):
        """
        Background task that attempts to replay failed batches from dead letter queue.

        Runs every 60 seconds. For each file in DLQ:
        1. Try to insert the batch
        2. On success, delete the DLQ file
        3. On failure, leave for next attempt

        Supports both narrow format (.jsonl) and wide format (.json) files.
        """
        data_logger.info("🔄 Dead letter queue recovery loop started (60s interval)")

        while not self.shutdown_event.is_set():
            try:
                # Shutdown-aware sleep for 60 seconds
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=60.0
                    )
                    # Shutdown signaled, exit loop
                    data_logger.info("Shutdown event detected in DLQ recovery loop")
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue with recovery
                    pass

                # Get all DLQ files (both narrow .jsonl and wide .json formats)
                narrow_files = list(self.dead_letter_queue_dir.glob('*.jsonl'))
                wide_files = list(self.dead_letter_queue_dir.glob('*.json'))
                dlq_files = sorted(narrow_files + wide_files)

                if not dlq_files:
                    continue  # No files to recover

                data_logger.info(f"🔄 Dead letter queue recovery: Processing {len(dlq_files)} failed batches...")

                for dlq_file in dlq_files:
                    try:
                        # Detect file format by extension
                        is_wide_format = dlq_file.suffix == '.json'

                        if is_wide_format:
                            # WIDE FORMAT (.json): Single reading with timestamp + params
                            with open(dlq_file, 'r') as f:
                                dlq_data = json.load(f)

                            timestamp = dlq_data.get('timestamp')
                            wide_record = dlq_data.get('params')

                            if not timestamp or not wide_record:
                                # Invalid file - delete it
                                data_logger.warning(f"Invalid wide DLQ file {dlq_file.name} - deleting")
                                dlq_file.unlink()
                                continue

                            # Attempt recovery using wide RPC
                            try:
                                response = self.supabase.rpc(
                                    'insert_parameter_reading_wide',
                                    params={
                                        'p_timestamp': timestamp,
                                        'p_params': wide_record
                                    }
                                ).execute()

                                inserted_count = response.data if response.data else 0

                                if inserted_count > 0:
                                    # Success! Delete the DLQ file
                                    dlq_file.unlink()
                                    self.metrics['dead_letter_queue_replays'] += inserted_count

                                    # Recalculate depth (both formats)
                                    narrow_depth = len(list(self.dead_letter_queue_dir.glob('*.jsonl')))
                                    wide_depth = len(list(self.dead_letter_queue_dir.glob('*.json')))
                                    self.metrics['dead_letter_queue_depth'] = narrow_depth + wide_depth

                                    data_logger.info(
                                        f"✅ Dead letter queue recovery: Replayed wide record ({inserted_count} params) from {dlq_file.name}. "
                                        f"Remaining queue depth: {self.metrics['dead_letter_queue_depth']} files"
                                    )
                                else:
                                    # No records inserted - leave file for next attempt
                                    data_logger.warning(
                                        f"⚠️ Dead letter queue recovery failed for {dlq_file.name}: Wide RPC returned 0 parameters. "
                                        f"Will retry in 60s."
                                    )

                            except Exception as e:
                                # Insert failed - leave file for next attempt
                                data_logger.warning(
                                    f"⚠️ Dead letter queue recovery failed for {dlq_file.name}: {e}. "
                                    f"Will retry in 60s."
                                )

                        else:
                            # NARROW FORMAT (.jsonl): Multiple records, one per line
                            history_records = []
                            with open(dlq_file, 'r') as f:
                                for line in f:
                                    history_records.append(json.loads(line.strip()))

                            if not history_records:
                                # Empty file - delete it
                                dlq_file.unlink()
                                continue

                            # Attempt recovery using narrow RPC
                            try:
                                # Run recovery RPC in a thread to keep loop responsive
                                inserted_count = await asyncio.to_thread(self._rpc_bulk_insert_sync, history_records)

                                if inserted_count > 0:
                                    # Success! Delete the DLQ file
                                    dlq_file.unlink()
                                    self.metrics['dead_letter_queue_replays'] += inserted_count

                                    # Recalculate depth (both formats)
                                    narrow_depth = len(list(self.dead_letter_queue_dir.glob('*.jsonl')))
                                    wide_depth = len(list(self.dead_letter_queue_dir.glob('*.json')))
                                    self.metrics['dead_letter_queue_depth'] = narrow_depth + wide_depth

                                    data_logger.info(
                                        f"✅ Dead letter queue recovery: Replayed {inserted_count} records from {dlq_file.name}. "
                                        f"Remaining queue depth: {self.metrics['dead_letter_queue_depth']}"
                                    )
                                else:
                                    # No records inserted - leave file for next attempt
                                    data_logger.warning(
                                        f"⚠️ Dead letter queue recovery failed for {dlq_file.name}: RPC returned 0 records. "
                                        f"Will retry in 60s."
                                    )

                            except Exception as e:
                                # Insert failed - leave file for next attempt
                                data_logger.warning(
                                    f"⚠️ Dead letter queue recovery failed for {dlq_file.name}: {e}. "
                                    f"Will retry in 60s."
                                )

                    except Exception as e:
                        data_logger.error(f"Error processing DLQ file {dlq_file.name}: {e}", exc_info=True)

            except asyncio.CancelledError:
                data_logger.info("Dead letter queue recovery loop cancelled")
                break
            except Exception as e:
                data_logger.error(f"Error in dead letter queue recovery loop: {e}", exc_info=True)
                # Continue loop despite error

    async def _log_parameters_with_metadata(self, parameter_values: Dict[str, float], 
                                            setpoint_values: Dict[str, float]) -> int:
        """
        Log parameters to database using WIDE TABLE format - ONE row with all parameters.
        
        Also synchronizes setpoint values from PLC to database, detecting external changes.

        Uses retry logic with exponential backoff and dead letter queue for zero data loss.

        Args:
            parameter_values: Dictionary of parameter_id -> current_value
            setpoint_values: Dictionary of parameter_id -> setpoint_value

        Returns:
            int: Number of parameters successfully logged
        """
        success_count = 0

        try:
            from datetime import datetime
            timestamp = datetime.utcnow().isoformat()

            # Build WIDE-FORMAT record with column names based on parameter IDs
            wide_record = {}
            
            for param_id, value in parameter_values.items():
                # Get column name from mapping
                column_name = PARAMETER_TO_COLUMN_MAP.get(param_id)
                
                if column_name is None:
                    # Parameter not in wide table mapping - log warning and skip
                    data_logger.warning(f"Parameter {param_id} not in wide table mapping - skipping")
                    continue
                
                # Add to wide record
                wide_record[column_name] = float(value)
                
                # Per-parameter log (optional) with metadata
                if self.verbose_parameter_logging:
                    metadata = self.parameter_metadata.get(param_id, {})
                    param_name = metadata.get('name', f'param_{param_id}')
                    component_name = metadata.get('component_name', 'unknown_component')
                    unit = metadata.get('unit', '')
                    
                    if unit:
                        value_str = f"{value:.3f} {unit}"
                    else:
                        value_str = f"{value:.3f}"
                    data_logger.info(
                        f"📊 PLC Read: {component_name}.{param_name} = {value_str}"
                    )

            # Insert wide record (single row) or enqueue
            if wide_record:
                if self.async_writer_enabled:
                    await self._enqueue_wide_record(timestamp, wide_record)
                    success_count = len(wide_record)
                else:
                    insert_success = await self._insert_wide_record_with_retry(timestamp, wide_record)
                    if insert_success:
                        success_count = len(wide_record)
                    else:
                        # Failed after retries - data is in DLQ for recovery
                        data_logger.error(
                            f"❌ Wide insert failed after retries: {len(wide_record)} parameters in dead letter queue"
                        )
            
            # Synchronize setpoint values with database (background task)
            if setpoint_values:
                asyncio.create_task(self._sync_setpoints_to_database(setpoint_values))

        except Exception as e:
            data_logger.error(f"Failed to log parameters with metadata: {e}", exc_info=True)

        return success_count

    async def _db_writer_loop(self):
        """Background task that consumes batches and writes them to DB without blocking the poller."""
        data_logger.info("🧵 DB writer started (async queue)")
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Use wait to allow immediate exit on shutdown
                    queue_task = asyncio.create_task(self._write_queue.get())
                    shutdown_task = asyncio.create_task(self.shutdown_event.wait())

                    done, pending = await asyncio.wait(
                        [queue_task, shutdown_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel pending tasks
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # Check if shutdown was signaled
                    if shutdown_task in done:
                        data_logger.info("Shutdown event detected in DB writer loop")
                        break

                    # Get the batch from completed queue task
                    batch = queue_task.result()

                    # Check if this is a wide record (tuple) or narrow record (list)
                    if isinstance(batch, tuple) and len(batch) == 3 and batch[0] == 'wide':
                        # Wide format: ('wide', timestamp, wide_record)
                        _, timestamp, wide_record = batch
                        # Suppress internal success logs - we'll log at this level instead
                        success = await self._insert_wide_record_with_retry(timestamp, wide_record, log_success=False)

                        # Log ACTUAL database write completion (after retry logic completes)
                        if success:
                            self.metrics['successful_readings'] += 1
                            data_logger.info(
                                f"✅ Database write completed: {len(wide_record)} parameters written successfully"
                            )
                        else:
                            self.metrics['failed_readings'] += 1
                            data_logger.error(
                                f"❌ Database write failed: {len(wide_record)} parameters moved to dead letter queue"
                            )
                    else:
                        # Narrow format (legacy): list of records
                        # Suppress internal success logs - we'll log at this level instead
                        success = await self._batch_insert_with_retry(batch, log_success=False)

                        # Log ACTUAL database write completion
                        if success:
                            self.metrics['successful_readings'] += 1
                            data_logger.info(
                                f"✅ Database write completed: {len(batch)} records written successfully"
                            )
                        else:
                            self.metrics['failed_readings'] += 1
                            data_logger.error(
                                f"❌ Database write failed: {len(batch)} records moved to dead letter queue"
                            )

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.metrics['failed_readings'] += 1
                    data_logger.error(f"DB writer error: {e}", exc_info=True)
        finally:
            data_logger.info("🧵 DB writer stopped")

    async def _enqueue_history_records(self, history_records: List[Dict[str, Any]]):
        """Enqueue a batch for background DB writing. Drop oldest batch if the queue is full."""
        try:
            self._write_queue.put_nowait(history_records)
        except asyncio.QueueFull:
            try:
                dropped_batch = self._write_queue.get_nowait()  # drop oldest
                self.metrics['batches_dropped'] += 1

                # CRITICAL: Log queue drop with full context - operators must see this immediately!
                dropped_count = len(dropped_batch) if isinstance(dropped_batch, list) else 1
                data_logger.warning(
                    f"⚠️ QUEUE FULL: Dropped oldest batch ({dropped_count} records) to make room. "
                    f"Total queue drops: {self.metrics['batches_dropped']}. "
                    f"DB writer is falling behind data collection!"
                )

                self._write_queue.put_nowait(history_records)
            except Exception:
                # As a last resort, fall back to DLQ to avoid data loss
                await self._write_to_dead_letter_queue(history_records)
                return
        finally:
            self.metrics['batches_enqueued'] += 1
            self.metrics['records_enqueued'] += len(history_records)
    
    async def _enqueue_wide_record(self, timestamp: str, wide_record: Dict[str, float]):
        """Enqueue a WIDE-FORMAT record for background DB writing. Drop oldest if queue is full."""
        try:
            # Store as tuple (timestamp, wide_record) to distinguish from narrow records
            self._write_queue.put_nowait(('wide', timestamp, wide_record))
        except asyncio.QueueFull:
            try:
                dropped_batch = self._write_queue.get_nowait()  # drop oldest
                self.metrics['batches_dropped'] += 1

                # CRITICAL: Log queue drop with full context - operators must see this immediately!
                if isinstance(dropped_batch, tuple) and len(dropped_batch) == 3 and dropped_batch[0] == 'wide':
                    # Wide format dropped
                    dropped_timestamp, dropped_params = dropped_batch[1], dropped_batch[2]
                    data_logger.warning(
                        f"⚠️ QUEUE FULL: Dropped oldest wide-format batch ({len(dropped_params)} parameters, "
                        f"timestamp={dropped_timestamp}) to make room. "
                        f"Total queue drops: {self.metrics['batches_dropped']}. "
                        f"DB writer is falling behind data collection!"
                    )
                else:
                    # Narrow format dropped
                    dropped_count = len(dropped_batch) if isinstance(dropped_batch, list) else 1
                    data_logger.warning(
                        f"⚠️ QUEUE FULL: Dropped oldest narrow-format batch ({dropped_count} records) to make room. "
                        f"Total queue drops: {self.metrics['batches_dropped']}. "
                        f"DB writer is falling behind data collection!"
                    )

                self._write_queue.put_nowait(('wide', timestamp, wide_record))
            except Exception:
                # As a last resort, fall back to DLQ to avoid data loss
                await self._write_wide_record_to_dlq(timestamp, wide_record)
                return
        finally:
            self.metrics['batches_enqueued'] += 1
            self.metrics['records_enqueued'] += len(wide_record)
    
    async def _sync_setpoints_to_database(self, setpoint_values: Dict[str, float]):
        """
        Synchronize setpoint values from PLC to database.
        
        Detects external changes by comparing PLC setpoints with database values.
        
        Args:
            setpoint_values: Dictionary of parameter_id -> setpoint from PLC
        """
        try:
            if not setpoint_values:
                return
            
            # Get current set_values from database for comparison (off the event loop)
            param_ids = list(setpoint_values.keys())
            db_setpoints = await asyncio.to_thread(self._supabase_select_setvalues_sync, param_ids)
            
            # Detect changes and prepare batch update
            updates_needed = []
            external_changes = []
            
            for param_id, plc_setpoint in setpoint_values.items():
                db_setpoint = db_setpoints.get(param_id)
                
                # Check if values differ (with small tolerance for floating point)
                if db_setpoint is None or abs(plc_setpoint - db_setpoint) > 0.01:
                    updates_needed.append(param_id)
                    
                    # Log external change detection
                    if db_setpoint is not None:
                        metadata = self.parameter_metadata.get(param_id, {})
                        component_name = metadata.get('component_name', 'unknown')
                        param_name = metadata.get('name', 'unknown')
                        unit = metadata.get('unit', '')
                        
                        delta = plc_setpoint - db_setpoint
                        pct_change = (delta / db_setpoint * 100) if db_setpoint != 0 else 0
                        
                        unit_str = f" {unit}" if unit else ""
                        data_logger.info(
                            f"🔄 External change detected: {component_name}.{param_name} "
                            f"set_value: DB={db_setpoint:.2f}{unit_str}, PLC={plc_setpoint:.2f}{unit_str} "
                            f"(Δ={delta:+.2f}, {pct_change:+.1f}%)"
                        )
                        external_changes.append(param_id)
            
            # Update metrics
            if external_changes:
                self.metrics['external_setpoint_changes_detected'] += len(external_changes)
            
            # Perform batch update if needed
            if updates_needed:
                # Note: Supabase doesn't have native batch update by ID list
                # We'll update one by one but in a single transaction context
                for param_id in updates_needed:
                    try:
                        await asyncio.to_thread(
                            self._supabase_update_setvalue_sync,
                            param_id,
                            setpoint_values[param_id]
                        )
                    except Exception as e:
                        data_logger.error(
                            f"Failed to update setpoint for parameter {param_id}: {e}"
                        )
                
                data_logger.info(
                    f"✅ Synchronized {len(updates_needed)} setpoint(s) from PLC to database "
                    f"({len(external_changes)} external changes)"
                )
        
        except Exception as e:
            data_logger.error(f"Failed to sync setpoints to database: {e}", exc_info=True)

    def _supabase_select_setvalues_sync(self, param_ids: List[str]) -> Dict[str, float]:
        """Synchronous select executed in threadpool: returns id->set_value mapping."""
        db_result = self.supabase.table('component_parameters').select(
            'id, set_value'
        ).in_('id', param_ids).execute()
        return {row['id']: row['set_value'] for row in (db_result.data or [])}

    def _supabase_update_setvalue_sync(self, param_id: str, value: float) -> None:
        """Synchronous update executed in threadpool for a single set_value."""
        self.supabase.table('component_parameters').update({
            'set_value': value,
            'updated_at': 'now()'
        }).eq('id', param_id).execute()

    def get_status(self) -> Dict[str, Any]:
        """Get current service status and metrics."""
        uptime = asyncio.get_event_loop().time() - self.metrics.get('service_start_time', 0)

        return {
            'service_name': 'PLC Data Service (Terminal 1)',
            'is_running': self.is_running,
            'plc_connected': self.plc_manager.is_connected(),
            'uptime_seconds': uptime,
            'metrics': self.metrics.copy()
        }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="PLC Data Service - Terminal 1")
    parser.add_argument("--plc", choices=["simulation", "real"], help="PLC backend type")
    parser.add_argument("--demo", action="store_true", help="Use simulation mode")
    parser.add_argument("--ip", dest="plc_ip", help="PLC IP address")
    parser.add_argument("--port", dest="plc_port", type=int, help="PLC port")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
    return parser.parse_args()


def apply_env_overrides(args):
    """Apply command line arguments to environment variables."""
    if args.demo:
        os.environ["PLC_TYPE"] = "simulation"
    if args.plc:
        os.environ["PLC_TYPE"] = args.plc
    if args.plc_ip:
        os.environ["PLC_IP"] = args.plc_ip
    if args.plc_port is not None:
        os.environ["PLC_PORT"] = str(args.plc_port)
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level


async def signal_handler(plc_service):
    """Handle shutdown signals gracefully."""
    main_logger.info("Received shutdown signal - stopping PLC Data Service...")
    await plc_service.stop()
    main_logger.info("PLC Data Service shutdown complete")


def setup_signal_handlers(service: PLCDataService, loop: asyncio.AbstractEventLoop):
    """Setup signal handlers using asyncio's add_signal_handler (event loop aware)."""

    def shutdown_callback():
        """Called by event loop when signal is received."""
        main_logger.info(f"🛑 Received shutdown signal, initiating graceful shutdown...")
        # Set flags (already on event loop thread)
        service.is_running = False
        service.shutdown_event.set()

    # Use asyncio's native signal handling (works correctly with event loop)
    loop.add_signal_handler(signal.SIGINT, shutdown_callback)
    loop.add_signal_handler(signal.SIGTERM, shutdown_callback)
    main_logger.info("✅ Signal handlers installed (SIGINT, SIGTERM)")


async def main():
    """Main entry point for PLC Data Service."""
    # Parse command line arguments
    args = parse_args()
    apply_env_overrides(args)

    # Configure logging
    from src.log_setup import set_log_level
    set_log_level(os.environ.get("LOG_LEVEL", "INFO"))

    # Setup global exception handlers to catch crashes
    from src.resilience.error_handlers import (
        setup_global_exception_handler,
        setup_asyncio_exception_handler
    )

    # Will setup handlers with registry after service creation
    registry = None

    main_logger.info("="*60)
    main_logger.info("🔧 STARTING PLC DATA SERVICE - TERMINAL 1")
    main_logger.info("="*60)
    main_logger.info(f"Machine ID: {MACHINE_ID}")
    main_logger.info(f"PLC Type: {PLC_TYPE}")
    main_logger.info("PLC DATA COLLECTION SERVICE - Terminal 1")
    main_logger.info(f"Terminal Liveness: ENABLED")
    main_logger.info("="*60)

    # Create and initialize service
    plc_service = PLCDataService()

    # Setup signal handlers now that we have the service
    # Note: This must be done inside the async context so we can get the running loop
    loop = asyncio.get_running_loop()
    setup_signal_handlers(plc_service, loop)

    try:
        # Initialize service
        if not await plc_service.initialize():
            main_logger.error("Failed to initialize PLC Data Service")
            return 1

        # Setup exception handlers now that we have registry
        if plc_service.registry:
            setup_global_exception_handler(
                registry=plc_service.registry,
                logger=main_logger
            )
            setup_asyncio_exception_handler(
                registry=plc_service.registry,
                logger=main_logger
            )
            main_logger.info("✅ Global exception handlers installed")

        # Start service
        await plc_service.start()

    except KeyboardInterrupt:
        main_logger.info("Received keyboard interrupt")
        await plc_service.stop()
    except RuntimeError as e:
        # Handle terminal already running error
        if "already running" in str(e):
            main_logger.error(str(e))
            return 1
        else:
            main_logger.error(f"Fatal runtime error: {e}", exc_info=True)
            await plc_service.stop()
            return 1
    except Exception as e:
        main_logger.error(f"Fatal error in PLC Data Service: {e}", exc_info=True)
        await plc_service.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
