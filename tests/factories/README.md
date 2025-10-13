# Test Data Factories

Comprehensive test data factories for the ALD Control System testing infrastructure.

## Overview

This module provides factory classes and convenience functions for generating realistic test data including:
- **Recipes** with steps (simple, complex, parameter-based)
- **Parameters** with constraints and validation rules
- **Commands** for recipe execution and parameter control

## Quick Start

```python
from tests.factories import (
    create_simple_recipe,
    create_ald_parameter_set,
    create_start_recipe_command,
)

# Create a simple recipe with 3 steps
recipe, steps = create_simple_recipe()

# Create ALD system parameters
params = create_ald_parameter_set()

# Create a command to start the recipe
command = create_start_recipe_command(recipe_id=recipe.id)
```

## Recipe Factories

### Convenience Functions

```python
from tests.factories import (
    create_simple_recipe,
    create_complex_recipe,
    create_recipe_with_parameters,
)

# Simple 3-step recipe (valve, purge, valve)
recipe, steps = create_simple_recipe()
# Returns: Recipe with 3 sequential steps

# Complex ALD deposition recipe with loops
recipe, steps = create_complex_recipe(loop_count=10)
# Returns: Recipe with 10+ steps including nested loops

# Recipe with parameter control steps
recipe, steps = create_recipe_with_parameters()
# Returns: Recipe with parameter set/read steps
```

### Factory Class Usage

```python
from tests.factories import RecipeFactory

factory = RecipeFactory(machine_id="test-machine-1")

# Create recipes
recipe1, steps1 = factory.create_simple_recipe(name="Custom Recipe")
recipe2, steps2 = factory.create_complex_recipe(loop_count=5)

# Create individual steps
valve_step = factory.create_valve_step(
    recipe_id=recipe1.id,
    sequence=1,
    valve_num=3,
    duration_ms=5000
)

purge_step = factory.create_purge_step(
    recipe_id=recipe1.id,
    sequence=2,
    gas_type="N2",
    duration_ms=10000
)

loop_step = factory.create_loop_step(
    recipe_id=recipe1.id,
    sequence=3,
    count=5
)

parameter_step = factory.create_parameter_step(
    recipe_id=recipe1.id,
    sequence=4,
    parameter_name="Temperature",
    value=250.0
)
```

### Database Operations

```python
# Insert recipe and steps
result = await factory.insert_recipe(supabase_client, recipe, steps)
# Returns: {"recipe": {...}, "steps": [...], "step_count": 3}

# Cleanup test data
await factory.cleanup_test_recipes(supabase_client)
# Deletes all test recipes (IDs starting with "recipe-test-")

# Or cleanup specific recipes
await factory.cleanup_test_recipes(supabase_client, recipe_ids=["recipe-test-123"])
```

## Parameter Factories

### Convenience Functions

```python
from tests.factories import (
    create_test_parameters,
    create_safety_critical_parameter,
    create_ald_parameter_set,
)

# Create bulk test parameters
params = create_test_parameters(count=10)
# Returns: 10 parameters with varied data types and constraints

# Create safety-critical parameter
temp = create_safety_critical_parameter(
    name="ChamberTemp",
    min_value=0.0,
    max_value=600.0
)
# Returns: Parameter with is_safety_critical=True

# Create realistic ALD parameter set
ald_params = create_ald_parameter_set()
# Returns: 10 parameters (temp, pressure, 4 valves, 4 flows)
```

### Factory Class Usage

```python
from tests.factories import ParameterFactory

factory = ParameterFactory(
    machine_id="test-machine-1",
    component_id="test-component-1"
)

# Create specific parameters
temp = factory.create_temperature_parameter(min_temp=0.0, max_temp=600.0)
pressure = factory.create_pressure_parameter(min_pressure=0.0, max_pressure=1000.0)
valve = factory.create_valve_parameter(valve_number=1)
flow = factory.create_flow_parameter(gas_type="N2")

# Create parameter with custom constraints
param = factory.create_parameter_with_constraints(
    min_value=10.0,
    max_value=100.0,
    name="CustomParam",
    data_type="float"
)

# Create parameter history
values = factory.create_parameter_history(
    parameter=temp,
    num_records=100,
    value_range=(20.0, 500.0)
)
# Returns: 100 ParameterValue records with random values
```

### Database Operations

