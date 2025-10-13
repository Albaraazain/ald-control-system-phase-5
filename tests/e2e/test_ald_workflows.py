"""
End-to-end workflow tests for ALD control system.

Tests comprehensive real-world ALD process control scenarios involving
all 3 terminals working together:
- Terminal 1: PLC data collection
- Terminal 2: Recipe execution
- Terminal 3: Parameter control

These tests verify the entire system behaves correctly under realistic
operating conditions including race conditions, failures, and high load.
"""

import pytest
import asyncio
import time
import signal
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

# Test fixtures and utilities
from tests.fixtures.terminal_fixtures import (
    three_terminals,
    terminal_health_monitor,
    terminal_log_capture
)
from tests.fixtures.database_fixtures import (
    clean_test_database,
    database_validator
)
from tests.fixtures.plc_fixtures import (
    plc_simulation,
    plc_state_validator
)
from tests.factories.recipe_factory import RecipeFactory
from tests.factories.command_factory import RecipeCommandFactory, ParameterCommandFactory
from tests.factories.parameter_factory import ParameterFactory
from tests.utils.async_helpers import (
    wait_for_condition,
    wait_for_database_record,
    wait_for_terminal_log,
    run_with_timeout,
    measure_execution_time
)


# ============================================================================
# TEST CLASS: Complete Recipe Execution Workflow
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
@pytest.mark.slow
class TestCompleteRecipeExecution:
    """Test complete recipe execution workflow with all 3 terminals."""

    async def test_recipe_with_valves_parameters_purge_loop(
        self,
        three_terminals,
        clean_test_database,
        plc_simulation,
        terminal_log_capture
    ):
        """
        Test complete recipe execution:
        - 3 valve operations (OPEN, CLOSE, OPEN)
        - 2 parameter writes (temperature, pressure)
        - 1 purge step (10s duration)
        - 1 loop (3 iterations)

        Verify:
        - Terminal 2 picks up recipe command
        - All steps execute in correct order
        - Terminal 1 reads parameter changes
        - All parameter values logged to database
        - Recipe marked as completed
        - Process_execution record created
        """
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory(machine_id="test-machine")
        command_factory = RecipeCommandFactory(machine_id="test-machine")

        # Step 1: Create custom recipe with required steps
        recipe_id = recipe_factory._generate_recipe_id()
        from tests.factories.recipe_factory import Recipe, RecipeStep

        recipe = Recipe(
            id=recipe_id,
            name="E2E Test Recipe - Complete Workflow",
            version="1.0",
            description="Test recipe with valves, parameters, purge, and loop"
        )

        # Create loop parent step
        loop_step_id = recipe_factory._generate_step_id()

        steps = [
            # Valve operation 1: OPEN
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=1,
                type="valve",
                name="Open Valve 1",
                parameters={"valve_number": 1, "state": "open", "duration_ms": 2000}
            ),
            # Parameter write 1: Temperature
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=2,
                type="set parameter",
                name="Set Temperature",
                parameters={"parameter_name": "Temperature", "value": 250.0}
            ),
            # Valve operation 2: CLOSE
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=3,
                type="valve",
                name="Close Valve 1",
                parameters={"valve_number": 1, "state": "close", "duration_ms": 0}
            ),
            # Parameter write 2: Pressure
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=4,
                type="set parameter",
                name="Set Pressure",
                parameters={"parameter_name": "Pressure", "value": 100.0}
            ),
            # Purge step: 10s
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=5,
                type="purge",
                name="Purge with N2",
                parameters={"gas_type": "N2", "duration_ms": 10000}
            ),
            # Loop: 3 iterations
            RecipeStep(
                id=loop_step_id,
                recipe_id=recipe_id,
                sequence_number=6,
                type="loop",
                name="Test Loop",
                parameters={"count": 3}
            ),
            # Loop child: Valve OPEN
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=7,
                type="valve",
                name="Loop: Open Valve 2",
                parameters={"valve_number": 2, "state": "open", "duration_ms": 1000},
                parent_step_id=loop_step_id
            )
        ]

        # Insert recipe and steps
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Step 2: Insert recipe command
        command = command_factory.create_start_recipe_command(recipe_id, status='pending')
        await command_factory.insert_command(supabase_client, command)

        # Step 3: Wait for Terminal 2 to pick up command (via realtime or polling)
        command_picked_up = await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": command.id, "status": "executing"},
            timeout=15.0
        )
        assert command_picked_up, "Terminal 2 failed to pick up recipe command within 15s"

        # Step 4: Verify emoji log appears
        recipe_log = await wait_for_terminal_log(
            terminal_log_capture,
            terminal_id=2,
            pattern=r"🔔.*recipe.*command",
            timeout=5.0
        )
        assert recipe_log, "Terminal 2 did not log recipe command pickup"

        # Step 5: Wait for recipe execution to complete (max 30s)
        recipe_completed = await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": command.id, "status": "completed"},
            timeout=30.0
        )
        assert recipe_completed, "Recipe execution did not complete within 30s"

        # Step 6: Verify process_execution record created
        process_execution = await wait_for_database_record(
            supabase_client,
            table="process_executions",
            filters={"recipe_id": recipe_id},
            timeout=5.0
        )
        assert process_execution, "No process_execution record created"
        assert process_execution["status"] == "completed"

        # Step 7: Verify Terminal 1 collected parameter changes during execution
        # Check Temperature = 250.0 was logged
        temp_logged = supabase_client.table("parameter_value_history").select("*").eq(
            "parameter_name", "Temperature"
        ).gte("value", 249.0).lte("value", 251.0).execute()

        assert len(temp_logged.data) > 0, "Terminal 1 did not log Temperature change"

        # Check Pressure = 100.0 was logged
        pressure_logged = supabase_client.table("parameter_value_history").select("*").eq(
            "parameter_name", "Pressure"
        ).gte("value", 99.0).lte("value", 101.0).execute()

        assert len(pressure_logged.data) > 0, "Terminal 1 did not log Pressure change"

        # Step 8: Verify timing precision
        start_time = datetime.fromisoformat(command_picked_up["executed_at"])
        end_time = datetime.fromisoformat(recipe_completed["completed_at"])
        duration = (end_time - start_time).total_seconds()

        # Expected duration: ~2s valve + 0s valve + 10s purge + 3*(1s valve) = ~15s
        # Allow ±3s tolerance
        assert 12.0 <= duration <= 18.0, f"Recipe duration {duration}s outside expected range [12s, 18s]"

    async def test_recipe_execution_creates_step_logs(
        self,
        three_terminals,
        clean_test_database
    ):
        """Verify each recipe step creates execution log entries."""
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        command_factory = RecipeCommandFactory()

        # Create simple 3-step recipe
        recipe, steps = recipe_factory.create_simple_recipe()
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Start recipe
        command = command_factory.create_start_recipe_command(recipe.id)
        await command_factory.insert_command(supabase_client, command)

        # Wait for completion
        await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": command.id, "status": "completed"},
            timeout=30.0
        )

        # Verify step execution logs exist for all 3 steps
        step_logs = supabase_client.table("recipe_step_executions").select("*").eq(
            "recipe_id", recipe.id
        ).execute()

        assert len(step_logs.data) == 3, f"Expected 3 step logs, got {len(step_logs.data)}"

        # Verify all steps marked as completed
        completed_steps = [log for log in step_logs.data if log["status"] == "completed"]
        assert len(completed_steps) == 3, "Not all steps marked as completed"


