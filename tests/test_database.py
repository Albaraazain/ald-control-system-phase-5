"""
Database testing utilities with transaction rollback support.

This module provides database fixtures and utilities specifically designed
for testing database operations with proper isolation and cleanup.
"""
import pytest
import asyncio
import uuid
from typing import Dict, Any, List, Optional, AsyncIterator
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from src.abstractions.interfaces import IDatabaseService, ITransaction
from src.di.container import ServiceContainer

# ============================================================================
# Test Database Transaction Manager
# ============================================================================

class TestTransactionManager:
    """
    Manages database transactions for testing with automatic rollback.

    This class provides a testing-specific transaction manager that ensures
    all database operations during tests are rolled back automatically,
    maintaining test isolation.
    """

    def __init__(self):
        self.active_transactions = {}
        self.rollback_stack = []

    @asynccontextmanager
    async def transaction_scope(self, test_id: str = None) -> AsyncIterator['TestTransaction']:
        """
        Create a transaction scope that automatically rolls back.

        Args:
            test_id: Optional test identifier for tracking
        """
        test_id = test_id or str(uuid.uuid4())
        transaction = TestTransaction(test_id, self)

        self.active_transactions[test_id] = transaction
        self.rollback_stack.append(test_id)

        try:
            await transaction.__aenter__()
            yield transaction
        except Exception as e:
            await transaction.rollback()
            raise
        finally:
            # Always rollback test transactions
            if test_id in self.active_transactions:
                await transaction.rollback()
                del self.active_transactions[test_id]
                if test_id in self.rollback_stack:
                    self.rollback_stack.remove(test_id)

    async def rollback_all(self):
        """Rollback all active transactions."""
        for test_id in list(self.rollback_stack):
            if test_id in self.active_transactions:
                await self.active_transactions[test_id].rollback()

class TestTransaction:
    """
    Test-specific transaction implementation with enhanced tracking.
    """

    def __init__(self, test_id: str, manager: TestTransactionManager):
        self.test_id = test_id
        self.manager = manager
        self.operations = []
        self.is_active = False
        self.rollback_called = False

    async def __aenter__(self):
        self.is_active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.is_active and not self.rollback_called:
            await self.rollback()
        return False

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a query and track it for rollback."""
        self.operations.append(("execute", query, params))
        # Return mock result for testing
        return {"rows_affected": 1, "result": []}

    async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> bool:
        """Execute multiple queries and track them for rollback."""
        self.operations.append(("execute_many", query, params_list))
        return True

    async def commit(self) -> bool:
        """Commit is disabled in test transactions - they always rollback."""
        # In testing, we don't actually commit to maintain isolation
        return True

    async def rollback(self) -> bool:
        """Rollback the transaction and all operations."""
        if self.rollback_called:
            return True

        # In a real implementation, this would rollback actual database operations
        # For testing, we just mark as rolled back and clear operations
        self.rollback_called = True
        self.is_active = False
        self.operations.clear()
        return True

# ============================================================================
# Mock Database Service for Testing
# ============================================================================

class TestDatabaseService:
    """
    Test-specific database service with transaction rollback support.
    """

    def __init__(self):
        self.transaction_manager = TestTransactionManager()
        self.query_log = []
        self.mock_data = {}

    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute query with logging for test verification."""
        self.query_log.append(("execute_query", query, params))
        return []

    async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> bool:
        """Execute multiple queries with logging."""
        self.query_log.append(("execute_many", query, params_list))
        return True

    async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch single row with mock data support."""
        self.query_log.append(("fetch_one", query, params))
        # Return mock data if available
        return self.mock_data.get("fetch_one_result")

    async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all rows with mock data support."""
        self.query_log.append(("fetch_all", query, params))
        # Return mock data if available
        return self.mock_data.get("fetch_all_result", [])

    async def begin_transaction(self) -> TestTransaction:
        """Begin a test transaction that auto-rolls back."""
        test_id = str(uuid.uuid4())
        return TestTransaction(test_id, self.transaction_manager)

    def set_mock_data(self, key: str, data: Any):
        """Set mock data for queries."""
        self.mock_data[key] = data

    def get_query_log(self) -> List[tuple]:
        """Get log of all executed queries for verification."""
        return self.query_log.copy()

    def clear_query_log(self):
        """Clear the query log."""
        self.query_log.clear()

    async def health_check(self):
        """Health check always returns healthy for tests."""
        from src.abstractions.interfaces import ServiceHealth
        return ServiceHealth.HEALTHY

    async def dispose(self):
        """Dispose and rollback all test transactions."""
        await self.transaction_manager.rollback_all()

# ============================================================================
# Test Data Seeding
# ============================================================================

