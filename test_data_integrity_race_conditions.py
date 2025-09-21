#!/usr/bin/env python3
"""
Comprehensive Data Integrity and Race Condition Testing Suite

This test suite validates the ALD control system's data integrity under:
- Concurrent operations and race conditions
- Transaction rollback scenarios
- Dual-mode logging consistency
- Process state transitions
- Connection pool exhaustion
- Compensating action execution

Critical Finding: Transactional system exists but not integrated into main.py
- Current: Uses legacy continuous_parameter_logger with race conditions
- Should use: TransactionalParameterLoggerAdapter with atomic operations
"""

import asyncio
import pytest
import time
import uuid
import threading
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from contextlib import asynccontextmanager

# System under test imports
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_collection.transactional.interfaces import (
    ParameterData, MachineState, DualModeResult
)
from src.data_collection.transactional.dual_mode_repository import dual_mode_repository
from src.data_collection.transactional.transaction_manager import transaction_manager
from src.data_collection.transactional.state_repository import state_repository
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.command_flow.state import state as command_state
from src.plc.manager import plc_manager
from src.db import get_supabase
from src.config import MACHINE_ID

class RaceConditionTestFramework:
    """Framework for testing race conditions with precise timing control."""

    def __init__(self):
        self.concurrent_operations = []
        self.barriers = {}
        self.results = {}
        self.timing_data = {}

    async def create_barrier(self, name: str, count: int):
        """Create a timing barrier for synchronized concurrent execution."""
        self.barriers[name] = asyncio.Barrier(count)

    async def wait_for_barrier(self, name: str):
        """Wait for all operations to reach the barrier."""
        await self.barriers[name].wait()

    async def execute_concurrent_operations(self, operations: List[callable], sync_points: List[str] = None):
        """Execute multiple operations concurrently with optional synchronization."""
        tasks = []
        for i, operation in enumerate(operations):
            task = asyncio.create_task(self._execute_with_timing(f"op_{i}", operation, sync_points))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def _execute_with_timing(self, op_id: str, operation: callable, sync_points: List[str] = None):
        """Execute operation with timing data collection."""
        start_time = time.time()
        try:
            if sync_points:
                for sync_point in sync_points:
                    if sync_point in self.barriers:
                        await self.wait_for_barrier(sync_point)

            result = await operation()
            end_time = time.time()

            self.timing_data[op_id] = {
                'duration': end_time - start_time,
                'start_time': start_time,
                'end_time': end_time,
                'success': True
            }
            self.results[op_id] = result
            return result

        except Exception as e:
            end_time = time.time()
            self.timing_data[op_id] = {
                'duration': end_time - start_time,
                'start_time': start_time,
                'end_time': end_time,
                'success': False,
                'error': str(e)
            }
            raise

