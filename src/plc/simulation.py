# File: plc/simulation.py (updated)
"""
Simulation implementation of the PLC interface.

Notes on Modbus types:
- The simulation intentionally ignores specific Modbus read/write types
  (coil, discrete_input, holding, input) and treats parameters by behavior
  only. This keeps simulated behavior consistent while the real PLC honors
  read/write Modbus types when provided.
"""
import asyncio
import random
from typing import Dict, Optional, Set
from src.log_setup import logger
from src.db import get_supabase
from src.plc.interface import PLCInterface

class SimulationPLC(PLCInterface):
    """Simulated PLC implementation for testing without hardware.

    In simulation, reads/writes do not distinguish between coil/register
    types. Binary-like params still behave as on/off, and numeric ones as
    ranged values, independent of Modbus type metadata.
    """
    
    # Parameter types that should not fluctuate
    NON_FLUCTUATING_TYPES = {
        'binary', 'state', 'status', 'switch', 'enable', 'enabled', 'on_off',
        'on', 'off', 'running', 'active', 'alarm', 'fault', 'error', 'warning',
        'mode', 'position', 'valve_state', 'valve_position'
    }
    
    # Maximum range for discrete/binary parameters that should not fluctuate
    BINARY_RANGE_THRESHOLD = 1
    
    def __init__(self):
        """Initialize the simulation."""
        self.connected = False
        self.current_values = {}  # Current value cache
        self.set_values = {}      # Set value cache
        self.param_metadata = {}  # Parameter metadata
        self.non_fluctuating_params = set()  # Parameters that shouldn't fluctuate
        self.valves = {}          # Valve states
        self._valve_cache = {}    # Valve parameter mappings
    
    async def initialize(self) -> bool:
        """Initialize the simulated PLC."""
        logger.info("Initializing simulation PLC")
        
        # Load parameter values and metadata from database
        await self._load_parameters()

        # Load valve mappings for set_value synchronization
        await self._load_valve_mappings()

        # Initialize all valves to closed
        for i in range(1, 11):  # Assuming up to 10 valves
            self.valves[i] = False
            
        self.connected = True
        logger.info("Simulation PLC initialized")
        return True
    
    async def _load_parameters(self):
        """Load parameter values and metadata from database."""
        supabase = get_supabase()
        
        # Get all component parameters
        params_result = supabase.table('component_parameters').select('*').execute()
        
        if not params_result.data:
            logger.warning("No parameters found in database")
            return
        
        # Process parameters and determine which ones should fluctuate
        for param in params_result.data:
            param_id = param['id']
            self.current_values[param_id] = param['current_value']
            self.set_values[param_id] = param['set_value']
            
            # Store metadata for making fluctuation decisions
            self.param_metadata[param_id] = {
                'name': (param.get('name') or str(param_id)).lower(),
                'min_value': param.get('min_value', 0),
                'max_value': param.get('max_value', 0),
                'unit': param.get('unit'),
                'component_id': param.get('component_id'),
                'is_writable': param.get('is_writable', False)
            }
            
            # Determine if this parameter should fluctuate
            should_fluctuate = self._should_parameter_fluctuate(param)
            if not should_fluctuate:
                self.non_fluctuating_params.add(param_id)
                logger.debug(
                    f"Parameter {param_id} ({param.get('name', str(param_id))}) "
                    f"will not fluctuate"
                )

    async def _load_valve_mappings(self):
        """Load valve mappings from the database for set_value synchronization."""
        try:
            supabase = get_supabase()

            # Get valve parameters by looking for component names starting with 'valve'
            # and parameter names containing 'valve_state'
            params_result = supabase.table('component_parameters').select('*').execute()

            valve_params = []
            for param in params_result.data:
                component_name = param.get('component_name', '').lower()
                param_name = param.get('name', '').lower()

                if (component_name.startswith('valve') and
                    'valve_state' in param_name):
                    valve_params.append(param)

            for valve_param in valve_params:
                # Extract valve number from component name
                component_name = valve_param.get('component_name', '')
                try:
                    import re
                    match = re.search(r'valve\s*(\d+)', component_name.lower())
                    if match:
                        valve_number = int(match.group(1))
                        self._valve_cache[valve_number] = {
                            'parameter_id': valve_param['id'],
                            'component_name': component_name
                        }
                        logger.info(f"Simulation: Mapped Valve {valve_number} to parameter {valve_param['id']}")
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Could not extract valve number from: {component_name}")

            logger.info(f"Simulation: Loaded mappings for {len(self._valve_cache)} valves")

        except Exception as e:
            logger.error(f"Error loading valve mappings in simulation: {str(e)}")

    def _should_parameter_fluctuate(self, param) -> bool:
        """
        Determine if a parameter should fluctuate in the simulation.
        
        Args:
            param: The parameter data from the database
            
        Returns:
            bool: True if the parameter should fluctuate, False otherwise
        """
        # Don't fluctuate if the range is small (binary or discrete values)
        if (param['max_value'] - param['min_value']) <= self.BINARY_RANGE_THRESHOLD:
            return False
        
        # Check parameter name for keywords that suggest it's a state or discrete parameter
        param_name = (param.get('name') or '').lower()
        for keyword in self.NON_FLUCTUATING_TYPES:
            if keyword in param_name:
                return False
                
        # Default to allowing fluctuation for other parameters
        return True
    
    async def disconnect(self) -> bool:
        """Disconnect from the simulated PLC."""
        logger.info("Disconnecting simulation PLC")
        self.connected = False
        return True
    
    async def read_parameter(self, parameter_id: str) -> float:
        """Read a parameter from the simulation with realistic fluctuations."""
        if not self.connected:
            raise RuntimeError("Not connected to simulation PLC")
            
        # If parameter isn't in our cache, try to load from database
        if parameter_id not in self.current_values:
            await self._load_parameter(parameter_id)
        
        # Get the base value for this parameter
        base_value = self.current_values[parameter_id]
        
        # If this parameter should not fluctuate, return its exact value
        if parameter_id in self.non_fluctuating_params:
            return base_value
        
        # Get set value as target
        set_value = self.set_values.get(parameter_id, base_value)
        
        # Calculate realistic fluctuation around set point
        # Current value should gravitate toward set point with some noise
        meta = self.param_metadata.get(parameter_id, {})
        min_val = meta.get('min_value', 0)
        max_val = meta.get('max_value', 100)
        
        # Calculate range as a percentage of the full scale
        full_range = max_val - min_val
        fluctuation_pct = 0.01  # 1% fluctuation
        
        # Generate fluctuation that tends toward the set point
        # Current value moves 10% toward set point plus random noise
        # Handle case where set_value is None (no setpoint defined)
        if set_value is not None and abs(base_value - set_value) > 0.001:  # If not already at set point
            # Move 10% toward set point
            new_value = base_value + 0.1 * (set_value - base_value)
            # Add random noise (0.5% of full scale)
            noise = random.uniform(-0.005, 0.005) * full_range
            new_value += noise
        elif set_value is not None:
            # At set point, just add noise around set point
            noise = random.uniform(-fluctuation_pct, fluctuation_pct) * full_range
            new_value = set_value + noise
        else:
            # No set point defined, add random noise around current value
            noise = random.uniform(-fluctuation_pct, fluctuation_pct) * full_range
            new_value = base_value + noise
        
        # Ensure value stays within bounds
        new_value = max(min_val, min(max_val, new_value))
        
        # Update the current value in our cache
        self.current_values[parameter_id] = new_value
        
        return new_value
    
    async def _load_parameter(self, parameter_id: str):
        """Load a specific parameter from the database."""
        supabase = get_supabase()
        
        result = supabase.table('component_parameters').select('*').eq('id', parameter_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise ValueError(f"Parameter {parameter_id} not found")
        
        param = result.data[0]
        self.current_values[parameter_id] = param['current_value']
        self.set_values[parameter_id] = param['set_value']
        
        # Store metadata for making fluctuation decisions
        self.param_metadata[parameter_id] = {
            'name': (param.get('name') or str(parameter_id)).lower(),
            'min_value': param.get('min_value', 0),
            'max_value': param.get('max_value', 0),
            'unit': param.get('unit'),
            'component_id': param.get('component_id'),
            'is_writable': param.get('is_writable', False)
        }
        
        # Determine if this parameter should fluctuate
        should_fluctuate = self._should_parameter_fluctuate(param)
        if not should_fluctuate:
            self.non_fluctuating_params.add(parameter_id)
    
    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        """Write a parameter value to the simulation."""
        if not self.connected:
            raise RuntimeError("Not connected to simulation PLC")

        # If parameter isn't in our cache, try to load from database
        if parameter_id not in self.current_values:
            await self._load_parameter(parameter_id)

        # Update both current and set values in simulation cache
        self.set_values[parameter_id] = value
        self.current_values[parameter_id] = value

        # Update database with set value (in background task to match real PLC pattern)
        asyncio.create_task(self._update_parameter_set_value(parameter_id, value))

        return True

    async def _update_parameter_set_value(self, parameter_id: str, value: float):
        """Update the set value of a parameter in the database."""
        try:
            supabase = get_supabase()
            supabase.table('component_parameters').update({
                'set_value': value,
                'updated_at': 'now()'
            }).eq('id', parameter_id).execute()

        except Exception as e:
            logger.error(f"Error updating parameter set value in simulation: {str(e)}")

    async def read_all_parameters(self) -> Dict[str, float]:
        """Read all parameters from the simulation with realistic fluctuations."""
        if not self.connected:
            raise RuntimeError("Not connected to simulation PLC")
            
        # Make sure we have all parameters loaded
        await self._load_parameters()
        
        # Create a result dictionary with updated values
        result = {}
        for param_id in self.current_values:
            result[param_id] = await self.read_parameter(param_id)
        
        return result
    
    async def control_valve(
        self,
        valve_number: int,
        state: bool,
        duration_ms: Optional[int] = None,
    ) -> bool:
        """Control a valve in the simulation."""
        if not self.connected:
            raise RuntimeError("Not connected to simulation PLC")
            
        logger.info(f"Simulation: {'Opening' if state else 'Closing'} valve {valve_number}")
        self.valves[valve_number] = state

        # Update database with new set value for valve parameter
        valve_meta = self._valve_cache.get(valve_number)
        if valve_meta:
            parameter_id = valve_meta['parameter_id']
            valve_set_value = 1.0 if state else 0.0
            asyncio.create_task(self._update_parameter_set_value(parameter_id, valve_set_value))

        # If duration specified, close after duration
        if state and duration_ms is not None:
            await asyncio.sleep(duration_ms / 1000)
            self.valves[valve_number] = False
            logger.info(f"Simulation: Auto-closing valve {valve_number} after {duration_ms}ms")

            # Update set value for auto-close operation
            if valve_meta:
                asyncio.create_task(self._update_parameter_set_value(parameter_id, 0.0))

        return True
    
    async def execute_purge(self, duration_ms: int) -> bool:
        """Execute a purge operation in the simulation."""
        if not self.connected:
            raise RuntimeError("Not connected to simulation PLC")
            
        logger.info(f"Simulation: Starting purge for {duration_ms}ms")
        
        # In simulation, we just wait for the duration
        await asyncio.sleep(duration_ms / 1000)
        
        logger.info("Simulation: Purge completed")
        return True

    # --- Minimal Modbus-like helpers for parameter_control_listener smoke tests ---
    # NOTE: These helpers intentionally operate by address only and make no attempt to
    #       interpret any legacy 'modbus_type'. This mirrors the real PLC behavior shift
    #       to the dual-address model where 'binary' data_type => coils and others =>
    #       holding registers. TODO: Consider mapping addresses to parameter IDs if
    #       richer simulation becomes necessary.
    async def write_holding_register(self, address: int, value: float) -> bool:
        """Simulate writing a holding register by address."""
        # Store in a simple map; in a richer sim we could map addresses to params
        if not hasattr(self, "_holding_registers"):
            self._holding_registers = {}
        self._holding_registers[address] = float(value)
        return True

    async def read_holding_register(self, address: int) -> Optional[float]:
        if hasattr(self, "_holding_registers") and address in self._holding_registers:
            return self._holding_registers[address]
        return 0.0

    async def write_coil(self, address: int, value: bool) -> bool:
        if not hasattr(self, "_coils"):
            self._coils = {}
        self._coils[address] = bool(value)
        return True

    async def read_coils(self, address: int, count: int = 1):
        # Return a simple list of bools of length count
        vals = []
        for i in range(count):
            vals.append(bool(getattr(self, "_coils", {}).get(address + i, False)))
        return vals
