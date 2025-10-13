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

from supabase import Client

from src.log_setup import get_service_logger, get_plc_logger, set_log_level, get_data_collection_logger
from src.config import MACHINE_ID
from src.db import create_async_supabase, get_supabase
from src.plc.manager import plc_manager
from src.connection_monitor import connection_monitor
from src.parameter_validation import validate_parameter_write

# Initialize parameter service logger (using PLC logger for consistency with parameter_control_listener)
logger = get_plc_logger()
data_logger = get_data_collection_logger()  # For parameter metadata initialization

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
        self.supabase: Client = None  # Sync Supabase client for metadata queries
        self.parameter_metadata: Dict[str, Dict[str, Any]] = {}  # Cache of parameter metadata

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

            # SAFETY VALIDATION before direct address write
            param_validation_info = {
                'data_type': data_type,
                'is_writable': True,  # Command override assumes writable
                'min_value': None,  # No bounds for direct address override (logged as warning)
                'max_value': None
            }
            is_valid, validation_error = validate_parameter_write(
                parameter_name, target_value, param_validation_info
            )
            if not is_valid:
                raise ValueError(f"Parameter validation failed: {validation_error}")

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
                    # Primary: Direct lookup by component_parameter_id in cache
                    logger.debug(f"🔍 [CACHE LOOKUP] Using component_parameter_id {component_parameter_id} for direct cache lookup")
                    cached_metadata = state.parameter_metadata.get(component_parameter_id)
                    if cached_metadata:
                        param_row = {
                            'id': component_parameter_id,
                            'name': cached_metadata.get('name'),
                            'data_type': cached_metadata.get('data_type'),
                            'min_value': cached_metadata.get('min_value'),
                            'max_value': cached_metadata.get('max_value'),
                            'is_writable': cached_metadata.get('is_writable'),
                            'component_name': cached_metadata.get('component_name')
                        }
                        logger.info(f"✅ [CACHE FOUND] Found parameter by ID in cache: {param_row.get('name', parameter_name)} (ID: {component_parameter_id})")
                        logger.debug(f"📋 [CACHE DETAILS] Parameter config from cache: data_type={param_row.get('data_type')}, writable={param_row.get('is_writable')}")
                    else:
                        logger.warning(f"⚠️ [CACHE LOOKUP] component_parameter_id {component_parameter_id} not found in cache, falling back to parameter_name lookup")

                # Fallback: parameter_name lookup using cache (parse Component.Parameter format)
                if not param_row:
                    logger.debug(f"🔍 [CACHE FALLBACK] Using parameter_name '{parameter_name}' for cache reverse lookup")

                    # Parse parameter_name format: "Component.Parameter" (e.g., "Precursor 3.temperature")
                    if '.' not in parameter_name:
                        raise ValueError(f"Invalid parameter_name format '{parameter_name}' - expected 'Component.Parameter'")

                    component_name, param_type = parameter_name.rsplit('.', 1)
                    logger.debug(f"🔍 [CACHE PARSE] Parsed parameter_name into component='{component_name}', type='{param_type}'")

                    # Map lowercase param_type to expected cache name (case-insensitive matching)
                    param_type_lower = param_type.lower()
                    type_to_name_mapping = {
                        'temperature': 'Temperature',
                        'pressure': 'Pressure',
                        'valve_state': 'Valve_State',
                        'state': 'State',
                        'flow_rate': 'Flow_Rate',
                        'set_point': 'Set_Point',
                        'binary': 'Binary_State',
                        'reading': 'Reading',
                        'value': 'Value'
                    }
                    expected_name = type_to_name_mapping.get(param_type_lower, param_type.title())

                    # Search cache for matching component_name and parameter name
                    found_param_id = None
                    found_metadata = None
                    for param_id, metadata in state.parameter_metadata.items():
                        if (metadata.get('component_name') == component_name and
                            metadata.get('name') == expected_name):
                            found_param_id = param_id
                            found_metadata = metadata
                            break

                    if found_param_id and found_metadata:
                        param_row = {
                            'id': found_param_id,
                            'name': found_metadata.get('name'),
                            'data_type': found_metadata.get('data_type'),
                            'min_value': found_metadata.get('min_value'),
                            'max_value': found_metadata.get('max_value'),
                            'is_writable': found_metadata.get('is_writable'),
                            'component_name': found_metadata.get('component_name')
                        }
                        logger.info(f"✅ [CACHE FOUND] Found parameter by name in cache: {parameter_name} (ID: {found_param_id})")
                        logger.debug(f"📋 [CACHE DETAILS] Parameter config from cache: data_type={param_row.get('data_type')}, writable={param_row.get('is_writable')}")

            except Exception as lookup_err:
                logger.error(f"Cache lookup error for '{parameter_name}' (ID: {component_parameter_id}): {lookup_err}")

            if not param_row:
                if component_parameter_id:
                    raise ValueError(
                        f"Parameter with component_parameter_id '{component_parameter_id}' and name '{parameter_name}' not found in cache"
                    )
                else:
                    raise ValueError(
                        f"Parameter '{parameter_name}' not found in cache (parsed as component='{component_name}', type='{param_type}')"
                    )

            parameter_id = param_row['id']
            data_type = param_row.get('data_type')

            # SAFETY VALIDATION before PLC write
            is_valid, validation_error = validate_parameter_write(
                parameter_name, target_value, param_row
            )
            if not is_valid:
                raise ValueError(f"Parameter validation failed: {validation_error}")

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
                    # Read with skip_noise=True for confirmation - simulation noise (±0.5-1.0) is 500-1000x
                    # larger than tolerance (0.001), causing false failures without this flag
                    current_value = await plc_manager.read_parameter(parameter_id, skip_noise=True)
                    if current_value is not None:
                        logger.info(f"📖 [VALUE CONFIRMED] Parameter {parameter_name} current value: {current_value} (target was: {target_value})")
                        # Check if value matches target (with tolerance for floats)
                        if data_type == 'binary':
                            matches = bool(current_value) == bool(target_value)
                        else:
                            # Use 1.0 absolute tolerance for analog parameters to handle real sensor noise
                            # Real hardware has ±0.1-1.0 units of natural noise from:
                            # - Sensor electrical noise (thermocouples, RTDs, pressure transducers)
                            # - ADC quantization error (typically ±1-2 LSB)
                            # - Modbus communication timing jitter
                            # - Environmental factors (EMI, temperature drift)
                            #
                            # LIMITATION: This is scale-dependent and may not work for all parameter types:
                            # - Works well for: temperature (°C), flow (sccm), small-range pressures
                            # - Too tight for: large-range pressures (mbar 0-100000)
                            # - Too loose for: high-precision measurements
                            #
                            # TODO: Move to parameter-specific tolerance stored in database
                            # (e.g., component_parameters.tolerance or percentage-based)
                            matches = abs(float(current_value) - float(target_value)) < 1.0

                        if matches:
                            logger.info(f"✅ [VALUE MATCH] Parameter value matches target exactly")
                        else:
                            error_msg = f"Confirmation read mismatch: expected {target_value}, got {current_value}"
                            logger.error(f"❌ [VALUE MISMATCH] {error_msg}")
                            # Mark command as failed due to confirmation mismatch
                            success = False
                    else:
                        logger.warning(f"⚠️ [CONFIRMATION READ] No value returned from confirmation read (cannot verify write)")
                except Exception as read_err:
                    logger.warning(f"⚠️ [CONFIRMATION READ] Confirmation read failed for '{parameter_name}': {read_err} (cannot verify write)")
            else:
                logger.error(f"❌ [PLC WRITE FAILED] PLC manager write failed, attempting fallback...")
                # Fallback by address when write fails and helpers exist
                addr = param_row.get('write_modbus_address')
                if addr is not None:
                    logger.info(f"📍 [FALLBACK WRITE] Using parameter table modbus address {addr} for {parameter_name}")
                    # Note: Validation already performed above, safe to proceed with fallback
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

        await _subscribe_with_timeout()

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


