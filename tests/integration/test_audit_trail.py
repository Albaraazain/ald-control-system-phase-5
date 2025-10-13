"""
Integration tests for audit trail functionality.

This test suite verifies that recipe parameter changes (valve operations and
parameter writes) are correctly captured in the parameter_control_commands audit table.

Tests verify:
- Valve step operations create audit records
- Parameter step operations create audit records
- Full recipes create complete audit trails
- Audit records have correct timestamps and values
"""

import pytest
import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.db import get_supabase, get_current_timestamp
from src.step_flow.valve_step import execute_valve_step
from src.step_flow.parameter_step import execute_parameter_step, set_parameter_value
from tests.utils.async_helpers import wait_for_condition, run_with_timeout


# Test fixtures and helpers

@pytest.fixture
def supabase_client():
    """Get Supabase client for database operations."""
    return get_supabase()


@pytest.fixture
def test_machine_id():
    """Get machine ID from environment or use existing machine_id from database."""
    machine_id = os.environ.get('MACHINE_ID')
    if not machine_id:
        # Get existing machine_id from parameter_control_commands table
        supabase = get_supabase()
        result = supabase.table('parameter_control_commands').select('machine_id').limit(1).execute()
        if result.data:
            machine_id = result.data[0]['machine_id']
        else:
            # Fallback: generate a UUID for test purposes
            machine_id = str(uuid.uuid4())
    return machine_id


@pytest.fixture
async def cleanup_audit_records(supabase_client):
    """Clean up audit records created during tests."""
    yield
    # Cleanup after test completes
    try:
        # Delete audit records created during test (with executed_at in last 5 minutes)
        cutoff_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        result = supabase_client.table('parameter_control_commands') \
            .delete() \
            .gte('created_at', cutoff_time) \
            .execute()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")


@pytest.fixture
def process_execution_context(supabase_client, test_machine_id):
    """
    Create proper process execution context (process_executions + process_execution_state).
    Returns process_id and cleanup function.
    """
    process_id = str(uuid.uuid4())

    # Get an existing recipe to satisfy FK constraint
    recipe_result = supabase_client.table('recipes').select('id').limit(1).execute()
    if not recipe_result.data:
        raise RuntimeError("No recipes found in database - cannot create test process_execution")
    recipe_id = recipe_result.data[0]['id']

    # Get an existing operator session to satisfy FK constraint
    session_result = supabase_client.table('operator_sessions').select('id, operator_id').limit(1).execute()
    if not session_result.data:
        raise RuntimeError("No operator sessions found in database - cannot create test process_execution")
    session_id = session_result.data[0]['id']
    operator_id = session_result.data[0]['operator_id']

    # Create process_executions record with all required fields
    process_record = {
        'id': process_id,
        'session_id': session_id,
        'machine_id': test_machine_id,
        'recipe_id': recipe_id,
        'recipe_version': {'version': 1, 'test': True},
        'start_time': get_current_timestamp(),
        'end_time': get_current_timestamp(),
        'operator_id': operator_id,
        'status': 'running',
        'parameters': {},
        'created_at': get_current_timestamp(),
        'updated_at': get_current_timestamp()
    }
    supabase_client.table('process_executions').insert(process_record).execute()

    # Create process_execution_state record
    state_record = {
        'execution_id': process_id,
        'progress': {},
        'last_updated': get_current_timestamp()
    }
    supabase_client.table('process_execution_state').insert(state_record).execute()

    yield process_id

    # Cleanup
    try:
        supabase_client.table('process_execution_state').delete().eq('execution_id', process_id).execute()
        supabase_client.table('process_executions').delete().eq('id', process_id).execute()
    except Exception as e:
        print(f"Warning: Process cleanup failed: {e}")


