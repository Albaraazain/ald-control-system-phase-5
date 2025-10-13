"""
Executes valve steps in a recipe.
"""
import asyncio
import os
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.plc.manager import plc_manager
from src.recipe_flow.cancellation import is_cancelled


async def _audit_log_valve_command(valve_number: int, process_id: str = None):
    """
    Background task to audit log valve commands to parameter_control_commands table.
    Runs asynchronously and does NOT block recipe execution.

    Args:
        valve_number: The valve number that was controlled
        process_id: The process execution ID (optional, for logging only - not stored in audit table)
    """
    try:
        supabase = get_supabase()
        machine_id = os.environ.get('MACHINE_ID', 'unknown')

        # Create audit record showing valve was already executed
        # Note: parameter_control_commands table does not have process_id column
        audit_record = {
            'machine_id': machine_id,
            'parameter_name': f'Valve_{valve_number}',
            'target_value': 1.0,  # Valve opened
            'executed_at': get_current_timestamp(),
            'completed_at': get_current_timestamp(),
        }

        # Insert audit record (non-blocking background operation)
        supabase.table('parameter_control_commands').insert(audit_record).execute()

        logger.debug(f"Audit logged valve {valve_number} command for process {process_id}")
    except Exception as e:
        # Log error but DO NOT propagate - recipe must continue even if audit fails
        logger.error(f"Failed to audit log valve {valve_number} command: {e}", exc_info=True)


async def execute_valve_step(process_id: str, step: dict):
    """
    Execute a valve operation step, opening a specific valve for a duration.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
    """
    supabase = get_supabase()
    step_id = step.get('id')
    
    # Load valve configuration from valve_step_config table
    result = supabase.table('valve_step_config').select('*').eq('step_id', step_id).execute()
    valve_config = result.data[0] if result.data else None
    
    if not valve_config:
        # Fallback to old method for backwards compatibility
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
    else:
        # Use new valve_step_config table
        valve_number = valve_config['valve_number']
        duration_ms = valve_config['duration_ms']
    
    logger.info(f"Opening valve {valve_number} for {duration_ms}ms")
    
    # Early cancel check
    if is_cancelled(process_id):
        logger.info("Valve step cancelled before execution")
        return

    # Get current progress from process_execution_state
    state_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).single().execute()
    current_progress = state_result.data['progress'] if state_result.data else {}
    
    # Update only basic fields in process_executions
    supabase.table('process_executions').update({
        'updated_at': get_current_timestamp()
    }).eq('id', process_id).execute()
    
    # Update process_execution_state
    state_update = {
        'current_step_type': 'valve',
        'current_step_name': step['name'],
        'current_valve_number': valve_number,
        'current_valve_duration_ms': duration_ms,
        'progress': current_progress,
        'last_updated': 'now()'
    }
    supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
    
    # Control the valve via PLC
    plc = plc_manager.plc
    if plc:
        success = await plc.control_valve(valve_number, True, duration_ms)
        if not success:
            raise RuntimeError(f"Failed to control valve {valve_number}")

        # Audit log the valve command in background (non-blocking)
        asyncio.create_task(_audit_log_valve_command(valve_number, process_id))
    else:
        # Fallback to simulation behavior if no PLC
        await asyncio.sleep(duration_ms / 1000)

    logger.info(f"Valve {valve_number} operation completed successfully")
