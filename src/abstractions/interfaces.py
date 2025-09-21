# File: src/abstractions/interfaces.py
"""
Abstract interfaces for all external dependencies and services.
Enables dependency injection, testability, and loose coupling.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, AsyncContextManager
import asyncio
from enum import Enum

class ServiceHealth(Enum):
    """Service health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class IPLCInterface(ABC):
    """Abstract interface for PLC communication"""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Check if PLC is currently connected"""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize PLC connection.

        Returns:
            True if successfully initialized, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from PLC.

        Returns:
            True if successfully disconnected, False otherwise
        """
        pass

    @abstractmethod
    async def read_parameter(self, parameter_id: str) -> float:
        """
        Read a single parameter value from the PLC.

        Args:
            parameter_id: The ID of the parameter to read

        Returns:
            The current value of the parameter

        Raises:
            PLCConnectionError: If PLC is not connected
            PLCParameterError: If parameter_id is invalid
        """
        pass

    @abstractmethod
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        """
        Write a parameter value to the PLC.

        Args:
            parameter_id: The ID of the parameter to write
            value: The value to write

        Returns:
            True if successful, False otherwise

        Raises:
            PLCConnectionError: If PLC is not connected
            PLCParameterError: If parameter_id is invalid
        """
        pass

    @abstractmethod
    async def read_all_parameters(self) -> Dict[str, float]:
        """
        Read all parameter values from the PLC.

        Returns:
            Dictionary of parameter IDs to values

        Raises:
            PLCConnectionError: If PLC is not connected
        """
        pass

    @abstractmethod
    async def read_bulk_parameters(self, parameter_ids: List[str]) -> Dict[str, float]:
        """
        Read multiple parameters in a single operation for performance.

        Args:
            parameter_ids: List of parameter IDs to read

        Returns:
            Dictionary of parameter IDs to values

        Raises:
            PLCConnectionError: If PLC is not connected
        """
        pass

    @abstractmethod
    async def control_valve(self, valve_number: int, state: bool, duration_ms: Optional[int] = None) -> bool:
        """
        Control a valve state.

        Args:
            valve_number: The valve number to control
            state: True to open, False to close
            duration_ms: Optional duration to keep valve open in milliseconds

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def execute_purge(self, duration_ms: int) -> bool:
        """
        Execute a purge operation for the specified duration.

        Args:
            duration_ms: Duration of purge in milliseconds

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """
        Perform health check on PLC connection.

        Returns:
            Current health status
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """Clean up resources and disconnect"""
        pass

class IDatabaseService(ABC):
    """Abstract interface for database operations"""

    @abstractmethod
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a database query.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Query result

        Raises:
            DatabaseConnectionError: If database is not available
            DatabaseQueryError: If query execution fails
        """
        pass

    @abstractmethod
    async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> bool:
        """
        Execute a query with multiple parameter sets.

        Args:
            query: SQL query to execute
            params_list: List of parameter dictionaries

        Returns:
            True if successful, False otherwise

        Raises:
            DatabaseConnectionError: If database is not available
        """
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row from query result.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Single row as dictionary or None if not found
        """
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch all rows from query result.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            List of rows as dictionaries
        """
        pass

    @abstractmethod
    async def begin_transaction(self) -> 'ITransaction':
        """
        Begin a database transaction.

        Returns:
            Transaction context manager
        """
        pass

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """
        Perform health check on database connection.

        Returns:
            Current health status
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """Clean up database connections and resources"""
        pass

class ITransaction(ABC):
    """Abstract interface for database transactions"""

    @abstractmethod
    async def commit(self) -> bool:
        """
        Commit the transaction.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def rollback(self) -> bool:
        """
        Roll back the transaction.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a query within the transaction.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Query result
        """
        pass

    @abstractmethod
    async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> bool:
        """
        Execute multiple queries within the transaction.

        Args:
            query: SQL query to execute
            params_list: List of parameter dictionaries

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def __aenter__(self) -> 'ITransaction':
        """Async context manager entry"""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Async context manager exit with automatic commit/rollback"""
        pass