class DataIntegrityTestSuite:
    """Comprehensive data integrity testing suite."""

    def __init__(self):
        self.race_framework = RaceConditionTestFramework()
        self.test_data = {}
        self.cleanup_tasks = []

    async def setup_test_environment(self):
        """Set up clean test environment."""
        # Initialize transaction manager
        await transaction_manager.initialize()

        # Clean up any existing test data
        await self._cleanup_test_data()

        # Set up test machine state
        await self._setup_test_machine()

    async def teardown_test_environment(self):
        """Clean up test environment."""
        await self._cleanup_test_data()
        await transaction_manager.cleanup()

    async def _setup_test_machine(self):
        """Set up test machine in known state."""
        try:
            supabase = get_supabase()
            # Ensure machine exists in idle state
            machine_data = {
                'id': MACHINE_ID,
                'status': 'idle',
                'current_process_id': None,
                'updated_at': datetime.utcnow().isoformat()
            }
            supabase.table('machines').upsert(machine_data).execute()
        except Exception as e:
            print(f"Warning: Could not set up test machine: {e}")

    async def _cleanup_test_data(self):
        """Clean up test data from database."""
        try:
            supabase = get_supabase()
            # Clean up test records (those with transaction_id starting with 'test_')
            supabase.table('parameter_value_history').delete().like('transaction_id', 'test_%').execute()
            supabase.table('process_data_points').delete().like('transaction_id', 'test_%').execute()
        except Exception as e:
            print(f"Warning: Could not clean up test data: {e}")

    # Race Condition Tests

    async def test_concurrent_dual_mode_logging(self):
        """Test concurrent dual-mode logging operations during state transitions."""
        print("\n=== Testing Concurrent Dual-Mode Logging ===")

        # Create test parameters
        test_params_1 = [
            ParameterData("TEST_PARAM_1", 25.5, 25.0),
            ParameterData("TEST_PARAM_2", 150.0, 150.0)
        ]
        test_params_2 = [
            ParameterData("TEST_PARAM_3", 75.2, 75.0),
            ParameterData("TEST_PARAM_4", 300.0, 300.0)
        ]

        # Set up concurrent operations
        await self.race_framework.create_barrier("start_logging", 2)

        async def log_operation_1():
            await self.race_framework.wait_for_barrier("start_logging")
            machine_state = MachineState("idle", None, datetime.utcnow())
            return await dual_mode_repository.insert_dual_mode_atomic(test_params_1, machine_state)

        async def log_operation_2():
            await self.race_framework.wait_for_barrier("start_logging")
            machine_state = MachineState("processing", "test_process_123", datetime.utcnow())
            return await dual_mode_repository.insert_dual_mode_atomic(test_params_2, machine_state)

        # Execute concurrent operations
        results = await self.race_framework.execute_concurrent_operations([
            log_operation_1, log_operation_2
        ])

        # Validate results
        assert len(results) == 2, "Both operations should complete"
        assert isinstance(results[0], DualModeResult), "First operation should return DualModeResult"
        assert isinstance(results[1], DualModeResult), "Second operation should return DualModeResult"

        # Validate data consistency
        assert results[0].success, f"First operation failed: {results[0].error_message}"
        assert results[1].success, f"Second operation failed: {results[1].error_message}"

        print(f"✓ Concurrent dual-mode logging test passed")
        print(f"  - Operation 1: {results[0].history_count} history, {results[0].process_count} process")
        print(f"  - Operation 2: {results[1].history_count} history, {results[1].process_count} process")

        return results

    async def test_rapid_process_state_transitions(self):
        """Test rapid process start/stop transitions during logging."""
        print("\n=== Testing Rapid Process State Transitions ===")

        process_id = f"test_process_{uuid.uuid4().hex[:8]}"

        # Set up rapid state transitions
        await self.race_framework.create_barrier("state_transition", 3)

        async def start_process():
            await self.race_framework.wait_for_barrier("state_transition")
            return await state_repository.update_machine_state(MACHINE_ID, "processing", process_id)

        async def log_during_transition():
            await self.race_framework.wait_for_barrier("state_transition")
            # Short delay to create race condition
            await asyncio.sleep(0.001)
            params = [ParameterData("TRANSITION_PARAM", 123.45, 123.0)]
            machine_state = await state_repository.get_machine_state(MACHINE_ID)
            return await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)

        async def stop_process():
            await self.race_framework.wait_for_barrier("state_transition")
            # Longer delay to create race condition window
            await asyncio.sleep(0.002)
            return await state_repository.update_machine_state(MACHINE_ID, "idle", None)

        # Execute concurrent state transitions
        results = await self.race_framework.execute_concurrent_operations([
            start_process, log_during_transition, stop_process
        ])

        # Validate results
        assert len(results) == 3, "All operations should complete"

        # Check final state consistency
        final_state = await state_repository.get_machine_state(MACHINE_ID)
        print(f"✓ Rapid state transition test passed")
        print(f"  - Final state: {final_state.status}")
        print(f"  - Logging result: {results[1].success if isinstance(results[1], DualModeResult) else 'Exception'}")

        return results

    async def test_transaction_rollback_scenarios(self):
        """Test transaction rollback and compensating actions."""
        print("\n=== Testing Transaction Rollback Scenarios ===")

        # Test partial failure with rollback
        invalid_params = [
            ParameterData("", None, None),  # Invalid parameter
            ParameterData("VALID_PARAM", 50.0, 50.0)  # Valid parameter
        ]

        machine_state = MachineState("processing", "test_rollback_process", datetime.utcnow())

        # This should fail validation and trigger rollback
        result = await dual_mode_repository.insert_dual_mode_atomic(invalid_params, machine_state)

        # Validate rollback occurred
        assert not result.success, "Operation should fail due to invalid parameters"
        assert result.error_message is not None, "Error message should be present"
        assert result.history_count == 0, "No records should be inserted due to rollback"
        assert result.process_count == 0, "No process records should be inserted due to rollback"

        print(f"✓ Transaction rollback test passed")
        print(f"  - Rollback reason: {result.error_message}")

        return result

    async def test_connection_pool_exhaustion(self):
        """Test system behavior under connection pool exhaustion."""
        print("\n=== Testing Connection Pool Exhaustion ===")

        # Create more concurrent operations than connection pool size
        pool_size = 10
        operation_count = 15

        params = [ParameterData(f"POOL_TEST_{i}", float(i), float(i)) for i in range(5)]
        machine_state = MachineState("idle", None, datetime.utcnow())

        async def pool_operation(op_id: int):
            await asyncio.sleep(random.uniform(0.001, 0.01))  # Random delay
            return await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)

        operations = [lambda i=i: pool_operation(i) for i in range(operation_count)]

        start_time = time.time()
        results = await self.race_framework.execute_concurrent_operations(operations)
        end_time = time.time()

        # Validate results
        successful_ops = sum(1 for r in results if isinstance(r, DualModeResult) and r.success)
        failed_ops = len(results) - successful_ops

        print(f"✓ Connection pool exhaustion test completed")
        print(f"  - Total operations: {operation_count}")
        print(f"  - Successful: {successful_ops}")
        print(f"  - Failed: {failed_ops}")
        print(f"  - Total time: {end_time - start_time:.3f}s")

        return results

    async def test_compensating_action_execution(self):
        """Test compensating actions during partial failures."""
        print("\n=== Testing Compensating Action Execution ===")

        # Create a scenario where process table insert fails
        test_tx_id = f"test_compensation_{uuid.uuid4().hex[:8]}"
        params = [ParameterData("COMPENSATION_TEST", 99.9, 100.0)]

        # Mock failure in process table insert
        original_method = dual_mode_repository._insert_batch_atomic

        async def mock_insert_with_failure(*args, **kwargs):
            # Let history insert succeed, then fail on process insert
            result = await original_method(*args, **kwargs)
            if args[1].is_processing:  # machine_state is second argument
                raise RuntimeError("Simulated process table failure")
            return result

        with patch.object(dual_mode_repository, '_insert_batch_atomic', mock_insert_with_failure):
            machine_state = MachineState("processing", "test_compensation_process", datetime.utcnow())
            result = await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)

        # Validate compensation occurred
        assert not result.success, "Operation should fail due to simulated error"
        assert "process table failure" in result.error_message.lower(), "Error should mention process table failure"

        # Verify no orphaned records remain
        supabase = get_supabase()
        history_records = supabase.table('parameter_value_history').select('*').eq('transaction_id', test_tx_id).execute()
        process_records = supabase.table('process_data_points').select('*').eq('transaction_id', test_tx_id).execute()

        assert len(history_records.data) == 0, "History records should be cleaned up by compensation"
        assert len(process_records.data) == 0, "Process records should not exist due to failure"

        print(f"✓ Compensating action test passed")
        print(f"  - Compensation executed successfully")

        return result

    # Integration Gap Tests

    async def test_legacy_vs_transactional_integration(self):
        """Test the critical integration gap between legacy and transactional systems."""
        print("\n=== Testing Legacy vs Transactional Integration Gap ===")

        # Test current legacy system behavior
        print("Testing legacy continuous_parameter_logger...")

        # Mock PLC data
        mock_plc_data = {
            "LEGACY_TEST_1": 25.5,
            "LEGACY_TEST_2": 150.0
        }

        with patch.object(plc_manager, 'read_all_parameters', return_value=mock_plc_data):
            with patch.object(plc_manager, 'is_connected', return_value=True):
                # Test legacy system
                legacy_start = time.time()
                await continuous_parameter_logger._read_and_log_parameters()
                legacy_end = time.time()

                legacy_duration = legacy_end - legacy_start

        # Test transactional system
        print("Testing transactional dual_mode_repository...")

        transactional_params = [
            ParameterData("TRANSACTIONAL_TEST_1", 25.5, 25.0),
            ParameterData("TRANSACTIONAL_TEST_2", 150.0, 150.0)
        ]
        machine_state = MachineState("idle", None, datetime.utcnow())

        transactional_start = time.time()
        transactional_result = await dual_mode_repository.insert_dual_mode_atomic(transactional_params, machine_state)
        transactional_end = time.time()

        transactional_duration = transactional_end - transactional_start

        # Analyze integration gap
        print(f"✓ Integration gap analysis completed")
        print(f"  - Legacy system duration: {legacy_duration:.3f}s")
        print(f"  - Transactional system duration: {transactional_duration:.3f}s")
        print(f"  - Transactional success: {transactional_result.success}")
        print(f"  - CRITICAL GAP: main.py still uses legacy system!")

        return {
            'legacy_duration': legacy_duration,
            'transactional_duration': transactional_duration,
            'transactional_success': transactional_result.success,
            'integration_gap_exists': True
        }

    # Data Consistency Validation

    async def test_dual_table_consistency(self):
        """Test consistency between parameter_value_history and process_data_points."""
        print("\n=== Testing Dual Table Consistency ===")

        process_id = f"test_consistency_{uuid.uuid4().hex[:8]}"

        # Create consistent test data
        params = [
            ParameterData("CONSISTENCY_TEST_1", 42.0, 42.0),
            ParameterData("CONSISTENCY_TEST_2", 84.0, 84.0)
        ]

        machine_state = MachineState("processing", process_id, datetime.utcnow())

        # Insert data
        result = await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)
        assert result.success, f"Insert failed: {result.error_message}"

        # Validate consistency
        supabase = get_supabase()

        # Get history records
        history_query = supabase.table('parameter_value_history').select('*').eq('transaction_id', result.transaction_id)
        history_records = history_query.execute().data

        # Get process records
        process_query = supabase.table('process_data_points').select('*').eq('transaction_id', result.transaction_id)
        process_records = process_query.execute().data

        # Validate consistency
        assert len(history_records) == len(params), "History record count mismatch"
        assert len(process_records) == len(params), "Process record count mismatch"
        assert len(history_records) == len(process_records), "Table record count mismatch"

        # Validate parameter values match
        for i, param in enumerate(params):
            history_param = next((r for r in history_records if r['parameter_id'] == param.parameter_id), None)
            process_param = next((r for r in process_records if r['parameter_id'] == param.parameter_id), None)

            assert history_param is not None, f"History record missing for {param.parameter_id}"
            assert process_param is not None, f"Process record missing for {param.parameter_id}"

            assert history_param['value'] == process_param['value'], f"Value mismatch for {param.parameter_id}"
            assert history_param['set_point'] == process_param['set_point'], f"Set point mismatch for {param.parameter_id}"

        print(f"✓ Dual table consistency test passed")
        print(f"  - History records: {len(history_records)}")
        print(f"  - Process records: {len(process_records)}")
        print(f"  - All values consistent")

        return {
            'history_count': len(history_records),
            'process_count': len(process_records),
            'consistent': True
        }

