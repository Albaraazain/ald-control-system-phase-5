# File: plc/interface.py
"""
Defines the interface for PLC communication.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

class PLCInterface(ABC):
    """Abstract interface for PLC communication."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize connection to the PLC.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the PLC.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def read_parameter(self, parameter_id: str, skip_noise: bool = False) -> float:
        """
        Read a parameter value from the PLC.

        Args:
            parameter_id: The ID of the parameter to read
            skip_noise: If True, return exact value without synthetic noise (simulation only).

                       ⚠️ CRITICAL: Required for confirmation reads after writes in simulation.
                       Without this flag, simulation noise (±0.5-1.0 units) exceeds tolerance,
                       causing false failures. Real PLCs ignore this flag (no synthetic noise).

                       Use skip_noise=True for: Confirmation reads after parameter writes
                       Use skip_noise=False for: Normal data collection reads

        Returns:
            float: The current value of the parameter
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
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def read_all_parameters(self) -> Dict[str, float]:
        """
        Read all parameter values from the PLC.
        
        Returns:
            Dict[str, float]: Dictionary of parameter IDs to values
        """
        pass
    
    @abstractmethod
    async def read_setpoint(self, parameter_id: str) -> Optional[float]:
        """
        Read the setpoint value for a parameter from the PLC.
        
        This reads from the write_modbus_address to get the actual setpoint
        that is currently configured on the PLC. This is useful for detecting
        external changes made directly on the machine.
        
        Args:
            parameter_id: The ID of the parameter to read setpoint for
            
        Returns:
            Optional[float]: The setpoint value, or None if parameter is not writable
                           or setpoint cannot be read
        """
        pass
    
    @abstractmethod
    async def read_all_setpoints(self) -> Dict[str, float]:
        """
        Read all setpoint values from the PLC.
        
        This reads setpoints for all writable parameters by reading from their
        write_modbus_address. Used to synchronize database with external changes.
        
        Returns:
            Dict[str, float]: Dictionary of parameter IDs to setpoint values
                            (only includes writable parameters)
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
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def execute_purge(self, duration_ms: int) -> bool:
        """
        Execute a purge operation for the specified duration.
        
        Args:
            duration_ms: Duration of purge in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass