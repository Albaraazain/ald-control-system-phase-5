"""
Atomic state repository implementation for consistent machine state management.

This module provides atomic state queries and updates to eliminate race conditions
in dual-mode parameter logging.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
from src.log_setup import logger
from src.db import get_supabase, get_current_timestamp
from .interfaces import IStateRepository, MachineState


class AtomicStateRepository(IStateRepository):
    """
    Repository for atomic machine state operations.

    Provides:
    - Atomic state queries with consistent reads
    - Atomic state updates with validation
    - Process existence validation
    - Race condition elimination
    """

    def __init__(self):
        """Initialize the state repository."""
        self._lock = asyncio.Lock()

    async def get_machine_state(self, machine_id: str) -> MachineState:
        """
        Get current machine state atomically.

        This method ensures that status and current_process_id are read
        consistently to eliminate race conditions during state transitions.
        """
        try:
            supabase = get_supabase()

            # Single atomic query to get both status and current_process_id
            result = supabase.table('machines').select(
                'status, current_process_id, updated_at'
            ).eq('id', machine_id).single().execute()

            if not result.data:
                raise ValueError(f"Machine {machine_id} not found")

            data = result.data
            timestamp = datetime.fromisoformat(data.get('updated_at', get_current_timestamp()))

            machine_state = MachineState(
                status=data['status'],
                current_process_id=data.get('current_process_id'),
                timestamp=timestamp
            )

            logger.debug(
                f"Retrieved machine state: status={machine_state.status}, "
                f"process_id={machine_state.current_process_id}, "
                f"is_processing={machine_state.is_processing}"
            )

            return machine_state

        except Exception as e:
            logger.error(f"Failed to get machine state for {machine_id}: {e}")
            raise

    async def update_machine_state(
        self,
        machine_id: str,
        status: str,
        process_id: Optional[str] = None
    ) -> MachineState:
        """
        Update machine state atomically.

        This method ensures that status and current_process_id are updated
        together in a single atomic operation to prevent race conditions.
        """
        try:
            async with self._lock:
                supabase = get_supabase()
                timestamp = get_current_timestamp()

                # Prepare update data
                update_data = {
                    'status': status,
                    'updated_at': timestamp
                }

                # Handle process_id based on status
                if status == 'processing':
                    if process_id is None:
                        raise ValueError("process_id required when status is 'processing'")
                    update_data['current_process_id'] = process_id
                elif status == 'idle':
                    update_data['current_process_id'] = None
                elif process_id is not None:
                    update_data['current_process_id'] = process_id

                # Atomic update
                result = supabase.table('machines').update(update_data).eq(
                    'id', machine_id
                ).execute()

                if not result.data or len(result.data) == 0:
                    raise ValueError(f"Failed to update machine {machine_id} or machine not found")

                updated_data = result.data[0]
                machine_state = MachineState(
                    status=updated_data['status'],
                    current_process_id=updated_data.get('current_process_id'),
                    timestamp=datetime.fromisoformat(updated_data['updated_at'])
                )

                logger.info(
                    f"Updated machine state atomically: machine_id={machine_id}, "
                    f"status={status}, process_id={process_id}"
                )

                return machine_state

        except Exception as e:
            logger.error(f"Failed to update machine state for {machine_id}: {e}")
            raise

    async def validate_process_exists(self, process_id: str) -> bool:
        """
        Validate that a process exists before logging data to it.

        This prevents orphaned process_data_points records and ensures
        referential integrity.
        """
        try:
            supabase = get_supabase()

            result = supabase.table('process_executions').select('id').eq(
                'id', process_id
            ).execute()

            exists = bool(result.data and len(result.data) > 0)

            if not exists:
                logger.warning(f"Process {process_id} does not exist")

            return exists

        except Exception as e:
            logger.error(f"Failed to validate process existence for {process_id}: {e}")
            return False

    async def get_machine_state_with_validation(
        self,
        machine_id: str,
        validate_process: bool = True
    ) -> MachineState:
        """
        Get machine state with optional process validation.

        This method provides an additional layer of validation to ensure
        that if the machine is in processing state, the process actually exists.
        """
        try:
            machine_state = await self.get_machine_state(machine_id)

            if validate_process and machine_state.is_processing:
                process_exists = await self.validate_process_exists(
                    machine_state.current_process_id
                )

                if not process_exists:
                    logger.error(
                        f"Machine {machine_id} reports processing state but "
                        f"process {machine_state.current_process_id} does not exist"
                    )
                    # Return idle state to prevent logging to non-existent process
                    return MachineState(
                        status='idle',
                        current_process_id=None,
                        timestamp=machine_state.timestamp
                    )

            return machine_state

        except Exception as e:
            logger.error(f"Failed to get validated machine state for {machine_id}: {e}")
            raise

    async def transition_state_safely(
        self,
        machine_id: str,
        from_status: str,
        to_status: str,
        process_id: Optional[str] = None
    ) -> MachineState:
        """
        Safely transition machine state with validation.

        This method ensures that state transitions are valid and atomic,
        preventing invalid state changes.
        """
        try:
            async with self._lock:
                # Get current state
                current_state = await self.get_machine_state(machine_id)

                # Validate transition
                if current_state.status != from_status:
                    raise ValueError(
                        f"Invalid state transition: expected {from_status}, "
                        f"got {current_state.status}"
                    )

                # Validate transition rules
                valid_transitions = {
                    'idle': ['processing'],
                    'processing': ['idle', 'error', 'completed'],
                    'error': ['idle'],
                    'completed': ['idle']
                }

                if to_status not in valid_transitions.get(from_status, []):
                    raise ValueError(
                        f"Invalid state transition from {from_status} to {to_status}"
                    )

                # Perform atomic update
                return await self.update_machine_state(machine_id, to_status, process_id)

        except Exception as e:
            logger.error(
                f"Failed to transition machine state from {from_status} to {to_status}: {e}"
            )
            raise

    async def get_health_status(self) -> dict:
        """Get health status of the state repository."""
        try:
            # Test basic connectivity
            supabase = get_supabase()
            result = supabase.table('machines').select('count', count='exact').execute()

            return {
                'status': 'healthy',
                'machine_count': result.count if result.count is not None else 0,
                'timestamp': get_current_timestamp()
            }

        except Exception as e:
            logger.error(f"State repository health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': get_current_timestamp()
            }


# Global state repository instance
state_repository = AtomicStateRepository()