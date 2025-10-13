"""
PLC-related test fixtures for simulating PLC hardware.

Provides fixtures for:
- Real SimulationPLC instance (not mocks)
- PLC with preloaded test parameters
- PLC state reset utilities
- PLC connection monitoring
"""

import pytest
import pytest_asyncio
import os
from typing import Dict, Any, Optional
from plc.simulation import SimulationPLC


@pytest_asyncio.fixture(scope="function")
async def plc_simulation():
    """
    Provide clean SimulationPLC instance for each test.

    Returns:
        SimulationPLC: Fresh PLC instance in demo mode

    Example:
        async def test_plc_read(plc_simulation):
            await plc_simulation.connect()
            value = await plc_simulation.read_parameter(param_id=1)
            assert value is not None
    """
    # Set demo mode to avoid real database dependencies
    os.environ['DEMO_MODE'] = 'true'

    plc = SimulationPLC()
    await plc.initialize()

    yield plc

    # Cleanup
    if plc.connected:
        await plc.disconnect()


@pytest_asyncio.fixture(scope="function")
async def plc_with_parameters(plc_simulation):
    """
    Provide SimulationPLC preloaded with test parameters.

    Returns:
        SimulationPLC: PLC with 10 test parameters loaded

    Example:
        async def test_read_all(plc_with_parameters):
            values = await plc_with_parameters.read_all_parameters()
            assert len(values) >= 10
    """
    # PLC is already initialized and connected from plc_simulation fixture

    # Load test parameters
    test_parameters = [
        {
            'id': i,
            'name': f'test_param_{i}',
            'modbus_address': 100 + i,
            'read_modbus_address': 100 + i,
            'write_modbus_address': 100 + i,
            'data_type': 'float',
            'min_value': 0.0,
            'max_value': 100.0,
            'default_value': 50.0,
            'is_writable': True,
            'scaling_factor': 1.0,
            'offset': 0.0
        }
        for i in range(1, 11)
    ]

    # Inject parameters directly into PLC metadata
    for param in test_parameters:
        plc_simulation.param_metadata[param['id']] = param
        plc_simulation.current_values[param['id']] = param['default_value']
        plc_simulation.set_values[param['id']] = param['default_value']

        # Use public API to initialize registers
        address = param['modbus_address']
        await plc_simulation.write_holding_register(address, int(param['default_value']))

    return plc_simulation


@pytest.fixture
def plc_state_validator():
    """
    Utility fixture for validating PLC state.

    Returns:
        PLCStateValidator: Helper class for assertions

    Example:
        async def test_plc_write(plc_simulation, plc_state_validator):
            await plc_simulation.write_parameter(param_id=1, value=75.0)
            await plc_state_validator.assert_parameter_value(
                plc_simulation, param_id=1, expected=75.0
            )
    """
    class PLCStateValidator:
        @staticmethod
        async def assert_parameter_value(
            plc: SimulationPLC,
            param_id: int,
            expected: float,
            tolerance: float = 0.01
        ):
            """Assert parameter has expected value within tolerance."""
            actual = await plc.read_parameter(param_id)
            assert actual is not None, f"Parameter {param_id} returned None"
            assert abs(actual - expected) < tolerance, \
                f"Parameter {param_id}: expected {expected}, got {actual}"

        @staticmethod
        async def assert_parameter_in_range(
            plc: SimulationPLC,
            param_id: int,
            min_value: float,
            max_value: float
        ):
            """Assert parameter value is within specified range."""
            actual = await plc.read_parameter(param_id)
            assert actual is not None, f"Parameter {param_id} returned None"
            assert min_value <= actual <= max_value, \
                f"Parameter {param_id} value {actual} not in range [{min_value}, {max_value}]"

        @staticmethod
        def assert_connected(plc: SimulationPLC):
            """Assert PLC is connected."""
            assert plc.connected, "PLC is not connected"

        @staticmethod
        def assert_disconnected(plc: SimulationPLC):
            """Assert PLC is disconnected."""
            assert not plc.connected, "PLC is still connected"

        @staticmethod
        async def assert_parameters_loaded(plc: SimulationPLC, min_count: int = 1):
            """Assert minimum number of parameters are loaded."""
            assert len(plc.param_metadata) >= min_count, \
                f"Expected at least {min_count} parameters, found {len(plc.param_metadata)}"

    return PLCStateValidator()


@pytest.fixture
def plc_connection_monitor():
    """
    Monitor PLC connection health and performance.

    Returns:
        PLCConnectionMonitor: Connection monitoring utilities

    Example:
        async def test_plc_reliability(plc_simulation, plc_connection_monitor):
            async with plc_connection_monitor.track_operations(plc_simulation) as tracker:
                # Perform operations
                await plc_simulation.read_parameter(1)
                await plc_simulation.write_parameter(1, 75.0)

            tracker.assert_success_rate(min_rate=0.99)
    """
    class PLCConnectionMonitor:
        def __init__(self):
            self.operation_count = 0
            self.failure_count = 0
            self.read_times = []
            self.write_times = []

        class OperationTracker:
            def __init__(self, monitor, plc):
                self.monitor = monitor
                self.plc = plc

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            def assert_success_rate(self, min_rate: float = 0.95):
                """Assert operation success rate meets minimum."""
                if self.monitor.operation_count == 0:
                    return

                success_count = self.monitor.operation_count - self.monitor.failure_count
                success_rate = success_count / self.monitor.operation_count

                assert success_rate >= min_rate, \
                    f"Success rate {success_rate:.2%} below minimum {min_rate:.2%}"

        def track_operations(self, plc: SimulationPLC):
            """Context manager to track PLC operations."""
            return self.OperationTracker(self, plc)

        def record_read(self, success: bool, duration: float):
            """Record a read operation."""
            self.operation_count += 1
            if not success:
                self.failure_count += 1
            else:
                self.read_times.append(duration)

        def record_write(self, success: bool, duration: float):
            """Record a write operation."""
            self.operation_count += 1
            if not success:
                self.failure_count += 1
            else:
                self.write_times.append(duration)

    return PLCConnectionMonitor()


