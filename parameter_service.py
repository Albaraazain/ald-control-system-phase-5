#!/usr/bin/env python3
"""
Terminal 3: Simple Parameter Service (parameter_service.py)

SIMPLIFIED IMPLEMENTATION:
- Listens for parameter commands from database
- Writes parameters DIRECTLY to PLC (NO coordination)
- Simple main loop with polling and realtime fallback
- Parameter validation and retry logic
- Direct PLC manager access

USER REQUIREMENT: Service that listens to parameter commands and writes directly to PLC.
"""
import asyncio
import argparse
import atexit
import fcntl
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional, Set

# Add project root to path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.log_setup import get_service_logger, get_plc_logger, set_log_level
from src.config import MACHINE_ID
from src.db import create_async_supabase, get_supabase
from src.plc.manager import plc_manager
from src.connection_monitor import connection_monitor

# Initialize parameter service logger (using PLC logger for consistency with parameter_control_listener)
logger = get_plc_logger()

# Global state for the parameter service
class ParameterServiceState:
    """Global state for parameter service operations"""
    def __init__(self):
        self.processed_commands: Set[str] = set()
        self.failed_commands: Dict[str, int] = {}
        self.max_retries = 3
        self.retry_delay_base = 5  # Base delay in seconds for exponential backoff
        self.is_running = False
        self.async_supabase = None

state = ParameterServiceState()


def ensure_single_instance():
    """Ensure only one parameter service instance runs"""
    lock_file = "/tmp/parameter_service.lock"
    pid_file = "main_pid.tmp"  # Use local PID file for consistency
    
    def cleanup_lock_files():
        """Clean up lock files on exit"""
        try:
            if os.path.exists(lock_file):
                os.unlink(lock_file)
            if os.path.exists(pid_file):
                os.unlink(pid_file)
        except Exception as e:
            logger.debug(f"Error cleaning up lock files: {e}")
    
    def signal_handler(signum, frame):
        """Handle signals to ensure cleanup"""
        logger.info(f"Received signal {signum}, cleaning up...")
        cleanup_lock_files()
        sys.exit(0)
    
    try:
        # Check if lock file exists and if the process is still running
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    old_pid = f.read().strip()
                    if old_pid and old_pid.isdigit():
                        # Check if the process is still running
                        try:
                            os.kill(int(old_pid), 0)  # This will raise OSError if process doesn't exist
                            logger.error("❌ Another parameter service is already running")
                            logger.error("💡 Kill existing instances or wait for them to finish")
                            exit(1)
                        except OSError:
                            # Process doesn't exist, remove stale lock file
                            logger.info("Removing stale lock file from previous run")
                            os.unlink(lock_file)
            except Exception as e:
                logger.debug(f"Error checking existing lock file: {e}")
                # Remove corrupted lock file
                if os.path.exists(lock_file):
                    os.unlink(lock_file)
        
        # Create new lock file
        fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Write PID to lock file
        pid = os.getpid()
        os.write(fd, f"{pid}\n".encode())
        os.fsync(fd)

        # Also write to local PID file for consistency
        with open(pid_file, 'w') as f:
            f.write(f"{pid}\n")

        # Set up cleanup handlers
        atexit.register(cleanup_lock_files)
        
        # Set up signal handlers for proper cleanup
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        return fd
    except (OSError, IOError) as e:
        logger.error("❌ Another parameter service is already running")
        logger.error("💡 Kill existing instances or wait for them to finish")
        logger.debug(f"Lock error: {e}")
        exit(1)


async def ensure_plc_connection() -> bool:
    """
    Ensure PLC is connected, attempt to reconnect if not.
    Uses the connection monitor's status for consistency.

    Returns:
        bool: True if connected or reconnected successfully, False otherwise
    """
    logger.debug("🔍 [CONNECTION CHECK] Verifying PLC connection status...")

    # First check with connection monitor's status
    if connection_monitor.plc_status["connected"]:
        logger.debug("✅ [CONNECTION CHECK] PLC connection confirmed via monitor")
        return True

    # If monitor says disconnected but manager says connected, verify
    if plc_manager.is_connected():
        logger.info("✅ [CONNECTION CHECK] PLC manager reports connected, updating monitor status")
        connection_monitor.plc_status["connected"] = True
        return True

    logger.warning("⚠️ [CONNECTION CHECK] PLC is not connected. Waiting for connection monitor to reconnect...")

    # Wait a bit for the connection monitor to do its job
    max_wait = 30  # seconds
    wait_interval = 2  # seconds
    total_waited = 0

    while total_waited < max_wait:
        await asyncio.sleep(wait_interval)
        total_waited += wait_interval
        logger.debug(f"⏱️ [CONNECTION WAIT] Waiting for PLC reconnection... ({total_waited}/{max_wait}s)")

        if connection_monitor.plc_status["connected"] or plc_manager.is_connected():
            logger.info(f"✅ [CONNECTION RESTORED] PLC connection restored after {total_waited}s")
            return True

    logger.error(f"❌ [CONNECTION TIMEOUT] PLC connection not restored after {max_wait} seconds")
    return False