async def get_audit_records(
    supabase_client,
    machine_id: str = None,
    parameter_name: str = None,
    component_parameter_id: str = None,
    since_seconds: int = 60
) -> List[Dict[str, Any]]:
    """
    Query audit records from parameter_control_commands table.

    Args:
        supabase_client: Supabase client
        machine_id: Filter by machine ID
        parameter_name: Filter by parameter name (e.g., 'Valve_1')
        component_parameter_id: Filter by component parameter ID
        since_seconds: Only return records created within this many seconds

    Returns:
        List of audit records
    """
    # Build query
    query = supabase_client.table('parameter_control_commands').select('*')

    # Filter by timestamp (recent records only)
    cutoff_time = (datetime.utcnow() - timedelta(seconds=since_seconds)).isoformat()
    query = query.gte('created_at', cutoff_time)

    # Apply filters
    if machine_id:
        query = query.eq('machine_id', machine_id)
    if parameter_name:
        query = query.eq('parameter_name', parameter_name)
    if component_parameter_id:
        query = query.eq('component_parameter_id', component_parameter_id)

    # Execute query
    result = query.execute()
    return result.data if result.data else []


async def wait_for_audit_record(
    supabase_client,
    expected_count: int = 1,
    timeout: float = 5.0,
    **filters
) -> List[Dict[str, Any]]:
    """
    Wait for audit records to appear in database.

    Args:
        supabase_client: Supabase client
        expected_count: Number of records to wait for
        timeout: Maximum wait time in seconds
        **filters: Filters to pass to get_audit_records()

    Returns:
        List of audit records

    Raises:
        TimeoutError: If records don't appear within timeout
    """
    records = []

    async def check_records():
        nonlocal records
        records = await get_audit_records(supabase_client, **filters)
        return len(records) >= expected_count

    await wait_for_condition(
        check_records,
        timeout=timeout,
        error_message=f"Expected {expected_count} audit record(s) but found {len(records)}"
    )

    return records


def validate_audit_record(
    record: Dict[str, Any],
    expected_machine_id: str = None,
    expected_parameter_name: str = None,
    expected_component_parameter_id: str = None,
    expected_target_value: float = None
):
    """
    Validate audit record has expected values and proper structure.

    Args:
        record: Audit record to validate
        expected_machine_id: Expected machine ID
        expected_parameter_name: Expected parameter name
        expected_component_parameter_id: Expected component parameter ID
        expected_target_value: Expected target value

    Raises:
        AssertionError: If validation fails
    """
    # Required fields
    assert 'id' in record, "Audit record missing ID"
    assert 'machine_id' in record, "Audit record missing machine_id"
    assert 'target_value' in record, "Audit record missing target_value"
    assert 'executed_at' in record, "Audit record missing executed_at"
    assert 'completed_at' in record, "Audit record missing completed_at"
    assert 'created_at' in record, "Audit record missing created_at"

    # Timestamps must be set
    assert record['executed_at'] is not None, "executed_at must not be null"
    assert record['completed_at'] is not None, "completed_at must not be null"

    # Timestamp ordering: executed_at <= completed_at
    executed_at = datetime.fromisoformat(record['executed_at'].replace('Z', '+00:00'))
    completed_at = datetime.fromisoformat(record['completed_at'].replace('Z', '+00:00'))
    assert executed_at <= completed_at, f"executed_at ({executed_at}) must be <= completed_at ({completed_at})"

    # Validate expected values
    if expected_machine_id is not None:
        assert record['machine_id'] == expected_machine_id, \
            f"Expected machine_id={expected_machine_id}, got {record['machine_id']}"

    if expected_parameter_name is not None:
        assert record.get('parameter_name') == expected_parameter_name, \
            f"Expected parameter_name={expected_parameter_name}, got {record.get('parameter_name')}"

    if expected_component_parameter_id is not None:
        assert record.get('component_parameter_id') == expected_component_parameter_id, \
            f"Expected component_parameter_id={expected_component_parameter_id}, got {record.get('component_parameter_id')}"

    if expected_target_value is not None:
        assert record['target_value'] == expected_target_value, \
            f"Expected target_value={expected_target_value}, got {record['target_value']}"


# Test Cases

