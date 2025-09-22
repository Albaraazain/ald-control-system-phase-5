"""
Safety Assertions for 3-Terminal Testing

Provides safety-specific assertion functions to validate
critical safety requirements in the ALD control system.
"""

import asyncio
import pytest
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


async def assert_emergency_state(terminal, error_message: str):
    """Assert that terminal is in emergency state."""
    is_emergency = await terminal.is_in_emergency_state()
    assert is_emergency, f"{error_message}: Terminal {terminal.terminal_id} not in emergency state"


async def assert_all_valves_closed(hardware_simulator, error_message: str):
    """Assert that all valves are closed for safety."""
    valve_states = await hardware_simulator.get_all_valve_states()

    open_valves = []
    for valve_id, state in valve_states.items():
        if state['is_open']:
            open_valves.append(valve_id)

    assert len(open_valves) == 0, f"{error_message}: Valves {open_valves} are still open"


async def assert_plc_safe_state(hardware_simulator, error_message: str):
    """Assert that PLC is in safe state."""
    plc_state = await hardware_simulator.get_plc_state()

    assert plc_state['state'] in ['IDLE', 'EMERGENCY'], \
        f"{error_message}: PLC state is {plc_state['state']}, expected IDLE or EMERGENCY"

    # If emergency is active, verify safe shutdown
    if plc_state['emergency_active']:
        is_safe = await hardware_simulator.is_in_safe_state()
        assert is_safe, f"{error_message}: PLC not in safe state during emergency"


async def assert_valve_conflict_prevented(
    valve_operations: List[Dict[str, Any]],
    valve_id: int,
    error_message: str
):
    """Assert that valve conflicts are prevented."""
    concurrent_operations = []

    for op in valve_operations:
        if op['valve_id'] == valve_id and op['status'] in ['ACTIVE', 'RUNNING']:
            concurrent_operations.append(op)

    assert len(concurrent_operations) <= 1, \
        f"{error_message}: Multiple operations detected on valve {valve_id}: {concurrent_operations}"


async def assert_timing_precision(
    scheduled_time: float,
    actual_time: float,
    precision_ms: int,
    error_message: str
):
    """Assert that timing precision requirements are met."""
    timing_error = abs(actual_time - scheduled_time)
    max_error = precision_ms / 1000.0

    assert timing_error <= max_error, \
        f"{error_message}: Timing error {timing_error:.3f}s exceeds ±{precision_ms}ms limit"


async def assert_exclusive_plc_access(
    plc_connections: List[Dict[str, Any]],
    expected_terminal: str,
    error_message: str
):
    """Assert that only one terminal has PLC access."""
    assert len(plc_connections) == 1, \
        f"{error_message}: Expected 1 PLC connection, found {len(plc_connections)}"

    assert plc_connections[0]['terminal_id'] == expected_terminal, \
        f"{error_message}: Expected {expected_terminal} to have PLC access, found {plc_connections[0]['terminal_id']}"


async def assert_emergency_propagation_time(
    response_times: Dict[str, float],
    max_propagation_ms: int,
    error_message: str
):
    """Assert that emergency signals propagate within time limit."""
    max_time = max_propagation_ms / 1000.0

    for terminal_id, response_time in response_times.items():
        assert response_time <= max_time, \
            f"{error_message}: Emergency propagation to {terminal_id} took {response_time:.3f}s, exceeds {max_propagation_ms}ms limit"


async def assert_graceful_degradation(
    failed_terminal: str,
    remaining_terminals: List[Dict[str, Any]],
    expected_states: Dict[str, str],
    error_message: str
):
    """Assert that system degrades gracefully when terminal fails."""
    for terminal_status in remaining_terminals:
        terminal_id = terminal_status['terminal_id']
        current_state = terminal_status['state']
        expected_state = expected_states.get(terminal_id, 'UNKNOWN')

        assert current_state == expected_state, \
            f"{error_message}: Terminal {terminal_id} in state {current_state}, expected {expected_state} after {failed_terminal} failure"


async def assert_parameter_freeze_safety(
    parameter_values_before: Dict[str, float],
    parameter_values_after: Dict[str, float],
    tolerance: float,
    error_message: str
):
    """Assert that parameters remain frozen at safe values during failure."""
    for param_id, value_before in parameter_values_before.items():
        if param_id not in parameter_values_after:
            raise AssertionError(f"{error_message}: Parameter {param_id} missing after failure")

        value_after = parameter_values_after[param_id]
        difference = abs(value_after - value_before)

        assert difference <= tolerance, \
            f"{error_message}: Parameter {param_id} changed from {value_before} to {value_after} (diff: {difference}), exceeds tolerance {tolerance}"


