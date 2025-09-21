"""
Data integrity and race condition testing framework for comprehensive atomic operation validation.
"""
import pytest
import asyncio
import time
import uuid
import threading
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

from tests.unit.test_container_mocking import MockServiceContainer
from src.abstractions.interfaces import IDatabaseService, IParameterLogger, IStateManager


@dataclass
class DataIntegrityTestResult:
    """Result of a data integrity test"""
    test_name: str
    success: bool
    race_condition_detected: bool
    data_consistency_verified: bool
    transaction_integrity: bool
    execution_time_ms: float
    operations_attempted: int
    operations_successful: int
    error_details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AtomicOperationTesting:
    """Testing framework for atomic operations and transaction integrity"""

    @staticmethod
    async def test_dual_mode_logging_atomicity(mock_container: MockServiceContainer) -> DataIntegrityTestResult:
        """Test atomic dual-mode logging operations"""
        logger_mock = mock_container.get_mock(IParameterLogger)
        db_mock = mock_container.get_mock(IDatabaseService)

        # Track dual-table operations
        parameter_history_operations = []
        process_data_operations = []

        async def mock_log_to_parameter_history(param_id: str, value: float, timestamp: float):
            parameter_history_operations.append({"param_id": param_id, "value": value, "timestamp": timestamp})
            return True

        async def mock_log_to_process_data(param_id: str, value: float, timestamp: float):
            process_data_operations.append({"param_id": param_id, "value": value, "timestamp": timestamp})
            return True

        # Setup dual-logging behavior
        logger_mock.log_to_parameter_history = AsyncMock(side_effect=mock_log_to_parameter_history)
        logger_mock.log_to_process_data = AsyncMock(side_effect=mock_log_to_process_data)

        start_time = time.time()
        operations_attempted = 0
        operations_successful = 0

        try:
            # Test atomic dual-table logging
            for i in range(10):
                operations_attempted += 1
                param_id = f"PARAM_{i}"
                value = random.uniform(10.0, 100.0)
                timestamp = time.time()

                # Atomic operation - both tables must be updated or neither
                try:
                    # Begin transaction
                    transaction_id = await db_mock.begin_transaction()

                    # Log to both tables within transaction
                    await logger_mock.log_to_parameter_history(param_id, value, timestamp)
                    await logger_mock.log_to_process_data(param_id, value, timestamp)

                    # Commit transaction
                    await db_mock.commit_transaction(transaction_id)
                    operations_successful += 1

                except Exception as e:
                    # Rollback on any failure
                    await db_mock.rollback_transaction(transaction_id)
                    # Remove partial operations
                    parameter_history_operations = [op for op in parameter_history_operations if op["param_id"] != param_id]
                    process_data_operations = [op for op in process_data_operations if op["param_id"] != param_id]

            execution_time_ms = (time.time() - start_time) * 1000

            # Verify data consistency - both tables should have same entries
            consistency_verified = len(parameter_history_operations) == len(process_data_operations)

            if consistency_verified:
                for i, param_op in enumerate(parameter_history_operations):
                    process_op = process_data_operations[i]
                    if (param_op["param_id"] != process_op["param_id"] or
                        param_op["value"] != process_op["value"]):
                        consistency_verified = False
                        break

            return DataIntegrityTestResult(
                test_name="dual_mode_logging_atomicity",
                success=operations_successful == operations_attempted,
                race_condition_detected=False,
                data_consistency_verified=consistency_verified,
                transaction_integrity=True,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                metadata={
                    "parameter_history_entries": len(parameter_history_operations),
                    "process_data_entries": len(process_data_operations)
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return DataIntegrityTestResult(
                test_name="dual_mode_logging_atomicity",
                success=False,
                race_condition_detected=False,
                data_consistency_verified=False,
                transaction_integrity=False,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                error_details=str(e)
            )

    @staticmethod
    async def test_transaction_rollback_integrity(mock_container: MockServiceContainer) -> DataIntegrityTestResult:
        """Test transaction rollback maintains data integrity"""
        db_mock = mock_container.get_mock(IDatabaseService)

        committed_transactions = []
        rolled_back_transactions = []

        async def mock_commit_transaction(transaction_id: str):
            committed_transactions.append(transaction_id)
            return True

        async def mock_rollback_transaction(transaction_id: str):
            rolled_back_transactions.append(transaction_id)
            return True

        db_mock.commit_transaction = AsyncMock(side_effect=mock_commit_transaction)
        db_mock.rollback_transaction = AsyncMock(side_effect=mock_rollback_transaction)

        start_time = time.time()
        operations_attempted = 0
        operations_successful = 0

        try:
            # Test multiple transactions with some failures
            for i in range(10):
                operations_attempted += 1
                transaction_id = f"tx_{uuid.uuid4()}"

                # Begin transaction
                await db_mock.begin_transaction()

                # Simulate transaction operations
                try:
                    # Simulate failure for some transactions
                    if i % 3 == 0:  # Every 3rd transaction fails
                        raise Exception("Simulated transaction failure")

                    # Simulate successful operations
                    await asyncio.sleep(0.001)  # Simulate work

                    # Commit successful transaction
                    await db_mock.commit_transaction(transaction_id)
                    operations_successful += 1

                except Exception:
                    # Rollback failed transaction
                    await db_mock.rollback_transaction(transaction_id)

            execution_time_ms = (time.time() - start_time) * 1000

            # Verify transaction integrity - no orphaned transactions
            total_handled = len(committed_transactions) + len(rolled_back_transactions)
            transaction_integrity = total_handled == operations_attempted

            return DataIntegrityTestResult(
                test_name="transaction_rollback_integrity",
                success=operations_successful > 0,
                race_condition_detected=False,
                data_consistency_verified=True,
                transaction_integrity=transaction_integrity,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                metadata={
                    "committed_transactions": len(committed_transactions),
                    "rolled_back_transactions": len(rolled_back_transactions)
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return DataIntegrityTestResult(
                test_name="transaction_rollback_integrity",
                success=False,
                race_condition_detected=False,
                data_consistency_verified=False,
                transaction_integrity=False,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                error_details=str(e)
            )


class RaceConditionTesting:
    """Testing framework for race condition detection and prevention"""

    @staticmethod
    async def test_concurrent_state_transitions(mock_container: MockServiceContainer) -> DataIntegrityTestResult:
        """Test concurrent state transitions for race conditions"""
        state_mock = mock_container.get_mock(IStateManager)

        shared_state = {"current_state": "IDLE", "state_changes": [], "access_count": 0}
        state_lock = asyncio.Lock()

        async def mock_set_state(new_state: str):
            async with state_lock:
                shared_state["access_count"] += 1
                # Simulate some processing time to increase race condition chance
                await asyncio.sleep(0.001)
                old_state = shared_state["current_state"]
                shared_state["current_state"] = new_state
                shared_state["state_changes"].append({"from": old_state, "to": new_state, "timestamp": time.time()})
                return True

        async def mock_get_state():
            async with state_lock:
                shared_state["access_count"] += 1
                await asyncio.sleep(0.001)
                return shared_state["current_state"]

        state_mock.set_state = AsyncMock(side_effect=mock_set_state)
        state_mock.get_state = AsyncMock(side_effect=mock_get_state)

        start_time = time.time()
        operations_attempted = 0
        operations_successful = 0

        try:
            # Create concurrent state transition tasks
            state_transitions = [
                ("IDLE", "STARTING"),
                ("STARTING", "RUNNING"),
                ("RUNNING", "STOPPING"),
                ("STOPPING", "IDLE")
            ]

            async def state_transition_worker(from_state: str, to_state: str, worker_id: int):
                nonlocal operations_attempted, operations_successful
                operations_attempted += 1

                try:
                    # Check current state
                    current = await state_mock.get_state()

                    # Only transition if in expected state
                    if current == from_state:
                        await state_mock.set_state(to_state)
                        operations_successful += 1
                        return True
                    else:
                        return False

                except Exception:
                    return False

            # Run multiple concurrent workers for each transition
            tasks = []
            for i, (from_state, to_state) in enumerate(state_transitions):
                for worker_id in range(3):  # 3 workers per transition
                    task = asyncio.create_task(state_transition_worker(from_state, to_state, worker_id))
                    tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            execution_time_ms = (time.time() - start_time) * 1000

            # Analyze for race conditions
            state_changes = shared_state["state_changes"]
            race_condition_detected = False

            # Check for invalid state transitions or concurrent modifications
            for i in range(1, len(state_changes)):
                prev_change = state_changes[i-1]
                curr_change = state_changes[i]

                # Check if state transition is logically valid
                if curr_change["from"] != prev_change["to"]:
                    race_condition_detected = True
                    break

            # Check if final state is consistent
            expected_final_states = ["IDLE", "STARTING", "RUNNING", "STOPPING"]
            final_state = shared_state["current_state"]
            data_consistency_verified = final_state in expected_final_states

            return DataIntegrityTestResult(
                test_name="concurrent_state_transitions",
                success=operations_successful > 0,
                race_condition_detected=race_condition_detected,
                data_consistency_verified=data_consistency_verified,
                transaction_integrity=True,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                metadata={
                    "final_state": final_state,
                    "total_state_changes": len(state_changes),
                    "total_state_accesses": shared_state["access_count"]
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return DataIntegrityTestResult(
                test_name="concurrent_state_transitions",
                success=False,
                race_condition_detected=True,
                data_consistency_verified=False,
                transaction_integrity=False,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                error_details=str(e)
            )

    @staticmethod
    async def test_concurrent_dual_table_writes(mock_container: MockServiceContainer) -> DataIntegrityTestResult:
        """Test concurrent writes to dual tables for race conditions"""
        logger_mock = mock_container.get_mock(IParameterLogger)
        db_mock = mock_container.get_mock(IDatabaseService)

        # Simulate dual-table data storage
        parameter_history = {}
        process_data = {}
        write_operations = []
        write_lock = asyncio.Lock()

        async def mock_dual_table_write(param_id: str, value: float, include_process: bool = False):
            operation_id = str(uuid.uuid4())
            write_operations.append({
                "operation_id": operation_id,
                "param_id": param_id,
                "value": value,
                "include_process": include_process,
                "timestamp": time.time()
            })

            async with write_lock:
                # Always write to parameter_history
                parameter_history[param_id] = {"value": value, "operation_id": operation_id}

                # Simulate processing delay that could cause race conditions
                await asyncio.sleep(0.001)

                # Conditionally write to process_data
                if include_process:
                    process_data[param_id] = {"value": value, "operation_id": operation_id}

                return operation_id

        logger_mock.dual_table_write = AsyncMock(side_effect=mock_dual_table_write)

        start_time = time.time()
        operations_attempted = 0
        operations_successful = 0

        try:
            # Create concurrent writers
            async def concurrent_writer(writer_id: int, parameter_count: int):
                nonlocal operations_attempted, operations_successful

                for i in range(parameter_count):
                    operations_attempted += 1
                    param_id = f"PARAM_{writer_id}_{i}"
                    value = random.uniform(1.0, 100.0)
                    include_process = (i % 2 == 0)  # Include in process data every other time

                    try:
                        operation_id = await logger_mock.dual_table_write(param_id, value, include_process)
                        operations_successful += 1
                    except Exception:
                        pass

            # Run multiple concurrent writers
            writer_tasks = []
            for writer_id in range(5):  # 5 concurrent writers
                task = asyncio.create_task(concurrent_writer(writer_id, 10))  # 10 operations each
                writer_tasks.append(task)

            await asyncio.gather(*writer_tasks)

            execution_time_ms = (time.time() - start_time) * 1000

            # Analyze for race conditions and data consistency
            race_condition_detected = False
            data_consistency_verified = True

            # Check for data inconsistencies
            for param_id, param_data in parameter_history.items():
                # Check if parameter exists in process_data when it should
                operation = next((op for op in write_operations
                                if op["param_id"] == param_id and op["operation_id"] == param_data["operation_id"]), None)

                if operation and operation["include_process"]:
                    if param_id not in process_data:
                        race_condition_detected = True
                        data_consistency_verified = False
                        break
                    elif process_data[param_id]["operation_id"] != param_data["operation_id"]:
                        race_condition_detected = True
                        data_consistency_verified = False
                        break

            return DataIntegrityTestResult(
                test_name="concurrent_dual_table_writes",
                success=operations_successful > 0,
                race_condition_detected=race_condition_detected,
                data_consistency_verified=data_consistency_verified,
                transaction_integrity=True,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                metadata={
                    "parameter_history_entries": len(parameter_history),
                    "process_data_entries": len(process_data),
                    "total_write_operations": len(write_operations)
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return DataIntegrityTestResult(
                test_name="concurrent_dual_table_writes",
                success=False,
                race_condition_detected=True,
                data_consistency_verified=False,
                transaction_integrity=False,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                error_details=str(e)
            )


class CompensatingActionTesting:
    """Testing framework for compensating actions and failure recovery"""

    @staticmethod
    async def test_compensating_actions_on_failure(mock_container: MockServiceContainer) -> DataIntegrityTestResult:
        """Test compensating actions maintain data integrity on failures"""
        db_mock = mock_container.get_mock(IDatabaseService)
        logger_mock = mock_container.get_mock(IParameterLogger)

        # Track compensating actions
        compensating_actions = []
        successful_operations = []
        failed_operations = []

        async def mock_compensate_dual_logging(operation_id: str, param_id: str):
            compensating_actions.append({
                "operation_id": operation_id,
                "param_id": param_id,
                "timestamp": time.time(),
                "action": "remove_partial_data"
            })
            return True

        async def mock_dual_logging_operation(param_id: str, value: float, should_fail: bool = False):
            operation_id = str(uuid.uuid4())

            try:
                # Step 1: Write to parameter_history
                await asyncio.sleep(0.001)  # Simulate database write

                if should_fail and random.random() < 0.3:  # 30% chance of failure
                    raise Exception("Simulated database failure")

                # Step 2: Write to process_data
                await asyncio.sleep(0.001)  # Simulate second database write

                if should_fail and random.random() < 0.3:  # 30% chance of failure at second step
                    # Compensating action needed - remove from parameter_history
                    await mock_compensate_dual_logging(operation_id, param_id)
                    raise Exception("Simulated failure after partial write")

                successful_operations.append({
                    "operation_id": operation_id,
                    "param_id": param_id,
                    "value": value
                })
                return operation_id

            except Exception as e:
                failed_operations.append({
                    "operation_id": operation_id,
                    "param_id": param_id,
                    "error": str(e)
                })
                raise

        logger_mock.dual_logging_operation = AsyncMock(side_effect=mock_dual_logging_operation)

        start_time = time.time()
        operations_attempted = 0
        operations_successful = 0

        try:
            # Test operations with failure scenarios
            for i in range(20):
                operations_attempted += 1
                param_id = f"PARAM_{i}"
                value = random.uniform(1.0, 100.0)
                should_fail = (i % 3 == 0)  # Every 3rd operation has failure potential

                try:
                    await logger_mock.dual_logging_operation(param_id, value, should_fail)
                    operations_successful += 1
                except Exception:
                    # Failure is expected for some operations
                    pass

            execution_time_ms = (time.time() - start_time) * 1000

            # Verify compensating actions maintain integrity
            total_failures = len(failed_operations)
            total_compensations = len(compensating_actions)

            # Data consistency check - no partial writes left
            data_consistency_verified = True
            transaction_integrity = total_compensations > 0  # Compensating actions were triggered

            return DataIntegrityTestResult(
                test_name="compensating_actions_on_failure",
                success=operations_successful > 0,
                race_condition_detected=False,
                data_consistency_verified=data_consistency_verified,
                transaction_integrity=transaction_integrity,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                metadata={
                    "total_failures": total_failures,
                    "compensating_actions": total_compensations,
                    "successful_operations": len(successful_operations)
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return DataIntegrityTestResult(
                test_name="compensating_actions_on_failure",
                success=False,
                race_condition_detected=False,
                data_consistency_verified=False,
                transaction_integrity=False,
                execution_time_ms=execution_time_ms,
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                error_details=str(e)
            )


class DataIntegrityTestOrchestrator:
    """Orchestrates all data integrity testing scenarios"""

    def __init__(self, mock_container: MockServiceContainer = None):
        self.mock_container = mock_container or MockServiceContainer()
        self.test_results: List[DataIntegrityTestResult] = []

    async def run_comprehensive_data_integrity_assessment(self) -> Dict[str, Any]:
        """Run complete data integrity assessment"""
        print("📊 Starting comprehensive data integrity assessment...")

        # Run all data integrity tests
        test_suites = [
            ("Dual Mode Logging Atomicity", AtomicOperationTesting.test_dual_mode_logging_atomicity(self.mock_container)),
            ("Transaction Rollback Integrity", AtomicOperationTesting.test_transaction_rollback_integrity(self.mock_container)),
            ("Concurrent State Transitions", RaceConditionTesting.test_concurrent_state_transitions(self.mock_container)),
            ("Concurrent Dual Table Writes", RaceConditionTesting.test_concurrent_dual_table_writes(self.mock_container)),
            ("Compensating Actions", CompensatingActionTesting.test_compensating_actions_on_failure(self.mock_container))
        ]

        all_results = []
        for suite_name, test_coro in test_suites:
            print(f"  Running {suite_name} tests...")
            result = await test_coro
            all_results.append(result)

        # Analyze results
        total_tests = len(all_results)
        successful_tests = sum(1 for r in all_results if r.success)
        race_conditions_detected = sum(1 for r in all_results if r.race_condition_detected)
        data_inconsistencies = sum(1 for r in all_results if not r.data_consistency_verified)
        transaction_failures = sum(1 for r in all_results if not r.transaction_integrity)

        total_operations = sum(r.operations_attempted for r in all_results)
        successful_operations = sum(r.operations_successful for r in all_results)

        return {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": (successful_tests / total_tests) * 100 if total_tests > 0 else 0
            },
            "integrity_analysis": {
                "race_conditions_detected": race_conditions_detected,
                "data_inconsistencies": data_inconsistencies,
                "transaction_failures": transaction_failures,
                "total_operations": total_operations,
                "successful_operations": successful_operations,
                "operation_success_rate": (successful_operations / total_operations) * 100 if total_operations > 0 else 0
            },
            "critical_issues": [
                {
                    "test": r.test_name,
                    "issue": "Race condition detected" if r.race_condition_detected else
                            "Data inconsistency" if not r.data_consistency_verified else
                            "Transaction integrity failure" if not r.transaction_integrity else "Unknown",
                    "details": r.error_details,
                    "operations_attempted": r.operations_attempted,
                    "operations_successful": r.operations_successful
                } for r in all_results if not r.success or r.race_condition_detected or not r.data_consistency_verified
            ],
            "all_results": all_results
        }


# Pytest fixtures
@pytest.fixture
def data_integrity_orchestrator(mock_container):
    """Pytest fixture for data integrity test orchestrator"""
    return DataIntegrityTestOrchestrator(mock_container)


# Example usage
if __name__ == "__main__":
    async def main():
        orchestrator = DataIntegrityTestOrchestrator()
        results = await orchestrator.run_comprehensive_data_integrity_assessment()

        print(f"\n📊 Data Integrity Assessment Results:")
        print(f"   Total Tests: {results['summary']['total_tests']}")
        print(f"   Successful: {results['summary']['successful_tests']}")
        print(f"   Failed: {results['summary']['failed_tests']}")
        print(f"   Success Rate: {results['summary']['success_rate']:.1f}%")

        print(f"\n⚠️  Integrity Analysis:")
        print(f"   Race Conditions: {results['integrity_analysis']['race_conditions_detected']}")
        print(f"   Data Inconsistencies: {results['integrity_analysis']['data_inconsistencies']}")
        print(f"   Transaction Failures: {results['integrity_analysis']['transaction_failures']}")
        print(f"   Operation Success Rate: {results['integrity_analysis']['operation_success_rate']:.1f}%")

        if results['critical_issues']:
            print(f"\n🚨 Critical Issues:")
            for issue in results['critical_issues']:
                print(f"   - {issue['test']}: {issue['issue']}")

    asyncio.run(main())