async def process_parameter_command(command: Dict[str, Any]):
    """
    Process a parameter control command by executing it via PLC manager DIRECTLY.
    NO COORDINATION - direct PLC access as requested by user.

    Args:
        command: The command data from the database
    """
    start_time = time.time()

    command_id = command['id']
    parameter_name = command['parameter_name']
    target_value = float(command['target_value'])
    timeout_ms = command.get('timeout_ms', 30000)
    machine_id = command.get('machine_id', 'global')

    logger.info(f"⚙️ [PARAMETER START] Command ID: {command_id} | Parameter: {parameter_name} | Target: {target_value} | Machine: {machine_id} | Timeout: {timeout_ms}ms")
    logger.debug(f"🔍 [PARAMETER DETAILS] Full command data: {command}")

    supabase = get_supabase()

    try:
        # Ensure PLC is connected, attempt reconnection if needed
        if not await ensure_plc_connection():
            # Track retry count
            retry_count = state.failed_commands.get(command_id, 0) + 1
            state.failed_commands[command_id] = retry_count

            # Calculate backoff delay
            backoff_delay = state.retry_delay_base * (2 ** (retry_count - 1))

            error_msg = f"PLC is not connected (retry {retry_count}/{state.max_retries})"
            logger.warning(f"{error_msg}. Will retry in {backoff_delay} seconds")

            # Record the error but keep as uncompleted for retry
            if retry_count < state.max_retries:
                supabase.table("parameter_control_commands").update({
                    "error_message": error_msg
                }).eq("id", command_id).execute()

                # Remove from processed to allow retry
                state.processed_commands.discard(command_id)

                # Wait before allowing retry
                await asyncio.sleep(backoff_delay)
                return
            else:
                raise RuntimeError(f"PLC connection failed after {state.max_retries} attempts")

        # Check for command-level modbus address override first
        command_write_addr = command.get('write_modbus_address') or command.get('modbus_address')
        logger.debug(f"🔍 [ADDRESS CHECK] Command modbus address override: {command_write_addr}")

        success = False
        current_value = None
        parameter_id = None
        data_type = None

        if command_write_addr is not None:
            # Use command override address - skip parameter table lookup for address
            logger.info(f"📍 [ADDRESS OVERRIDE] Using modbus address {command_write_addr} from command {command_id}")
            data_type = command.get('data_type', 'float')  # Default to float if not specified
            logger.debug(f"🔢 [DATA TYPE] Parameter data type: {data_type}")

            # Write directly using override address
            logger.debug(f"✏️ [PLC WRITE START] Writing to modbus address {command_write_addr}...")

            # Handle both RealPLC (with communicator) and SimulationPLC (direct methods)
            if hasattr(plc_manager.plc, 'communicator'):
                # RealPLC with communicator
                if hasattr(plc_manager.plc.communicator, 'write_coil') and data_type == 'binary':
                    bool_value = bool(target_value)
                    logger.debug(f"✏️ [PLC WRITE] Writing binary value {bool_value} to coil {command_write_addr}")
                    success = plc_manager.plc.communicator.write_coil(command_write_addr, bool_value)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Binary value {bool_value} written to coil {command_write_addr}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write binary value to coil {command_write_addr}")
                elif (hasattr(plc_manager.plc.communicator, 'write_float') and callable(getattr(plc_manager.plc.communicator, 'write_float'))) or (hasattr(plc_manager.plc.communicator, 'write_integer_32bit') and callable(getattr(plc_manager.plc.communicator, 'write_integer_32bit'))):
                    float_value = float(target_value)
                    logger.debug(f"✏️ [PLC WRITE] Writing float value {float_value} to holding register {command_write_addr}")
                    # Use write_float for float values, write_integer_32bit for integer values
                    if hasattr(plc_manager.plc.communicator, 'write_integer_32bit') and callable(getattr(plc_manager.plc.communicator, 'write_integer_32bit')) and (isinstance(target_value, int) or target_value.is_integer()):
                        success = plc_manager.plc.communicator.write_integer_32bit(command_write_addr, int(float_value))
                    elif hasattr(plc_manager.plc.communicator, 'write_float') and callable(getattr(plc_manager.plc.communicator, 'write_float')):
                        success = plc_manager.plc.communicator.write_float(command_write_addr, float_value)
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] No suitable write method available on communicator")
                        success = False
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Float value {float_value} written to holding register {command_write_addr}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write float value to holding register {command_write_addr}")
                else:
                    logger.warning(f"⚠️ [PLC INTERFACE] PLC communicator doesn't support direct address writing")
                    success = False
            else:
                # SimulationPLC with direct methods
                if hasattr(plc_manager.plc, 'write_coil') and data_type == 'binary':
                    bool_value = bool(target_value)
                    logger.debug(f"✏️ [PLC WRITE] Writing binary value {bool_value} to coil {command_write_addr}")
                    success = await plc_manager.plc.write_coil(command_write_addr, bool_value)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Binary value {bool_value} written to coil {command_write_addr}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write binary value to coil {command_write_addr}")
                elif hasattr(plc_manager.plc, 'write_holding_register'):
                    float_value = float(target_value)
                    logger.debug(f"✏️ [PLC WRITE] Writing float value {float_value} to holding register {command_write_addr}")
                    success = await plc_manager.plc.write_holding_register(command_write_addr, float_value)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Float value {float_value} written to holding register {command_write_addr}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write float value to holding register {command_write_addr}")
                else:
                    logger.warning(f"⚠️ [PLC INTERFACE] PLC doesn't support direct address writing")
                    success = False
        else:
            # No override address - use parameter lookup with component_parameter_id preference
            param_row = None
            component_parameter_id = command.get('component_parameter_id')

            try:
                if component_parameter_id:
                    # Primary: Direct lookup by component_parameter_id (preferred method)
                    logger.debug(f"🔍 [PARAM LOOKUP] Using component_parameter_id {component_parameter_id} for direct parameter lookup")
                    q_id = (
                        supabase.table('component_parameters_full')
                        .select('*')
                        .eq('id', component_parameter_id)
                        .execute()
                    )
                    rows = q_id.data or []
                    if rows:
                        param_row = rows[0]
                        logger.info(f"✅ [PARAM FOUND] Found parameter by ID: {param_row.get('name', parameter_name)} (ID: {component_parameter_id})")
                        logger.debug(f"📋 [PARAM DETAILS] Parameter config: modbus_addr={param_row.get('write_modbus_address')}, data_type={param_row.get('data_type')}, writable={param_row.get('is_writable')}")
                    else:
                        logger.warning(f"⚠️ [PARAM LOOKUP] component_parameter_id {component_parameter_id} not found, falling back to parameter_name lookup")

                # Fallback: parameter_name lookup (for backward compatibility)
                if not param_row:
                    logger.debug(f"🔍 [PARAM FALLBACK] Using parameter_name '{parameter_name}' for fallback lookup")
                    q1 = (
                        supabase.table('component_parameters_full')
                        .select('*')
                        .eq('parameter_name', parameter_name)
                        .execute()
                    )
                    rows = q1.data or []

                    if rows:
                        # Prefer writable parameter when multiple rows
                        writable_rows = [r for r in rows if r.get('is_writable')]
                        param_row = (writable_rows[0] if writable_rows else rows[0])
                        if len(rows) > 1:
                            logger.warning(f"⚠️ [PARAM AMBIGUOUS] Multiple parameters found for name '{parameter_name}', using {param_row['id']}. Consider using component_parameter_id for precise targeting.")
                            param_info = [f"ID:{r['id']} writable:{r.get('is_writable')}" for r in rows]
                            logger.debug(f"📋 [PARAM OPTIONS] Found {len(rows)} parameters: {param_info}")
                        logger.info(f"✅ [PARAM FOUND] Found parameter by name: {parameter_name} (ID: {param_row['id']})")
                        logger.debug(f"📋 [PARAM DETAILS] Parameter config: modbus_addr={param_row.get('write_modbus_address')}, data_type={param_row.get('data_type')}, writable={param_row.get('is_writable')}")

            except Exception as lookup_err:
                logger.error(f"Parameter lookup error for '{parameter_name}' (ID: {component_parameter_id}): {lookup_err}")

            if not param_row:
                if component_parameter_id:
                    raise ValueError(
                        f"Parameter with component_parameter_id '{component_parameter_id}' and name '{parameter_name}' not found"
                    )
                else:
                    raise ValueError(
                        f"Parameter '{parameter_name}' not found in component_parameters_full"
                    )

            parameter_id = param_row['id']
            data_type = param_row.get('data_type')

            # DIRECT PLC ACCESS - write via PLC manager (NO coordination)
            logger.info(
                f"✏️ [PLC WRITE START] Writing parameter DIRECTLY to PLC: id={parameter_id} name={parameter_name} value={target_value}"
            )
            success = await plc_manager.write_parameter(parameter_id, target_value)

            if success:
                logger.info(f"✅ [PLC WRITE SUCCESS] Parameter written successfully via PLC manager")
                # Confirmation read when available
                try:
                    logger.debug(f"🔍 [CONFIRMATION READ] Attempting to read back parameter value...")
                    current_value = await plc_manager.read_parameter(parameter_id)
                    if current_value is not None:
                        logger.info(f"📖 [VALUE CONFIRMED] Parameter {parameter_name} current value: {current_value} (target was: {target_value})")
                        # Check if value matches target (with tolerance for floats)
                        if data_type == 'binary':
                            matches = bool(current_value) == bool(target_value)
                        else:
                            matches = abs(float(current_value) - float(target_value)) < 0.001

                        if matches:
                            logger.info(f"✅ [VALUE MATCH] Parameter value matches target exactly")
                        else:
                            logger.debug(f"🔍 [VALUE MISMATCH] Parameter value {current_value} differs from target {target_value} (expected in simulation mode)")
                    else:
                        logger.debug(f"🔍 [CONFIRMATION READ] No value returned from confirmation read")
                except Exception as read_err:
                    logger.debug(f"⚠️ [CONFIRMATION READ] Confirmation read failed for '{parameter_name}': {read_err}")
            else:
                logger.error(f"❌ [PLC WRITE FAILED] PLC manager write failed, attempting fallback...")
                # Fallback by address when write fails and helpers exist
                addr = param_row.get('write_modbus_address')
                if addr is not None:
                    logger.info(f"📍 [FALLBACK WRITE] Using parameter table modbus address {addr} for {parameter_name}")
                    if hasattr(plc_manager.plc.communicator, 'write_coil') and data_type == 'binary':
                        bool_value = bool(target_value)
                        logger.debug(f"✏️ [FALLBACK WRITE] Writing binary {bool_value} to coil {addr}")
                        success = plc_manager.plc.communicator.write_coil(addr, bool_value)
                        if success:
                            logger.info(f"✅ [FALLBACK SUCCESS] Binary value written to coil via fallback")
                        else:
                            logger.error(f"❌ [FALLBACK FAILED] Fallback coil write failed")
                    elif hasattr(plc_manager.plc.communicator, 'write_float') or hasattr(plc_manager.plc.communicator, 'write_integer_32bit'):
                        if isinstance(target_value, int) or target_value.is_integer():
                            success = plc_manager.plc.communicator.write_integer_32bit(addr, int(float(target_value)))
                        else:
                            success = plc_manager.plc.communicator.write_float(addr, float(target_value))
                        if success:
                            logger.info(f"✅ [FALLBACK SUCCESS] Float value written to holding register via fallback")
                        else:
                            logger.error(f"❌ [FALLBACK FAILED] Fallback holding register write failed")
                else:
                    logger.error(f"❌ [NO ADDRESS] No modbus address available for parameter {parameter_name} (ID: {parameter_id})")

        # Update command status based on result
        if success:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ [COMMAND SUCCESS] Parameter command completed successfully")
            logger.info(f"📊 [PERFORMANCE] Command ID: {command_id} | Parameter: {parameter_name} | Duration: {processing_time_ms}ms")
            if current_value is not None:
                logger.info(f"📈 [VALUE CHANGE] Final value: {current_value} (was target: {target_value})")

            # Clear failed command tracking
            if command_id in state.failed_commands:
                retry_count = state.failed_commands.pop(command_id)
                logger.debug(f"🔄 [RETRY CLEARED] Cleared failed command tracking after {retry_count} previous attempts")

            logger.debug(f"💾 [DB UPDATE] Finalizing successful command in database...")
            await finalize_parameter_command(command_id, success=True)
        else:
            # Track retry count
            retry_count = state.failed_commands.get(command_id, 0) + 1
            state.failed_commands[command_id] = retry_count

            if retry_count < state.max_retries:
                error_msg = f"Failed to write parameter to PLC (retry {retry_count}/{state.max_retries})"
                logger.warning(f"⚠️ [RETRY ATTEMPT] Command {command_id}: {error_msg}")

                # Calculate backoff delay for next retry
                backoff_delay = state.retry_delay_base * (2 ** (retry_count - 1))
                logger.debug(f"⏱️ [RETRY SCHEDULE] Next retry in {backoff_delay}s (exponential backoff)")

                # Record the error for visibility and allow retry
                logger.debug(f"💾 [DB UPDATE] Recording retry attempt in database...")
                supabase.table("parameter_control_commands").update({
                    "error_message": error_msg
                }).eq("id", command_id).execute()
                logger.debug(f"✅ [DB UPDATED] Error message recorded for retry tracking")

                # Remove from processed to allow retry
                state.processed_commands.discard(command_id)
                logger.debug(f"🔄 [RETRY ENABLED] Command removed from processed set for retry")
            else:
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.error(f"❌ [COMMAND FAILED] Parameter command failed permanently")
                logger.error(f"📊 [FAILURE DETAILS] ID: {command_id} | Parameter: {parameter_name} | Status: MAX_RETRIES_EXCEEDED | Duration: {processing_time_ms}ms")
                logger.debug(f"💾 [DB UPDATE] Finalizing failed command in database...")
                await finalize_parameter_command(command_id, success=False, error_message=f"Failed to write parameter to PLC after {state.max_retries} attempts")

    except Exception as e:
        error_msg = f"Error executing parameter command: {str(e)}"
        logger.error(f"Parameter command {command_id} failed: {error_msg}", exc_info=True)

        # Track retry count for other errors too
        retry_count = state.failed_commands.get(command_id, 0) + 1
        state.failed_commands[command_id] = retry_count

        if retry_count < state.max_retries and "PLC" in str(e):
            # For PLC-related errors, allow retry
            error_msg_with_retry = f"{error_msg} (retry {retry_count}/{state.max_retries})"

            # Record the error and allow retry after backoff
            supabase.table("parameter_control_commands").update({
                "error_message": error_msg_with_retry
            }).eq("id", command_id).execute()

            # Remove from processed to allow retry
            state.processed_commands.discard(command_id)

            # Wait with exponential backoff
            backoff_delay = state.retry_delay_base * (2 ** (retry_count - 1))
            await asyncio.sleep(backoff_delay)
        else:
            # Non-PLC errors or exceeded retries
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ PARAMETER COMMAND FAILED - ID: {command_id} | Parameter: {parameter_name} | Status: ERROR | Duration: {processing_time_ms}ms")
            await finalize_parameter_command(command_id, success=False, error_message=f"{error_msg} (after {retry_count} attempts)")


