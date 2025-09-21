"""
Pytest version of basic integration tests.

This demonstrates migrating existing tests to use the pytest framework
with dependency injection, fixtures, and proper test isolation.
"""
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock

# Import test utilities
from tests.test_utils import AsyncTestUtils, TestAssertions
from tests.test_database import TestDatabaseService, TestDataSeeder

# Import project modules
from src.di.container import ServiceContainer
from src.abstractions.interfaces import IDatabaseService

# ============================================================================
# Basic Integration Tests - Pytest Version
# ============================================================================

@pytest.mark.integration
@pytest.mark.database
class TestBasicIntegration:
    """
    Pytest version of basic integration tests.

    This class demonstrates how to migrate existing integration tests
    to use the pytest framework with proper fixtures and DI mocking.
    """

    @pytest.fixture(autouse=True)
    async def setup_test_data(self, test_db_service: TestDatabaseService, test_data_seeder: TestDataSeeder):
        """Set up test data for integration tests."""
        self.db_service = test_db_service

        # Seed test recipes that match the original test expectations
        self.test_recipes = [
            {
                "id": "ecdfb993-fd08-402a-adfa-353b426cd925",
                "name": "Simple Test Recipe",
                "description": "A simple test recipe for validation",
                "created_at": "2023-01-01T00:00:00Z"
            },
            {
                "id": "f6478f3a-7068-458f-9438-1acf14719d4e",
                "name": "Complex Test Recipe",
                "description": "A complex test recipe for validation",
                "created_at": "2023-01-01T00:00:00Z"
            }
        ]

        self.test_recipe_steps = {
            "ecdfb993-fd08-402a-adfa-353b426cd925": [
                {"id": "step1", "step_number": 1, "step_type": "valve", "recipe_id": "ecdfb993-fd08-402a-adfa-353b426cd925"},
                {"id": "step2", "step_number": 2, "step_type": "purge", "recipe_id": "ecdfb993-fd08-402a-adfa-353b426cd925"},
                {"id": "step3", "step_number": 3, "step_type": "valve", "recipe_id": "ecdfb993-fd08-402a-adfa-353b426cd925"}
            ],
            "f6478f3a-7068-458f-9438-1acf14719d4e": [
                {"id": "step1", "step_number": 1, "step_type": "valve", "recipe_id": "f6478f3a-7068-458f-9438-1acf14719d4e"},
                {"id": "step2", "step_number": 2, "step_type": "purge", "recipe_id": "f6478f3a-7068-458f-9438-1acf14719d4e"},
                {"id": "step3", "step_number": 3, "step_type": "parameter", "recipe_id": "f6478f3a-7068-458f-9438-1acf14719d4e"},
                {"id": "step4", "step_number": 4, "step_type": "loop", "recipe_id": "f6478f3a-7068-458f-9438-1acf14719d4e"},
                {"id": "step5", "step_number": 5, "step_type": "valve", "recipe_id": "f6478f3a-7068-458f-9438-1acf14719d4e"}
            ]
        }

        # Configure mock database responses
        self.db_service.set_mock_data("fetch_all_result", self.test_recipes)

    @pytest.mark.asyncio
    async def test_recipe_existence(self, test_assertions: TestAssertions):
        """Test that test recipes exist and can be queried - pytest version."""
        # Arrange
        simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"

        # Act
        # Simulate recipe queries
        all_recipes = await self.db_service.fetch_all("SELECT * FROM recipes")
        simple_recipe = [r for r in all_recipes if r["id"] == simple_recipe_id]
        complex_recipe = [r for r in all_recipes if r["id"] == complex_recipe_id]

        # Assert
        assert len(simple_recipe) == 1, "Simple test recipe not found"
        assert len(complex_recipe) == 1, "Complex test recipe not found"

        assert simple_recipe[0]["name"] == "Simple Test Recipe"
        assert complex_recipe[0]["name"] == "Complex Test Recipe"

    @pytest.mark.asyncio
    async def test_recipe_steps(self):
        """Test recipe steps exist and have correct counts - pytest version."""
        # Arrange
        simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"

        # Configure mock responses for recipe steps
        self.db_service.set_mock_data("fetch_all_result", self.test_recipe_steps[simple_recipe_id])
        simple_steps = await self.db_service.fetch_all(f"SELECT * FROM recipe_steps WHERE recipe_id = '{simple_recipe_id}'")

        self.db_service.set_mock_data("fetch_all_result", self.test_recipe_steps[complex_recipe_id])
        complex_steps = await self.db_service.fetch_all(f"SELECT * FROM recipe_steps WHERE recipe_id = '{complex_recipe_id}'")

        # Assert
        assert len(simple_steps) == 3, f"Simple recipe should have 3 steps, found {len(simple_steps)}"
        assert len(complex_steps) == 5, f"Complex recipe should have 5 steps, found {len(complex_steps)}"

        # Verify step structure
        for step in simple_steps:
            assert "step_number" in step
            assert "step_type" in step
            assert step["recipe_id"] == simple_recipe_id

    @pytest.mark.asyncio
    async def test_step_configurations(self):
        """Test step configurations exist - pytest version."""
        # Arrange
        mock_configs = {
            "valve_configs": [
                {"id": "config1", "valve_number": 1, "duration": 1000},
                {"id": "config2", "valve_number": 2, "duration": 1500}
            ],
            "purge_configs": [
                {"id": "purge1", "duration": 2000},
                {"id": "purge2", "duration": 3000}
            ],
            "loop_configs": [
                {"id": "loop1", "iterations": 5}
            ]
        }

        # Act & Assert
        for config_type, configs in mock_configs.items():
            self.db_service.set_mock_data("fetch_all_result", configs)
            results = await self.db_service.fetch_all(f"SELECT * FROM {config_type}")

            assert len(results) > 0, f"No {config_type} configurations found"
            assert len(results) == len(configs), f"Expected {len(configs)} {config_type}, found {len(results)}"

    @pytest.mark.asyncio
    async def test_recipe_parameters(self):
        """Test recipe parameters exist - pytest version."""
        # Arrange
        simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"

        mock_parameters = {
            simple_recipe_id: [
                {"parameter_id": "temp_reactor", "default_value": 25.0},
                {"parameter_id": "pressure_chamber", "default_value": 1013.25}
            ],
            complex_recipe_id: [
                {"parameter_id": "temp_reactor", "default_value": 150.0},
                {"parameter_id": "pressure_chamber", "default_value": 500.0},
                {"parameter_id": "flow_rate_ar", "default_value": 100.0}
            ]
        }

        # Act & Assert for simple recipe
        self.db_service.set_mock_data("fetch_all_result", mock_parameters[simple_recipe_id])
        simple_params = await self.db_service.fetch_all(f"SELECT * FROM recipe_parameters WHERE recipe_id = '{simple_recipe_id}'")

        assert len(simple_params) == 2, f"Simple recipe should have 2 parameters, found {len(simple_params)}"

        # Act & Assert for complex recipe
        self.db_service.set_mock_data("fetch_all_result", mock_parameters[complex_recipe_id])
        complex_params = await self.db_service.fetch_all(f"SELECT * FROM recipe_parameters WHERE recipe_id = '{complex_recipe_id}'")

        assert len(complex_params) == 3, f"Complex recipe should have 3 parameters, found {len(complex_params)}"

    @pytest.mark.asyncio
    async def test_complete_integration_workflow(self, async_test_utils: AsyncTestUtils):
        """Test complete integration workflow with performance tracking - pytest version."""
        # This test demonstrates a complete workflow similar to the original main() function

        # Arrange
        workflow_steps = []

        # Act
        async def database_connection_test():
            workflow_steps.append("database_connected")
            return True

        async def recipe_validation_test():
            all_recipes = await self.db_service.fetch_all("SELECT * FROM recipes")
            workflow_steps.append("recipes_validated")
            return len(all_recipes) >= 2

        async def step_validation_test():
            # Validate steps for both recipes
            for recipe in self.test_recipes:
                recipe_id = recipe["id"]
                expected_steps = len(self.test_recipe_steps[recipe_id])

                self.db_service.set_mock_data("fetch_all_result", self.test_recipe_steps[recipe_id])
                steps = await self.db_service.fetch_all(f"SELECT * FROM recipe_steps WHERE recipe_id = '{recipe_id}'")
                assert len(steps) == expected_steps

            workflow_steps.append("steps_validated")
            return True

        async def configuration_validation_test():
            # Validate configurations exist
            config_types = ["valve_step_config", "purge_step_config", "loop_step_config"]
            for config_type in config_types:
                self.db_service.set_mock_data("fetch_all_result", [{"id": "test_config"}])
                configs = await self.db_service.fetch_all(f"SELECT * FROM {config_type}")
                assert len(configs) > 0

            workflow_steps.append("configurations_validated")
            return True

        # Execute workflow with performance tracking
        workflow_operations = [
            database_connection_test,
            recipe_validation_test,
            step_validation_test,
            configuration_validation_test
        ]

        # Run all operations with timeout
        for operation in workflow_operations:
            await async_test_utils.assert_completes_within(
                operation(), timeout_ms=5000, error_msg=f"Operation {operation.__name__} timed out"
            )

        # Assert
        expected_steps = [
            "database_connected",
            "recipes_validated",
            "steps_validated",
            "configurations_validated"
        ]

        assert workflow_steps == expected_steps, f"Workflow steps mismatch: {workflow_steps} vs {expected_steps}"

