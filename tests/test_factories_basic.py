"""
Basic tests to verify factory functionality.

This module tests that all factories can be imported and generate valid data.
"""

import pytest
from tests.factories import (
    # Recipe factories
    RecipeFactory, Recipe, RecipeStep,
    create_simple_recipe, create_complex_recipe, create_recipe_with_parameters,
    # Parameter factories
    ParameterFactory, Parameter, ParameterValue,
    create_test_parameters, create_safety_critical_parameter, create_ald_parameter_set,
    # Command factories
    RecipeCommandFactory, ParameterCommandFactory, RecipeCommand, ParameterCommand,
    create_start_recipe_command, create_stop_recipe_command, create_parameter_write_command,
)


class TestRecipeFactory:
    """Test recipe factory functionality."""

    def test_create_simple_recipe(self):
        """Test simple recipe creation."""
        recipe, steps = create_simple_recipe()

        assert recipe is not None
        assert isinstance(recipe, Recipe)
        assert recipe.id.startswith("recipe-test-")
        assert len(steps) == 3
        assert all(isinstance(step, RecipeStep) for step in steps)
        assert all(step.recipe_id == recipe.id for step in steps)

    def test_create_complex_recipe(self):
        """Test complex recipe creation."""
        recipe, steps = create_complex_recipe(loop_count=5)

        assert recipe is not None
        assert isinstance(recipe, Recipe)
        assert len(steps) > 10
        # Should have loop steps
        assert any(step.type == "loop" for step in steps)

    def test_create_recipe_with_parameters(self):
        """Test recipe with parameter steps."""
        recipe, steps = create_recipe_with_parameters()

        assert recipe is not None
        assert len(steps) == 4
        # Should have parameter set steps
        assert any(step.type == "set parameter" for step in steps)

    def test_factory_class_usage(self):
        """Test using RecipeFactory class directly."""
        factory = RecipeFactory(machine_id="custom-machine")
        recipe, steps = factory.create_simple_recipe(name="Custom Recipe")

        assert recipe.name == "Custom Recipe"
        assert len(steps) == 3

    def test_unique_ids(self):
        """Test that factories generate unique IDs."""
        recipe1, _ = create_simple_recipe()
        recipe2, _ = create_simple_recipe()

        assert recipe1.id != recipe2.id


class TestParameterFactory:
    """Test parameter factory functionality."""

    def test_create_test_parameters(self):
        """Test bulk parameter creation."""
        params = create_test_parameters(count=5)

        assert len(params) == 5
        assert all(isinstance(p, Parameter) for p in params)
        assert all(p.id.startswith("param-test-") for p in params)

    def test_create_safety_critical_parameter(self):
        """Test safety-critical parameter creation."""
        param = create_safety_critical_parameter(name="SafetyTemp", min_value=0.0, max_value=600.0)

        assert param.is_safety_critical is True
        assert param.min_value == 0.0
        assert param.max_value == 600.0

    def test_create_ald_parameter_set(self):
        """Test ALD parameter set creation."""
        params = create_ald_parameter_set()

        assert len(params) == 10
        # Should have temperature, pressure, valves, flows
        param_names = [p.name for p in params]
        assert "Temperature" in param_names
        assert "Pressure" in param_names

    def test_factory_class_usage(self):
        """Test using ParameterFactory class directly."""
        factory = ParameterFactory(machine_id="custom-machine")
        temp = factory.create_temperature_parameter(0.0, 500.0)

        assert temp.name == "Temperature"
        assert temp.unit == "°C"
        assert temp.min_value == 0.0
        assert temp.max_value == 500.0

    def test_unique_ids_and_addresses(self):
        """Test that factories generate unique IDs and Modbus addresses."""
        factory = ParameterFactory()
        param1 = factory.create_temperature_parameter()
        param2 = factory.create_pressure_parameter()

        assert param1.id != param2.id
        assert param1.modbus_address != param2.modbus_address


class TestCommandFactory:
    """Test command factory functionality."""

    def test_create_start_recipe_command(self):
        """Test start recipe command creation."""
        cmd = create_start_recipe_command(recipe_id="test-recipe-123")

        assert isinstance(cmd, RecipeCommand)
        assert cmd.type == "start_recipe"
        assert cmd.status == "pending"
        assert cmd.parameters["recipe_id"] == "test-recipe-123"
        assert cmd.id.startswith("cmd-test-")

    def test_create_stop_recipe_command(self):
        """Test stop recipe command creation."""
        cmd = create_stop_recipe_command()

        assert isinstance(cmd, RecipeCommand)
        assert cmd.type == "stop_recipe"
        assert cmd.status == "pending"

    def test_create_parameter_write_command(self):
        """Test parameter write command creation."""
        cmd = create_parameter_write_command(
            parameter_name="Temperature",
            target_value=250.0
        )

        assert isinstance(cmd, ParameterCommand)
        assert cmd.parameter_name == "Temperature"
        assert cmd.target_value == 250.0
        assert cmd.id.startswith("param-cmd-test-")

    def test_recipe_command_factory_class(self):
        """Test RecipeCommandFactory class usage."""
        factory = RecipeCommandFactory(machine_id="custom-machine")

        # Test start command
        start_cmd = factory.create_start_recipe_command("recipe-456")
        assert start_cmd.machine_id == "custom-machine"

        # Test global command
        global_cmd = factory.create_global_command("recipe-789")
        assert global_cmd.machine_id is None

    def test_parameter_command_factory_class(self):
        """Test ParameterCommandFactory class usage."""
        factory = ParameterCommandFactory(machine_id="custom-machine")

        # Test parameter write by name
        cmd1 = factory.create_parameter_write_command(parameter_name="Pressure", target_value=100.0)
        assert cmd1.parameter_name == "Pressure"

        # Test parameter write by ID
        cmd2 = factory.create_parameter_write_command(component_parameter_id="param-123", target_value=50.0)
        assert cmd2.component_parameter_id == "param-123"

        # Test direct address
        cmd3 = factory.create_command_with_address(modbus_address=2000, target_value=75.0)
        assert cmd3.modbus_address == 2000

    def test_command_state_transitions(self):
        """Test command state transition methods."""
        factory = RecipeCommandFactory()
        cmd = factory.create_start_recipe_command("recipe-abc")

        # Mark executing
        cmd = factory.mark_executing(cmd)
        assert cmd.status == "executing"
        assert cmd.executed_at is not None

        # Mark completed
        cmd = factory.mark_completed(cmd)
        assert cmd.status == "completed"
        assert cmd.completed_at is not None

    def test_unique_ids(self):
        """Test that factories generate unique command IDs."""
        cmd1 = create_start_recipe_command("recipe-1")
        cmd2 = create_start_recipe_command("recipe-2")

        assert cmd1.id != cmd2.id


class TestDataStructures:
    """Test data structure serialization."""

    def test_recipe_to_dict(self):
        """Test Recipe to_dict conversion."""
        recipe, _ = create_simple_recipe()
        data = recipe.to_dict()

        assert isinstance(data, dict)
        assert "id" in data
        assert "name" in data
        assert "version" in data

    def test_parameter_to_dict(self):
        """Test Parameter to_dict conversion."""
        param = create_safety_critical_parameter()
        data = param.to_dict()

        assert isinstance(data, dict)
        assert "id" in data
        assert "name" in data
        assert "is_safety_critical" in data

    def test_command_to_dict(self):
        """Test command to_dict conversion."""
        cmd = create_start_recipe_command("recipe-xyz")
        data = cmd.to_dict()

        assert isinstance(data, dict)
        assert "id" in data
        assert "type" in data
        assert "parameters" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