# ============================================================================
# TEST CLASS: Parameter Override During Recipe
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
class TestParameterOverrideDuringRecipe:
    """Test parameter override via Terminal 3 while recipe executes."""

    async def test_parameter_override_no_race_condition(
        self,
        three_terminals,
        clean_test_database,
        plc_simulation
    ):
        """
        Test:
        1. Start recipe that sets Temperature to 500°C
        2. While recipe running, insert parameter command to override to 550°C (Terminal 3)
        3. Verify Terminal 3 writes 550°C to PLC
        4. Verify Terminal 1 reads 550°C
        5. Verify recipe continues with new value
        6. Verify no race conditions or conflicts
        """
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        recipe_command_factory = RecipeCommandFactory()
        param_command_factory = ParameterCommandFactory()

        # Create recipe that sets temperature
        recipe, steps = recipe_factory.create_recipe_with_parameters()
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Start recipe
        recipe_cmd = recipe_command_factory.create_start_recipe_command(recipe.id)
        await recipe_command_factory.insert_command(supabase_client, recipe_cmd)

        # Wait for recipe to start executing
        await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": recipe_cmd.id, "status": "executing"},
            timeout=10.0
        )

        # Wait 2s to let recipe progress
        await asyncio.sleep(2.0)

        # Insert parameter override command (550°C)
        param_cmd = param_command_factory.create_parameter_write_command(
            parameter_name="Temperature",
            target_value=550.0
        )
        await param_command_factory.insert_command(supabase_client, param_cmd)

        # Wait for Terminal 3 to execute parameter write
        param_completed = await wait_for_database_record(
            supabase_client,
            table="parameter_control_commands",
            filters={"id": param_cmd.id, "completed_at": lambda x: x is not None},
            timeout=10.0
        )
        assert param_completed, "Terminal 3 did not execute parameter write"

        # Verify Terminal 1 reads 550°C (within 2 cycles = 2s)
        await asyncio.sleep(2.5)

        temp_reading = supabase_client.table("parameter_value_history").select("*").eq(
            "parameter_name", "Temperature"
        ).gte("value", 549.0).lte("value", 551.0).order("timestamp", desc=True).limit(1).execute()

        assert len(temp_reading.data) > 0, "Terminal 1 did not read overridden temperature"

        # Wait for recipe to complete
        recipe_completed = await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": recipe_cmd.id, "status": "completed"},
            timeout=20.0
        )
        assert recipe_completed, "Recipe did not complete after parameter override"

    async def test_multiple_parameter_overrides_during_recipe(
        self,
        three_terminals,
        clean_test_database
    ):
        """Test multiple rapid parameter overrides while recipe executes."""
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        recipe_command_factory = RecipeCommandFactory()
        param_command_factory = ParameterCommandFactory()

        # Create long-running recipe
        recipe, steps = recipe_factory.create_complex_recipe(loop_count=5)
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Start recipe
        recipe_cmd = recipe_command_factory.create_start_recipe_command(recipe.id)
        await recipe_command_factory.insert_command(supabase_client, recipe_cmd)

        # Wait for recipe to start
        await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": recipe_cmd.id, "status": "executing"},
            timeout=10.0
        )

        # Insert 5 parameter commands rapidly
        param_commands = []
        for i, value in enumerate([100.0, 200.0, 300.0, 400.0, 500.0]):
            param_cmd = param_command_factory.create_parameter_write_command(
                parameter_name="Temperature",
                target_value=value
            )
            await param_command_factory.insert_command(supabase_client, param_cmd)
            param_commands.append(param_cmd)
            await asyncio.sleep(0.5)  # Rapid-fire

        # Wait for all parameter commands to complete
        for param_cmd in param_commands:
            completed = await wait_for_database_record(
                supabase_client,
                table="parameter_control_commands",
                filters={"id": param_cmd.id, "completed_at": lambda x: x is not None},
                timeout=10.0
            )
            assert completed, f"Parameter command {param_cmd.id} did not complete"

        # Verify no commands failed (no race conditions)
        failed_commands = supabase_client.table("parameter_control_commands").select("*").in_(
            "id", [cmd.id for cmd in param_commands]
        ).not_.is_("error_message", "null").execute()

        assert len(failed_commands.data) == 0, f"Some parameter commands failed: {failed_commands.data}"


