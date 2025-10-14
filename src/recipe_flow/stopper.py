"""
Handles stopping recipe execution.
"""
from src.log_setup import logger
from src.config import MACHINE_ID
from src.db import get_supabase, get_current_timestamp
from src.recipe_flow.continuous_data_recorder import continuous_recorder
from src.recipe_flow.cancellation import cancel as cancel_process

# Valid process status values from database enum
PROCESS_STATUSES = ('preparing', 'running', 'paused', 'completed', 'failed', 'aborted')

async def stop_recipe(command_id: int, parameters: dict):
    """
    Handle a command to stop a running recipe.
    
    Args:
        command_id: The ID of the command being processed
        parameters: Command parameters (may include process_id)
    """
    logger.info(f"Handling stop recipe command {command_id}")
    supabase = get_supabase()
    
    # 1. Get the current machine status
    machine_result = supabase.table('machines').select('*').eq('id', MACHINE_ID).execute()
    
    if not machine_result.data or len(machine_result.data) == 0:
        raise ValueError(f"Machine with ID {MACHINE_ID} not found")
    
    machine = machine_result.data[0]
    
    # Check if machine is processing a recipe
    if machine['status'] != 'processing' or not machine['current_process_id']:
        logger.warning(f"No active process to stop on machine {MACHINE_ID}")
        return
    
    process_id = machine['current_process_id']
    
    # Signal cancellation to running executor and stop continuous data recording
    cancel_process(process_id)
    await continuous_recorder.stop()
    
    # 2. Update the process execution record
    # Use an allowed terminal status to reflect a user-initiated stop.
    # 'aborted' is part of the allowed PROCESS_STATUSES and matches our DB enum.
    await update_process_status(process_id, 'aborted')
    
    # 3. Update machine status to idle
    await update_machine_status(process_id)
    
    # 4. Update machine state to idle
    await update_machine_state(process_id)
    
    logger.info(f"Recipe execution process {process_id} stopped successfully")

async def update_process_status(process_id: str, status: str):
    """
    Update process execution status in the database.
    Valid statuses: preparing, running, paused, completed, failed, aborted
    """
    if status not in PROCESS_STATUSES:
        raise ValueError(f"Invalid process status: {status}. Must be one of {PROCESS_STATUSES}")
    """Update process execution status in the database."""
    supabase = get_supabase()
    now = get_current_timestamp()
    
    update_data = {
        'status': status,
        'end_time': now,
        'updated_at': now
    }
    
    result = supabase.table('process_executions').update(update_data).eq('id', process_id).execute()
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Failed to update process {process_id} status")
        return None
    
    logger.info(f"Updated process {process_id} status to {status}")
    return result.data[0]

async def update_machine_status(process_id: str):
    """
    Update machine status to idle when a process stops.
    Note: machines_base doesn't have 'status' column - status is tracked in machine_state table.
    This function only updates current_process_id.
    """
    supabase = get_supabase()
    
    update_data = {
        'current_process_id': None,
        'updated_at': get_current_timestamp()
    }
    
    result = supabase.table('machines_base').update(update_data).eq('id', MACHINE_ID).execute()
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Failed to update machine status")
        return None
    
    logger.info(f"Updated machines_base current_process_id to None (status tracked in machine_state)")
    return result.data[0]

async def update_machine_state(process_id: str):
    """Update machine state to idle when a process stops."""
    supabase = get_supabase()
    now = get_current_timestamp()
    
    update_data = {
        'current_state': 'idle',
        'state_since': now,
        'process_id': None,
        'is_failure_mode': False,
        'updated_at': now
    }
    
    result = supabase.table('machine_state').update(update_data).eq('machine_id', MACHINE_ID).execute()
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Failed to update machine state")
        return None
    
    logger.info(f"Updated machine state to idle")
    return result.data[0]
