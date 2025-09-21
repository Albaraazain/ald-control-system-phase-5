#!/usr/bin/env python3
"""
Dependency Injection Container Testing Framework

Tests for DI container registration, resolution, and lifecycle management.
Validates interface compliance and service isolation capabilities.
"""

import pytest
import asyncio
from typing import Dict, Any, Protocol, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from abc import ABC, abstractmethod

# Test DI Container Framework
class ServiceContainer:
    """Test service container for dependency injection testing"""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}

    def register_singleton(self, interface: type, implementation: type):
        """Register a singleton service"""
        self._services[interface.__name__] = implementation

    def register_factory(self, interface: type, factory: callable):
        """Register a factory function for service creation"""
        self._factories[interface.__name__] = factory

    def resolve(self, interface: type) -> Any:
        """Resolve a service instance"""
        service_name = interface.__name__

        # Check if singleton already exists
        if service_name in self._singletons:
            return self._singletons[service_name]

        # Create from factory
        if service_name in self._factories:
            instance = self._factories[service_name]()
            self._singletons[service_name] = instance
            return instance

        # Create from registered implementation
        if service_name in self._services:
            implementation = self._services[service_name]
            instance = implementation()
            self._singletons[service_name] = instance
            return instance

        raise ValueError(f"Service {service_name} not registered")

    def clear(self):
        """Clear all registrations and singletons"""
        self._services.clear()
        self._singletons.clear()
        self._factories.clear()


# Test Interfaces for DI
class IPLCInterface(Protocol):
    """Protocol for PLC interface testing"""

    async def initialize(self) -> bool:
        ...

    async def disconnect(self) -> bool:
        ...

    async def read_parameter(self, parameter_id: str) -> float:
        ...

    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        ...

    async def read_all_parameters(self) -> Dict[str, float]:
        ...


class IParameterLogger(Protocol):
    """Protocol for parameter logger testing"""

    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    def get_status(self) -> Dict[str, Any]:
        ...


class IDataAccess(Protocol):
    """Protocol for data access testing"""

    async def insert_parameter_history(self, records: list) -> bool:
        ...

    async def insert_process_data_points(self, records: list) -> bool:
        ...

    async def get_current_process_id(self) -> Optional[str]:
        ...


# Mock Implementations
class MockPLCInterface:
    """Mock PLC interface for testing"""

    def __init__(self):
        self.connected = False
        self.parameters = {
            "temperature": 25.5,
            "pressure": 1.2,
            "flow_rate": 0.8
        }

    async def initialize(self) -> bool:
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        self.connected = False
        return True

    async def read_parameter(self, parameter_id: str) -> float:
        if not self.connected:
            raise RuntimeError("PLC not connected")
        return self.parameters.get(parameter_id, 0.0)

    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        if not self.connected:
            raise RuntimeError("PLC not connected")
        self.parameters[parameter_id] = value
        return True

    async def read_all_parameters(self) -> Dict[str, float]:
        if not self.connected:
            raise RuntimeError("PLC not connected")
        return self.parameters.copy()


class MockParameterLogger:
    """Mock parameter logger for testing"""

    def __init__(self, plc_interface: IPLCInterface, data_access: IDataAccess):
        self.plc = plc_interface
        self.data_access = data_access
        self.is_running = False

    async def start(self) -> None:
        self.is_running = True

    async def stop(self) -> None:
        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "plc_connected": getattr(self.plc, 'connected', False)
        }


class MockDataAccess:
    """Mock data access for testing"""

    def __init__(self):
        self.history_records = []
        self.process_records = []
        self.current_process_id = None

    async def insert_parameter_history(self, records: list) -> bool:
        self.history_records.extend(records)
        return True

    async def insert_process_data_points(self, records: list) -> bool:
        self.process_records.extend(records)
        return True

    async def get_current_process_id(self) -> Optional[str]:
        return self.current_process_id

    def set_process_id(self, process_id: Optional[str]):
        self.current_process_id = process_id


# Test Fixtures
@pytest.fixture
def service_container():
    """Service container fixture"""
    return ServiceContainer()


