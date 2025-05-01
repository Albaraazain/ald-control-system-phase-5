# File: plc/manager.py
"""
Manager for PLC interface instances.
"""
from typing import Dict, Any, Optional
from log_setup import logger
from config import PLC_TYPE, PLC_CONFIG
from plc.interface import PLCInterface
from plc.factory import PLCFactory

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
    
    async def initialize(self, plc_type: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> PLCInterface:
        """
        Initialize the PLC interface.
        
        Args:
            plc_type: Type of PLC to use (defaults to config value)
            config: Configuration for the PLC (defaults to config value)
            
        Returns:
            PLCInterface: The initialized PLC interface
        """
        # Close existing connection if any
        await self.disconnect()
        
        # Use provided values or defaults from config
        plc_type = plc_type or PLC_TYPE
        config = config or PLC_CONFIG
        
        logger.info(f"Initializing PLC of type {plc_type}")
        self._plc = await PLCFactory.create_plc(plc_type, config)
        return self._plc
    
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

# Global instance
plc_manager = PLCManager()