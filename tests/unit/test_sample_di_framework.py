"""
Sample unit tests demonstrating the pytest framework with DI container mocking.

This file serves as a template and example for how to write unit tests
using the new pytest framework with dependency injection support.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock
from typing import Dict, Any

# Import test utilities
from tests.test_utils import (
    AsyncTestUtils, DITestUtils, PerformanceTestUtils,
    RecipeTestBuilder, ParameterTestBuilder, MockScenario
)
from tests.test_database import TestDatabaseService, DatabaseTestUtils

# Import project modules
from src.di.container import ServiceContainer, ServiceLifetime
from src.abstractions.interfaces import (
    IPLCInterface, IDatabaseService, IParameterLogger, ServiceHealth
)

# ============================================================================
# DI Container Unit Tests
# ============================================================================

@pytest.mark.unit
class TestDIContainer:
    """Unit tests for the dependency injection container."""

    @pytest.mark.asyncio
    async def test_container_service_registration(self, test_container: ServiceContainer, di_test_utils: DITestUtils):
        """Test that services can be registered and resolved."""
        # Arrange
        mock_plc = AsyncMock(spec=IPLCInterface)
        test_container.register_singleton(IPLCInterface, factory=lambda c: mock_plc)

        # Act & Assert
        resolved_plc = await di_test_utils.assert_service_resolution(
            test_container, IPLCInterface, AsyncMock
        )

        assert resolved_plc is mock_plc

    @pytest.mark.asyncio
    async def test_singleton_behavior(self, test_container: ServiceContainer, di_test_utils: DITestUtils):
        """Test that singleton services return the same instance."""
        # Arrange
        mock_service = AsyncMock(spec=IPLCInterface)
        test_container.register_singleton(IPLCInterface, factory=lambda c: mock_service)

        # Act & Assert
        await di_test_utils.assert_singleton_behavior(test_container, IPLCInterface)

    @pytest.mark.asyncio
    async def test_transient_behavior(self, test_container: ServiceContainer, di_test_utils: DITestUtils):
        """Test that transient services return different instances."""
        # Arrange
        test_container.register_transient(
            IPLCInterface,
            factory=lambda c: AsyncMock(spec=IPLCInterface)
        )

        # Act & Assert
        await di_test_utils.assert_transient_behavior(test_container, IPLCInterface)

    @pytest.mark.asyncio
    async def test_container_disposal(self, test_container: ServiceContainer, di_test_utils: DITestUtils):
        """Test that container disposal works correctly."""
        # Arrange
        mock_plc = AsyncMock(spec=IPLCInterface)
        test_container.register_singleton(IPLCInterface, factory=lambda c: mock_plc)

        # Act & Assert
        await di_test_utils.assert_container_disposal(test_container)

# ============================================================================
# Mock Service Scenario Tests
# ============================================================================

@pytest.mark.unit
class TestMockServiceScenarios:
    """Test different mock service scenarios."""

    @pytest.mark.asyncio
    async def test_healthy_system_scenario(self, mock_container: ServiceContainer, mock_scenarios):
        """Test the healthy system mock scenario."""
        # Arrange
        await mock_scenarios.apply_scenario(mock_container, MockScenario.HEALTHY_SYSTEM)

        # Act
        plc = await mock_container.resolve(IPLCInterface)
        db = await mock_container.resolve(IDatabaseService)
        logger = await mock_container.resolve(IParameterLogger)

        # Assert
        assert plc.connected is True
        assert await plc.health_check() == ServiceHealth.HEALTHY
        assert await db.health_check() == ServiceHealth.HEALTHY
        assert await logger.health_check() == ServiceHealth.HEALTHY

    @pytest.mark.asyncio
    async def test_plc_disconnected_scenario(self, mock_container: ServiceContainer, mock_scenarios):
        """Test the PLC disconnected mock scenario."""
        # Arrange
        await mock_scenarios.apply_scenario(mock_container, MockScenario.PLC_DISCONNECTED)

        # Act
        plc = await mock_container.resolve(IPLCInterface)

        # Assert
        assert plc.connected is False
        assert await plc.health_check() == ServiceHealth.UNHEALTHY

        with pytest.raises(Exception, match="PLC not connected"):
            await plc.read_parameter("test_param")

# ============================================================================
# Async Testing Utilities Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.async
class TestAsyncUtilities:
    """Test async testing utilities."""

    @pytest.mark.asyncio
    async def test_assert_completes_within(self, async_test_utils: AsyncTestUtils):
        """Test that operations complete within specified timeouts."""
        async def fast_operation():
            await asyncio.sleep(0.1)
            return "completed"

        # Act & Assert
        result = await async_test_utils.assert_completes_within(
            fast_operation(), timeout_ms=500, error_msg="Operation should complete quickly"
        )

        assert result == "completed"

    @pytest.mark.asyncio
    async def test_assert_takes_at_least(self, async_test_utils: AsyncTestUtils):
        """Test that operations take at least the specified time."""
        async def slow_operation():
            await asyncio.sleep(0.2)
            return "completed"

        # Act & Assert
        result = await async_test_utils.assert_takes_at_least(
            slow_operation(), min_time_ms=100, error_msg="Operation should take at least 100ms"
        )

        assert result == "completed"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, async_test_utils: AsyncTestUtils):
        """Test running concurrent operations."""
        call_count = {"count": 0}

        async def increment_operation():
            call_count["count"] += 1
            await asyncio.sleep(0.1)
            return call_count["count"]

        operations = [increment_operation for _ in range(5)]

        # Act
        results = await async_test_utils.run_concurrent_operations(operations, max_concurrent=3)

        # Assert
        assert len(results) == 5
        assert call_count["count"] == 5
        assert all(isinstance(r, int) for r in results)

# ============================================================================
# Performance Testing Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.performance
class TestPerformanceUtilities:
    """Test performance testing utilities."""

    @pytest.mark.asyncio
    async def test_performance_measurement(self, performance_test_utils: PerformanceTestUtils):
        """Test performance measurement capabilities."""
        async def test_operation():
            await asyncio.sleep(0.1)
            return "completed"

        # Act & Assert
        metrics = await performance_test_utils.assert_performance_target(
            test_operation,
            max_duration_ms=200,  # Should complete within 200ms
            max_memory_mb=100     # Should use less than 100MB
        )

        assert metrics.duration_ms > 90   # Should take at least ~100ms
        assert metrics.duration_ms < 200  # Should complete within 200ms

# ============================================================================
# Test Data Builder Tests
# ============================================================================

@pytest.mark.unit
class TestDataBuilders:
    """Test the test data builder utilities."""

    def test_recipe_builder(self, recipe_builder: RecipeTestBuilder, test_assertions):
        """Test recipe data builder functionality."""
        # Act
        recipe = (recipe_builder
                 .with_name("Test Recipe")
                 .with_description("A test recipe")
                 .add_valve_step(valve_number=1, duration_ms=1000)
                 .add_purge_step(duration_ms=2000)
                 .add_parameter_step("temp_reactor", 150.0)
                 .add_recipe_parameter("default_temp", 25.0)
                 .build())

        # Assert
        test_assertions.assert_recipe_structure_valid(recipe)
        assert recipe["name"] == "Test Recipe"
        assert recipe["description"] == "A test recipe"
        assert len(recipe["steps"]) == 3
        assert "default_temp" in recipe["parameters"]

    def test_parameter_builder(self, parameter_builder: ParameterTestBuilder, test_assertions):
        """Test parameter data builder functionality."""
        # Act
        parameters = (parameter_builder
                     .add_temperature("temp_reactor", 150.0)
                     .add_pressure("pressure_chamber", 1013.25)
                     .add_flow_rate("flow_rate_ar", 100.0)
                     .add_valve_state(1, True)
                     .add_valve_state(2, False)
                     .build())

        # Assert
        assert len(parameters) == 5
        assert parameters["temp_reactor"] == 150.0
        assert parameters["pressure_chamber"] == 1013.25
        assert parameters["valve_1_state"] == 1.0
        assert parameters["valve_2_state"] == 0.0

        # Test custom assertions
        expected = {
            "temp_reactor": 150.0,
            "pressure_chamber": 1013.25,
            "flow_rate_ar": 100.0,
            "valve_1_state": 1.0,
            "valve_2_state": 0.0
        }

        test_assertions.assert_parameter_values_close(parameters, expected, tolerance=0.01)

# ============================================================================
# Database Testing Integration
# ============================================================================

@pytest.mark.unit
@pytest.mark.database
class TestDatabaseUtilities:
    """Test database testing utilities."""

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self, test_db_service: TestDatabaseService, db_test_utils: DatabaseTestUtils):
        """Test that database transactions roll back properly."""
        # Act
        async with test_db_service.transaction_manager.transaction_scope() as transaction:
            await transaction.execute("INSERT INTO test_table (id, name) VALUES (1, 'test')")
            await transaction.execute("UPDATE test_table SET name = 'updated' WHERE id = 1")

        # Assert
        await db_test_utils.assert_transaction_rollback(transaction)

    @pytest.mark.asyncio
    async def test_query_logging(self, test_db_service: TestDatabaseService, db_test_utils: DatabaseTestUtils):
        """Test that database queries are properly logged."""
        # Act
        await test_db_service.execute_query("SELECT * FROM test_table")
        await test_db_service.fetch_all("SELECT * FROM parameters")

        # Assert
        await db_test_utils.assert_query_executed(test_db_service, "SELECT * FROM test_table")

        query_log = test_db_service.get_query_log()
        assert len(query_log) == 2
        assert query_log[0][0] == "execute_query"
        assert query_log[1][0] == "fetch_all"

    @pytest.mark.asyncio
    async def test_seeded_test_data(self, seeded_test_db: TestDatabaseService):
        """Test working with pre-seeded test data."""
        # Act
        recipes = await seeded_test_db.fetch_all("SELECT * FROM recipes")

        # Assert
        assert len(recipes) == 3  # Should have 3 seeded recipes
        assert all("Test Recipe" in recipe["name"] for recipe in recipes)

# ============================================================================
# Integration with Existing Code Tests
# ============================================================================

@pytest.mark.unit
class TestExistingCodeIntegration:
    """Test integration with existing codebase patterns."""

    @pytest.mark.asyncio
    async def test_parameter_logging_with_mocks(self, mock_container: ServiceContainer):
        """Test parameter logging using the DI container with mocks."""
        # Arrange
        plc = await mock_container.resolve(IPLCInterface)
        logger = await mock_container.resolve(IParameterLogger)

        # Configure mock data
        test_parameters = {
            "temp_reactor": 150.0,
            "pressure_chamber": 1013.25,
            "flow_rate_ar": 100.0
        }
        plc.read_all_parameters.return_value = test_parameters

        # Act
        parameters = await plc.read_all_parameters()
        log_result = await logger.log_parameters(parameters)

        # Assert
        assert parameters == test_parameters
        assert log_result is True
        plc.read_all_parameters.assert_called_once()
        logger.log_parameters.assert_called_once_with(test_parameters)

    @pytest.mark.asyncio
    async def test_recipe_execution_simulation(
        self,
        mock_container: ServiceContainer,
        recipe_builder: RecipeTestBuilder
    ):
        """Test simulated recipe execution using mocks."""
        # Arrange
        plc = await mock_container.resolve(IPLCInterface)
        recipe = (recipe_builder
                 .with_name("Test Execution Recipe")
                 .add_valve_step(1, 1000)
                 .add_purge_step(2000)
                 .add_valve_step(2, 1500)
                 .build())

        # Act
        for step in recipe["steps"]:
            if step["step_type"] == "valve":
                await plc.control_valve(
                    step["parameters"]["valve_number"],
                    True,
                    step["duration"]
                )
            elif step["step_type"] == "purge":
                await plc.execute_purge(step["parameters"]["duration_ms"])

        # Assert
        assert plc.control_valve.call_count == 2
        assert plc.execute_purge.call_count == 1

        # Verify specific calls
        plc.control_valve.assert_any_call(1, True, 1000)
        plc.control_valve.assert_any_call(2, True, 1500)
        plc.execute_purge.assert_called_with(2000)

# ============================================================================
# Error Handling and Edge Cases
# ============================================================================

@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in the testing framework."""

    @pytest.mark.asyncio
    async def test_service_resolution_error(self, test_container: ServiceContainer):
        """Test proper error handling when service resolution fails."""
        from src.di.container import ServiceNotRegisteredError

        # Act & Assert
        with pytest.raises(ServiceNotRegisteredError):
            await test_container.resolve(IPLCInterface)

    @pytest.mark.asyncio
    async def test_database_error_simulation(self, test_db_service: TestDatabaseService, db_test_utils: DatabaseTestUtils):
        """Test database error simulation."""
        # Arrange
        await db_test_utils.simulate_database_error(test_db_service, "Simulated error")

        # Act & Assert
        with pytest.raises(Exception, match="Simulated error"):
            await test_db_service.execute_query("SELECT * FROM test_table")

    @pytest.mark.asyncio
    async def test_timeout_handling(self, async_test_utils: AsyncTestUtils):
        """Test timeout handling in async operations."""
        async def hanging_operation():
            await asyncio.sleep(10)  # Long operation
            return "completed"

        # Act & Assert
        with pytest.raises(Exception):  # Should fail due to timeout
            await async_test_utils.assert_completes_within(
                hanging_operation(), timeout_ms=100
            )

