"""
Command processor for handling different types of commands.
"""
from log_setup import logger
from config import CommandStatus
from command_flow.status import update_command_status
from recipe_flow.starter import start_recipe
from recipe_flow.stopper import stop_recipe
from step_flow.parameter_step import set_parameter
from command_flow.state import state

async def process_command(command):
    """
    Process a command based on its type and route to the appropriate handler.
    
    Args:
        command: The command data from the database
    """
    command_id = command['id']
    command_type = command['type']
    parameters = command['parameters'] if command['parameters'] else {}
    
    logger.info(f"Processing command {command_id} of type {command_type}")
    
    try:
        # Set the current command ID globally
        state.current_command_id = command_id
        # Route command to appropriate handler based on type
        if command_type == 'start_recipe':
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
        await update_command_status(command_id, CommandStatus.COMPLETED)
        # Clear the current command ID after successful completion
        state.current_command_id = None
        
    except Exception as e:
        logger.error(f"Error processing command {command_id}: {str(e)}", exc_info=True)
        await update_command_status(command_id, CommandStatus.ERROR, str(e))
        # Clear the current command ID on error
        state.current_command_id = None
