"""
Test data factories for ALD Control System testing.

This module exports all factory classes and convenience functions for
creating test data including recipes, parameters, and commands.

Usage:
    from tests.factories import RecipeFactory, create_simple_recipe

    # Using factory classes
    factory = RecipeFactory()
    recipe, steps = factory.create_simple_recipe()

    # Using convenience functions
    recipe, steps = create_simple_recipe()

    # Creating commands
    from tests.factories import create_start_recipe_command
    command = create_start_recipe_command(recipe_id="recipe-123")
"""

# Recipe factories
from .recipe_factory import (
    RecipeFactory,
    Recipe,
    RecipeStep,
    create_simple_recipe,
    create_complex_recipe,
    create_recipe_with_parameters,
)

# Parameter factories
from .parameter_factory import (
    ParameterFactory,
    Parameter,
    ParameterValue,
    create_test_parameters,
    create_safety_critical_parameter,
    create_ald_parameter_set,
)

# Command factories
from .command_factory import (
    RecipeCommandFactory,
    ParameterCommandFactory,
    RecipeCommand,
    ParameterCommand,
    create_start_recipe_command,
    create_stop_recipe_command,
    create_parameter_write_command,
)

__all__ = [
    # Recipe factory classes
    "RecipeFactory",
    "Recipe",
    "RecipeStep",
    # Recipe convenience functions
    "create_simple_recipe",
    "create_complex_recipe",
    "create_recipe_with_parameters",
    # Parameter factory classes
    "ParameterFactory",
    "Parameter",
    "ParameterValue",
    # Parameter convenience functions
    "create_test_parameters",
    "create_safety_critical_parameter",
    "create_ald_parameter_set",
    # Command factory classes
    "RecipeCommandFactory",
    "ParameterCommandFactory",
    "RecipeCommand",
    "ParameterCommand",
    # Command convenience functions
    "create_start_recipe_command",
    "create_stop_recipe_command",
    "create_parameter_write_command",
]
