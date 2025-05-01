"""
Executes a recipe by processing its steps in sequence.
"""
import asyncio
from log_setup import logger
from config import MACHINE_ID
from db import get_supabase, get_current_timestamp
from recipe_flow.data_recorder import record_process_data
from step_flow.executor import execute_step
from recipe_flow.continuous_data_recorder import continuous_recorder

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
                
        # Update process with total steps count and initialize progress
        supabase.table('process_executions').update({
            'progress': {
                'total_steps': total_steps,
                'completed_steps': 0,
                'total_cycles': total_cycles,
                'completed_cycles': 0
            }
        }).eq('id', process_id).execute()
        
        # 2. Build parent-child step map
        parent_to_child_steps = await build_parent_child_step_map(all_steps)
        
        # 3. Get top-level steps (those without parent_step_id)
        top_level_steps = [step for step in all_steps if not step.get('parent_step_id')]
        top_level_steps.sort(key=lambda x: x['sequence_number'])
        
        # 4. Execute top-level steps sequentially
        for step in top_level_steps:
            logger.info(f"Executing top-level step: {step['name']} (Type: {step['type']})")
            
            # Update process with current step
            supabase.table('process_executions').update({
                'current_step': step,
                'updated_at': get_current_timestamp()
            }).eq('id', process_id).execute()
            
            # Execute the step
            await execute_step(process_id, step, all_steps, parent_to_child_steps)
            
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
    
    # Update machine state to error
    supabase.table('machine_state').update({
        'current_state': 'error',
        'is_failure_mode': True,
        'failure_description': f"Recipe execution error: {error_message}",
        'updated_at': now
    }).eq('machine_id', MACHINE_ID).execute()
    
    # Update machine status
    supabase.table('machines').update({
        'status': 'error',
        'updated_at': now
    }).eq('id', MACHINE_ID).execute()