@pytest.fixture
def plc_reset_utility():
    """
    Utility for resetting PLC state during tests.

    Returns:
        PLCResetUtility: State reset functions

    Example:
        async def test_plc_isolation(plc_simulation, plc_reset_utility):
            # Modify state
            await plc_simulation.write_parameter(1, 99.0)

            # Reset to defaults
            await plc_reset_utility.reset_all_parameters(plc_simulation)

            # Verify reset
            value = await plc_simulation.read_parameter(1)
            assert value == 50.0  # default value
    """
    class PLCResetUtility:
        @staticmethod
        async def reset_all_parameters(plc: SimulationPLC):
            """Reset all parameters to their default values."""
            for param_id, metadata in plc.param_metadata.items():
                default_value = metadata.get('default_value', 0.0)
                plc.current_values[param_id] = default_value
                plc.set_values[param_id] = default_value

                # Reset in Modbus registers using public API
                if 'modbus_address' in metadata:
                    address = metadata['modbus_address']
                    data_type = metadata.get('data_type', 'float')
                    if data_type == 'binary':
                        await plc.write_coil(address, bool(default_value))
                    else:
                        await plc.write_holding_register(address, default_value)

        @staticmethod
        async def clear_all_parameters(plc: SimulationPLC):
            """Remove all parameters from PLC."""
            plc.param_metadata.clear()
            plc.current_values.clear()
            plc.set_values.clear()
            plc._holding_registers.clear()
            plc._coils.clear()

        @staticmethod
        async def set_parameter_bulk(
            plc: SimulationPLC,
            updates: Dict[int, float]
        ):
            """Set multiple parameters at once."""
            for param_id, value in updates.items():
                if param_id in plc.param_metadata:
                    plc.current_values[param_id] = value
                    plc.set_values[param_id] = value

                    metadata = plc.param_metadata[param_id]
                    if 'modbus_address' in metadata:
                        address = metadata['modbus_address']
                        data_type = metadata.get('data_type', 'float')
                        if data_type == 'binary':
                            await plc.write_coil(address, bool(value))
                        else:
                            await plc.write_holding_register(address, value)

    return PLCResetUtility()


@pytest_asyncio.fixture(scope="function")
async def plc_with_binary_parameters(plc_simulation):
    """
    Provide SimulationPLC with binary (coil) parameters for testing.

    Returns:
        SimulationPLC: PLC with binary parameters configured

    Example:
        async def test_valve_control(plc_with_binary_parameters):
            await plc_with_binary_parameters.write_parameter(param_id=101, value=1.0)
            value = await plc_with_binary_parameters.read_parameter(param_id=101)
            assert value == 1.0
    """
    # PLC is already initialized and connected from plc_simulation fixture

    # Add binary parameters (valves, relays, etc.)
    binary_params = [
        {
            'id': 100 + i,
            'name': f'valve_{i}',
            'modbus_address': 1000 + i,
            'read_modbus_address': 1000 + i,
            'write_modbus_address': 1000 + i,
            'data_type': 'binary',
            'min_value': 0.0,
            'max_value': 1.0,
            'default_value': 0.0,
            'is_writable': True,
            'scaling_factor': 1.0,
            'offset': 0.0
        }
        for i in range(1, 11)
    ]

    for param in binary_params:
        plc_simulation.param_metadata[param['id']] = param
        plc_simulation.current_values[param['id']] = param['default_value']
        plc_simulation.set_values[param['id']] = param['default_value']

        # Use public API to set coil registers
        address = param['modbus_address']
        await plc_simulation.write_coil(address, bool(param['default_value']))

    return plc_simulation


@pytest.fixture
def mock_plc_manager():
    """
    Mock PLCManager for unit tests that don't need real PLC simulation.

    Returns:
        Mock: Mocked PLCManager with common methods

    Example:
        def test_service_with_mock(mock_plc_manager):
            service = MyService(plc_manager=mock_plc_manager)
            mock_plc_manager.read_parameter.return_value = 42.0
            result = service.get_parameter_value(1)
            assert result == 42.0
    """
    from unittest.mock import AsyncMock, Mock

    mock_manager = Mock()
    mock_manager.connect = AsyncMock(return_value=True)
    mock_manager.disconnect = AsyncMock(return_value=True)
    mock_manager.read_parameter = AsyncMock(return_value=42.0)
    mock_manager.write_parameter = AsyncMock(return_value=True)
    mock_manager.read_all_parameters = AsyncMock(return_value={1: 42.0, 2: 43.0})
    mock_manager.initialize = AsyncMock(return_value=True)
    mock_manager.connected = True

    return mock_manager
