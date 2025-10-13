"""
Recipe data factory for generating test recipes, steps, and commands.

This module provides factories for creating realistic recipe test data
with proper database relationships and randomized content.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from faker import Faker

fake = Faker()
Faker.seed(42)  # Consistent randomization for reproducibility


@dataclass
class RecipeStep:
    """Recipe step data structure."""
    id: str
    recipe_id: str
    sequence_number: int
    type: str
    name: str
    parameters: Dict[str, Any]
    parent_step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


@dataclass
class Recipe:
    """Recipe data structure."""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


class RecipeFactory:
    """Factory for generating test recipes with various patterns."""

    def __init__(self, machine_id: str = "test-machine"):
        """Initialize factory with machine ID."""
        self.machine_id = machine_id
        self._recipe_counter = 0
        self._step_counter = 0

    def _generate_recipe_id(self) -> str:
        """Generate unique recipe ID."""
        self._recipe_counter += 1
        return f"recipe-test-{uuid.uuid4().hex[:8]}-{self._recipe_counter}"

    def _generate_step_id(self) -> str:
        """Generate unique step ID."""
        self._step_counter += 1
        return f"step-test-{uuid.uuid4().hex[:8]}-{self._step_counter}"

    def create_simple_recipe(self, name: Optional[str] = None) -> tuple[Recipe, List[RecipeStep]]:
        """
        Create a simple 3-step recipe (valve, purge, valve).

        Returns:
            tuple[Recipe, List[RecipeStep]]: Recipe and its steps
        """
        recipe_id = self._generate_recipe_id()
        recipe_name = name or f"Simple Test Recipe {fake.word().title()}"

        recipe = Recipe(
            id=recipe_id,
            name=recipe_name,
            version="1.0",
            description="Simple 3-step test recipe for basic execution testing"
        )

        steps = [
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=1,
                type="valve",
                name="Open Valve 1",
                parameters={"valve_number": 1, "state": "open", "duration_ms": 5000}
            ),
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=2,
                type="purge",
                name="Purge with N2",
                parameters={"gas_type": "N2", "duration_ms": 10000}
            ),
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=3,
                type="valve",
                name="Close Valve 1",
                parameters={"valve_number": 1, "state": "close", "duration_ms": 0}
            )
        ]

        return recipe, steps

    def create_complex_recipe(self, name: Optional[str] = None, loop_count: int = 10) -> tuple[Recipe, List[RecipeStep]]:
        """
        Create a complex recipe with 10+ steps including loops.

        Simulates ALD deposition recipe with precursor/oxidant cycles.

        Args:
            name: Optional recipe name
            loop_count: Number of deposition cycles (default: 10)

        Returns:
            tuple[Recipe, List[RecipeStep]]: Recipe and its steps
        """
        recipe_id = self._generate_recipe_id()
        recipe_name = name or f"ALD Deposition Recipe {fake.word().title()}"

        recipe = Recipe(
            id=recipe_id,
            name=recipe_name,
            version="2.0",
            description=f"Complex ALD recipe with {loop_count} deposition cycles"
        )

        steps = []
        seq = 1

        # Step 1: Initialization
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="valve",
            name="Initialize Chamber",
            parameters={"valve_number": 1, "state": "open", "duration_ms": 1000}
        ))
        seq += 1

        # Step 2: Main deposition loop
        loop_step_id = self._generate_step_id()
        steps.append(RecipeStep(
            id=loop_step_id,
            recipe_id=recipe_id,
            sequence_number=seq,
            type="loop",
            name="Deposition Loop",
            parameters={"count": loop_count}
        ))
        seq += 1

        # Loop children: Precursor pulse
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="valve",
            name="Precursor Pulse",
            parameters={"valve_number": 3, "state": "pulse", "duration_ms": 500},
            parent_step_id=loop_step_id
        ))
        seq += 1

        # Loop children: First purge
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="purge",
            name="Purge 1",
            parameters={"gas_type": "N2", "duration_ms": 3000},
            parent_step_id=loop_step_id
        ))
        seq += 1

        # Loop children: Oxidant pulse
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="valve",
            name="Oxidant Pulse",
            parameters={"valve_number": 4, "state": "pulse", "duration_ms": 500},
            parent_step_id=loop_step_id
        ))
        seq += 1

        # Loop children: Second purge
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="purge",
            name="Purge 2",
            parameters={"gas_type": "N2", "duration_ms": 3000},
            parent_step_id=loop_step_id
        ))
        seq += 1

        # Step 7: Anneal loop
        anneal_loop_id = self._generate_step_id()
        steps.append(RecipeStep(
            id=anneal_loop_id,
            recipe_id=recipe_id,
            sequence_number=seq,
            type="loop",
            name="Anneal Loop",
            parameters={"count": 3}
        ))
        seq += 1

        # Anneal children: Set temperature
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="set parameter",
            name="Set Temp High",
            parameters={"parameter_name": "Temperature", "value": 500.0},
            parent_step_id=anneal_loop_id
        ))
        seq += 1

        # Anneal children: Hold
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="purge",
            name="Anneal Hold",
            parameters={"gas_type": "Ar", "duration_ms": 5000},
            parent_step_id=anneal_loop_id
        ))
        seq += 1

        # Final step: Finalize
        steps.append(RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=seq,
            type="valve",
            name="Finalize",
            parameters={"valve_number": 1, "state": "close", "duration_ms": 0}
        ))

        return recipe, steps

    def create_recipe_with_loops(self, name: Optional[str] = None, iterations: int = 3) -> tuple[Recipe, List[RecipeStep]]:
        """
        Create recipe with loop iterations.

        Alias for create_complex_recipe() to match test expectations.

        Args:
            name: Optional recipe name
            iterations: Number of loop iterations (default: 3)

        Returns:
            tuple[Recipe, List[RecipeStep]]: Recipe with loops
        """
        return self.create_complex_recipe(name=name, loop_count=iterations)

    def create_recipe_with_parameters(self, name: Optional[str] = None) -> tuple[Recipe, List[RecipeStep]]:
        """
        Create recipe with parameter substitution steps.

        Returns:
            tuple[Recipe, List[RecipeStep]]: Recipe with parameter steps
        """
        recipe_id = self._generate_recipe_id()
        recipe_name = name or f"Parameter Control Recipe {fake.word().title()}"

        recipe = Recipe(
            id=recipe_id,
            name=recipe_name,
            version="1.0",
            description="Recipe with parameter control steps"
        )

        steps = [
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=1,
                type="set parameter",
                name="Set Temperature",
                parameters={"parameter_name": "Temperature", "value": 250.0}
            ),
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=2,
                type="set parameter",
                name="Set Pressure",
                parameters={"parameter_name": "Pressure", "value": 100.0}
            ),
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=3,
                type="purge",
                name="Stabilize",
                parameters={"gas_type": "N2", "duration_ms": 5000}
            ),
            RecipeStep(
                id=self._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=4,
                type="set parameter",
                name="Reset Temperature",
                parameters={"parameter_name": "Temperature", "value": 25.0}
            )
        ]

        return recipe, steps

    def create_valve_step(self, recipe_id: str, sequence: int, valve_num: int,
                         duration_ms: int = 5000) -> RecipeStep:
        """Create a single valve step."""
        return RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=sequence,
            type="valve",
            name=f"Valve {valve_num} Step",
            parameters={"valve_number": valve_num, "duration_ms": duration_ms}
        )

    def create_purge_step(self, recipe_id: str, sequence: int,
                         gas_type: str = "N2", duration_ms: int = 10000) -> RecipeStep:
        """Create a single purge step."""
        return RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=sequence,
            type="purge",
            name=f"Purge with {gas_type}",
            parameters={"gas_type": gas_type, "duration_ms": duration_ms}
        )

    def create_loop_step(self, recipe_id: str, sequence: int,
                        count: int = 5) -> RecipeStep:
        """Create a loop step."""
        return RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=sequence,
            type="loop",
            name=f"Loop {count} iterations",
            parameters={"count": count}
        )

    def create_parameter_step(self, recipe_id: str, sequence: int,
                            parameter_name: str, value: float) -> RecipeStep:
        """Create a parameter set step."""
        return RecipeStep(
            id=self._generate_step_id(),
            recipe_id=recipe_id,
            sequence_number=sequence,
            type="set parameter",
            name=f"Set {parameter_name}",
            parameters={"parameter_name": parameter_name, "value": value}
        )

    async def insert_to_database(self, recipe: Recipe, steps: List[RecipeStep],
                                 supabase) -> Dict[str, Any]:
        """
        Insert recipe and steps into database.

        Alias for insert_recipe() to match test expectations.

        Args:
            recipe: Recipe to insert
            steps: Recipe steps to insert
            supabase: Supabase client instance

        Returns:
            Dict with inserted recipe and steps
        """
        return await self.insert_recipe(supabase, recipe, steps)

    async def insert_recipe(self, supabase_client, recipe: Recipe,
                           steps: List[RecipeStep]) -> Dict[str, Any]:
        """
        Insert recipe and steps into database.

        Args:
            supabase_client: Supabase client instance
            recipe: Recipe to insert
            steps: Recipe steps to insert

        Returns:
            Dict with inserted recipe and steps
        """
        # Insert recipe
        recipe_result = supabase_client.table("recipes").insert(recipe.to_dict()).execute()

        # Insert steps
        steps_data = [step.to_dict() for step in steps]
        steps_result = supabase_client.table("recipe_steps").insert(steps_data).execute()

        return {
            "recipe": recipe_result.data[0] if recipe_result.data else None,
            "steps": steps_result.data if steps_result.data else [],
            "step_count": len(steps)
        }

    async def cleanup_test_recipes(self, supabase_client, recipe_ids: Optional[List[str]] = None):
        """
        Clean up test recipes and related data.

        Args:
            supabase_client: Supabase client instance
            recipe_ids: Optional list of specific recipe IDs to delete
        """
        if recipe_ids:
            # Delete specific recipes
            for recipe_id in recipe_ids:
                # Delete recipe steps first (foreign key constraint)
                supabase_client.table("recipe_steps").delete().eq("recipe_id", recipe_id).execute()
                # Delete recipe
                supabase_client.table("recipes").delete().eq("id", recipe_id).execute()
        else:
            # Delete all test recipes (starts with "recipe-test-")
            test_recipes = supabase_client.table("recipes").select("id").like("id", "recipe-test-%").execute()

            for recipe in test_recipes.data:
                recipe_id = recipe["id"]
                supabase_client.table("recipe_steps").delete().eq("recipe_id", recipe_id).execute()
                supabase_client.table("recipes").delete().eq("id", recipe_id).execute()


# Convenience functions
def create_simple_recipe(machine_id: str = "test-machine") -> tuple[Recipe, List[RecipeStep]]:
    """Convenience function to create a simple recipe."""
    factory = RecipeFactory(machine_id)
    return factory.create_simple_recipe()


def create_complex_recipe(machine_id: str = "test-machine", loop_count: int = 10) -> tuple[Recipe, List[RecipeStep]]:
    """Convenience function to create a complex recipe."""
    factory = RecipeFactory(machine_id)
    return factory.create_complex_recipe(loop_count=loop_count)


def create_recipe_with_parameters(machine_id: str = "test-machine") -> tuple[Recipe, List[RecipeStep]]:
    """Convenience function to create a recipe with parameters."""
    factory = RecipeFactory(machine_id)
    return factory.create_recipe_with_parameters()
