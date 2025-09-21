"""
Comprehensive test utilities for ALD Control System.

This module provides specialized utilities for testing complex async operations,
DI container testing, and domain-specific test helpers.
"""
import asyncio
import time
import pytest
import uuid
from typing import Dict, Any, List, Optional, Callable, AsyncIterator, TypeVar, Type
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
import inspect
from dataclasses import dataclass, field
from enum import Enum

# Import project types
from src.di.container import ServiceContainer
from src.abstractions.interfaces import (
    IPLCInterface, IDatabaseService, IParameterLogger, ServiceHealth
)

T = TypeVar('T')

# ============================================================================
# Async Testing Utilities
# ============================================================================

class AsyncTestUtils:
    """Advanced async testing utilities for complex scenarios."""

    @staticmethod
    async def assert_completes_within(coro, timeout_ms: float, error_msg: str = None):
        """Assert that a coroutine completes within the specified timeout."""
        timeout_seconds = timeout_ms / 1000.0
        error_msg = error_msg or f"Operation did not complete within {timeout_ms}ms"

        try:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            pytest.fail(error_msg)

    @staticmethod
    async def assert_takes_at_least(coro, min_time_ms: float, error_msg: str = None):
        """Assert that a coroutine takes at least the specified time."""
        start_time = time.perf_counter()
        result = await coro
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        error_msg = error_msg or f"Operation completed too quickly: {elapsed_ms:.2f}ms < {min_time_ms}ms"
        assert elapsed_ms >= min_time_ms, error_msg
        return result

    @staticmethod
    async def run_concurrent_operations(operations: List[Callable], max_concurrent: int = 10):
        """Run multiple async operations concurrently with limited concurrency."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(operation):
            async with semaphore:
                if asyncio.iscoroutinefunction(operation):
                    return await operation()
                else:
                    return operation()

        tasks = [run_with_semaphore(op) for op in operations]
        return await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def assert_no_race_conditions(
        concurrent_operations: List[Callable],
        state_checker: Callable[[], bool],
        iterations: int = 10
    ):
        """Test for race conditions by running concurrent operations multiple times."""
        for i in range(iterations):
            # Run concurrent operations
            results = await AsyncTestUtils.run_concurrent_operations(concurrent_operations)

            # Check for exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            if exceptions:
                pytest.fail(f"Race condition detected - exceptions occurred: {exceptions}")

            # Check state consistency
            if not state_checker():
                pytest.fail(f"Race condition detected - inconsistent state after iteration {i}")

    @staticmethod
    @asynccontextmanager
    async def async_time_limit(timeout_seconds: float):
        """Context manager for time-limited async operations."""
        try:
            async with asyncio.timeout(timeout_seconds):
                yield
        except asyncio.TimeoutError:
            pytest.fail(f"Operation exceeded time limit of {timeout_seconds} seconds")

# ============================================================================
# DI Container Test Utilities
# ============================================================================

class DITestUtils:
    """Utilities for testing dependency injection scenarios."""

    @staticmethod
    async def assert_service_resolution(
        container: ServiceContainer,
        service_type: Type[T],
        expected_instance_type: Type = None
    ) -> T:
        """Assert that a service can be resolved from the container."""
        try:
            service = await container.resolve(service_type)
            assert service is not None, f"Service {service_type.__name__} resolved to None"

            if expected_instance_type:
                assert isinstance(service, expected_instance_type), \
                    f"Expected {expected_instance_type.__name__}, got {type(service).__name__}"

            return service
        except Exception as e:
            pytest.fail(f"Failed to resolve service {service_type.__name__}: {str(e)}")

    @staticmethod
    async def assert_circular_dependency_detection(
        container: ServiceContainer,
        service_type: Type[T]
    ):
        """Assert that circular dependencies are properly detected."""
        from src.di.container import CircularDependencyError

        with pytest.raises(CircularDependencyError):
            await container.resolve(service_type)

    @staticmethod
    async def assert_singleton_behavior(
        container: ServiceContainer,
        service_type: Type[T]
    ):
        """Assert that singleton services return the same instance."""
        instance1 = await container.resolve(service_type)
        instance2 = await container.resolve(service_type)

        assert instance1 is instance2, \
            f"Singleton service {service_type.__name__} returned different instances"

    @staticmethod
    async def assert_transient_behavior(
        container: ServiceContainer,
        service_type: Type[T]
    ):
        """Assert that transient services return different instances."""
        instance1 = await container.resolve(service_type)
        instance2 = await container.resolve(service_type)

        assert instance1 is not instance2, \
            f"Transient service {service_type.__name__} returned the same instance"

    @staticmethod
    async def assert_container_disposal(container: ServiceContainer):
        """Assert that container disposal works correctly."""
        # Resolve some services to create instances
        await container.resolve(IPLCInterface)
        await container.resolve(IDatabaseService)

        # Dispose container
        await container.dispose()

        # Assert that container is marked as disposed
        assert container._is_disposed, "Container not marked as disposed"

        # Assert that further resolutions fail
        with pytest.raises(RuntimeError, match="Container has been disposed"):
            await container.resolve(IPLCInterface)

# ============================================================================
# Performance Test Utilities
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Performance measurement results."""
    duration_ms: float
    peak_memory_mb: float
    avg_memory_mb: float
    operations_per_second: float = 0.0
    error_count: int = 0
    additional_metrics: Dict[str, Any] = field(default_factory=dict)

