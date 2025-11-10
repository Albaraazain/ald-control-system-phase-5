"""
Executes valve steps in a recipe.
"""
import asyncio
import os
from datetime import datetime, timezone
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.plc.manager import plc_manager
from src.recipe_flow.cancellation import is_cancelled


async def _audit_log_recipe_operation(
    process_id: str,
    recipe_id: str,
    step_id: str,
    operation_type: str,
    parameter_name: str,
    target_value: float,
    duration_ms: int = None,
    step_sequence: int = None,
    plc_write_start: datetime = None,
    plc_write_end: datetime = None,
    modbus_address: int = None,
    error_message: str = None,
    final_status: str = 'success'
):
    """
    Comprehensive audit logging to recipe_execution_audit table.

    Logs ALL recipe operations with full context for traceability, debugging, and compliance.

    Args:
        process_id: Process execution ID
        recipe_id: Recipe ID
        step_id: Recipe step ID
        operation_type: Type of operation ('valve', 'parameter', 'purge', etc.)
        parameter_name: Human-readable name (e.g., 'Valve_1')
        target_value: Commanded value
        duration_ms: Duration for valve/purge operations
        step_sequence: Sequential position in recipe
        plc_write_start: When PLC write started
        plc_write_end: When PLC write completed
        modbus_address: Modbus address written to
        error_message: Error details if failed
        final_status: Operation status ('success', 'failed', 'cancelled')
    """
    try:
        supabase = get_supabase()
        machine_id = os.environ.get('MACHINE_ID')

        # Build comprehensive audit record
        audit_record = {
            'process_id': process_id,
            'recipe_id': recipe_id,
            'step_id': step_id,
            'machine_id': machine_id,
            'operation_type': operation_type,
            'parameter_name': parameter_name,
            'target_value': target_value,
            'duration_ms': duration_ms,
            'step_sequence': step_sequence if step_sequence is not None else 0,
            'loop_iteration': 0,  # TODO: Extract from execution context when loops implemented
            'operation_initiated_at': get_current_timestamp(),
            'plc_write_start_time': plc_write_start.isoformat() if plc_write_start else None,
            'plc_write_end_time': plc_write_end.isoformat() if plc_write_end else None,
            'operation_completed_at': get_current_timestamp(),
            'verification_attempted': False,  # TODO: Enable when verification implemented
            'final_status': final_status,
            'modbus_address': modbus_address,
            'error_message': error_message,
        }

        # Insert audit record to recipe_execution_audit table
        result = supabase.table('recipe_execution_audit').insert(audit_record).execute()

        logger.info(f"✅ Audited {operation_type} operation: {parameter_name} = {target_value} (process: {process_id})")

    except Exception as e:
        # Log error but DO NOT propagate - recipe execution must continue even if audit fails
        logger.error(f"❌ Failed to audit {operation_type} operation {parameter_name}: {e}", exc_info=True)


