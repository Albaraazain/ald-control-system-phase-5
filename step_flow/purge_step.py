"""
Executes purge steps in a recipe.
"""
import asyncio
from log_setup import logger
from db import get_supabase, get_current_timestamp
from plc.manager import plc_manager

async def execute_purge_step(process_id: str, step: dict):
    """
    Execute a purging step, which runs for a specified duration.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
    """
    parameters = step.get('parameters', {})
    
    # Check for both possible parameter names
    duration_ms = None
    if 'duration_ms' in parameters:
        duration_ms = int(parameters['duration_ms'])
    elif 'duration' in parameters:
        duration_ms = int(parameters['duration'])
    
    # Validate parameters
    if duration_ms is None:
        raise ValueError("Purging step is missing required parameter: duration_ms or duration")
    
    logger.info(f"Executing purging step for {duration_ms}ms")
    
    # Update process execution with purge details and progress
    supabase = get_supabase()
    
    # Get current progress
    process_result = supabase.table('process_executions').select('current_step_type, current_step_name, progress').eq('id', process_id).single().execute()
    current_progress = process_result.data['progress']
    
    # Update step details and progress
    supabase.table('process_executions').update({
        'current_step_type': 'purge',
        'current_step_name': step['name'],
        'current_purge_duration_ms': duration_ms,
        'updated_at': get_current_timestamp(),
        'progress': current_progress  # Include current progress to maintain counts
    }).eq('id', process_id).execute()
    
    # Execute the purge via PLC
    plc = plc_manager.plc
    if plc:
        success = await plc.execute_purge(duration_ms)
        if not success:
            raise RuntimeError(f"Failed to execute purge operation")
    else:
        # Fallback to simulation behavior if no PLC
        await asyncio.sleep(duration_ms / 1000)
    
    logger.info(f"Purging step completed successfully")