class TestDataSeeder:
    """
    Utility for seeding test data in an isolated manner.
    """

    @staticmethod
    async def seed_test_recipes(db_service: TestDatabaseService, count: int = 3) -> List[Dict[str, Any]]:
        """Seed test recipe data."""
        recipes = []

        for i in range(count):
            recipe = {
                "id": str(uuid.uuid4()),
                "name": f"Test Recipe {i + 1}",
                "description": f"Test recipe description {i + 1}",
                "created_at": "2023-01-01T00:00:00Z"
            }
            recipes.append(recipe)

        # Set mock data for recipe queries
        db_service.set_mock_data("fetch_all_result", recipes)

        return recipes

    @staticmethod
    async def seed_test_parameters(db_service: TestDatabaseService, count: int = 10) -> List[Dict[str, Any]]:
        """Seed test parameter data."""
        parameters = []

        base_parameters = [
            {"id": "temp_reactor", "name": "Reactor Temperature", "unit": "°C", "type": "float"},
            {"id": "pressure_chamber", "name": "Chamber Pressure", "unit": "mbar", "type": "float"},
            {"id": "flow_rate_ar", "name": "Argon Flow Rate", "unit": "sccm", "type": "float"},
            {"id": "valve_1_state", "name": "Valve 1 State", "unit": "bool", "type": "binary"},
            {"id": "valve_2_state", "name": "Valve 2 State", "unit": "bool", "type": "binary"},
        ]

        for i, param in enumerate(base_parameters[:count]):
            param_copy = param.copy()
            param_copy["created_at"] = "2023-01-01T00:00:00Z"
            parameters.append(param_copy)

        # Add additional parameters if needed
        for i in range(len(base_parameters), count):
            parameters.append({
                "id": f"test_param_{i}",
                "name": f"Test Parameter {i}",
                "unit": "unit",
                "type": "float",
                "created_at": "2023-01-01T00:00:00Z"
            })

        db_service.set_mock_data("fetch_all_result", parameters)
        return parameters

    @staticmethod
    async def seed_test_processes(db_service: TestDatabaseService, count: int = 5) -> List[Dict[str, Any]]:
        """Seed test process data."""
        processes = []

        for i in range(count):
            process = {
                "id": str(uuid.uuid4()),
                "recipe_id": str(uuid.uuid4()),
                "status": "completed" if i % 2 == 0 else "running",
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-01-01T01:00:00Z" if i % 2 == 0 else None,
                "created_at": "2023-01-01T00:00:00Z"
            }
            processes.append(process)

        db_service.set_mock_data("fetch_all_result", processes)
        return processes

# ============================================================================
# Database Test Utilities
# ============================================================================

class DatabaseTestUtils:
    """Utilities for database testing scenarios."""

    @staticmethod
    async def assert_query_executed(db_service: TestDatabaseService, expected_query: str):
        """Assert that a specific query was executed."""
        query_log = db_service.get_query_log()
        executed_queries = [entry[1] for entry in query_log if entry[0] == "execute_query"]

        assert expected_query in executed_queries, \
            f"Query '{expected_query}' not found in executed queries: {executed_queries}"

    @staticmethod
    async def assert_transaction_rollback(transaction: TestTransaction):
        """Assert that a transaction was properly rolled back."""
        assert transaction.rollback_called, "Transaction was not rolled back"
        assert not transaction.is_active, "Transaction is still active after rollback"
        assert len(transaction.operations) == 0, "Operations not cleared after rollback"

    @staticmethod
    async def simulate_database_error(db_service: TestDatabaseService, error_message: str = "Database error"):
        """Configure database service to simulate errors."""
        def error_func(*args, **kwargs):
            raise Exception(error_message)

        # Replace methods with error functions
        db_service.execute_query = error_func
        db_service.fetch_one = error_func
        db_service.fetch_all = error_func

    @staticmethod
    async def simulate_slow_database(db_service: TestDatabaseService, delay_seconds: float = 1.0):
        """Configure database service to simulate slow responses."""
        original_execute = db_service.execute_query
        original_fetch_one = db_service.fetch_one
        original_fetch_all = db_service.fetch_all

        async def slow_execute_query(*args, **kwargs):
            await asyncio.sleep(delay_seconds)
            return await original_execute(*args, **kwargs)

        async def slow_fetch_one(*args, **kwargs):
            await asyncio.sleep(delay_seconds)
            return await original_fetch_one(*args, **kwargs)

        async def slow_fetch_all(*args, **kwargs):
            await asyncio.sleep(delay_seconds)
            return await original_fetch_all(*args, **kwargs)

        db_service.execute_query = slow_execute_query
        db_service.fetch_one = slow_fetch_one
        db_service.fetch_all = slow_fetch_all

# ============================================================================
# Pytest Fixtures for Database Testing
# ============================================================================