async def assert_no_race_conditions(
    operation_log: List[Dict[str, Any]],
    critical_resource: str,
    error_message: str
):
    """Assert that no race conditions occurred on critical resources."""
    # Group operations by resource and check for overlaps
    resource_operations = []

    for operation in operation_log:
        if operation.get('resource') == critical_resource:
            resource_operations.append(operation)

    # Sort by start time
    resource_operations.sort(key=lambda x: x['start_time'])

    # Check for overlapping operations
    for i in range(len(resource_operations) - 1):
        current_op = resource_operations[i]
        next_op = resource_operations[i + 1]

        current_end = current_op['start_time'] + current_op.get('duration', 0)
        next_start = next_op['start_time']

        # Check for overlap (with small tolerance for timing precision)
        if current_end > next_start + 0.001:  # 1ms tolerance
            assert False, \
                f"{error_message}: Race condition detected on {critical_resource}: {current_op['operation_id']} overlaps with {next_op['operation_id']}"


async def assert_command_priority_ordering(
    processed_commands: List[Dict[str, Any]],
    priority_order: List[str],
    error_message: str
):
    """Assert that commands were processed in correct priority order."""
    # Group commands by priority
    priority_groups = {}
    for priority in priority_order:
        priority_groups[priority] = []

    for command in processed_commands:
        priority = command.get('priority', 'normal')
        if priority in priority_groups:
            priority_groups[priority].append(command)

    # Verify priority ordering
    last_process_time = 0
    for priority in priority_order:
        commands_at_priority = priority_groups[priority]

        for command in commands_at_priority:
            process_time = command.get('process_time', 0)

            # Ensure this priority level started after previous priority completed
            assert process_time >= last_process_time, \
                f"{error_message}: Priority {priority} command {command['command_id']} processed out of order"

        # Update last process time for this priority level
        if commands_at_priority:
            last_process_time = max(cmd.get('process_time', 0) for cmd in commands_at_priority)


async def assert_database_consistency(
    database_records: List[Dict[str, Any]],
    consistency_rules: Dict[str, Any],
    error_message: str
):
    """Assert that database state remains consistent during operations."""
    # Check referential integrity
    if 'foreign_keys' in consistency_rules:
        for fk_rule in consistency_rules['foreign_keys']:
            parent_table = fk_rule['parent_table']
            child_table = fk_rule['child_table']
            parent_key = fk_rule['parent_key']
            foreign_key = fk_rule['foreign_key']

            # Get parent IDs
            parent_records = [r for r in database_records if r['table'] == parent_table]
            parent_ids = {r[parent_key] for r in parent_records}

            # Check child records
            child_records = [r for r in database_records if r['table'] == child_table]
            for child_record in child_records:
                if child_record.get(foreign_key) is not None:
                    assert child_record[foreign_key] in parent_ids, \
                        f"{error_message}: Foreign key violation: {child_table}.{foreign_key}={child_record[foreign_key]} not found in {parent_table}.{parent_key}"

    # Check unique constraints
    if 'unique_constraints' in consistency_rules:
        for unique_rule in consistency_rules['unique_constraints']:
            table = unique_rule['table']
            unique_fields = unique_rule['fields']

            table_records = [r for r in database_records if r['table'] == table]
            unique_combinations = set()

            for record in table_records:
                combination = tuple(record.get(field) for field in unique_fields)
                assert combination not in unique_combinations, \
                    f"{error_message}: Unique constraint violation in {table} for fields {unique_fields}: {combination}"
                unique_combinations.add(combination)


async def assert_audit_trail_completeness(
    audit_records: List[Dict[str, Any]],
    critical_operations: List[str],
    error_message: str
):
    """Assert that all critical operations are logged in audit trail."""
    logged_operations = {record['operation'] for record in audit_records}

    missing_operations = []
    for operation in critical_operations:
        if operation not in logged_operations:
            missing_operations.append(operation)

    assert len(missing_operations) == 0, \
        f"{error_message}: Critical operations not logged: {missing_operations}"


async def assert_security_boundaries(
    access_attempts: List[Dict[str, Any]],
    authorized_terminals: Dict[str, List[str]],
    error_message: str
):
    """Assert that security boundaries are maintained."""
    unauthorized_access = []

    for attempt in access_attempts:
        terminal_id = attempt['terminal_id']
        resource = attempt['resource']
        operation = attempt['operation']

        # Check if terminal is authorized for this resource
        if resource not in authorized_terminals:
            continue  # Skip if resource not in authorization rules

        authorized_for_resource = authorized_terminals[resource]

        if terminal_id not in authorized_for_resource:
            if attempt.get('blocked', False):
                # Good - unauthorized access was blocked
                continue
            else:
                # Bad - unauthorized access was allowed
                unauthorized_access.append({
                    'terminal': terminal_id,
                    'resource': resource,
                    'operation': operation
                })

    assert len(unauthorized_access) == 0, \
        f"{error_message}: Unauthorized access detected: {unauthorized_access}"


