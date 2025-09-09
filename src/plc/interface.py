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
    async def read_parameter(self, parameter_id: str) -> float:
        """
        Read a parameter value from the PLC.
        
        Args:
            parameter_id: The ID of the parameter to read
            
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