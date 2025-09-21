# File: src/domain/value_objects.py
"""
Value objects for the ALD control system domain.
Immutable objects that represent concepts without identity.
"""
from dataclasses import dataclass
from typing import Optional, Union
import uuid
import re

@dataclass(frozen=True)
class ValueObject:
    """Base class for value objects"""

    def __post_init__(self):
        self.validate()

    def validate(self):
        """Validate value object state - override in subclasses"""
        pass

@dataclass(frozen=True)
class ProcessId(ValueObject):
    """Process identifier value object"""
    value: str

    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid.uuid4()))
        super().__post_init__()

    def validate(self):
        if not isinstance(self.value, str):
            raise ValueError("ProcessId must be a string")
        if len(self.value.strip()) == 0:
            raise ValueError("ProcessId cannot be empty")

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class RecipeId(ValueObject):
    """Recipe identifier value object"""
    value: str

    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid.uuid4()))
        super().__post_init__()

    def validate(self):
        if not isinstance(self.value, str):
            raise ValueError("RecipeId must be a string")
        if len(self.value.strip()) == 0:
            raise ValueError("RecipeId cannot be empty")

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class ParameterId(ValueObject):
    """Parameter identifier value object"""
    value: str

    def validate(self):
        if not isinstance(self.value, str):
            raise ValueError("ParameterId must be a string")
        if len(self.value.strip()) == 0:
            raise ValueError("ParameterId cannot be empty")
        # Validate parameter ID format (alphanumeric with underscores)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', self.value):
            raise ValueError("ParameterId must start with letter and contain only alphanumeric characters and underscores")

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class Duration(ValueObject):
    """Duration value object representing time periods"""
    milliseconds: int

    def validate(self):
        if not isinstance(self.milliseconds, int):
            raise ValueError("Duration milliseconds must be an integer")
        if self.milliseconds < 0:
            raise ValueError("Duration cannot be negative")

    @property
    def seconds(self) -> float:
        """Get duration in seconds"""
        return self.milliseconds / 1000.0

    @property
    def minutes(self) -> float:
        """Get duration in minutes"""
        return self.milliseconds / 60000.0

    @property
    def total_milliseconds(self) -> int:
        """Get total milliseconds"""
        return self.milliseconds

    @classmethod
    def from_seconds(cls, seconds: float) -> 'Duration':
        """Create duration from seconds"""
        return cls(int(seconds * 1000))

    @classmethod
    def from_minutes(cls, minutes: float) -> 'Duration':
        """Create duration from minutes"""
        return cls(int(minutes * 60000))

    def __str__(self):
        if self.milliseconds < 1000:
            return f"{self.milliseconds}ms"
        elif self.milliseconds < 60000:
            return f"{self.seconds:.1f}s"
        else:
            return f"{self.minutes:.1f}min"

@dataclass(frozen=True)
class ValueRange(ValueObject):
    """Value range for parameters with min/max bounds"""
    min_value: Optional[float]
    max_value: Optional[float]

    def validate(self):
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValueError("min_value cannot be greater than max_value")

    def contains(self, value: float) -> bool:
        """Check if value is within range"""
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True

    def clamp(self, value: float) -> float:
        """Clamp value to range bounds"""
        if self.min_value is not None and value < self.min_value:
            return self.min_value
        if self.max_value is not None and value > self.max_value:
            return self.max_value
        return value

    @property
    def is_bounded(self) -> bool:
        """Check if range has both min and max bounds"""
        return self.min_value is not None and self.max_value is not None

    @property
    def span(self) -> Optional[float]:
        """Get the span of the range"""
        if self.is_bounded:
            return self.max_value - self.min_value
        return None

