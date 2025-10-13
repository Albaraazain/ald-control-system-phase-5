"""
Comprehensive pytest configuration and fixtures for ALD Control System testing.

This module provides shared fixtures, test data factories, and configuration
for all test suites including unit, integration, and end-to-end tests.
"""

import os
import sys
import asyncio
import pytest
import tempfile
import shutil
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Test configuration
pytest_plugins = ["pytest_asyncio"]

# Import all new test fixtures
from tests.fixtures.terminal_fixtures import (
    terminal_launcher,
    three_terminals,
    terminal_health_monitor,
    terminal_log_capture
)
from tests.fixtures.plc_fixtures import (
    plc_simulation,
    plc_with_parameters,
    plc_state_validator,
    plc_connection_monitor,
    plc_reset_utility,
    plc_with_binary_parameters,
    mock_plc_manager
)
from tests.fixtures.database_fixtures import (
    clean_test_database,
    test_machine,
    test_operator,
    database_validator,
    database_cleanup_utility,
    database_connection_monitor
)
from tests.utils.async_helpers import (
    wait_for_condition,
    wait_for_database_record,
    wait_for_terminal_log,
    run_with_timeout,
    collect_events,
    drain_queue,
    AsyncSubprocessManager,
    retry_on_exception,
    measure_execution_time,
    run_concurrently,
    sleep_until
)

# Environment setup
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup global test environment variables."""
    os.environ.update({
        "TEST_MODE": "true",
        "LOG_LEVEL": "DEBUG",
        "PLC_TYPE": "simulation",
        "MACHINE_ID": "test-machine",
        "SUPABASE_KEY": "test_key_for_testing",
        "DATABASE_URL": "postgresql://test_user:test_password@localhost:5432/test_ald"
    })
    yield
    # Cleanup is automatic

# Async event loop configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session.

    Configured with extended timeout for long-running multi-terminal tests.
    """
    loop = asyncio.new_event_loop()

    # Configure loop for long-running tests
    loop.set_debug(True)  # Enable debug mode for async tracking

    # Set slow callback threshold to 100ms for performance monitoring
    loop.slow_callback_duration = 0.1

    yield loop

    # Cleanup: cancel all pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()

    # Wait for tasks to complete cancellation
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    loop.close()

# Temporary directory fixture
@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)

# Mock PLC fixtures
@pytest.fixture
def mock_plc():
    """Provide a mock PLC interface for testing."""
    from abstractions.interfaces import IPLCInterface

    mock = Mock(spec=IPLCInterface)
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock()
    mock.read_parameter = AsyncMock(return_value=42.0)
    mock.write_parameter = AsyncMock(return_value=True)
    mock.read_multiple_parameters = AsyncMock(return_value={"param1": 42.0, "param2": 24.0})
    mock.is_connected = Mock(return_value=True)
    mock.get_connection_status = Mock(return_value="connected")

    return mock

@pytest.fixture
def mock_plc_communicator():
    """Provide a mock PLC communicator for testing."""
    from plc.communicator import PLCCommunicator

    mock = Mock(spec=PLCCommunicator)
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock()
    mock.read_modbus_address = AsyncMock(return_value=42.0)
    mock.write_modbus_address = AsyncMock(return_value=True)
    mock.read_bulk_addresses = AsyncMock(return_value=[42.0, 24.0, 13.5])
    mock.is_connected = Mock(return_value=True)

    return mock

# Database fixtures
@pytest.fixture
def mock_database():
    """Provide a mock database service for testing."""
    from abstractions.interfaces import IDatabaseService

    mock = Mock(spec=IDatabaseService)
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock()
    mock.execute_query = AsyncMock(return_value=[])
    mock.execute_transaction = AsyncMock(return_value=True)
    mock.health_check = AsyncMock(return_value=True)

    return mock

@pytest.fixture
async def test_database():
    """Provide a real test database connection (if available)."""
    try:
        from data_collection.database_service import DatabaseService

        # Use test database URL if available
        test_db_url = os.getenv("TEST_DATABASE_URL", "postgresql://test_user:test_password@localhost:5432/test_ald")

        db_service = DatabaseService()
        await db_service.connect()

        yield db_service

        await db_service.disconnect()
    except Exception:
        # Fall back to mock if real database not available
        yield mock_database()

