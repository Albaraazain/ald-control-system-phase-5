"""
Test assertion utilities for multi-terminal ALD control system testing.

This module provides specialized assertion functions with detailed error messages,
context information, and support for both sync and async testing patterns.

Usage:
    from tests.utils.assertions import (
        assert_terminal_healthy,
        assert_plc_connection,
        assert_database_state,
        assert_recipe_completed
    )

    # In tests
    await assert_terminal_healthy(terminal_id=1, pid=12345)
    await assert_plc_connection(plc_manager)
    await assert_recipe_completed(recipe_id=1, db=test_db, timeout=60)
"""

import os
import fcntl
import time
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class AssertionError(Exception):
    """Custom assertion error with rich context."""
    pass


# ==============================================================================
# Terminal Health Assertions
# ==============================================================================

def assert_terminal_healthy(
    terminal_id: int,
    pid: Optional[int] = None,
    check_lock: bool = True,
    check_process: bool = True
) -> None:
    """
    Assert that a terminal process is healthy and running.

    Checks:
    - Process is running (if PID provided)
    - fcntl lock file exists and is held

    Args:
        terminal_id: Terminal number (1, 2, or 3)
        pid: Process ID to check (optional)
        check_lock: Whether to verify fcntl lock exists
        check_process: Whether to verify process is running

    Raises:
        AssertionError: If terminal is not healthy with detailed reason

    Example:
        assert_terminal_healthy(terminal_id=1, pid=12345)
    """
    context = {
        "terminal_id": terminal_id,
        "pid": pid,
        "timestamp": datetime.now().isoformat(),
        "checks_performed": []
    }

    # Check process is running
    if check_process and pid is not None:
        context["checks_performed"].append("process_running")
        try:
            os.kill(pid, 0)  # Signal 0 checks if process exists
        except OSError:
            raise AssertionError(
                f"Terminal {terminal_id} process not running\n"
                f"Expected: Process PID {pid} to be alive\n"
                f"Actual: Process not found or no permission\n"
                f"Context: {context}"
            )

    # Check fcntl lock
    if check_lock:
        context["checks_performed"].append("fcntl_lock")
        lock_file = f"/tmp/terminal{terminal_id}_service.lock"

        if not os.path.exists(lock_file):
            raise AssertionError(
                f"Terminal {terminal_id} lock file missing\n"
                f"Expected: Lock file at {lock_file}\n"
                f"Actual: File does not exist\n"
                f"Context: {context}"
            )

        # Try to acquire lock (should fail if terminal holds it)
        try:
            with open(lock_file, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                # If we got the lock, terminal doesn't hold it
                raise AssertionError(
                    f"Terminal {terminal_id} lock not held\n"
                    f"Expected: Terminal to hold exclusive lock on {lock_file}\n"
                    f"Actual: Lock was available (terminal not holding it)\n"
                    f"Context: {context}"
                )
        except IOError:
            # Lock is held (expected)
            pass


# ==============================================================================
# PLC Connection Assertions
# ==============================================================================

async def assert_plc_connection(
    plc_manager,
    expected_connected: bool = True
) -> None:
    """
    Assert PLC connection state.

    Args:
        plc_manager: PLCManager instance
        expected_connected: Expected connection state

    Raises:
        AssertionError: If connection state doesn't match expected

    Example:
        await assert_plc_connection(plc_manager, expected_connected=True)
    """
    actual_connected = plc_manager.is_connected if hasattr(plc_manager, 'is_connected') else plc_manager.connected

    context = {
        "plc_type": plc_manager.__class__.__name__,
        "timestamp": datetime.now().isoformat(),
        "expected_connected": expected_connected,
        "actual_connected": actual_connected
    }

    if actual_connected != expected_connected:
        raise AssertionError(
            f"PLC connection state mismatch\n"
            f"Expected: connected={expected_connected}\n"
            f"Actual: connected={actual_connected}\n"
            f"Context: {context}"
        )


# ==============================================================================
# Database State Assertions
# ==============================================================================

async def assert_database_state(
    db,
    table: str,
    condition: str,
    expected_count: Optional[int] = None,
    min_count: Optional[int] = None,
    max_count: Optional[int] = None,
    expected_exists: Optional[bool] = None
) -> None:
    """
    Assert database state matches expectations.

    Args:
        db: Database connection
        table: Table name
        condition: WHERE clause condition
        expected_count: Exact expected row count
        min_count: Minimum expected row count
        max_count: Maximum expected row count
        expected_exists: Whether rows should exist (True) or not (False)

    Raises:
        AssertionError: If database state doesn't match expected

    Example:
        await assert_database_state(
            db,
            table="parameter_value_history",
            condition="parameter_id = 1 AND timestamp > NOW() - INTERVAL '1 minute'",
            min_count=1
        )
    """
    query = f"SELECT COUNT(*) as count FROM {table} WHERE {condition}"

    try:
        result = await db.execute_query(query)
        actual_count = result[0]['count'] if result else 0
    except Exception as e:
        raise AssertionError(
            f"Database query failed\n"
            f"Query: {query}\n"
            f"Error: {str(e)}\n"
            f"Timestamp: {datetime.now().isoformat()}"
        )

    context = {
        "table": table,
        "condition": condition,
        "actual_count": actual_count,
        "timestamp": datetime.now().isoformat()
    }

    # Check expected_count
    if expected_count is not None:
        context["expected_count"] = expected_count
        if actual_count != expected_count:
            raise AssertionError(
                f"Database record count mismatch\n"
                f"Table: {table}\n"
                f"Condition: {condition}\n"
                f"Expected: {expected_count} records\n"
                f"Actual: {actual_count} records\n"
                f"Context: {context}"
            )

    # Check min_count
    if min_count is not None:
        context["min_count"] = min_count
        if actual_count < min_count:
            raise AssertionError(
                f"Database record count below minimum\n"
                f"Table: {table}\n"
                f"Condition: {condition}\n"
                f"Expected: At least {min_count} records\n"
                f"Actual: {actual_count} records\n"
                f"Context: {context}"
            )

    # Check max_count
    if max_count is not None:
        context["max_count"] = max_count
        if actual_count > max_count:
            raise AssertionError(
                f"Database record count exceeds maximum\n"
                f"Table: {table}\n"
                f"Condition: {condition}\n"
                f"Expected: At most {max_count} records\n"
                f"Actual: {actual_count} records\n"
                f"Context: {context}"
            )

    # Check expected_exists
    if expected_exists is not None:
        context["expected_exists"] = expected_exists
        if expected_exists and actual_count == 0:
            raise AssertionError(
                f"Database records not found\n"
                f"Table: {table}\n"
                f"Condition: {condition}\n"
                f"Expected: Records to exist\n"
                f"Actual: No records found\n"
                f"Context: {context}"
            )
        elif not expected_exists and actual_count > 0:
            raise AssertionError(
                f"Unexpected database records found\n"
                f"Table: {table}\n"
                f"Condition: {condition}\n"
                f"Expected: No records\n"
                f"Actual: {actual_count} records found\n"
                f"Context: {context}"
            )


# ==============================================================================
# Timing Violation Assertions
# ==============================================================================

async def assert_no_timing_violations(
    log_file: str,
    terminal_id: int,
    max_violations: int = 0,
    time_window_seconds: Optional[int] = None
) -> None:
    """
    Assert no timing violations in Terminal 1 logs.

    Args:
        log_file: Path to log file
        terminal_id: Terminal ID for context
        max_violations: Maximum allowed violations (default 0)
        time_window_seconds: Only check recent N seconds (optional)

    Raises:
        AssertionError: If timing violations exceed threshold

    Example:
        await assert_no_timing_violations(
            log_file="logs/plc.log",
            terminal_id=1,
            max_violations=0
        )
    """
    if not os.path.exists(log_file):
        raise AssertionError(
            f"Log file not found\n"
            f"Expected: Log file at {log_file}\n"
            f"Actual: File does not exist\n"
            f"Terminal: {terminal_id}"
        )

    violations = []
    cutoff_time = None

    if time_window_seconds:
        cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)

    with open(log_file, 'r') as f:
        for line in f:
            if 'timing violation' in line.lower() or 'timing precision' in line.lower():
                # Try to extract timestamp
                if cutoff_time:
                    # Simple timestamp parsing (adjust format as needed)
                    # Example: "2025-10-10 19:00:00,123"
                    try:
                        timestamp_str = line.split()[0] + ' ' + line.split()[1]
                        log_time = datetime.fromisoformat(timestamp_str.replace(',', '.'))
                        if log_time < cutoff_time:
                            continue
                    except:
                        pass  # If parsing fails, include the violation

                violations.append(line.strip())

    actual_violations = len(violations)

    if actual_violations > max_violations:
        violation_sample = '\n  '.join(violations[:10])  # Show first 10
        raise AssertionError(
            f"Timing violations exceed threshold\n"
            f"Terminal: {terminal_id}\n"
            f"Log file: {log_file}\n"
            f"Expected: At most {max_violations} violations\n"
            f"Actual: {actual_violations} violations\n"
            f"Time window: {time_window_seconds}s\n"
            f"Sample violations:\n  {violation_sample}\n"
            f"Timestamp: {datetime.now().isoformat()}"
        )