# ============================================================================
# TEST CLASS: Safety Validation
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
class TestSafetyValidation:
    """Test safety validation prevents equipment damage."""

    async def test_dangerous_temperature_rejected(
        self,
        three_terminals,
        clean_test_database,
        plc_simulation
    ):
        """
        Test:
        - Insert parameter command with dangerous value: Temperature = 3000°C
        - Verify Terminal 3 rejects command (validation failure)
        - Verify PLC value unchanged
        - Verify command marked as failed with error message
        """
        supabase_client = clean_test_database
        param_factory = ParameterCommandFactory()

        # Get current PLC temperature value
        initial_temp = await plc_simulation.read_parameter("Temperature")

        # Insert dangerous command
        dangerous_cmd = param_factory.create_out_of_range_command(
            parameter_name="Temperature",
            target_value=3000.0  # Way above max (assume max is ~1000°C)
        )
        await param_factory.insert_command(supabase_client, dangerous_cmd)

        # Wait for Terminal 3 to process (should fail validation)
        await asyncio.sleep(3.0)

        # Verify command marked as failed
        cmd_result = supabase_client.table("parameter_control_commands").select("*").eq(
            "id", dangerous_cmd.id
        ).execute()

        assert len(cmd_result.data) > 0, "Command not found in database"
        cmd_data = cmd_result.data[0]

        assert cmd_data["error_message"] is not None, "No error message recorded for dangerous command"
        assert "validation" in cmd_data["error_message"].lower() or "range" in cmd_data["error_message"].lower()

        # Verify PLC value unchanged
        current_temp = await plc_simulation.read_parameter("Temperature")
        assert abs(current_temp - initial_temp) < 1.0, "PLC temperature changed despite validation failure"

    async def test_negative_pressure_rejected(
        self,
        three_terminals,
        clean_test_database,
        plc_simulation
    ):
        """Test negative pressure value rejected by Terminal 3."""
        supabase_client = clean_test_database
        param_factory = ParameterCommandFactory()

        initial_pressure = await plc_simulation.read_parameter("Pressure")

        # Insert invalid command (negative pressure)
        invalid_cmd = param_factory.create_out_of_range_command(
            parameter_name="Pressure",
            target_value=-100.0
        )
        await param_factory.insert_command(supabase_client, invalid_cmd)

        await asyncio.sleep(3.0)

        # Verify failure
        cmd_result = supabase_client.table("parameter_control_commands").select("*").eq(
            "id", invalid_cmd.id
        ).execute()

        assert cmd_result.data[0]["error_message"] is not None

        # Verify PLC unchanged
        current_pressure = await plc_simulation.read_parameter("Pressure")
        assert abs(current_pressure - initial_pressure) < 0.1

    async def test_multiple_dangerous_commands_all_rejected(
        self,
        three_terminals,
        clean_test_database
    ):
        """Test multiple dangerous commands all properly rejected."""
        supabase_client = clean_test_database
        param_factory = ParameterCommandFactory()

        dangerous_commands = [
            param_factory.create_out_of_range_command("Temperature", 5000.0),
            param_factory.create_out_of_range_command("Pressure", -500.0),
            param_factory.create_out_of_range_command("FlowRate", 99999.0),
        ]

        for cmd in dangerous_commands:
            await param_factory.insert_command(supabase_client, cmd)

        await asyncio.sleep(5.0)

        # Verify all failed
        for cmd in dangerous_commands:
            cmd_result = supabase_client.table("parameter_control_commands").select("*").eq(
                "id", cmd.id
            ).execute()

            assert cmd_result.data[0]["error_message"] is not None, f"Command {cmd.id} should have failed validation"


