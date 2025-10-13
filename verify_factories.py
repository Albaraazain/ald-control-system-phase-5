"""
Simple verification script for factory functionality.
Runs without pytest to verify factories work correctly.
"""

import sys
from tests.factories import (
    # Recipe factories
    RecipeFactory, create_simple_recipe, create_complex_recipe, create_recipe_with_parameters,
    # Parameter factories
    ParameterFactory, create_test_parameters, create_safety_critical_parameter, create_ald_parameter_set,
    # Command factories
    RecipeCommandFactory, ParameterCommandFactory,
    create_start_recipe_command, create_stop_recipe_command, create_parameter_write_command,
)


def test_recipe_factories():
    """Test recipe factory functionality."""
    print("Testing Recipe Factories...")

    # Test simple recipe
    recipe, steps = create_simple_recipe()
    assert recipe.id.startswith("recipe-test-"), "Recipe ID should start with 'recipe-test-'"
    assert len(steps) == 3, f"Expected 3 steps, got {len(steps)}"
    print(f"  ✓ Simple recipe created: {recipe.name} with {len(steps)} steps")

    # Test complex recipe
    recipe, steps = create_complex_recipe(loop_count=5)
    assert len(steps) >= 10, f"Expected >=10 steps, got {len(steps)}"
    assert any(step.type == "loop" for step in steps), "Should have loop steps"
    print(f"  ✓ Complex recipe created: {recipe.name} with {len(steps)} steps")

    # Test recipe with parameters
    recipe, steps = create_recipe_with_parameters()
    assert len(steps) == 4, f"Expected 4 steps, got {len(steps)}"
    assert any(step.type == "set parameter" for step in steps), "Should have parameter steps"
    print(f"  ✓ Recipe with parameters created: {recipe.name}")

    # Test factory class
    factory = RecipeFactory(machine_id="test-machine")
    recipe1, _ = factory.create_simple_recipe()
    recipe2, _ = factory.create_simple_recipe()
    assert recipe1.id != recipe2.id, "Recipe IDs should be unique"
    print(f"  ✓ Unique IDs verified: {recipe1.id} != {recipe2.id}")

    print("✅ Recipe Factories: PASSED\n")


def test_parameter_factories():
    """Test parameter factory functionality."""
    print("Testing Parameter Factories...")

    # Test bulk parameters
    params = create_test_parameters(count=5)
    assert len(params) == 5, f"Expected 5 parameters, got {len(params)}"
    assert all(p.id.startswith("param-test-") for p in params), "All IDs should start with 'param-test-'"
    print(f"  ✓ Created {len(params)} test parameters")

    # Test safety-critical parameter
    param = create_safety_critical_parameter(name="SafetyTemp", min_value=0.0, max_value=600.0)
    assert param.is_safety_critical is True, "Should be safety-critical"
    assert param.min_value == 0.0 and param.max_value == 600.0, "Bounds should match"
    print(f"  ✓ Safety-critical parameter created: {param.name}")

    # Test ALD parameter set
    params = create_ald_parameter_set()
    assert len(params) == 10, f"Expected 10 ALD parameters, got {len(params)}"
    param_names = [p.name for p in params]
    assert "Temperature" in param_names, "Should have Temperature"
    assert "Pressure" in param_names, "Should have Pressure"
    print(f"  ✓ ALD parameter set created with {len(params)} parameters")

    # Test factory class
    factory = ParameterFactory()
    temp = factory.create_temperature_parameter(0.0, 500.0)
    pressure = factory.create_pressure_parameter(0.0, 100.0)
    assert temp.id != pressure.id, "IDs should be unique"
    assert temp.modbus_address != pressure.modbus_address, "Modbus addresses should be unique"
    print(f"  ✓ Unique IDs and addresses verified")

    print("✅ Parameter Factories: PASSED\n")


