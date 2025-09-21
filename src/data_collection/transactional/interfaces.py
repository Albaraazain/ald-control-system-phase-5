"""
Transactional data access interfaces for bulletproof dual-mode parameter logging.

This module defines the core interfaces for atomic transaction management,
state-aware data access, and consistency guarantees.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncContextManager
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParameterData:
    """Parameter data with validation and metadata."""
    parameter_id: str
    value: Any
    set_point: Optional[Any] = None
    timestamp: Optional[datetime] = None

    def validate(self) -> bool:
        """Validate parameter data integrity."""
        return (
            self.parameter_id is not None and
            self.value is not None and
            isinstance(self.parameter_id, str) and
            len(self.parameter_id) > 0
        )


@dataclass
class MachineState:
    """Atomic machine state snapshot."""
    status: str
    current_process_id: Optional[str]
    timestamp: datetime

    @property
    def is_processing(self) -> bool:
        """Check if machine is in processing state."""
        return self.status == 'processing' and self.current_process_id is not None


@dataclass
class DualModeResult:
    """Result of dual-mode parameter logging operation."""
    history_count: int
    process_count: int
    machine_state: MachineState
    transaction_id: str
    success: bool
    error_message: Optional[str] = None


class ITransactionManager(ABC):
    """Interface for async transaction management."""

    @abstractmethod
    async def begin_transaction(self) -> AsyncContextManager:
        """Begin a new database transaction."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        pass

    @abstractmethod
    async def savepoint(self, name: str) -> None:
        """Create a savepoint within the transaction."""
        pass

    @abstractmethod
    async def rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a specific savepoint."""
        pass


class IStateRepository(ABC):
    """Interface for atomic state queries."""

    @abstractmethod
    async def get_machine_state(self, machine_id: str) -> MachineState:
        """Get current machine state atomically."""
        pass

    @abstractmethod
    async def update_machine_state(
        self,
        machine_id: str,
        status: str,
        process_id: Optional[str] = None
    ) -> MachineState:
        """Update machine state atomically."""
        pass

    @abstractmethod
    async def validate_process_exists(self, process_id: str) -> bool:
        """Validate that a process exists before logging."""
        pass


class IDualModeRepository(ABC):
    """Interface for atomic dual-mode parameter operations."""

    @abstractmethod
    async def insert_dual_mode_atomic(
        self,
        parameters: List[ParameterData],
        machine_state: MachineState
    ) -> DualModeResult:
        """
        Insert parameters atomically to both tables based on machine state.

        This is the core atomic operation that ensures:
        - All-or-nothing writes to both tables
        - Consistent state-based logging decisions
        - Referential integrity validation
        """
        pass

    @abstractmethod
    async def insert_history_only(
        self,
        parameters: List[ParameterData]
    ) -> int:
        """Insert parameters to history table only (idle mode)."""
        pass

    @abstractmethod
    async def validate_batch_constraints(
        self,
        parameters: List[ParameterData],
        process_id: Optional[str]
    ) -> List[str]:
        """Validate batch constraints and return any errors."""
        pass


class IParameterValidator(ABC):
    """Interface for parameter data validation."""

    @abstractmethod
    async def validate_parameter_value(
        self,
        parameter_id: str,
        value: Any
    ) -> bool:
        """Validate a single parameter value."""
        pass

    @abstractmethod
    async def validate_parameter_batch(
        self,
        parameters: List[ParameterData]
    ) -> List[str]:
        """Validate a batch of parameters and return errors."""
        pass

    @abstractmethod
    async def get_parameter_constraints(
        self,
        parameter_id: str
    ) -> Dict[str, Any]:
        """Get validation constraints for a parameter."""
        pass


class IFailureRecovery(ABC):
    """Interface for failure recovery and resilience."""

    @abstractmethod
    async def execute_with_retry(
        self,
        operation: callable,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> Any:
        """Execute operation with retry logic."""
        pass

    @abstractmethod
    async def create_compensating_action(
        self,
        operation_id: str,
        operation_data: Dict[str, Any]
    ) -> None:
        """Create compensating action for rollback."""
        pass

    @abstractmethod
    async def execute_compensating_actions(
        self,
        transaction_id: str
    ) -> None:
        """Execute all compensating actions for a transaction."""
        pass


class IUnitOfWork(ABC):
    """Interface for unit of work pattern."""

    @abstractmethod
    async def __aenter__(self):
        """Enter async context manager."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager with transaction handling."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit all operations in the unit of work."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback all operations in the unit of work."""
        pass

    @abstractmethod
    def register_operation(self, operation: callable) -> None:
        """Register an operation to be executed in this unit of work."""
        pass


class ITransactionalParameterLogger(ABC):
    """Main interface for transactional parameter logging."""

    @abstractmethod
    async def log_parameters_atomic(
        self,
        parameters: Dict[str, Any],
        machine_id: str
    ) -> DualModeResult:
        """
        Log parameters with full atomicity and consistency guarantees.

        This is the main entry point that coordinates:
        - Atomic state query
        - Parameter validation
        - Dual-mode logging decision
        - Transaction management
        - Failure recovery
        """
        pass

    @abstractmethod
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the transactional logging system."""
        pass