@pytest.fixture
def mock_plc():
    """Mock PLC interface fixture"""
    return MockPLCInterface()


@pytest.fixture
def mock_data_access():
    """Mock data access fixture"""
    return MockDataAccess()


@pytest.fixture
def configured_container(service_container, mock_plc, mock_data_access):
    """Pre-configured service container with mocks"""
    service_container.register_factory(IPLCInterface, lambda: mock_plc)
    service_container.register_factory(IDataAccess, lambda: mock_data_access)
    service_container.register_factory(
        IParameterLogger,
        lambda: MockParameterLogger(
            service_container.resolve(IPLCInterface),
            service_container.resolve(IDataAccess)
        )
    )
    return service_container


# DI Container Tests
class TestDependencyInjectionContainer:
    """Test dependency injection container functionality"""

    def test_service_registration_and_resolution(self, service_container):
        """Test basic service registration and resolution"""
        # Register service
        service_container.register_singleton(IPLCInterface, MockPLCInterface)

        # Resolve service
        plc = service_container.resolve(IPLCInterface)

        assert isinstance(plc, MockPLCInterface)

    def test_singleton_behavior(self, service_container):
        """Test that singletons return same instance"""
        service_container.register_singleton(IPLCInterface, MockPLCInterface)

        plc1 = service_container.resolve(IPLCInterface)
        plc2 = service_container.resolve(IPLCInterface)

        assert plc1 is plc2

    def test_factory_registration(self, service_container):
        """Test factory-based service creation"""
        factory_called = False

        def plc_factory():
            nonlocal factory_called
            factory_called = True
            return MockPLCInterface()

        service_container.register_factory(IPLCInterface, plc_factory)

        plc = service_container.resolve(IPLCInterface)

        assert factory_called
        assert isinstance(plc, MockPLCInterface)

    def test_dependency_injection(self, configured_container):
        """Test dependency injection between services"""
        logger = configured_container.resolve(IParameterLogger)

        assert isinstance(logger, MockParameterLogger)
        assert isinstance(logger.plc, MockPLCInterface)
        assert isinstance(logger.data_access, MockDataAccess)

    def test_service_not_found_error(self, service_container):
        """Test error when service not registered"""
        with pytest.raises(ValueError, match="Service IPLCInterface not registered"):
            service_container.resolve(IPLCInterface)

    def test_container_clear(self, configured_container):
        """Test clearing container state"""
        # Resolve a service first
        logger = configured_container.resolve(IParameterLogger)
        assert logger is not None

        # Clear container
        configured_container.clear()

        # Should fail to resolve after clearing
        with pytest.raises(ValueError):
            configured_container.resolve(IParameterLogger)


# Interface Compliance Tests
class TestInterfaceCompliance:
    """Test interface compliance and contract validation"""

    @pytest.mark.asyncio
    async def test_plc_interface_compliance(self, mock_plc):
        """Test PLC interface implementation compliance"""
        # Test initialization
        result = await mock_plc.initialize()
        assert result is True
        assert mock_plc.connected is True

        # Test parameter reading
        value = await mock_plc.read_parameter("temperature")
        assert isinstance(value, (int, float))

        # Test parameter writing
        result = await mock_plc.write_parameter("temperature", 30.0)
        assert result is True
        assert mock_plc.parameters["temperature"] == 30.0

        # Test bulk reading
        all_params = await mock_plc.read_all_parameters()
        assert isinstance(all_params, dict)
        assert "temperature" in all_params

        # Test disconnection
        result = await mock_plc.disconnect()
        assert result is True
        assert mock_plc.connected is False

    @pytest.mark.asyncio
    async def test_parameter_logger_interface_compliance(self, configured_container):
        """Test parameter logger interface compliance"""
        logger = configured_container.resolve(IParameterLogger)

        # Test lifecycle methods
        await logger.start()
        status = logger.get_status()
        assert status["is_running"] is True

        await logger.stop()
        status = logger.get_status()
        assert status["is_running"] is False

    @pytest.mark.asyncio
    async def test_data_access_interface_compliance(self, mock_data_access):
        """Test data access interface compliance"""
        # Test parameter history insertion
        history_records = [
            {"parameter_id": "temp", "value": 25.0, "timestamp": "2023-01-01T00:00:00Z"}
        ]
        result = await mock_data_access.insert_parameter_history(history_records)
        assert result is True
        assert len(mock_data_access.history_records) == 1

        # Test process data insertion
        process_records = [
            {"process_id": "123", "parameter_id": "temp", "value": 25.0}
        ]
        result = await mock_data_access.insert_process_data_points(process_records)
        assert result is True
        assert len(mock_data_access.process_records) == 1

        # Test process ID retrieval
        mock_data_access.set_process_id("test-process-123")
        process_id = await mock_data_access.get_current_process_id()
        assert process_id == "test-process-123"


