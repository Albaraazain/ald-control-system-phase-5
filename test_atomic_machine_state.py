#!/usr/bin/env python3
"""
Test script for atomic machine state operations

This test validates that the atomic transaction implementation
correctly eliminates race conditions between machines and machine_state tables.
"""

import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from src.config import MACHINE_ID
from src.db import get_supabase
from src.utils.atomic_machine_state import (
    atomic_complete_machine_state,
    atomic_error_machine_state,
    atomic_processing_machine_state
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_machine_state_consistency():
    """
    Check consistency between machines and machine_state tables.
    Returns tuple (machines_status, machine_state_current_state, is_consistent)
    """
    supabase = get_supabase()

    # Get machines table status
    machine_result = supabase.table('machines').select('status, current_process_id').eq('id', MACHINE_ID).single().execute()
    machine_status = machine_result.data['status'] if machine_result.data else None
    machine_process_id = machine_result.data['current_process_id'] if machine_result.data else None

    # Get machine_state table status
    state_result = supabase.table('machine_state').select('current_state, process_id').eq('machine_id', MACHINE_ID).single().execute()
    state_current_state = state_result.data['current_state'] if state_result.data else None
    state_process_id = state_result.data['process_id'] if state_result.data else None

    # Check consistency
    status_consistent = machine_status == state_current_state
    process_id_consistent = machine_process_id == state_process_id
    is_consistent = status_consistent and process_id_consistent

    return machine_status, state_current_state, machine_process_id, state_process_id, is_consistent


def test_atomic_completion():
    """Test atomic completion operation."""
    logger.info("Testing atomic completion operation...")

    try:
        # Get initial state
        initial_state = get_machine_state_consistency()
        logger.info(f"Initial state: {initial_state}")

        # Perform atomic completion
        result = atomic_complete_machine_state(MACHINE_ID)
        logger.info(f"Atomic completion result: {result}")

        # Check final state
        final_state = get_machine_state_consistency()
        logger.info(f"Final state: {final_state}")

        # Validate consistency
        if final_state[4]:  # is_consistent
            logger.info("✅ PASS: Atomic completion maintains consistency")
            return True
        else:
            logger.error("❌ FAIL: Atomic completion caused inconsistency")
            return False

    except Exception as e:
        logger.error(f"❌ FAIL: Atomic completion raised exception: {e}")
        return False


def test_atomic_error():
    """Test atomic error operation."""
    logger.info("Testing atomic error operation...")

    try:
        # Get initial state
        initial_state = get_machine_state_consistency()
        logger.info(f"Initial state: {initial_state}")

        # Perform atomic error
        result = atomic_error_machine_state(MACHINE_ID, "Test error message")
        logger.info(f"Atomic error result: {result}")

        # Check final state
        final_state = get_machine_state_consistency()
        logger.info(f"Final state: {final_state}")

        # Validate consistency and error state
        if final_state[4] and final_state[0] == 'error' and final_state[1] == 'error':
            logger.info("✅ PASS: Atomic error maintains consistency and sets error state")
            return True
        else:
            logger.error("❌ FAIL: Atomic error caused inconsistency or wrong state")
            return False

    except Exception as e:
        logger.error(f"❌ FAIL: Atomic error raised exception: {e}")
        return False


def test_atomic_processing():
    """Test atomic processing operation."""
    logger.info("Testing atomic processing operation...")

    test_process_id = "test-process-12345"

    try:
        # Get initial state
        initial_state = get_machine_state_consistency()
        logger.info(f"Initial state: {initial_state}")

        # Perform atomic processing
        result = atomic_processing_machine_state(MACHINE_ID, test_process_id)
        logger.info(f"Atomic processing result: {result}")

        # Check final state
        final_state = get_machine_state_consistency()
        logger.info(f"Final state: {final_state}")

        # Validate consistency and processing state
        expected_status = 'processing'
        if (final_state[4] and
            final_state[0] == expected_status and
            final_state[1] == expected_status and
            final_state[2] == test_process_id and
            final_state[3] == test_process_id):
            logger.info("✅ PASS: Atomic processing maintains consistency and sets processing state")
            return True
        else:
            logger.error("❌ FAIL: Atomic processing caused inconsistency or wrong state")
            return False

    except Exception as e:
        logger.error(f"❌ FAIL: Atomic processing raised exception: {e}")
        return False


def test_concurrent_operations():
    """Test concurrent atomic operations to verify no race conditions."""
    logger.info("Testing concurrent atomic operations...")

    results = []

    def atomic_operation_worker(operation_id):
        """Worker function for concurrent testing."""
        try:
            if operation_id % 3 == 0:
                atomic_complete_machine_state(MACHINE_ID)
            elif operation_id % 3 == 1:
                atomic_error_machine_state(MACHINE_ID, f"Concurrent test error {operation_id}")
            else:
                atomic_processing_machine_state(MACHINE_ID, f"concurrent-process-{operation_id}")

            # Check consistency after operation
            state = get_machine_state_consistency()
            return state[4]  # is_consistent

        except Exception as e:
            logger.error(f"Concurrent operation {operation_id} failed: {e}")
            return False

    # Run concurrent operations
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(atomic_operation_worker, i) for i in range(20)]
        results = [future.result() for future in futures]

    # Check results
    all_consistent = all(results)
    successful_operations = sum(results)

    logger.info(f"Concurrent operations: {successful_operations}/{len(results)} maintained consistency")

    if all_consistent:
        logger.info("✅ PASS: All concurrent operations maintained consistency")
        return True
    else:
        logger.error("❌ FAIL: Some concurrent operations caused inconsistency")
        return False


def test_migration_deployment():
    """Test that the migration can be deployed successfully."""
    logger.info("Testing migration deployment...")

    try:
        supabase = get_supabase()

        # Test if stored procedures exist by calling them
        result = supabase.rpc('atomic_complete_machine_state', {
            'p_machine_id': MACHINE_ID
        }).execute()

        if result.data:
            logger.info("✅ PASS: Stored procedures are deployed and accessible")
            return True
        else:
            logger.error("❌ FAIL: Stored procedures not accessible")
            return False

    except Exception as e:
        logger.error(f"❌ FAIL: Migration deployment test failed: {e}")
        return False


def main():
    """Run all atomic machine state tests."""
    logger.info("🚀 Starting atomic machine state test suite...")

    tests = [
        ("Migration Deployment", test_migration_deployment),
        ("Atomic Completion", test_atomic_completion),
        ("Atomic Error", test_atomic_error),
        ("Atomic Processing", test_atomic_processing),
        ("Concurrent Operations", test_concurrent_operations)
    ]

    results = []

    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))

        # Brief pause between tests
        time.sleep(1)

    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("="*50)

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\nTotal: {passed}/{len(results)} tests passed")

    if passed == len(results):
        logger.info("🎉 All tests passed! Atomic operations are working correctly.")
        return True
    else:
        logger.error("⚠️  Some tests failed. Review implementation before deployment.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)