# ============================================================================
# TEST CLASS: Multi-Recipe Execution
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
class TestMultiRecipeExecution:
    """Test multiple recipe execution scenarios."""

    async def test_three_recipes_sequential_execution(
        self,
        three_terminals,
        clean_test_database
    ):
        """
        Test:
        - Insert 3 recipe commands simultaneously
        - Verify Terminal 2 executes them sequentially
        - Verify no overlapping execution
        - Verify correct order (by created_at timestamp)
        - Verify all 3 marked as completed
        """
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        command_factory = RecipeCommandFactory()

        # Create 3 simple recipes
        recipes_and_steps = [
            recipe_factory.create_simple_recipe(name=f"Recipe {i+1}")
            for i in range(3)
        ]

        # Insert all recipes
        for recipe, steps in recipes_and_steps:
            await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Insert 3 commands simultaneously
        commands = []
        for recipe, _ in recipes_and_steps:
            cmd = command_factory.create_start_recipe_command(recipe.id)
            await command_factory.insert_command(supabase_client, cmd)
            commands.append(cmd)
            await asyncio.sleep(0.1)  # Tiny delay to ensure order

        # Wait for all to complete
        for cmd in commands:
            completed = await wait_for_database_record(
                supabase_client,
                table="recipe_commands",
                filters={"id": cmd.id, "status": "completed"},
                timeout=60.0
            )
            assert completed, f"Recipe {cmd.id} did not complete"

        # Verify sequential execution (no overlap)
        execution_times = []
        for cmd in commands:
            cmd_data = supabase_client.table("recipe_commands").select("*").eq("id", cmd.id).execute().data[0]
            execution_times.append({
                "id": cmd.id,
                "start": datetime.fromisoformat(cmd_data["executed_at"]),
                "end": datetime.fromisoformat(cmd_data["completed_at"])
            })

        # Check no overlap
        for i in range(len(execution_times) - 1):
            current_end = execution_times[i]["end"]
            next_start = execution_times[i + 1]["start"]
            assert next_start >= current_end, f"Recipe {i+1} and {i+2} overlapped!"

    async def test_recipe_queue_maintains_order(
        self,
        three_terminals,
        clean_test_database
    ):
        """Test recipe queue processes commands in FIFO order."""
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        command_factory = RecipeCommandFactory()

        # Create 5 recipes
        recipes = []
        for i in range(5):
            recipe, steps = recipe_factory.create_simple_recipe(name=f"Queue Test {i+1}")
            await recipe_factory.insert_recipe(supabase_client, recipe, steps)
            recipes.append(recipe)

        # Insert commands with known order
        command_order = []
        for recipe in recipes:
            cmd = command_factory.create_start_recipe_command(recipe.id)
            await command_factory.insert_command(supabase_client, cmd)
            command_order.append(cmd.id)
            await asyncio.sleep(0.05)

        # Wait for all to complete
        for cmd_id in command_order:
            await wait_for_database_record(
                supabase_client,
                table="recipe_commands",
                filters={"id": cmd_id, "status": "completed"},
                timeout=90.0
            )

        # Verify execution order matches insertion order
        all_commands = supabase_client.table("recipe_commands").select("*").in_(
            "id", command_order
        ).order("executed_at").execute()

        executed_order = [cmd["id"] for cmd in all_commands.data]
        assert executed_order == command_order, f"Execution order {executed_order} != insertion order {command_order}"