async def finalize_parameter_command(
    command_id: str,
    success: bool,
    error_message: Optional[str] = None,
):
    """Finalize a parameter control command by setting completed_at and optional error message."""
    try:
        supabase = get_supabase()
        update_data = {
            "completed_at": datetime.utcnow().isoformat()
        }
        if not success and error_message is not None:
            update_data["error_message"] = error_message

        result = (
            supabase.table("parameter_control_commands")
            .update(update_data)
            .eq("id", command_id)
            .execute()
        )
        if result.data:
            logger.info(f"Command {command_id} finalized: {'completed' if success else 'failed'}")
        else:
            logger.warning(f"Failed to finalize parameter command {command_id}")
    except Exception as e:
        logger.error(f"Error finalizing parameter command: {str(e)}", exc_info=True)


async def handle_parameter_command_insert(payload):
    """
    Handle an insert event for a parameter control command.

    Args:
        payload: The event payload from Supabase
    """
    try:
        # Determine if this is from realtime or polling using connection_monitor
        realtime_connected = connection_monitor.realtime_status["connected"]
        source = "realtime" if realtime_connected else "polling"
        logger.info(f"🔔 PARAMETER COMMAND RECEIVED [{source.upper()}] - Processing parameter control command")

        # Update realtime status if this came from realtime
        if realtime_connected:
            connection_monitor.update_realtime_status(True)

        # Extract the command record from the payload
        record = payload.get("data", {}).get("record")
        if not record:
            logger.error(f"Invalid payload structure: {payload}")
            return

        # Only process commands for this machine
        if "machine_id" in record and record["machine_id"] is not None:
            if record["machine_id"] != MACHINE_ID:
                logger.info(
                    f"Ignoring parameter command for different machine: {record['machine_id']}"
                )
                return

        # Process if not yet executed
        command_id = record["id"]
        parameter_name = record.get("parameter_name", "?")

        # Already processed?
        if command_id in state.processed_commands:
            logger.debug(f"Command {command_id} already processed, skipping")
            return

        # Skip if already claimed/executed
        if record.get("executed_at") is not None:
            logger.debug(f"Command {command_id} already executed, skipping")
            state.processed_commands.add(command_id)
            return

        # Retry budget check
        if state.failed_commands.get(command_id, 0) >= state.max_retries:
            logger.warning(f"Command {command_id} exceeded max retries ({state.max_retries}), marking failed")
            await finalize_parameter_command(command_id, success=False, error_message=f"Exceeded maximum retry attempts ({state.max_retries})")
            state.processed_commands.add(command_id)
            return

        logger.info(f"🟡 PARAMETER COMMAND PROCESSING - ID: {command_id} | Parameter: {parameter_name} | Status: CLAIMED")

        # Ensure PLC connection before claiming
        if not await ensure_plc_connection():
            logger.warning(f"Cannot process command {command_id}: PLC is not connected")
            return

        # Claim by setting executed_at if still NULL
        supabase = get_supabase()
        result = (
            supabase.table("parameter_control_commands")
            .update({
                "executed_at": datetime.utcnow().isoformat(),
                "error_message": None
            })
            .eq("id", command_id)
            .is_("executed_at", None)
            .execute()
        )

        if result.data and len(result.data) > 0:
            logger.info(f"🟢 PARAMETER COMMAND EXECUTING - ID: {command_id} | Status: PROCESSING")
            state.processed_commands.add(command_id)
            await process_parameter_command(record)
        else:
            logger.info(f"⚠️ PARAMETER COMMAND SKIPPED - ID: {command_id} | Status: ALREADY_CLAIMED")
            state.processed_commands.add(command_id)

    except Exception as e:
        logger.error(f"Error handling parameter command insert: {str(e)}", exc_info=True)


