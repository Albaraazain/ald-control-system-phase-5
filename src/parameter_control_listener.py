"""
Parameter control listener for receiving and executing parameter control commands from Supabase.
Listens to the parameter_control_commands table to validate the end-to-end control path.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Set
from src.log_setup import get_plc_logger

logger = get_plc_logger()  # Parameter control is PLC-related
from src.config import MACHINE_ID
from src.db import get_supabase
from src.plc.manager import plc_manager
from src.connection_monitor import connection_monitor


# Track commands that have been processed to avoid duplicates
processed_commands: Set[str] = set()
failed_commands: Dict[str, int] = {}  # Track retry count for failed commands
MAX_RETRIES = 3
RETRY_DELAY_BASE = 5  # Base delay in seconds for exponential backoff


async def ensure_plc_connection() -> bool:
    """
    Ensure PLC is connected, attempt to reconnect if not.
    Uses the connection monitor's status for consistency.
    
    Returns:
        bool: True if connected or reconnected successfully, False otherwise
    """
    # First check with connection monitor's status
    if connection_monitor.plc_status["connected"]:
        return True
    
    # If monitor says disconnected but manager says connected, verify
    if plc_manager.is_connected():
        logger.info("PLC manager reports connected, updating monitor status")
        connection_monitor.plc_status["connected"] = True
        return True
    
    logger.warning("PLC is not connected. Waiting for connection monitor to reconnect...")
    
    # Wait a bit for the connection monitor to do its job
    max_wait = 30  # seconds
    wait_interval = 2  # seconds
    total_waited = 0
    
    while total_waited < max_wait:
        await asyncio.sleep(wait_interval)
        total_waited += wait_interval
        
        if connection_monitor.plc_status["connected"] or plc_manager.is_connected():
            logger.info("PLC connection restored")
            return True
    
    logger.error(f"PLC connection not restored after {max_wait} seconds")
    return False


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
                    and (cmd['id'] not in processed_commands)
                    and (failed_commands.get(cmd['id'], 0) < MAX_RETRIES)
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

    while True:
        try:
            # Check current realtime status from connection_monitor
            realtime_connected = connection_monitor.realtime_status["connected"]

            # Poll if realtime is disconnected or as periodic safety check (every minute)
            should_poll = not realtime_connected or (asyncio.get_event_loop().time() % 60 < 1)

            if should_poll:
                await check_pending_parameter_commands()

            # Clean up old processed commands periodically (keep last 100)
            if len(processed_commands) > 100:
                processed_list = list(processed_commands)
                processed_commands.clear()
                processed_commands.update(processed_list[-50:])
                logger.debug(f"Cleaned up processed commands cache, kept {len(processed_commands)} entries")

            # Clean up old failed commands
            if len(failed_commands) > 50:
                cleaned_count = 0
                failed_commands_copy = failed_commands.copy()
                for cmd_id, retry_count in failed_commands_copy.items():
                    if retry_count >= MAX_RETRIES:
                        del failed_commands[cmd_id]
                        cleaned_count += 1
                if cleaned_count > 0:
                    logger.debug(f"Cleaned up {cleaned_count} failed commands from cache")

            # Simplified interval: fast when realtime down, slower when working
            poll_interval = 1 if not realtime_connected else 10
            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error in parameter command polling: {str(e)}", exc_info=True)
            await asyncio.sleep(poll_interval)


# Track channel reference for cleanup (no longer tracking connection status here)
realtime_channel = None


async def setup_parameter_control_listener(async_supabase, realtime_service=None):
    """
    Set up a listener for parameter control command inserts in the Supabase database.
    Uses realtime channels for instant updates with polling as a fallback.

    Args:
        async_supabase: An async Supabase client
    """
    global realtime_channel

    logger.info("Setting up parameter control listener with realtime support...")

    try:
        # Create channel name for parameter control commands
        channel_name = f"parameter-control-commands-{MACHINE_ID}"

        # Define callback for INSERT events only (removed unused UPDATE subscription)
        def on_insert(payload):
            logger.info("🔔 PARAMETER COMMAND RECEIVED [REALTIME] - Processing new parameter control command")
            logger.debug(f"Payload: {payload}")
            asyncio.create_task(handle_parameter_command_insert(payload))

        def on_error(payload):
            logger.error(f"Realtime channel error: {payload}")
            connection_monitor.update_realtime_status(False, f"Channel error: {payload}")

        if realtime_service is not None:
            # Use centralized realtime service (only INSERT, no UPDATE)
            logger.info("Registering parameter_control_commands subscription via RealtimeService...")
            await realtime_service.subscribe_postgres(
                name=channel_name,
                table="parameter_control_commands",
                on_insert=on_insert,
            )
            # Update connection_monitor based on realtime service status
            connection_monitor.update_realtime_status(realtime_service.is_connected())
        else:
            # Fallback to direct subscription using async_supabase (only INSERT)
            realtime_channel = async_supabase.channel(channel_name)
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
        if command_id in processed_commands:
            logger.debug(f"Command {command_id} already processed, skipping")
            return

        # Skip if already claimed/executed
        if record.get("executed_at") is not None:
            logger.debug(f"Command {command_id} already executed, skipping")
            processed_commands.add(command_id)
            return

        # Retry budget check
        if failed_commands.get(command_id, 0) >= MAX_RETRIES:
            logger.warning(f"Command {command_id} exceeded max retries ({MAX_RETRIES}), marking failed")
            await finalize_parameter_command(command_id, success=False, error_message=f"Exceeded maximum retry attempts ({MAX_RETRIES})")
            processed_commands.add(command_id)
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
            processed_commands.add(command_id)
            await process_parameter_command(record)
        else:
            logger.info(f"⚠️ PARAMETER COMMAND SKIPPED - ID: {command_id} | Status: ALREADY_CLAIMED")
            processed_commands.add(command_id)

    except Exception as e:
        logger.error(f"Error handling parameter command insert: {str(e)}", exc_info=True)


async def process_parameter_command(command: Dict[str, Any]):
    """
    Process a parameter control command by executing it via pymodbus.

    Args:
        command: The command data from the database
    """
    import time
    start_time = time.time()

    command_id = command['id']
    parameter_name = command['parameter_name']
    target_value = float(command['target_value'])
    timeout_ms = command.get('timeout_ms', 30000)

    logger.info(f"🔧 PARAMETER COMMAND EXECUTION - ID: {command_id} | Parameter: {parameter_name} | Target: {target_value}")

    supabase = get_supabase()
    
    try:
        # Ensure PLC is connected, attempt reconnection if needed
        if not await ensure_plc_connection():
            # Track retry count
            retry_count = failed_commands.get(command_id, 0) + 1
            failed_commands[command_id] = retry_count
            
            # Calculate backoff delay
            backoff_delay = RETRY_DELAY_BASE * (2 ** (retry_count - 1))
            
            error_msg = f"PLC is not connected (retry {retry_count}/{MAX_RETRIES})"
            logger.warning(f"{error_msg}. Will retry in {backoff_delay} seconds")
            
            # Record the error but keep as uncompleted for retry
            if retry_count < MAX_RETRIES:
                supabase = get_supabase()
                supabase.table("parameter_control_commands").update({
                    "error_message": error_msg
                }).eq("id", command_id).execute()
                
                # Remove from processed to allow retry
                processed_commands.discard(command_id)
                
                # Wait before allowing retry
                await asyncio.sleep(backoff_delay)
                return
            else:
                raise RuntimeError(f"PLC connection failed after {MAX_RETRIES} attempts")
        
        # Check for command-level modbus address override first
        command_write_addr = command.get('write_modbus_address') or command.get('modbus_address')

        success = False
        current_value = None
        parameter_id = None
        data_type = None

        if command_write_addr is not None:
            # Use command override address - skip parameter table lookup for address
            logger.info(f"Using override modbus address {command_write_addr} from command {command_id}")
            data_type = command.get('data_type', 'float')  # Default to float if not specified

            # Write directly using override address
            # Handle both RealPLC (with communicator) and SimulationPLC (direct methods)
            if hasattr(plc_manager.plc, 'communicator'):
                # RealPLC with communicator
                if hasattr(plc_manager.plc.communicator, 'write_coil') and data_type == 'binary':
                    success = plc_manager.plc.communicator.write_coil(command_write_addr, bool(target_value))
                    logger.info(f"Wrote binary value {bool(target_value)} to coil {command_write_addr}")
                elif (hasattr(plc_manager.plc.communicator, 'write_float') and callable(getattr(plc_manager.plc.communicator, 'write_float'))) or (hasattr(plc_manager.plc.communicator, 'write_integer_32bit') and callable(getattr(plc_manager.plc.communicator, 'write_integer_32bit'))):
                    # Use write_float for float values, write_integer_32bit for integer values
                    if hasattr(plc_manager.plc.communicator, 'write_integer_32bit') and callable(getattr(plc_manager.plc.communicator, 'write_integer_32bit')) and (isinstance(target_value, int) or target_value.is_integer()):
                        success = plc_manager.plc.communicator.write_integer_32bit(command_write_addr, int(float(target_value)))
                    elif hasattr(plc_manager.plc.communicator, 'write_float') and callable(getattr(plc_manager.plc.communicator, 'write_float')):
                        success = plc_manager.plc.communicator.write_float(command_write_addr, float(target_value))
                    else:
                        logger.warning(f"No suitable write method available on communicator")
                        success = False
                    if success:
                        logger.info(f"Wrote value {float(target_value)} to holding register {command_write_addr}")
                else:
                    logger.warning(f"PLC communicator doesn't support direct address writing")
                    success = False
            else:
                # SimulationPLC with direct methods
                if hasattr(plc_manager.plc, 'write_coil') and data_type == 'binary':
                    success = await plc_manager.plc.write_coil(command_write_addr, bool(target_value))
                    logger.info(f"Wrote binary value {bool(target_value)} to coil {command_write_addr}")
                elif hasattr(plc_manager.plc, 'write_holding_register'):
                    success = await plc_manager.plc.write_holding_register(command_write_addr, float(target_value))
                    logger.info(f"Wrote value {float(target_value)} to holding register {command_write_addr}")
                else:
                    logger.warning(f"PLC doesn't support direct address writing")
                    success = False
            
            # Read-after-write verification for override address writes
            if success:
                try:
                    # Read back from the SAME address we wrote to (setpoint address)
                    read_back_value = None
                    if hasattr(plc_manager.plc, 'communicator'):
                        # RealPLC with communicator - use read_float/read_integer_32bit
                        if data_type == 'binary' and hasattr(plc_manager.plc.communicator, 'read_coils'):
                            coils = plc_manager.plc.communicator.read_coils(command_write_addr, 1)
                            read_back_value = float(coils[0]) if coils else 0.0
                        elif hasattr(plc_manager.plc.communicator, 'read_float'):
                            # Try float first for most parameters
                            read_back_value = plc_manager.plc.communicator.read_float(command_write_addr)
                    else:
                        # SimulationPLC with direct methods
                        if data_type == 'binary' and hasattr(plc_manager.plc, 'read_coil'):
                            read_back_value = float(await plc_manager.plc.read_coil(command_write_addr))
                        elif hasattr(plc_manager.plc, 'read_holding_register'):
                            read_back_value = await plc_manager.plc.read_holding_register(command_write_addr)
                    
                    if read_back_value is not None:
                        # Verify with tolerance
                        tolerance = 0.01
                        abs_diff = abs(read_back_value - target_value)
                        rel_diff = abs_diff / max(abs(target_value), 0.001)
                        
                        if abs_diff > tolerance and rel_diff > tolerance:
                            logger.warning(
                                f"⚠️ [SETPOINT WRITE VERIFICATION FAILED] Address {command_write_addr}: "
                                f"Wrote {target_value}, Read back {read_back_value}, "
                                f"Diff: {abs_diff:.4f} ({rel_diff*100:.2f}%)"
                            )
                        else:
                            logger.info(
                                f"✅ [SETPOINT WRITE VERIFIED] Address {command_write_addr}: "
                                f"Wrote {target_value}, Read back {read_back_value} - SETPOINT CONFIRMED"
                            )
                            logger.info(
                                f"ℹ️  NOTE: This is the SETPOINT (write addr {command_write_addr}). "
                                f"The CURRENT/FEEDBACK value may be different and updated by hardware."
                            )
                except Exception as verify_err:
                    logger.debug(f"Could not verify setpoint write for address {command_write_addr}: {verify_err}")
        else:
            # No override address - use parameter lookup with component_parameter_id preference
            param_row = None
            component_parameter_id = command.get('component_parameter_id')

            try:
                if component_parameter_id:
                    # Primary: Direct lookup by component_parameter_id (preferred method)
                    logger.info(f"Using component_parameter_id {component_parameter_id} for direct parameter lookup")
                    q_id = (
                        supabase.table('component_parameters_full')
                        .select('*')
                        .eq('id', component_parameter_id)
                        .execute()
                    )
                    rows = q_id.data or []
                    if rows:
                        param_row = rows[0]
                        logger.info(f"Found parameter by ID: {param_row.get('name', parameter_name)}")
                    else:
                        logger.warning(f"component_parameter_id {component_parameter_id} not found, falling back to parameter_name lookup")

                # Fallback: parameter_name lookup (for backward compatibility)
                if not param_row:
                    logger.info(f"Using parameter_name '{parameter_name}' for fallback lookup")
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
                            logger.warning(f"Multiple parameters found for name '{parameter_name}', using {param_row['id']}. Consider using component_parameter_id for precise targeting.")

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

            # Prefer high-level write via PLC manager
            logger.info(
                f"Writing parameter id={parameter_id} name={parameter_name} value={target_value}"
            )
            success = await plc_manager.write_parameter(parameter_id, target_value)
            if success:
                # Confirmation read with tolerance check
                try:
                    # Read with skip_noise=True for confirmation - need exact value for tolerance check
                    # SIMULATION NOTE: Without skip_noise, simulation adds ±0.5-1.0 noise, causing
                    # confirmation read to fail tolerance check (noise is 500-1000x larger than tolerance)
                    current_value = await plc_manager.read_parameter(parameter_id, skip_noise=True)
                    
                    # Verify the write was successful with tolerance check
                    tolerance = 0.01  # Allow 1% difference or 0.01 absolute for small values
                    abs_diff = abs(current_value - target_value)
                    rel_diff = abs_diff / max(abs(target_value), 0.001)  # Avoid div by zero
                    
                    if abs_diff > tolerance and rel_diff > tolerance:
                        logger.warning(
                            f"⚠️ [WRITE VERIFICATION FAILED] Parameter '{parameter_name}' "
                            f"(ID: {parameter_id}): "
                            f"Wrote {target_value}, Read back {current_value}, "
                            f"Diff: {abs_diff:.4f} ({rel_diff*100:.2f}%)"
                        )
                    else:
                        logger.info(
                            f"✅ [WRITE VERIFIED] Parameter '{parameter_name}' "
                            f"(ID: {parameter_id}): "
                            f"Wrote {target_value}, Read back {current_value}, "
                            f"Diff: {abs_diff:.4f} ({rel_diff*100:.2f}%) - WITHIN TOLERANCE"
                        )
                except Exception as read_err:
                    logger.warning(
                        f"⚠️ [READ-AFTER-WRITE FAILED] Could not verify write for "
                        f"'{parameter_name}': {read_err}"
                    )
            else:
                # Fallback by address when write fails and helpers exist
                addr = param_row.get('write_modbus_address')
                if addr is not None:
                    logger.info(f"Using parameter table modbus address {addr} for {parameter_name}")
                    if hasattr(plc_manager.plc.communicator, 'write_coil') and data_type == 'binary':
                        success = plc_manager.plc.communicator.write_coil(addr, bool(target_value))
                    elif hasattr(plc_manager.plc.communicator, 'write_float') or hasattr(plc_manager.plc.communicator, 'write_integer_32bit'):
                        # Use write_float for float values, write_integer_32bit for integer values
                        if isinstance(target_value, int) or target_value.is_integer():
                            success = plc_manager.plc.communicator.write_integer_32bit(addr, int(float(target_value)))
                        else:
                            success = plc_manager.plc.communicator.write_float(addr, float(target_value))
                else:
                    logger.error(f"No modbus address available for parameter {parameter_name} (ID: {parameter_id})")
        
        # Update command status based on result
        if success:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ PARAMETER COMMAND COMPLETED - ID: {command_id} | Parameter: {parameter_name} | Status: SUCCESS | Duration: {processing_time_ms}ms")
            failed_commands.pop(command_id, None)
            await finalize_parameter_command(command_id, success=True)
        else:
            # Track retry count
            retry_count = failed_commands.get(command_id, 0) + 1
            failed_commands[command_id] = retry_count
            
            if retry_count < MAX_RETRIES:
                error_msg = f"Failed to write parameter to PLC (retry {retry_count}/{MAX_RETRIES})"
                logger.warning(f"Parameter command {command_id}: {error_msg}")
                
                # Record the error for visibility and allow retry
                supabase = get_supabase()
                supabase.table("parameter_control_commands").update({
                    "error_message": error_msg
                }).eq("id", command_id).execute()
                
                # Remove from processed to allow retry
                processed_commands.discard(command_id)
            else:
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.error(f"❌ PARAMETER COMMAND FAILED - ID: {command_id} | Parameter: {parameter_name} | Status: MAX_RETRIES_EXCEEDED | Duration: {processing_time_ms}ms")
                await finalize_parameter_command(command_id, success=False, error_message=f"Failed to write parameter to PLC after {MAX_RETRIES} attempts")
            
    except Exception as e:
        error_msg = f"Error executing parameter command: {str(e)}"
        logger.error(f"Parameter command {command_id} failed: {error_msg}", exc_info=True)
        
        # Track retry count for other errors too
        retry_count = failed_commands.get(command_id, 0) + 1
        failed_commands[command_id] = retry_count
        
        if retry_count < MAX_RETRIES and "PLC" in str(e):
            # For PLC-related errors, allow retry
            error_msg_with_retry = f"{error_msg} (retry {retry_count}/{MAX_RETRIES})"
            
            # Record the error and allow retry after backoff
            supabase = get_supabase()
            supabase.table("parameter_control_commands").update({
                "error_message": error_msg_with_retry
            }).eq("id", command_id).execute()
            
            # Remove from processed to allow retry
            processed_commands.discard(command_id)
            
            # Wait with exponential backoff
            backoff_delay = RETRY_DELAY_BASE * (2 ** (retry_count - 1))
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


# Test function to create sample parameter commands
async def create_test_parameter_commands():
    """
    Create some test parameter control commands for testing.
    This is a helper function for development/testing purposes.
    Now supports both component_parameter_id (preferred) and parameter_name (fallback).
    """
    try:
        supabase = get_supabase()

        # Try to create commands with component_parameter_id when possible
        logger.info("Creating test parameter commands with component_parameter_id when available...")

        # Get some actual parameters from the database
        params_result = supabase.table('component_parameters').select('id, name, parameter_name').limit(3).execute()

        test_commands = []

        if params_result.data:
            # Create commands using component_parameter_id (preferred method)
            for param in params_result.data:
                test_commands.append({
                    "parameter_name": param.get('parameter_name') or param['name'],
                    "component_parameter_id": param['id'],  # Direct parameter ID
                    "target_value": 1.0,
                    "machine_id": MACHINE_ID
                })
            logger.info(f"Created {len(test_commands)} commands with component_parameter_id")
        else:
            # Fallback to parameter_name only (legacy method)
            logger.warning("No parameters found in database, using legacy parameter_name method")
            test_commands = [
                {
                    "parameter_name": "pump_1",
                    "target_value": 1,
                    "machine_id": MACHINE_ID
                },
                {
                    "parameter_name": "nitrogen_generator",
                    "target_value": 1,
                    "machine_id": MACHINE_ID
                },
                {
                    "parameter_name": "mfc_1_flow_rate",
                    "target_value": 200.0,
                    "machine_id": MACHINE_ID
                }
            ]

        result = (
            supabase.table("parameter_control_commands")
            .insert(test_commands)
            .execute()
        )

        if result.data:
            logger.info(f"Successfully created {len(result.data)} test parameter commands")
            for cmd in result.data:
                param_id = cmd.get('component_parameter_id', 'N/A')
                param_name = cmd['parameter_name']
                logger.info(f"  Command {cmd['id']}: {param_name} (ID: {param_id})")
        else:
            logger.warning("Failed to create test parameter commands")

    except Exception as e:
        logger.error(f"Error creating test parameter commands: {str(e)}", exc_info=True)