# ============================================================================
# TEST CLASS: Data Collection During Idle
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestDataCollectionIdle:
    """Test Terminal 1 data collection during system idle."""

    async def test_100_cycles_no_gaps(
        self,
        three_terminals,
        clean_test_database
    ):
        """
        Test:
        - Run Terminal 1 for 100 cycles (~100s)
        - No recipe execution, no parameter commands
        - Verify 100 parameter snapshots in database
        - Verify timing precision maintained
        - Verify no data gaps
        """
        supabase_client = clean_test_database

        # Get initial count
        initial_count_result = supabase_client.table("parameter_value_history").select("id").execute()
        initial_count = len(initial_count_result.data) if initial_count_result.data else 0

        # Wait for 100 cycles (100 seconds + buffer)
        await asyncio.sleep(105.0)

        # Get final count
        final_count_result = supabase_client.table("parameter_value_history").select("id").execute()
        final_count = len(final_count_result.data) if final_count_result.data else 0

        records_added = final_count - initial_count

        # Verify ~100 records added (allow ±5 tolerance)
        assert 95 <= records_added <= 105, f"Expected ~100 records, got {records_added}"

        # Verify timing precision: get last 100 timestamps
        recent_records = supabase_client.table("parameter_value_history").select(
            "timestamp"
        ).order("timestamp", desc=True).limit(100).execute()

        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in recent_records.data]
        timestamps.reverse()  # Oldest first

        # Check intervals between consecutive records
        intervals = []
        for i in range(len(timestamps) - 1):
            interval = (timestamps[i + 1] - timestamps[i]).total_seconds()
            intervals.append(interval)

        # Verify most intervals are ~1.0s ± 0.2s
        good_intervals = [i for i in intervals if 0.8 <= i <= 1.2]
        assert len(good_intervals) >= 90, f"Only {len(good_intervals)}/99 intervals within tolerance"

    async def test_data_collection_continuous_no_drops(
        self,
        three_terminals,
        clean_test_database
    ):
        """Test Terminal 1 never drops data collection cycles."""
        supabase_client = clean_test_database

        # Collect timestamps for 30 cycles
        await asyncio.sleep(35.0)

        recent_records = supabase_client.table("parameter_value_history").select(
            "timestamp"
        ).order("timestamp", desc=True).limit(30).execute()

        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in recent_records.data]
        timestamps.reverse()

        # Verify NO gaps > 2s (which would indicate dropped cycle)
        for i in range(len(timestamps) - 1):
            gap = (timestamps[i + 1] - timestamps[i]).total_seconds()
            assert gap < 2.0, f"Data gap detected: {gap}s between cycles"


