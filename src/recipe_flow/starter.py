"""
Handles starting recipe execution.
"""
from src.log_setup import logger
from src.config import MACHINE_ID
from src.db import get_supabase, get_current_timestamp
from src.recipe_flow.executor import execute_recipe
from src.recipe_flow.continuous_data_recorder import continuous_recorder

async def start_recipe(command_id: int, parameters: dict):
    """
    Handle a command to start a recipe execution.
    
    Args:
        command_id: The ID of the command being processed
        parameters: Command parameters including recipe_id and optional operator_id
    """
    logger.info(f"Starting recipe from command {command_id}")
    supabase = get_supabase()
    
    # Validate required parameters
    if 'recipe_id' not in parameters:
        raise ValueError("Recipe ID is required for start_recipe command")
    
    recipe_id = parameters['recipe_id']
    operator_id = parameters.get('operator_id')
    
    # 1. Get recipe details
    recipe_result = supabase.table('recipes').select('*').eq('id', recipe_id).execute()
    if not recipe_result.data or len(recipe_result.data) == 0:
        raise ValueError(f"Recipe with ID {recipe_id} not found")
    
    recipe = recipe_result.data[0]
    logger.info(f"Starting recipe: {recipe['name']} (ID: {recipe_id})")
    
    # 2. Get recipe steps
    steps_result = supabase.table('recipe_steps').select('*').eq('recipe_id', recipe_id).order('sequence_number').execute()
    recipe_steps = steps_result.data
    if not recipe_steps:
        raise ValueError(f"Recipe {recipe_id} has no steps")
    
    # 3. Get current machine status
    machine_result = supabase.table('machines').select('*').eq('id', MACHINE_ID).execute()
    if not machine_result.data or len(machine_result.data) == 0:
        raise ValueError(f"Machine with ID {MACHINE_ID} not found")
    
    machine = machine_result.data[0]
    
    # 4. Check if machine is available
    if machine['status'] not in ['idle', 'offline']:
        raise ValueError(f"Machine is currently {machine['status']} and cannot start a new recipe")
    
    # 5. Use current operator from machine if not provided
    if not operator_id:
        operator_id = machine['current_operator_id']
        if not operator_id:
            raise ValueError("No operator specified for recipe execution")
    
    # 6. Get or create operator session
    current_session = await get_or_create_operator_session(operator_id)
    
    # 7. Load recipe parameters from recipe_parameters table
    params_result = supabase.table('recipe_parameters').select('*').eq('recipe_id', recipe_id).execute()
    recipe_params = {p['parameter_name']: p['parameter_value'] for p in params_result.data if params_result.data}
    
    # 7.5 Prepare recipe version JSON
    recipe_version = {
        'id': recipe['id'],
        'name': recipe['name'],
        'version': recipe['version'],
        'steps': recipe_steps,
        'chamber_temperature_set_point': recipe_params.get('chamber_temperature_set_point', recipe.get('chamber_temperature_set_point')),
        'pressure_set_point': recipe_params.get('pressure_set_point', recipe.get('pressure_set_point')),
        'parameters': recipe_params  # Include all loaded parameters
    }
    # 8. Create process execution record
    process_id = await create_process_execution(
        current_session['id'],
        recipe_id,
        recipe_version,
        operator_id,
        recipe_steps
    )
    
    # 8.5 Calculate total steps including loop iterations for progress tracking
    total_steps = 0
    for step in recipe_steps:
        if step['type'].lower() == 'loop':
            loop_count = int(step['parameters']['count'])
            child_steps = [s for s in recipe_steps if s.get('parent_step_id') == step['id']]
            total_steps += len(child_steps) * loop_count
        elif not step.get('parent_step_id'):  # Only count non-child steps
            total_steps += 1
    
    # 8.6 Create process execution state record (DB trigger may handle this)
    # Many deployments auto-create this row via a DB trigger; avoid racing inserts here.
    logger.info("Skipping explicit process_execution_state insert (handled by trigger if present)")
    
    # 9. Update machine status
    await update_machine_status('processing', process_id)
    
    # 10. Update machine state
    await update_machine_state('processing', process_id)
    
    # 11-12. Start continuous data recording and execute the recipe
    # Wrap in try/except to ensure we transition to an error state if something
    # fails before execute_recipe() can handle it.
    try:
        await continuous_recorder.start(process_id)
        await execute_recipe(process_id)
    except Exception as e:
        # Defer to the shared error handler to keep DB state consistent
        from src.recipe_flow.executor import handle_recipe_error  # local import to avoid cycles
        await handle_recipe_error(process_id, str(e))
        raise
    
    logger.info(f"Recipe {recipe_id} started successfully with process ID: {process_id}")
    