async def check_pending_parameter_commands():
    """
    Check for existing pending parameter control commands and process them.
    This is called after subscribing to the channel to handle any commands
    that were inserted before the subscription was established.
    """
    try:
        logger.info("Checking for existing pending parameter control commands...")
        supabase = get_supabase()

        # Query for pending parameter control commands for this machine
        # Exclude commands that have been processed or exceeded retry limit
        result = (
            supabase.table("parameter_control_commands")
            .select("*")
            .is_("executed_at", None)
            .order("created_at", desc=False)
            .execute()
        )

        if result.data and len(result.data) > 0:
            # Filter out already processed commands and those that exceeded retry limit
            # Include commands for this machine OR global commands (machine_id is NULL)
            commands_to_process = [
                cmd for cmd in result.data
                if (
                    (cmd.get('machine_id') in (None, MACHINE_ID))
                    and (cmd['id'] not in state.processed_commands)
                    and (state.failed_commands.get(cmd['id'], 0) < state.max_retries)
                )
            ]

            if commands_to_process:
                logger.info(f"Found {len(commands_to_process)} pending parameter control commands to process")

                # Check PLC connection before processing
                if not await ensure_plc_connection():
                    logger.warning("Cannot process parameter commands: PLC is not connected")
                    # Don't mark as failed yet, will retry on next poll
                    return

                for command in commands_to_process:
                    logger.info(f"Processing existing pending parameter command: {command['id']}")
                    # Create a payload similar to what would be received from a realtime event
                    payload = {
                        "data": {
                            "record": command
                        }
                    }
                    await handle_parameter_command_insert(payload)
            else:
                logger.debug("No new pending parameter control commands to process")
        else:
            logger.debug("No pending parameter control commands found")

    except Exception as e:
        logger.error(f"Error checking pending parameter commands: {str(e)}", exc_info=True)


