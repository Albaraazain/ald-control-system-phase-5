"""
Executes parameter setting steps in a recipe and handles parameter set commands.
"""
from log_setup import logger
from db import get_supabase, get_current_timestamp
from plc.manager import plc_manager


async def execute_parameter_step(process_id: str, step: dict):
    """
    Execute a parameter-setting step, updating a component parameter value.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
    """
    parameters = step.get('parameters', {})
    
    # Validate parameters
    required_params = ['parameter_id', 'value']
    for param in required_params:
        if param not in parameters:
            raise ValueError(f"Parameter step is missing required parameter: {param}")
    
    parameter_id = parameters['parameter_id']
    parameter_value = parameters['value']
    
    supabase = get_supabase()
    
    # Get current progress from process_execution_state
    state_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).single().execute()
    current_progress = state_result.data['progress'] if state_result.data else {}
    
    # Update only basic fields in process_executions
    supabase.table('process_executions').update({
        'updated_at': get_current_timestamp()
    }).eq('id', process_id).execute()
    
    # Update process_execution_state
    state_update = {
        'current_step_type': 'set_parameter',
        'current_step_name': step['name'],
        'current_parameter_id': parameter_id,
        'current_parameter_value': parameter_value,
        'progress': current_progress,
        'last_updated': 'now()'
    }
    supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
    
    # Set the parameter to the specified value
    await set_parameter_value(parameter_id, parameter_value)

async def set_parameter(command_id: int, parameters: dict):
    """
    Handle a command to set a specific parameter.
    This is used for direct parameter setting commands.
    
    Args:
        command_id: The ID of the command being processed
        parameters: Command parameters including parameter_id and value
    """
    logger.info(f"Setting parameter from command {command_id}")
    
    # Validate parameters
    if 'parameter_id' not in parameters:
        raise ValueError("Parameter ID is required for set_parameter command")
    
    if 'value' not in parameters:
        raise ValueError("Value is required for set_parameter command")
    
    parameter_id = parameters['parameter_id']
    parameter_value = parameters['value']
    
    # Set the parameter to the specified value
    await set_parameter_value(parameter_id, parameter_value)


async def set_parameter_value(parameter_id, parameter_value):
    """
    Set a parameter to a specific value.
    
    Args:
        parameter_id: The ID of the parameter to update
        parameter_value: The new value for the parameter
    """
    supabase = get_supabase()
    
    logger.info(f"Setting parameter {parameter_id} to {parameter_value}")
    
    # 1. Find the parameter record in the database by ID
    param_result = supabase.table('component_parameters').select('*').eq('id', parameter_id).execute()
    
    if not param_result.data or len(param_result.data) == 0:
        raise ValueError(f"Parameter with ID {parameter_id} not found")
    
    parameter = param_result.data[0]
    
    # 2. Validate the value against min and max
    min_value = parameter['min_value']
    max_value = parameter['max_value']
    
    if parameter_value < min_value or parameter_value > max_value:
        raise ValueError(f"Parameter value {parameter_value} outside allowed range ({min_value} to {max_value})")
    
    # 3. Write the value to the PLC
    plc = plc_manager.plc
    if plc:
        success = await plc.write_parameter(parameter_id, parameter_value)
        if not success:
            raise RuntimeError(f"Failed to write parameter {parameter_id} to PLC")
    
    # 4. Update the parameter value in the database
    update_data = {
        'set_value': parameter_value,
        'updated_at': get_current_timestamp()
    }
    
    result = supabase.table('component_parameters').update(update_data).eq('id', parameter_id).execute()
    
    if not result.data or len(result.data) == 0:
        raise RuntimeError(f"Failed to update parameter {parameter_id}")
    
    logger.info(f"Parameter {parameter_id} set successfully to {parameter_value}")
    return result.data[0]