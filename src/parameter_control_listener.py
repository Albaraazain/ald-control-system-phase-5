"""
Parameter control listener for receiving and executing parameter control commands from Supabase.
This listens to the parameter_control_commands table for testing UI to machine communication.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from src.log_setup import logger
from src.config import MACHINE_ID
from src.db import get_supabase
from src.plc.manager import plc_manager


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
            logger.info(f"Found {len(result.data)} pending parameter control commands")
            for command in result.data:
                logger.info(f"Processing existing pending parameter command: {command['id']}")
                # Create a payload similar to what would be received from a realtime event
                payload = {
                    "data": {
                        "record": command
                    }
                }
                await handle_parameter_command_insert(payload)
        else:
            logger.info("No pending parameter control commands found")
            
    except Exception as e:
        logger.error(f"Error checking pending parameter commands: {str(e)}", exc_info=True)


async def poll_for_parameter_commands():
    """
    Periodically poll for new pending parameter control commands.
    This is a fallback mechanism in case the realtime subscription isn't working.
    """
    while True:
        try:
            await check_pending_parameter_commands()
            # Poll every 3 seconds for quicker parameter response
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Error in parameter command polling: {str(e)}", exc_info=True)
            # Wait a bit before retrying
            await asyncio.sleep(5)


async def setup_parameter_control_listener(async_supabase):
    """
    Set up a listener for parameter control command inserts in the Supabase database.

    Args:
        async_supabase: An async Supabase client
    """
    logger.info("Setting up parameter control listener...")

    # Create channel for parameter control commands
    channel = async_supabase.channel("parameter-control-commands")

    # Define the callback for insert events
    def on_insert(payload):
        logger.info(f"Received parameter control insert event: {payload}")
        asyncio.create_task(handle_parameter_command_insert(payload))

    # Subscribe to database changes
    logger.info("Subscribing to INSERT events on parameter_control_commands table...")
    channel = channel.on_postgres_changes(
        event="INSERT", schema="public", table="parameter_control_commands", callback=on_insert
    )

    # Subscribe to the channel
    await channel.subscribe()
    logger.info("Successfully subscribed to parameter_control_commands table")
    
    # Check for existing pending commands
    await check_pending_parameter_commands()
    logger.info("Checked for existing pending parameter control commands")
    
    # Start polling for commands as a fallback
    logger.info("Starting parameter control command polling as a fallback mechanism")
    asyncio.create_task(poll_for_parameter_commands())


async def handle_parameter_command_insert(payload):
    """
    Handle an insert event for a parameter control command.

    Args:
        payload: The event payload from Supabase
    """
    try:
        logger.info(f"Received parameter control command payload")
        # Extract the command record from the payload
        record = payload["data"]["record"]

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
            logger.info(f"New pending parameter control command: {command_id}, parameter: {parameter_name}")

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
                # Process the command
                await process_parameter_command(record)
            else:
                logger.info(f"Parameter command {command_id} already claimed or status changed")

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
        # Check if PLC is connected
        if not plc_manager.is_connected():
            raise RuntimeError("PLC is not connected")
        
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
            await update_parameter_command_status(
                command_id, 
                "completed", 
                current_value=current_value
            )
        else:
            logger.error(f"Parameter command {command_id} failed to execute")
            await update_parameter_command_status(
                command_id, 
                "failed", 
                error_message="Failed to write parameter to PLC"
            )
            
    except Exception as e:
        error_msg = f"Error executing parameter command: {str(e)}"
        logger.error(f"Parameter command {command_id} failed: {error_msg}", exc_info=True)
        await update_parameter_command_status(
            command_id, 
            "failed", 
            error_message=error_msg
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