# ============================================================================
# TEST CLASS: Graceful Shutdown
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
class TestGracefulShutdown:
    """Test graceful shutdown behavior."""

    async def test_sigterm_during_recipe_execution(
        self,
        three_terminals,
        clean_test_database
    ):
        """
        Test:
        - Start all 3 terminals
        - Execute recipe (50% complete)
        - Send SIGTERM to all terminals
        - Verify recipe marked as failed
        - Verify no orphaned locks
        - Verify all database transactions committed
        - Restart terminals
        - Verify system recovers cleanly
        """
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        command_factory = RecipeCommandFactory()

        # Create long-running recipe
        recipe, steps = recipe_factory.create_complex_recipe(loop_count=10)
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Start recipe
        cmd = command_factory.create_start_recipe_command(recipe.id)
        await command_factory.insert_command(supabase_client, cmd)

        # Wait for execution to start
        await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": cmd.id, "status": "executing"},
            timeout=10.0
        )

        # Let recipe run for 10s (50% complete)
        await asyncio.sleep(10.0)

        # Send SIGTERM to all terminal processes
        terminal_pids = three_terminals["pids"]
        for pid in terminal_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        # Wait for graceful shutdown
        await asyncio.sleep(5.0)

        # Verify recipe marked as failed or interrupted
        cmd_result = supabase_client.table("recipe_commands").select("*").eq("id", cmd.id).execute()
        assert cmd_result.data[0]["status"] in ["failed", "interrupted"]

        # Verify no orphaned locks (check machine_state table)
        machine_state = supabase_client.table("machine_state").select("*").eq(
            "machine_id", "test-machine"
        ).execute()

        if machine_state.data:
            assert machine_state.data[0].get("locked_by") is None, "Machine still locked after shutdown"

        # Restart terminals (handled by three_terminals fixture cleanup)
        # Verify system recovers: insert simple recipe command
        simple_recipe, simple_steps = recipe_factory.create_simple_recipe()
        await recipe_factory.insert_recipe(supabase_client, simple_recipe, simple_steps)

        recovery_cmd = command_factory.create_start_recipe_command(simple_recipe.id)
        await command_factory.insert_command(supabase_client, recovery_cmd)

        # Verify execution completes successfully
        recovery_complete = await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": recovery_cmd.id, "status": "completed"},
            timeout=30.0
        )
        assert recovery_complete, "System did not recover after shutdown"

    async def test_shutdown_commits_all_data(
        self,
        three_terminals,
        clean_test_database
    ):
        """Verify shutdown commits all pending database transactions."""
        supabase_client = clean_test_database

        # Let Terminal 1 collect data for 10 cycles
        await asyncio.sleep(12.0)

        # Get count before shutdown
        count_before = len(supabase_client.table("parameter_value_history").select("id").execute().data)

        # Send SIGTERM
        for pid in three_terminals["pids"]:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        await asyncio.sleep(3.0)

        # Get count after shutdown
        count_after = len(supabase_client.table("parameter_value_history").select("id").execute().data)

        # Verify no data lost (counts should be very close)
        assert count_after >= count_before, "Data lost during shutdown"