# Dependency Injection fixtures
@pytest.fixture
def mock_service_container():
    """Provide a mock DI service container for testing."""
    from di.service_container import ServiceContainer

    container = Mock(spec=ServiceContainer)
    container.resolve = Mock()
    container.register = Mock()
    container.register_singleton = Mock()
    container.register_factory = Mock()
    container.health_check = AsyncMock(return_value=True)

    return container

@pytest.fixture
async def test_service_container():
    """Provide a real DI service container configured for testing."""
    from di.service_container import ServiceContainer
    from di.container_builder import ConfigurationBasedContainerBuilder

    builder = ConfigurationBasedContainerBuilder()

    # Configure test services
    test_config = {
        "services": {
            "plc": {
                "type": "simulation",
                "lifetime": "singleton"
            },
            "database": {
                "type": "mock",
                "lifetime": "singleton"
            },
            "logger": {
                "type": "console",
                "lifetime": "singleton"
            }
        }
    }

    container = builder.build_container(test_config)

    yield container

    # Cleanup
    await container.dispose()

# Performance testing fixtures
@pytest.fixture
def performance_monitor():
    """Provide performance monitoring utilities for tests."""
    import time
    import psutil
    import threading
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class PerformanceMetrics:
        duration: float
        memory_peak: float
        cpu_usage: float

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.metrics = []
            self.monitoring = False

        def start(self):
            self.start_time = time.time()
            self.monitoring = True
            self._start_monitoring()

        def stop(self):
            self.monitoring = False
            duration = time.time() - self.start_time if self.start_time else 0
            return PerformanceMetrics(
                duration=duration,
                memory_peak=max([m.get('memory', 0) for m in self.metrics] + [0]),
                cpu_usage=sum([m.get('cpu', 0) for m in self.metrics]) / max(len(self.metrics), 1)
            )

        def _start_monitoring(self):
            def monitor():
                process = psutil.Process()
                while self.monitoring:
                    try:
                        self.metrics.append({
                            'memory': process.memory_info().rss / 1024 / 1024,  # MB
                            'cpu': process.cpu_percent(),
                            'timestamp': time.time()
                        })
                        time.sleep(0.1)
                    except:
                        break

            thread = threading.Thread(target=monitor, daemon=True)
            thread.start()

    return PerformanceMonitor()

# Test data factories
@pytest.fixture
def parameter_data_factory():
    """Factory for creating test parameter data."""
    def create_parameter_data(
        parameter_id: int = 1,
        value: float = 42.0,
        timestamp: str = "2024-01-01T00:00:00Z",
        machine_id: str = "test-machine"
    ):
        return {
            "parameter_id": parameter_id,
            "value": value,
            "timestamp": timestamp,
            "machine_id": machine_id
        }

    return create_parameter_data

@pytest.fixture
def recipe_data_factory():
    """Factory for creating test recipe data."""
    def create_recipe_data(
        recipe_id: int = 1,
        name: str = "Test Recipe",
        steps: list = None
    ):
        if steps is None:
            steps = [
                {"type": "valve", "valve_id": 1, "state": "open", "duration": 5.0},
                {"type": "purge", "duration": 10.0},
                {"type": "parameter", "parameter_id": 1, "value": 100.0}
            ]

        return {
            "recipe_id": recipe_id,
            "name": name,
            "steps": steps,
            "created_at": "2024-01-01T00:00:00Z"
        }

    return create_recipe_data

@pytest.fixture
def command_data_factory():
    """Factory for creating test command data."""
    def create_command_data(
        command_id: int = 1,
        command_type: str = "start_recipe",
        payload: dict = None,
        status: str = "pending"
    ):
        if payload is None:
            payload = {"recipe_id": 1}

        return {
            "command_id": command_id,
            "command_type": command_type,
            "payload": payload,
            "status": status,
            "created_at": "2024-01-01T00:00:00Z",
            "machine_id": "test-machine"
        }

    return create_command_data