class PerformanceTestUtils:
    """Utilities for performance testing and benchmarking."""

    @staticmethod
    @asynccontextmanager
    async def measure_performance(
        operation_count: int = 1,
        sample_interval: float = 0.1
    ) -> AsyncIterator[PerformanceMetrics]:
        """Context manager for measuring performance metrics."""
        import psutil
        import threading

        # Initialize metrics
        metrics = PerformanceMetrics(
            duration_ms=0.0,
            peak_memory_mb=0.0,
            avg_memory_mb=0.0
        )

        memory_samples = []
        monitoring = True

        def monitor_memory():
            process = psutil.Process()
            while monitoring:
                try:
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(memory_mb)
                    time.sleep(sample_interval)
                except:
                    break

        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
        monitor_thread.start()

        start_time = time.perf_counter()

        try:
            yield metrics
        finally:
            # Stop monitoring
            end_time = time.perf_counter()
            monitoring = False
            monitor_thread.join(timeout=1.0)

            # Calculate metrics
            metrics.duration_ms = (end_time - start_time) * 1000
            metrics.peak_memory_mb = max(memory_samples) if memory_samples else 0
            metrics.avg_memory_mb = sum(memory_samples) / len(memory_samples) if memory_samples else 0
            if metrics.duration_ms > 0:
                metrics.operations_per_second = operation_count / (metrics.duration_ms / 1000)

    @staticmethod
    async def assert_performance_target(
        operation: Callable,
        max_duration_ms: float,
        max_memory_mb: float = None,
        min_ops_per_second: float = None
    ) -> PerformanceMetrics:
        """Assert that an operation meets performance targets."""
        async with PerformanceTestUtils.measure_performance() as metrics:
            if asyncio.iscoroutinefunction(operation):
                await operation()
            else:
                operation()

        # Check duration
        assert metrics.duration_ms <= max_duration_ms, \
            f"Operation took {metrics.duration_ms:.2f}ms, expected <= {max_duration_ms}ms"

        # Check memory usage
        if max_memory_mb is not None:
            assert metrics.peak_memory_mb <= max_memory_mb, \
                f"Peak memory usage {metrics.peak_memory_mb:.2f}MB, expected <= {max_memory_mb}MB"

        # Check operations per second
        if min_ops_per_second is not None:
            assert metrics.operations_per_second >= min_ops_per_second, \
                f"Operations per second {metrics.operations_per_second:.2f}, expected >= {min_ops_per_second}"

        return metrics

# ============================================================================
# Test Data Builders
# ============================================================================

