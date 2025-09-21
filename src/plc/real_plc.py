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
from src.config import is_essentials_filter_enabled

class RealPLC(PLCInterface):
    """Real PLC implementation for production use."""
    
    # Data type mapping
    DATA_TYPES = {
        'float': 'float',
        'int32': 'int32',
        'int16': 'int16',
        'binary': 'binary'
    }
    
    # Modbus register selection is inferred from data_type only.
    # - binary uses coils
    # - int16/int32/float use holding registers
    
    def __init__(
        self,
        ip_address: str,
        port: int,
        hostname: str = None,
        auto_discover: bool = False,
    ):
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
        self._purge_parameter_id = None
        
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
        Uses dual-address model (read_modbus_address/write_modbus_address) only.
        """
        # Local helper: gate which params are considered "essential" for noisy machines
        def _is_essential_param(name: str, component_name: str) -> bool:
            n = (name or "").lower()
            comp = (component_name or "").lower()

            # Core allowlist
            essential_exact = {
                "flow", "flow_rate", "flow_read", "flow_set",
                "pressure", "pressure_read", "pressure_set",
                "power_on", "power_off", "power_state",
            }

            if n in essential_exact:
                return True

            # Prefix matches
            if n.startswith("temperature"):
                return True

            # Special handling for valve_state: keep only numbered process valves
            if n == "valve_state":
                # Keep "Valve N"; ignore other variants like "Gas Valve", "Exhaust Gate Valve"
                return comp.startswith("valve ")

            return False

        try:
            supabase = get_supabase()
            
            # Query all parameters from the view that already denormalizes
            # parameter definition fields and component name
            result = supabase.table('component_parameters_full').select('*').execute()
            
            if result.data:
                apply_filter = is_essentials_filter_enabled()
                kept = 0
                for param in result.data:
                    parameter_id = param['id']
                    
                    # Get component name directly from the denormalized view
                    component_name = param.get('component_name', '')
                    if component_name and len(component_name) > 30:
                        short_component_name = component_name[:27] + "..."
                    else:
                        short_component_name = component_name
                    
                    # Names and metadata are denormalized in the view
                    param_name = param.get('parameter_name') or param.get('name')
                    param_unit = param.get('unit')
                    param_description = param.get('description')
                    
                    # Resolve read/write addresses (dual-address model only)
                    read_addr = param.get('read_modbus_address')
                    write_addr = param.get('write_modbus_address')

                    # Essentials filter (enabled only for specific machine IDs)
                    if apply_filter and not _is_essential_param(param_name, component_name):
                        # Skip non-essential parameters entirely: no cache and no logs
                        continue

                    self._parameter_cache[parameter_id] = {
                        'name': param_name or param['name'],
                        'read_modbus_address': read_addr,
                        'write_modbus_address': write_addr,
                        # Prefer explicit Modbus types if provided by the view
                        # TODO: Add explicit input-register/discrete-input support in communicator
                        'read_modbus_type': param.get('read_modbus_type'),
                        'write_modbus_type': param.get('write_modbus_type'),
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
                    kept += 1
                    # Log each parameter with its addresses (using short component name)
                    logger.info(
                        f"Parameter '{param_name or param['name']}' ({short_component_name}) "
                        f"(ID: {parameter_id}) read_addr: {read_addr}, write_addr: {write_addr}, "
                        f"data_type: {param['data_type']}"
                    )

                    # Validate required presence of addresses; log explicit errors
                    # Suppress these errors for ignored params by filtering before this point.
                    if read_addr is None:
                        logger.error(
                            f"Parameter {parameter_id} ({param_name}) missing read_modbus_address; "
                            f"reads will fail until populated."
                        )
                    if (
                        self._parameter_cache[parameter_id].get('is_writable')
                        and write_addr is None
                    ):
                        logger.error(
                            f"Parameter {parameter_id} ({param_name}) is writable but missing "
                            f"write_modbus_address; writes will fail until populated."
                        )
                    
                # Leave behavior unchanged for other machines
                total = kept if apply_filter else len(self._parameter_cache)
                logger.info(f"Loaded metadata for {total} parameters")
            else:
                logger.warning("No component parameters found in database")
                
        except Exception as e:
            logger.error(f"Error loading parameter metadata: {str(e)}", exc_info=True)
    
    async def _load_valve_mappings(self):
        """
        Load valve mappings from the database.
        Valves are treated as components with a specific parameter for valve state.
        """
        try:
            supabase = get_supabase()
            
            # Use the denormalized view for component and definition info
            query = supabase.table('component_parameters_full').select('*').execute()
            
            # Manually filter for valve parameters by checking:
            # 1. name is 'valve_state' (or definition name is 'valve_state')
            # 2. component_name starts with 'Valve'
            valve_params = []
            for param in query.data:
                # Check both the parameter name and the definition name
                param_name = param.get('parameter_name') or param.get('name')
                
                component_name = param.get('component_name', '')
                if ((param_name == 'valve_state' or param.get('name') == 'valve_state') and
                    component_name.lower().startswith('valve')):
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
                            
                            # Only add to cache if WRITE address is present
                            write_addr = valve_param.get('write_modbus_address')
                            if write_addr is not None:
                                self._valve_cache[valve_number] = {
                                    'parameter_id': valve_param['id'],
                                    'address': write_addr,
                                    'component_name': component_name,
                                    'data_type': 'binary'  # Valves are always binary coils
                                }
                                logger.info(
                                    f"Added Valve {valve_number} with write_modbus_address "
                                    f"{write_addr}"
                                )
                            else:
                                logger.error(
                                    f"Valve {valve_number} ({component_name}) "
                                    f"missing write_modbus_address"
                                )
                    except (ValueError, AttributeError) as e:
                        logger.warning(
                            f"Could not extract valve number from component name: "
                            f"{component_name}. Error: {e}"
                        )
                
                # Log detailed valve mapping information
                for valve_num, valve_data in self._valve_cache.items():
                    logger.info(
                        f"Valve {valve_num} ({valve_data['component_name']}) mapped to address: "
                        f"{valve_data['address']}"
                    )
                
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
            
            # Use the denormalized view for definition and component info
            query = supabase.table('component_parameters_full').select('*').execute()
            
            # Look for components/parameters with 'purge' in name or component_name
            purge_params = []
            for param in query.data:
                # Check both the parameter name and the definition name
                param_name = param.get('parameter_name') or param.get('name', '')
                component_name = param.get('component_name', '')
                if ('purge' in param_name.lower() or
                    'purge' in param.get('name', '').lower() or
                    'purge' in component_name.lower() or
                    param.get('operand') == 'W_Purge'):
                    purge_params.append(param)
            
            logger.info(f"Found {len(purge_params)} potential purge parameters")
            
            if purge_params:
                purge_param = purge_params[0]  # Use the first matching parameter
                
                write_addr = purge_param.get('write_modbus_address')
                if write_addr is not None:
                    self._purge_address = write_addr
                    self._purge_parameter_id = purge_param['id']
                    # Purge is a binary coil trigger
                    self._purge_data_type = 'binary'
                    purge_component_name = purge_param.get('component_name', '')
                    logger.info(
                        f"Loaded purge operation from database: "
                        f"write_modbus_address {self._purge_address}, "
                        f"data_type: {self._purge_data_type}, parameter_id: {self._purge_parameter_id}, "
                        f"name: {purge_param.get('name')}, component: {purge_component_name}"
                    )
                else:
                    purge_component_name = purge_param.get('component_name', '')
                    logger.error(
                        f"Purge parameter found but missing write_modbus_address: "
                        f"{purge_param.get('name')} (Component: {purge_component_name})"
                    )
            else:
                logger.warning("No purge operation parameter found in database")
                # TODO: Consider configurable fallback purge address if schema incomplete
                
        except Exception as e:
            logger.error(f"Error loading purge parameters: {str(e)}", exc_info=True)
            # TODO: Decide on safe fallback behavior for purge if addresses are missing
    
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
        
        address = param_meta.get('read_modbus_address')
        data_type = param_meta['data_type']
        read_type = (param_meta.get('read_modbus_type') or '').lower()

        # Require presence of read address
        if address is None:
            logger.error(
                f"Parameter {parameter_id} ({param_meta.get('name')}) missing read_modbus_address"
            )
            # TODO: Decide if we should raise instead of returning DB value
            return param_meta.get('current_value', 0.0)

        # Read the parameter using explicit read_modbus_type when available.
        # Fallback: infer from data_type (binary -> coils, else holding regs).
        # TODO: Add communicator methods for input registers and discrete inputs
        #       and switch 'input'/'discrete_input' to those when available.
        value = None
        try:
            if read_type in ('coil', 'discrete_input'):
                # For now, read discrete inputs via coils until supported
                result = self.communicator.read_coils(address, count=1)
                if result is not None:
                    value = 1.0 if result[0] else 0.0
            elif read_type in ('holding', 'input'):
                # For now, treat input registers like holding until supported
                if data_type == 'float':
                    value = self.communicator.read_float(address)
                elif data_type == 'int32':
                    value = self.communicator.read_integer_32bit(address)
                elif data_type == 'int16':
                    result = self.communicator.client.read_holding_registers(
                        address, count=1, slave=self.communicator.slave_id
                    )
                    if not result.isError():
                        value = result.registers[0]
                    else:
                        logger.error(
                            f"Failed to read holding register: {result}"
                        )
                elif data_type == 'binary':
                    # Edge case: binary stored in a register
                    result = self.communicator.client.read_holding_registers(
                        address, count=1, slave=self.communicator.slave_id
                    )
                    if not result.isError():
                        value = 1.0 if result.registers[0] else 0.0
                else:
                    raise ValueError(f"Unsupported data type: {data_type}")
            else:
                # Fallback to data_type-based behavior
                if data_type == 'binary':
                    result = self.communicator.read_coils(address, count=1)
                    if result is not None:
                        value = 1.0 if result[0] else 0.0
                elif data_type == 'float':
                    value = self.communicator.read_float(address)
                elif data_type == 'int32':
                    value = self.communicator.read_integer_32bit(address)
                elif data_type == 'int16':
                    result = self.communicator.client.read_holding_registers(
                        address, count=1, slave=self.communicator.slave_id
                    )
                    if not result.isError():
                        value = result.registers[0]
                    else:
                        logger.error(
                            f"Failed to read holding register: {result}"
                        )
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
            logger.error(
                f"Error reading parameter {parameter_id} ({param_meta.get('name')}): "
                f"{str(e)}"
            )
        
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
            logger.debug(
                f"Updating current value of parameter: {param_name} ({component_name}) "
                f"with value: {value}"
            )
            
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
        
        address = param_meta.get('write_modbus_address')
        data_type = param_meta['data_type']
        write_type = (param_meta.get('write_modbus_type') or '').lower()
        component_name = param_meta.get('component_name', '').lower()
        param_name = param_meta.get('name', '').lower()
        
        # Require presence of write address for writes
        if address is None:
            logger.error(
                f"Parameter {parameter_id} ({param_meta.get('name')}) missing write_modbus_address"
            )
            return False
            
        # Apply scaling for MFCs and Pressure Gauges if needed for write operations
        original_value = value
        if (
            (component_name.startswith('mfc') and param_name == 'flow_set')
            or (
                component_name.startswith('pressure')
                and param_name.startswith('scale_')
            )
        ):
            # Get MFC or Pressure Gauge scaling
            mfc_match = re.search(r'mfc\s*(\d+)', component_name)
            pg_match = re.search(r'pressure\s*gauge\s*(\d+)', component_name)
            
            if (
                mfc_match
                and mfc_match.group(1) in self._mfc_scaling_cache
                and param_name == 'flow_set'
            ):
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
                    logger.debug(
                        (
                            f"Applied inverse MFC {mfc_num} scaling to value: "
                            f"{original_value} -> {value}"
                        )
                    )
        
        success = False
        try:
            # Prefer explicit write_modbus_type when available.
            # Fallback: infer from data_type (binary -> coil, else holding regs).
            # TODO: Add communicator methods for input/discrete inputs (read-only types).
            if write_type == 'coil':
                success = self.communicator.write_coil(address, value > 0)
            elif write_type == 'holding':
                if data_type == 'float':
                    success = self.communicator.write_float(address, value)
                elif data_type == 'int32':
                    success = self.communicator.write_integer_32bit(
                        address, int(value)
                    )
                elif data_type == 'int16':
                    result = self.communicator.client.write_register(
                        address, int(value), slave=self.communicator.slave_id
                    )
                    success = not result.isError()
                elif data_type == 'binary':
                    # Edge case: binary stored in register (treat non-zero as 1)
                    result = self.communicator.client.write_register(
                        address, 1 if value > 0 else 0,
                        slave=self.communicator.slave_id
                    )
                    success = not result.isError()
                else:
                    raise ValueError(f"Unsupported data type: {data_type}")
            else:
                # Fallback to data_type-based behavior
                if data_type == 'binary':
                    success = self.communicator.write_coil(address, value > 0)
                elif data_type == 'float':
                    success = self.communicator.write_float(address, value)
                elif data_type == 'int32':
                    success = self.communicator.write_integer_32bit(
                        address, int(value)
                    )
                elif data_type == 'int16':
                    result = self.communicator.client.write_register(
                        address, int(value), slave=self.communicator.slave_id
                    )
                    success = not result.isError()
                else:
                    raise ValueError(f"Unsupported data type: {data_type}")
        except Exception as e:
            logger.error(
                f"Error writing parameter {parameter_id} ({param_meta.get('name')}): "
                f"{str(e)}"
            )
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
    
    async def control_valve(
        self,
        valve_number: int,
        state: bool,
        duration_ms: Optional[int] = None,
    ) -> bool:
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
            logger.error(
                f"Valve {valve_number} not found in valve cache. Available valves: "
                f"{list(self._valve_cache.keys())}"
            )
            raise ValueError(f"Valve {valve_number} not found in valve cache")
        
        address = valve_meta['address']
        
        logger.info(
            f"{'Opening' if state else 'Closing'} valve {valve_number} at address {address} "
            f"(Parameter ID: {valve_meta['parameter_id']})"
        )
        
        # Write to the valve coil
        success = self.communicator.write_coil(address, state)

        if not success:
            logger.error(f"Failed to {'open' if state else 'close'} valve {valve_number}")
            return False

        # Update database with new set value for valve parameter (in background task)
        parameter_id = valve_meta['parameter_id']
        valve_set_value = 1.0 if state else 0.0
        asyncio.create_task(self._update_parameter_set_value(parameter_id, valve_set_value))

        # If duration specified, schedule valve to close after duration
        if state and duration_ms is not None and duration_ms > 0:
            # Create a background task to close the valve after the specified duration
            asyncio.create_task(self._auto_close_valve(valve_number, address, duration_ms))

        return success

    def _is_connection_error(self, error) -> bool:
        """Check if an error is connection-related and should trigger reconnection."""
        error_str = str(error).lower()

        # Check for broken pipe error (errno 32)
        is_broken_pipe = (
            hasattr(error, 'errno') and error.errno == errno.EPIPE
        ) or (
            'broken pipe' in error_str or
            'errno 32' in error_str or
            'connection reset' in error_str or
            'connection aborted' in error_str or
            'connection refused' in error_str or
            'connection timed out' in error_str or
            'socket' in error_str
        )

        return is_broken_pipe

    async def _ensure_plc_connection(self) -> bool:
        """Ensure PLC connection is established, reconnect if necessary."""
        if self.connected and self.communicator and self.communicator._is_connection_healthy():
            return True

        logger.info("Attempting to establish PLC connection...")

        try:
            # Try to connect
            success = self.communicator.connect()

            if success:
                self.connected = True
                logger.info("Successfully reconnected to PLC")
                return True
            else:
                logger.error("Failed to reconnect to PLC")
                self.connected = False
                return False

        except Exception as e:
            logger.error(f"Exception during PLC reconnection: {e}")
            self.connected = False
            return False
    
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
                logger.warning(
                    f"Not closing valve {valve_number} after timeout: Not connected to PLC"
                )
                return
            
            # Close the valve
            logger.info(f"Auto-closing valve {valve_number} after {duration_ms}ms")
            success = self.communicator.write_coil(address, False)

            if success:
                # Update database with new set value for valve parameter (closed state)
                valve_meta = self._valve_cache.get(valve_number)
                if valve_meta:
                    parameter_id = valve_meta['parameter_id']
                    asyncio.create_task(self._update_parameter_set_value(parameter_id, 0.0))
            else:
                logger.error(f"Failed to auto-close valve {valve_number}")
            
        except Exception as e:
            logger.error(f"Error in auto-close valve task: {str(e)}")
    
    def _scale_value(
        self,
        value: float,
        min_in: float,
        max_in: float,
        min_out: float,
        max_out: float,
    ) -> float:
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
    
    def _inverse_scale_value(
        self,
        value: float,
        min_in: float,
        max_in: float,
        min_out: float,
        max_out: float,
    ) -> float:
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
                param_name = (
                    definition.get('name') if definition else param.get('name', '')
                ).lower()
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
                        pressure_parameters[pg_num]['max_value'] = param.get(
                            'current_value', 100000
                        )
                    elif param_name == 'scale_min_voltage':
                        pressure_parameters[pg_num]['min_voltage'] = param.get('current_value', 0)
                    elif param_name == 'scale_max_voltage':
                        pressure_parameters[pg_num]['max_voltage'] = param.get('current_value', 10)
            
            # Store the collected scaling parameters
            self._mfc_scaling_cache = mfc_parameters
            self._pressure_scaling_cache = pressure_parameters
            
            # Log scaling parameters
            for mfc_num, scaling in self._mfc_scaling_cache.items():
                logger.info(
                    (
                        f"MFC {mfc_num} scaling: min_value={scaling.get('min_value', 0)}, "
                        f"max_value={scaling.get('max_value', 0)}, "
                        f"min_voltage={scaling.get('min_voltage', 0)}, "
                        f"max_voltage={scaling.get('max_voltage', 0)}"
                    )
                )

            for pg_num, scaling in self._pressure_scaling_cache.items():
                logger.info(
                    (
                        f"Pressure Gauge {pg_num} scaling: "
                        f"min_value={scaling.get('min_value', 0)}, "
                        f"max_value={scaling.get('max_value', 0)}, "
                        f"min_voltage={scaling.get('min_voltage', 0)}, "
                        f"max_voltage={scaling.get('max_voltage', 0)}"
                    )
                )
                
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
            logger.error(
                "Purge operation parameters not found in database. Make sure there's a parameter "
                "with 'purge' in its name."
            )
            raise ValueError("Purge operation parameters not found")
        
        logger.info(
            f"Starting purge operation for {duration_ms}ms at write_modbus_address "
            f"{self._purge_address} with data type {self._purge_data_type}"
        )
        
        # Activate purge operation
        if self._purge_data_type == 'binary':
            # Trigger purge by setting coil
            success = self.communicator.write_coil(self._purge_address, True)
            logger.info(f"Sending purge command to coil address {self._purge_address}")
        else:
            # Trigger purge by writing 1 to register
            success = self.communicator.write_integer_32bit(self._purge_address, 1)
            logger.info(
                f"Sending purge command to register address {self._purge_address} "
                f"(value: 1)"
            )
        
        if not success:
            logger.error("Failed to start purge operation")
            return False

        # Update database with new set value for purge parameter (activated state)
        if self._purge_parameter_id:
            purge_set_value = 1.0
            asyncio.create_task(self._update_parameter_set_value(self._purge_parameter_id, purge_set_value))

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
            
            if success:
                # Update database with new set value for purge parameter (deactivated state)
                if self._purge_parameter_id:
                    purge_set_value = 0.0
                    asyncio.create_task(self._update_parameter_set_value(self._purge_parameter_id, purge_set_value))
            else:
                logger.error("Failed to complete purge operation")
            
        except Exception as e:
            logger.error(f"Error in complete purge task: {str(e)}")