# Security testing fixtures
@pytest.fixture
def security_test_context():
    """Provide security testing context and utilities."""
    from dataclasses import dataclass

    @dataclass
    class SecurityTestContext:
        test_credentials: dict
        mock_tokens: dict
        invalid_inputs: list

    return SecurityTestContext(
        test_credentials={
            "valid_user": "test_user",
            "valid_token": "test_token_12345",
            "test_machine_id": "test-machine-secure"
        },
        mock_tokens={
            "expired": "expired_token_12345",
            "invalid": "invalid_token_format",
            "malicious": "'; DROP TABLE users; --"
        },
        invalid_inputs=[
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "\x00\x01\x02\x03",
            "A" * 10000  # Buffer overflow attempt
        ]
    )

# Async test utilities
@pytest.fixture
def async_test_helpers():
    """Provide utilities for async testing."""
    class AsyncTestHelpers:
        @staticmethod
        async def wait_for_condition(condition_func, timeout=5.0, interval=0.1):
            """Wait for a condition to become true."""
            import asyncio

            start_time = asyncio.get_event_loop().time()
            while True:
                if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                    return True

                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError(f"Condition not met within {timeout} seconds")

                await asyncio.sleep(interval)

        @staticmethod
        async def run_with_timeout(coro, timeout=5.0):
            """Run a coroutine with timeout."""
            try:
                return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Operation timed out after {timeout} seconds")

    return AsyncTestHelpers()

# Test markers utility
@pytest.fixture(autouse=True)
def test_markers(request):
    """Automatically apply test configuration based on markers."""
    # Skip slow tests unless explicitly requested
    if request.node.get_closest_marker('slow') and not request.config.getoption('--run-slow', default=False):
        pytest.skip("Slow test skipped (use --run-slow to run)")

    # Skip hardware tests unless hardware is available
    if request.node.get_closest_marker('hardware'):
        if not os.getenv('HARDWARE_AVAILABLE', '').lower() == 'true':
            pytest.skip("Hardware not available for testing")

    # Configure database tests
    if request.node.get_closest_marker('database'):
        if not os.getenv('TEST_DATABASE_URL'):
            pytest.skip("Test database not configured")

# Custom pytest options
def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests"
    )
    parser.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="Run hardware-dependent tests"
    )
    parser.addoption(
        "--performance-baseline",
        action="store",
        help="Performance baseline file for comparison"
    )
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests with real terminals and database"
    )
    parser.addoption(
        "--run-stress",
        action="store_true",
        default=False,
        help="Run stress tests with high load scenarios"
    )
    parser.addoption(
        "--terminal-timeout",
        action="store",
        type=int,
        default=60,
        help="Timeout in seconds for terminal operations (default: 60)"
    )

def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "hardware: mark test as requiring hardware")
    config.addinivalue_line("markers", "benchmark: mark test as performance benchmark")
    config.addinivalue_line("markers", "flaky: mark test as potentially flaky")

    # Multi-terminal testing markers
    config.addinivalue_line("markers", "multi_terminal: mark test as requiring multiple terminal processes")
    config.addinivalue_line("markers", "serial: mark test to run serially (no parallel execution)")
    config.addinivalue_line("markers", "integration: mark test as integration test (requires --run-integration)")
    config.addinivalue_line("markers", "stress: mark test as stress test (requires --run-stress)")
    config.addinivalue_line("markers", "terminal1: mark test as using terminal 1 (PLC Read Service)")
    config.addinivalue_line("markers", "terminal2: mark test as using terminal 2 (Recipe Service)")
    config.addinivalue_line("markers", "terminal3: mark test as using terminal 3 (Parameter Service)")

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on configuration."""
    skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
    skip_hardware = pytest.mark.skip(reason="need --run-hardware option to run")
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    skip_stress = pytest.mark.skip(reason="need --run-stress option to run")

    for item in items:
        if "slow" in item.keywords and not config.getoption("--run-slow"):
            item.add_marker(skip_slow)
        if "hardware" in item.keywords and not config.getoption("--run-hardware"):
            item.add_marker(skip_hardware)
        if "integration" in item.keywords and not config.getoption("--run-integration"):
            item.add_marker(skip_integration)
        if "stress" in item.keywords and not config.getoption("--run-stress"):
            item.add_marker(skip_stress)

        # Serial tests should not run in parallel (xdist)
        if "serial" in item.keywords:
            item.add_marker(pytest.mark.xdist_group(name="serial"))