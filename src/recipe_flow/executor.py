"""
Executes a recipe by processing its steps in sequence.
"""
import asyncio
from src.log_setup import logger
from src.config import MACHINE_ID
from src.db import get_supabase, get_current_timestamp
from src.recipe_flow.data_recorder import record_process_data
from src.step_flow.executor import execute_step
from src.recipe_flow.continuous_data_recorder import continuous_recorder

async def execute_recipe(process_id: str):
    """
    Execute all steps of a recipe process.
    
    Args:
        process_id: The ID of the process execution record
    """
    logger.info(f"Starting execution of recipe process: {process_id}")
    supabase = get_supabase()
    
    try:
        # 1. Get process execution record
        process_result = supabase.table('process_executions').select('*').eq('id', process_id).execute()
        if not process_result.data or len(process_result.data) == 0:
            raise ValueError(f"Process execution {process_id} not found")
        
        process = process_result.data[0]
        recipe_version = process['recipe_version']
        all_steps = recipe_version['steps']
        
        # Calculate total steps including loop iterations
        total_steps = 0
        total_cycles = 0
        for step in all_steps:
            if step['type'].lower() == 'loop':
                loop_count = int(step['parameters']['count'])
                child_steps = [s for s in all_steps if s.get('parent_step_id') == step['id']]
                total_steps += len(child_steps) * loop_count
                total_cycles += loop_count
            elif not step.get('parent_step_id'):  # Only count non-child steps
                total_steps += 1
                
        # Initialize progress in process_execution_state
        state_progress_update = {
            'progress': {
                'total_steps': total_steps,
                'completed_steps': 0,
                'total_cycles': total_cycles,
                'completed_cycles': 0
            },
            'last_updated': 'now()'
        }
        supabase.table('process_execution_state').update(state_progress_update).eq('execution_id', process_id).execute()
        
        # 2. Build parent-child step map
        parent_to_child_steps = await build_parent_child_step_map(all_steps)
        
        # 3. Get top-level steps (those without parent_step_id)
        top_level_steps = [step for step in all_steps if not step.get('parent_step_id')]
        top_level_steps.sort(key=lambda x: x['sequence_number'])
        
        # 4. Execute top-level steps sequentially
        overall_step_count = 0
        for step_index, step in enumerate(top_level_steps):
            logger.info(f"Executing top-level step: {step['name']} (Type: {step['type']})")
            
            # Touch process record updated_at for activity
            supabase.table('process_executions').update({
                'updated_at': get_current_timestamp()
            }).eq('id', process_id).execute()
            
            # Get current progress from process_execution_state
            progress_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).execute()
            current_progress = progress_result.data[0]['progress'] if progress_result.data else {'total_steps': total_steps, 'completed_steps': 0}
            
            # Update process execution state for current step
            state_update = {
                'current_step_index': step_index,
                'current_step_type': step['type'],
                'current_step_name': step.get('name', ''),
                'current_overall_step': overall_step_count,
                'progress': current_progress,
                'last_updated': 'now()'
            }
            
            # Add step-specific fields based on type
            if step['type'].lower() == 'valve':
                valve_params = step.get('parameters', {})
                state_update['current_valve_number'] = valve_params.get('valve_number')
                state_update['current_valve_duration_ms'] = valve_params.get('duration_ms')
            elif step['type'].lower() == 'purge':
                purge_params = step.get('parameters', {})
                state_update['current_purge_duration_ms'] = purge_params.get('duration_ms')
            elif step['type'].lower() == 'loop':
                loop_params = step.get('parameters', {})
                state_update['current_loop_count'] = loop_params.get('count')
                state_update['current_loop_iteration'] = 0  # Will be updated by loop_step
            
            # Update the process execution state
            state_result = supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
            if not state_result.data:
                logger.warning(f"Failed to update process_execution_state for step {step_index}")
            
            # Execute the step
            await execute_step(process_id, step, all_steps, parent_to_child_steps, overall_step_count)
            
            # Update step count based on step type
            if step['type'].lower() == 'loop':
                # Loop steps handle their own counting
                loop_count = int(step['parameters']['count'])
                child_steps = [s for s in all_steps if s.get('parent_step_id') == step['id']]
                overall_step_count += len(child_steps) * loop_count
            else:
                overall_step_count += 1
            
            # Record data points after each step
            await record_process_data(process_id)
        
        # 5. All steps completed successfully
        await complete_recipe(process_id)
        
    except Exception as e:
        logger.error(f"Error executing recipe: {str(e)}", exc_info=True)
        await handle_recipe_error(process_id, str(e))

