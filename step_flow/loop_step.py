"""
Executes loop steps in a recipe.
"""
from log_setup import logger
from db import get_supabase, get_current_timestamp
from recipe_flow.data_recorder import record_process_data

async def execute_loop_step(process_id: str, step: dict, all_steps: list, parent_to_child_steps: dict):
    """
    Execute a loop step and all its child steps for the specified number of iterations.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
        all_steps: List of all steps in the recipe
        parent_to_child_steps: Dictionary mapping parent step IDs to their child steps
    """
    parameters = step.get('parameters', {})
    supabase = get_supabase()
    
    # Validate parameters
    if 'count' not in parameters:
        raise ValueError(f"Loop step is missing required parameter: count")
    
    loop_count = int(parameters['count'])
    step_id = step['id']
    
    # Get child steps for this loop
    child_steps = parent_to_child_steps.get(step_id, [])
    if not child_steps:
        logger.warning(f"Loop step {step_id} has no child steps to execute")
        return
        
    # Calculate total steps that will be executed in this loop
    steps_per_iteration = len(child_steps)
    total_loop_steps = steps_per_iteration * loop_count
    
    # Get current progress
    process_result = supabase.table('process_executions').select('progress').eq('id', process_id).single().execute()
    current_progress = process_result.data['progress']
    
    # Update total steps to include all iterations
    updated_progress = {
        'total_steps': current_progress['total_steps'] + total_loop_steps,
        'completed_steps': current_progress['completed_steps'],
        'total_cycles': current_progress['total_cycles'] + loop_count,
        'completed_cycles': current_progress['completed_cycles']
    }
    
    # Update process_executions with new totals
    supabase.table('process_executions').update({
        'progress': updated_progress
    }).eq('id', process_id).execute()
    
    # Execute child steps for the specified number of iterations
    for iteration in range(loop_count):
        logger.info(f"Executing loop iteration {iteration + 1}/{loop_count}")
        
        # Update process execution with loop details
        supabase.table('process_executions').update({
            'current_step_type': 'loop',
            'current_step_name': step['name'],
            'current_loop_count': loop_count,
            'current_loop_iteration': iteration + 1,
            'updated_at': get_current_timestamp(),
            'progress': current_progress
        }).eq('id', process_id).execute()
        
        # Execute each child step in sequence
        for child_step in child_steps:
            logger.info(f"Executing child step {child_step['name']} (Type: {child_step['type']})")
            
            # Update process with current step
            supabase.table('process_executions').update({
                'current_step': child_step,
                'updated_at': get_current_timestamp()
            }).eq('id', process_id).execute()
            
            # Execute the step based on its type
            step_type = child_step['type'].lower()
            
            if step_type == 'purge':
                from step_flow.purge_step import execute_purge_step
                purge_step = {
                    'type': 'purging',
                    'name': child_step['name'],
                    'parameters': child_step['parameters']
                }
                await execute_purge_step(process_id, purge_step)
                
            elif step_type == 'valve':
                from step_flow.valve_step import execute_valve_step
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
                from step_flow.parameter_step import execute_parameter_step
                await execute_parameter_step(process_id, child_step)
            
            # Record data points after each step execution
            await record_process_data(process_id)
            
            # Update completed steps count
            current_progress['completed_steps'] += 1
            supabase.table('process_executions').update({
                'progress': current_progress
            }).eq('id', process_id).execute()
            
        # Update completed cycles count
        current_progress['completed_cycles'] += 1
        supabase.table('process_executions').update({
            'progress': current_progress
        }).eq('id', process_id).execute()
            
    logger.info(f"Loop step completed after {loop_count} iterations")