```python
# Insert parameters
result = await factory.insert_parameters(supabase_client, params)
# Returns: {"parameters": [...], "count": 10}

# Insert parameter values
result = await factory.insert_parameter_values(supabase_client, values)
# Returns: {"values": [...], "count": 100}

# Cleanup test data
await factory.cleanup_test_parameters(supabase_client)
# Deletes all test parameters and related data

# Or cleanup specific parameters
await factory.cleanup_test_parameters(
    supabase_client,
    parameter_ids=["param-test-123"]
)
```

## Command Factories

### Recipe Commands

```python
from tests.factories import (
    RecipeCommandFactory,
    create_start_recipe_command,
    create_stop_recipe_command,
)

# Convenience functions
start_cmd = create_start_recipe_command(
    recipe_id="recipe-123",
    machine_id="machine-1"
)

stop_cmd = create_stop_recipe_command(machine_id="machine-1")

# Factory class usage
factory = RecipeCommandFactory(machine_id="machine-1")

# Create commands with different states
pending_cmd = factory.create_start_recipe_command(
    recipe_id="recipe-456",
    status="pending"
)

# Create global command (NULL machine_id)
global_cmd = factory.create_global_command(
    recipe_id="recipe-789",
    command_type="start_recipe"
)

# Update command state
cmd = factory.mark_executing(pending_cmd)
# Sets status='executing', executed_at=now()

cmd = factory.mark_completed(cmd)
# Sets status='completed', completed_at=now()

cmd = factory.mark_failed(cmd, error="Test error")
# Sets status='failed', error_message="Test error"
```

### Parameter Commands

```python
from tests.factories import (
    ParameterCommandFactory,
    create_parameter_write_command,
)

# Convenience function
cmd = create_parameter_write_command(
    parameter_name="Temperature",
    target_value=250.0,
    machine_id="machine-1"
)

# Factory class usage
factory = ParameterCommandFactory(machine_id="machine-1")

# Create command by parameter name
cmd1 = factory.create_parameter_write_command(
    parameter_name="Pressure",
    target_value=100.0,
    timeout_ms=5000
)

# Create command by parameter ID
cmd2 = factory.create_parameter_write_command(
    component_parameter_id="param-123",
    target_value=50.0
)

# Create command with direct Modbus address
cmd3 = factory.create_command_with_address(
    modbus_address=2000,
    target_value=75.0,
    data_type="float"
)

# Create global parameter command
global_cmd = factory.create_global_parameter_command(
    parameter_name="Temperature",
    target_value=300.0
)

# Create out-of-range command (for testing validation)
invalid_cmd = factory.create_out_of_range_command(
    parameter_name="Temperature",
    target_value=999.0  # Outside safe range
)
```

### Database Operations

```python
# Insert recipe command
result = await recipe_factory.insert_command(supabase_client, command)
# Returns: Inserted command data

# Insert parameter command
result = await param_factory.insert_command(supabase_client, command)
# Returns: Inserted command data

# Cleanup recipe commands
await recipe_factory.cleanup_test_commands(supabase_client)
# Deletes all test commands (IDs starting with "cmd-test-")

# Cleanup parameter commands
await param_factory.cleanup_test_commands(supabase_client)
# Deletes all test commands (IDs starting with "param-cmd-test-")
```

## Data Structures

### Recipe & RecipeStep

```python
from tests.factories import Recipe, RecipeStep

recipe = Recipe(
    id="recipe-test-123",
    name="Test Recipe",
    version="1.0",
    description="Description",
    created_at="2025-01-01T00:00:00Z"
)

step = RecipeStep(
    id="step-test-456",
    recipe_id="recipe-test-123",
    sequence_number=1,
    type="valve",
    name="Open Valve 1",
    parameters={"valve_number": 1, "state": "open"},
    parent_step_id=None  # NULL for top-level steps
)

# Convert to dict for database insertion
recipe_dict = recipe.to_dict()
step_dict = step.to_dict()
```

### Parameter & ParameterValue

```python
from tests.factories import Parameter, ParameterValue

parameter = Parameter(
    id="param-test-789",
    name="Temperature",
    component_id="component-1",
    modbus_address=1000,
    data_type="float",
    min_value=0.0,
    max_value=600.0,
    is_writable=True,
    is_safety_critical=True,
    description="Chamber temperature",
    unit="°C"
)

value = ParameterValue(
    parameter_id="param-test-789",
    value=250.0,
    timestamp="2025-01-01T00:00:00Z",
    machine_id="machine-1"
)

# Convert to dict
param_dict = parameter.to_dict()
value_dict = value.to_dict()
```