# ============================================================================
# Parametrized Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.parametrize("valve_number", pytest.VALVE_NUMBERS[:3])  # Test first 3 valves
@pytest.mark.parametrize("duration", pytest.DURATIONS[:3])          # Test first 3 durations
class TestParametrizedValveControl:
    """Parametrized tests for valve control scenarios."""

    @pytest.mark.asyncio
    async def test_valve_control_combinations(
        self,
        mock_container: ServiceContainer,
        valve_number: int,
        duration: int
    ):
        """Test valve control with different valve/duration combinations."""
        # Arrange
        plc = await mock_container.resolve(IPLCInterface)

        # Act
        result = await plc.control_valve(valve_number, True, duration)

        # Assert
        assert result is True
        plc.control_valve.assert_called_with(valve_number, True, duration)

@pytest.mark.unit
@pytest.mark.parametrize("parameter_count", pytest.PARAMETER_COUNTS[:3])  # Test first 3 counts
class TestParametrizedParameterReading:
    """Parametrized tests for parameter reading scenarios."""

    @pytest.mark.asyncio
    async def test_bulk_parameter_reading(
        self,
        mock_container: ServiceContainer,
        parameter_builder: ParameterTestBuilder,
        parameter_count: int
    ):
        """Test bulk parameter reading with different parameter counts."""
        # Arrange
        plc = await mock_container.resolve(IPLCInterface)
        test_parameters = {}

        for i in range(parameter_count):
            test_parameters[f"param_{i}"] = float(i * 10)

        plc.read_bulk_parameters.return_value = test_parameters

        # Act
        result = await plc.read_bulk_parameters(list(test_parameters.keys()))

        # Assert
        assert len(result) == parameter_count
        assert result == test_parameters
        plc.read_bulk_parameters.assert_called_once()

# ============================================================================
# Smoke Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.smoke
class TestFrameworkSmokeTests:
    """Quick smoke tests to verify framework functionality."""

    @pytest.mark.asyncio
    async def test_basic_di_container_functionality(self, test_container: ServiceContainer):
        """Smoke test for basic DI container functionality."""
        # Arrange
        mock_service = AsyncMock(spec=IPLCInterface)
        test_container.register_singleton(IPLCInterface, factory=lambda c: mock_service)

        # Act
        resolved = await test_container.resolve(IPLCInterface)

        # Assert
        assert resolved is mock_service

    def test_basic_test_data_creation(self, recipe_builder: RecipeTestBuilder):
        """Smoke test for basic test data creation."""
        # Act
        recipe = recipe_builder.with_name("Smoke Test Recipe").build()

        # Assert
        assert recipe["name"] == "Smoke Test Recipe"
        assert "id" in recipe

    @pytest.mark.asyncio
    async def test_basic_async_utilities(self, async_test_utils: AsyncTestUtils):
        """Smoke test for basic async utilities."""
        async def simple_operation():
            return "success"

        # Act
        result = await async_test_utils.assert_completes_within(
            simple_operation(), timeout_ms=1000
        )

        # Assert
        assert result == "success"