async def get_or_create_operator_session(operator_id):
    """Get an existing operator session or create a new one."""
    supabase = get_supabase()
    
    # Try to find an active session
    session_result = supabase.table('operator_sessions').select('*').eq('operator_id', operator_id).eq('machine_id', MACHINE_ID).eq('status', 'active').execute()
    
    if session_result.data and len(session_result.data) > 0:
        logger.info(f"Using existing operator session: {session_result.data[0]['id']}")
        return session_result.data[0]
    
    # Create a new session
    session_data = {
        'operator_id': operator_id,
        'machine_id': MACHINE_ID,
        'start_time': get_current_timestamp(),
        'status': 'active'
    }
    
    session_result = supabase.table('operator_sessions').insert(session_data).execute()
    if not session_result.data or len(session_result.data) == 0:
        raise RuntimeError("Failed to create operator session")
    
    logger.info(f"Created new operator session: {session_result.data[0]['id']}")
    return session_result.data[0]

async def create_process_execution(session_id, recipe_id, recipe_version, operator_id, recipe_steps):
    """Create a new process execution record in the database."""
    supabase = get_supabase()
    now = get_current_timestamp()
    
    process_data = {
        'session_id': session_id,
        'machine_id': MACHINE_ID,
        'recipe_id': recipe_id,
        'recipe_version': recipe_version,
        'start_time': now,
        'operator_id': operator_id,
        'status': 'running',
        'parameters': recipe_version.get('parameters', {
            'chamber_temperature_set_point': recipe_version.get('chamber_temperature_set_point'),
            'pressure_set_point': recipe_version.get('pressure_set_point')
        })
    }
    process_result = supabase.table('process_executions').insert(process_data).execute()
    if not process_result.data or len(process_result.data) == 0:
        raise RuntimeError("Failed to create process execution record")
    
    return process_result.data[0]['id']

async def update_machine_status(status, process_id=None):
    """Update the machine status in the database."""
    supabase = get_supabase()
    
    update_data = {
        'status': status,
        'updated_at': get_current_timestamp()
    }
    
    if process_id:
        update_data['current_process_id'] = process_id
    elif status == 'idle':
        update_data['current_process_id'] = None
    
    result = supabase.table('machines').update(update_data).eq('id', MACHINE_ID).execute()
    if not result.data or len(result.data) == 0:
        raise RuntimeError("Failed to update machine status")
    
    logger.info(f"Updated machine status to {status}")
    return result.data[0]

async def update_machine_state(state, process_id=None):
    """Update the machine state in the database."""
    supabase = get_supabase()
    now = get_current_timestamp()
    
    state_update = {
        'current_state': state,
        'state_since': now,
        'is_failure_mode': False,
        'failure_component': None,
        'failure_description': None,
        'updated_at': now
    }
    
    if process_id:
        state_update['process_id'] = process_id
    else:
        state_update['process_id'] = None
    
    result = supabase.table('machine_state').update(state_update).eq('machine_id', MACHINE_ID).execute()
    if not result.data or len(result.data) == 0:
        raise RuntimeError("Failed to update machine state")
    
    logger.info(f"Updated machine state to {state}")
    return result.data[0]