class SafetyValidator:
    """High-level safety validation utilities."""

    def __init__(self):
        self.validation_results = []

    async def validate_emergency_response(
        self,
        terminal_cluster,
        hardware_simulator,
        max_response_time_ms: int = 500
    ) -> Dict[str, Any]:
        """Comprehensive emergency response validation."""
        terminal_1, terminal_2, terminal_3 = terminal_cluster

        # Trigger emergency
        start_time = asyncio.get_event_loop().time()
        await terminal_2.trigger_emergency_shutdown("SAFETY_VALIDATION_TEST")

        # Monitor response
        response_times = {}
        terminals = [
            ('terminal_1', terminal_1),
            ('terminal_2', terminal_2),
            ('terminal_3', terminal_3)
        ]

        for terminal_id, terminal in terminals:
            while True:
                if await terminal.is_in_emergency_state():
                    response_times[terminal_id] = asyncio.get_event_loop().time() - start_time
                    break

                if asyncio.get_event_loop().time() - start_time > 2.0:  # 2s timeout
                    response_times[terminal_id] = float('inf')
                    break

                await asyncio.sleep(0.001)

        # Validate response times
        validation_result = {
            'test': 'emergency_response',
            'passed': True,
            'response_times': response_times,
            'max_allowed_ms': max_response_time_ms,
            'violations': []
        }

        max_allowed_s = max_response_time_ms / 1000.0
        for terminal_id, response_time in response_times.items():
            if response_time > max_allowed_s:
                validation_result['passed'] = False
                validation_result['violations'].append({
                    'terminal': terminal_id,
                    'response_time_ms': response_time * 1000,
                    'violation': f"Exceeded {max_response_time_ms}ms limit"
                })

        # Validate hardware safety
        is_safe = await hardware_simulator.is_in_safe_state()
        if not is_safe:
            validation_result['passed'] = False
            validation_result['violations'].append({
                'component': 'hardware',
                'violation': 'Hardware not in safe state after emergency'
            })

        self.validation_results.append(validation_result)
        return validation_result

    async def validate_valve_serialization(
        self,
        terminal_cluster,
        hardware_simulator,
        test_valve_id: int = 1
    ) -> Dict[str, Any]:
        """Comprehensive valve serialization validation."""
        terminal_1, terminal_2, terminal_3 = terminal_cluster

        validation_result = {
            'test': 'valve_serialization',
            'passed': True,
            'conflicts_prevented': 0,
            'violations': []
        }

        # Test concurrent access prevention
        for i in range(5):  # Run multiple conflict tests
            # Terminal 2 requests valve
            request_2 = await terminal_2.request_valve_operation(
                valve_id=test_valve_id,
                operation=f"recipe_step_{i}",
                duration_ms=1000,
                priority="normal"
            )

            # Immediately try Terminal 3
            request_3 = await terminal_3.request_valve_operation(
                valve_id=test_valve_id,
                operation=f"parameter_change_{i}",
                duration_ms=500,
                priority="normal"
            )

            # Validate conflict prevention
            if request_2['status'] == 'GRANTED' and request_3['status'] == 'BLOCKED':
                validation_result['conflicts_prevented'] += 1
            elif request_2['status'] == 'BLOCKED' and request_3['status'] == 'GRANTED':
                validation_result['conflicts_prevented'] += 1
            else:
                validation_result['passed'] = False
                validation_result['violations'].append({
                    'test_iteration': i,
                    'terminal_2_status': request_2['status'],
                    'terminal_3_status': request_3['status'],
                    'violation': 'Concurrent access not prevented'
                })

            # Wait for operations to complete
            await asyncio.sleep(1.2)

        self.validation_results.append(validation_result)
        return validation_result

    async def get_overall_safety_status(self) -> Dict[str, Any]:
        """Get overall safety validation status."""
        total_tests = len(self.validation_results)
        passed_tests = sum(1 for result in self.validation_results if result['passed'])

        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'overall_status': 'SAFE' if passed_tests == total_tests else 'UNSAFE',
            'detailed_results': self.validation_results
        }


@pytest.fixture
def safety_validator():
    """Provide safety validator utility."""
    return SafetyValidator()