@dataclass(frozen=True)
class Temperature(ValueObject):
    """Temperature value object with unit support"""
    value: float
    unit: str = "°C"

    def validate(self):
        if not isinstance(self.value, (int, float)):
            raise ValueError("Temperature value must be numeric")
        if self.unit not in ["°C", "°F", "K"]:
            raise ValueError("Temperature unit must be °C, °F, or K")
        # Validate absolute zero bounds
        if self.unit == "K" and self.value < 0:
            raise ValueError("Kelvin temperature cannot be negative")
        if self.unit == "°C" and self.value < -273.15:
            raise ValueError("Celsius temperature cannot be below absolute zero")
        if self.unit == "°F" and self.value < -459.67:
            raise ValueError("Fahrenheit temperature cannot be below absolute zero")

    def to_celsius(self) -> 'Temperature':
        """Convert to Celsius"""
        if self.unit == "°C":
            return self
        elif self.unit == "°F":
            celsius = (self.value - 32) * 5/9
            return Temperature(celsius, "°C")
        elif self.unit == "K":
            celsius = self.value - 273.15
            return Temperature(celsius, "°C")

    def to_fahrenheit(self) -> 'Temperature':
        """Convert to Fahrenheit"""
        if self.unit == "°F":
            return self
        celsius = self.to_celsius()
        fahrenheit = celsius.value * 9/5 + 32
        return Temperature(fahrenheit, "°F")

    def to_kelvin(self) -> 'Temperature':
        """Convert to Kelvin"""
        if self.unit == "K":
            return self
        celsius = self.to_celsius()
        kelvin = celsius.value + 273.15
        return Temperature(kelvin, "K")

    def __str__(self):
        return f"{self.value:.1f}{self.unit}"

@dataclass(frozen=True)
class Pressure(ValueObject):
    """Pressure value object with unit support"""
    value: float
    unit: str = "Pa"

    def validate(self):
        if not isinstance(self.value, (int, float)):
            raise ValueError("Pressure value must be numeric")
        if self.value < 0:
            raise ValueError("Pressure cannot be negative")
        if self.unit not in ["Pa", "kPa", "MPa", "bar", "mbar", "atm", "psi", "torr", "mmHg"]:
            raise ValueError(f"Unsupported pressure unit: {self.unit}")

    def to_pascals(self) -> 'Pressure':
        """Convert to Pascals"""
        if self.unit == "Pa":
            return self

        conversion_factors = {
            "kPa": 1000,
            "MPa": 1000000,
            "bar": 100000,
            "mbar": 100,
            "atm": 101325,
            "psi": 6894.76,
            "torr": 133.322,
            "mmHg": 133.322
        }

        pascals = self.value * conversion_factors[self.unit]
        return Pressure(pascals, "Pa")

    def to_unit(self, target_unit: str) -> 'Pressure':
        """Convert to specified unit"""
        pascals = self.to_pascals()

        conversion_factors = {
            "Pa": 1,
            "kPa": 1/1000,
            "MPa": 1/1000000,
            "bar": 1/100000,
            "mbar": 1/100,
            "atm": 1/101325,
            "psi": 1/6894.76,
            "torr": 1/133.322,
            "mmHg": 1/133.322
        }

        if target_unit not in conversion_factors:
            raise ValueError(f"Unsupported pressure unit: {target_unit}")

        converted_value = pascals.value * conversion_factors[target_unit]
        return Pressure(converted_value, target_unit)

    def __str__(self):
        return f"{self.value:.2f} {self.unit}"