async def build_parent_child_step_map(steps):
    """
    Build a map of parent steps to their child steps.
    
    Args:
        steps: List of all steps in the recipe
        
    Returns:
        Dictionary mapping parent step IDs to lists of their child steps
    """
    parent_to_child_steps = {}
    
    for step in steps:
        parent_id = step.get('parent_step_id')
        if parent_id:
            if parent_id not in parent_to_child_steps:
                parent_to_child_steps[parent_id] = []
            parent_to_child_steps[parent_id].append(step)
    
    # Sort child steps by sequence number
    for parent_id in parent_to_child_steps:
        parent_to_child_steps[parent_id].sort(key=lambda x: x['sequence_number'])
    
    return parent_to_child_steps


async def complete_recipe(process_id: str):
    """
    Mark a recipe as completed and update machine status.
    
    Args:
        process_id: The ID of the process execution record
    """
    logger.info(f"Recipe execution completed successfully: {process_id}")
    
    # Stop continuous data recording
    await continuous_recorder.stop()
    
    supabase = get_supabase()
    now = get_current_timestamp()
    
    # Update process execution record
    supabase.table('process_executions').update({
        'status': 'completed',
        'end_time': now,
        'updated_at': now
    }).eq('id', process_id).execute()
    
    # Mark process_execution_state as completed
    final_progress_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).execute()
    final_progress = final_progress_result.data[0]['progress'] if final_progress_result.data else {}
    
    state_completion_update = {
        'current_step_type': 'completed',
        'current_step_name': 'Recipe Completed',
        'progress': final_progress,
        'last_updated': 'now()'
    }
    supabase.table('process_execution_state').update(state_completion_update).eq('execution_id', process_id).execute()
    
    # Update machine status
    supabase.table('machines').update({
        'status': 'idle',
        'current_process_id': None,
        'updated_at': now
    }).eq('id', MACHINE_ID).execute()
    
    # Update machine state
    supabase.table('machine_state').update({
        'current_state': 'idle',
        'state_since': now,
        'process_id': None,
        'is_failure_mode': False,
        'updated_at': now
    }).eq('machine_id', MACHINE_ID).execute()

async def handle_recipe_error(process_id: str, error_message: str):
    """
    Handle an error during recipe execution.
    
    Args:
        process_id: The ID of the process execution record
        error_message: Description of the error
    """
    logger.error(f"Recipe execution failed: {error_message}")
    
    # Stop continuous data recording
    await continuous_recorder.stop()
    
    supabase = get_supabase()
    now = get_current_timestamp()
    
    # Update process with error
    supabase.table('process_executions').update({
        'status': 'failed',
        'error_message': error_message,
        'updated_at': now
    }).eq('id', process_id).execute()
    
    # Update process_execution_state with error
    state_error_update = {
        'current_step_type': 'error',
        'current_step_name': f'Error: {error_message[:100]}',  # Truncate long error messages
        'last_updated': 'now()'
    }
    supabase.table('process_execution_state').update(state_error_update).eq('execution_id', process_id).execute()
    
    # Update machine state to error
    supabase.table('machine_state').update({
        'current_state': 'error',
        'is_failure_mode': True,
        'failure_description': f"Recipe execution error: {error_message}",
        'updated_at': now
    }).eq('machine_id', MACHINE_ID).execute()

    # Also mark machine status as error and clear current process association
    supabase.table('machines').update({
        'status': 'error',
        'current_process_id': None,
        'updated_at': now
    }).eq('id', MACHINE_ID).execute()
    
    # Update machine status
    supabase.table('machines').update({
        'status': 'error',
        'updated_at': now
    }).eq('id', MACHINE_ID).execute()
