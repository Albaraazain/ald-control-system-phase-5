"""
Executes loop steps in a recipe.
"""
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.recipe_flow.data_recorder import record_process_data

async def execute_loop_step(process_id: str, step: dict, all_steps: list, parent_to_child_steps: dict):
    """
    Execute a loop step and all its child steps for the specified number of iterations.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
        all_steps: List of all steps in the recipe
        parent_to_child_steps: Dictionary mapping parent step IDs to their child steps
    """
    supabase = get_supabase()
    step_id = step['id']
    
    # Load loop configuration from loop_step_config table
    result = supabase.table('loop_step_config').select('*').eq('step_id', step_id).execute()
    loop_config = result.data[0] if result.data else None
    
    if not loop_config:
        # Fallback to old method for backwards compatibility
        parameters = step.get('parameters', {})
        
        # Validate parameters
        if 'count' not in parameters:
            raise ValueError(f"Loop step is missing required parameter: count")
        
        loop_count = int(parameters['count'])
    else:
        # Use new loop_step_config table
        loop_count = loop_config['iteration_count']
    
    # Get child steps for this loop
    child_steps = parent_to_child_steps.get(step_id, [])
    if not child_steps:
        logger.warning(f"Loop step {step_id} has no child steps to execute")
        return
        
    # Calculate total steps that will be executed in this loop
    steps_per_iteration = len(child_steps)
    total_loop_steps = steps_per_iteration * loop_count
    
    # Get current progress from process_execution_state
    state_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).single().execute()
    current_progress = state_result.data['progress'] if state_result.data else {'total_steps': 0, 'completed_steps': 0, 'total_cycles': 0, 'completed_cycles': 0}
    
    # Update total steps to include all iterations
    updated_progress = {
        'total_steps': current_progress['total_steps'] + total_loop_steps,
        'completed_steps': current_progress['completed_steps'],
        'total_cycles': current_progress['total_cycles'] + loop_count,
        'completed_cycles': current_progress['completed_cycles']
    }
    
    # Update process_execution_state with new totals
    supabase.table('process_execution_state').update({
        'progress': updated_progress,
        'last_updated': 'now()'
    }).eq('execution_id', process_id).execute()
    
    # Execute child steps for the specified number of iterations
    for iteration in range(loop_count):
        logger.info(f"Executing loop iteration {iteration + 1}/{loop_count}")
        
        # Update only basic fields in process_executions
        supabase.table('process_executions').update({
            'updated_at': get_current_timestamp()
        }).eq('id', process_id).execute()
        
        # Update process_execution_state for loop iteration
        state_update = {
            'current_step_type': 'loop',
            'current_step_name': step['name'],
            'current_loop_iteration': iteration + 1,
            'current_loop_count': loop_count,
            'last_updated': 'now()'
        }
        supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
        
        # Execute each child step in sequence
        for child_step in child_steps:
            logger.info(f"Executing child step {child_step['name']} (Type: {child_step['type']})")
            
            # Touch process record updated_at for activity
            supabase.table('process_executions').update({
                'updated_at': get_current_timestamp()
            }).eq('id', process_id).execute()
            
            # Update process_execution_state for child step
            child_state_update = {
                'current_step_type': child_step['type'],
                'current_step_name': child_step['name'],
                'last_updated': 'now()'
            }
            
            # Add specific fields based on child step type
            if child_step['type'].lower() == 'valve':
                valve_params = child_step.get('parameters', {})
                child_state_update['current_valve_number'] = valve_params.get('valve_number')
                child_state_update['current_valve_duration_ms'] = valve_params.get('duration_ms')
            elif child_step['type'].lower() == 'purge':
                purge_params = child_step.get('parameters', {})
                child_state_update['current_purge_duration_ms'] = purge_params.get('duration_ms')
            
            supabase.table('process_execution_state').update(child_state_update).eq('execution_id', process_id).execute()
            
            # Execute the step based on its type
            step_type = child_step['type'].lower()
            
            if step_type == 'purge':
                from src.step_flow.purge_step import execute_purge_step
                purge_step = {
                    'type': 'purging',
                    'name': child_step['name'],
                    'parameters': child_step['parameters']
                }
                await execute_purge_step(process_id, purge_step)
                
            elif step_type == 'valve':
                from src.step_flow.valve_step import execute_valve_step
                valve_params = child_step['parameters']
                if 'valve_number' not in valve_params:
                    raise ValueError(f"Valve step missing valve_number parameter: {child_step['name']}")
                    
                valve_number = valve_params['valve_number']
                valve_step = {
                    'type': f'open valve {valve_number}',
                    'name': child_step['name'],
                    'parameters': valve_params
                }
                await execute_valve_step(process_id, valve_step)
                
            elif step_type == 'set parameter':
                from src.step_flow.parameter_step import execute_parameter_step
                await execute_parameter_step(process_id, child_step)
            
            # Record data points after each step execution
            await record_process_data(process_id)
            
            # Update completed steps count in process_execution_state
            current_progress['completed_steps'] += 1
            supabase.table('process_execution_state').update({
                'progress': current_progress,
                'last_updated': 'now()'
            }).eq('execution_id', process_id).execute()
            
            # Also update process_execution_state progress
            state_progress_update = {
                'progress': {
                    'total_steps': current_progress.get('total_steps', 0),
                    'completed_steps': current_progress['completed_steps']
                },
                'last_updated': 'now()'
            }
            supabase.table('process_execution_state').update(state_progress_update).eq('execution_id', process_id).execute()
            
        # Update completed cycles count in process_execution_state
        current_progress['completed_cycles'] += 1
        supabase.table('process_execution_state').update({
            'progress': current_progress,
            'last_updated': 'now()'
        }).eq('execution_id', process_id).execute()
            
    logger.info(f"Loop step completed after {loop_count} iterations")
