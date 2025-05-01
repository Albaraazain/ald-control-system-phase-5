"""
Command listener for receiving and dispatching commands from Supabase.
"""

import asyncio
from log_setup import logger
from config import MACHINE_ID, CommandStatus
from db import get_supabase
from command_flow.processor import process_command


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
        asyncio.create_task(handle_command_insert(payload))

    # Subscribe to database changes
    channel = channel.on_postgres_changes(
        event="INSERT", schema="public", table="recipe_commands", callback=on_insert
    )

    # Subscribe to the channel
    await channel.subscribe()
    logger.info("Successfully subscribed to recipe_commands table")


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