async def initialize_parameter_metadata_cache(service_state: ParameterServiceState) -> None:
    """Initialize parameter metadata cache for enhanced logging - adapted from Terminal 1."""
    try:
        data_logger.info("Loading parameter metadata for enhanced logging...")

        # Get all component parameters first
        params_response = service_state.supabase.table('component_parameters').select(
            'id, definition_id, component_id, min_value, max_value, is_writable, data_type'
        ).execute()

        # Get all component definitions
        defs_response = service_state.supabase.table('component_definitions').select(
            'id, name, type'
        ).execute()

        # Get all machine components (actual instances with correct names)
        components_response = service_state.supabase.table('machine_components').select(
            'id, name, definition_id'
        ).execute()

        # Create a lookup for component definitions
        component_defs = {def_item['id']: def_item for def_item in defs_response.data}

        # Create a lookup for component instances (maps component_id -> instance name)
        component_instances = {comp['id']: comp for comp in components_response.data}

        if params_response.data:
            for param in params_response.data:
                param_id = param['id']
                definition_id = param.get('definition_id')

                # Look up component definition
                component_def = component_defs.get(definition_id, {})
                component_type = component_def.get('type', '')

                # Use machine component instance name instead of definition name
                component_id = param.get('component_id')
                component_instance = component_instances.get(component_id, {})
                component_name = component_instance.get('name') or component_def.get('name', f'Component_{str(component_id)[:8] if component_id else "unknown"}')

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

                service_state.parameter_metadata[param_id] = {
                    'name': param_name,
                    'component_name': component_name,
                    'component_type': component_type,
                    'component_id': param.get('component_id'),
                    'data_type': data_type,
                    'unit': unit,
                    'min_value': param.get('min_value', 0),
                    'max_value': param.get('max_value', 0),
                    'is_writable': param.get('is_writable', False)
                }

            data_logger.info(f"✅ Loaded metadata for {len(service_state.parameter_metadata)} parameters")

            # Log a few examples of the metadata for debugging
            for i, (param_id, metadata) in enumerate(service_state.parameter_metadata.items()):
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

        # Initialize sync Supabase client for parameter metadata queries
        logger.info("Creating sync Supabase client...")
        state.supabase = get_supabase()
        logger.info("✅ Sync Supabase client initialized")

        # Create async Supabase client for realtime features
        logger.info("Creating async Supabase client...")
        state.async_supabase = await create_async_supabase()

        # Load parameter metadata cache
        logger.info("Loading parameter metadata cache...")
        await initialize_parameter_metadata_cache(state)
        logger.info("✅ Parameter metadata cache initialized")

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
                from src.parameter_validation import get_validation_stats
                validation_stats = get_validation_stats()

                logger.info(f"[Health Check] Realtime: {connection_monitor.realtime_status['connected']}, "
                           f"PLC: {plc_manager.is_connected()}, "
                           f"Processed: {len(state.processed_commands)}, "
                           f"Failed: {len(state.failed_commands)}")

                if validation_stats['total_parameters_with_failures'] > 0:
                    logger.warning(f"[Validation Stats] {validation_stats['total_parameters_with_failures']} parameters with validation failures: "
                                 f"{validation_stats['failure_details']}")

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