class RecipeTestBuilder:
    """Builder pattern for creating test recipe data."""

    def __init__(self):
        self.data = {
            "id": str(uuid.uuid4()),
            "name": f"Test Recipe {uuid.uuid4().hex[:8]}",
            "description": "Generated test recipe",
            "steps": [],
            "parameters": {}
        }

    def with_id(self, recipe_id: str) -> 'RecipeTestBuilder':
        self.data["id"] = recipe_id
        return self

    def with_name(self, name: str) -> 'RecipeTestBuilder':
        self.data["name"] = name
        return self

    def with_description(self, description: str) -> 'RecipeTestBuilder':
        self.data["description"] = description
        return self

    def add_valve_step(self, valve_number: int, duration_ms: int, step_number: int = None) -> 'RecipeTestBuilder':
        step_number = step_number or len(self.data["steps"]) + 1
        self.data["steps"].append({
            "id": str(uuid.uuid4()),
            "step_number": step_number,
            "step_type": "valve",
            "duration": duration_ms,
            "parameters": {"valve_number": valve_number}
        })
        return self

    def add_purge_step(self, duration_ms: int, step_number: int = None) -> 'RecipeTestBuilder':
        step_number = step_number or len(self.data["steps"]) + 1
        self.data["steps"].append({
            "id": str(uuid.uuid4()),
            "step_number": step_number,
            "step_type": "purge",
            "duration": duration_ms,
            "parameters": {"duration_ms": duration_ms}
        })
        return self

    def add_parameter_step(self, parameter_id: str, value: float, step_number: int = None) -> 'RecipeTestBuilder':
        step_number = step_number or len(self.data["steps"]) + 1
        self.data["steps"].append({
            "id": str(uuid.uuid4()),
            "step_number": step_number,
            "step_type": "parameter",
            "duration": 0,
            "parameters": {"parameter_id": parameter_id, "value": value}
        })
        return self

    def add_recipe_parameter(self, parameter_id: str, default_value: float) -> 'RecipeTestBuilder':
        self.data["parameters"][parameter_id] = default_value
        return self

    def build(self) -> Dict[str, Any]:
        return self.data.copy()

class ParameterTestBuilder:
    """Builder pattern for creating test parameter data."""

    def __init__(self):
        self.parameters = {}

    def add_temperature(self, parameter_id: str, value: float) -> 'ParameterTestBuilder':
        self.parameters[parameter_id] = value
        return self

    def add_pressure(self, parameter_id: str, value: float) -> 'ParameterTestBuilder':
        self.parameters[parameter_id] = value
        return self

    def add_flow_rate(self, parameter_id: str, value: float) -> 'ParameterTestBuilder':
        self.parameters[parameter_id] = value
        return self

    def add_valve_state(self, valve_number: int, state: bool) -> 'ParameterTestBuilder':
        self.parameters[f"valve_{valve_number}_state"] = float(state)
        return self

    def add_custom(self, parameter_id: str, value: float) -> 'ParameterTestBuilder':
        self.parameters[parameter_id] = value
        return self

    def build(self) -> Dict[str, float]:
        return self.parameters.copy()

# ============================================================================
# Mock Service Test Scenarios
# ============================================================================

class MockScenario(Enum):
    """Predefined mock scenarios for different testing needs."""
    HEALTHY_SYSTEM = "healthy"
    PLC_DISCONNECTED = "plc_disconnected"
    DATABASE_ERROR = "database_error"
    SLOW_RESPONSES = "slow_responses"
    INTERMITTENT_FAILURES = "intermittent_failures"
    MEMORY_PRESSURE = "memory_pressure"

