"""
Parameter control listener for receiving and executing parameter control commands from Supabase.
This listens to the parameter_control_commands table for testing UI to machine communication.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Set
from src.log_setup import logger
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
            .eq("status", "pending")
            .eq("machine_id", MACHINE_ID)
            .order("priority", desc=True)  # Higher priority first
            .order("created_at", desc=False)  # Older commands first within same priority
            .execute()
        )
        
        if result.data and len(result.data) > 0:
            # Filter out already processed commands and those that exceeded retry limit
            commands_to_process = [
                cmd for cmd in result.data 
                if cmd['id'] not in processed_commands 
                and failed_commands.get(cmd['id'], 0) < MAX_RETRIES
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
    global realtime_connected
    
    # Adjust polling based on realtime status
    base_interval = 10 if realtime_connected else 3  # More aggressive if realtime is down
    poll_interval = base_interval
    max_poll_interval = 60 if realtime_connected else 30
    
    logger.info(f"Starting parameter command polling (interval: {base_interval}s, realtime: {realtime_connected})")
    
    while True:
        try:
            # Only poll if realtime is disconnected or as periodic safety check
            should_poll = not realtime_connected or (asyncio.get_event_loop().time() % 60 < 1)
            
            if should_poll:
                await check_pending_parameter_commands()
            
            # Clean up old processed commands periodically (keep last 100)
            if len(processed_commands) > 100:
                # Convert to list, sort by time (assuming UUIDs have time component), keep last 50
                processed_list = list(processed_commands)
                processed_commands.clear()
                processed_commands.update(processed_list[-50:])
                logger.debug(f"Cleaned up processed commands cache, kept {len(processed_commands)} entries")
            
            # Clean up old failed commands
            if len(failed_commands) > 50:
                # Remove entries for commands that have exceeded retry limit
                cleaned_count = 0
                failed_commands_copy = failed_commands.copy()
                for cmd_id, retry_count in failed_commands_copy.items():
                    if retry_count >= MAX_RETRIES:
                        del failed_commands[cmd_id]
                        cleaned_count += 1
                if cleaned_count > 0:
                    logger.debug(f"Cleaned up {cleaned_count} failed commands from cache")
            
            # Adjust poll interval based on realtime status
            if realtime_connected:
                poll_interval = base_interval * 2  # Less frequent when realtime is working
            else:
                poll_interval = base_interval  # Normal frequency when realtime is down
            
            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Error in parameter command polling: {str(e)}", exc_info=True)
            # Exponential backoff on errors
            poll_interval = min(poll_interval * 2, max_poll_interval)
            await asyncio.sleep(poll_interval)


# Track channel subscription status
realtime_connected = False
realtime_channel = None


async def monitor_realtime_connection():
    """
    Monitor the realtime channel connection and reconnect if needed.
    """
    global realtime_connected, realtime_channel
    
    while True:
        try:
            if not realtime_connected and realtime_channel:
                logger.warning("Realtime channel disconnected, attempting to reconnect...")
                try:
                    await realtime_channel.subscribe()
                    realtime_connected = True
                    logger.info("Successfully reconnected to realtime channel")
                    connection_monitor.update_realtime_status(True)
                except Exception as e:
                    logger.error(f"Failed to reconnect realtime channel: {str(e)}")
                    realtime_connected = False
                    connection_monitor.update_realtime_status(False, str(e))
            elif realtime_connected:
                # Update monitor that realtime is working
                connection_monitor.update_realtime_status(True)
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in realtime connection monitor: {str(e)}", exc_info=True)
            connection_monitor.update_realtime_status(False, str(e))
            await asyncio.sleep(60)


async def setup_parameter_control_listener(async_supabase):
    """
    Set up a listener for parameter control command inserts in the Supabase database.
    Uses realtime channels for instant updates with polling as a fallback.

    Args:
        async_supabase: An async Supabase client
    """
    global realtime_connected, realtime_channel
    
    logger.info("Setting up parameter control listener with realtime support...")

    try:
        # Create channel for parameter control commands
        channel_name = f"parameter-control-commands-{MACHINE_ID}"
        realtime_channel = async_supabase.channel(channel_name)
        
        # Define callbacks for different events
        def on_insert(payload):
            logger.info(f"Received realtime INSERT event for parameter control")
            logger.debug(f"Payload: {payload}")
            asyncio.create_task(handle_parameter_command_insert(payload))
        
        def on_update(payload):
            # Log updates but don't process them (they're handled by polling)
            logger.debug(f"Received realtime UPDATE event for parameter control: {payload}")
        
        def on_error(payload):
            global realtime_connected
            logger.error(f"Realtime channel error: {payload}")
            realtime_connected = False
        
        # Subscribe to database changes for INSERT and UPDATE events
        logger.info("Setting up realtime subscriptions for parameter_control_commands table...")
        
        # Subscribe to INSERT events
        realtime_channel = realtime_channel.on_postgres_changes(
            event="INSERT", 
            schema="public", 
            table="parameter_control_commands",
            callback=on_insert
        )
        
        # Also subscribe to UPDATE events to track status changes
        realtime_channel = realtime_channel.on_postgres_changes(
            event="UPDATE",
            schema="public",
            table="parameter_control_commands",
            callback=on_update
        )
        
        # Subscribe to the channel
        logger.info("Subscribing to realtime channel...")
        await realtime_channel.subscribe()
        realtime_connected = True
        connection_monitor.update_realtime_status(True)
        logger.info(f"Successfully subscribed to realtime channel: {channel_name}")
        
    except Exception as e:
        logger.error(f"Failed to set up realtime channel: {str(e)}", exc_info=True)
        logger.warning("Realtime subscription failed, will rely on polling mechanism")
        realtime_connected = False
        connection_monitor.update_realtime_status(False, str(e))
    
    # Start realtime connection monitor
    if realtime_channel:
        logger.info("Starting realtime connection monitor")
        asyncio.create_task(monitor_realtime_connection())
    
    # Check for existing pending commands
    logger.info("Checking for existing pending parameter control commands...")
    await check_pending_parameter_commands()
    
    # Start polling for commands as a fallback (will be more aggressive if realtime fails)
    poll_task = asyncio.create_task(poll_for_parameter_commands())
    logger.info("Started parameter control command polling as fallback mechanism")
    
    # Log the final status
    if realtime_connected:
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
        # Determine if this is from realtime or polling
        source = "realtime" if realtime_connected else "polling"
        logger.info(f"Processing parameter control command from {source}")
        
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

        # Only process pending commands
        if record["status"] == "pending":
            command_id = record["id"]
            parameter_name = record["parameter_name"]
            
            # Check if we've already processed this command
            if command_id in processed_commands:
                logger.debug(f"Command {command_id} already processed, skipping")
                return
            
            # Check if this command has exceeded retry limit
            if failed_commands.get(command_id, 0) >= MAX_RETRIES:
                logger.warning(f"Command {command_id} has exceeded max retries ({MAX_RETRIES}), skipping")
                # Mark as permanently failed
                await update_parameter_command_status(
                    command_id, 
                    "failed", 
                    error_message=f"Exceeded maximum retry attempts ({MAX_RETRIES})"
                )
                processed_commands.add(command_id)
                return
            
            logger.info(f"New pending parameter control command: {command_id}, parameter: {parameter_name}")

            # Check PLC connection before attempting to claim
            if not await ensure_plc_connection():
                logger.warning(f"Cannot process command {command_id}: PLC is not connected")
                # Don't mark as failed, will retry later
                return

            # Try to claim the command by updating its status
            supabase = get_supabase()
            result = (
                supabase.table("parameter_control_commands")
                .update({
                    "status": "executing",
                    "executed_at": datetime.utcnow().isoformat()
                })
                .eq("id", command_id)
                .eq("status", "pending")
                .execute()
            )

            # Check if we successfully claimed the command
            if result.data and len(result.data) > 0:
                logger.info(f"Successfully claimed parameter command {command_id}")
                # Mark as being processed
                processed_commands.add(command_id)
                # Process the command
                await process_parameter_command(record)
            else:
                logger.info(f"Parameter command {command_id} already claimed or status changed")
                # Mark as processed to avoid retrying
                processed_commands.add(command_id)

    except Exception as e:
        logger.error(f"Error handling parameter command insert: {str(e)}", exc_info=True)


async def process_parameter_command(command: Dict[str, Any]):
    """
    Process a parameter control command by executing it via pymodbus.
    
    Args:
        command: The command data from the database
    """
    command_id = command['id']
    parameter_name = command['parameter_name']
    parameter_type = command['parameter_type']
    target_value = float(command['target_value'])
    modbus_address = command.get('modbus_address')
    modbus_type = command.get('modbus_type')
    timeout_ms = command.get('timeout_ms', 30000)
    
    logger.info(f"Processing parameter command {command_id}: {parameter_name} = {target_value}")
    
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
            
            # Reset to pending for retry if under limit
            if retry_count < MAX_RETRIES:
                supabase = get_supabase()
                supabase.table("parameter_control_commands").update({
                    "status": "pending",
                    "error_message": error_msg
                }).eq("id", command_id).execute()
                
                # Remove from processed to allow retry
                processed_commands.discard(command_id)
                
                # Wait before allowing retry
                await asyncio.sleep(backoff_delay)
                return
            else:
                raise RuntimeError(f"PLC connection failed after {MAX_RETRIES} attempts")
        
        # Execute the parameter change based on modbus_type
        success = False
        current_value = None
        
        if modbus_type == 'coil':
            # Binary parameter (pump on/off, etc.)
            binary_value = bool(target_value)
            logger.info(f"Writing coil at address {modbus_address}: {binary_value}")
            
            # For coils, we use the PLC's direct modbus interface
            # This is a simplified approach - you may want to extend PLCInterface
            if hasattr(plc_manager.plc, 'write_coil'):
                success = await plc_manager.plc.write_coil(modbus_address, binary_value)
                current_value = float(binary_value) if success else None
            else:
                # Fallback to generic parameter write
                success = await plc_manager.write_parameter(parameter_name, target_value)
                if success:
                    current_value = await plc_manager.read_parameter(parameter_name)
                    
        elif modbus_type == 'holding_register':
            # Numeric parameter (flow rates, temperatures, etc.)
            logger.info(f"Writing holding register at address {modbus_address}: {target_value}")
            
            if hasattr(plc_manager.plc, 'write_holding_register'):
                success = await plc_manager.plc.write_holding_register(modbus_address, target_value)
                if success and hasattr(plc_manager.plc, 'read_holding_register'):
                    current_value = await plc_manager.plc.read_holding_register(modbus_address)
            else:
                # Fallback to generic parameter write
                success = await plc_manager.write_parameter(parameter_name, target_value)
                if success:
                    current_value = await plc_manager.read_parameter(parameter_name)
                    
        else:
            # Generic parameter write using the existing PLC interface
            logger.info(f"Writing parameter {parameter_name}: {target_value}")
            success = await plc_manager.write_parameter(parameter_name, target_value)
            if success:
                current_value = await plc_manager.read_parameter(parameter_name)
        
        # Update command status based on result
        if success:
            logger.info(f"Parameter command {command_id} executed successfully")
            # Clear from failed commands if it was there
            failed_commands.pop(command_id, None)
            await update_parameter_command_status(
                command_id, 
                "completed", 
                current_value=current_value
            )
        else:
            # Track retry count
            retry_count = failed_commands.get(command_id, 0) + 1
            failed_commands[command_id] = retry_count
            
            if retry_count < MAX_RETRIES:
                error_msg = f"Failed to write parameter to PLC (retry {retry_count}/{MAX_RETRIES})"
                logger.warning(f"Parameter command {command_id}: {error_msg}")
                
                # Reset to pending for retry
                supabase = get_supabase()
                supabase.table("parameter_control_commands").update({
                    "status": "pending",
                    "error_message": error_msg
                }).eq("id", command_id).execute()
                
                # Remove from processed to allow retry
                processed_commands.discard(command_id)
            else:
                logger.error(f"Parameter command {command_id} failed after {MAX_RETRIES} attempts")
                await update_parameter_command_status(
                    command_id, 
                    "failed", 
                    error_message=f"Failed to write parameter to PLC after {MAX_RETRIES} attempts"
                )
            
    except Exception as e:
        error_msg = f"Error executing parameter command: {str(e)}"
        logger.error(f"Parameter command {command_id} failed: {error_msg}", exc_info=True)
        
        # Track retry count for other errors too
        retry_count = failed_commands.get(command_id, 0) + 1
        failed_commands[command_id] = retry_count
        
        if retry_count < MAX_RETRIES and "PLC" in str(e):
            # For PLC-related errors, allow retry
            error_msg_with_retry = f"{error_msg} (retry {retry_count}/{MAX_RETRIES})"
            
            # Reset to pending for retry
            supabase = get_supabase()
            supabase.table("parameter_control_commands").update({
                "status": "pending",
                "error_message": error_msg_with_retry
            }).eq("id", command_id).execute()
            
            # Remove from processed to allow retry
            processed_commands.discard(command_id)
            
            # Wait with exponential backoff
            backoff_delay = RETRY_DELAY_BASE * (2 ** (retry_count - 1))
            await asyncio.sleep(backoff_delay)
        else:
            # Non-PLC errors or exceeded retries
            await update_parameter_command_status(
                command_id, 
                "failed", 
                error_message=f"{error_msg} (after {retry_count} attempts)"
            )


async def update_parameter_command_status(
    command_id: str, 
    status: str, 
    current_value: Optional[float] = None,
    error_message: Optional[str] = None
):
    """
    Update the status of a parameter control command.
    
    Args:
        command_id: The ID of the command to update
        status: The new status ('executing', 'completed', 'failed')
        current_value: The current value after execution (if successful)
        error_message: Error message if failed
    """
    try:
        supabase = get_supabase()
        
        update_data = {
            "status": status,
            "completed_at": datetime.utcnow().isoformat() if status in ['completed', 'failed'] else None
        }
        
        if current_value is not None:
            update_data["current_value"] = current_value
            
        if error_message is not None:
            update_data["error_message"] = error_message
        
        result = (
            supabase.table("parameter_control_commands")
            .update(update_data)
            .eq("id", command_id)
            .execute()
        )
        
        if result.data:
            logger.info(f"Updated parameter command {command_id} status to {status}")
        else:
            logger.warning(f"Failed to update parameter command {command_id} status")
            
    except Exception as e:
        logger.error(f"Error updating parameter command status: {str(e)}", exc_info=True)


# Test function to create sample parameter commands
async def create_test_parameter_commands():
    """
    Create some test parameter control commands for testing.
    This is a helper function for development/testing purposes.
    """
    try:
        supabase = get_supabase()
        
        test_commands = [
            {
                "parameter_name": "pump_1",
                "parameter_type": "binary", 
                "target_value": 1,
                "modbus_address": 100,
                "modbus_type": "coil",
                "machine_id": MACHINE_ID,
                "priority": 1
            },
            {
                "parameter_name": "nitrogen_generator",
                "parameter_type": "binary",
                "target_value": 1,
                "modbus_address": 102, 
                "modbus_type": "coil",
                "machine_id": MACHINE_ID,
                "priority": 1
            },
            {
                "parameter_name": "mfc_1_flow_rate",
                "parameter_type": "flow_rate",
                "target_value": 200.0,
                "modbus_address": 200,
                "modbus_type": "holding_register", 
                "machine_id": MACHINE_ID,
                "priority": 0
            }
        ]
        
        result = (
            supabase.table("parameter_control_commands")
            .insert(test_commands)
            .execute()
        )
        
        if result.data:
            logger.info(f"Created {len(result.data)} test parameter commands")
        else:
            logger.warning("Failed to create test parameter commands")
            
    except Exception as e:
        logger.error(f"Error creating test parameter commands: {str(e)}", exc_info=True)