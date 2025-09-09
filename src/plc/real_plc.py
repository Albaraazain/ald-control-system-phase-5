# File: plc/real_plc.py (updated)
"""
Real hardware implementation of the PLC interface.
"""
import asyncio
import re
from typing import Dict, Optional, List, Tuple, Any
from src.log_setup import logger
from src.plc.interface import PLCInterface
from src.plc.communicator import PLCCommunicator
from src.db import get_supabase

class RealPLC(PLCInterface):
    """Real PLC implementation for production use."""
    
    # Data type mapping
    DATA_TYPES = {
        'float': 'float',
        'int32': 'int32',
        'int16': 'int16',
        'binary': 'binary'
    }
    
    # Modbus type mapping
    MODBUS_TYPES = {
        'holding_register': 'holding',
        'input_register': 'input',
        'coil': 'coil',
        'discrete_input': 'discrete_input'
    }
    
    def __init__(self, ip_address: str, port: int, hostname: str = None, auto_discover: bool = False):
        """
        Initialize with PLC connection details.
        
        Args:
            ip_address: IP address of the PLC (fallback if hostname/discovery fails)
            port: Port number for PLC communication
            hostname: Optional hostname for dynamic resolution (e.g., 'plc.local')
            auto_discover: Enable automatic network discovery for DHCP environments
        """
        self.ip_address = ip_address
        self.hostname = hostname
        self.port = port
        self.auto_discover = auto_discover
        self.connected = False
        
        # Create communicator with dynamic discovery capabilities
        self.communicator = PLCCommunicator(
            plc_ip=ip_address, 
            port=port,
            hostname=hostname,
            auto_discover=auto_discover,
            connection_timeout=10,
            retries=3
        )
        
        # Cache for parameter metadata
        self._parameter_cache = {}
        
        # Cache for valve mappings
        self._valve_cache = {}
        
        # Purge operation parameters
        self._purge_address = None
        self._purge_data_type = None
        
        # MFC voltage scaling parameters
        self._mfc_scaling_cache = {}
        
        # Pressure gauge voltage scaling parameters
        self._pressure_scaling_cache = {}
    
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
                
                # Load MFC and pressure gauge scaling parameters
                await self._load_scaling_parameters()
                
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
            # Join with component_parameter_definitions to get name, unit, description
            result = supabase.table('component_parameters').select(
                '*, component_parameter_definitions!definition_id(name, unit, description)'
            ).execute()
            
            # Filter out entries where modbus_address is None manually
            result.data = [param for param in result.data if param.get('modbus_address') is not None]
            logger.info(f"Found {len(result.data)} parameters with Modbus addresses")
            
            if result.data:
                for param in result.data:
                    parameter_id = param['id']
                    # Determine the modbus_type based on data_type if not specified
                    modbus_type = param.get('modbus_type')
                    if not modbus_type:
                        # Set default modbus_type based on data_type
                        if param.get('data_type') == 'binary':
                            modbus_type = 'coil'
                        elif param.get('data_type') in ['float', 'int32', 'int16']:
                            modbus_type = 'holding'
                        else:
                            modbus_type = 'unknown'
                    else:
                        # Map database modbus_type to internal representation
                        modbus_type = self.MODBUS_TYPES.get(modbus_type, modbus_type)
                    
                    # Get component name and truncate if needed to avoid log overflow
                    component_name = param.get('component_name', '')
                    if component_name and len(component_name) > 30:
                        short_component_name = component_name[:27] + "..."
                    else:
                        short_component_name = component_name
                    
                    # Get name, unit, and description from definition if available
                    definition = param.get('component_parameter_definitions', {})
                    param_name = definition.get('name') if definition else param.get('name')
                    param_unit = definition.get('unit') if definition else None
                    param_description = definition.get('description') if definition else None
                    
                    self._parameter_cache[parameter_id] = {
                        'name': param_name or param['name'],
                        'modbus_address': param['modbus_address'],
                        'modbus_type': modbus_type,
                        'data_type': param['data_type'],
                        'min_value': param['min_value'],
                        'max_value': param['max_value'],
                        'is_writable': param['is_writable'],
                        'component_name': component_name,
                        'short_component_name': short_component_name,
                        'current_value': param.get('current_value'),
                        'unit': param_unit,
                        'description': param_description
                    }
                    # Log each parameter with its Modbus address and type (using short component name)
                    logger.info(f"Parameter '{param_name or param['name']}' ({short_component_name}) (ID: {parameter_id}) has Modbus address: {param['modbus_address']}, "
                               f"data_type: {param['data_type']}, modbus_type: {modbus_type}")
                    
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
            
            # Query all parameters with definition information
            query = supabase.table('component_parameters').select(
                '*, component_parameter_definitions!definition_id(name, unit, description)'
            ).execute()
            
            # Manually filter for valve parameters by checking:
            # 1. name is 'valve_state' (or definition name is 'valve_state')
            # 2. component_name starts with 'Valve'
            valve_params = []
            for param in query.data:
                # Check both the parameter name and the definition name
                definition = param.get('component_parameter_definitions', {})
                param_name = definition.get('name') if definition else param.get('name')
                
                if ((param_name == 'valve_state' or param.get('name') == 'valve_state') and 
                    param.get('component_name', '').lower().startswith('valve')):
                    valve_params.append(param)
            
            logger.info(f"Found {len(valve_params)} valve parameters")
            
            if valve_params:
                for valve_param in valve_params:
                    # Extract valve number from component_name (e.g., "Valve 1" -> 1)
                    component_name = valve_param.get('component_name', '')
                    try:
                        # Extract the valve number
                        import re
                        match = re.search(r'valve\s*(\d+)', component_name.lower())
                        if match:
                            valve_number = int(match.group(1))
                            
                            # Only add to cache if Modbus address is present
                            if valve_param.get('modbus_address'):
                                # For valves, always set the proper modbus_type
                                modbus_type = valve_param.get('modbus_type')
                                if not modbus_type:
                                    modbus_type = 'coil'  # Valves are always coils
                                
                                self._valve_cache[valve_number] = {
                                    'parameter_id': valve_param['id'],
                                    'modbus_address': valve_param['modbus_address'],
                                    'modbus_type': modbus_type,
                                    'component_name': component_name,
                                    'data_type': 'binary'  # Valves are always binary
                                }
                                logger.info(f"Added Valve {valve_number} with Modbus address {valve_param['modbus_address']}, modbus_type: {modbus_type}")
                            else:
                                logger.warning(f"Valve {valve_number} ({component_name}) has no Modbus address defined in database")
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Could not extract valve number from component name: {component_name}. Error: {e}")
                
                # Log detailed valve mapping information
                for valve_num, valve_data in self._valve_cache.items():
                    logger.info(f"Valve {valve_num} ({valve_data['component_name']}) mapped to Modbus address: {valve_data['modbus_address']}")
                
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
            
            # Try looking for purge parameters in database with definition information
            query = supabase.table('component_parameters').select(
                '*, component_parameter_definitions!definition_id(name, unit, description)'
            ).execute()
            
            # Look for components/parameters with 'purge' in name or component_name
            purge_params = []
            for param in query.data:
                # Check both the parameter name and the definition name
                definition = param.get('component_parameter_definitions', {})
                param_name = definition.get('name') if definition else param.get('name', '')
                
                if ('purge' in param_name.lower() or
                    'purge' in param.get('name', '').lower() or
                    'purge' in param.get('component_name', '').lower() or
                    param.get('operand') == 'W_Purge'):
                    purge_params.append(param)
            
            logger.info(f"Found {len(purge_params)} potential purge parameters")
            
            if purge_params:
                purge_param = purge_params[0]  # Use the first matching parameter
                
                if purge_param.get('modbus_address'):
                    self._purge_address = purge_param['modbus_address']
                    self._purge_data_type = purge_param.get('data_type') or 'binary'
                    
                    # Set the modbus_type based on data_type or existing modbus_type
                    modbus_type = purge_param.get('modbus_type')
                    if not modbus_type:
                        if self._purge_data_type == 'binary':
                            modbus_type = 'coil'
                        else:
                            modbus_type = 'holding'
                    
                    self._purge_modbus_type = modbus_type
                    
                    logger.info(f"Loaded purge operation from database: address {self._purge_address}, "
                               f"data_type: {self._purge_data_type}, modbus_type: {self._purge_modbus_type}, "
                               f"parameter_id: {purge_param['id']}, name: {purge_param['name']}, "
                               f"component: {purge_param.get('component_name')}")
                else:
                    # Use purge from components database
                    logger.warning(f"Purge parameter found but has no Modbus address: {purge_param.get('name')}, "
                                  f"Component: {purge_param.get('component_name')}")
                    self._purge_address = 20  # Default from CSV
                    self._purge_data_type = 'binary'
                    self._purge_modbus_type = 'coil'
                    logger.info(f"Using default purge address: address {self._purge_address}, data_type: {self._purge_data_type}")
            else:
                logger.warning("No purge operation parameter found in database")
                self._purge_address = 20  # Default from CSV
                self._purge_data_type = 'binary'
                self._purge_modbus_type = 'coil'
                logger.info(f"Using default purge address: address {self._purge_address}, data_type: {self._purge_data_type}")
                
        except Exception as e:
            logger.error(f"Error loading purge parameters: {str(e)}", exc_info=True)
            # Fallback to default purge address
            self._purge_address = 20  # Default from CSV
            self._purge_data_type = 'binary'
            self._purge_modbus_type = 'coil'
            logger.info(f"Using fallback purge address: {self._purge_address}, data_type: {self._purge_data_type}")
    
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
        
        address = param_meta.get('modbus_address')
        data_type = param_meta['data_type']
        modbus_type = param_meta['modbus_type']
        
        # Handle case where Modbus address is missing (e.g., MFC power_on)
        if not address:
            logger.warning(f"Parameter {parameter_id} ({param_meta.get('name')}) has no Modbus address. Returning current value from database.")
            return param_meta.get('current_value', 0.0)
        
        # Read the parameter based on Modbus type and data type
        value = None
        try:
            # First check modbus_type
            if modbus_type == 'coil':
                result = self.communicator.read_coils(address, count=1)
                if result is not None:
                    value = 1.0 if result[0] else 0.0
            elif modbus_type == 'discrete_input':
                result = self.communicator.client.read_discrete_inputs(address, count=1, slave=self.communicator.slave_id)
                if not result.isError():
                    value = 1.0 if result.bits[0] else 0.0
                else:
                    logger.error(f"Failed to read discrete input: {result}")
            elif modbus_type == 'input':
                # Handle input registers based on data type
                if data_type == 'float':
                    value = self.communicator.read_float(address, register_type='input')
                elif data_type == 'int32':
                    value = self.communicator.read_integer_32bit(address, register_type='input')
                elif data_type == 'int16':
                    result = self.communicator.client.read_input_registers(address, count=1, slave=self.communicator.slave_id)
                    if not result.isError():
                        value = result.registers[0]
                    else:
                        logger.error(f"Failed to read input register: {result}")
            elif modbus_type == 'holding':
                # Handle holding registers based on data type
                if data_type == 'float':
                    value = self.communicator.read_float(address)
                elif data_type == 'int32':
                    value = self.communicator.read_integer_32bit(address)
                elif data_type == 'int16':
                    result = self.communicator.client.read_holding_registers(address, count=1, slave=self.communicator.slave_id)
                    if not result.isError():
                        value = result.registers[0]
                    else:
                        logger.error(f"Failed to read holding register: {result}")
            else:
                # Fallback based on data_type for backwards compatibility
                if data_type == 'float':
                    value = self.communicator.read_float(address)
                elif data_type == 'int32':
                    value = self.communicator.read_integer_32bit(address)
                elif data_type == 'int16':
                    result = self.communicator.client.read_holding_registers(address, count=1, slave=self.communicator.slave_id)
                    if not result.isError():
                        value = result.registers[0]
                    else:
                        logger.error(f"Failed to read int16: {result}")
                elif data_type == 'binary':
                    result = self.communicator.read_coils(address, count=1)
                    if result is not None:
                        value = 1.0 if result[0] else 0.0
                else:
                    raise ValueError(f"Unsupported data type: {data_type}")
            
            # Apply scaling for MFCs and Pressure Gauges if needed
            component_name = param_meta.get('component_name', '').lower()
            param_name = param_meta.get('name', '').lower()
            
            # Check if this is a value that needs scaling
            if value is not None and (
                (component_name.startswith('mfc') and param_name == 'flow_read') or
                (component_name.startswith('pressure') and param_name == 'pressure_read')
            ):
                # Get MFC or Pressure Gauge scaling
                mfc_match = re.search(r'mfc\s*(\d+)', component_name)
                pg_match = re.search(r'pressure\s*gauge\s*(\d+)', component_name)
                
                if mfc_match and mfc_match.group(1) in self._mfc_scaling_cache:
                    # Apply MFC voltage scaling
                    mfc_num = mfc_match.group(1)
                    scaling = self._mfc_scaling_cache.get(mfc_num)
                    if scaling:
                        # Convert voltage reading to flow value
                        value = self._scale_value(
                            value,
                            scaling.get('min_voltage', 0),
                            scaling.get('max_voltage', 10),
                            scaling.get('min_value', 0),
                            scaling.get('max_value', 0)
                        )
                        logger.debug(f"Applied MFC {mfc_num} scaling to value: {value}")
                
                elif pg_match and pg_match.group(1) in self._pressure_scaling_cache:
                    # Apply Pressure Gauge voltage scaling
                    pg_num = pg_match.group(1)
                    scaling = self._pressure_scaling_cache.get(pg_num)
                    if scaling:
                        # Convert voltage reading to pressure value
                        value = self._scale_value(
                            value,
                            scaling.get('min_voltage', 0),
                            scaling.get('max_voltage', 10),
                            scaling.get('min_value', 0),
                            scaling.get('max_value', 0)
                        )
                        logger.debug(f"Applied Pressure Gauge {pg_num} scaling to value: {value}")
            
        except Exception as e:
            logger.error(f"Error reading parameter {parameter_id} ({param_meta.get('name')}): {str(e)}")
        
        if value is None:
            logger.warning(f"Failed to read value for parameter {parameter_id}. Returning None.")
            return None
            
        # Update database with current value (in background task)
        asyncio.create_task(self._update_parameter_value(parameter_id, value))
        
        return float(value)
    
    async def _update_parameter_value(self, parameter_id: str, value: float):
        """Update the current value of a parameter in the database."""
        try:
            supabase = get_supabase()
            
            # Get parameter details from cache to log more info
            param_meta = self._parameter_cache.get(parameter_id, {})
            # Use the pre-truncated component name from the cache
            component_name = param_meta.get('short_component_name', '')
            param_name = param_meta.get('name', '')
                
            # Log parameter update with truncated names
            logger.debug(f"Updating current value of parameter: {param_name} ({component_name}) with value: {value}")
            
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
        
        address = param_meta.get('modbus_address')
        data_type = param_meta['data_type']
        modbus_type = param_meta['modbus_type']
        component_name = param_meta.get('component_name', '').lower()
        param_name = param_meta.get('name', '').lower()
        
        # Special handling for MFC power_on parameter without Modbus address
        if not address:
            logger.warning(f"Parameter {parameter_id} ({param_meta.get('name')}) has no Modbus address. Updating database only.")
            # Just update the database and return success
            asyncio.create_task(self._update_parameter_set_value(parameter_id, value))
            return True
            
        # Apply scaling for MFCs and Pressure Gauges if needed for write operations
        original_value = value
        if (component_name.startswith('mfc') and param_name == 'flow_set') or (component_name.startswith('pressure') and param_name.startswith('scale_')):
            # Get MFC or Pressure Gauge scaling
            mfc_match = re.search(r'mfc\s*(\d+)', component_name)
            pg_match = re.search(r'pressure\s*gauge\s*(\d+)', component_name)
            
            if mfc_match and mfc_match.group(1) in self._mfc_scaling_cache and param_name == 'flow_set':
                # Apply inverse MFC voltage scaling for set values
                mfc_num = mfc_match.group(1)
                scaling = self._mfc_scaling_cache.get(mfc_num)
                if scaling:
                    # Convert flow value to voltage for writing
                    value = self._inverse_scale_value(
                        value,
                        scaling.get('min_value', 0),
                        scaling.get('max_value', 0),
                        scaling.get('min_voltage', 0),
                        scaling.get('max_voltage', 10)
                    )
                    logger.debug(f"Applied inverse MFC {mfc_num} scaling to value: {original_value} -> {value}")
        
        success = False
        try:
            # Write parameter based on Modbus type and data type
            if modbus_type == 'coil':
                success = self.communicator.write_coil(address, value > 0)
            elif modbus_type == 'holding':
                if data_type == 'float':
                    success = self.communicator.write_float(address, value)
                elif data_type == 'int32':
                    success = self.communicator.write_integer_32bit(address, int(value))
                elif data_type == 'int16':
                    result = self.communicator.client.write_register(address, int(value), slave=self.communicator.slave_id)
                    success = not result.isError()
                else:
                    # Fall back to float for unknown data types in holding registers
                    success = self.communicator.write_float(address, value)
            else:
                # Fallback method for backwards compatibility
                if data_type == 'float':
                    success = self.communicator.write_float(address, value)
                elif data_type == 'int32':
                    success = self.communicator.write_integer_32bit(address, int(value))
                elif data_type == 'int16':
                    result = self.communicator.client.write_register(address, int(value), slave=self.communicator.slave_id)
                    success = not result.isError()
                elif data_type == 'binary':
                    success = self.communicator.write_coil(address, value > 0)
                else:
                    raise ValueError(f"Unsupported data type: {data_type}")
        except Exception as e:
            logger.error(f"Error writing parameter {parameter_id} ({param_meta.get('name')}): {str(e)}")
            success = False
        
        if success:
            # Update database with new set value (in background task)
            asyncio.create_task(self._update_parameter_set_value(parameter_id, original_value))
            
        return success
    
    async def _update_parameter_set_value(self, parameter_id: str, value: float):
        """Update the set value of a parameter in the database."""
        try:
            supabase = get_supabase()
            
            # Get parameter details from cache to log more info
            param_meta = self._parameter_cache.get(parameter_id, {})
            # Use the pre-truncated component name from the cache
            component_name = param_meta.get('short_component_name', '') 
            param_name = param_meta.get('name', '')
                
            # Log parameter update with truncated names
            logger.debug(f"Updating parameter: {param_name} ({component_name}) with value: {value}")
            
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
            logger.error(f"Valve {valve_number} not found in valve cache. Available valves: {list(self._valve_cache.keys())}")
            raise ValueError(f"Valve {valve_number} not found in valve cache")
        
        address = valve_meta['modbus_address']
        
        logger.info(f"{'Opening' if state else 'Closing'} valve {valve_number} at Modbus address {address} (Parameter ID: {valve_meta['parameter_id']})")
        
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
    
    def _scale_value(self, value: float, min_in: float, max_in: float, min_out: float, max_out: float) -> float:
        """
        Scale a value from one range to another using linear interpolation.
        
        Args:
            value: The input value to scale
            min_in: Minimum value of the input range
            max_in: Maximum value of the input range
            min_out: Minimum value of the output range
            max_out: Maximum value of the output range
            
        Returns:
            float: The scaled value
        """
        if max_in == min_in:  # Avoid division by zero
            return min_out
            
        # Basic linear interpolation formula
        # (value - min_in) / (max_in - min_in) = (result - min_out) / (max_out - min_out)
        return min_out + (max_out - min_out) * (value - min_in) / (max_in - min_in)
    
    def _inverse_scale_value(self, value: float, min_in: float, max_in: float, min_out: float, max_out: float) -> float:
        """
        The inverse of _scale_value. Converts from the output range back to the input range.
        
        Args:
            value: The output value to convert back
            min_in: Minimum value of the original input range
            max_in: Maximum value of the original input range
            min_out: Minimum value of the original output range
            max_out: Maximum value of the original output range
            
        Returns:
            float: The value in the input range
        """
        # Just swap the in/out parameters to reverse the mapping
        return self._scale_value(value, min_out, max_out, min_in, max_in)
    
    async def _load_scaling_parameters(self):
        """
        Load MFC and pressure gauge scaling parameters from the database.
        These parameters map voltage readings to actual flow/pressure values.
        """
        try:
            supabase = get_supabase()
            
            # Query all parameters with definition information
            query = supabase.table('component_parameters').select(
                '*, component_parameter_definitions!definition_id(name, unit, description)'
            ).execute()
            
            # Process all parameters to find MFC and Pressure Gauge scaling parameters
            mfc_parameters = {}
            pressure_parameters = {}
            
            for param in query.data:
                component_name = param.get('component_name', '').lower()
                # Check both the parameter name and the definition name
                definition = param.get('component_parameter_definitions', {})
                param_name = (definition.get('name') if definition else param.get('name', '')).lower()
                operand = param.get('operand', '')
                
                # Extract component number
                mfc_match = re.search(r'mfc\s*(\d+)', component_name)
                pg_match = re.search(r'pressure\s*gauge\s*(\d+)', component_name)
                
                # Process MFC parameters
                if mfc_match:
                    mfc_num = mfc_match.group(1)
                    if mfc_num not in mfc_parameters:
                        mfc_parameters[mfc_num] = {}
                    
                    # Add parameters to MFC scaling cache
                    if param_name == 'scale_min':
                        mfc_parameters[mfc_num]['min_value'] = param.get('current_value', 0)
                    elif param_name == 'scale_max':
                        mfc_parameters[mfc_num]['max_value'] = param.get('current_value', 200)
                    elif param_name == 'scale_min_voltage':
                        mfc_parameters[mfc_num]['min_voltage'] = param.get('current_value', 0)
                    elif param_name == 'scale_max_voltage':
                        mfc_parameters[mfc_num]['max_voltage'] = param.get('current_value', 10)
                        
                # Process Pressure Gauge parameters
                elif pg_match:
                    pg_num = pg_match.group(1)
                    if pg_num not in pressure_parameters:
                        pressure_parameters[pg_num] = {}
                    
                    # Add parameters to Pressure Gauge scaling cache
                    if param_name == 'scale_min':
                        pressure_parameters[pg_num]['min_value'] = param.get('current_value', 0)
                    elif param_name == 'scale_max':
                        pressure_parameters[pg_num]['max_value'] = param.get('current_value', 100000)
                    elif param_name == 'scale_min_voltage':
                        pressure_parameters[pg_num]['min_voltage'] = param.get('current_value', 0)
                    elif param_name == 'scale_max_voltage':
                        pressure_parameters[pg_num]['max_voltage'] = param.get('current_value', 10)
            
            # Store the collected scaling parameters
            self._mfc_scaling_cache = mfc_parameters
            self._pressure_scaling_cache = pressure_parameters
            
            # Log scaling parameters
            for mfc_num, scaling in self._mfc_scaling_cache.items():
                logger.info(f"MFC {mfc_num} scaling: min_value={scaling.get('min_value', 0)}, "
                          f"max_value={scaling.get('max_value', 0)}, min_voltage={scaling.get('min_voltage', 0)}, "
                          f"max_voltage={scaling.get('max_voltage', 0)}")
                          
            for pg_num, scaling in self._pressure_scaling_cache.items():
                logger.info(f"Pressure Gauge {pg_num} scaling: min_value={scaling.get('min_value', 0)}, "
                          f"max_value={scaling.get('max_value', 0)}, min_voltage={scaling.get('min_voltage', 0)}, "
                          f"max_voltage={scaling.get('max_voltage', 0)}")
                
        except Exception as e:
            logger.error(f"Error loading scaling parameters: {str(e)}", exc_info=True)
            # Initialize with empty caches
            self._mfc_scaling_cache = {}
            self._pressure_scaling_cache = {}
    
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
            logger.error("Purge operation parameters not found in database. Make sure there's a parameter with 'purge' in its name.")
            raise ValueError("Purge operation parameters not found")
        
        logger.info(f"Starting purge operation for {duration_ms}ms at Modbus address {self._purge_address} "
                  f"with data type {self._purge_data_type}, modbus_type: {getattr(self, '_purge_modbus_type', 'coil')}")
        
        # Activate purge operation
        if self._purge_data_type == 'binary':
            # Trigger purge by setting coil
            success = self.communicator.write_coil(self._purge_address, True)
            logger.info(f"Sending purge command to coil address {self._purge_address}")
        else:
            # Trigger purge by writing 1 to register
            success = self.communicator.write_integer_32bit(self._purge_address, 1)
            logger.info(f"Sending purge command to register address {self._purge_address} (value: 1)")
        
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