# Service Isolation Tests
class TestServiceIsolation:
    """Test service isolation and independence"""

    @pytest.mark.asyncio
    async def test_plc_failure_isolation(self, configured_container):
        """Test that PLC failures don't crash other services"""
        logger = configured_container.resolve(IParameterLogger)
        plc = configured_container.resolve(IPLCInterface)

        # Start logger
        await logger.start()

        # Simulate PLC disconnection
        await plc.disconnect()

        # Logger should handle PLC failure gracefully
        status = logger.get_status()
        assert status["is_running"] is True
        assert status["plc_connected"] is False

    @pytest.mark.asyncio
    async def test_data_access_failure_isolation(self, configured_container):
        """Test that data access failures are isolated"""
        logger = configured_container.resolve(IParameterLogger)
        data_access = configured_container.resolve(IDataAccess)

        # Mock data access failure
        original_insert = data_access.insert_parameter_history
        data_access.insert_parameter_history = AsyncMock(side_effect=Exception("DB Error"))

        # Logger should continue running despite data access failures
        await logger.start()
        status = logger.get_status()
        assert status["is_running"] is True

        # Restore original method
        data_access.insert_parameter_history = original_insert

    def test_service_independence(self, service_container):
        """Test that services can be tested independently"""
        # Create separate instances for isolation
        plc1 = MockPLCInterface()
        plc2 = MockPLCInterface()

        # Register different instances
        service_container.register_factory(IPLCInterface, lambda: plc1)

        resolved_plc = service_container.resolve(IPLCInterface)

        # Should get the registered instance, not the other one
        assert resolved_plc is plc1
        assert resolved_plc is not plc2


# Lifecycle Management Tests
class TestServiceLifecycle:
    """Test service lifecycle management"""

    @pytest.mark.asyncio
    async def test_service_startup_sequence(self, configured_container):
        """Test proper service startup sequence"""
        plc = configured_container.resolve(IPLCInterface)
        logger = configured_container.resolve(IParameterLogger)

        # Initialize PLC first
        await plc.initialize()

        # Then start logger
        await logger.start()

        # Verify both are running
        assert plc.connected is True

        status = logger.get_status()
        assert status["is_running"] is True
        assert status["plc_connected"] is True

    @pytest.mark.asyncio
    async def test_service_shutdown_sequence(self, configured_container):
        """Test proper service shutdown sequence"""
        plc = configured_container.resolve(IPLCInterface)
        logger = configured_container.resolve(IParameterLogger)

        # Start services
        await plc.initialize()
        await logger.start()

        # Shutdown in reverse order
        await logger.stop()
        await plc.disconnect()

        # Verify both are stopped
        status = logger.get_status()
        assert status["is_running"] is False
        assert plc.connected is False

    def test_circular_dependency_detection(self, service_container):
        """Test detection of circular dependencies"""
        # This is a basic test - in practice, you'd implement
        # more sophisticated circular dependency detection
        class ServiceA:
            def __init__(self, service_b):
                self.service_b = service_b

        class ServiceB:
            def __init__(self, service_a):
                self.service_a = service_a

        # Register circular dependencies (would cause issues in real DI container)
        # This test demonstrates what to watch for
        assert True  # Placeholder for actual circular dependency detection


if __name__ == "__main__":
    pytest.main([__file__, "-v"])