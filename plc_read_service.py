#!/usr/bin/env python3
"""
Simple PLC Read Service - Terminal 1

This is a SIMPLE service that:
1. Reads PLC parameters every 1 second
2. Updates the parameter_value_history database table
3. NO coordination, NO complex architecture, NO transactional overhead

Usage:
    python plc_read_service.py
"""
import asyncio
import atexit
import fcntl
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any

from src.log_setup import get_service_logger
from src.plc.manager import plc_manager
from src.db import get_supabase, get_current_timestamp
from src.config import MACHINE_ID, is_core_config_ready, missing_required_keys

# Simple logger for this service
logger = get_service_logger('plc_read')


def ensure_single_instance():
    """Ensure only one plc_read_service instance runs"""
    lock_file = "/tmp/plc_read_service.lock"
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
        logger.error("❌ Another plc_read_service is already running")
        logger.error("💡 Kill existing instances or wait for them to finish")
        exit(1)


class SimplePLCReadService:
    """Simple PLC reading service with minimal complexity."""

    def __init__(self, interval_seconds: float = 1.0):
        """Initialize the simple PLC read service."""
        self.interval = interval_seconds
        self.is_running = False
        self.error_count = 0
        self.max_consecutive_errors = 5
        self.last_successful_read = None

    async def start(self):
        """Start the PLC reading service."""
        logger.info("🚀 Starting Simple PLC Read Service")
        logger.info(f"🔄 Service configuration: interval={self.interval}s, max_errors={self.max_consecutive_errors}")

        # Check configuration
        if not is_core_config_ready():
            missing = missing_required_keys()
            logger.error(f"❌ Missing required configuration: {missing}")
            return False
        logger.info(f"✅ Configuration validated for machine_id={MACHINE_ID}")

        # Initialize PLC
        logger.info("📡 Initializing PLC connection...")
        plc_success = await plc_manager.initialize()
        if not plc_success:
            logger.error("❌ Failed to initialize PLC connection")
            return False

        logger.info(f"✅ PLC connected: {plc_manager.is_connected()}")
        logger.info(f"📡 PLC connection details: {plc_manager.get_connection_info() if hasattr(plc_manager, 'get_connection_info') else 'Connection established'}")

        # Start reading loop
        self.is_running = True
        self.error_count = 0
        start_time = datetime.now(timezone.utc)
        logger.info(f"🔄 Service started at {start_time.isoformat()}")

        logger.info(f"📊 Starting parameter reading loop every {self.interval} seconds...")
        await self._reading_loop()

    async def stop(self):
        """Stop the PLC reading service."""
        stop_time = datetime.now(timezone.utc)
        logger.info(f"⏹️  Stopping Simple PLC Read Service at {stop_time.isoformat()}")
        logger.info(f"📊 Final stats: error_count={self.error_count}, last_successful_read={self.last_successful_read}")

        self.is_running = False

        logger.info("📡 Disconnecting from PLC...")
        await plc_manager.disconnect()
        logger.info("✅ PLC disconnected successfully")

    async def _reading_loop(self):
        """Main reading loop - simple and straightforward."""
        loop_count = 0
        logger.info("🔄 Entering main reading loop")

        while self.is_running:
            loop_count += 1
            cycle_start_time = time.time()
            timestamp = datetime.now(timezone.utc)

            logger.debug(f"🔄 Loop cycle #{loop_count} starting at {timestamp.isoformat()}")

            try:
                # Read parameters from PLC
                logger.debug("📡 Starting PLC parameter read operation")
                await self._read_and_store_parameters()

                # Reset error count on success
                self.error_count = 0
                self.last_successful_read = time.time()
                logger.debug(f"✅ Cycle #{loop_count} completed successfully")

            except Exception as e:
                self.error_count += 1
                logger.error(f"⚠️ Error reading parameters (cycle #{loop_count}, attempt {self.error_count}): {e}", exc_info=True)

                # If too many consecutive errors, pause
                if self.error_count >= self.max_consecutive_errors:
                    logger.error(f"❌ Too many consecutive errors ({self.error_count}), pausing 30 seconds")
                    await asyncio.sleep(30)
                    self.error_count = 0
                    logger.info("🔄 Resuming after error recovery pause")

            # Maintain consistent interval
            cycle_elapsed = time.time() - cycle_start_time
            sleep_time = max(0, self.interval - cycle_elapsed)

            if sleep_time > 0:
                logger.debug(f"⏱️  Cycle #{loop_count} took {cycle_elapsed:.3f}s, sleeping {sleep_time:.3f}s to maintain {self.interval}s interval")
                await asyncio.sleep(sleep_time)
            else:
                logger.warning(f"⚠️ Cycle #{loop_count} took {cycle_elapsed:.3f}s, exceeding target interval of {self.interval}s")

        logger.info(f"🔄 Reading loop terminated after {loop_count} cycles")

    async def _read_and_store_parameters(self):
        """Read all parameters from PLC and store in database."""
        read_start_time = time.time()

        # Check PLC connection
        if not plc_manager.is_connected():
            logger.warning("⚠️ PLC not connected, skipping read cycle")
            return

        logger.debug("📡 PLC connection verified, proceeding with parameter read")

        # Read all parameters
        logger.debug("📡 Initiating read_all_parameters() call")
        try:
            parameter_values = await plc_manager.read_all_parameters()
            read_elapsed = time.time() - read_start_time
            logger.debug(f"📡 PLC read completed in {read_elapsed:.3f}s")
        except Exception as e:
            logger.error(f"❌ Failed to read parameters from PLC: {e}", exc_info=True)
            raise

        if not parameter_values:
            logger.warning("⚠️ No parameters read from PLC - empty response")
            return

        logger.info(f"📊 Successfully read {len(parameter_values)} parameters from PLC")

        # Log parameter values for debugging
        for param_id, value in parameter_values.items():
            logger.debug(f"📊 Parameter {param_id}: {value}")

        # Prepare records for database (matching actual schema)
        timestamp = get_current_timestamp()
        records = []
        valid_count = 0
        invalid_count = 0

        for parameter_id, value in parameter_values.items():
            if value is not None:
                records.append({
                    'parameter_id': parameter_id,
                    'value': value,
                    'timestamp': timestamp
                })
                valid_count += 1
            else:
                invalid_count += 1
                logger.debug(f"📊 Skipping parameter {parameter_id}: null value")

        logger.info(f"📊 Prepared {valid_count} valid records for database (skipped {invalid_count} null values)")

        # Store in database - simple insert, no transactions
        if records:
            logger.debug(f"💾 Starting database insert for {len(records)} records")
            db_start_time = time.time()
            await self._insert_parameter_records(records)
            db_elapsed = time.time() - db_start_time
            logger.info(f"💾 Database insert completed in {db_elapsed:.3f}s for {len(records)} parameter values")
        else:
            logger.warning("⚠️ No valid records to insert into database")

    async def _insert_parameter_records(self, records: list):
        """Insert parameter records into parameter_value_history table."""
        try:
            logger.debug(f"💾 Getting Supabase connection for {len(records)} records")
            supabase = get_supabase()

            # Simple batch insert
            batch_size = 50
            total_batches = (len(records) + batch_size - 1) // batch_size
            logger.debug(f"💾 Processing {total_batches} batches with batch_size={batch_size}")

            for i in range(0, len(records), batch_size):
                batch_num = i // batch_size + 1
                batch = records[i:i+batch_size]

                logger.debug(f"💾 Inserting batch {batch_num}/{total_batches} ({len(batch)} records)")
                batch_start_time = time.time()

                result = supabase.table('parameter_value_history').insert(batch).execute()

                batch_elapsed = time.time() - batch_start_time
                logger.debug(f"💾 Batch {batch_num} completed in {batch_elapsed:.3f}s")

                if not result.data:
                    logger.warning(f"⚠️ No data returned for batch {batch_num}/{total_batches}")
                else:
                    logger.debug(f"✅ Batch {batch_num} inserted {len(result.data)} records successfully")

            logger.info(f"💾 All {total_batches} batches inserted successfully")

        except Exception as e:
            logger.error(f"❌ Failed to insert parameter records: {e}", exc_info=True)
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get current service status with enhanced debugging information."""
        current_time = time.time()
        uptime = current_time - (self.last_successful_read or current_time) if self.last_successful_read else 0

        status = {
            'service_name': 'Simple PLC Read Service',
            'is_running': self.is_running,
            'interval_seconds': self.interval,
            'error_count': self.error_count,
            'max_consecutive_errors': self.max_consecutive_errors,
            'last_successful_read': self.last_successful_read,
            'last_successful_read_ago_seconds': uptime if self.last_successful_read else None,
            'plc_connected': plc_manager.is_connected() if plc_manager.plc else False,
            'machine_id': MACHINE_ID,
            'current_timestamp': current_time,
            'service_health': 'healthy' if self.error_count < self.max_consecutive_errors else 'degraded'
        }

        logger.debug(f"📊 Service status requested: {status}")
        return status


async def main():
    """Main entry point for the service."""
    # Ensure only one instance runs
    ensure_single_instance()

    service = SimplePLCReadService()

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
    except Exception as e:
        logger.error(f"❌ Service error: {e}", exc_info=True)
    finally:
        await service.stop()
        logger.info("👋 Simple PLC Read Service stopped")


if __name__ == "__main__":
    asyncio.run(main())