def test_command_factories():
    """Test command factory functionality."""
    print("Testing Command Factories...")

    # Test recipe commands
    start_cmd = create_start_recipe_command(recipe_id="test-recipe-123")
    assert start_cmd.type == "start_recipe", f"Expected 'start_recipe', got {start_cmd.type}"
    assert start_cmd.status == "pending", f"Expected 'pending', got {start_cmd.status}"
    assert start_cmd.id.startswith("cmd-test-"), "Command ID should start with 'cmd-test-'"
    print(f"  ✓ Start recipe command created: {start_cmd.id}")

    stop_cmd = create_stop_recipe_command()
    assert stop_cmd.type == "stop_recipe", f"Expected 'stop_recipe', got {stop_cmd.type}"
    print(f"  ✓ Stop recipe command created: {stop_cmd.id}")

    # Test parameter commands
    param_cmd = create_parameter_write_command(parameter_name="Temperature", target_value=250.0)
    assert param_cmd.parameter_name == "Temperature", "Parameter name should match"
    assert param_cmd.target_value == 250.0, "Target value should match"
    assert param_cmd.id.startswith("param-cmd-test-"), "Command ID should start with 'param-cmd-test-'"
    print(f"  ✓ Parameter write command created: {param_cmd.id}")

    # Test factory classes
    recipe_factory = RecipeCommandFactory(machine_id="custom-machine")
    cmd1 = recipe_factory.create_start_recipe_command("recipe-456")
    assert cmd1.machine_id == "custom-machine", "Machine ID should match"

    global_cmd = recipe_factory.create_global_command("recipe-789")
    assert global_cmd.machine_id is None, "Global command should have NULL machine_id"
    print(f"  ✓ Global command created: {global_cmd.id}")

    # Test parameter factory
    param_factory = ParameterCommandFactory()
    cmd_by_name = param_factory.create_parameter_write_command(parameter_name="Pressure", target_value=100.0)
    cmd_by_id = param_factory.create_parameter_write_command(component_parameter_id="param-123", target_value=50.0)
    cmd_by_addr = param_factory.create_command_with_address(modbus_address=2000, target_value=75.0)
    print(f"  ✓ Parameter commands by name/ID/address created")

    # Test state transitions
    cmd = recipe_factory.create_start_recipe_command("recipe-abc")
    cmd = recipe_factory.mark_executing(cmd)
    assert cmd.status == "executing", "Status should be 'executing'"
    assert cmd.executed_at is not None, "Should have executed_at timestamp"
    cmd = recipe_factory.mark_completed(cmd)
    assert cmd.status == "completed", "Status should be 'completed'"
    assert cmd.completed_at is not None, "Should have completed_at timestamp"
    print(f"  ✓ Command state transitions verified")

    # Test unique IDs
    cmd1 = create_start_recipe_command("recipe-1")
    cmd2 = create_start_recipe_command("recipe-2")
    assert cmd1.id != cmd2.id, "Command IDs should be unique"
    print(f"  ✓ Unique command IDs verified")

    print("✅ Command Factories: PASSED\n")


def test_data_serialization():
    """Test data structure serialization."""
    print("Testing Data Serialization...")

    # Test recipe to_dict
    recipe, steps = create_simple_recipe()
    recipe_dict = recipe.to_dict()
    assert isinstance(recipe_dict, dict), "Should return dict"
    assert "id" in recipe_dict and "name" in recipe_dict, "Should have required fields"
    print(f"  ✓ Recipe to_dict works")

    step_dict = steps[0].to_dict()
    assert isinstance(step_dict, dict), "Should return dict"
    assert "id" in step_dict and "type" in step_dict, "Should have required fields"
    print(f"  ✓ RecipeStep to_dict works")

    # Test parameter to_dict
    param = create_safety_critical_parameter()
    param_dict = param.to_dict()
    assert isinstance(param_dict, dict), "Should return dict"
    assert "id" in param_dict and "is_safety_critical" in param_dict, "Should have required fields"
    print(f"  ✓ Parameter to_dict works")

    # Test command to_dict
    cmd = create_start_recipe_command("recipe-xyz")
    cmd_dict = cmd.to_dict()
    assert isinstance(cmd_dict, dict), "Should return dict"
    assert "id" in cmd_dict and "type" in cmd_dict, "Should have required fields"
    print(f"  ✓ Command to_dict works")

    print("✅ Data Serialization: PASSED\n")


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("FACTORY VERIFICATION TESTS")
    print("=" * 60 + "\n")

    try:
        test_recipe_factories()
        test_parameter_factories()
        test_command_factories()
        test_data_serialization()

        print("=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