class IParameterLogger(ABC):
    """Abstract interface for parameter logging services"""

    @abstractmethod
    async def start(self) -> bool:
        """
        Start the parameter logging service.

        Returns:
            True if started successfully, False otherwise
        """
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop the parameter logging service.

        Returns:
            True if stopped successfully, False otherwise
        """
        pass

    @abstractmethod
    async def log_parameters(
        self,
        parameters: Dict[str, float],
        process_id: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Log parameter values.

        Args:
            parameters: Dictionary of parameter IDs to values
            process_id: Optional process ID for process-specific logging
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            True if logged successfully, False otherwise
        """
        pass

    @abstractmethod
    async def log_dual_mode(
        self,
        parameters: Dict[str, float],
        process_id: Optional[str] = None,
        machine_status: Optional[str] = None
    ) -> bool:
        """
        Log parameters in dual-mode (both parameter_value_history and process_data_points).

        Args:
            parameters: Dictionary of parameter IDs to values
            process_id: Optional process ID
            machine_status: Optional machine status

        Returns:
            True if logged successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the parameter logger.

        Returns:
            Status information dictionary
        """
        pass

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """
        Perform health check on parameter logging service.

        Returns:
            Current health status
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """Clean up resources and stop logging"""
        pass

class IEventBus(ABC):
    """Abstract interface for event-driven communication"""

    @abstractmethod
    async def publish(self, event_type: str, data: Dict[str, Any], source: Optional[str] = None) -> bool:
        """
        Publish an event to the bus.

        Args:
            event_type: Type of event being published
            data: Event data payload
            source: Optional source identifier

        Returns:
            True if published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> str:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of events to subscribe to
            handler: Async function to handle events

        Returns:
            Subscription ID for later unsubscribing
        """
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.

        Args:
            subscription_id: Subscription ID from subscribe()

        Returns:
            True if unsubscribed successfully, False otherwise
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """Clean up event bus resources"""
        pass

class IConfigurationService(ABC):
    """Abstract interface for configuration management"""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        pass

    @abstractmethod
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get all configuration values for a section.

        Args:
            section: Configuration section name

        Returns:
            Dictionary of configuration values
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        pass

    @abstractmethod
    async def reload(self) -> bool:
        """
        Reload configuration from source.

        Returns:
            True if reloaded successfully, False otherwise
        """
        pass

class IStateManager(ABC):
    """Abstract interface for state management"""

    @abstractmethod
    async def get_machine_state(self) -> Dict[str, Any]:
        """
        Get current machine state.

        Returns:
            Machine state dictionary
        """
        pass

    @abstractmethod
    async def set_machine_state(self, state: Dict[str, Any]) -> bool:
        """
        Set machine state atomically.

        Args:
            state: New machine state

        Returns:
            True if set successfully, False otherwise
        """
        pass

    @abstractmethod
    async def transition_state(self, from_state: str, to_state: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Perform atomic state transition.

        Args:
            from_state: Expected current state
            to_state: Target state
            context: Optional transition context

        Returns:
            True if transition successful, False otherwise
        """
        pass

    @abstractmethod
    async def watch_state_changes(self, callback: Callable[[Dict[str, Any]], None]) -> str:
        """
        Watch for state changes.

        Args:
            callback: Function to call on state changes

        Returns:
            Watcher ID for later removal
        """
        pass

class IConnectionMonitor(ABC):
    """Abstract interface for connection monitoring"""

    @abstractmethod
    async def monitor_plc_connection(self) -> bool:
        """
        Monitor PLC connection status.

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    async def monitor_database_connection(self) -> bool:
        """
        Monitor database connection status.

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get overall connection status.

        Returns:
            Connection status dictionary
        """
        pass

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """
        Perform health check on all monitored connections.

        Returns:
            Overall health status
        """
        pass

# Exception classes for service interfaces
class ServiceError(Exception):
    """Base class for service errors"""
    pass

class PLCConnectionError(ServiceError):
    """Raised when PLC connection issues occur"""
    pass

class PLCParameterError(ServiceError):
    """Raised when PLC parameter operations fail"""
    pass

class DatabaseConnectionError(ServiceError):
    """Raised when database connection issues occur"""
    pass

class DatabaseQueryError(ServiceError):
    """Raised when database query execution fails"""
    pass

class ConfigurationError(ServiceError):
    """Raised when configuration issues occur"""
    pass

class StateTransitionError(ServiceError):
    """Raised when state transition failures occur"""
    pass