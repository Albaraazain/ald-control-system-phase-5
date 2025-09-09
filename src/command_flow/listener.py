"""
Command listener for receiving and dispatching commands from Supabase.
"""

import asyncio
from src.log_setup import logger
from src.config import MACHINE_ID, CommandStatus
from src.db import get_supabase
from src.command_flow.processor import process_command


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
            .eq("machine_id", MACHINE_ID)
            .execute()
        )
        
        if result.data and len(result.data) > 0:
            logger.info(f"Found {len(result.data)} pending commands")
            for command in result.data:
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
    logger.info("Setting up command listener...")

    # Create channel for recipe commands
    channel = async_supabase.channel("recipe-commands")

    # Define the callback for insert events
    def on_insert(payload):
        logger.info(f"Received insert event: {payload}")
        asyncio.create_task(handle_command_insert(payload))

    # Subscribe to database changes
    logger.info("Subscribing to INSERT events on recipe_commands table...")
    channel = channel.on_postgres_changes(
        event="INSERT", schema="public", table="recipe_commands", callback=on_insert
    )

    # Subscribe to the channel
    await channel.subscribe()
    logger.info("Successfully subscribed to recipe_commands table")
    
    # Check for existing pending commands
    await check_pending_commands()
    logger.info("Checked for existing pending commands")
    
    # Start polling for commands as a fallback
    logger.info("Starting command polling as a fallback mechanism")
    asyncio.create_task(poll_for_commands())


async def handle_command_insert(payload):
    """
    Handle an insert event for a recipe command.

    Args:
        payload: The event payload from Supabase
    """
    try:
        logger.info(f"Received command payload")
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
            logger.info(f"New pending command: {command_id}, type: {record['type']}")

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
                logger.info(f"Successfully claimed command {command_id}")
                # Process the command
                await process_command(record)
            else:
                logger.info(f"Command {command_id} already claimed or status changed")

    except Exception as e:
        logger.error(f"Error handling command insert: {str(e)}", exc_info=True)
