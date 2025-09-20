# File: plc/manager.py
"""
Manager for PLC interface instances.
"""
from typing import Dict, Any, Optional
from src.log_setup import logger
from src.config import PLC_TYPE, PLC_CONFIG
from src.plc.interface import PLCInterface
from src.plc.factory import PLCFactory

class PLCManager:
    """Singleton manager for PLC interfaces."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PLCManager, cls).__new__(cls)
            cls._instance._plc = None
        return cls._instance
    
    def __init__(self):
        # Only initialize if not already initialized
        if not hasattr(self, '_plc'):
            self._plc = None
    
    @property
    def plc(self) -> Optional[PLCInterface]:
        """Get the current PLC interface."""
        return self._plc
    
    async def initialize(self, plc_type: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize the PLC interface.
        
        Args:
            plc_type: Type of PLC to use (defaults to config value)
            config: Configuration for the PLC (defaults to config value)
            
        Returns:
            bool: True if successfully initialized, False otherwise
        """
        # Close existing connection if any
        await self.disconnect()
        
        # Use provided values or defaults from config
        plc_type = plc_type or PLC_TYPE
        config = config or PLC_CONFIG
        
        logger.info(f"Initializing PLC of type {plc_type}")
        try:
            self._plc = await PLCFactory.create_plc(plc_type, config)

            # If factory returned an already-initialized/connected instance, skip re-init
            if self._plc and getattr(self._plc, 'connected', False):
                return True

            # Otherwise, initialize the PLC connection
            if self._plc:
                success = await self._plc.initialize()
                return success
            return False
        except Exception as e:
            logger.error(f"Error initializing PLC: {str(e)}", exc_info=True)
            return False
    
    async def disconnect(self) -> bool:
        """
        Disconnect the current PLC interface if connected.
        
        Returns:
            bool: True if disconnected successfully, False otherwise
        """
        if self._plc is not None:
            try:
                success = await self._plc.disconnect()
                if success:
                    self._plc = None
                return success
            except Exception as e:
                logger.error(f"Error disconnecting PLC: {str(e)}", exc_info=True)
                return False
        return True
        
    def is_connected(self) -> bool:
        """
        Check if the PLC is currently connected.
        
        Returns:
            bool: True if PLC is connected, False otherwise
        """
        return self._plc is not None and getattr(self._plc, 'connected', False)
        
    async def read_parameter(self, parameter_id: str) -> float:
        """
        Read a parameter value from the PLC.
        
        Args:
            parameter_id: The ID of the parameter to read
            
        Returns:
            float: The current value of the parameter
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        return await self._plc.read_parameter(parameter_id)
        
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        """
        Write a parameter value to the PLC.
        
        Args:
            parameter_id: The ID of the parameter to write
            value: The value to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        return await self._plc.write_parameter(parameter_id, value)
        
    async def read_all_parameters(self) -> Dict[str, float]:
        """
        Read all parameter values from the PLC.
        
        Returns:
            Dict[str, float]: Dictionary of parameter IDs to values
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        return await self._plc.read_all_parameters()
        
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
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        return await self._plc.control_valve(valve_number, state, duration_ms)
        
    async def execute_purge(self, duration_ms: int) -> bool:
        """
        Execute a purge operation for the specified duration.
        
        Args:
            duration_ms: Duration of purge in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        return await self._plc.execute_purge(duration_ms)

# Global instance
plc_manager = PLCManager()
