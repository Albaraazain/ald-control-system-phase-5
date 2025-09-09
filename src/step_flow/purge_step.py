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
    supabase = get_supabase()
    step_id = step.get('id')
    
    # Load purge configuration from purge_step_config table
    result = supabase.table('purge_step_config').select('*').eq('step_id', step_id).execute()
    purge_config = result.data[0] if result.data else None
    
    if not purge_config:
        # Fallback to old method for backwards compatibility
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
        
        # Set default values for new fields
        gas_type = parameters.get('gas_type', 'N2')
        flow_rate = parameters.get('flow_rate', 0.0)
    else:
        # Use new purge_step_config table
        duration_ms = purge_config['duration_ms']
        gas_type = purge_config['gas_type']
        flow_rate = purge_config['flow_rate']
    
    logger.info(f"Executing purging step for {duration_ms}ms with {gas_type} gas at {flow_rate} flow rate")
    
    # Get current progress from process_execution_state
    state_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).single().execute()
    current_progress = state_result.data['progress'] if state_result.data else {}
    
    # Update only basic fields in process_executions
    supabase.table('process_executions').update({
        'updated_at': get_current_timestamp()
    }).eq('id', process_id).execute()
    
    # Update process_execution_state
    state_update = {
        'current_step_type': 'purge',
        'current_step_name': step['name'],
        'current_purge_duration_ms': duration_ms,
        'progress': current_progress,
        'last_updated': 'now()'
    }
    supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
    
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