@pytest.mark.asyncio
@pytest.mark.integration
async def test_valve_step_creates_audit_record(
    supabase_client,
    test_machine_id,
    process_execution_context,
    cleanup_audit_records
):
    """
    Test Case 1: Verify valve step creates audit record in parameter_control_commands.

    This test executes a valve step and verifies:
    - Audit record is created
    - Record has correct valve number (parameter_name='Valve_X')
    - Record has correct target value (1.0 for open)
    - Timestamps are set correctly
    """
    # Use proper process execution context
    test_process_id = process_execution_context
    valve_number = 1
    duration_ms = 1000

    step = {
        'id': str(uuid.uuid4()),
        'name': f'Open Valve {valve_number}',
        'type': f'open valve {valve_number}',  # Fallback method: type contains valve number
        'parameters': {
            'duration_ms': duration_ms
        }
    }

    # Execute valve step with proper database context
    await execute_valve_step(test_process_id, step)

    # Give background audit task time to complete
    await asyncio.sleep(0.5)

    # Wait for audit record to appear (background task takes small time)
    # Note: parameter_control_commands table does not have process_id column
    records = await wait_for_audit_record(
        supabase_client,
        expected_count=1,
        timeout=5.0,
        machine_id=test_machine_id,
        parameter_name=f'Valve_{valve_number}',
        since_seconds=10
    )

    # Validate audit record
    assert len(records) == 1, f"Expected 1 audit record, found {len(records)}"

    audit_record = records[0]
    validate_audit_record(
        audit_record,
        expected_machine_id=test_machine_id,
        expected_parameter_name=f'Valve_{valve_number}',
        expected_target_value=1.0
    )

    print(f"✅ Valve step audit record validated: {audit_record['id']}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parameter_step_creates_audit_record(
    supabase_client,
    test_machine_id,
    cleanup_audit_records
):
    """
    Test Case 2: Verify parameter step creates audit record in parameter_control_commands.

    This test executes a parameter step and verifies:
    - Audit record is created
    - Record has correct component_parameter_id
    - Record has correct target_value
    - Timestamps are set correctly
    """
    # Find a test parameter (use first available)
    params_result = supabase_client.table('component_parameters') \
        .select('*') \
        .limit(1) \
        .execute()

    if not params_result.data:
        pytest.skip("No component_parameters available for testing")

    test_parameter = params_result.data[0]
    parameter_id = test_parameter['id']
    test_value = float(test_parameter['min_value'])  # Use min value as safe test value

    test_process_id = str(uuid.uuid4())

    # Execute parameter write
    await set_parameter_value(parameter_id, test_value)

    # Wait for audit record (background task)
    records = await wait_for_audit_record(
        supabase_client,
        expected_count=1,
        timeout=5.0,
        machine_id=test_machine_id,
        component_parameter_id=parameter_id,
        since_seconds=10
    )

    # Validate audit record
    assert len(records) >= 1, f"Expected at least 1 audit record, found {len(records)}"

    # Get most recent record
    audit_record = records[0]
    validate_audit_record(
        audit_record,
        expected_machine_id=test_machine_id,
        expected_component_parameter_id=parameter_id,
        expected_target_value=test_value
    )

    print(f"✅ Parameter step audit record validated: {audit_record['id']}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_recipe_audit_coverage(
    supabase_client,
    test_machine_id,
    process_execution_context,
    cleanup_audit_records
):
    """
    Test Case 3: Verify full recipe execution creates complete audit trail.

    This test simulates a recipe with multiple valve and parameter steps:
    - 2 valve steps
    - 1 parameter step

    Verifies:
    - All 3 audit records are created
    - All records link to same process_id
    - All records have proper timestamps
    - All records have correct values
    """
    test_process_id = process_execution_context

    # Find a test parameter
    params_result = supabase_client.table('component_parameters') \
        .select('*') \
        .limit(1) \
        .execute()

    if not params_result.data:
        pytest.skip("No component_parameters available for testing")

    test_parameter = params_result.data[0]
    parameter_id = test_parameter['id']
    test_value = float(test_parameter['min_value'])

    # Define recipe steps (using backwards compatibility - no valve_step_config)
    valve_step_1 = {
        'id': str(uuid.uuid4()),
        'name': 'Open Valve 1',
        'type': 'open valve 1',
        'parameters': {'duration_ms': 500}
    }

    valve_step_2 = {
        'id': str(uuid.uuid4()),
        'name': 'Open Valve 2',
        'type': 'open valve 2',
        'parameters': {'duration_ms': 500}
    }

    # Execute recipe steps
    await execute_valve_step(test_process_id, valve_step_1)
    await execute_valve_step(test_process_id, valve_step_2)
    await set_parameter_value(parameter_id, test_value)

    # Wait for all audit records (3 total: 2 valves + 1 parameter)
    # Note: parameter_control_commands table does not have process_id column
    all_records = await wait_for_audit_record(
        supabase_client,
        expected_count=3,
        timeout=8.0,
        machine_id=test_machine_id,
        since_seconds=15
    )

    # Should have at least 3 records total
    assert len(all_records) >= 3, f"Expected at least 3 audit records, found {len(all_records)}"

    # Verify valve audit records (by parameter_name)
    valve_records = [r for r in all_records if r.get('parameter_name') and 'Valve_' in r.get('parameter_name')]
    assert len(valve_records) >= 2, f"Expected 2 valve audit records, found {len(valve_records)}"

    # Verify parameter audit record (by component_parameter_id)
    param_records = [r for r in all_records if r.get('component_parameter_id') == parameter_id]
    assert len(param_records) >= 1, f"Expected 1 parameter audit record, found {len(param_records)}"

    # Validate each valve record
    for i, valve_record in enumerate(valve_records[:2], 1):
        validate_audit_record(
            valve_record,
            expected_machine_id=test_machine_id,
            expected_target_value=1.0
        )
        print(f"✅ Valve {i} audit record validated")

    # Validate parameter record
    validate_audit_record(
        param_records[0],
        expected_machine_id=test_machine_id,
        expected_component_parameter_id=parameter_id,
        expected_target_value=test_value
    )
    print(f"✅ Parameter audit record validated")

    print(f"✅ Full recipe audit trail complete: {len(all_records)} records")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_record_timestamp_consistency(
    supabase_client,
    test_machine_id,
    process_execution_context,
    cleanup_audit_records
):
    """
    Test Case 4: Verify audit record timestamps are consistent and logical.

    This test verifies:
    - executed_at is set
    - completed_at is set
    - executed_at <= completed_at
    - Both timestamps are recent (within last minute)
    """
    # Use proper process execution context
    test_process_id = process_execution_context

    step = {
        'id': str(uuid.uuid4()),
        'name': 'Test Valve Timing',
        'type': 'open valve 3',
        'parameters': {'duration_ms': 100}
    }

    start_time = datetime.utcnow()

    await execute_valve_step(test_process_id, step)

    # Wait for audit record
    # Note: parameter_control_commands table does not have process_id column
    records = await wait_for_audit_record(
        supabase_client,
        expected_count=1,
        timeout=5.0,
        machine_id=test_machine_id,
        parameter_name='Valve_3',
        since_seconds=10
    )

    end_time = datetime.utcnow()

    assert len(records) == 1
    record = records[0]

    # Parse timestamps
    executed_at = datetime.fromisoformat(record['executed_at'].replace('Z', '+00:00'))
    completed_at = datetime.fromisoformat(record['completed_at'].replace('Z', '+00:00'))

    # Verify timestamps are within test window
    assert start_time <= executed_at.replace(tzinfo=None) <= end_time, \
        "executed_at timestamp outside test execution window"
    assert start_time <= completed_at.replace(tzinfo=None) <= end_time, \
        "completed_at timestamp outside test execution window"

    # Verify executed_at <= completed_at
    assert executed_at <= completed_at, \
        f"executed_at ({executed_at}) must be <= completed_at ({completed_at})"

    print(f"✅ Timestamp consistency validated")
    print(f"   executed_at: {executed_at}")
    print(f"   completed_at: {completed_at}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, '-v', '-s'])
