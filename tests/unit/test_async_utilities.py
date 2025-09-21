"""
Async testing utilities for database transactions, event handling, and concurrent operations.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from contextlib import asynccontextmanager
import time
from dataclasses import dataclass
import uuid

from src.di.container import ServiceContainer
from src.abstractions.interfaces import IDatabaseService, IParameterLogger, IEventBus
from tests.unit.test_container_mocking import MockServiceContainer


@dataclass
class AsyncTestResult:
    """Result of an async test operation"""
    success: bool
    duration_ms: float
    error: Optional[Exception] = None
    data: Optional[Dict[str, Any]] = None


class AsyncTestContext:
    """Context manager for async testing with automatic cleanup"""

    def __init__(self, mock_container: MockServiceContainer = None):
        self.mock_container = mock_container or MockServiceContainer()
        self.async_tasks: List[asyncio.Task] = []
        self.cleanup_callbacks: List[Callable] = []
        self.start_time: float = 0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cancel all running tasks
        for task in self.async_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Run cleanup callbacks
        for cleanup in self.cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(cleanup):
                    await cleanup()
                else:
                    cleanup()
            except Exception:
                pass  # Ignore cleanup errors

    def add_task(self, coro) -> asyncio.Task:
        """Add an async task to be managed by this context"""
        task = asyncio.create_task(coro)
        self.async_tasks.append(task)
        return task

    def add_cleanup(self, callback: Callable):
        """Add a cleanup callback"""
        self.cleanup_callbacks.append(callback)

    def get_duration_ms(self) -> float:
        """Get duration since context creation in milliseconds"""
        return (time.time() - self.start_time) * 1000


class DatabaseTransactionTestUtilities:
    """Utilities for testing database transactions and rollbacks"""

    @staticmethod
    async def simulate_transaction_scenario(
        mock_container: MockServiceContainer,
        success_operations: int = 3,
        failure_at_operation: Optional[int] = None
    ) -> AsyncTestResult:
        """Simulate a transaction scenario with optional failure"""
        db_mock = mock_container.get_mock(IDatabaseService)

        operation_count = 0

        async def mock_execute_transaction(operations: List[Dict]):
            nonlocal operation_count
            for i, op in enumerate(operations):
                operation_count += 1
                if failure_at_operation and i == failure_at_operation:
                    raise Exception(f"Simulated failure at operation {i}")
            return True

        db_mock.execute_transaction.side_effect = mock_execute_transaction

        try:
            # Simulate transaction with multiple operations
            operations = [{"sql": f"INSERT INTO test VALUES ({i})"} for i in range(success_operations)]

            start_time = time.time()
            result = await db_mock.execute_transaction(operations)
            duration_ms = (time.time() - start_time) * 1000

            return AsyncTestResult(
                success=True,
                duration_ms=duration_ms,
                data={"operations_executed": operation_count}
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return AsyncTestResult(
                success=False,
                duration_ms=duration_ms,
                error=e,
                data={"operations_executed": operation_count}
            )

    @staticmethod
    def create_transaction_rollback_scenario(mock_container: MockServiceContainer):
        """Create a scenario that tests transaction rollback functionality"""
        db_mock = mock_container.get_mock(IDatabaseService)

        rollback_called = False
        commit_called = False

        async def mock_begin_transaction():
            return "transaction_id_123"

        async def mock_commit_transaction(transaction_id: str):
            nonlocal commit_called
            commit_called = True
            return True

        async def mock_rollback_transaction(transaction_id: str):
            nonlocal rollback_called
            rollback_called = True
            return True

        db_mock.begin_transaction = AsyncMock(side_effect=mock_begin_transaction)
        db_mock.commit_transaction = AsyncMock(side_effect=mock_commit_transaction)
        db_mock.rollback_transaction = AsyncMock(side_effect=mock_rollback_transaction)

        return {
            'rollback_called': lambda: rollback_called,
            'commit_called': lambda: commit_called
        }


class ConcurrentOperationTestUtilities:
    """Utilities for testing concurrent operations and race conditions"""

    @staticmethod
    async def simulate_concurrent_parameter_logging(
        mock_container: MockServiceContainer,
        concurrent_writers: int = 5,
        operations_per_writer: int = 10
    ) -> List[AsyncTestResult]:
        """Simulate concurrent parameter logging to test race conditions"""
        logger_mock = mock_container.get_mock(IParameterLogger)

        results = []
        write_count = 0

        async def mock_log_parameter(param_id: str, value: float):
            nonlocal write_count
            write_count += 1
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms simulation
            return True

        logger_mock.log_parameter.side_effect = mock_log_parameter

        async def writer_task(writer_id: int) -> AsyncTestResult:
            start_time = time.time()
            try:
                for i in range(operations_per_writer):
                    await logger_mock.log_parameter(f"param_{writer_id}_{i}", float(i))

                duration_ms = (time.time() - start_time) * 1000
                return AsyncTestResult(
                    success=True,
                    duration_ms=duration_ms,
                    data={"writer_id": writer_id, "operations": operations_per_writer}
                )
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                return AsyncTestResult(
                    success=False,
                    duration_ms=duration_ms,
                    error=e,
                    data={"writer_id": writer_id}
                )

        # Run all writers concurrently
        tasks = [asyncio.create_task(writer_task(i)) for i in range(concurrent_writers)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to AsyncTestResult
        formatted_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                formatted_results.append(AsyncTestResult(
                    success=False,
                    duration_ms=0,
                    error=result,
                    data={"writer_id": i}
                ))
            else:
                formatted_results.append(result)

        return formatted_results

    @staticmethod
    async def simulate_race_condition_scenario(
        mock_container: MockServiceContainer,
        shared_resource_operations: int = 10
    ) -> AsyncTestResult:
        """Simulate race condition on shared resource"""
        shared_state = {"counter": 0, "operations": []}

        async def increment_operation(operation_id: str):
            # Simulate read-modify-write race condition
            current_value = shared_state["counter"]
            await asyncio.sleep(0.001)  # Simulate processing delay
            shared_state["counter"] = current_value + 1
            shared_state["operations"].append(operation_id)

        # Run multiple operations concurrently that modify shared state
        tasks = [
            asyncio.create_task(increment_operation(f"op_{i}"))
            for i in range(shared_resource_operations)
        ]

        start_time = time.time()
        await asyncio.gather(*tasks)
        duration_ms = (time.time() - start_time) * 1000

        # Check for race condition - counter should equal operations if no race condition
        race_condition_detected = shared_state["counter"] != shared_resource_operations

        return AsyncTestResult(
            success=not race_condition_detected,
            duration_ms=duration_ms,
            data={
                "expected_count": shared_resource_operations,
                "actual_count": shared_state["counter"],
                "race_condition_detected": race_condition_detected,
                "operations_completed": len(shared_state["operations"])
            }
        )


class EventBusTestUtilities:
    """Utilities for testing event-driven architecture"""

    @staticmethod
    def create_event_testing_scenario(mock_container: MockServiceContainer):
        """Create event bus testing scenario with event tracking"""
        event_bus_mock = mock_container.get_mock(IEventBus)

        published_events = []
        event_handlers = {}

        async def mock_publish(event_type: str, event_data: Dict[str, Any]):
            event_id = str(uuid.uuid4())
            event = {
                "id": event_id,
                "type": event_type,
                "data": event_data,
                "timestamp": time.time()
            }
            published_events.append(event)

            # Simulate event handling
            if event_type in event_handlers:
                for handler in event_handlers[event_type]:
                    await handler(event)

            return event_id

        def mock_subscribe(event_type: str, handler: Callable):
            if event_type not in event_handlers:
                event_handlers[event_type] = []
            event_handlers[event_type].append(handler)

        event_bus_mock.publish.side_effect = mock_publish
        event_bus_mock.subscribe.side_effect = mock_subscribe

        return {
            'published_events': published_events,
            'event_handlers': event_handlers,
            'get_events_by_type': lambda event_type: [e for e in published_events if e['type'] == event_type]
        }


class PerformanceTestingUtilities:
    """Utilities for performance testing async operations"""

    @staticmethod
    async def measure_async_operation_performance(
        operation: Callable,
        iterations: int = 100,
        max_duration_ms: float = 1000
    ) -> Dict[str, Any]:
        """Measure performance of an async operation"""
        durations = []
        failures = 0

        for i in range(iterations):
            start_time = time.time()
            try:
                await operation()
                duration_ms = (time.time() - start_time) * 1000
                durations.append(duration_ms)
            except Exception:
                failures += 1
                duration_ms = (time.time() - start_time) * 1000
                durations.append(duration_ms)

        if durations:
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            # Calculate percentiles
            sorted_durations = sorted(durations)
            p95_index = int(0.95 * len(sorted_durations))
            p99_index = int(0.99 * len(sorted_durations))

            return {
                "iterations": iterations,
                "failures": failures,
                "success_rate": ((iterations - failures) / iterations) * 100,
                "avg_duration_ms": avg_duration,
                "min_duration_ms": min_duration,
                "max_duration_ms": max_duration,
                "p95_duration_ms": sorted_durations[p95_index] if p95_index < len(sorted_durations) else max_duration,
                "p99_duration_ms": sorted_durations[p99_index] if p99_index < len(sorted_durations) else max_duration,
                "performance_within_target": max_duration <= max_duration_ms
            }
        else:
            return {
                "iterations": 0,
                "failures": failures,
                "success_rate": 0,
                "performance_within_target": False
            }

    @staticmethod
    async def stress_test_async_system(
        mock_container: MockServiceContainer,
        concurrent_operations: int = 50,
        duration_seconds: int = 10
    ) -> Dict[str, Any]:
        """Stress test async system with high load"""
        logger_mock = mock_container.get_mock(IParameterLogger)
        db_mock = mock_container.get_mock(IDatabaseService)

        operations_completed = 0
        errors = 0

        async def stress_operation():
            nonlocal operations_completed, errors
            try:
                await logger_mock.log_parameter(f"stress_param_{operations_completed}", 1.0)
                await db_mock.execute_query("SELECT 1")
                operations_completed += 1
            except Exception:
                errors += 1

        # Run stress test for specified duration
        start_time = time.time()
        end_time = start_time + duration_seconds

        tasks = []
        while time.time() < end_time:
            for _ in range(concurrent_operations):
                task = asyncio.create_task(stress_operation())
                tasks.append(task)

            # Wait a bit before next batch
            await asyncio.sleep(0.1)

        # Wait for remaining tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = time.time() - start_time

        return {
            "duration_seconds": total_duration,
            "operations_completed": operations_completed,
            "errors": errors,
            "operations_per_second": operations_completed / total_duration,
            "error_rate": (errors / (operations_completed + errors)) * 100 if operations_completed + errors > 0 else 0,
            "concurrent_operations": concurrent_operations
        }


# Pytest fixtures for async testing
@pytest.fixture
async def async_test_context():
    """Pytest fixture providing async test context with cleanup"""
    async with AsyncTestContext() as context:
        yield context


@pytest.fixture
def event_testing_scenario(mock_container):
    """Pytest fixture for event testing scenario"""
    return EventBusTestUtilities.create_event_testing_scenario(mock_container)


@pytest.fixture
def transaction_rollback_scenario(mock_container):
    """Pytest fixture for transaction rollback testing"""
    return DatabaseTransactionTestUtilities.create_transaction_rollback_scenario(mock_container)


# Example usage and tests
if __name__ == "__main__":
    async def example_usage():
        """Example of how to use async testing utilities"""
        mock_container = MockServiceContainer()

        # Test concurrent operations
        results = await ConcurrentOperationTestUtilities.simulate_concurrent_parameter_logging(
            mock_container, concurrent_writers=3, operations_per_writer=5
        )

        print(f"Concurrent operation results: {len(results)} writers completed")
        for i, result in enumerate(results):
            print(f"Writer {i}: Success={result.success}, Duration={result.duration_ms:.2f}ms")

        # Test race condition
        race_result = await ConcurrentOperationTestUtilities.simulate_race_condition_scenario(
            mock_container, shared_resource_operations=10
        )

        print(f"Race condition test: Success={race_result.success}")
        print(f"Race condition data: {race_result.data}")

    asyncio.run(example_usage())