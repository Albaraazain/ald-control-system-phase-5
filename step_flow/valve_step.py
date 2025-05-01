"""
Executes valve steps in a recipe.
"""
import asyncio
from log_setup import logger
from db import get_supabase, get_current_timestamp
from plc.manager import plc_manager

async def execute_valve_step(process_id: str, step: dict):
    """
    Execute a valve operation step, opening a specific valve for a duration.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
    """
    parameters = step.get('parameters', {})
    step_type = step['type']
    
    # If valve number not in type, try to get it from parameters
    valve_number = None
    if 'open valve' in step_type.lower():
        # Extract valve number from step type (e.g., "open valve 1" -> 1)
        try:
            valve_number = int(step_type.split('valve')[1].strip())
        except (IndexError, ValueError):
            pass
    
    # If not found in type, check parameters
    if valve_number is None and 'valve_number' in parameters:
        valve_number = parameters['valve_number']
    
    if valve_number is None:
        raise ValueError(f"Unable to determine valve number from step: {step}")
    
    # Validate parameters
    if 'duration_ms' not in parameters:
        raise ValueError(f"Valve step is missing required parameter: duration_ms")
    
    duration_ms = int(parameters['duration_ms'])
    
    logger.info(f"Opening valve {valve_number} for {duration_ms}ms")
    
    # Update process execution with valve details and increment step count
    supabase = get_supabase()
    
    # Get current progress
    process_result = supabase.table('process_executions').select('current_step_type, current_step_name, progress').eq('id', process_id).single().execute()
    current_progress = process_result.data['progress']
    
    # Update step details and progress
    supabase.table('process_executions').update({
        'current_step_type': 'valve',
        'current_step_name': step['name'],
        'current_valve_number': valve_number,
        'current_valve_duration_ms': duration_ms,
        'updated_at': get_current_timestamp(),
        'progress': current_progress  # Include current progress to maintain counts
    }).eq('id', process_id).execute()
    
    # Control the valve via PLC
    plc = plc_manager.plc
    if plc:
        success = await plc.control_valve(valve_number, True, duration_ms)
        if not success:
            raise RuntimeError(f"Failed to control valve {valve_number}")
    else:
        # Fallback to simulation behavior if no PLC
        await asyncio.sleep(duration_ms / 1000)
    
    logger.info(f"Valve {valve_number} operation completed successfully")