class MockServiceScenarios:
    """Predefined mock scenarios for comprehensive testing."""

    @staticmethod
    def apply_scenario(mock_container: ServiceContainer, scenario: MockScenario):
        """Apply a predefined test scenario to the mock container."""
        if scenario == MockScenario.HEALTHY_SYSTEM:
            MockServiceScenarios._configure_healthy_system(mock_container)
        elif scenario == MockScenario.PLC_DISCONNECTED:
            MockServiceScenarios._configure_plc_disconnected(mock_container)
        elif scenario == MockScenario.DATABASE_ERROR:
            MockServiceScenarios._configure_database_error(mock_container)
        elif scenario == MockScenario.SLOW_RESPONSES:
            MockServiceScenarios._configure_slow_responses(mock_container)
        elif scenario == MockScenario.INTERMITTENT_FAILURES:
            MockServiceScenarios._configure_intermittent_failures(mock_container)

    @staticmethod
    async def _configure_healthy_system(mock_container: ServiceContainer):
        """Configure mocks for a healthy system scenario."""
        plc = await mock_container.resolve(IPLCInterface)
        db = await mock_container.resolve(IDatabaseService)
        logger = await mock_container.resolve(IParameterLogger)

        plc.connected = True
        plc.health_check.return_value = ServiceHealth.HEALTHY
        db.health_check.return_value = ServiceHealth.HEALTHY
        logger.health_check.return_value = ServiceHealth.HEALTHY

    @staticmethod
    async def _configure_plc_disconnected(mock_container: ServiceContainer):
        """Configure mocks for a PLC disconnected scenario."""
        plc = await mock_container.resolve(IPLCInterface)

        plc.connected = False
        plc.health_check.return_value = ServiceHealth.UNHEALTHY
        plc.read_parameter.side_effect = Exception("PLC not connected")
        plc.write_parameter.side_effect = Exception("PLC not connected")

    @staticmethod
    async def _configure_database_error(mock_container: ServiceContainer):
        """Configure mocks for database error scenario."""
        db = await mock_container.resolve(IDatabaseService)

        db.health_check.return_value = ServiceHealth.UNHEALTHY
        db.execute_query.side_effect = Exception("Database connection lost")
        db.fetch_all.side_effect = Exception("Database connection lost")

    @staticmethod
    async def _configure_slow_responses(mock_container: ServiceContainer):
        """Configure mocks for slow response scenario."""
        async def slow_operation(*args, **kwargs):
            await asyncio.sleep(2.0)  # 2 second delay
            return True

        plc = await mock_container.resolve(IPLCInterface)
        db = await mock_container.resolve(IDatabaseService)

        plc.read_parameter.side_effect = slow_operation
        db.execute_query.side_effect = slow_operation

    @staticmethod
    async def _configure_intermittent_failures(mock_container: ServiceContainer):
        """Configure mocks for intermittent failure scenario."""
        call_count = {"count": 0}

        async def intermittent_failure(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] % 3 == 0:  # Fail every 3rd call
                raise Exception("Intermittent failure")
            return True

        plc = await mock_container.resolve(IPLCInterface)
        plc.read_parameter.side_effect = intermittent_failure

# ============================================================================
# Test Fixtures Extensions
# ============================================================================

@pytest.fixture
def async_test_utils():
    """Provide async testing utilities."""
    return AsyncTestUtils()

@pytest.fixture
def di_test_utils():
    """Provide DI testing utilities."""
    return DITestUtils()

@pytest.fixture
def performance_test_utils():
    """Provide performance testing utilities."""
    return PerformanceTestUtils()

@pytest.fixture
def recipe_builder():
    """Provide recipe test data builder."""
    return RecipeTestBuilder()

@pytest.fixture
def parameter_builder():
    """Provide parameter test data builder."""
    return ParameterTestBuilder()

@pytest.fixture
def mock_scenarios():
    """Provide mock scenario utilities."""
    return MockServiceScenarios()

# ============================================================================
# Test Assertion Helpers
# ============================================================================

class TestAssertions:
    """Custom assertion helpers for domain-specific testing."""

    @staticmethod
    def assert_parameter_values_close(
        actual: Dict[str, float],
        expected: Dict[str, float],
        tolerance: float = 0.01
    ):
        """Assert that parameter values are within tolerance."""
        assert set(actual.keys()) == set(expected.keys()), \
            f"Parameter sets don't match: {actual.keys()} vs {expected.keys()}"

        for param_id in expected:
            actual_val = actual[param_id]
            expected_val = expected[param_id]
            diff = abs(actual_val - expected_val)

            assert diff <= tolerance, \
                f"Parameter {param_id}: {actual_val} not within {tolerance} of {expected_val}"

    @staticmethod
    def assert_recipe_structure_valid(recipe_data: Dict[str, Any]):
        """Assert that recipe data has valid structure."""
        required_fields = ["id", "name", "steps"]
        for field in required_fields:
            assert field in recipe_data, f"Recipe missing required field: {field}"

        assert isinstance(recipe_data["steps"], list), "Recipe steps must be a list"

        for i, step in enumerate(recipe_data["steps"]):
            assert "step_number" in step, f"Step {i} missing step_number"
            assert "step_type" in step, f"Step {i} missing step_type"
            assert "duration" in step, f"Step {i} missing duration"

    @staticmethod
    def assert_health_status_valid(health_status: ServiceHealth):
        """Assert that health status is valid."""
        assert isinstance(health_status, ServiceHealth), \
            f"Health status must be ServiceHealth enum, got {type(health_status)}"

@pytest.fixture
def test_assertions():
    """Provide custom test assertions."""
    return TestAssertions()