@pytest.fixture
async def test_db_service() -> TestDatabaseService:
    """Provide a test database service with transaction rollback."""
    db_service = TestDatabaseService()
    try:
        yield db_service
    finally:
        await db_service.dispose()

@pytest.fixture
async def test_db_transaction(test_db_service: TestDatabaseService) -> TestTransaction:
    """Provide a test database transaction that auto-rolls back."""
    async with test_db_service.transaction_manager.transaction_scope() as transaction:
        yield transaction

@pytest.fixture
async def seeded_test_db(test_db_service: TestDatabaseService) -> TestDatabaseService:
    """Provide a test database pre-seeded with test data."""
    # Seed basic test data
    await TestDataSeeder.seed_test_recipes(test_db_service, count=3)
    await TestDataSeeder.seed_test_parameters(test_db_service, count=10)
    await TestDataSeeder.seed_test_processes(test_db_service, count=5)

    return test_db_service

@pytest.fixture
def db_test_utils() -> DatabaseTestUtils:
    """Provide database testing utilities."""
    return DatabaseTestUtils()

@pytest.fixture
def test_data_seeder() -> TestDataSeeder:
    """Provide test data seeding utilities."""
    return TestDataSeeder()

# ============================================================================
# Database Integration Test Base Class
# ============================================================================

class DatabaseTestBase:
    """
    Base class for database integration tests.

    Provides common functionality and setup for database testing scenarios.
    """

    @pytest.fixture(autouse=True)
    async def setup_database_test(self, test_db_service: TestDatabaseService):
        """Auto-setup for database tests."""
        self.db_service = test_db_service
        self.db_utils = DatabaseTestUtils()

    async def assert_data_integrity(self, expected_operations: List[str]):
        """Assert that expected database operations were performed."""
        query_log = self.db_service.get_query_log()
        operation_types = [entry[0] for entry in query_log]

        for expected_op in expected_operations:
            assert expected_op in operation_types, \
                f"Expected operation '{expected_op}' not found in: {operation_types}"

    async def rollback_and_verify_cleanup(self):
        """Rollback all transactions and verify proper cleanup."""
        await self.db_service.transaction_manager.rollback_all()

        # Verify all transactions are cleaned up
        assert len(self.db_service.transaction_manager.active_transactions) == 0, \
            "Active transactions not properly cleaned up"
        assert len(self.db_service.transaction_manager.rollback_stack) == 0, \
            "Rollback stack not properly cleaned up"

# ============================================================================
# Performance Testing for Database Operations
# ============================================================================

class DatabasePerformanceTestUtils:
    """Utilities for testing database operation performance."""

    @staticmethod
    async def benchmark_query_execution(
        db_service: TestDatabaseService,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        iterations: int = 100
    ) -> Dict[str, Any]:
        """Benchmark database query execution performance."""
        import time

        execution_times = []

        for _ in range(iterations):
            start_time = time.perf_counter()
            await db_service.execute_query(query, params)
            end_time = time.perf_counter()

            execution_times.append((end_time - start_time) * 1000)  # Convert to milliseconds

        return {
            "iterations": iterations,
            "avg_time_ms": sum(execution_times) / len(execution_times),
            "min_time_ms": min(execution_times),
            "max_time_ms": max(execution_times),
            "total_time_ms": sum(execution_times)
        }

    @staticmethod
    async def test_concurrent_database_access(
        db_service: TestDatabaseService,
        concurrent_operations: int = 10,
        operations_per_thread: int = 5
    ) -> Dict[str, Any]:
        """Test concurrent database access patterns."""
        async def database_operation():
            operations = []
            for i in range(operations_per_thread):
                start_time = asyncio.get_event_loop().time()
                await db_service.execute_query(f"SELECT * FROM test_table WHERE id = {i}")
                end_time = asyncio.get_event_loop().time()
                operations.append(end_time - start_time)
            return operations

        # Run concurrent operations
        tasks = [database_operation() for _ in range(concurrent_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        all_times = []
        error_count = 0

        for result in results:
            if isinstance(result, Exception):
                error_count += 1
            else:
                all_times.extend(result)

        return {
            "concurrent_operations": concurrent_operations,
            "operations_per_thread": operations_per_thread,
            "total_operations": len(all_times),
            "error_count": error_count,
            "success_rate": (len(all_times) / (concurrent_operations * operations_per_thread)) * 100,
            "avg_response_time_ms": (sum(all_times) / len(all_times)) * 1000 if all_times else 0,
            "max_response_time_ms": max(all_times) * 1000 if all_times else 0
        }

@pytest.fixture
def db_performance_utils() -> DatabasePerformanceTestUtils:
    """Provide database performance testing utilities."""
    return DatabasePerformanceTestUtils()