# ==============================================================================
# Recipe Execution Assertions
# ==============================================================================

async def assert_recipe_completed(
    recipe_id: int,
    db,
    timeout: int = 300,
    expected_status: str = "completed"
) -> None:
    """
    Assert recipe execution completed successfully.

    Args:
        recipe_id: Recipe ID to check
        db: Database connection
        timeout: Maximum wait time in seconds
        expected_status: Expected final status

    Raises:
        AssertionError: If recipe doesn't complete or has wrong status

    Example:
        await assert_recipe_completed(recipe_id=1, db=test_db, timeout=60)
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        query = """
            SELECT status, error_message, completed_at
            FROM process_executions
            WHERE recipe_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            result = await db.execute_query(query, recipe_id)
        except Exception as e:
            raise AssertionError(
                f"Database query failed while checking recipe status\n"
                f"Recipe ID: {recipe_id}\n"
                f"Error: {str(e)}\n"
                f"Timestamp: {datetime.now().isoformat()}"
            )

        if not result:
            # No execution record yet
            await asyncio.sleep(1)
            continue

        status = result[0]['status']
        error_message = result[0].get('error_message')
        completed_at = result[0].get('completed_at')

        if status == expected_status:
            return  # Success!

        if status in ['failed', 'cancelled', 'error']:
            raise AssertionError(
                f"Recipe execution failed\n"
                f"Recipe ID: {recipe_id}\n"
                f"Expected status: {expected_status}\n"
                f"Actual status: {status}\n"
                f"Error message: {error_message}\n"
                f"Completed at: {completed_at}\n"
                f"Timestamp: {datetime.now().isoformat()}"
            )

        # Still running, wait and retry
        await asyncio.sleep(2)

    # Timeout
    raise AssertionError(
        f"Recipe execution timeout\n"
        f"Recipe ID: {recipe_id}\n"
        f"Expected: Recipe to complete within {timeout}s\n"
        f"Actual: Recipe still running or status not reached\n"
        f"Last status: {status if result else 'No record'}\n"
        f"Timestamp: {datetime.now().isoformat()}"
    )