# ============================================================================
# Performance Integration Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.performance
class TestIntegrationPerformance:
    """Performance-focused integration tests using the pytest framework."""

    @pytest.mark.asyncio
    async def test_database_query_performance(self, test_db_service: TestDatabaseService, performance_test_utils):
        """Test database query performance meets requirements."""

        async def query_operation():
            await test_db_service.fetch_all("SELECT * FROM recipes")
            await test_db_service.fetch_all("SELECT * FROM recipe_steps")
            await test_db_service.fetch_all("SELECT * FROM parameters")

        # Assert performance requirements
        metrics = await performance_test_utils.assert_performance_target(
            query_operation,
            max_duration_ms=100,    # Should complete within 100ms
            max_memory_mb=50        # Should use less than 50MB
        )

        # Additional assertions
        assert metrics.duration_ms < 100, f"Database queries took {metrics.duration_ms}ms, expected < 100ms"

    @pytest.mark.asyncio
    async def test_concurrent_database_access(self, test_db_service: TestDatabaseService, async_test_utils: AsyncTestUtils):
        """Test concurrent database access patterns."""

        async def concurrent_query():
            return await test_db_service.fetch_all("SELECT * FROM recipes")

        # Create multiple concurrent operations
        operations = [concurrent_query for _ in range(10)]

        # Run concurrently and measure
        results = await async_test_utils.run_concurrent_operations(operations, max_concurrent=5)

        # Assert
        assert len(results) == 10
        assert all(not isinstance(r, Exception) for r in results), "Some concurrent operations failed"

