"""
Command processor for handling different types of commands.
"""
from src.log_setup import get_command_flow_logger

logger = get_command_flow_logger()
from src.config import CommandStatus, MACHINE_ID
from src.db import get_supabase
from src.command_flow.status import update_command_status
from src.recipe_flow.starter import start_recipe
from src.recipe_flow.stopper import stop_recipe
from src.step_flow.parameter_step import set_parameter
from src.command_flow.state import state

async def validate_machine_available_for_recipe():
    """
    Validate that machine is available for starting a new recipe.
    Checks both status and current_process_id to prevent race conditions.

    Raises:
        ValueError: If machine is not available for recipe execution
    """
    supabase = get_supabase()

    # Get current machine status - same pattern as starter.py:45-49
    machine_result = supabase.table('machines').select('*').eq('id', MACHINE_ID).execute()
    if not machine_result.data or len(machine_result.data) == 0:
        raise ValueError(f"Machine with ID {MACHINE_ID} not found")

    machine = machine_result.data[0]

    # Check if machine status is available - same pattern as starter.py:52-53
    if machine['status'] not in ['idle', 'offline']:
        raise ValueError(f"Machine is currently {machine['status']} and cannot start a new recipe")

    # RACE CONDITION FIX: Also check current_process_id to prevent concurrent starts
    if machine['current_process_id'] is not None:
        raise ValueError(f"Machine already has an active process (ID: {machine['current_process_id']}) and cannot start a new recipe")

async def process_command(command):
    """
    Process a command based on its type and route to the appropriate handler.

    Args:
        command: The command data from the database
    """
    import time
    start_time = time.time()

    command_id = command['id']
    command_type = command['type']
    parameters = command['parameters'] if command['parameters'] else {}

    logger.info(f"🔧 RECIPE COMMAND EXECUTION - ID: {command_id} | Type: {command_type} | Status: EXECUTING")
    
    try:
        # Set the current command ID globally
        state.current_command_id = command_id
        # Route command to appropriate handler based on type
        if command_type == 'start_recipe':
            # RACE CONDITION FIX: Validate machine availability before starting recipe
            await validate_machine_available_for_recipe()
            await start_recipe(command_id, parameters)
        elif command_type == 'stop_recipe':
            await stop_recipe(command_id, parameters)
        elif command_type == 'set_parameter':
            await set_parameter(command_id, parameters)
        else:
            logger.warning(f"Unknown command type: {command_type}")
            await update_command_status(
                command_id, 
                CommandStatus.ERROR, 
                f"Unknown command type: {command_type}"
            )
            return
        
        # If we get here, command was successful
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"✅ RECIPE COMMAND COMPLETED - ID: {command_id} | Type: {command_type} | Status: SUCCESS | Duration: {processing_time_ms}ms")
        await update_command_status(command_id, CommandStatus.COMPLETED)
        # Clear the current command ID after successful completion
        state.current_command_id = None

    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"❌ RECIPE COMMAND FAILED - ID: {command_id} | Type: {command_type} | Status: ERROR | Duration: {processing_time_ms}ms | Error: {str(e)}", exc_info=True)
        await update_command_status(command_id, CommandStatus.ERROR, str(e))
        # Clear the current command ID on error
        state.current_command_id = None