### RecipeCommand & ParameterCommand

```python
from tests.factories import RecipeCommand, ParameterCommand

recipe_cmd = RecipeCommand(
    id="cmd-test-111",
    type="start_recipe",
    status="pending",
    machine_id="machine-1",
    parameters={"recipe_id": "recipe-123"},
    created_at="2025-01-01T00:00:00Z",
    executed_at=None,
    completed_at=None,
    error_message=None
)

param_cmd = ParameterCommand(
    id="param-cmd-test-222",
    parameter_name="Temperature",
    component_parameter_id=None,
    target_value=250.0,
    machine_id="machine-1",
    timeout_ms=5000,
    created_at="2025-01-01T00:00:00Z",
    executed_at=None,
    completed_at=None,
    error_message=None,
    modbus_address=None,
    data_type=None
)

# Convert to dict
recipe_cmd_dict = recipe_cmd.to_dict()
param_cmd_dict = param_cmd.to_dict()
```

## Testing Patterns

### Integration Testing with Database

```python
import pytest
from tests.factories import RecipeFactory, ParameterFactory

@pytest.mark.asyncio
@pytest.mark.database
async def test_recipe_execution(supabase_client):
    """Test recipe execution with real database."""
    factory = RecipeFactory()

    # Create and insert recipe
    recipe, steps = factory.create_simple_recipe()
    result = await factory.insert_recipe(supabase_client, recipe, steps)

    try:
        # Test recipe execution...
        assert result["step_count"] == 3

    finally:
        # Cleanup
        await factory.cleanup_test_recipes(
            supabase_client,
            recipe_ids=[recipe.id]
        )
```

### Stress Testing

```python
import pytest
from tests.factories import ParameterFactory

@pytest.mark.performance
async def test_bulk_parameter_insertion(supabase_client):
    """Test inserting 1000 parameters."""
    factory = ParameterFactory()

    # Generate 1000 parameters
    params = factory.create_test_parameters(count=1000)

    try:
        # Measure insertion time
        result = await factory.insert_parameters(supabase_client, params)
        assert result["count"] == 1000

    finally:
        await factory.cleanup_test_parameters(supabase_client)
```

### Unit Testing

```python
from tests.factories import create_simple_recipe

def test_recipe_structure():
    """Test recipe structure without database."""
    recipe, steps = create_simple_recipe()

    assert recipe.id.startswith("recipe-test-")
    assert len(steps) == 3
    assert all(step.recipe_id == recipe.id for step in steps)
```

## Unique ID Generation

All factories generate unique IDs using a combination of UUID and counter:

- **Recipes**: `recipe-test-{uuid}-{counter}`
- **Recipe Steps**: `step-test-{uuid}-{counter}`
- **Parameters**: `param-test-{uuid}-{counter}`
- **Recipe Commands**: `cmd-test-{uuid}-{counter}`
- **Parameter Commands**: `param-cmd-test-{uuid}-{counter}`

The UUID portion ensures global uniqueness, while the counter provides easy identification during debugging.

## Modbus Address Allocation

ParameterFactory automatically allocates unique Modbus addresses starting from 1000 to avoid conflicts with real system addresses.

## Data Types

### Parameter Data Types
- `float`: Floating-point values (temperature, pressure, flow)
- `integer`: Integer values (counts, steps, cycles)
- `binary`: Binary values (valve states, 0 or 1)

### Recipe Step Types
- `valve`: Valve control steps
- `purge`: Gas purge steps
- `loop`: Loop containers for repeating steps
- `set parameter`: Parameter write steps

### Command Types
- `start_recipe`: Start recipe execution
- `stop_recipe`: Stop recipe execution

### Command Status Values
- `pending`: Command created, not yet executed
- `queued`: Command queued for execution
- `executing`: Command currently executing
- `completed`: Command completed successfully
- `failed`: Command failed with error

## Best Practices

1. **Always cleanup test data** after tests to avoid database pollution
2. **Use unique machine_id** for each test to avoid conflicts
3. **Use convenience functions** for simple cases, factory classes for complex scenarios
4. **Seed faker** is set to 42 for reproducible randomization
5. **Validate constraints** when creating parameters with min/max values
6. **Use async database methods** for non-blocking I/O operations

## Examples

See `verify_factories.py` for comprehensive usage examples and verification tests.