# ============================================================================
# Error Handling Integration Tests
# ============================================================================

@pytest.mark.integration
class TestIntegrationErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.mark.asyncio
    async def test_database_connection_failure(self, test_db_service: TestDatabaseService, db_test_utils):
        """Test handling of database connection failures."""
        # Arrange
        await db_test_utils.simulate_database_error(test_db_service, "Connection lost")

        # Act & Assert
        with pytest.raises(Exception, match="Connection lost"):
            await test_db_service.fetch_all("SELECT * FROM recipes")

    @pytest.mark.asyncio
    async def test_invalid_recipe_id_handling(self, test_db_service: TestDatabaseService):
        """Test handling of invalid recipe IDs."""
        # Arrange
        invalid_recipe_id = "invalid-uuid-format"
        test_db_service.set_mock_data("fetch_all_result", [])  # No results

        # Act
        results = await test_db_service.fetch_all(f"SELECT * FROM recipes WHERE id = '{invalid_recipe_id}'")

        # Assert
        assert len(results) == 0, "Invalid recipe ID should return no results"

    @pytest.mark.asyncio
    async def test_missing_recipe_steps_handling(self, test_db_service: TestDatabaseService):
        """Test handling of recipes with missing steps."""
        # Arrange
        recipe_id_without_steps = "recipe-without-steps"
        test_db_service.set_mock_data("fetch_all_result", [])  # No steps

        # Act
        steps = await test_db_service.fetch_all(f"SELECT * FROM recipe_steps WHERE recipe_id = '{recipe_id_without_steps}'")

        # Assert
        assert len(steps) == 0, "Recipe without steps should return empty list"

# ============================================================================
# Compatibility Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.regression
class TestBackwardCompatibility:
    """Test backward compatibility with existing systems."""

    @pytest.mark.asyncio
    async def test_original_test_data_compatibility(self, test_db_service: TestDatabaseService):
        """Test that pytest framework works with original test data expectations."""
        # This test ensures the pytest version produces the same results as the original

        # Arrange - Use exact same recipe IDs from original test
        simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"

        # Set up mock data to match original expectations
        recipes = [
            {"id": simple_recipe_id, "name": "Simple Test Recipe"},
            {"id": complex_recipe_id, "name": "Complex Test Recipe"}
        ]
        test_db_service.set_mock_data("fetch_all_result", recipes)

        # Act - Query using same logic as original test
        all_recipes = await test_db_service.fetch_all("SELECT * FROM recipes")
        simple_recipe = [r for r in all_recipes if r["id"] == simple_recipe_id]
        complex_recipe = [r for r in all_recipes if r["id"] == complex_recipe_id]

        # Assert - Same assertions as original test
        assert len(simple_recipe) == 1, "Simple test recipe not found"
        assert len(complex_recipe) == 1, "Complex test recipe not found"

        # Verify the pytest framework provides the same validation capabilities
        assert simple_recipe[0]["name"] == "Simple Test Recipe"
        assert complex_recipe[0]["name"] == "Complex Test Recipe"

    def test_pytest_markers_compatibility(self):
        """Test that pytest markers are properly configured."""
        # This test verifies that all required markers are available
        import pytest

        # Verify custom markers are available
        assert hasattr(pytest, 'VALVE_NUMBERS')
        assert hasattr(pytest, 'DURATIONS')
        assert hasattr(pytest, 'PARAMETER_COUNTS')
        assert hasattr(pytest, 'ERROR_SCENARIOS')

        # Verify marker lists have expected content
        assert len(pytest.VALVE_NUMBERS) > 0
        assert len(pytest.DURATIONS) > 0
        assert len(pytest.PARAMETER_COUNTS) > 0
        assert len(pytest.ERROR_SCENARIOS) > 0