# ==============================================================================
# Parameter Value Assertions
# ==============================================================================

async def assert_parameter_value(
    parameter_id: int,
    expected_value: float,
    db,
    plc_manager=None,
    tolerance: float = 0.01,
    check_database: bool = True,
    check_plc: bool = True,
    max_age_seconds: int = 5
) -> None:
    """
    Assert parameter value matches expected in both database and PLC.

    Args:
        parameter_id: Parameter ID
        expected_value: Expected parameter value
        db: Database connection
        plc_manager: PLC manager instance (optional)
        tolerance: Acceptable difference from expected value
        check_database: Whether to check database
        check_plc: Whether to check PLC
        max_age_seconds: Maximum age of database record

    Raises:
        AssertionError: If parameter value doesn't match

    Example:
        await assert_parameter_value(
            parameter_id=1,
            expected_value=100.0,
            db=test_db,
            plc_manager=plc,
            tolerance=0.1
        )
    """
    context = {
        "parameter_id": parameter_id,
        "expected_value": expected_value,
        "tolerance": tolerance,
        "timestamp": datetime.now().isoformat()
    }

    # Check database
    if check_database:
        query = """
            SELECT value, timestamp
            FROM parameter_value_history
            WHERE parameter_id = $1
            ORDER BY timestamp DESC
            LIMIT 1
        """

        result = await db.execute_query(query, parameter_id)

        if not result:
            raise AssertionError(
                f"Parameter value not found in database\n"
                f"Parameter ID: {parameter_id}\n"
                f"Expected: Recent record in parameter_value_history\n"
                f"Actual: No records found\n"
                f"Context: {context}"
            )

        db_value = float(result[0]['value'])
        db_timestamp = result[0]['timestamp']

        # Check age
        record_age = (datetime.now() - db_timestamp).total_seconds()
        if record_age > max_age_seconds:
            raise AssertionError(
                f"Parameter database record too old\n"
                f"Parameter ID: {parameter_id}\n"
                f"Expected: Record within {max_age_seconds}s\n"
                f"Actual: Record age {record_age:.1f}s\n"
                f"DB value: {db_value}\n"
                f"Timestamp: {db_timestamp}\n"
                f"Context: {context}"
            )

        # Check value
        if abs(db_value - expected_value) > tolerance:
            context["db_value"] = db_value
            context["db_timestamp"] = db_timestamp.isoformat()
            raise AssertionError(
                f"Parameter database value mismatch\n"
                f"Parameter ID: {parameter_id}\n"
                f"Expected: {expected_value} ± {tolerance}\n"
                f"Actual: {db_value}\n"
                f"Difference: {abs(db_value - expected_value):.4f}\n"
                f"Context: {context}"
            )

    # Check PLC
    if check_plc and plc_manager:
        try:
            plc_value = await plc_manager.read_parameter(parameter_id)
        except Exception as e:
            raise AssertionError(
                f"Failed to read parameter from PLC\n"
                f"Parameter ID: {parameter_id}\n"
                f"Error: {str(e)}\n"
                f"Context: {context}"
            )

        if abs(plc_value - expected_value) > tolerance:
            context["plc_value"] = plc_value
            raise AssertionError(
                f"Parameter PLC value mismatch\n"
                f"Parameter ID: {parameter_id}\n"
                f"Expected: {expected_value} ± {tolerance}\n"
                f"Actual: {plc_value}\n"
                f"Difference: {abs(plc_value - expected_value):.4f}\n"
                f"Context: {context}"
            )


