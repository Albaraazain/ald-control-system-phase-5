"""
Transactional data access layer for bulletproof dual-mode parameter logging.

This package provides:
- Atomic transaction management with rollback capabilities
- State-aware data access that eliminates race conditions
- Dual-mode repository with all-or-nothing guarantees
- Comprehensive failure recovery and compensation mechanisms
- Performance monitoring and health checks

Key Components:
- TransactionalParameterLogger: Main interface for atomic parameter logging
- AsyncTransactionManager: Transaction boundary management
- AtomicStateRepository: Consistent machine state operations
- AtomicDualModeRepository: Dual-table atomic operations

Usage:
    from src.data_collection.transactional import transactional_logger

    # Initialize the system
    await transactional_logger.initialize()

    # Log parameters atomically
    result = await transactional_logger.log_parameters_atomic({
        'temperature': 25.5,
        'pressure': 101.3,
        'flow_rate': 2.1
    })

    if result.success:
        print(f"Logged {result.history_count} to history, {result.process_count} to process")
    else:
        print(f"Logging failed: {result.error_message}")
"""

from .interfaces import (
    ITransactionManager,
    IStateRepository,
    IDualModeRepository,
    IParameterValidator,
    IFailureRecovery,
    IUnitOfWork,
    ITransactionalParameterLogger,
    ParameterData,
    MachineState,
    DualModeResult
)

from .transaction_manager import (
    AsyncTransactionManager,
    TransactionContext,
    transaction_manager
)

from .state_repository import (
    AtomicStateRepository,
    state_repository
)

from .dual_mode_repository import (
    AtomicDualModeRepository,
    dual_mode_repository
)

from .transactional_logger import (
    TransactionalParameterLogger,
    transactional_logger
)

__all__ = [
    # Interfaces
    'ITransactionManager',
    'IStateRepository',
    'IDualModeRepository',
    'IParameterValidator',
    'IFailureRecovery',
    'IUnitOfWork',
    'ITransactionalParameterLogger',

    # Data classes
    'ParameterData',
    'MachineState',
    'DualModeResult',
    'TransactionContext',

    # Implementations
    'AsyncTransactionManager',
    'AtomicStateRepository',
    'AtomicDualModeRepository',
    'TransactionalParameterLogger',

    # Global instances
    'transaction_manager',
    'state_repository',
    'dual_mode_repository',
    'transactional_logger'
]

# Version info
__version__ = "1.0.0"
__description__ = "Bulletproof transactional data access layer for dual-mode parameter logging"
__author__ = "ALD Control System Team"