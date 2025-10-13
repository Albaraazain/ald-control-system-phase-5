"""
Database-related test fixtures for Supabase/database testing.

Provides fixtures for:
- Clean test database
- Test machine/operator records
- Database state verification helpers
- Table cleanup utilities
- Supabase connection health checks
"""

import pytest
import pytest_asyncio
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


@pytest_asyncio.fixture(scope="function")
async def clean_test_database():
    """
    Provide clean test database for each test.

    Cleans relevant test tables before and after test execution.

    Returns:
        Supabase client for test operations

    Example:
        async def test_database_insert(clean_test_database):
            db = clean_test_database
            # Test will have clean database state
    """
    from db import get_supabase

    # Ensure test mode
    os.environ['TEST_MODE'] = 'true'
    test_machine_id = os.environ.get('TEST_MACHINE_ID', 'test-machine')

    db = get_supabase()

    # Cleanup before test
    await _cleanup_test_data(db, test_machine_id)

    yield db

    # Cleanup after test
    await _cleanup_test_data(db, test_machine_id)


async def _cleanup_test_data(db, machine_id: str):
    """Clean up all test data for given machine ID."""
    tables = [
        'parameter_value_history',
        'recipe_commands',
        'parameter_control_commands',
        'process_executions',
        'process_execution_state',
    ]

    for table in tables:
        try:
            await db.table(table).delete().eq('machine_id', machine_id).execute()
        except Exception:
            pass  # Table might not exist or be empty


@pytest_asyncio.fixture
async def test_machine(clean_test_database):
    """
    Create test machine record in database.

    Returns:
        dict: Machine record with id, name, etc.

    Example:
        async def test_with_machine(test_machine):
            assert test_machine['id'] is not None
    """
    db = clean_test_database
    machine_id = os.environ.get('TEST_MACHINE_ID', 'test-machine')

    machine_data = {
        'id': machine_id,
        'name': 'Test ALD Machine',
        'location': 'Test Lab',
        'status': 'idle',
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    try:
        result = await db.table('machines').upsert(machine_data).execute()
        return result.data[0] if result.data else machine_data
    except Exception:
        return machine_data


@pytest_asyncio.fixture
async def test_operator(clean_test_database):
    """
    Create test operator/session record.

    Returns:
        dict: Operator session record

    Example:
        async def test_with_operator(test_operator):
            assert test_operator['operator_id'] is not None
    """
    operator_data = {
        'operator_id': 'test-operator',
        'name': 'Test Operator',
        'email': 'test@example.com',
        'session_start': datetime.now(timezone.utc).isoformat()
    }

    return operator_data


@pytest.fixture
def database_validator():
    """
    Utility fixture for validating database state.

    Returns:
        DatabaseValidator: Helper class for database assertions

    Example:
        async def test_db_write(clean_test_database, database_validator):
            # Insert data
            await database_validator.assert_record_exists(
                db, 'recipes', 'id', recipe_id
            )
    """
    class DatabaseValidator:
        @staticmethod
        async def assert_record_exists(
            db,
            table: str,
            column: str,
            value: Any
        ):
            """Assert record exists in table."""
            result = await db.table(table).select('*').eq(column, value).execute()
            assert len(result.data) > 0, \
                f"No record found in {table} where {column}={value}"

        @staticmethod
        async def assert_record_count(
            db,
            table: str,
            expected_count: int,
            filter_column: Optional[str] = None,
            filter_value: Optional[Any] = None
        ):
            """Assert table has expected number of records."""
            query = db.table(table).select('*', count='exact')

            if filter_column and filter_value is not None:
                query = query.eq(filter_column, filter_value)

            result = await query.execute()
            actual_count = result.count if hasattr(result, 'count') else len(result.data)

            assert actual_count == expected_count, \
                f"Expected {expected_count} records in {table}, found {actual_count}"

        @staticmethod
        async def assert_field_value(
            db,
            table: str,
            record_id: str,
            field: str,
            expected_value: Any
        ):
            """Assert specific field has expected value."""
            result = await db.table(table).select(field).eq('id', record_id).execute()
            assert len(result.data) > 0, f"Record {record_id} not found in {table}"

            actual_value = result.data[0].get(field)
            assert actual_value == expected_value, \
                f"Field {field}: expected {expected_value}, got {actual_value}"

    return DatabaseValidator()


@pytest.fixture
def database_cleanup_utility():
    """
    Utility for cleaning specific tables or records.

    Returns:
        DatabaseCleanup: Cleanup helper functions

    Example:
        async def test_cleanup(clean_test_database, database_cleanup_utility):
            await database_cleanup_utility.cleanup_table(db, 'recipes')
    """
    class DatabaseCleanup:
        @staticmethod
        async def cleanup_table(
            db,
            table: str,
            condition_column: Optional[str] = None,
            condition_value: Optional[Any] = None
        ):
            """Clean all records from table, optionally with condition."""
            query = db.table(table).delete()

            if condition_column and condition_value is not None:
                query = query.eq(condition_column, condition_value)

            await query.execute()

        @staticmethod
        async def cleanup_old_records(
            db,
            table: str,
            timestamp_column: str,
            older_than_hours: int = 24
        ):
            """Delete records older than specified hours."""
            cutoff = datetime.now(timezone.utc).timestamp() - (older_than_hours * 3600)
            cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()

            await db.table(table).delete().lt(timestamp_column, cutoff_iso).execute()

        @staticmethod
        async def cleanup_by_ids(
            db,
            table: str,
            ids: List[str]
        ):
            """Delete specific records by ID list."""
            for record_id in ids:
                await db.table(table).delete().eq('id', record_id).execute()

    return DatabaseCleanup()


@pytest.fixture
def database_connection_monitor():
    """
    Monitor database connection health and performance.

    Returns:
        DatabaseConnectionMonitor: Connection monitoring utilities

    Example:
        async def test_db_performance(clean_test_database, database_connection_monitor):
            async with database_connection_monitor.track_queries() as tracker:
                # Perform database operations
                await db.table('recipes').select('*').execute()

            tracker.assert_query_time(max_ms=500)
    """
    class DatabaseConnectionMonitor:
        def __init__(self):
            self.query_times = []
            self.query_count = 0
            self.error_count = 0

        class QueryTracker:
            def __init__(self, monitor):
                self.monitor = monitor
                self.start_time = None

            async def __aenter__(self):
                import time
                self.start_time = time.perf_counter()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                import time
                if self.start_time:
                    duration_ms = (time.perf_counter() - self.start_time) * 1000
                    self.monitor.query_times.append(duration_ms)
                    self.monitor.query_count += 1

                if exc_type:
                    self.monitor.error_count += 1

            def assert_query_time(self, max_ms: float):
                """Assert last query completed within time limit."""
                if not self.monitor.query_times:
                    return

                last_time = self.monitor.query_times[-1]
                assert last_time <= max_ms, \
                    f"Query took {last_time:.2f}ms, expected <= {max_ms}ms"

        def track_queries(self):
            """Context manager to track query performance."""
            return self.QueryTracker(self)

    return DatabaseConnectionMonitor()
