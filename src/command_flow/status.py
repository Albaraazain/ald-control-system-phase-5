"""
Status management for commands.
"""
from typing import Optional
from log_setup import logger
from db import get_supabase, get_current_timestamp

async def update_command_status(command_id: int, status: str, error_message: Optional[str] = None):
    """
    Update the status of a command in the database.
    
    Args:
        command_id: The ID of the command to update
        status: The new status (pending, processing, completed, error)
        error_message: Optional error message for failed commands
        
    Returns:
        The updated command data or empty dict if update failed
    """
    supabase = get_supabase()
    
    # Prepare update data
    update_data = {
        'status': status,
        'updated_at': get_current_timestamp()
    }
    
    # Add execution timestamp for completed commands
    if status == 'completed':
        update_data['executed_at'] = get_current_timestamp()
    
    # Add error message for failed commands
    if status == 'error' and error_message:
        update_data['error_message'] = error_message
    
    logger.info(f"Updating command {command_id} status to {status}")
    
    # Update the command in the database
    result = supabase.table('recipe_commands').update(update_data).eq('id', command_id).execute()
    
    # Check if update was successful
    if not result.data or len(result.data) == 0:
        logger.warning(f"Failed to update command {command_id} or command not found")
        return {}
    
    return result.data[0]