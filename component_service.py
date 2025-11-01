#!/usr/bin/env python3
"""
Component Service (component_service.py)

SIMPLIFIED IMPLEMENTATION:
- Listens for component commands from database
- Processes component control operations DIRECTLY (NO coordination)
- Simple main loop with polling and realtime fallback
- Component validation and retry logic
- Direct PLC manager access

USER REQUIREMENT: Service that listens to component commands and processes component operations.
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

# Initialize component service logger (using PLC logger for consistency with component_control_listener)
logger = get_plc_logger()
data_logger = get_data_collection_logger()  # For component metadata initialization

# Global state for the component service
class ComponentServiceState:
    """Global state for component service operations"""
    def __init__(self):
        self.processed_commands: Set[str] = set()
        self.failed_commands: Dict[str, int] = {}
        self.max_retries = 3
        self.retry_delay_base = 5  # Base delay in seconds for exponential backoff
        self.is_running = False
        self.async_supabase = None
        self.supabase: Client = None  # Sync Supabase client for metadata queries
        self.component_metadata: Dict[str, Dict[str, Any]] = {}  # Cache of component metadata

state = ComponentServiceState()


def ensure_single_instance():
    """Ensure only one component service instance runs"""
    lock_file = "/tmp/component_service.lock"
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
                            logger.error("❌ Another component service is already running")
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
        logger.error("❌ Another component service is already running")
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


async def process_component_command(command: Dict[str, Any]):
    """
    Process a component control command (turn_on/turn_off operations).

    Args:
        command: Command data from component_control_commands table
                Required fields: id, component_id, action
    """
    start_time = time.time()

    # Extract component command fields (NOT parameter fields)
    command_id = command['id']
    component_id = command['component_id']
    action = command['action']  # 'turn_on' or 'turn_off'
    reason = command.get('reason', 'manual')
    machine_id = command.get('machine_id', 'global')

    logger.info(f"⚙️ [COMPONENT START] Command ID: {command_id} | Component ID: {component_id} | Action: {action} | Reason: {reason} | Machine: {machine_id}")
    logger.debug(f"🔍 [COMPONENT DETAILS] Full command data: {command}")

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
                supabase.table("component_control_commands").update({
                    "error_message": error_msg
                }).eq("id", command_id).execute()

                # Remove from processed to allow retry
                state.processed_commands.discard(command_id)

                # Wait before allowing retry
                await asyncio.sleep(backoff_delay)
                return
            else:
                raise RuntimeError(f"PLC connection failed after {state.max_retries} attempts")

        # Load component metadata from machine_components table
        logger.debug(f"🔍 [COMPONENT LOOKUP] Fetching component metadata for ID: {component_id}")
        component_response = supabase.table('machine_components').select('*').eq('id', component_id).execute()

        if not component_response.data or len(component_response.data) == 0:
            raise ValueError(f"Component {component_id} not found in machine_components table")

        component_data = component_response.data[0]
        component_type = component_data.get('type') or component_data.get('component_type')
        component_name = component_data.get('name')
        modbus_address = component_data.get('modbus_address') or component_data.get('write_modbus_address')

        logger.info(f"📦 [COMPONENT] Type: {component_type}, Name: {component_name}, Address: {modbus_address}")

        # Validate action
        if action not in ['turn_on', 'turn_off']:
            raise ValueError(f"Invalid action: {action}. Must be 'turn_on' or 'turn_off'")

        # Convert action to boolean for PLC write
        target_state = (action == 'turn_on')  # True for on, False for off
        logger.debug(f"🔢 [ACTION CONVERSION] Action '{action}' -> Boolean: {target_state}")

        success = False

        if modbus_address is not None:
            # Write component state to PLC coil
            logger.debug(f"✏️ [PLC WRITE START] Writing {action} (boolean={target_state}) to coil address {modbus_address}...")

            # Handle both RealPLC (with communicator) and SimulationPLC (direct methods)
            if hasattr(plc_manager.plc, 'communicator'):
                # RealPLC with communicator
                if hasattr(plc_manager.plc.communicator, 'write_coil'):
                    logger.debug(f"✏️ [PLC WRITE] Writing boolean {target_state} to coil {modbus_address}")
                    success = plc_manager.plc.communicator.write_coil(modbus_address, target_state)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Component {component_name} set to {action} at coil {modbus_address}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write {action} to component {component_name} at coil {modbus_address}")
                else:
                    logger.error(f"❌ [PLC INTERFACE] PLC communicator doesn't support write_coil")
                    success = False
            else:
                # SimulationPLC with direct methods
                if hasattr(plc_manager.plc, 'write_coil'):
                    logger.debug(f"✏️ [PLC WRITE] Writing boolean {target_state} to coil {modbus_address}")
                    success = await plc_manager.plc.write_coil(modbus_address, target_state)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Component {component_name} set to {action} at coil {modbus_address}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write {action} to component {component_name} at coil {modbus_address}")
                else:
                    logger.error(f"❌ [PLC INTERFACE] PLC doesn't support write_coil")
                    success = False
        else:
            raise ValueError(f"Component {component_name} (ID: {component_id}) has no modbus address configured in machine_components table")

        # Update command status based on result
        if success:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ [COMMAND SUCCESS] Component command completed successfully")
            logger.info(f"📊 [PERFORMANCE] Command ID: {command_id} | Component: {component_name} | Action: {action} | Duration: {processing_time_ms}ms")
            await finalize_component_command(command_id, success=True)

            # Update component.is_activated in machine_components table
            supabase.table('machine_components').update({
                'is_activated': target_state
            }).eq('id', component_id).execute()

            logger.info(f"✅ [COMPONENT UPDATE] Component {component_name} is_activated set to {target_state}")
        else:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ [COMMAND FAILED] Component command failed")
            logger.error(f"📊 [PERFORMANCE] Command ID: {command_id} | Component: {component_name} | Action: {action} | Duration: {processing_time_ms}ms")
            await finalize_component_command(command_id, success=False, error_message="PLC write operation failed")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ [COMPONENT ERROR] {error_msg}")

        # Track retry count
        retry_count = state.failed_commands.get(command_id, 0) + 1
        state.failed_commands[command_id] = retry_count

        if retry_count < state.max_retries:
            error_msg_with_retry = f"{error_msg} (retry {retry_count}/{state.max_retries})"

            # Record the error and allow retry after backoff
            supabase.table("component_control_commands").update({
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
            logger.error(f"❌ COMPONENT COMMAND FAILED - ID: {command_id} | Component: {component_name} | Action: {action} | Status: ERROR | Duration: {processing_time_ms}ms")
            await finalize_component_command(command_id, success=False, error_message=f"{error_msg} (after {retry_count} attempts)")


async def finalize_component_command(
    command_id: str,
    success: bool,
    error_message: Optional[str] = None,
):
    """Finalize a component control command by setting completed_at and optional error message."""
    try:
        supabase = get_supabase()
        update_data = {
            "completed_at": datetime.utcnow().isoformat()
        }
        if not success and error_message is not None:
            update_data["error_message"] = error_message

        result = (
            supabase.table("component_control_commands")
            .update(update_data)
            .eq("id", command_id)
            .execute()
        )
        if result.data:
            logger.info(f"Command {command_id} finalized: {'completed' if success else 'failed'}")
        else:
            logger.warning(f"Failed to finalize component command {command_id}")
    except Exception as e:
        logger.error(f"Error finalizing component command: {str(e)}", exc_info=True)


async def handle_component_command_insert(payload):
    """
    Handle an insert event for a component control command.

    Args:
        payload: The event payload from Supabase
    """
    try:
        # Determine if this is from realtime or polling using connection_monitor
        realtime_connected = connection_monitor.realtime_status["connected"]
        source = "realtime" if realtime_connected else "polling"
        logger.info(f"🔔 COMPONENT COMMAND RECEIVED [{source.upper()}] - Processing component control command")

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
                    f"Ignoring component command for different machine: {record['machine_id']}"
                )
                return

        # Process if not yet executed
        command_id = record["id"]
        component_name = record.get("component_name", "?")

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
            await finalize_component_command(command_id, success=False, error_message=f"Exceeded maximum retry attempts ({state.max_retries})")
            state.processed_commands.add(command_id)
            return

        logger.info(f"🟡 COMPONENT COMMAND PROCESSING - ID: {command_id} | Component: {component_name} | Status: CLAIMED")

        # Ensure PLC connection before claiming
        if not await ensure_plc_connection():
            logger.warning(f"Cannot process command {command_id}: PLC is not connected")
            return

        # Claim by setting executed_at if still NULL
        supabase = get_supabase()
        result = (
            supabase.table("component_control_commands")
            .update({
                "executed_at": datetime.utcnow().isoformat(),
                "error_message": None
            })
            .eq("id", command_id)
            .is_("executed_at", None)
            .execute()
        )

        if result.data and len(result.data) > 0:
            logger.info(f"🟢 COMPONENT COMMAND EXECUTING - ID: {command_id} | Status: PROCESSING")
            state.processed_commands.add(command_id)
            await process_component_command(record)
        else:
            logger.info(f"⚠️ COMPONENT COMMAND SKIPPED - ID: {command_id} | Status: ALREADY_CLAIMED")
            state.processed_commands.add(command_id)

    except Exception as e:
        logger.error(f"Error handling component command insert: {str(e)}", exc_info=True)


async def check_pending_component_commands():
    """
    Check for existing pending component control commands and process them.
    This is called after subscribing to the channel to handle any commands
    that were inserted before the subscription was established.
    """
    try:
        logger.info("Checking for existing pending component control commands...")
        supabase = get_supabase()

        # Query for pending component control commands for this machine
        # Exclude commands that have been processed or exceeded retry limit
        result = (
            supabase.table("component_control_commands")
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
                logger.info(f"Found {len(commands_to_process)} pending component control commands to process")

                # Check PLC connection before processing
                if not await ensure_plc_connection():
                    logger.warning("Cannot process component commands: PLC is not connected")
                    # Don't mark as failed yet, will retry on next poll
                    return

                for command in commands_to_process:
                    logger.info(f"Processing existing pending component command: {command['id']}")
                    # Create a payload similar to what would be received from a realtime event
                    payload = {
                        "data": {
                            "record": command
                        }
                    }
                    await handle_component_command_insert(payload)
            else:
                logger.debug("No new pending component control commands to process")
        else:
            logger.debug("No pending component control commands found")

    except Exception as e:
        logger.error(f"Error checking pending component commands: {str(e)}", exc_info=True)


async def poll_for_component_commands():
    """
    Periodically poll for new pending component control commands.
    This serves as a fallback when realtime isn't working and as a safety net.
    """
    # Use connection_monitor for realtime status instead of global variable
    realtime_connected = connection_monitor.realtime_status["connected"]
    # Reduced from 10s to 2s when realtime is working for faster safety check fallback
    poll_interval = 1 if not realtime_connected else 2  # Faster responsiveness

    logger.info(f"Starting component command polling (interval: {poll_interval}s, realtime: {realtime_connected})")

    while state.is_running:
        try:
            # Check current realtime status from connection_monitor
            realtime_connected = connection_monitor.realtime_status["connected"]

            # Poll if realtime is disconnected or as periodic safety check (every minute)
            should_poll = not realtime_connected or (asyncio.get_event_loop().time() % 60 < 1)

            if should_poll:
                await check_pending_component_commands()

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

            # Simplified interval: fast when realtime down, faster safety check when working
            # Reduced from 10s to 2s for better responsiveness
            poll_interval = 1 if not realtime_connected else 2
            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error in component command polling: {str(e)}", exc_info=True)
            await asyncio.sleep(poll_interval)


async def setup_component_control_listener():
    """
    Set up a listener for component control command inserts in the Supabase database.
    Uses realtime channels for instant updates with polling as a fallback.
    """
    logger.info("Setting up component control listener with realtime support...")

    try:
        # Create channel name for component control commands
        channel_name = f"component-control-commands-{MACHINE_ID}"

        # Define callback for INSERT events only
        def on_insert(payload):
            logger.info("🔔 COMPONENT COMMAND RECEIVED [REALTIME] - Processing new component control command")
            logger.debug(f"Payload: {payload}")
            asyncio.create_task(handle_component_command_insert(payload))

        def on_error(payload):
            logger.error(f"Realtime channel error: {payload}")
            connection_monitor.update_realtime_status(False, f"Channel error: {payload}")

        # Direct subscription using async_supabase (only INSERT)
        realtime_channel = state.async_supabase.channel(channel_name)
        logger.info("Setting up realtime subscription for component_control_commands INSERT events only...")
        realtime_channel = realtime_channel.on_postgres_changes(
            event="INSERT",
            schema="public",
            table="component_control_commands",
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
    logger.info("Checking for existing pending component control commands...")
    await check_pending_component_commands()

    # Start polling for commands as a fallback (will be more aggressive if realtime fails)
    poll_task = asyncio.create_task(poll_for_component_commands())
    logger.info("Started component control command polling as fallback mechanism")

    # Log the final status using connection_monitor as single source of truth
    if connection_monitor.realtime_status["connected"]:
        logger.info("✅ Component control listener ready with REALTIME + polling fallback")
    else:
        logger.warning("⚠️ Component control listener ready with POLLING ONLY (realtime failed)")


async def cleanup_handler():
    """Perform cleanup when application is interrupted"""
    logger.info(f"🧹 [CLEANUP START] Beginning component service cleanup...")

    try:
        # Stop the service
        logger.debug(f"⏹️ [SHUTDOWN] Stopping component service...")
        state.is_running = False
        logger.debug(f"✅ [SHUTDOWN] Service stopped successfully")

        # No complex coordination to cleanup - just direct PLC access
        logger.debug(f"📋 [CLEANUP] No complex coordination to cleanup - using direct PLC access")

    except Exception as e:
        logger.exception(f"❌ [CLEANUP ERROR] Error during component service cleanup")
    finally:
        logger.info(f"✅ [SHUTDOWN COMPLETE] Component service shutdown complete")
        sys.exit(0)


async def initialize_component_metadata_cache(service_state: ComponentServiceState) -> None:
    """Initialize component metadata cache for enhanced logging - adapted from Terminal 1."""
    try:
        data_logger.info("Loading component metadata for enhanced logging...")

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

                service_state.component_metadata[param_id] = {
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

            data_logger.info(f"✅ Loaded metadata for {len(service_state.component_metadata)} component parameters")

            # Log a few examples of the metadata for debugging
            for i, (param_id, metadata) in enumerate(service_state.component_metadata.items()):
                if i >= 3:  # Only show first 3
                    break
                data_logger.debug(
                    f"Component parameter {param_id}: {metadata['component_name']}.{metadata['name']} "
                    f"({metadata['data_type']}, {metadata['unit']})"
                )
        else:
            data_logger.warning("No component metadata found in database")

    except Exception as e:
        data_logger.error(f"Failed to load component metadata: {e}", exc_info=True)
        # Continue with empty metadata - service should still work


async def main():
    """
    Main function for Component Service
    Sets up component control listener and runs indefinitely with DIRECT PLC ACCESS
    """
    async def signal_handler(signal, frame):
        """Handle SIGINT signal"""
        logger.info(f"⚠️ [SIGNAL] Received interrupt signal, initiating cleanup...")
        await cleanup_handler()

    try:
        # Ensure single instance before any initialization
        logger.info("Checking for existing component service instances...")
        ensure_single_instance()
        logger.info("✅ Single instance lock acquired successfully")

        logger.info("Starting Component Service (DIRECT PLC ACCESS)")
        logger.info("="*60)
        logger.info("Component Service Configuration:")
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

        # Load component metadata cache
        logger.info("Loading component metadata cache...")
        await initialize_component_metadata_cache(state)
        logger.info("✅ Component metadata cache initialized")

        # Start component control listener
        logger.info("Starting component control listener...")
        state.is_running = True
        await setup_component_control_listener()

        logger.info("Component service running and ready to process commands")
        logger.info("="*60)
        logger.info("System Status:")
        logger.info(
            f"  - Realtime Channels: "
            f"{'✅ Active' if connection_monitor.realtime_status['connected'] else '⚠️ Using Polling'}"
        )
        logger.info(f"  - PLC Connection: {'✅ Connected' if plc_manager.is_connected() else '⚠️ Disconnected'}")
        logger.info(f"  - Machine ID: {MACHINE_ID}")
        logger.info("="*60)
        logger.info("Component service is ready to receive commands")

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
        logger.error(f"Error in component service main loop: {str(e)}", exc_info=True)
        await cleanup_handler()
        raise


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Component Service (Direct PLC Access)")
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