async def poll_for_parameter_commands():
    """
    Periodically poll for new pending parameter control commands.
    This serves as a fallback when realtime isn't working and as a safety net.
    """
    # Use connection_monitor for realtime status instead of global variable
    realtime_connected = connection_monitor.realtime_status["connected"]
    poll_interval = 1 if not realtime_connected else 10  # Simplified logic

    logger.info(f"Starting parameter command polling (interval: {poll_interval}s, realtime: {realtime_connected})")

    while state.is_running:
        try:
            # Check current realtime status from connection_monitor
            realtime_connected = connection_monitor.realtime_status["connected"]

            # Poll if realtime is disconnected or as periodic safety check (every minute)
            should_poll = not realtime_connected or (asyncio.get_event_loop().time() % 60 < 1)

            if should_poll:
                await check_pending_parameter_commands()

            # Clean up old processed commands periodically (keep last 100)
            if len(state.processed_commands) > 100:
                processed_list = list(state.processed_commands)
                state.processed_commands.clear()
                state.processed_commands.update(processed_list[-50:])
                logger.debug(f"Cleaned up processed commands cache, kept {len(state.processed_commands)} entries")

            # Clean up old failed commands
            if len(state.failed_commands) > 50:
                cleaned_count = 0
                failed_commands_copy = state.failed_commands.copy()
                for cmd_id, retry_count in failed_commands_copy.items():
                    if retry_count >= state.max_retries:
                        del state.failed_commands[cmd_id]
                        cleaned_count += 1
                if cleaned_count > 0:
                    logger.debug(f"Cleaned up {cleaned_count} failed commands from cache")

            # Simplified interval: fast when realtime down, slower when working
            poll_interval = 1 if not realtime_connected else 10
            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error in parameter command polling: {str(e)}", exc_info=True)
            await asyncio.sleep(poll_interval)


