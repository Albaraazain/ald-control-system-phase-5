# File: data_collection/continuous_parameter_logger.py
"""
Continuous parameter data logging service with dual-mode operation.

This service continuously reads PLC parameters and logs to database with:
- Mode 1 (Idle): Logs to parameter_value_history table only
- Mode 2 (Process Running): Logs to both parameter_value_history AND process_data_points tables
"""
import asyncio
import time
from typing import Optional, Dict, Any
from src.log_setup import logger
from src.plc.manager import plc_manager
from src.db import get_supabase, get_current_timestamp
from src.config import MACHINE_ID


class ContinuousParameterLogger:
    """Continuous parameter logger with dual-mode operation."""

    def __init__(self, interval_seconds: float = 1.0):
        """
        Initialize the continuous parameter logger.

        Args:
            interval_seconds: Time between readings in seconds (default: 1.0)
        """
        self.interval = interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._error_count = 0
        self._max_consecutive_errors = 5
        self._last_successful_read = None

    async def start(self):
        """Start continuous parameter logging."""
        if self.is_running:
            logger.warning("Continuous parameter logger is already running")
            return

        self.is_running = True
        self._error_count = 0
        self._task = asyncio.create_task(self._logging_loop())
        logger.info("Started continuous parameter logging service")

    async def stop(self):
        """Stop the continuous parameter logging."""
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

        logger.info("Stopped continuous parameter logging service")

    async def _logging_loop(self):
        """Internal loop that logs parameters at the specified interval."""
        try:
            while self.is_running:
                start_time = time.time()

                try:
                    # Read all parameters and log them
                    await self._read_and_log_parameters()
                    self._error_count = 0  # Reset error count on success
                    self._last_successful_read = time.time()

                except Exception as e:
                    self._error_count += 1
                    logger.error(
                        f"Error in parameter logging (attempt {self._error_count}): {str(e)}",
                        exc_info=True
                    )

                    # If too many consecutive errors, pause longer
                    if self._error_count >= self._max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive errors ({self._error_count}), "
                            f"pausing for 30 seconds"
                        )
                        await asyncio.sleep(30)
                        self._error_count = 0  # Reset after pause

                # Calculate sleep time to maintain consistent interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.interval - elapsed)

                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("Parameter logging loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in parameter logging loop: {str(e)}", exc_info=True)
            self.is_running = False

    async def _read_and_log_parameters(self):
        """
        Read all parameters from PLC and log to appropriate database tables.

        Implements dual-mode logic:
        - Always logs to parameter_value_history
        - Additionally logs to process_data_points if process is running
        """
        # Check if PLC is connected
        if not plc_manager.is_connected():
            logger.debug("PLC not connected, skipping parameter reading")
            return

        # Check if a process is currently running
        current_process_id = await self._get_current_process_id()

        # Read all parameters from PLC
        try:
            parameter_values = await plc_manager.read_all_parameters()
        except Exception as e:
            logger.error(f"Failed to read parameters from PLC: {str(e)}")
            return

        if not parameter_values:
            logger.debug("No parameters read from PLC")
            return

        # Get current timestamp
        timestamp = get_current_timestamp()

        # Get parameter metadata for set_point values
        parameter_metadata = await self._get_parameter_metadata(list(parameter_values.keys()))

        # Prepare data for logging
        history_records = []
        process_records = []

        for parameter_id, current_value in parameter_values.items():
            if current_value is None:
                continue

            set_point = parameter_metadata.get(parameter_id, {}).get('set_value')

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

        # Log to database tables
        await self._insert_records(history_records, process_records, current_process_id)

        logger.debug(
            f"Logged {len(history_records)} parameters to history"
            f"{f' and {len(process_records)} to process data' if process_records else ''}"
        )

    async def _get_current_process_id(self) -> Optional[str]:
        """
        Get the current process ID if a process is running.

        Returns:
            str: Process ID if running, None if idle
        """
        try:
            supabase = get_supabase()
            result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()

            if result.data and result.data.get('status') == 'processing':
                return result.data.get('current_process_id')

            return None

        except Exception as e:
            logger.error(f"Error checking current process status: {str(e)}")
            return None

    async def _get_parameter_metadata(self, parameter_ids: list) -> Dict[str, Dict[str, Any]]:
        """
        Get parameter metadata including set_value for the given parameter IDs.

        Args:
            parameter_ids: List of parameter IDs to get metadata for

        Returns:
            Dict mapping parameter_id to metadata dict
        """
        try:
            supabase = get_supabase()
            result = supabase.table('component_parameters').select('id, set_value').in_('id', parameter_ids).execute()

            metadata = {}
            if result.data:
                for param in result.data:
                    metadata[param['id']] = {'set_value': param.get('set_value')}

            return metadata

        except Exception as e:
            logger.error(f"Error getting parameter metadata: {str(e)}")
            return {}

    async def _insert_records(self, history_records: list, process_records: list, current_process_id: Optional[str]):
        """
        Insert records into the database tables.

        Args:
            history_records: Records for parameter_value_history table
            process_records: Records for process_data_points table (if process running)
            current_process_id: Current process ID (for logging)
        """
        try:
            supabase = get_supabase()

            # Insert into parameter_value_history (always)
            if history_records:
                # Insert in batches to avoid large requests
                batch_size = 50
                for i in range(0, len(history_records), batch_size):
                    batch = history_records[i:i+batch_size]
                    supabase.table('parameter_value_history').insert(batch).execute()

            # Insert into process_data_points (only if process running)
            if process_records and current_process_id:
                # Insert in batches to avoid large requests
                batch_size = 50
                for i in range(0, len(process_records), batch_size):
                    batch = process_records[i:i+batch_size]
                    supabase.table('process_data_points').insert(batch).execute()

        except Exception as e:
            logger.error(f"Error inserting parameter records: {str(e)}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the parameter logger.

        Returns:
            Dict with status information
        """
        return {
            'is_running': self.is_running,
            'interval_seconds': self.interval,
            'error_count': self._error_count,
            'last_successful_read': self._last_successful_read,
            'plc_connected': plc_manager.is_connected()
        }


# Global instance
continuous_parameter_logger = ContinuousParameterLogger()