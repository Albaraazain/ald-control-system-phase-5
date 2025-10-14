# File: plc/manager.py
"""
Manager for PLC interface instances.

CRITICAL: This module implements a singleton pattern to ensure only ONE PLC connection
is created across all terminals/processes that import this module.

USAGE PATTERN (CORRECT):
    from src.plc.manager import plc_manager  # Import the global singleton instance
    await plc_manager.initialize()
    value = await plc_manager.read_parameter(param_id)

ANTI-PATTERN (INCORRECT):
    from src.plc.manager import PLCManager  # DO NOT import the class
    manager = PLCManager()  # This creates a new reference to the singleton, but still uses shared state

WHY SINGLETON:
- PLC hardware typically limits concurrent Modbus TCP connections (usually ~5)
- Multiple connections to the same PLC can cause resource conflicts
- Singleton ensures only 1 connection for read/write operations across all terminals

TERMINAL USAGE:
- Terminal 1 (PLC Data Service): Uses plc_manager for continuous data collection
- Terminal 2 (Recipe Service): Uses plc_manager for recipe execution
- Terminal 3 (Parameter Service): Uses plc_manager for parameter control
All terminals share the SAME connection instance via the singleton pattern.
"""
from typing import Dict, Any, Optional
from src.log_setup import get_plc_logger

logger = get_plc_logger()
from src.config import PLC_TYPE, PLC_CONFIG
from src.plc.interface import PLCInterface
from src.plc.factory import PLCFactory

class PLCManager:
    """
    Singleton manager for PLC interfaces.

    Thread-safe singleton implementation using __new__ method.
    Ensures only one PLC connection exists across all terminals.
    """

    _instance = None

    def __new__(cls):
        """
        Create or return the singleton instance.

        This method is called before __init__ and ensures only one instance exists.
        Thread-safe due to Python's GIL (Global Interpreter Lock).
        """
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
        
    async def read_parameter(self, parameter_id: str, skip_noise: bool = False) -> float:
        """
        Read a parameter value from the PLC.

        Args:
            parameter_id: The ID of the parameter to read
            skip_noise: If True, skip noise generation in simulation (confirmation reads)

        Returns:
            float: The current value of the parameter
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")

        value = await self._plc.read_parameter(parameter_id, skip_noise=skip_noise)
        logger.debug(f"PLC read parameter {parameter_id}: {value}")
        return value
        
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

        logger.info(f"PLC write parameter {parameter_id}: {value}")
        success = await self._plc.write_parameter(parameter_id, value)
        if success:
            logger.info(f"✅ PLC write successful: {parameter_id} = {value}")
        else:
            logger.error(f"❌ PLC write failed: {parameter_id} = {value}")
        return success
        
    async def read_all_parameters(self) -> Dict[str, float]:
        """
        Read all parameter values from the PLC.

        Returns:
            Dict[str, float]: Dictionary of parameter IDs to values
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")

        parameter_values = await self._plc.read_all_parameters()
        logger.debug(f"PLC read all parameters: {len(parameter_values)} values retrieved")
        return parameter_values
    
    async def read_setpoint(self, parameter_id: str) -> Optional[float]:
        """
        Read the setpoint value for a parameter from the PLC.
        
        This reads from write_modbus_address to detect external changes.
        
        Args:
            parameter_id: The ID of the parameter to read setpoint for
            
        Returns:
            Optional[float]: The setpoint value, or None if not writable
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        
        setpoint = await self._plc.read_setpoint(parameter_id)
        if setpoint is not None:
            logger.debug(f"PLC read setpoint {parameter_id}: {setpoint}")
        return setpoint
    
    async def read_all_setpoints(self) -> Dict[str, float]:
        """
        Read all setpoint values from the PLC.
        
        Returns:
            Dict[str, float]: Dictionary of parameter IDs to setpoint values
        """
        if self._plc is None:
            raise RuntimeError("Not connected to PLC")
        
        setpoint_values = await self._plc.read_all_setpoints()
        logger.debug(f"PLC read all setpoints: {len(setpoint_values)} values retrieved")
        return setpoint_values
        
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

# ============================================================================
# GLOBAL SINGLETON INSTANCE - USE THIS IN ALL TERMINALS
# ============================================================================
# This is the ONLY instance of PLCManager that should be used throughout the
# application. Import this instance in your code, NOT the PLCManager class.
#
# CORRECT USAGE:
#   from src.plc.manager import plc_manager
#   await plc_manager.initialize()
#   value = await plc_manager.read_parameter(param_id)
#
# TERMINAL CONNECTIONS:
#   Terminal 1 (plc_data_service.py): Uses plc_manager for continuous PLC reads
#   Terminal 2 (simple_recipe_service.py): Uses plc_manager for recipe execution
#   Terminal 3 (parameter_service.py): Uses plc_manager for parameter writes
#
# All terminals share this SINGLE connection to prevent multiple Modbus TCP
# connections and resource conflicts with the PLC hardware.
# ============================================================================
plc_manager = PLCManager()
