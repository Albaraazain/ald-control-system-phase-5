"""
Executes recipe steps based on their type.
"""
from src.log_setup import get_step_flow_logger

logger = get_step_flow_logger()
from src.db import get_supabase
from src.step_flow.loop_step import execute_loop_step
from src.step_flow.purge_step import execute_purge_step
from src.step_flow.valve_step import execute_valve_step
from src.step_flow.parameter_step import execute_parameter_step

async def execute_step(process_id: str, step: dict, all_steps: list, parent_to_child_steps: dict, overall_step_count: int = 0):
    """
    Execute a recipe step based on its type.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data to execute
        all_steps: List of all steps in the recipe
        parent_to_child_steps: Dictionary mapping parent step IDs to their child steps
        overall_step_count: Current overall step count for progress tracking
    """
    step_type = step['type'].lower()
    step_name = step['name']
    
    logger.info(f"Executing step '{step_name}' of type '{step_type}'")
    
    try:
        # Get current progress for non-loop steps from process_execution_state
        if step_type != 'loop':
            supabase = get_supabase()
            state_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).single().execute()
            current_progress = state_result.data['progress'] if state_result.data else {'total_steps': 0, 'completed_steps': 0}
        
        # Route to appropriate step handler based on step type
        if step_type == 'loop':
            await execute_loop_step(process_id, step, all_steps, parent_to_child_steps)
            
        elif step_type == 'purge':
            # Some deployments store purge configuration in a separate table;
            # tolerate missing inline parameters.
            step_data = {
                'id': step.get('id'),
                'type': 'purging',
                'name': step_name,
                'parameters': step.get('parameters', {})
            }
            await execute_purge_step(process_id, step_data)
            
        elif step_type == 'valve':
            # Let execute_valve_step handle loading configuration from valve_step_config table
            # This supports both new normalized schema (valve_step_config) and old parameters
            valve_step = {
                'id': step.get('id'),
                'type': 'valve',  # execute_valve_step will determine valve_number from config
                'name': step_name,
                'parameters': step.get('parameters', {})
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
            
            # Update process_execution_state progress only
            state_update = {
                'progress': current_progress,
                'last_updated': 'now()'
            }
            supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
        
    except Exception as e:
        logger.error(f"Error executing step '{step_name}': {str(e)}", exc_info=True)
        raise