async def setup_parameter_control_listener():
    """
    Set up a listener for parameter control command inserts in the Supabase database.
    Uses realtime channels for instant updates with polling as a fallback.
    """
    logger.info("Setting up parameter control listener with realtime support...")

    try:
        # Create channel name for parameter control commands
        channel_name = f"parameter-control-commands-{MACHINE_ID}"

        # Define callback for INSERT events only
        def on_insert(payload):
            logger.info("🔔 PARAMETER COMMAND RECEIVED [REALTIME] - Processing new parameter control command")
            logger.debug(f"Payload: {payload}")
            asyncio.create_task(handle_parameter_command_insert(payload))

        def on_error(payload):
            logger.error(f"Realtime channel error: {payload}")
            connection_monitor.update_realtime_status(False, f"Channel error: {payload}")

        # Direct subscription using async_supabase (only INSERT)
        realtime_channel = state.async_supabase.channel(channel_name)
        logger.info("Setting up realtime subscription for parameter_control_commands INSERT events only...")
        realtime_channel = realtime_channel.on_postgres_changes(
            event="INSERT",
            schema="public",
            table="parameter_control_commands",
            callback=on_insert
        )

        # Subscribe to the channel in background with watchdog timeout to prevent setup hang
        logger.info("Subscribing to realtime channel...")
        async def _subscribe_with_timeout():
            try:
                await asyncio.wait_for(realtime_channel.subscribe(), timeout=10.0)
                connection_monitor.update_realtime_status(True)
                logger.info(f"Successfully subscribed to realtime channel: {channel_name}")
            except asyncio.TimeoutError:
                logger.warning("Realtime subscription timed out after 10 seconds; continuing with polling")
                connection_monitor.update_realtime_status(False, "realtime subscribe timeout")
            except Exception as sub_err:
                logger.error(f"Realtime subscribe error: {sub_err}", exc_info=True)
                connection_monitor.update_realtime_status(False, str(sub_err))

        asyncio.create_task(_subscribe_with_timeout())

    except Exception as e:
        logger.error(f"Failed to set up realtime channel: {str(e)}", exc_info=True)
        logger.warning("Realtime subscription failed, will rely on polling mechanism")
        connection_monitor.update_realtime_status(False, str(e))

    # Check for existing pending commands
    logger.info("Checking for existing pending parameter control commands...")
    await check_pending_parameter_commands()

    # Start polling for commands as a fallback (will be more aggressive if realtime fails)
    poll_task = asyncio.create_task(poll_for_parameter_commands())
    logger.info("Started parameter control command polling as fallback mechanism")

    # Log the final status using connection_monitor as single source of truth
    if connection_monitor.realtime_status["connected"]:
        logger.info("✅ Parameter control listener ready with REALTIME + polling fallback")
    else:
        logger.warning("⚠️ Parameter control listener ready with POLLING ONLY (realtime failed)")


