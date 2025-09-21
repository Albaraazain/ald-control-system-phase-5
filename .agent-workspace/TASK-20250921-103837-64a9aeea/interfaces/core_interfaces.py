# File: src/application/interfaces/core_interfaces.py
"""
Core interface abstractions for ALD Control System v2.0
Provides interface-based service abstractions for dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncContextManager
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Domain Value Objects and DTOs
# =============================================================================

@dataclass(frozen=True)
class ParameterReading:
    """Value object for parameter readings"""
    parameter_id: str
    value: float
    timestamp: datetime
    quality: str = "good"
    process_id: Optional[str] = None

@dataclass(frozen=True)
class MachineState:
    """Value object for machine state"""
    machine_id: str
    status: str  # idle, processing, error, maintenance
    current_process_id: Optional[str]
    last_updated: datetime

@dataclass(frozen=True)
class ProcessInfo:
    """Value object for process information"""
    process_id: str
    recipe_id: str
    machine_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None

class LoggingMode(Enum):
    """Logging mode enumeration"""
    IDLE = "idle"
    PROCESS = "process"

# =============================================================================
# PLC Interface Abstractions
# =============================================================================

class IPLCInterface(ABC):
    """Abstract interface for PLC communication"""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize PLC connection"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from PLC"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if PLC is connected"""
        pass

    @abstractmethod
    async def read_parameter(self, parameter_id: str) -> float:
        """Read single parameter value"""
        pass

    @abstractmethod
    async def read_parameters_bulk(self, parameter_ids: List[str]) -> Dict[str, float]:
        """Read multiple parameters in bulk operation"""
        pass

    @abstractmethod
    async def read_all_parameters(self) -> Dict[str, float]:
        """Read all configured parameters"""
        pass

    @abstractmethod
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        """Write parameter value"""
        pass

    @abstractmethod
    async def control_valve(self, valve_number: int, state: bool,
                          duration_ms: Optional[int] = None) -> bool:
        """Control valve state"""
        pass

    @abstractmethod
    async def execute_purge(self, duration_ms: int) -> bool:
        """Execute purge operation"""
        pass

class IPLCFactory(ABC):
    """Abstract factory for creating PLC interfaces"""

    @abstractmethod
    async def create_plc(self, plc_type: str, config: Dict[str, Any]) -> IPLCInterface:
        """Create PLC interface instance"""
        pass

# =============================================================================
# Data Repository Interfaces
# =============================================================================

class IParameterRepository(ABC):
    """Abstract interface for parameter data access"""

    @abstractmethod
    async def insert_parameter_reading(self, reading: ParameterReading) -> bool:
        """Insert single parameter reading"""
        pass

    @abstractmethod
    async def insert_parameter_readings_bulk(self, readings: List[ParameterReading]) -> bool:
        """Insert multiple parameter readings in transaction"""
        pass

    @abstractmethod
    async def insert_dual_mode_readings(self, readings: List[ParameterReading],
                                      mode: LoggingMode, process_id: Optional[str] = None) -> bool:
        """Insert readings with dual-mode logic (idle/process tables)"""
        pass

    @abstractmethod
    async def get_parameter_readings(self, parameter_id: str,
                                   start_time: datetime, end_time: datetime) -> List[ParameterReading]:
        """Get parameter readings for time range"""
        pass

    @abstractmethod
    async def get_process_parameters(self, process_id: str) -> List[ParameterReading]:
        """Get all parameter readings for a process"""
        pass

class IProcessRepository(ABC):
    """Abstract interface for process data access"""

    @abstractmethod
    async def create_process(self, process_info: ProcessInfo) -> bool:
        """Create new process record"""
        pass

    @abstractmethod
    async def update_process_status(self, process_id: str, status: str) -> bool:
        """Update process status"""
        pass

    @abstractmethod
    async def get_process(self, process_id: str) -> Optional[ProcessInfo]:
        """Get process information"""
        pass

    @abstractmethod
    async def get_current_process(self, machine_id: str) -> Optional[ProcessInfo]:
        """Get current running process for machine"""
        pass

class IMachineRepository(ABC):
    """Abstract interface for machine data access"""

    @abstractmethod
    async def get_machine_state(self, machine_id: str) -> Optional[MachineState]:
        """Get current machine state"""
        pass

    @abstractmethod
    async def update_machine_state(self, machine_state: MachineState) -> bool:
        """Update machine state atomically"""
        pass

    @abstractmethod
    async def set_machine_process(self, machine_id: str, process_id: Optional[str]) -> bool:
        """Set current process for machine"""
        pass

# =============================================================================
# Transaction Management
# =============================================================================

class IUnitOfWork(ABC):
    """Abstract unit of work for transaction management"""

    @abstractmethod
    async def __aenter__(self) -> 'IUnitOfWork':
        """Enter transaction context"""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit transaction context with commit/rollback"""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit transaction"""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback transaction"""
        pass

    @property
    @abstractmethod
    def parameter_repository(self) -> IParameterRepository:
        """Get parameter repository for this transaction"""
        pass

    @property
    @abstractmethod
    def process_repository(self) -> IProcessRepository:
        """Get process repository for this transaction"""
        pass

    @property
    @abstractmethod
    def machine_repository(self) -> IMachineRepository:
        """Get machine repository for this transaction"""
        pass

class ITransactionManager(ABC):
    """Abstract transaction manager"""

    @abstractmethod
    def begin_transaction(self) -> IUnitOfWork:
        """Begin new transaction"""
        pass

# =============================================================================
# Data Collection Service Interfaces
# =============================================================================

class IParameterLogger(ABC):
    """Abstract interface for parameter logging service"""

    @abstractmethod
    async def start(self) -> None:
        """Start parameter logging"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop parameter logging"""
        pass

    @abstractmethod
    async def is_running(self) -> bool:
        """Check if logging is running"""
        pass

    @abstractmethod
    async def log_parameters_once(self) -> int:
        """Log parameters once and return count"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get logger status"""
        pass

