"""
Parameter data factory for generating test parameters with constraints.

This module provides factories for creating realistic parameter test data
with proper validation ranges and data types.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from faker import Faker
import random

fake = Faker()
Faker.seed(42)


@dataclass
class Parameter:
    """Parameter data structure."""
    id: str
    name: str
    component_id: str
    modbus_address: int
    data_type: str  # 'float', 'integer', 'binary'
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_writable: bool = True
    is_safety_critical: bool = False
    description: Optional[str] = None
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


@dataclass
class ParameterValue:
    """Parameter value history record."""
    parameter_id: str
    value: float
    timestamp: str
    machine_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


class ParameterFactory:
    """Factory for generating test parameters with various patterns."""

    def __init__(self, machine_id: str = "test-machine", component_id: str = "test-component"):
        """Initialize factory with machine and component ID."""
        self.machine_id = machine_id
        self.component_id = component_id
        self._parameter_counter = 0
        self._modbus_address_counter = 1000  # Start at 1000 to avoid conflicts

    def _generate_parameter_id(self) -> str:
        """Generate unique parameter ID."""
        self._parameter_counter += 1
        return f"param-test-{uuid.uuid4().hex[:8]}-{self._parameter_counter}"

    def _get_next_modbus_address(self) -> int:
        """Get next available Modbus address."""
        addr = self._modbus_address_counter
        self._modbus_address_counter += 1
        return addr

    def create_test_parameters(self, count: int = 10) -> List[Parameter]:
        """
        Create bulk test parameters with varied characteristics.

        Args:
            count: Number of parameters to create

        Returns:
            List[Parameter]: List of generated parameters
        """
        parameters = []
        data_types = ['float', 'integer', 'binary']
        units = ['°C', 'Pa', 'mbar', 'sccm', '%', 'V', 'A', 'W']

        for i in range(count):
            data_type = random.choice(data_types)

            if data_type == 'float':
                min_val = random.uniform(0.0, 100.0)
                max_val = min_val + random.uniform(50.0, 500.0)
                unit = random.choice(units)
            elif data_type == 'integer':
                min_val = float(random.randint(0, 100))
                max_val = float(min_val + random.randint(50, 500))
                unit = random.choice(['count', 'steps', 'cycles'])
            else:  # binary
                min_val = 0.0
                max_val = 1.0
                unit = None

            param = Parameter(
                id=self._generate_parameter_id(),
                name=f"{fake.word().title()}_{i+1}",
                component_id=self.component_id,
                modbus_address=self._get_next_modbus_address(),
                data_type=data_type,
                min_value=min_val,
                max_value=max_val,
                is_writable=random.choice([True, False]),
                is_safety_critical=random.choice([True, False]) if i < 3 else False,
                description=f"Test parameter {i+1}: {fake.sentence()}",
                unit=unit
            )
            parameters.append(param)

        return parameters

    def create_parameter_with_constraints(
        self,
        min_value: float,
        max_value: float,
        name: Optional[str] = None,
        data_type: str = 'float'
    ) -> Parameter:
        """
        Create parameter with specific min/max constraints.

        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            name: Optional parameter name
            data_type: Data type ('float', 'integer', 'binary')

        Returns:
            Parameter: Parameter with specified constraints
        """
        param_name = name or f"Bounded_{fake.word().title()}"

        return Parameter(
            id=self._generate_parameter_id(),
            name=param_name,
            component_id=self.component_id,
            modbus_address=self._get_next_modbus_address(),
            data_type=data_type,
            min_value=min_value,
            max_value=max_value,
            is_writable=True,
            is_safety_critical=False,
            description=f"Parameter with bounds [{min_value}, {max_value}]",
            unit='°C' if 'temp' in param_name.lower() else 'units'
        )

    def create_safety_critical_parameter(
        self,
        name: Optional[str] = None,
        min_value: float = 0.0,
        max_value: float = 500.0
    ) -> Parameter:
        """
        Create safety-critical parameter (should have validation).

        Args:
            name: Optional parameter name
            min_value: Minimum safe value
            max_value: Maximum safe value

        Returns:
            Parameter: Safety-critical parameter
        """
        param_name = name or f"SafetyCritical_{fake.word().title()}"

        return Parameter(
            id=self._generate_parameter_id(),
            name=param_name,
            component_id=self.component_id,
            modbus_address=self._get_next_modbus_address(),
            data_type='float',
            min_value=min_value,
            max_value=max_value,
            is_writable=True,
            is_safety_critical=True,
            description=f"SAFETY CRITICAL: {param_name}. Must be within [{min_value}, {max_value}]",
            unit='°C' if 'temp' in param_name.lower() else 'Pa'
        )

    def create_temperature_parameter(self, min_temp: float = 0.0, max_temp: float = 600.0) -> Parameter:
        """Create temperature parameter."""
        return Parameter(
            id=self._generate_parameter_id(),
            name="Temperature",
            component_id=self.component_id,
            modbus_address=self._get_next_modbus_address(),
            data_type='float',
            min_value=min_temp,
            max_value=max_temp,
            is_writable=True,
            is_safety_critical=True,
            description="Chamber temperature sensor",
            unit='°C'
        )

    def create_pressure_parameter(self, min_pressure: float = 0.0, max_pressure: float = 1000.0) -> Parameter:
        """Create pressure parameter."""
        return Parameter(
            id=self._generate_parameter_id(),
            name="Pressure",
            component_id=self.component_id,
            modbus_address=self._get_next_modbus_address(),
            data_type='float',
            min_value=min_pressure,
            max_value=max_pressure,
            is_writable=False,  # Typically read-only
            is_safety_critical=True,
            description="Chamber pressure sensor",
            unit='mbar'
        )

    def create_valve_parameter(self, valve_number: int = 1) -> Parameter:
        """Create binary valve parameter."""
        return Parameter(
            id=self._generate_parameter_id(),
            name=f"Valve_{valve_number}",
            component_id=self.component_id,
            modbus_address=self._get_next_modbus_address(),
            data_type='binary',
            min_value=0.0,
            max_value=1.0,
            is_writable=True,
            is_safety_critical=False,
            description=f"Valve {valve_number} control (0=closed, 1=open)",
            unit=None
        )

    def create_flow_parameter(self, gas_type: str = "N2") -> Parameter:
        """Create gas flow parameter."""
        return Parameter(
            id=self._generate_parameter_id(),
            name=f"{gas_type}_Flow",
            component_id=self.component_id,
            modbus_address=self._get_next_modbus_address(),
            data_type='float',
            min_value=0.0,
            max_value=1000.0,
            is_writable=True,
            is_safety_critical=False,
            description=f"{gas_type} mass flow controller",
            unit='sccm'
        )

    def create_parameter_value(
        self,
        parameter_id: str,
        value: float,
        timestamp: Optional[str] = None
    ) -> ParameterValue:
        """Create parameter value history record."""
        return ParameterValue(
            parameter_id=parameter_id,
            value=value,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            machine_id=self.machine_id
        )

    def create_parameter_history(
        self,
        parameter: Parameter,
        num_records: int = 10,
        value_range: Optional[tuple] = None
    ) -> List[ParameterValue]:
        """
        Create historical values for a parameter.

        Args:
            parameter: Parameter to create history for
            num_records: Number of historical records
            value_range: Optional (min, max) tuple for values

        Returns:
            List[ParameterValue]: Historical parameter values
        """
        values = []
        min_val, max_val = value_range or (parameter.min_value or 0.0, parameter.max_value or 100.0)

        for i in range(num_records):
            if parameter.data_type == 'binary':
                value = float(random.choice([0, 1]))
            elif parameter.data_type == 'integer':
                value = float(random.randint(int(min_val), int(max_val)))
            else:  # float
                value = random.uniform(min_val, max_val)

            values.append(self.create_parameter_value(
                parameter_id=parameter.id,
                value=value
            ))

        return values

    async def insert_parameters(
        self,
        supabase_client,
        parameters: List[Parameter]
    ) -> Dict[str, Any]:
        """
        Insert parameters into database.

        Args:
            supabase_client: Supabase client instance
            parameters: Parameters to insert

        Returns:
            Dict with insertion results
        """
        params_data = [param.to_dict() for param in parameters]
        result = supabase_client.table("component_parameters").insert(params_data).execute()

        return {
            "parameters": result.data if result.data else [],
            "count": len(parameters)
        }

    async def insert_parameter_values(
        self,
        supabase_client,
        values: List[ParameterValue]
    ) -> Dict[str, Any]:
        """
        Insert parameter values into history table.

        Args:
            supabase_client: Supabase client instance
            values: Parameter values to insert

        Returns:
            Dict with insertion results
        """
        values_data = [val.to_dict() for val in values]
        result = supabase_client.table("parameter_value_history").insert(values_data).execute()

        return {
            "values": result.data if result.data else [],
            "count": len(values)
        }

    async def cleanup_test_parameters(
        self,
        supabase_client,
        parameter_ids: Optional[List[str]] = None
    ):
        """
        Clean up test parameters and related data.

        Args:
            supabase_client: Supabase client instance
            parameter_ids: Optional list of specific parameter IDs to delete
        """
        if parameter_ids:
            # Delete specific parameters
            for param_id in parameter_ids:
                # Delete parameter values first (foreign key)
                supabase_client.table("parameter_value_history").delete().eq("parameter_id", param_id).execute()
                # Delete parameter commands
                supabase_client.table("parameter_control_commands").delete().eq("component_parameter_id", param_id).execute()
                # Delete parameter
                supabase_client.table("component_parameters").delete().eq("id", param_id).execute()
        else:
            # Delete all test parameters (starts with "param-test-")
            test_params = supabase_client.table("component_parameters").select("id").like("id", "param-test-%").execute()

            for param in test_params.data:
                param_id = param["id"]
                supabase_client.table("parameter_value_history").delete().eq("parameter_id", param_id).execute()
                supabase_client.table("parameter_control_commands").delete().eq("component_parameter_id", param_id).execute()
                supabase_client.table("component_parameters").delete().eq("id", param_id).execute()


# Convenience functions
def create_test_parameters(count: int = 10, machine_id: str = "test-machine") -> List[Parameter]:
    """Convenience function to create test parameters."""
    factory = ParameterFactory(machine_id=machine_id)
    return factory.create_test_parameters(count)


def create_safety_critical_parameter(
    name: str = "SafetyTemp",
    min_value: float = 0.0,
    max_value: float = 500.0,
    machine_id: str = "test-machine"
) -> Parameter:
    """Convenience function to create safety-critical parameter."""
    factory = ParameterFactory(machine_id=machine_id)
    return factory.create_safety_critical_parameter(name, min_value, max_value)


def create_ald_parameter_set(machine_id: str = "test-machine") -> List[Parameter]:
    """Create a realistic set of ALD system parameters."""
    factory = ParameterFactory(machine_id=machine_id)

    return [
        factory.create_temperature_parameter(0.0, 600.0),
        factory.create_pressure_parameter(0.0, 100.0),
        factory.create_valve_parameter(1),
        factory.create_valve_parameter(2),
        factory.create_valve_parameter(3),
        factory.create_valve_parameter(4),
        factory.create_flow_parameter("N2"),
        factory.create_flow_parameter("Ar"),
        factory.create_flow_parameter("Precursor"),
        factory.create_flow_parameter("Oxidant"),
    ]