async def cleanup_handler():
    """Perform cleanup when application is interrupted"""
    logger.info(f"🧹 [CLEANUP START] Beginning parameter service cleanup...")

    try:
        # Stop the service
        logger.debug(f"⏹️ [SHUTDOWN] Stopping parameter service...")
        state.is_running = False
        logger.debug(f"✅ [SHUTDOWN] Service stopped successfully")

        # No complex coordination to cleanup - just direct PLC access
        logger.debug(f"📋 [CLEANUP] No complex coordination to cleanup - using direct PLC access")

    except Exception as e:
        logger.exception(f"❌ [CLEANUP ERROR] Error during parameter service cleanup")
    finally:
        logger.info(f"✅ [SHUTDOWN COMPLETE] Parameter service shutdown complete")
        sys.exit(0)


async def main():
    """
    Main function for Terminal 3: Simple Parameter Service
    Sets up parameter control listener and runs indefinitely with DIRECT PLC ACCESS
    """
    async def signal_handler(signal, frame):
        """Handle SIGINT signal"""
        logger.info(f"⚠️ [SIGNAL] Received interrupt signal, initiating cleanup...")
        await cleanup_handler()

    try:
        # Ensure single instance before any initialization
        logger.info("Checking for existing parameter service instances...")
        ensure_single_instance()
        logger.info("✅ Single instance lock acquired successfully")

        logger.info("Starting Terminal 3: Simple Parameter Service (DIRECT PLC ACCESS)")
        logger.info("="*60)
        logger.info("Simple Parameter Service Configuration:")
        logger.info(f"  - Machine ID: {MACHINE_ID}")
        logger.info(f"  - Max Retries: {state.max_retries}")
        logger.info(f"  - Retry Base Delay: {state.retry_delay_base}s")
        logger.info(f"  - Architecture: DIRECT PLC ACCESS (NO coordination)")
        logger.info("="*60)

        # Set up signal handler
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(signal_handler(s, f)))

        # Initialize PLC manager
        logger.info("Initializing PLC manager...")
        success = await plc_manager.initialize()
        if success:
            logger.info("✅ PLC manager initialized successfully")
        else:
            logger.warning("⚠️ PLC manager initialization failed, will retry during operation")

        # Create async Supabase client for realtime features
        logger.info("Creating async Supabase client...")
        state.async_supabase = await create_async_supabase()

        # Start parameter control listener
        logger.info("Starting parameter control listener...")
        state.is_running = True
        await setup_parameter_control_listener()

        logger.info("Simple parameter service running and ready to process commands")
        logger.info("="*60)
        logger.info("System Status:")
        logger.info(
            f"  - Realtime Channels: "
            f"{'✅ Active' if connection_monitor.realtime_status['connected'] else '⚠️ Using Polling'}"
        )
        logger.info(f"  - PLC Connection: {'✅ Connected' if plc_manager.is_connected() else '⚠️ Disconnected'}")
        logger.info(f"  - Machine ID: {MACHINE_ID}")
        logger.info("="*60)
        logger.info("Simple parameter service is ready to receive commands")

        # Keep the application running indefinitely
        while state.is_running:
            await asyncio.sleep(1)

            # Periodic status logging
            if asyncio.get_event_loop().time() % 300 < 1:  # Every 5 minutes
                logger.info(f"[Health Check] Realtime: {connection_monitor.realtime_status['connected']}, "
                           f"PLC: {plc_manager.is_connected()}, "
                           f"Processed: {len(state.processed_commands)}, "
                           f"Failed: {len(state.failed_commands)}")

    except Exception as e:
        logger.error(f"Error in parameter service main loop: {str(e)}", exc_info=True)
        await cleanup_handler()
        raise


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Terminal 3: Simple Parameter Service (Direct PLC Access)")
    parser.add_argument("--log-level", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
                        help="Logging level (default from LOG_LEVEL env or INFO)")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts for failed commands")
    parser.add_argument("--retry-delay", type=int, default=5, help="Base delay for exponential backoff (seconds)")
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()

    # Apply log level if specified
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level
        set_log_level(args.log_level)

    # Configure retry settings
    if args.max_retries:
        state.max_retries = args.max_retries
    if args.retry_delay:
        state.retry_delay_base = args.retry_delay

    # Run the service
    asyncio.run(main())