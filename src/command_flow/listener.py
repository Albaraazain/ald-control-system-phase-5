"""
Command listener for receiving and dispatching commands from Supabase.
Includes realtime subscription with timeout and polling fallback.
"""

import asyncio
from src.log_setup import get_command_flow_logger

logger = get_command_flow_logger()
from src.config import MACHINE_ID, CommandStatus
from src.db import get_supabase
from src.command_flow.processor import process_command
from src.connection_monitor import connection_monitor


realtime_connected = False


async def check_pending_commands():
    """
    Check for existing pending commands and process them.
    This is called after subscribing to the channel to handle any commands
    that were inserted before the subscription was established.
    """
    try:
        logger.info("Checking for existing pending commands...")
        supabase = get_supabase()
        
        # Query for pending commands for this machine
        result = (
            supabase.table("recipe_commands")
            .select("*")
            .eq("status", CommandStatus.PENDING)
            .execute()
        )
        
        if result.data and len(result.data) > 0:
            # Include commands for this machine OR global commands (machine_id is NULL)
            pending_for_this_machine = [
                c for c in result.data if c.get('machine_id') in (None, MACHINE_ID)
            ]
            logger.info(f"Found {len(pending_for_this_machine)} pending commands for this machine")
            for command in pending_for_this_machine:
                logger.info(f"Processing existing pending command: {command['id']}")
                # Create a payload similar to what would be received from a realtime event
                payload = {
                    "data": {
                        "record": command
                    }
                }
                await handle_command_insert(payload)
        else:
            logger.info("No pending commands found")
            
    except Exception as e:
        logger.error(f"Error checking pending commands: {str(e)}", exc_info=True)


async def poll_for_commands():
    """
    Periodically poll for new pending commands.
    This is a fallback mechanism in case the realtime subscription isn't working.
    """
    while True:
        try:
            await check_pending_commands()
            # Poll every 5 seconds
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in command polling: {str(e)}", exc_info=True)
            # Wait a bit before retrying
            await asyncio.sleep(10)


async def setup_command_listener(async_supabase):
    """
    Set up a listener for command inserts in the Supabase database.

    Args:
        async_supabase: An async Supabase client
    """
    global realtime_connected
    logger.info("Setting up command listener with realtime support...")

    # Define channel name
    channel_name = "recipe-commands"

    # Define the callback for insert events
    def on_insert(payload):
        logger.info("🔔 RECIPE COMMAND RECEIVED [REALTIME] - Processing new recipe command")
        logger.debug(f"Payload: {payload}")
        asyncio.create_task(handle_command_insert(payload))

    # Direct subscription
    channel = async_supabase.channel(channel_name)
    logger.info("Subscribing to INSERT events on recipe_commands table...")
    channel = channel.on_postgres_changes(
        event="INSERT", schema="public", table="recipe_commands", callback=on_insert
    )

    logger.info("Subscribing to recipe_commands realtime channel...")
    async def _subscribe_with_timeout():
        global realtime_connected
        try:
            await asyncio.wait_for(channel.subscribe(), timeout=10.0)
            realtime_connected = True
            connection_monitor.update_realtime_status(True)
            logger.info("Successfully subscribed to recipe_commands realtime channel")
        except asyncio.TimeoutError:
            logger.warning("Recipe command realtime subscription timed out after 10 seconds; using polling fallback")
            realtime_connected = False
            connection_monitor.update_realtime_status(False, "recipe subscribe timeout")
        except Exception as e:
            logger.error(f"Failed to subscribe to recipe_commands realtime channel: {str(e)}", exc_info=True)
            realtime_connected = False
            connection_monitor.update_realtime_status(False, str(e))

    await _subscribe_with_timeout()
    
    # Check for existing pending commands
    await check_pending_commands()
    logger.info("Checked for existing pending commands")

    # Start polling for commands as a fallback
    base_msg = "REALTIME + polling fallback" if realtime_connected else "POLLING ONLY (realtime failed)"
    logger.info(f"Starting recipe command polling; listener ready with {base_msg}")
    asyncio.create_task(poll_for_commands())


async def handle_command_insert(payload):
    """
    Handle an insert event for a recipe command.

    Args:
        payload: The event payload from Supabase
    """
    try:
        logger.info("🔔 RECIPE COMMAND RECEIVED - Processing recipe command")
        # Extract the command record from the payload
        record = payload["data"]["record"]

        # Only process commands for this machine or global commands
        if "machine_id" in record and record["machine_id"] is not None:
            if record["machine_id"] != MACHINE_ID:
                logger.info(
                    f"Ignoring command for different machine: {record['machine_id']}"
                )
                return

        # Only process pending commands
        if record["status"] == CommandStatus.PENDING:
            command_id = record["id"]
            command_type = record["type"]
            logger.info(f"🟡 RECIPE COMMAND PROCESSING - ID: {command_id} | Type: {command_type} | Status: CLAIMING")

            # Try to claim the command by updating its status
            supabase = get_supabase()
            result = (
                supabase.table("recipe_commands")
                .update({"status": CommandStatus.PROCESSING})
                .eq("id", command_id)
                .eq("status", CommandStatus.PENDING)
                .execute()
            )

            # Check if we successfully claimed the command
            if result.data and len(result.data) > 0:
                logger.info(f"🟢 RECIPE COMMAND EXECUTING - ID: {command_id} | Type: {command_type} | Status: PROCESSING")
                # Process the command
                await process_command(record)
            else:
                logger.info(f"⚠️ RECIPE COMMAND SKIPPED - ID: {command_id} | Type: {command_type} | Status: ALREADY_CLAIMED")

    except Exception as e:
        logger.error(f"Error handling command insert: {str(e)}", exc_info=True)
