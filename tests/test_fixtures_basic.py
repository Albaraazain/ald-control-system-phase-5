"""
Basic smoke tests to verify test framework fixtures are working.

This test file validates that all new fixtures can be imported and used.
Run with: pytest tests/test_fixtures_basic.py -v
"""

import pytest


@pytest.mark.asyncio
async def test_async_helpers_import():
    """Test that async helpers can be imported and used."""
    from tests.utils.async_helpers import wait_for_condition

    # Test simple condition wait
    result = await wait_for_condition(
        lambda: True,
        timeout=1.0
    )
    assert result is True


@pytest.mark.asyncio
async def test_plc_simulation_fixture(plc_simulation):
    """Test that PLC simulation fixture works."""
    assert plc_simulation is not None
    # PLC should be initialized
    assert hasattr(plc_simulation, 'disconnect')
    assert hasattr(plc_simulation, 'read_parameter')
    assert hasattr(plc_simulation, 'write_parameter')


@pytest.mark.asyncio
async def test_plc_with_parameters_fixture(plc_with_parameters):
    """Test that PLC with parameters fixture works."""
    assert plc_with_parameters is not None

    # Should have test parameters loaded
    assert len(plc_with_parameters.param_metadata) >= 10


@pytest.mark.asyncio
async def test_plc_state_validator_fixture(plc_simulation, plc_state_validator):
    """Test that PLC state validator fixture works."""
    # Validator should have assertion methods
    assert hasattr(plc_state_validator, 'assert_connected')
    assert hasattr(plc_state_validator, 'assert_parameter_value')

    # PLC should be initialized and connected
    plc_state_validator.assert_connected(plc_simulation)


def test_terminal_health_monitor_fixture(terminal_health_monitor):
    """Test that terminal health monitor fixture works."""
    assert terminal_health_monitor is not None
    assert hasattr(terminal_health_monitor, 'is_process_alive')
    assert hasattr(terminal_health_monitor, 'check_lock_file_exists')


@pytest.mark.asyncio
async def test_database_validator_fixture(database_validator):
    """Test that database validator fixture works."""
    assert database_validator is not None
    assert hasattr(database_validator, 'assert_record_exists')
    assert hasattr(database_validator, 'assert_record_count')


def test_pytest_markers_registered():
    """Test that custom pytest markers are registered."""
    # This test just needs to run without errors
    # The markers are validated by pytest at collection time
    pass


def test_conftest_imports():
    """Test that conftest can import all fixtures."""
    # If this test runs, conftest imported successfully
    import tests.conftest
    assert hasattr(tests.conftest, 'pytest_configure')
    assert hasattr(tests.conftest, 'pytest_addoption')
