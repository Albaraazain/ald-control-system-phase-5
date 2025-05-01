# File: plc/real_plc.py (updated)
"""
Real hardware implementation of the PLC interface.
"""
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from log_setup import logger
from plc.interface import PLCInterface
from plc.communicator import PLCCommunicator
from db import get_supabase

class RealPLC(PLCInterface):
    """Real PLC implementation for production use."""
    
    # Data type mapping
    DATA_TYPES = {
        'float': 'float',
        'int32': 'int32',
        'int16': 'int16',
        'binary': 'binary'
    }
    
    def __init__(self, ip_address: str, port: int):
        """
        Initialize with PLC connection details.
        
        Args:
            ip_address: IP address of the PLC
            port: Port number for PLC communication
        """
        self.ip_address = ip_address
        self.port = port
        self.connected = False
        self.communicator = PLCCommunicator(plc_ip=ip_address, port=port)
        
        # Cache for parameter metadata
        self._parameter_cache = {}
        
        # Cache for valve mappings
        self._valve_cache = {}
        
        # Purge operation parameters
        self._purge_address = None
        self._purge_data_type = None
    
    async def initialize(self) -> bool:
        """Initialize connection to the real PLC."""
        logger.info(f"Connecting to real PLC at {self.ip_address}:{self.port}")
        
        try:
            # Connect to the PLC using the communicator
            success = self.communicator.connect()
            
            if success:
                self.connected = True
                logger.info("Successfully connected to PLC")
                
                # Load parameter metadata from database
                await self._load_parameter_metadata()
                
                # Load valve mappings
                await self._load_valve_mappings()
                
                # Load purge operation parameters
                await self._load_purge_parameters()
                
                return True
            else:
                logger.error("Failed to connect to PLC")
                return False
            
        except Exception as e:
            logger.error(f"Failed to connect to PLC: {str(e)}", exc_info=True)
            self.connected = False
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from the real PLC."""
        logger.info("Disconnecting from PLC")
        
        if not self.connected:
            return True
            
        try:
            success = self.communicator.disconnect()
            if success:
                self.connected = False
                logger.info("Successfully disconnected from PLC")
            return success
            
        except Exception as e:
            logger.error(f"Error disconnecting from PLC: {str(e)}", exc_info=True)
            return False
    
    async def _load_parameter_metadata(self):
        """
        Load parameter metadata from the database.
        This includes Modbus addresses, data types, etc.
        """
        try:
            supabase = get_supabase()
            
            # Query all parameters with Modbus information
            result = supabase.table('component_parameters').select('*').not_is('modbus_address', None).execute()
            
            if result.data:
                for param in result.data:
                    parameter_id = param['id']
                    self._parameter_cache[parameter_id] = {
                        'name': param['name'],
                        'modbus_address': param['modbus_address'],
                        'modbus_type': param['modbus_type'],
                        'data_type': param['data_type'],
                        'min_value': param['min_value'],
                        'max_value': param['max_value'],
                        'is_writable': param['is_writable']
                    }
                    
                logger.info(f"Loaded metadata for {len(self._parameter_cache)} parameters")
            else:
                logger.warning("No parameters with Modbus addresses found in database")
                
        except Exception as e:
            logger.error(f"Error loading parameter metadata: {str(e)}", exc_info=True)
    
    async def _load_valve_mappings(self):
        """
        Load valve mappings from the database.
        Valves are treated as components with a specific parameter for valve state.
        """
        try:
            supabase = get_supabase()
            
            # Query parameters that represent valve states (by convention or property)
            # Assuming valve parameters have names containing "valve" and are binary type
            query = supabase.table('component_parameters').select('*') \
                .like('name', '%valve%') \
                .eq('data_type', 'binary') \
                .execute()
            
            if query.data:
                for valve_param in query.data:
                    # Extract valve number from name (assuming naming convention includes number)
                    name = valve_param['name'].lower()
                    try:
                        # Try to extract valve number from parameter name (e.g., "Valve 1 state" -> 1)
                        # This logic may need to be adjusted based on your naming convention
                        import re
                        match = re.search(r'valve\s*(\d+)', name)
                        if match:
                            valve_number = int(match.group(1))
                            
                            self._valve_cache[valve_number] = {
                                'parameter_id': valve_param['id'],
                                'modbus_address': valve_param['modbus_address'],
                                'modbus_type': valve_param['modbus_type']
                            }
                    except (ValueError, AttributeError):
                        logger.warning(f"Could not extract valve number from parameter: {name}")
                
                logger.info(f"Loaded mappings for {len(self._valve_cache)} valves")
            else:
                logger.warning("No valve parameters found")
                
        except Exception as e:
            logger.error(f"Error loading valve mappings: {str(e)}", exc_info=True)
    
    async def _load_purge_parameters(self):
        """
        Load purge operation parameters from the database.
        """
        try:
            supabase = get_supabase()
            
            # Query parameter for purge operation (by convention)
            # Assuming purge operation has a dedicated parameter
            query = supabase.table('component_parameters').select('*') \
                .like('name', '%purge%') \
                .execute()
            
            if query.data:
                purge_param = query.data[0]  # Use the first matching parameter
                
                self._purge_address = purge_param['modbus_address']
                self._purge_data_type = purge_param['data_type']
                
                logger.info(f"Loaded purge operation parameter: address {self._purge_address}")
            else:
                logger.warning("No purge operation parameter found")
                
        except Exception as e:
            logger.error(f"Error loading purge parameters: {str(e)}", exc_info=True)
    
    async def read_parameter(self, parameter_id: str) -> float:
        """
        Read a parameter value from the PLC.
        
        Args:
            parameter_id: The ID of the parameter to read
            
        Returns:
            float: The current value of the parameter
        """
        if not self.connected:
            raise RuntimeError("Not connected to PLC")
        
        # Get parameter metadata from cache
        param_meta = self._parameter_cache.get(parameter_id)
        if not param_meta:
            raise ValueError(f"Parameter {parameter_id} not found in metadata cache")
        
        address = param_meta['modbus_address']
        data_type = param_meta['data_type']
        
        # Read the parameter based on its data type
        if data_type == 'float':
            value = self.communicator.read_float(address)
        elif data_type == 'int32':
            value = self.communicator.read_integer_32bit(address)
        elif data_type == 'int16':
            # Read holding register as 16-bit integer
            result = self.communicator.client.read_holding_registers(address, count=1, slave=self.communicator.slave_id)
            if result.isError():
                logger.error(f"Failed to read int16: {result}")
                return None
            value = result.registers[0]
        elif data_type == 'binary':
            # Read as coil
            result = self.communicator.read_coils(address, count=1)
            if result is None:
                return None
            value = 1.0 if result[0] else 0.0
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        if value is None:
            return None
            
        # Update database with current value (in background task)
        asyncio.create_task(self._update_parameter_value(parameter_id, value))
        
        return float(value)
    
    async def _update_parameter_value(self, parameter_id: str, value: float):
        """Update the current value of a parameter in the database."""
        try:
            supabase = get_supabase()
            
            supabase.table('component_parameters').update({
                'current_value': value,
                'updated_at': 'now()'
            }).eq('id', parameter_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating parameter value in database: {str(e)}")
    
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        """
        Write a parameter value to the PLC.
        
        Args:
            parameter_id: The ID of the parameter to write
            value: The value to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected:
            raise RuntimeError("Not connected to PLC")
        
        # Get parameter metadata from cache
        param_meta = self._parameter_cache.get(parameter_id)
        if not param_meta:
            raise ValueError(f"Parameter {parameter_id} not found in metadata cache")
        
        # Check if parameter is writable
        if not param_meta.get('is_writable', False):
            raise ValueError(f"Parameter {parameter_id} is not writable")
        
        # Check value against min/max
        min_value = param_meta['min_value']
        max_value = param_meta['max_value']
        
        if value < min_value or value > max_value:
            raise ValueError(f"Value {value} is outside allowed range ({min_value} to {max_value})")
        
        address = param_meta['modbus_address']
        data_type = param_meta['data_type']
        
        # Write the parameter based on its data type
        if data_type == 'float':
            success = self.communicator.write_float(address, value)
        elif data_type == 'int32':
            success = self.communicator.write_integer_32bit(address, int(value))
        elif data_type == 'int16':
            # Write holding register as 16-bit integer
            result = self.communicator.client.write_register(address, int(value), slave=self.communicator.slave_id)
            success = not result.isError()
        elif data_type == 'binary':
            # Write as coil (True if value > 0)
            success = self.communicator.write_coil(address, value > 0)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        if success:
            # Update database with new set value (in background task)
            asyncio.create_task(self._update_parameter_set_value(parameter_id, value))
            
        return success
    
    async def _update_parameter_set_value(self, parameter_id: str, value: float):
        """Update the set value of a parameter in the database."""
        try:
            supabase = get_supabase()
            
            supabase.table('component_parameters').update({
                'set_value': value,
                'updated_at': 'now()'
            }).eq('id', parameter_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating parameter set value in database: {str(e)}")
    
    async def read_all_parameters(self) -> Dict[str, float]:
        """
        Read all parameter values from the PLC.
        
        Returns:
            Dict[str, float]: Dictionary of parameter IDs to values
        """
        if not self.connected:
            raise RuntimeError("Not connected to PLC")
        
        result = {}
        
        for parameter_id in self._parameter_cache:
            try:
                value = await self.read_parameter(parameter_id)
                if value is not None:
                    result[parameter_id] = value
            except Exception as e:
                logger.error(f"Error reading parameter {parameter_id}: {str(e)}")
        
        return result
    
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
        if not self.connected:
            raise RuntimeError("Not connected to PLC")
        
        # Get valve metadata from cache
        valve_meta = self._valve_cache.get(valve_number)
        if not valve_meta:
            raise ValueError(f"Valve {valve_number} not found in valve cache")
        
        address = valve_meta['modbus_address']
        
        logger.info(f"{'Opening' if state else 'Closing'} valve {valve_number} at address {address}")
        
        # Write to the valve coil
        success = self.communicator.write_coil(address, state)
        
        if not success:
            logger.error(f"Failed to {'open' if state else 'close'} valve {valve_number}")
            return False
        
        # If duration specified, schedule valve to close after duration
        if state and duration_ms is not None and duration_ms > 0:
            # Create a background task to close the valve after the specified duration
            asyncio.create_task(self._auto_close_valve(valve_number, address, duration_ms))
        
        return True
    
    async def _auto_close_valve(self, valve_number: int, address: int, duration_ms: int):
        """
        Automatically close a valve after a specified duration.
        
        Args:
            valve_number: The valve number
            address: The Modbus address of the valve
            duration_ms: Duration in milliseconds to wait before closing
        """
        try:
            # Wait for the specified duration
            await asyncio.sleep(duration_ms / 1000)
            
            # Check if we're still connected
            if not self.connected:
                logger.warning(f"Not closing valve {valve_number} after timeout: Not connected to PLC")
                return
            
            # Close the valve
            logger.info(f"Auto-closing valve {valve_number} after {duration_ms}ms")
            success = self.communicator.write_coil(address, False)
            
            if not success:
                logger.error(f"Failed to auto-close valve {valve_number}")
            
        except Exception as e:
            logger.error(f"Error in auto-close valve task: {str(e)}")
    
    async def execute_purge(self, duration_ms: int) -> bool:
        """
        Execute a purge operation for the specified duration.
        
        Args:
            duration_ms: Duration of purge in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected:
            raise RuntimeError("Not connected to PLC")
        
        # Check if purge parameters are available
        if self._purge_address is None:
            raise ValueError("Purge operation parameters not found")
        
        logger.info(f"Starting purge operation for {duration_ms}ms")
        
        # Activate purge operation
        if self._purge_data_type == 'binary':
            # Trigger purge by setting coil
            success = self.communicator.write_coil(self._purge_address, True)
        else:
            # Trigger purge by writing 1 to register
            success = self.communicator.write_integer_32bit(self._purge_address, 1)
        
        if not success:
            logger.error("Failed to start purge operation")
            return False
        
        # Create a background task to complete the purge
        asyncio.create_task(self._complete_purge(duration_ms))
        
        return True
    
    async def _complete_purge(self, duration_ms: int):
        """
        Complete a purge operation after the specified duration.
        
        Args:
            duration_ms: Duration of purge in milliseconds
        """
        try:
            # Wait for the specified duration
            await asyncio.sleep(duration_ms / 1000)
            
            # Check if we're still connected
            if not self.connected:
                logger.warning("Not completing purge operation: Not connected to PLC")
                return
            
            # End purge operation
            logger.info(f"Completing purge operation after {duration_ms}ms")
            
            if self._purge_data_type == 'binary':
                # End purge by clearing coil
                success = self.communicator.write_coil(self._purge_address, False)
            else:
                # End purge by writing 0 to register
                success = self.communicator.write_integer_32bit(self._purge_address, 0)
            
            if not success:
                logger.error("Failed to complete purge operation")
            
        except Exception as e:
            logger.error(f"Error in complete purge task: {str(e)}")