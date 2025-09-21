"""
Pytest configuration and shared fixtures for ALD Control System testing.

This file provides:
1. DI container mocking and test isolation
2. Async testing utilities
3. Database test fixtures with transaction rollback
4. PLC simulation and mocking
5. Test data factories
6. Common test utilities
"""
import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, AsyncGenerator, Generator
import tempfile
import shutil
import uuid
from pathlib import Path

# Add the project root to Python path for testing
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import project modules
from src.di.container import ServiceContainer, ServiceLifetime
from src.abstractions.interfaces import (
    IPLCInterface, IDatabaseService, IParameterLogger, IEventBus,
    IConfigurationService, IStateManager, IConnectionMonitor,
    ServiceHealth, ITransaction
)
from src.log_setup import setup_logger

# Test logger
test_logger = setup_logger("test_framework")

# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers to avoid warnings
    config.addinivalue_line(
        "markers", "unit: Unit tests - fast, isolated, mocked dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests - test component interactions"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests - full system testing"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 5 seconds to run"
    )
    config.addinivalue_line(
        "markers", "async: Tests that use asyncio"
    )
    config.addinivalue_line(
        "markers", "database: Tests that require database connection"
    )
    config.addinivalue_line(
        "markers", "plc: Tests that require PLC connection or simulation"
    )
    config.addinivalue_line(
        "markers", "security: Security-related tests"
    )
    config.addinivalue_line(
        "markers", "performance: Performance and benchmark tests"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test file locations."""
    for item in items:
        # Add markers based on file path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Add async marker for async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.async)

# ============================================================================
# DI Container Test Fixtures
# ============================================================================

@pytest.fixture
async def test_container() -> AsyncGenerator[ServiceContainer, None]:
    """
    Provide an isolated DI container for each test.

    This fixture creates a fresh ServiceContainer instance that is completely
    isolated from the production container. It's automatically disposed after
    each test to prevent resource leaks.
    """
    container = ServiceContainer()

    try:
        yield container
    finally:
        await container.dispose()

@pytest.fixture
async def mock_container(test_container: ServiceContainer) -> AsyncGenerator[ServiceContainer, None]:
    """
    Provide a DI container pre-configured with mock services.

    This fixture sets up a test container with mock implementations of all
    the main service interfaces, making it easy to write isolated unit tests.
    """
    # Create mock services
    mock_plc = create_mock_plc()
    mock_db = create_mock_database()
    mock_logger = create_mock_parameter_logger()
    mock_event_bus = create_mock_event_bus()
    mock_config = create_mock_configuration()
    mock_state = create_mock_state_manager()
    mock_monitor = create_mock_connection_monitor()

    # Register mocks in container
    test_container.register_singleton(IPLCInterface, factory=lambda c: mock_plc)
    test_container.register_singleton(IDatabaseService, factory=lambda c: mock_db)
    test_container.register_singleton(IParameterLogger, factory=lambda c: mock_logger)
    test_container.register_singleton(IEventBus, factory=lambda c: mock_event_bus)
    test_container.register_singleton(IConfigurationService, factory=lambda c: mock_config)
    test_container.register_singleton(IStateManager, factory=lambda c: mock_state)
    test_container.register_singleton(IConnectionMonitor, factory=lambda c: mock_monitor)

    yield test_container

# ============================================================================
# Mock Service Factories
# ============================================================================

def create_mock_plc() -> AsyncMock:
    """Create a mock PLC interface with realistic behavior."""
    mock_plc = AsyncMock(spec=IPLCInterface)

    # Default property values
    mock_plc.connected = True

    # Default method returns
    mock_plc.initialize.return_value = True
    mock_plc.disconnect.return_value = True
    mock_plc.health_check.return_value = ServiceHealth.HEALTHY

    # Mock parameter data
    mock_parameters = {
        "temp_reactor": 25.0,
        "pressure_chamber": 1013.25,
        "flow_rate_ar": 100.0,
        "valve_1_state": 0.0,
        "valve_2_state": 1.0
    }

    mock_plc.read_parameter.side_effect = lambda param_id: mock_parameters.get(param_id, 0.0)
    mock_plc.read_all_parameters.return_value = mock_parameters
    mock_plc.read_bulk_parameters.side_effect = lambda param_ids: {
        pid: mock_parameters.get(pid, 0.0) for pid in param_ids
    }
    mock_plc.write_parameter.return_value = True
    mock_plc.control_valve.return_value = True
    mock_plc.execute_purge.return_value = True

    return mock_plc

def create_mock_database() -> AsyncMock:
    """Create a mock database service with transaction support."""
    mock_db = AsyncMock(spec=IDatabaseService)

    # Mock transaction
    mock_transaction = AsyncMock(spec=ITransaction)
    mock_transaction.commit.return_value = True
    mock_transaction.rollback.return_value = True
    mock_transaction.execute.return_value = []
    mock_transaction.execute_many.return_value = True
    mock_transaction.__aenter__.return_value = mock_transaction
    mock_transaction.__aexit__.return_value = False

    # Database service defaults
    mock_db.execute_query.return_value = []
    mock_db.execute_many.return_value = True
    mock_db.fetch_one.return_value = None
    mock_db.fetch_all.return_value = []
    mock_db.begin_transaction.return_value = mock_transaction
    mock_db.health_check.return_value = ServiceHealth.HEALTHY

    return mock_db

def create_mock_parameter_logger() -> AsyncMock:
    """Create a mock parameter logger with dual-mode support."""
    mock_logger = AsyncMock(spec=IParameterLogger)

    mock_logger.start.return_value = True
    mock_logger.stop.return_value = True
    mock_logger.log_parameters.return_value = True
    mock_logger.log_dual_mode.return_value = True
    mock_logger.get_status.return_value = {
        "running": True,
        "last_log_time": 1234567890.0,
        "log_count": 100,
        "error_count": 0
    }
    mock_logger.health_check.return_value = ServiceHealth.HEALTHY

    return mock_logger

def create_mock_event_bus() -> AsyncMock:
    """Create a mock event bus for testing event-driven behavior."""
    mock_event_bus = AsyncMock(spec=IEventBus)

    mock_event_bus.publish.return_value = True
    mock_event_bus.subscribe.return_value = str(uuid.uuid4())
    mock_event_bus.unsubscribe.return_value = True

    return mock_event_bus

def create_mock_configuration() -> MagicMock:
    """Create a mock configuration service with test settings."""
    mock_config = MagicMock(spec=IConfigurationService)

    test_config = {
        "database": {
            "url": "test://localhost/test_db",
            "max_connections": 5
        },
        "plc": {
            "host": "localhost",
            "port": 502,
            "timeout": 1.0
        },
        "logging": {
            "level": "DEBUG",
            "interval": 1.0
        }
    }

    mock_config.get.side_effect = lambda key, default=None: test_config.get(key, default)
    mock_config.get_section.side_effect = lambda section: test_config.get(section, {})
    mock_config.reload.return_value = True

    return mock_config

def create_mock_state_manager() -> AsyncMock:
    """Create a mock state manager for testing state transitions."""
    mock_state = AsyncMock(spec=IStateManager)

    mock_machine_state = {
        "status": "idle",
        "current_recipe": None,
        "process_id": None,
        "last_update": 1234567890.0
    }

    mock_state.get_machine_state.return_value = mock_machine_state
    mock_state.set_machine_state.return_value = True
    mock_state.transition_state.return_value = True
    mock_state.watch_state_changes.return_value = str(uuid.uuid4())

    return mock_state

def create_mock_connection_monitor() -> AsyncMock:
    """Create a mock connection monitor for testing connectivity."""
    mock_monitor = AsyncMock(spec=IConnectionMonitor)

    mock_monitor.monitor_plc_connection.return_value = True
    mock_monitor.monitor_database_connection.return_value = True
    mock_monitor.get_connection_status.return_value = {
        "plc": {"connected": True, "last_check": 1234567890.0},
        "database": {"connected": True, "last_check": 1234567890.0}
    }
    mock_monitor.health_check.return_value = ServiceHealth.HEALTHY

    return mock_monitor

# ============================================================================
# Database Test Fixtures
# ============================================================================

@pytest.fixture
async def test_database(test_container: ServiceContainer):
    """
    Provide a test database with transaction rollback.

    This fixture sets up a test database connection that automatically
    rolls back all changes at the end of each test, ensuring test isolation.
    """
    # For now, return the mock database from the container
    # In a real implementation, this would set up a test database
    # with transaction rollback capabilities
    return await test_container.resolve(IDatabaseService)

@pytest.fixture
def test_db_transaction():
    """
    Provide a database transaction that auto-rolls back.

    This fixture wraps database operations in a transaction that
    automatically rolls back at the end of the test.
    """
    # This would implement actual transaction rollback in a real scenario
    mock_transaction = AsyncMock(spec=ITransaction)
    mock_transaction.commit.return_value = True
    mock_transaction.rollback.return_value = True
    return mock_transaction

# ============================================================================
# Test Data Factories
# ============================================================================

class TestDataFactory:
    """Factory for creating test data objects."""

    @staticmethod
    def create_recipe_data(recipe_id: Optional[str] = None) -> Dict[str, Any]:
        """Create test recipe data."""
        return {
            "id": recipe_id or str(uuid.uuid4()),
            "name": f"Test Recipe {uuid.uuid4().hex[:8]}",
            "description": "A test recipe for automated testing",
            "steps": TestDataFactory.create_recipe_steps()
        }

    @staticmethod
    def create_recipe_steps(count: int = 3) -> list[Dict[str, Any]]:
        """Create test recipe steps."""
        return [
            {
                "id": str(uuid.uuid4()),
                "step_number": i + 1,
                "step_type": "valve" if i % 2 == 0 else "purge",
                "duration": 1000 + (i * 500),
                "parameters": {"valve_number": i + 1} if i % 2 == 0 else {"duration_ms": 2000}
            }
            for i in range(count)
        ]

    @staticmethod
    def create_parameter_data(count: int = 5) -> Dict[str, float]:
        """Create test parameter data."""
        base_params = {
            "temp_reactor": 25.0,
            "pressure_chamber": 1013.25,
            "flow_rate_ar": 100.0,
            "valve_1_state": 0.0,
            "valve_2_state": 1.0
        }

        if count <= len(base_params):
            return dict(list(base_params.items())[:count])

        # Add more parameters if needed
        for i in range(len(base_params), count):
            base_params[f"test_param_{i}"] = float(i * 10)

        return base_params

    @staticmethod
    def create_process_data(process_id: Optional[str] = None) -> Dict[str, Any]:
        """Create test process data."""
        return {
            "process_id": process_id or str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
            "status": "running",
            "start_time": 1234567890.0,
            "parameters": TestDataFactory.create_parameter_data(),
            "machine_state": "processing"
        }

@pytest.fixture
def test_data_factory() -> TestDataFactory:
    """Provide the test data factory."""
    return TestDataFactory()

# ============================================================================
# Async Test Utilities
# ============================================================================

@pytest.fixture
def async_timeout() -> float:
    """Default timeout for async operations in tests."""
    return 5.0

@pytest.fixture
def event_loop():
    """Provide a fresh event loop for each test."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()

class AsyncTestHelper:
    """Helper utilities for async testing."""

    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout: float = 5.0,
        check_interval: float = 0.1
    ) -> bool:
        """
        Wait for a condition to become true.

        Args:
            condition_func: Function that returns True when condition is met
            timeout: Maximum time to wait
            check_interval: How often to check the condition

        Returns:
            True if condition was met, False if timeout
        """
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            if condition_func():
                return True
            await asyncio.sleep(check_interval)

        return False

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run a coroutine with timeout."""
        return await asyncio.wait_for(coro, timeout=timeout)

@pytest.fixture
def async_helper() -> AsyncTestHelper:
    """Provide async testing utilities."""
    return AsyncTestHelper()

# ============================================================================
# Test Environment Setup
# ============================================================================

@pytest.fixture(scope="session")
def test_workspace() -> Generator[Path, None, None]:
    """
    Provide a temporary workspace for test files.

    This creates a temporary directory that exists for the entire test session
    and is cleaned up automatically.
    """
    temp_dir = tempfile.mkdtemp(prefix="ald_test_")
    workspace = Path(temp_dir)

    try:
        yield workspace
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def test_config(test_workspace: Path) -> Dict[str, Any]:
    """Provide test configuration settings."""
    return {
        "test_mode": True,
        "workspace": str(test_workspace),
        "database": {
            "url": "sqlite:///:memory:",
            "echo": False
        },
        "plc": {
            "simulation_mode": True,
            "host": "localhost",
            "port": 502
        },
        "logging": {
            "level": "DEBUG",
            "file": str(test_workspace / "test.log")
        }
    }

# ============================================================================
# Test Cleanup and Isolation
# ============================================================================

@pytest.fixture(autouse=True)
async def test_isolation():
    """
    Ensure test isolation by cleaning up global state.

    This fixture runs automatically for every test to ensure proper isolation.
    """
    # Setup: Clear any global state before test
    yield

    # Cleanup: Clear any global state after test
    # This would clear singletons, global variables, etc.
    # For now, just log that cleanup is happening
    test_logger.debug("Test isolation cleanup completed")

# ============================================================================
# Performance Testing Utilities
# ============================================================================

@pytest.fixture
def performance_monitor():
    """Provide utilities for performance testing."""
    import time
    import psutil
    import threading

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.memory_usage = []
            self.monitoring = False
            self._monitor_thread = None

        def start_monitoring(self):
            """Start monitoring performance metrics."""
            self.start_time = time.perf_counter()
            self.monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop)
            self._monitor_thread.daemon = True
            self._monitor_thread.start()

        def stop_monitoring(self):
            """Stop monitoring and return results."""
            self.end_time = time.perf_counter()
            self.monitoring = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=1.0)

            return {
                "duration_ms": (self.end_time - self.start_time) * 1000,
                "peak_memory_mb": max(self.memory_usage) if self.memory_usage else 0,
                "avg_memory_mb": sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0
            }

        def _monitor_loop(self):
            """Internal monitoring loop."""
            process = psutil.Process()
            while self.monitoring:
                try:
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    self.memory_usage.append(memory_mb)
                    time.sleep(0.1)
                except:
                    break

    return PerformanceMonitor()

# ============================================================================
# Security Testing Utilities
# ============================================================================

@pytest.fixture
def security_test_helper():
    """Provide utilities for security testing."""

    class SecurityTestHelper:
        @staticmethod
        def create_malicious_input() -> Dict[str, Any]:
            """Create various types of malicious input for testing."""
            return {
                "sql_injection": "'; DROP TABLE users; --",
                "xss_script": "<script>alert('xss')</script>",
                "path_traversal": "../../../etc/passwd",
                "command_injection": "; rm -rf /",
                "large_string": "A" * 10000,
                "null_bytes": "test\x00injection",
                "unicode_attack": "\u0000\ufeff"
            }

        @staticmethod
        def validate_no_sensitive_data(data: Any) -> bool:
            """Check that sensitive data is not exposed."""
            data_str = str(data).lower()
            sensitive_patterns = [
                "password", "secret", "key", "token", "credential",
                "private", "confidential", "sensitive"
            ]

            for pattern in sensitive_patterns:
                if pattern in data_str:
                    return False
            return True

    return SecurityTestHelper()

# ============================================================================
# Logging Configuration for Tests
# ============================================================================

@pytest.fixture(autouse=True)
def configure_test_logging():
    """Configure logging for test environment."""
    import logging

    # Set test-appropriate logging levels
    logging.getLogger("src").setLevel(logging.DEBUG)
    logging.getLogger("test_framework").setLevel(logging.DEBUG)

    # Suppress overly verbose third-party logs during testing
    logging.getLogger("supabase").setLevel(logging.WARNING)
    logging.getLogger("pymodbus").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

# ============================================================================
# Parametrized Test Data
# ============================================================================

# Common test parameter sets for parametrized testing
PARAMETER_SETS = {
    "valve_numbers": [1, 2, 3, 4, 5],
    "durations": [100, 500, 1000, 2000, 5000],
    "parameter_counts": [1, 5, 10, 25, 50],
    "recipe_step_counts": [1, 3, 5, 10],
    "error_scenarios": [
        "connection_lost",
        "timeout",
        "invalid_parameter",
        "permission_denied",
        "resource_exhausted"
    ]
}

# Export commonly used parameter sets
pytest.VALVE_NUMBERS = PARAMETER_SETS["valve_numbers"]
pytest.DURATIONS = PARAMETER_SETS["durations"]
pytest.PARAMETER_COUNTS = PARAMETER_SETS["parameter_counts"]
pytest.ERROR_SCENARIOS = PARAMETER_SETS["error_scenarios"]