class IDataCollectionService(ABC):
    """Abstract interface for data collection service orchestration"""

    @abstractmethod
    async def start(self) -> None:
        """Start all data collection services"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop all data collection services"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get overall service status"""
        pass

# =============================================================================
# State Management Interfaces
# =============================================================================

class IStateManager(ABC):
    """Abstract interface for machine state management"""

    @abstractmethod
    async def get_current_state(self, machine_id: str) -> Optional[MachineState]:
        """Get current machine state"""
        pass

    @abstractmethod
    async def transition_to_processing(self, machine_id: str, process_id: str) -> bool:
        """Transition machine to processing state"""
        pass

    @abstractmethod
    async def transition_to_idle(self, machine_id: str) -> bool:
        """Transition machine to idle state"""
        pass

    @abstractmethod
    async def get_logging_mode(self, machine_id: str) -> LoggingMode:
        """Get current logging mode for machine"""
        pass

# =============================================================================
# Event System Interfaces
# =============================================================================

class IDomainEvent(ABC):
    """Abstract domain event"""

    @property
    @abstractmethod
    def event_id(self) -> str:
        """Unique event identifier"""
        pass

    @property
    @abstractmethod
    def timestamp(self) -> datetime:
        """Event timestamp"""
        pass

    @property
    @abstractmethod
    def aggregate_id(self) -> str:
        """Aggregate identifier"""
        pass

class IEventHandler(ABC):
    """Abstract event handler"""

    @abstractmethod
    async def handle(self, event: IDomainEvent) -> None:
        """Handle domain event"""
        pass

class IEventBus(ABC):
    """Abstract event bus for publish/subscribe"""

    @abstractmethod
    def subscribe(self, event_type: type, handler: IEventHandler) -> None:
        """Subscribe to event type"""
        pass

    @abstractmethod
    async def publish(self, event: IDomainEvent) -> None:
        """Publish event to subscribers"""
        pass

    @abstractmethod
    def get_events(self, aggregate_id: Optional[str] = None) -> List[IDomainEvent]:
        """Get events from store"""
        pass

# =============================================================================
# Cache and Performance Interfaces
# =============================================================================

class ICacheService(ABC):
    """Abstract cache service"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cached value with optional TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete cached value"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached values"""
        pass

class IConnectionPool(ABC):
    """Abstract database connection pool"""

    @abstractmethod
    async def acquire(self) -> AsyncContextManager[Any]:
        """Acquire connection from pool"""
        pass

    @abstractmethod
    async def execute(self, query: str, *args) -> Any:
        """Execute query with connection from pool"""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        pass

# =============================================================================
# Configuration Interfaces
# =============================================================================

class IConfigurationService(ABC):
    """Abstract configuration service"""

    @abstractmethod
    def get_string(self, key: str, default: Optional[str] = None) -> str:
        """Get string configuration value"""
        pass

    @abstractmethod
    def get_int(self, key: str, default: Optional[int] = None) -> int:
        """Get integer configuration value"""
        pass

    @abstractmethod
    def get_float(self, key: str, default: Optional[float] = None) -> float:
        """Get float configuration value"""
        pass

    @abstractmethod
    def get_bool(self, key: str, default: Optional[bool] = None) -> bool:
        """Get boolean configuration value"""
        pass

    @abstractmethod
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get configuration section"""
        pass

# =============================================================================
# Security Interfaces
# =============================================================================

class ICredentialManager(ABC):
    """Abstract credential management"""

    @abstractmethod
    async def get_credential(self, key: str) -> Optional[str]:
        """Get secure credential"""
        pass

    @abstractmethod
    async def set_credential(self, key: str, value: str) -> None:
        """Set secure credential"""
        pass

    @abstractmethod
    async def rotate_credential(self, key: str) -> str:
        """Rotate credential and return new value"""
        pass

class IInputValidator(ABC):
    """Abstract input validation"""

    @abstractmethod
    def validate_parameter_value(self, parameter_id: str, value: float) -> bool:
        """Validate parameter value"""
        pass

    @abstractmethod
    def validate_json_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate JSON against schema"""
        pass

    @abstractmethod
    def sanitize_input(self, value: str) -> str:
        """Sanitize string input"""
        pass

# =============================================================================
# Monitoring and Health Interfaces
# =============================================================================

class IHealthCheck(ABC):
    """Abstract health check"""

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Perform health check"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Health check name"""
        pass

class IMetricsCollector(ABC):
    """Abstract metrics collection"""

    @abstractmethod
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment counter metric"""
        pass

    @abstractmethod
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set gauge metric"""
        pass

    @abstractmethod
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram value"""
        pass

# =============================================================================
# Circuit Breaker Interface
# =============================================================================

class ICircuitBreaker(ABC):
    """Abstract circuit breaker for resilience"""

    @abstractmethod
    async def call(self, func, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        pass

    @property
    @abstractmethod
    def state(self) -> str:
        """Current circuit breaker state (open/closed/half-open)"""
        pass

    @property
    @abstractmethod
    def failure_count(self) -> int:
        """Current failure count"""
        pass