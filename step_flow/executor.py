"""
Executes recipe steps based on their type.
"""
from log_setup import logger
from db import get_supabase
from step_flow.loop_step import execute_loop_step
from step_flow.purge_step import execute_purge_step
from step_flow.valve_step import execute_valve_step
from step_flow.parameter_step import execute_parameter_step

async def execute_step(process_id: str, step: dict, all_steps: list, parent_to_child_steps: dict):
    """
    Execute a recipe step based on its type.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data to execute
        all_steps: List of all steps in the recipe
        parent_to_child_steps: Dictionary mapping parent step IDs to their child steps
    """
    step_type = step['type'].lower()
    step_name = step['name']
    
    logger.info(f"Executing step '{step_name}' of type '{step_type}'")
    
    try:
        # Get current progress for non-loop steps
        if step_type != 'loop':
            supabase = get_supabase()
            process_result = supabase.table('process_executions').select('progress').eq('id', process_id).single().execute()
            current_progress = process_result.data['progress']
        
        # Route to appropriate step handler based on step type
        if step_type == 'loop':
            await execute_loop_step(process_id, step, all_steps, parent_to_child_steps)
            
        elif step_type == 'purge':
            step_data = {
                'type': 'purging',
                'name': step_name,
                'parameters': step['parameters']
            }
            await execute_purge_step(process_id, step_data)
            
        elif step_type == 'valve':
            valve_params = step['parameters']
            if 'valve_number' not in valve_params:
                raise ValueError(f"Valve step missing valve_number parameter: {step_name}")
                
            valve_number = valve_params['valve_number']
            valve_step = {
                'type': f'open valve {valve_number}',
                'name': step_name,
                'parameters': valve_params
            }
            await execute_valve_step(process_id, valve_step)
            
        elif step_type == 'set parameter':
            await execute_parameter_step(process_id, step)
            
        else:
            logger.warning(f"Unknown step type: {step_type}")
            raise ValueError(f"Unknown step type: {step_type}")
        
        logger.info(f"Step '{step_name}' executed successfully")
        
        # Update completed steps for non-loop steps (loop steps handle their own counts)
        if step_type != 'loop':
            current_progress['completed_steps'] += 1
            supabase = get_supabase()
            supabase.table('process_executions').update({
                'progress': current_progress
            }).eq('id', process_id).execute()
        
    except Exception as e:
        logger.error(f"Error executing step '{step_name}': {str(e)}", exc_info=True)
        raise