# ==============================================================================
# Data Loss Assertions
# ==============================================================================

async def assert_no_data_loss(
    db,
    terminal_id: int,
    start_time: datetime,
    end_time: datetime,
    expected_frequency_hz: float = 1.0,
    tolerance_percent: float = 5.0
) -> None:
    """
    Assert no data loss in Terminal 1 data collection.

    Checks that data collection maintained expected frequency without gaps.

    Args:
        db: Database connection
        terminal_id: Terminal ID for context
        start_time: Start of time window
        end_time: End of time window
        expected_frequency_hz: Expected collection frequency (default 1 Hz)
        tolerance_percent: Acceptable data loss percentage

    Raises:
        AssertionError: If data loss exceeds tolerance

    Example:
        await assert_no_data_loss(
            db=test_db,
            terminal_id=1,
            start_time=test_start,
            end_time=test_end,
            expected_frequency_hz=1.0,
            tolerance_percent=5.0
        )
    """
    duration_seconds = (end_time - start_time).total_seconds()
    expected_count = int(duration_seconds * expected_frequency_hz)

    query = """
        SELECT COUNT(*) as count
        FROM parameter_value_history
        WHERE timestamp BETWEEN $1 AND $2
    """

    result = await db.execute_query(query, start_time, end_time)
    actual_count = result[0]['count'] if result else 0

    data_loss_percent = ((expected_count - actual_count) / expected_count * 100) if expected_count > 0 else 0

    context = {
        "terminal_id": terminal_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration_seconds,
        "expected_frequency_hz": expected_frequency_hz,
        "expected_count": expected_count,
        "actual_count": actual_count,
        "data_loss_percent": data_loss_percent,
        "tolerance_percent": tolerance_percent,
        "timestamp": datetime.now().isoformat()
    }

    if data_loss_percent > tolerance_percent:
        raise AssertionError(
            f"Data loss exceeds tolerance\n"
            f"Terminal: {terminal_id}\n"
            f"Time window: {start_time.isoformat()} to {end_time.isoformat()}\n"
            f"Duration: {duration_seconds:.1f}s\n"
            f"Expected: {expected_count} records (at {expected_frequency_hz} Hz)\n"
            f"Actual: {actual_count} records\n"
            f"Data loss: {data_loss_percent:.2f}%\n"
            f"Tolerance: {tolerance_percent}%\n"
            f"Context: {context}"
        )


# ==============================================================================
# Sync Wrappers for Non-Async Tests
# ==============================================================================

def assert_plc_connection_sync(plc_manager, expected_connected: bool = True) -> None:
    """Synchronous wrapper for assert_plc_connection."""
    asyncio.run(assert_plc_connection(plc_manager, expected_connected))


def assert_database_state_sync(db, table: str, condition: str, **kwargs) -> None:
    """Synchronous wrapper for assert_database_state."""
    asyncio.run(assert_database_state(db, table, condition, **kwargs))


def assert_recipe_completed_sync(recipe_id: int, db, **kwargs) -> None:
    """Synchronous wrapper for assert_recipe_completed."""
    asyncio.run(assert_recipe_completed(recipe_id, db, **kwargs))


def assert_parameter_value_sync(parameter_id: int, expected_value: float, db, **kwargs) -> None:
    """Synchronous wrapper for assert_parameter_value."""
    asyncio.run(assert_parameter_value(parameter_id, expected_value, db, **kwargs))


def assert_no_data_loss_sync(db, terminal_id: int, start_time: datetime, end_time: datetime, **kwargs) -> None:
    """Synchronous wrapper for assert_no_data_loss."""
    asyncio.run(assert_no_data_loss(db, terminal_id, start_time, end_time, **kwargs))
