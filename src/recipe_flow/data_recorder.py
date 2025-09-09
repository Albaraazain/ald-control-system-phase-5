"""
Records process data during recipe execution.
"""
from log_setup import logger
from config import MACHINE_ID
from db import get_supabase, get_current_timestamp

async def record_process_data(process_id: str):
    """
    Record current values of all component parameters as data points.
    
    Args:
        process_id: The ID of the current process execution
    """
    logger.info(f"Recording process data points for process {process_id}")
    supabase = get_supabase()
    
    # 1. Get all active components for this machine
    components_result = supabase.table('machine_components').select('id').eq('machine_id', MACHINE_ID).eq('is_activated', True).execute()
    
    if not components_result.data:
        logger.warning("No active components found for machine")
        return
    
    component_ids = [comp['id'] for comp in components_result.data]
    
    # 2. Get all parameters for these components
    data_points = []
    now = get_current_timestamp()
    
    for component_id in component_ids:
        params_result = supabase.table('component_parameters').select('*').eq('component_id', component_id).execute()
        
        if not params_result.data:
            continue
            
        for param in params_result.data:
            data_point = {
                'process_id': process_id,
                'parameter_id': param['id'],
                'value': param['current_value'],
                'set_point': param['set_value'],
                'timestamp': now
            }
            data_points.append(data_point)
    
    # 3. Insert data points in batches to avoid large requests
    if data_points:
        # Insert in batches of 50
        batch_size = 50
        for i in range(0, len(data_points), batch_size):
            batch = data_points[i:i+batch_size]
            supabase.table('process_data_points').insert(batch).execute()
        
        logger.info(f"Recorded {len(data_points)} data points for process {process_id}")
    else:
        logger.warning("No parameters found to record as data points")