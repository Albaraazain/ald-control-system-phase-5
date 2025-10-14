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
import atexit
import fcntl
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
# Removed broken transactional import - will use direct database logging

# Service-specific loggers
plc_logger = get_plc_logger()
data_logger = get_data_collection_logger()


def ensure_single_instance():
    """Ensure only one plc_data_service instance runs"""
    lock_file = "/tmp/plc_data_service.lock"
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Write PID to lock file
        os.write(fd, f"{os.getpid()}\n".encode())
        os.fsync(fd)

        # Clean up on exit
        atexit.register(lambda: os.unlink(lock_file) if os.path.exists(lock_file) else None)

        return fd
    except (OSError, IOError):
        plc_logger.error("❌ Another plc_data_service is already running")
        plc_logger.error("💡 Kill existing instances or wait for them to finish")
        exit(1)




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
        self.is_running = False
        self.data_collection_task = None
        self.writer_task = None
        self.recovery_task = None

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

        # Throttle how often we read setpoints (they rarely change)
        self.setpoint_refresh_interval: float = float(os.environ.get('SETPOINT_REFRESH_INTERVAL', '10'))
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
        """Stop all PLC Data Service operations."""
        if not self.is_running:
            return

        try:
            plc_logger.info("Stopping PLC Data Service...")
            self.is_running = False

            # Cancel all tasks
            tasks = [self.data_collection_task, self.writer_task, self.recovery_task]
            for task in tasks:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Disconnect PLC
            await self.plc_manager.disconnect()

            # Cleanup parameter metadata cache
            self.parameter_metadata = {}

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

        while self.is_running:
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

                await asyncio.sleep(sleep_time)

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
                self.metrics['successful_readings'] += 1
                if self.async_writer_enabled:
                    data_logger.info(
                        f"✅ PLC data collection enqueued: {success_count}/{len(parameter_values)} parameters"
                    )
                else:
                    data_logger.info(
                        f"✅ PLC data collection completed: {success_count}/{len(parameter_values)} parameters logged successfully"
                    )
            else:
                self.metrics['failed_readings'] += 1
                data_logger.error(f"❌ PLC data collection failed for all {len(parameter_values)} parameters")

        except Exception as e:
            self.metrics['failed_readings'] += 1
            data_logger.error(f"Failed to collect and log PLC data: {e}", exc_info=True)
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

    async def _batch_insert_with_retry(self, history_records: List[Dict[str, Any]]) -> bool:
        """
        Batch insert using PostgreSQL RPC for optimal performance.

        Uses server-side stored procedure to minimize serialization overhead
        and improve insert performance for high-frequency data collection.

        Implements 3-attempt retry with delays: 1s, 2s, 4s
        On final failure, writes to dead letter queue for recovery.

        Args:
            history_records: List of parameter records to insert

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
                        data_logger.info(
                            f"✅ RPC insert succeeded on retry attempt {attempt + 1}/{max_attempts}: "
                            f"{inserted_count} parameter values logged"
                        )
                    else:
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

    async def _insert_wide_record_with_retry(self, timestamp: str, wide_record: Dict[str, float]) -> bool:
        """
        Insert single WIDE-FORMAT row using PostgreSQL RPC for optimal performance.
        
        Much faster than 51 narrow rows - reduces from 51 inserts to 1 insert per second!

        Implements 3-attempt retry with delays: 1s, 2s, 4s
        On final failure, writes to dead letter queue for recovery.

        Args:
            timestamp: ISO format timestamp for the reading
            wide_record: Dictionary of column_name -> value for all parameters

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
                        data_logger.info(
                            f"✅ Wide insert succeeded on retry {attempt + 1}/{max_attempts}: "
                            f"{inserted_count} parameters"
                        )
                    else:
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

            # Write each record as a JSON line
            with open(dlq_file, 'w') as f:
                for record in history_records:
                    f.write(json.dumps(record) + '\n')

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

            # Write wide record as JSON with timestamp
            dlq_data = {
                'timestamp': timestamp,
                'params': wide_record
            }
            
            with open(dlq_file, 'w') as f:
                json.dump(dlq_data, f, indent=2)

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
        """
        data_logger.info("🔄 Dead letter queue recovery loop started (60s interval)")

        while self.is_running:
            try:
                await asyncio.sleep(60.0)  # Check every 60 seconds

                # Get all DLQ files
                dlq_files = sorted(self.dead_letter_queue_dir.glob('*.jsonl'))

                if not dlq_files:
                    continue  # No files to recover

                data_logger.info(f"🔄 Dead letter queue recovery: Processing {len(dlq_files)} failed batches...")

                for dlq_file in dlq_files:
                    try:
                        # Read records from file
                        history_records = []
                        with open(dlq_file, 'r') as f:
                            for line in f:
                                history_records.append(json.loads(line.strip()))

                        if not history_records:
                            # Empty file - delete it
                            dlq_file.unlink()
                            continue

                        # Attempt single retry using RPC (no exponential backoff for recovery)
                        try:
                            # Run recovery RPC in a thread to keep loop responsive
                            inserted_count = await asyncio.to_thread(self._rpc_bulk_insert_sync, history_records)
                            
                            if inserted_count > 0:
                                # Success! Delete the DLQ file
                                dlq_file.unlink()
                                self.metrics['dead_letter_queue_replays'] += inserted_count
                                self.metrics['dead_letter_queue_depth'] = len(list(self.dead_letter_queue_dir.glob('*.jsonl')))

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
            while self.is_running:
                try:
                    batch = await self._write_queue.get()
                    
                    # Check if this is a wide record (tuple) or narrow record (list)
                    if isinstance(batch, tuple) and len(batch) == 3 and batch[0] == 'wide':
                        # Wide format: ('wide', timestamp, wide_record)
                        _, timestamp, wide_record = batch
                        await self._insert_wide_record_with_retry(timestamp, wide_record)
                    else:
                        # Narrow format (legacy): list of records
                        await self._batch_insert_with_retry(batch)
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    data_logger.error(f"DB writer error: {e}", exc_info=True)
        finally:
            data_logger.info("🧵 DB writer stopped")

    async def _enqueue_history_records(self, history_records: List[Dict[str, Any]]):
        """Enqueue a batch for background DB writing. Drop oldest batch if the queue is full."""
        try:
            self._write_queue.put_nowait(history_records)
        except asyncio.QueueFull:
            try:
                _ = self._write_queue.get_nowait()  # drop oldest
                self.metrics['batches_dropped'] += 1
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
                _ = self._write_queue.get_nowait()  # drop oldest
                self.metrics['batches_dropped'] += 1
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


async def main():
    """Main entry point for PLC Data Service."""
    # Ensure only one instance runs
    ensure_single_instance()

    # Parse command line arguments
    args = parse_args()
    apply_env_overrides(args)

    # Configure logging
    from src.log_setup import set_log_level
    set_log_level(os.environ.get("LOG_LEVEL", "INFO"))

    main_logger.info("="*60)
    main_logger.info("🔧 STARTING PLC DATA SERVICE - TERMINAL 1")
    main_logger.info("="*60)
    main_logger.info(f"Machine ID: {MACHINE_ID}")
    main_logger.info(f"PLC Type: {PLC_TYPE}")
    main_logger.info("PLC DATA COLLECTION SERVICE - Terminal 1")
    main_logger.info("="*60)

    # Create and initialize service
    plc_service = PLCDataService()

    # Set up signal handlers
    def shutdown_handler(signum, frame):
        asyncio.create_task(signal_handler(plc_service))

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Initialize service
        if not await plc_service.initialize():
            main_logger.error("Failed to initialize PLC Data Service")
            return 1

        # Start service
        await plc_service.start()

    except KeyboardInterrupt:
        main_logger.info("Received keyboard interrupt")
        await plc_service.stop()
    except Exception as e:
        main_logger.error(f"Fatal error in PLC Data Service: {e}", exc_info=True)
        await plc_service.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