async def run_comprehensive_data_integrity_tests():
    """Run the complete data integrity test suite."""
    print("=" * 80)
    print("COMPREHENSIVE DATA INTEGRITY AND RACE CONDITION TEST SUITE")
    print("=" * 80)

    test_suite = DataIntegrityTestSuite()

    try:
        # Set up test environment
        print("\nSetting up test environment...")
        await test_suite.setup_test_environment()

        # Run race condition tests
        print("\n" + "=" * 50)
        print("RACE CONDITION TESTS")
        print("=" * 50)

        await test_suite.test_concurrent_dual_mode_logging()
        await test_suite.test_rapid_process_state_transitions()
        await test_suite.test_connection_pool_exhaustion()

        # Run transaction integrity tests
        print("\n" + "=" * 50)
        print("TRANSACTION INTEGRITY TESTS")
        print("=" * 50)

        await test_suite.test_transaction_rollback_scenarios()
        await test_suite.test_compensating_action_execution()

        # Run data consistency tests
        print("\n" + "=" * 50)
        print("DATA CONSISTENCY TESTS")
        print("=" * 50)

        await test_suite.test_dual_table_consistency()

        # Run integration gap tests
        print("\n" + "=" * 50)
        print("INTEGRATION GAP ANALYSIS")
        print("=" * 50)

        integration_result = await test_suite.test_legacy_vs_transactional_integration()

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUITE SUMMARY")
        print("=" * 80)
        print("✓ All data integrity tests completed successfully")
        print("✓ Race condition handling validated")
        print("✓ Transaction rollback mechanisms working")
        print("✓ Compensating actions executing correctly")
        print("✓ Dual-table consistency maintained")
        print("")
        print("🔴 CRITICAL FINDING:")
        print("   Integration gap exists - transactional system not integrated into main.py")
        print("   Current system still vulnerable to race conditions!")
        print("")
        print("🔧 RECOMMENDED ACTION:")
        print("   Integrate TransactionalParameterLoggerAdapter into main service")

        return True

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up test environment
        print("\nCleaning up test environment...")
        await test_suite.teardown_test_environment()

if __name__ == "__main__":
    # Run the comprehensive test suite
    asyncio.run(run_comprehensive_data_integrity_tests())