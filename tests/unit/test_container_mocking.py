"""
Unit testing framework for dependency injection container with comprehensive mocking support.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, Type, TypeVar, Optional
from contextlib import asynccontextmanager

from src.di.container import ServiceContainer, ServiceLifetime, ServiceDescriptor
from src.abstractions.interfaces import (
    IPLCInterface, IDatabaseService, IParameterLogger,
    IEventBus, IConfigurationService, IStateManager, IConnectionMonitor
)

T = TypeVar('T')

class MockServiceContainer:
    """Mock service container for unit testing with DI support"""

    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._mocks: Dict[Type, Mock] = {}
        self._call_counts: Dict[str, int] = {}

    def register_mock(self, service_type: Type[T], mock_instance: Optional[T] = None) -> T:
        """Register a mock for a service type"""
        if mock_instance is None:
            mock_instance = self._create_auto_mock(service_type)
        self._services[service_type] = mock_instance
        self._mocks[service_type] = mock_instance
        return mock_instance

    def _create_auto_mock(self, service_type: Type[T]) -> T:
        """Create appropriate mock based on service type"""
        if hasattr(service_type, '__abstractmethods__'):
            # Abstract class or interface - create mock with all abstract methods
            mock = MagicMock(spec=service_type)

            # For async interfaces, ensure async methods return coroutines
            if service_type == IPLCInterface:
                mock.initialize = AsyncMock(return_value=True)
                mock.disconnect = AsyncMock(return_value=True)
                mock.read_parameter = AsyncMock(return_value=0.0)
                mock.write_parameter = AsyncMock(return_value=True)
                mock.connected = True

            elif service_type == IDatabaseService:
                mock.connect = AsyncMock(return_value=True)
                mock.disconnect = AsyncMock(return_value=True)
                mock.execute_query = AsyncMock(return_value=[])
                mock.execute_transaction = AsyncMock(return_value=True)
                mock.health_check = AsyncMock(return_value=True)

            elif service_type == IParameterLogger:
                mock.log_parameter = AsyncMock(return_value=True)
                mock.log_bulk_parameters = AsyncMock(return_value=True)
                mock.start_logging = AsyncMock(return_value=True)
                mock.stop_logging = AsyncMock(return_value=True)

            return mock
        else:
            # Concrete class - create mock with spec
            return MagicMock(spec=service_type)

    def get_service(self, service_type: Type[T]) -> T:
        """Get service (mock) by type"""
        if service_type in self._services:
            return self._services[service_type]

        # Auto-register mock if not found
        return self.register_mock(service_type)

    def get_mock(self, service_type: Type[T]) -> Mock:
        """Get the underlying mock for assertions"""
        if service_type not in self._mocks:
            self.register_mock(service_type)
        return self._mocks[service_type]

    def reset_mocks(self):
        """Reset all mocks and call counts"""
        for mock in self._mocks.values():
            mock.reset_mock()
        self._call_counts.clear()

    def verify_service_called(self, service_type: Type, method_name: str, times: int = 1):
        """Verify that a service method was called specific number of times"""
        mock = self.get_mock(service_type)
        method = getattr(mock, method_name)
        assert method.call_count == times, f"{service_type.__name__}.{method_name} was called {method.call_count} times, expected {times}"

    def setup_plc_mock_behavior(self, connected: bool = True, read_values: Dict[str, float] = None, write_success: bool = True):
        """Setup common PLC mock behaviors"""
        plc_mock = self.get_mock(IPLCInterface)
        plc_mock.connected = connected
        plc_mock.initialize.return_value = connected
        plc_mock.disconnect.return_value = True
        plc_mock.write_parameter.return_value = write_success

        if read_values:
            def mock_read_parameter(param_id: str):
                return read_values.get(param_id, 0.0)
            plc_mock.read_parameter.side_effect = mock_read_parameter
        else:
            plc_mock.read_parameter.return_value = 0.0


@pytest.fixture
def mock_container():
    """Pytest fixture providing mock service container"""
    return MockServiceContainer()


@pytest.fixture
def mock_plc_interface(mock_container):
    """Pytest fixture for mocked PLC interface"""
    return mock_container.register_mock(IPLCInterface)


@pytest.fixture
def mock_database_service(mock_container):
    """Pytest fixture for mocked database service"""
    return mock_container.register_mock(IDatabaseService)


@pytest.fixture
def mock_parameter_logger(mock_container):
    """Pytest fixture for mocked parameter logger"""
    return mock_container.register_mock(IParameterLogger)


class AsyncTestCase:
    """Base class for async unit tests with DI mocking"""

    def __init__(self):
        self.mock_container = MockServiceContainer()

    async def setup_method(self):
        """Setup method called before each test"""
        self.mock_container.reset_mocks()

    async def teardown_method(self):
        """Teardown method called after each test"""
        pass

    def assert_service_called(self, service_type: Type, method_name: str, times: int = 1):
        """Assert that a service method was called specific number of times"""
        self.mock_container.verify_service_called(service_type, method_name, times)


# Test utilities for common scenarios
class PLCTestScenarios:
    """Pre-configured test scenarios for PLC testing"""

    @staticmethod
    def create_connected_plc_scenario(mock_container: MockServiceContainer):
        """Create a scenario with connected PLC"""
        mock_container.setup_plc_mock_behavior(
            connected=True,
            read_values={'PRESSURE': 15.5, 'TEMPERATURE': 25.0, 'FLOW_RATE': 100.0},
            write_success=True
        )

    @staticmethod
    def create_disconnected_plc_scenario(mock_container: MockServiceContainer):
        """Create a scenario with disconnected PLC"""
        plc_mock = mock_container.get_mock(IPLCInterface)
        plc_mock.connected = False
        plc_mock.initialize.return_value = False
        plc_mock.read_parameter.side_effect = Exception("PLC not connected")
        plc_mock.write_parameter.side_effect = Exception("PLC not connected")

    @staticmethod
    def create_intermittent_connection_scenario(mock_container: MockServiceContainer):
        """Create a scenario with intermittent PLC connection"""
        plc_mock = mock_container.get_mock(IPLCInterface)

        # Simulate connection failures every 3rd call
        call_count = 0
        def intermittent_read(param_id: str):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise Exception("Temporary connection lost")
            return 10.0

        plc_mock.read_parameter.side_effect = intermittent_read


class DatabaseTestScenarios:
    """Pre-configured test scenarios for database testing"""

    @staticmethod
    def create_healthy_database_scenario(mock_container: MockServiceContainer):
        """Create a scenario with healthy database"""
        db_mock = mock_container.get_mock(IDatabaseService)
        db_mock.connect.return_value = True
        db_mock.health_check.return_value = True
        db_mock.execute_query.return_value = []
        db_mock.execute_transaction.return_value = True

    @staticmethod
    def create_transaction_failure_scenario(mock_container: MockServiceContainer):
        """Create a scenario with database transaction failures"""
        db_mock = mock_container.get_mock(IDatabaseService)
        db_mock.execute_transaction.side_effect = Exception("Transaction rollback")
        db_mock.execute_query.return_value = []

    @staticmethod
    def create_connection_pool_exhaustion_scenario(mock_container: MockServiceContainer):
        """Create a scenario with connection pool exhaustion"""
        db_mock = mock_container.get_mock(IDatabaseService)
        db_mock.connect.side_effect = Exception("Connection pool exhausted")


# Performance testing utilities
class PerformanceTestUtilities:
    """Utilities for performance testing with mocks"""

    @staticmethod
    def create_high_latency_plc_scenario(mock_container: MockServiceContainer, latency_ms: int = 100):
        """Create PLC scenario with simulated latency"""
        plc_mock = mock_container.get_mock(IPLCInterface)

        async def delayed_read(param_id: str):
            await asyncio.sleep(latency_ms / 1000.0)  # Convert ms to seconds
            return 10.0

        async def delayed_write(param_id: str, value: float):
            await asyncio.sleep(latency_ms / 1000.0)
            return True

        plc_mock.read_parameter.side_effect = delayed_read
        plc_mock.write_parameter.side_effect = delayed_write

    @staticmethod
    def create_bulk_operation_scenario(mock_container: MockServiceContainer, bulk_size: int = 50):
        """Create scenario for testing bulk operations"""
        logger_mock = mock_container.get_mock(IParameterLogger)

        async def bulk_log_with_delay(parameters: list):
            # Simulate bulk processing time
            processing_time = len(parameters) * 0.001  # 1ms per parameter
            await asyncio.sleep(processing_time)
            return True

        logger_mock.log_bulk_parameters.side_effect = bulk_log_with_delay


if __name__ == "__main__":
    # Example usage
    container = MockServiceContainer()
    PLCTestScenarios.create_connected_plc_scenario(container)

    plc = container.get_service(IPLCInterface)
    print(f"PLC connected: {plc.connected}")
    print(f"Reading pressure: {asyncio.run(plc.read_parameter('PRESSURE'))}")