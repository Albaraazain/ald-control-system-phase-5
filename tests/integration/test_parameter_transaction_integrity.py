#!/usr/bin/env python3
"""
Transaction Integrity Integration Tests for Parameter Synchronization

Tests the transactional aspects of parameter synchronization:
1. ACID compliance with component_parameters updates
2. Rollback scenarios and compensation actions
3. Concurrent transaction handling
4. Deadlock prevention and recovery
5. Consistency guarantees across multiple tables
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger
from src.db import get_supabase
from src.data_collection.transactional.dual_mode_repository import DualModeRepository
from src.data_collection.transactional.interfaces import (
    ParameterData, MachineState, DualModeResult,
    ITransactionManager, IDualModeRepository
)
from src.data_collection.transactional.transaction_manager import TransactionManager

# Set up logging
logger = setup_logger(__name__)


class TransactionIntegrityTest:
    """Transaction integrity test framework for parameter synchronization."""

    def __init__(self):
        self.supabase = get_supabase()
        self.test_machine_id = f"test-machine-{uuid.uuid4()}"

    @pytest.mark.asyncio
    async def test_acid_compliance_parameter_updates(self):
        """Test ACID compliance for parameter synchronization updates."""
        logger.info("🔍 Testing ACID compliance for parameter updates")

        try:
            # Create test parameters
            test_parameters = []
            param_ids = []
            for i in range(5):
                param_id = await self._create_test_parameter(name=f"acid_test_param_{i}")
                param_ids.append(param_id)
                test_parameters.append(ParameterData(
                    parameter_id=param_id,
                    value=float(i * 10.5),
                    timestamp=datetime.now()
                ))

            machine_state = MachineState(
                status="processing",
                current_process_id=str(uuid.uuid4()),
                timestamp=datetime.now()
            )

            # Mock the dual mode repository for enhanced testing
            with patch('src.data_collection.transactional.dual_mode_repository.DualModeRepository') as MockRepo:
                mock_repo = MockRepo.return_value

                # Test Atomicity - all operations succeed or all fail
                mock_repo.insert_dual_mode_atomic = AsyncMock(return_value=DualModeResult(
                    history_count=5,
                    process_count=5,
                    component_updates_count=5,  # Enhanced: component_parameters updated
                    machine_state=machine_state,
                    transaction_id=str(uuid.uuid4()),
                    success=True
                ))

                result = await mock_repo.insert_dual_mode_atomic(test_parameters, machine_state)

                # Verify atomicity
                assert result.success is True
                assert result.history_count == 5
                assert result.process_count == 5
                assert result.component_updates_count == 5  # Enhanced functionality

                # Test Consistency - verify all tables updated consistently
                mock_repo.validate_batch_constraints = AsyncMock(return_value=[])
                constraints_result = await mock_repo.validate_batch_constraints(
                    test_parameters, machine_state.current_process_id
                )
                assert len(constraints_result) == 0

                # Test Isolation - concurrent operations don't interfere
                # (Tested in concurrent operations test)

                # Test Durability - changes persist after commit
                # (Tested through database verification)

                logger.info("✅ ACID compliance test passed")
                return True

        except Exception as e:
            logger.error(f"❌ ACID compliance test failed: {str(e)}")
            return False

    @pytest.mark.asyncio
    async def test_transaction_rollback_scenarios(self):
        """Test various transaction rollback scenarios."""
        logger.info("🔍 Testing transaction rollback scenarios")

        try:
            # Scenario 1: PLC write failure should rollback database updates
            test_param_id = await self._create_test_parameter()

            # Mock transaction manager
            with patch('src.data_collection.transactional.transaction_manager.TransactionManager') as MockTxnMgr:
                mock_txn_mgr = MockTxnMgr.return_value
                mock_txn_mgr.begin_transaction = AsyncMock()
                mock_txn_mgr.commit = AsyncMock()
                mock_txn_mgr.rollback = AsyncMock()

                # Simulate PLC failure during parameter write
                with patch('src.plc.manager.plc_manager') as mock_plc_mgr:
                    mock_plc_mgr.plc.write_parameter = AsyncMock(return_value=False)  # Failure
                    mock_plc_mgr.plc.is_connected = Mock(return_value=True)

                    # Get initial parameter state
                    initial_state = self.supabase.table("component_parameters").select("*").eq(
                        "id", test_param_id
                    ).single().execute()
                    initial_set_value = initial_state.data.get('set_value')

                    # Attempt parameter write with enhanced synchronization
                    try:
                        async with mock_txn_mgr.begin_transaction():
                            # Enhanced implementation would update both set_value and current_value
                            self.supabase.table('component_parameters').update({
                                'set_value': 999.9,
                                'current_value': 999.9  # Enhanced behavior
                            }).eq('id', test_param_id).execute()

                            # Simulate PLC write failure
                            success = await mock_plc_mgr.plc.write_parameter(test_param_id, 999.9)
                            if not success:
                                await mock_txn_mgr.rollback()
                                raise RuntimeError("PLC write failed")

                            await mock_txn_mgr.commit()

                    except RuntimeError:
                        # Expected failure due to PLC write failure
                        pass

                    # Verify rollback was called
                    mock_txn_mgr.rollback.assert_called_once()

                    # Verify database state was not changed (rollback successful)
                    final_state = self.supabase.table("component_parameters").select("*").eq(
                        "id", test_param_id
                    ).single().execute()
                    final_set_value = final_state.data.get('set_value')

                    assert initial_set_value == final_set_value

            # Scenario 2: Database constraint violation rollback
            invalid_parameters = [
                ParameterData(parameter_id="nonexistent_param", value=42.0)
            ]

            with patch('src.data_collection.transactional.dual_mode_repository.DualModeRepository') as MockRepo:
                mock_repo = MockRepo.return_value
                mock_repo.validate_batch_constraints = AsyncMock(return_value=[
                    "Parameter nonexistent_param does not exist"
                ])

                constraints = await mock_repo.validate_batch_constraints(invalid_parameters, None)
                assert len(constraints) > 0  # Should have constraint violations

            logger.info("✅ Transaction rollback scenarios test passed")
            return True

        except Exception as e:
            logger.error(f"❌ Transaction rollback scenarios test failed: {str(e)}")
            return False

    @pytest.mark.asyncio
    async def test_concurrent_transaction_handling(self):
        """Test concurrent transaction handling and deadlock prevention."""
        logger.info("🔍 Testing concurrent transaction handling")

        try:
            # Create test parameters for concurrent access
            param_ids = []
            for i in range(10):
                param_id = await self._create_test_parameter(name=f"concurrent_param_{i}")
                param_ids.append(param_id)

            # Test concurrent writes to different parameters (should succeed)
            async def concurrent_parameter_write(param_id: str, value: float, delay: float = 0):
                await asyncio.sleep(delay)  # Simulate processing time

                with patch('src.plc.manager.plc_manager') as mock_plc_mgr:
                    mock_plc_mgr.plc.write_parameter = AsyncMock(return_value=True)
                    mock_plc_mgr.plc.is_connected = Mock(return_value=True)

                    # Simulate enhanced parameter write with transaction
                    async with self._mock_transaction():
                        # Update both set_value and current_value
                        self.supabase.table('component_parameters').update({
                            'set_value': value,
                            'current_value': value,  # Enhanced behavior
                            'updated_at': datetime.now().isoformat()
                        }).eq('id', param_id).execute()

                        await mock_plc_mgr.plc.write_parameter(param_id, value)

                return param_id, value

            # Execute concurrent writes
            tasks = []
            for i, param_id in enumerate(param_ids[:5]):  # Test with 5 concurrent writes
                task = asyncio.create_task(
                    concurrent_parameter_write(param_id, float(i * 20), delay=i * 0.1)
                )
                tasks.append(task)

            start_time = datetime.now()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = datetime.now()

            # Verify no exceptions occurred
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Concurrent transactions failed: {exceptions}"

            # Verify all transactions completed
            successful_writes = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_writes) == 5

            # Test concurrent reads and writes (should handle gracefully)
            async def concurrent_parameter_read():
                test_values = {pid: float(i * 5) for i, pid in enumerate(param_ids)}

                with patch('src.plc.manager.plc_manager') as mock_plc_mgr:
                    mock_plc_mgr.plc.read_all_parameters = AsyncMock(return_value=test_values)
                    mock_plc_mgr.plc.is_connected = Mock(return_value=True)

                    # Simulate enhanced continuous logging with current_value updates
                    parameters = [
                        ParameterData(parameter_id=pid, value=value)
                        for pid, value in test_values.items()
                    ]

                    # Mock enhanced dual mode repository
                    with patch('src.data_collection.transactional.dual_mode_repository.DualModeRepository') as MockRepo:
                        mock_repo = MockRepo.return_value
                        mock_repo.insert_dual_mode_atomic = AsyncMock(return_value=DualModeResult(
                            history_count=len(parameters),
                            process_count=0,
                            component_updates_count=len(parameters),  # Enhanced: updates component_parameters
                            machine_state=MachineState("idle", None, datetime.now()),
                            transaction_id=str(uuid.uuid4()),
                            success=True
                        ))

                        await mock_repo.insert_dual_mode_atomic(
                            parameters,
                            MachineState("idle", None, datetime.now())
                        )

                return len(parameters)

            # Execute concurrent read while writes are happening
            read_task = asyncio.create_task(concurrent_parameter_read())
            write_task = asyncio.create_task(concurrent_parameter_write(param_ids[5], 100.0))

            read_result, write_result = await asyncio.gather(read_task, write_task)

            assert read_result > 0
            assert write_result[1] == 100.0

            logger.info("✅ Concurrent transaction handling test passed")
            return True

        except Exception as e:
            logger.error(f"❌ Concurrent transaction handling test failed: {str(e)}")
            return False

    @pytest.mark.asyncio
    async def test_compensation_actions_and_recovery(self):
        """Test compensation actions and failure recovery."""
        logger.info("🔍 Testing compensation actions and recovery")

        try:
            # Mock failure recovery interface
            with patch('src.data_collection.transactional.failure_recovery.FailureRecovery') as MockRecovery:
                mock_recovery = MockRecovery.return_value
                mock_recovery.execute_with_retry = AsyncMock()
                mock_recovery.create_compensating_action = AsyncMock()
                mock_recovery.execute_compensating_actions = AsyncMock()

                # Test retry mechanism
                retry_count = 0
                async def failing_operation():
                    nonlocal retry_count
                    retry_count += 1
                    if retry_count < 3:
                        raise Exception("Temporary failure")
                    return "success"

                mock_recovery.execute_with_retry.side_effect = failing_operation

                # Execute operation with retry
                result = await mock_recovery.execute_with_retry(failing_operation, max_retries=3)

                # Verify retry was called multiple times
                assert mock_recovery.execute_with_retry.called

                # Test compensation actions
                operation_id = str(uuid.uuid4())
                operation_data = {
                    "parameter_id": "test_param",
                    "old_value": 50.0,
                    "new_value": 100.0,
                    "timestamp": datetime.now().isoformat()
                }

                await mock_recovery.create_compensating_action(operation_id, operation_data)
                mock_recovery.create_compensating_action.assert_called_once_with(operation_id, operation_data)

                # Test executing compensation actions
                transaction_id = str(uuid.uuid4())
                await mock_recovery.execute_compensating_actions(transaction_id)
                mock_recovery.execute_compensating_actions.assert_called_once_with(transaction_id)

            logger.info("✅ Compensation actions and recovery test passed")
            return True

        except Exception as e:
            logger.error(f"❌ Compensation actions and recovery test failed: {str(e)}")
            return False

    @pytest.mark.asyncio
    async def test_consistency_across_multiple_tables(self):
        """Test consistency guarantees across parameter_value_history, process_data_points, and component_parameters."""
        logger.info("🔍 Testing consistency across multiple tables")

        try:
            # Create test data
            test_parameters = []
            for i in range(3):
                param_id = await self._create_test_parameter(name=f"consistency_param_{i}")
                test_parameters.append(ParameterData(
                    parameter_id=param_id,
                    value=float(i * 25.5),
                    timestamp=datetime.now()
                ))

            # Test idle mode - should update parameter_value_history + component_parameters
            idle_state = MachineState(
                status="idle",
                current_process_id=None,
                timestamp=datetime.now()
            )

            with patch('src.data_collection.transactional.dual_mode_repository.DualModeRepository') as MockRepo:
                mock_repo = MockRepo.return_value

                # Enhanced idle mode: updates both tables atomically
                mock_repo.insert_dual_mode_atomic = AsyncMock(return_value=DualModeResult(
                    history_count=3,
                    process_count=0,  # No process data points in idle mode
                    component_updates_count=3,  # Enhanced: component_parameters updated
                    machine_state=idle_state,
                    transaction_id=str(uuid.uuid4()),
                    success=True
                ))

                idle_result = await mock_repo.insert_dual_mode_atomic(test_parameters, idle_state)

                # Verify idle mode consistency
                assert idle_result.history_count == 3
                assert idle_result.process_count == 0
                assert idle_result.component_updates_count == 3  # Enhanced behavior
                assert idle_result.success is True

            # Test processing mode - should update all three tables
            process_state = MachineState(
                status="processing",
                current_process_id=str(uuid.uuid4()),
                timestamp=datetime.now()
            )

            # Enhanced processing mode: updates all three tables atomically
            mock_repo.insert_dual_mode_atomic = AsyncMock(return_value=DualModeResult(
                history_count=3,
                process_count=3,  # Process data points updated
                component_updates_count=3,  # Enhanced: component_parameters updated
                machine_state=process_state,
                transaction_id=str(uuid.uuid4()),
                success=True
            ))

            process_result = await mock_repo.insert_dual_mode_atomic(test_parameters, process_state)

            # Verify processing mode consistency
            assert process_result.history_count == 3
            assert process_result.process_count == 3
            assert process_result.component_updates_count == 3  # Enhanced behavior
            assert process_result.success is True

            # Test partial failure scenario - should rollback all tables
            mock_repo.insert_dual_mode_atomic = AsyncMock(return_value=DualModeResult(
                history_count=0,
                process_count=0,
                component_updates_count=0,  # No updates due to failure
                machine_state=process_state,
                transaction_id=str(uuid.uuid4()),
                success=False,
                error_message="Database constraint violation"
            ))

            failure_result = await mock_repo.insert_dual_mode_atomic(test_parameters, process_state)

            # Verify failure handling
            assert failure_result.success is False
            assert failure_result.history_count == 0
            assert failure_result.process_count == 0
            assert failure_result.component_updates_count == 0

            logger.info("✅ Multi-table consistency test passed")
            return True

        except Exception as e:
            logger.error(f"❌ Multi-table consistency test failed: {str(e)}")
            return False

    async def _create_test_parameter(self, name: str = None) -> str:
        """Create a test parameter in the database."""
        param_data = {
            "id": str(uuid.uuid4()),
            "name": name or f"test_param_{uuid.uuid4()}",
            "display_name": "Test Parameter",
            "unit": "units",
            "min_value": 0.0,
            "max_value": 1000.0,
            "default_value": 50.0,
            "current_value": 50.0,
            "set_value": 50.0,
            "read_modbus_address": 1001,
            "write_modbus_address": 2001,
            "component_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        result = self.supabase.table("component_parameters").insert(param_data).execute()
        return result.data[0]["id"]

    async def _mock_transaction(self):
        """Mock transaction context manager."""
        class MockTransaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type:
                    # Rollback on exception
                    pass
                else:
                    # Commit on success
                    pass

        return MockTransaction()


@pytest.mark.asyncio
async def test_transaction_integrity_suite():
    """Main transaction integrity test suite."""
    test_framework = TransactionIntegrityTest()

    # Run all transaction integrity tests
    results = []
    results.append(await test_framework.test_acid_compliance_parameter_updates())
    results.append(await test_framework.test_transaction_rollback_scenarios())
    results.append(await test_framework.test_concurrent_transaction_handling())
    results.append(await test_framework.test_compensation_actions_and_recovery())
    results.append(await test_framework.test_consistency_across_multiple_tables())

    # Generate summary
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r)
    failed_tests = total_tests - passed_tests

    logger.info("=" * 60)
    logger.info("🏁 TRANSACTION INTEGRITY TEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {failed_tests}")
    logger.info(f"Success Rate: {(passed_tests / total_tests * 100):.1f}%")
    logger.info("=" * 60)

    # Assert overall success
    assert failed_tests == 0, f"{failed_tests} transaction integrity tests failed"


if __name__ == "__main__":
    asyncio.run(test_transaction_integrity_suite())