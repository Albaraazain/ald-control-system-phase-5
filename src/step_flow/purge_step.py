"""
Executes purge steps in a recipe.

Purge is implemented as a time-based wait only with periodic cancellation checks.
No PLC actuation (no valve toggles or writes) occurs during purge in either real
or simulation modes; recording/logging continues as usual.
"""
import asyncio
import time
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from src.recipe_flow.cancellation import is_cancelled


async def execute_purge_step(process_id: str, step: dict) -> None:
    """
    Execute a purging step, which runs for a specified duration.

    Args:
        process_id: The ID of the current process execution
        step: The step data including parameters
    """
    supabase = get_supabase()
    step_id = step.get('id')

    # Load purge configuration from purge_step_config table when we have a valid step_id
    purge_config = None
    if step_id is not None:
        result = (
            supabase.table('purge_step_config')
            .select('*')
            .eq('step_id', step_id)
            .execute()
        )
        purge_config = result.data[0] if result.data else None

    if not purge_config:
        # Fallback to old method for backwards compatibility
        parameters = step.get('parameters', {})

        # Defensive: Check for both possible parameter names
        duration_ms = None
        if 'duration_ms' in parameters:
            try:
                duration_ms = int(parameters['duration_ms'])
            except (ValueError, TypeError):
                logger.warning(
                    f"⚠️ Purge step '{step.get('name', 'Unknown')}' has non-numeric "
                    f"duration_ms '{parameters.get('duration_ms')}'. Defaulting to 1000ms."
                )
                duration_ms = None
        elif 'duration' in parameters:
            try:
                duration_ms = int(parameters['duration'])
            except (ValueError, TypeError):
                logger.warning(
                    f"⚠️ Purge step '{step.get('name', 'Unknown')}' has non-numeric "
                    f"duration '{parameters.get('duration')}'. Defaulting to 1000ms."
                )
                duration_ms = None

        # Defensive: Use sensible default if missing or invalid
        if duration_ms is None:
            logger.warning(
                f"⚠️ Purge step '{step.get('name', 'Unknown')}' missing duration parameter. "
                f"Defaulting to 1000ms (1 second)."
            )
            duration_ms = 1000  # Default to 1 second
        elif duration_ms < 0:
            logger.warning(
                f"⚠️ Purge step '{step.get('name', 'Unknown')}' has negative duration "
                f"{duration_ms}ms. Defaulting to 1000ms."
            )
            duration_ms = 1000

        # Set default values for new fields
        gas_type = parameters.get('gas_type', 'N2')
        flow_rate = parameters.get('flow_rate', 0.0)
    else:
        # Use new purge_step_config table
        duration_ms = purge_config['duration_ms']
        gas_type = purge_config['gas_type']
        flow_rate = purge_config['flow_rate']

    logger.info(
        "Executing purge step (wait-only): duration=%sms, gas=%s, flow_rate=%s",
        duration_ms,
        gas_type,
        flow_rate,
    )

    # Early cancel check
    if is_cancelled(process_id):
        logger.info("Purge step cancelled before execution")
        return

    # Get current progress from process_execution_state
    state_result = (
        supabase
        .table('process_execution_state')
        .select('progress')
        .eq('execution_id', process_id)
        .single()
        .execute()
    )
    current_progress = state_result.data['progress'] if state_result.data else {}

    # Update only basic fields in process_executions
    supabase.table('process_executions').update(
        {'updated_at': get_current_timestamp()}
    ).eq('id', process_id).execute()

    # Update process_execution_state
    state_update = {
        'current_step_type': 'purge',
        'current_step_name': step['name'],
        'current_purge_duration_ms': duration_ms,
        'progress': current_progress,
        'last_updated': 'now()'
    }
    (
        supabase
        .table('process_execution_state')
        .update(state_update)
        .eq('execution_id', process_id)
        .execute()
    )

    # Purge is a time-based wait only; periodically check for cancellation.
    start = time.monotonic()
    end_time = start + (duration_ms / 1000.0)
    interval = 0.2  # seconds

    while True:
        if is_cancelled(process_id):
            logger.info("Purge step cancelled during wait; exiting early")
            return

        now = time.monotonic()
        if now >= end_time:
            break
        await asyncio.sleep(min(interval, max(0.0, end_time - now)))

    logger.info("Purge step completed (wait-only; no PLC actuation)")
