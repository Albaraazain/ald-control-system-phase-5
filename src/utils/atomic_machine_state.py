"""
Atomic machine state update utilities

This module provides atomic operations to replace dual table updates
and eliminate race conditions between machines and machine_state tables.
"""

import logging
from typing import Dict, Any, Optional
from src.db import get_supabase

logger = logging.getLogger(__name__)


def atomic_complete_machine_state(machine_id: str) -> Dict[str, Any]:
    """
    Atomically set machine to idle state (recipe completion).

    This replaces the non-atomic dual table updates in executor.py:203-216

    Args:
        machine_id: UUID of the machine to update

    Returns:
        Dict containing success status and updated records

    Raises:
        Exception: If atomic update fails
    """
    try:
        supabase = get_supabase()
        result = supabase.rpc('atomic_complete_machine_state', {
            'p_machine_id': machine_id
        }).execute()

        if result.data:
            logger.info(f"Successfully completed machine state atomically for machine {machine_id}")
            return result.data
        else:
            raise Exception("Atomic complete machine state returned no data")

    except Exception as e:
        logger.error(f"Failed to atomically complete machine state for {machine_id}: {e}")
        raise


def atomic_error_machine_state(machine_id: str, error_message: str) -> Dict[str, Any]:
    """
    Atomically set machine to error state with failure description.

    This replaces the non-atomic dual table updates in executor.py:250-262

    Args:
        machine_id: UUID of the machine to update
        error_message: Error description for failure_description

    Returns:
        Dict containing success status and updated records

    Raises:
        Exception: If atomic update fails
    """
    try:
        supabase = get_supabase()
        result = supabase.rpc('atomic_error_machine_state', {
            'p_machine_id': machine_id,
            'p_error_message': error_message
        }).execute()

        if result.data:
            logger.info(f"Successfully set machine state to error atomically for machine {machine_id}")
            return result.data
        else:
            raise Exception("Atomic error machine state returned no data")

    except Exception as e:
        logger.error(f"Failed to atomically set machine error state for {machine_id}: {e}")
        raise


def atomic_processing_machine_state(machine_id: str, process_id: str) -> Dict[str, Any]:
    """
    Atomically set machine to processing state with process ID.

    This replaces dual table updates in starter.py and other processing states

    Args:
        machine_id: UUID of the machine to update
        process_id: UUID of the process being executed

    Returns:
        Dict containing success status and updated records

    Raises:
        Exception: If atomic update fails
    """
    try:
        supabase = get_supabase()
        result = supabase.rpc('atomic_processing_machine_state', {
            'p_machine_id': machine_id,
            'p_process_id': process_id
        }).execute()

        if result.data:
            logger.info(f"Successfully set machine state to processing atomically for machine {machine_id}")
            return result.data
        else:
            raise Exception("Atomic processing machine state returned no data")

    except Exception as e:
        logger.error(f"Failed to atomically set machine processing state for {machine_id}: {e}")
        raise


def atomic_update_machine_state_custom(
    machine_id: str,
    machine_status: str,
    machine_state_current_state: str,
    current_process_id: Optional[str] = None,
    machine_state_process_id: Optional[str] = None,
    is_failure_mode: bool = False,
    failure_description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Custom atomic machine state update for specific scenarios.

    Args:
        machine_id: UUID of the machine to update
        machine_status: Status for machines table ('idle', 'processing', 'error')
        machine_state_current_state: State for machine_state table
        current_process_id: Process ID for machines table (optional)
        machine_state_process_id: Process ID for machine_state table (optional)
        is_failure_mode: Failure mode flag for machine_state table
        failure_description: Error description (optional)

    Returns:
        Dict containing success status and updated records

    Raises:
        Exception: If atomic update fails
    """
    try:
        supabase = get_supabase()
        result = supabase.rpc('atomic_update_machine_state', {
            'p_machine_id': machine_id,
            'p_machine_status': machine_status,
            'p_current_process_id': current_process_id,
            'p_machine_state_current_state': machine_state_current_state,
            'p_machine_state_process_id': machine_state_process_id,
            'p_is_failure_mode': is_failure_mode,
            'p_failure_description': failure_description
        }).execute()

        if result.data:
            logger.info(f"Successfully updated machine state atomically for machine {machine_id}")
            return result.data
        else:
            raise Exception("Atomic machine state update returned no data")

    except Exception as e:
        logger.error(f"Failed to atomically update machine state for {machine_id}: {e}")
        raise


# Backward compatibility wrappers for existing code
def legacy_dual_table_complete(machine_id: str, now: str) -> None:
    """
    Legacy wrapper for dual table completion.
    Use atomic_complete_machine_state() instead.
    """
    logger.warning("Using legacy dual table wrapper - consider migrating to atomic_complete_machine_state()")
    atomic_complete_machine_state(machine_id)


def legacy_dual_table_error(machine_id: str, error_message: str, now: str) -> None:
    """
    Legacy wrapper for dual table error state.
    Use atomic_error_machine_state() instead.
    """
    logger.warning("Using legacy dual table wrapper - consider migrating to atomic_error_machine_state()")
    atomic_error_machine_state(machine_id, error_message)