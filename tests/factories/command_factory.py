"""
Command data factory for generating test commands (recipe and parameter).

This module provides factories for creating recipe commands and parameter
control commands for testing command processing flows.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from faker import Faker

fake = Faker()
Faker.seed(42)


@dataclass
class RecipeCommand:
    """Recipe command data structure."""
    id: str
    type: str  # 'start_recipe', 'stop_recipe'
    status: str  # 'pending', 'queued', 'executing', 'completed', 'failed'
    machine_id: Optional[str]
    parameters: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


@dataclass
class ParameterCommand:
    """Parameter control command data structure."""
    id: str
    parameter_name: Optional[str]
    component_parameter_id: Optional[str]
    target_value: float
    machine_id: Optional[str]
    timeout_ms: int = 5000
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    modbus_address: Optional[int] = None
    data_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


class RecipeCommandFactory:
    """Factory for generating recipe commands."""

    def __init__(self, machine_id: str = "test-machine"):
        """Initialize factory with machine ID."""
        self.machine_id = machine_id
        self._command_counter = 0

    def _generate_command_id(self) -> str:
        """Generate unique command ID."""
        self._command_counter += 1
        return f"cmd-test-{uuid.uuid4().hex[:8]}-{self._command_counter}"

    def create_start_recipe_command(
        self,
        recipe_id: str,
        status: str = 'pending',
        machine_id: Optional[str] = None
    ) -> RecipeCommand:
        """Create a start recipe command."""
        return RecipeCommand(
            id=self._generate_command_id(),
            type='start_recipe',
            status=status,
            machine_id=machine_id or self.machine_id,
            parameters={"recipe_id": recipe_id}
        )

    def create_stop_recipe_command(
        self,
        status: str = 'pending',
        machine_id: Optional[str] = None
    ) -> RecipeCommand:
        """Create a stop recipe command."""
        return RecipeCommand(
            id=self._generate_command_id(),
            type='stop_recipe',
            status=status,
            machine_id=machine_id or self.machine_id,
            parameters={}
        )

    def create_global_command(self, recipe_id: str, command_type: str = 'start_recipe') -> RecipeCommand:
        """Create a global command (NULL machine_id)."""
        return RecipeCommand(
            id=self._generate_command_id(),
            type=command_type,
            status='pending',
            machine_id=None,  # Global command
            parameters={"recipe_id": recipe_id} if command_type == 'start_recipe' else {}
        )

    def mark_executing(self, command: RecipeCommand) -> RecipeCommand:
        """Mark command as executing."""
        command.status = 'executing'
        command.executed_at = datetime.now(timezone.utc).isoformat()
        return command

    def mark_completed(self, command: RecipeCommand) -> RecipeCommand:
        """Mark command as completed."""
        command.status = 'completed'
        command.completed_at = datetime.now(timezone.utc).isoformat()
        return command

    def mark_failed(self, command: RecipeCommand, error: str) -> RecipeCommand:
        """Mark command as failed."""
        command.status = 'failed'
        command.completed_at = datetime.now(timezone.utc).isoformat()
        command.error_message = error
        return command

    async def insert_command(self, supabase_client, command: RecipeCommand) -> Dict[str, Any]:
        """Insert recipe command into database."""
        result = supabase_client.table("recipe_commands").insert(command.to_dict()).execute()
        return result.data[0] if result.data else None

    async def cleanup_test_commands(self, supabase_client, command_ids: Optional[List[str]] = None):
        """Clean up test recipe commands."""
        if command_ids:
            for cmd_id in command_ids:
                supabase_client.table("recipe_commands").delete().eq("id", cmd_id).execute()
        else:
            # Delete all test commands
            supabase_client.table("recipe_commands").delete().like("id", "cmd-test-%").execute()

    # Alias methods for test compatibility
    def create_recipe_command(self, recipe_id: str, machine_id: Optional[str] = None) -> RecipeCommand:
        """Alias for create_start_recipe_command - creates a start recipe command."""
        return self.create_start_recipe_command(recipe_id, machine_id=machine_id)

    def insert_to_database(self, command: RecipeCommand, supabase):
        """Synchronous alias for insert_command - inserts recipe command to database."""
        result = supabase.table("recipe_commands").insert(command.to_dict()).execute()
        return result.data[0] if result.data else None


class ParameterCommandFactory:
    """Factory for generating parameter control commands."""

    def __init__(self, machine_id: str = "test-machine"):
        """Initialize factory with machine ID."""
        self.machine_id = machine_id
        self._command_counter = 0

    def _generate_command_id(self) -> str:
        """Generate unique command ID."""
        self._command_counter += 1
        return f"param-cmd-test-{uuid.uuid4().hex[:8]}-{self._command_counter}"

    def create_parameter_write_command(
        self,
        parameter_name: Optional[str] = None,
        component_parameter_id: Optional[str] = None,
        target_value: float = 100.0,
        machine_id: Optional[str] = None,
        timeout_ms: int = 5000
    ) -> ParameterCommand:
        """
        Create a parameter write command.

        Either parameter_name OR component_parameter_id must be provided.
        """
        return ParameterCommand(
            id=self._generate_command_id(),
            parameter_name=parameter_name,
            component_parameter_id=component_parameter_id,
            target_value=target_value,
            machine_id=machine_id or self.machine_id,
            timeout_ms=timeout_ms
        )

    def create_global_parameter_command(
        self,
        parameter_name: str,
        target_value: float
    ) -> ParameterCommand:
        """Create global parameter command (NULL machine_id)."""
        return ParameterCommand(
            id=self._generate_command_id(),
            parameter_name=parameter_name,
            component_parameter_id=None,
            target_value=target_value,
            machine_id=None  # Global
        )

    def create_command_with_address(
        self,
        modbus_address: int,
        target_value: float,
        data_type: str = 'float'
    ) -> ParameterCommand:
        """Create command with direct Modbus address override."""
        return ParameterCommand(
            id=self._generate_command_id(),
            parameter_name=None,
            component_parameter_id=None,
            target_value=target_value,
            machine_id=self.machine_id,
            modbus_address=modbus_address,
            data_type=data_type
        )

    def create_out_of_range_command(
        self,
        parameter_name: str,
        target_value: float,
        # Value should be out of param's min/max
    ) -> ParameterCommand:
        """Create command with out-of-range value (for testing validation)."""
        return ParameterCommand(
            id=self._generate_command_id(),
            parameter_name=parameter_name,
            component_parameter_id=None,
            target_value=target_value,
            machine_id=self.machine_id
        )

    def mark_executing(self, command: ParameterCommand) -> ParameterCommand:
        """Mark command as executing (executed_at set)."""
        command.executed_at = datetime.now(timezone.utc).isoformat()
        return command

    def mark_completed(self, command: ParameterCommand) -> ParameterCommand:
        """Mark command as completed."""
        command.completed_at = datetime.now(timezone.utc).isoformat()
        return command

    def mark_failed(self, command: ParameterCommand, error: str) -> ParameterCommand:
        """Mark command as failed."""
        command.completed_at = datetime.now(timezone.utc).isoformat()
        command.error_message = error
        return command

    async def insert_command(self, supabase_client, command: ParameterCommand) -> Dict[str, Any]:
        """Insert parameter command into database."""
        result = supabase_client.table("parameter_control_commands").insert(command.to_dict()).execute()
        return result.data[0] if result.data else None

    async def cleanup_test_commands(self, supabase_client, command_ids: Optional[List[str]] = None):
        """Clean up test parameter commands."""
        if command_ids:
            for cmd_id in command_ids:
                supabase_client.table("parameter_control_commands").delete().eq("id", cmd_id).execute()
        else:
            # Delete all test commands
            supabase_client.table("parameter_control_commands").delete().like("id", "param-cmd-test-%").execute()

    # Alias methods for test compatibility
    def create_parameter_command(
        self,
        parameter_name: str,
        target_value: float,
        machine_id: Optional[str] = None
    ) -> ParameterCommand:
        """Alias for create_parameter_write_command - creates a parameter write command."""
        return self.create_parameter_write_command(
            parameter_name=parameter_name,
            target_value=target_value,
            machine_id=machine_id
        )

    def create_safety_critical_command(
        self,
        parameter_name: str,
        out_of_bounds_value: float
    ) -> ParameterCommand:
        """Alias for create_out_of_range_command - creates safety-critical test command."""
        return self.create_out_of_range_command(parameter_name, out_of_bounds_value)

    def insert_to_database(self, command: ParameterCommand, supabase):
        """Synchronous alias for insert_command - inserts parameter command to database."""
        result = supabase.table("parameter_control_commands").insert(command.to_dict()).execute()
        return result.data[0] if result.data else None


# Convenience functions
def create_start_recipe_command(recipe_id: str, machine_id: str = "test-machine") -> RecipeCommand:
    """Convenience function to create start recipe command."""
    factory = RecipeCommandFactory(machine_id)
    return factory.create_start_recipe_command(recipe_id)


def create_stop_recipe_command(machine_id: str = "test-machine") -> RecipeCommand:
    """Convenience function to create stop recipe command."""
    factory = RecipeCommandFactory(machine_id)
    return factory.create_stop_recipe_command()


def create_parameter_write_command(
    parameter_name: str,
    target_value: float,
    machine_id: str = "test-machine"
) -> ParameterCommand:
    """Convenience function to create parameter write command."""
    factory = ParameterCommandFactory(machine_id)
    return factory.create_parameter_write_command(parameter_name=parameter_name, target_value=target_value)
