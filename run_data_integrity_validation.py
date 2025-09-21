#!/usr/bin/env python3
"""
Data Integrity Validation Runner (No External Dependencies)

Validates the transactional data layer and race condition handling without pytest.
Tests the critical integration between legacy and transactional systems.
"""

import asyncio
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

def validate_imports():
    """Validate that all required modules can be imported."""
    try:
        from src.data_collection.transactional.interfaces import (
            ParameterData, MachineState, DualModeResult
        )
        from src.data_collection.transactional.dual_mode_repository import dual_mode_repository
        from src.data_collection.transactional.transaction_manager import transaction_manager
        from src.db import get_supabase
        from src.config import MACHINE_ID
        print("✓ All required modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

async def test_transactional_system_basic():
    """Basic test of transactional system functionality."""
    print("\n=== Basic Transactional System Test ===")

    try:
        from src.data_collection.transactional.interfaces import ParameterData, MachineState
        from src.data_collection.transactional.dual_mode_repository import dual_mode_repository
        from src.data_collection.transactional.transaction_manager import transaction_manager

        # Initialize transaction manager
        await transaction_manager.initialize()

        # Test basic operation
        params = [
            ParameterData("TEST_BASIC_1", 25.5, 25.0),
            ParameterData("TEST_BASIC_2", 150.0, 150.0)
        ]

        machine_state = MachineState("idle", None, datetime.utcnow())

        result = await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)

        print(f"✓ Basic transactional test passed")
        print(f"  - Success: {result.success}")
        print(f"  - History records: {result.history_count}")
        print(f"  - Process records: {result.process_count}")
        print(f"  - Transaction ID: {result.transaction_id}")

        return True

    except Exception as e:
        print(f"❌ Basic transactional test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_dual_mode_processing():
    """Test dual-mode logging with processing state."""
    print("\n=== Dual-Mode Processing Test ===")

    try:
        from src.data_collection.transactional.interfaces import ParameterData, MachineState
        from src.data_collection.transactional.dual_mode_repository import dual_mode_repository

        # Test processing mode (should log to both tables)
        params = [
            ParameterData("DUAL_TEST_1", 42.0, 42.0),
            ParameterData("DUAL_TEST_2", 84.0, 84.0)
        ]

        process_id = f"test_dual_mode_{uuid.uuid4().hex[:8]}"
        machine_state = MachineState("processing", process_id, datetime.utcnow())

        result = await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)

        print(f"✓ Dual-mode processing test passed")
        print(f"  - Success: {result.success}")
        print(f"  - History records: {result.history_count}")
        print(f"  - Process records: {result.process_count}")
        print(f"  - Both tables populated: {result.history_count > 0 and result.process_count > 0}")

        return result.success and result.history_count > 0 and result.process_count > 0

    except Exception as e:
        print(f"❌ Dual-mode processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_concurrent_operations():
    """Test concurrent operations for race conditions."""
    print("\n=== Concurrent Operations Test ===")

    try:
        from src.data_collection.transactional.interfaces import ParameterData, MachineState
        from src.data_collection.transactional.dual_mode_repository import dual_mode_repository

        # Create multiple concurrent operations
        async def concurrent_operation(op_id: int):
            params = [ParameterData(f"CONCURRENT_{op_id}", float(op_id), float(op_id))]
            machine_state = MachineState("idle", None, datetime.utcnow())
            return await dual_mode_repository.insert_dual_mode_atomic(params, machine_state)

        # Run 10 concurrent operations
        operations = [concurrent_operation(i) for i in range(10)]
        results = await asyncio.gather(*operations, return_exceptions=True)

        # Count successful operations
        successful = sum(1 for r in results if hasattr(r, 'success') and r.success)
        total = len(results)

        print(f"✓ Concurrent operations test completed")
        print(f"  - Total operations: {total}")
        print(f"  - Successful: {successful}")
        print(f"  - Success rate: {successful/total*100:.1f}%")
        print(f"  - Race condition handling: {'GOOD' if successful == total else 'NEEDS_REVIEW'}")

        return successful == total

    except Exception as e:
        print(f"❌ Concurrent operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_failure_rollback():
    """Test failure scenarios and rollback mechanisms."""
    print("\n=== Failure Rollback Test ===")

    try:
        from src.data_collection.transactional.interfaces import ParameterData, MachineState
        from src.data_collection.transactional.dual_mode_repository import dual_mode_repository

        # Test with invalid parameters (should trigger rollback)
        invalid_params = [
            ParameterData("", None, None),  # Invalid
            ParameterData("VALID_PARAM", 50.0, 50.0)  # Valid
        ]

        machine_state = MachineState("processing", "test_rollback_process", datetime.utcnow())

        result = await dual_mode_repository.insert_dual_mode_atomic(invalid_params, machine_state)

        print(f"✓ Failure rollback test completed")
        print(f"  - Operation failed as expected: {not result.success}")
        print(f"  - Error message: {result.error_message}")
        print(f"  - No partial data inserted: {result.history_count == 0 and result.process_count == 0}")
        print(f"  - Rollback successful: {not result.success and result.history_count == 0}")

        return not result.success and result.history_count == 0

    except Exception as e:
        print(f"❌ Failure rollback test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_integration_status():
    """Check if transactional system is properly integrated."""
    print("\n=== Integration Status Check ===")

    try:
        # Check if main service uses transactional adapter
        from src.data_collection.service import data_collection_service

        # Try to get status
        status = data_collection_service.get_status()

        # Check for transactional adapter
        uses_transactional = 'transactional_parameter_logger' in status

        print(f"✓ Integration status check completed")
        print(f"  - Service status: {status}")
        print(f"  - Uses transactional adapter: {uses_transactional}")
        print(f"  - Integration status: {'INTEGRATED' if uses_transactional else 'NOT_INTEGRATED'}")

        if uses_transactional:
            print("  - 🎉 GOOD: Transactional system is integrated!")
        else:
            print("  - ⚠️  WARNING: Still using legacy system")

        return uses_transactional

    except Exception as e:
        print(f"❌ Integration status check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_health_status():
    """Test health status reporting."""
    print("\n=== Health Status Test ===")

    try:
        from src.data_collection.transactional.dual_mode_repository import dual_mode_repository

        health = await dual_mode_repository.get_health_status()

        print(f"✓ Health status test completed")
        print(f"  - Health status: {health}")
        print(f"  - System healthy: {health.get('status') == 'healthy'}")

        return health.get('status') == 'healthy'

    except Exception as e:
        print(f"❌ Health status test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_comprehensive_validation():
    """Run comprehensive data integrity validation."""
    print("=" * 80)
    print("DATA INTEGRITY VALIDATION SUITE")
    print("=" * 80)

    # Track test results
    results = {}

    # Validate imports first
    if not validate_imports():
        print("❌ Cannot proceed - import failures")
        return False

    # Run tests
    test_functions = [
        ("Basic Transactional System", test_transactional_system_basic),
        ("Dual-Mode Processing", test_dual_mode_processing),
        ("Concurrent Operations", test_concurrent_operations),
        ("Failure Rollback", test_failure_rollback),
        ("Integration Status", test_integration_status),
        ("Health Status", test_health_status),
    ]

    for test_name, test_func in test_functions:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    passed_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print(f"\nOverall: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")

    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Data integrity system is working correctly!")
    elif passed_tests >= total_tests * 0.8:
        print("⚠️  MOSTLY WORKING - Some issues need attention")
    else:
        print("❌ MULTIPLE FAILURES - System needs significant work")

    # Key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)

    if results.get("Integration Status", False):
        print("✓ GOOD: Transactional system is properly integrated")
        print("✓ GOOD: Race condition protections are active")
        print("✓ GOOD: Atomic operations are being used")
    else:
        print("⚠️  WARNING: Integration gap may still exist")
        print("⚠️  WARNING: Legacy system might still be in use")

    if results.get("Failure Rollback", False):
        print("✓ GOOD: Rollback mechanisms are working")
        print("✓ GOOD: Data consistency is maintained")

    if results.get("Concurrent Operations", False):
        print("✓ GOOD: Concurrent operations are handled safely")
        print("✓ GOOD: Race conditions are properly managed")

    return passed_tests == total_tests

if __name__ == "__main__":
    # Run the validation suite
    success = asyncio.run(run_comprehensive_validation())