async def execute_valve_step(process_id: str, step: dict):
    """
    Execute a valve operation step, opening a specific valve for a duration.
    
    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
    """
    supabase = get_supabase()
    step_id = step.get('id')
    
    # Load valve configuration from valve_step_config table
    result = supabase.table('valve_step_config').select('*').eq('step_id', step_id).execute()
    valve_config = result.data[0] if result.data else None
    
    if not valve_config:
        # Fallback to old method for backwards compatibility
        parameters = step.get('parameters', {})
        step_type = step['type']
        
        # Defensive: Try to extract valve number from type
        valve_number = None
        if 'open valve' in step_type.lower():
            # Extract valve number from step type (e.g., "open valve 1" -> 1)
            try:
                valve_number = int(step_type.split('valve')[1].strip())
            except (IndexError, ValueError):
                pass
        
        # If not found in type, check parameters
        if valve_number is None and 'valve_number' in parameters:
            try:
                valve_number = int(parameters['valve_number'])
            except (ValueError, TypeError):
                pass
        
        # Defensive: Default to valve 1 if unable to determine
        if valve_number is None:
            logger.warning(
                f"⚠️ Valve step '{step.get('name', 'Unknown')}' unable to determine valve number. "
                f"Defaulting to valve 1."
            )
            valve_number = 1
        
        # Defensive: Handle missing or invalid duration_ms
        duration_ms = None
        if 'duration_ms' in parameters:
            try:
                duration_ms = int(parameters['duration_ms'])
            except (ValueError, TypeError):
                logger.warning(
                    f"⚠️ Valve step '{step.get('name', 'Unknown')}' has non-numeric "
                    f"duration_ms '{parameters.get('duration_ms')}'. Defaulting to 1000ms."
                )
        
        if duration_ms is None:
            logger.warning(
                f"⚠️ Valve step '{step.get('name', 'Unknown')}' missing duration_ms parameter. "
                f"Defaulting to 1000ms (1 second)."
            )
            duration_ms = 1000  # Default to 1 second
        elif duration_ms < 0:
            logger.warning(
                f"⚠️ Valve step '{step.get('name', 'Unknown')}' has negative duration "
                f"{duration_ms}ms. Defaulting to 1000ms."
            )
            duration_ms = 1000
    else:
        # Use new valve_step_config table
        valve_number = valve_config['valve_number']
        duration_ms = valve_config['duration_ms']
    
    logger.info(f"Opening valve {valve_number} for {duration_ms}ms")
    
    # Early cancel check
    if is_cancelled(process_id):
        logger.info("Valve step cancelled before execution")
        return

    # Get current progress from process_execution_state
    state_result = supabase.table('process_execution_state').select('progress').eq('execution_id', process_id).single().execute()
    current_progress = state_result.data['progress'] if state_result.data else {}
    
    # Update only basic fields in process_executions
    supabase.table('process_executions').update({
        'updated_at': get_current_timestamp()
    }).eq('id', process_id).execute()
    
    # Update process_execution_state
    state_update = {
        'current_step_type': 'valve',
        'current_step_name': step['name'],
        'current_valve_number': valve_number,
        'current_valve_duration_ms': duration_ms,
        'progress': current_progress,
        'last_updated': 'now()'
    }
    supabase.table('process_execution_state').update(state_update).eq('execution_id', process_id).execute()
    
    # Get recipe_id and step_sequence for audit trail
    process_result = supabase.table('process_executions').select('recipe_id').eq('id', process_id).single().execute()
    recipe_id = process_result.data['recipe_id'] if process_result.data else None

    # Get step sequence from execution state
    state_result = supabase.table('process_execution_state').select('current_overall_step').eq('execution_id', process_id).single().execute()
    step_sequence = state_result.data['current_overall_step'] if state_result.data else 0

    # Control the valve via PLC
    from src.plc.context import get_plc
    plc = get_plc()
    plc_write_start = None
    plc_write_end = None
    error_msg = None
    status = 'success'

    if plc:
        plc_write_start = datetime.now(timezone.utc)
        success = await plc.control_valve(valve_number, True, duration_ms)
        plc_write_end = datetime.now(timezone.utc)

        if not success:
            error_msg = f"Failed to control valve {valve_number}"
            status = 'failed'

            # Audit the failed operation
            await _audit_log_recipe_operation(
                process_id=process_id,
                recipe_id=recipe_id,
                step_id=step_id,
                operation_type='valve',
                parameter_name=f'Valve_{valve_number}',
                target_value=1,
                duration_ms=duration_ms,
                step_sequence=step_sequence,
                plc_write_start=plc_write_start,
                plc_write_end=plc_write_end,
                error_message=error_msg,
                final_status=status
            )

            raise RuntimeError(error_msg)

        # Audit the successful valve operation with full context
        await _audit_log_recipe_operation(
            process_id=process_id,
            recipe_id=recipe_id,
            step_id=step_id,
            operation_type='valve',
            parameter_name=f'Valve_{valve_number}',
            target_value=1,
            duration_ms=duration_ms,
            step_sequence=step_sequence,
            plc_write_start=plc_write_start,
            plc_write_end=plc_write_end,
            final_status=status
        )
    else:
        # Fallback to simulation behavior if no PLC
        await asyncio.sleep(duration_ms / 1000)

        # Still audit the simulated operation
        await _audit_log_recipe_operation(
            process_id=process_id,
            recipe_id=recipe_id,
            step_id=step_id,
            operation_type='valve',
            parameter_name=f'Valve_{valve_number}',
            target_value=1,
            duration_ms=duration_ms,
            step_sequence=step_sequence,
            final_status='success'
        )

    logger.info(f"Valve {valve_number} operation completed successfully")