@dataclass(frozen=True)
class FlowRate(ValueObject):
    """Flow rate value object with unit support"""
    value: float
    unit: str = "L/min"

    def validate(self):
        if not isinstance(self.value, (int, float)):
            raise ValueError("Flow rate value must be numeric")
        if self.value < 0:
            raise ValueError("Flow rate cannot be negative")
        if self.unit not in ["L/min", "L/s", "mL/min", "mL/s", "m³/h", "m³/min", "cfm", "gpm"]:
            raise ValueError(f"Unsupported flow rate unit: {self.unit}")

    def to_liters_per_minute(self) -> 'FlowRate':
        """Convert to liters per minute"""
        if self.unit == "L/min":
            return self

        conversion_factors = {
            "L/s": 60,
            "mL/min": 1/1000,
            "mL/s": 60/1000,
            "m³/h": 1000/60,
            "m³/min": 1000,
            "cfm": 28.3168,
            "gpm": 3.78541
        }

        liters_per_minute = self.value * conversion_factors[self.unit]
        return FlowRate(liters_per_minute, "L/min")

    def to_unit(self, target_unit: str) -> 'FlowRate':
        """Convert to specified unit"""
        base = self.to_liters_per_minute()

        conversion_factors = {
            "L/min": 1,
            "L/s": 1/60,
            "mL/min": 1000,
            "mL/s": 1000/60,
            "m³/h": 60/1000,
            "m³/min": 1/1000,
            "cfm": 1/28.3168,
            "gpm": 1/3.78541
        }

        if target_unit not in conversion_factors:
            raise ValueError(f"Unsupported flow rate unit: {target_unit}")

        converted_value = base.value * conversion_factors[target_unit]
        return FlowRate(converted_value, target_unit)

    def __str__(self):
        return f"{self.value:.2f} {self.unit}"

@dataclass(frozen=True)
class Address(ValueObject):
    """Modbus address value object"""
    address: int
    register_type: str = "holding"  # holding, input, coil, discrete

    def validate(self):
        if not isinstance(self.address, int):
            raise ValueError("Address must be an integer")
        if self.address < 0:
            raise ValueError("Address cannot be negative")
        if self.address > 65535:
            raise ValueError("Address cannot exceed 65535")
        if self.register_type not in ["holding", "input", "coil", "discrete"]:
            raise ValueError("Register type must be holding, input, coil, or discrete")

    @property
    def modbus_address(self) -> int:
        """Get the actual Modbus address"""
        return self.address

    @property
    def is_read_only(self) -> bool:
        """Check if address is read-only"""
        return self.register_type in ["input", "discrete"]

    def __str__(self):
        return f"{self.register_type}:{self.address}"

@dataclass(frozen=True)
class Coordinate(ValueObject):
    """3D coordinate value object"""
    x: float
    y: float
    z: float = 0.0

    def validate(self):
        if not all(isinstance(val, (int, float)) for val in [self.x, self.y, self.z]):
            raise ValueError("Coordinates must be numeric")

    def distance_to(self, other: 'Coordinate') -> float:
        """Calculate distance to another coordinate"""
        return ((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)**0.5

    def __str__(self):
        if self.z == 0.0:
            return f"({self.x:.2f}, {self.y:.2f})"
        return f"({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"

# Factory functions for common value objects
def create_process_id() -> ProcessId:
    """Create a new process ID"""
    return ProcessId(str(uuid.uuid4()))

def create_recipe_id() -> RecipeId:
    """Create a new recipe ID"""
    return RecipeId(str(uuid.uuid4()))

def create_parameter_id(name: str) -> ParameterId:
    """Create a parameter ID from name"""
    # Convert name to valid parameter ID format
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    clean_name = re.sub(r'^[^a-zA-Z]', 'param_', clean_name)
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    return ParameterId(clean_name)

def create_temperature_celsius(value: float) -> Temperature:
    """Create temperature in Celsius"""
    return Temperature(value, "°C")

def create_pressure_pa(value: float) -> Pressure:
    """Create pressure in Pascals"""
    return Pressure(value, "Pa")

def create_flow_rate_lpm(value: float) -> FlowRate:
    """Create flow rate in liters per minute"""
    return FlowRate(value, "L/min")

def create_duration_seconds(seconds: float) -> Duration:
    """Create duration from seconds"""
    return Duration.from_seconds(seconds)

def create_duration_minutes(minutes: float) -> Duration:
    """Create duration from minutes"""
    return Duration.from_minutes(minutes)