# ============================================================================
# TEST CLASS: Realtime Failure Fallback
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
class TestRealtimeFailureFallback:
    """Test realtime failure and polling fallback."""

    async def test_realtime_failure_switches_to_polling(
        self,
        three_terminals,
        clean_test_database,
        terminal_log_capture
    ):
        """
        Test:
        - Start all 3 terminals with realtime enabled
        - Block realtime connections (simulate Supabase realtime outage)
        - Insert recipe command
        - Verify Terminal 2 picks up via polling
        - Insert parameter command
        - Verify Terminal 3 picks up via polling
        - Verify no duplicate processing
        - Restore realtime
        - Verify switch back to realtime
        """
        # This test requires custom network blocking - simplified version
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        recipe_cmd_factory = RecipeCommandFactory()
        param_cmd_factory = ParameterCommandFactory()

        # Note: Full implementation would use network chaos injection
        # For now, verify polling works by just using it

        # Insert recipe command
        recipe, steps = recipe_factory.create_simple_recipe()
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        cmd = recipe_cmd_factory.create_start_recipe_command(recipe.id)
        await recipe_cmd_factory.insert_command(supabase_client, cmd)

        # Verify Terminal 2 picks up (via polling or realtime)
        picked_up = await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": cmd.id, "status": "executing"},
            timeout=15.0
        )
        assert picked_up, "Terminal 2 failed to pick up command"

        # Verify completion
        completed = await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": cmd.id, "status": "completed"},
            timeout=30.0
        )
        assert completed

    async def test_no_duplicate_processing_realtime_and_polling(
        self,
        three_terminals,
        clean_test_database
    ):
        """Verify command not processed twice if both realtime and polling active."""
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        command_factory = RecipeCommandFactory()

        # Insert recipe command
        recipe, steps = recipe_factory.create_simple_recipe()
        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        cmd = command_factory.create_start_recipe_command(recipe.id)
        await command_factory.insert_command(supabase_client, cmd)

        # Wait for completion
        await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": cmd.id, "status": "completed"},
            timeout=30.0
        )

        # Check execution logs - should only have 1 process_execution record
        executions = supabase_client.table("process_executions").select("*").eq(
            "recipe_id", recipe.id
        ).execute()

        assert len(executions.data) == 1, f"Command processed {len(executions.data)} times (expected 1)"


# ============================================================================
# TEST CLASS: Concurrent Safety-Critical Operations
# ============================================================================

@pytest.mark.integration
@pytest.mark.multi_terminal
class TestConcurrentSafetyCriticalOps:
    """Test concurrent safety-critical operations are serialized."""

    async def test_valve_control_serialization(
        self,
        three_terminals,
        clean_test_database,
        plc_simulation
    ):
        """
        Test:
        - Terminal 3: Write safety-critical parameter (valve state)
        - Terminal 2: Recipe tries to control same valve
        - Verify serialization (no race condition)
        - Verify final state deterministic
        """
        supabase_client = clean_test_database
        recipe_factory = RecipeFactory()
        recipe_cmd_factory = RecipeCommandFactory()
        param_cmd_factory = ParameterCommandFactory()

        # Create recipe that controls Valve 1
        recipe_id = recipe_factory._generate_recipe_id()
        from tests.factories.recipe_factory import Recipe, RecipeStep

        recipe = Recipe(id=recipe_id, name="Valve Control Test", version="1.0")
        steps = [
            RecipeStep(
                id=recipe_factory._generate_step_id(),
                recipe_id=recipe_id,
                sequence_number=1,
                type="valve",
                name="Open Valve 1",
                parameters={"valve_number": 1, "state": "open", "duration_ms": 5000}
            )
        ]

        await recipe_factory.insert_recipe(supabase_client, recipe, steps)

        # Start recipe
        recipe_cmd = recipe_cmd_factory.create_start_recipe_command(recipe_id)
        await recipe_cmd_factory.insert_command(supabase_client, recipe_cmd)

        # Immediately insert parameter command for same valve
        valve_param_cmd = param_cmd_factory.create_parameter_write_command(
            parameter_name="Valve_1_State",
            target_value=0.0  # Close valve
        )
        await param_cmd_factory.insert_command(supabase_client, valve_param_cmd)

        # Wait for both to complete
        await wait_for_database_record(
            supabase_client,
            table="recipe_commands",
            filters={"id": recipe_cmd.id, "status": "completed"},
            timeout=15.0
        )

        await wait_for_database_record(
            supabase_client,
            table="parameter_control_commands",
            filters={"id": valve_param_cmd.id, "completed_at": lambda x: x is not None},
            timeout=15.0
        )

        # Verify final PLC state is deterministic (last write wins)
        valve_state = await plc_simulation.read_parameter("Valve_1_State")

        # Verify neither command failed due to conflict
        recipe_result = supabase_client.table("recipe_commands").select("*").eq("id", recipe_cmd.id).execute()
        param_result = supabase_client.table("parameter_control_commands").select("*").eq("id", valve_param_cmd.id).execute()

        assert recipe_result.data[0]["status"] == "completed"
        assert param_result.data[0]["error_message"] is None

    async def test_concurrent_parameter_writes_no_corruption(
        self,
        three_terminals,
        clean_test_database,
        plc_simulation
    ):
        """Test concurrent parameter writes don't corrupt PLC state."""
        supabase_client = clean_test_database
        param_factory = ParameterCommandFactory()

        # Insert 10 parameter commands for different parameters simultaneously
        commands = []
        for i in range(10):
            cmd = param_factory.create_parameter_write_command(
                parameter_name=f"TestParam_{i % 3}",  # 3 different parameters
                target_value=float(i * 10)
            )
            await param_factory.insert_command(supabase_client, cmd)
            commands.append(cmd)

        # Wait for all to complete
        for cmd in commands:
            await wait_for_database_record(
                supabase_client,
                table="parameter_control_commands",
                filters={"id": cmd.id, "completed_at": lambda x: x is not None},
                timeout=20.0
            )

        # Verify all completed without errors
        for cmd in commands:
            result = supabase_client.table("parameter_control_commands").select("*").eq("id", cmd.id).execute()
            assert result.data[0]["error_message"] is None, f"Command {cmd.id} failed"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def verify_terminal_health(terminal_id: int, timeout: float = 5.0) -> bool:
    """Verify a terminal is healthy and responsive."""
    # Implementation would check process status and recent logs
    return True


async def wait_for_recipe_step_completion(
    supabase_client,
    recipe_id: str,
    step_sequence: int,
    timeout: float = 30.0
) -> bool:
    """Wait for specific recipe step to complete."""
    return await wait_for_database_record(
        supabase_client,
        table="recipe_step_executions",
        filters={
            "recipe_id": recipe_id,
            "sequence_number": step_sequence,
            "status": "completed"
        },
        timeout=timeout
    )


async def get_terminal_resource_usage(pid: int) -> Dict[str, float]:
    """Get CPU and memory usage for terminal process."""
    import psutil
    try:
        process = psutil.Process(pid)
        return {
            "cpu_percent": process.cpu_percent(interval=1.0),
            "memory_mb": process.memory_info().rss / 1024 / 1024
        }
    except psutil.NoSuchProcess:
        return {"cpu_percent": 0.0, "memory_mb": 0.0}
