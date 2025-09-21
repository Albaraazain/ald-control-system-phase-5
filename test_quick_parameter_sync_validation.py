#!/usr/bin/env python3
"""
Quick parameter synchronization validation without external dependencies.
Tests the critical findings from agent coordination.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def validate_dual_mode_repository_enhancement():
    """Validate the dual-mode repository enhancement for component_parameters."""
    logger.info("🔍 Testing dual-mode repository component_parameters synchronization")

    try:
        from src.data_collection.transactional import transactional_logger

        # Initialize transactional logger
        if not transactional_logger._is_initialized:
            await transactional_logger.initialize()

        # Test atomic operation
        test_params = {'test_param_1': 42.0}
        result = await transactional_logger.log_parameters_atomic(test_params)

        # Check for component_updates_count (new field from implementer)
        has_component_updates = hasattr(result, 'component_updates_count')

        print(f"✅ Dual-mode repository enhancement: {'FOUND' if has_component_updates else 'NOT FOUND'}")
        print(f"   - Atomic operation success: {result.success}")
        print(f"   - Component updates count: {getattr(result, 'component_updates_count', 'N/A')}")
        print(f"   - Transaction ID: {result.transaction_id}")

        return has_component_updates and result.success

    except Exception as e:
        print(f"❌ Error testing dual-mode repository: {e}")
        return False


async def validate_transactional_adapter_integration():
    """Validate transactional adapter integration."""
    logger.info("🔍 Testing transactional adapter integration")

    try:
        from src.data_collection.transactional_adapter import transactional_parameter_logger_adapter

        # Test health status
        health_status = await transactional_parameter_logger_adapter.get_health_status()

        # Test atomic operation
        atomic_test = await transactional_parameter_logger_adapter.test_atomic_operation()

        is_healthy = health_status.get('overall_status') == 'healthy'
        atomic_works = atomic_test.get('test_successful', False)

        print(f"✅ Transactional adapter integration:")
        print(f"   - Health status: {health_status.get('overall_status', 'unknown')}")
        print(f"   - Atomic test: {'PASS' if atomic_works else 'FAIL'}")
        print(f"   - Component updates: {atomic_test.get('component_updates_count', 'N/A')}")

        return is_healthy and atomic_works

    except Exception as e:
        print(f"❌ Error testing transactional adapter: {e}")
        return False


async def validate_parameter_write_synchronization():
    """Validate parameter write synchronization."""
    logger.info("🔍 Testing parameter write synchronization")

    try:
        from src.db import get_supabase
        from src.config import MACHINE_ID

        supabase = get_supabase()

        # Get a test parameter
        param_result = supabase.table('component_parameters') \
            .select('id, min_value, max_value, set_value') \
            .eq('machine_id', MACHINE_ID) \
            .not_.is_('min_value', 'null') \
            .not_.is_('max_value', 'null') \
            .limit(1) \
            .execute()

        if not param_result.data:
            print("⚠️  No parameters available for testing")
            return False

        param = param_result.data[0]
        param_id = param['id']
        test_value = (param['min_value'] + param['max_value']) / 2
        initial_set_value = param['set_value']

        # Test parameter write using the parameter step function
        from src.step_flow.parameter_step import set_parameter_value

        await set_parameter_value(param_id, test_value)

        # Check if set_value was updated
        updated_result = supabase.table('component_parameters') \
            .select('set_value, updated_at') \
            .eq('id', param_id) \
            .single() \
            .execute()

        final_set_value = updated_result.data['set_value']
        set_value_updated = final_set_value == test_value

        print(f"✅ Parameter write synchronization:")
        print(f"   - Parameter ID: {param_id}")
        print(f"   - Test value: {test_value}")
        print(f"   - Initial set_value: {initial_set_value}")
        print(f"   - Final set_value: {final_set_value}")
        print(f"   - Set value updated: {'YES' if set_value_updated else 'NO'}")

        return set_value_updated

    except Exception as e:
        print(f"❌ Error testing parameter write synchronization: {e}")
        return False


async def validate_component_parameters_table_structure():
    """Validate component_parameters table has required columns."""
    logger.info("🔍 Validating component_parameters table structure")

    try:
        from src.db import get_supabase

        supabase = get_supabase()

        # Try to select current_value and set_value columns
        result = supabase.table('component_parameters') \
            .select('id, current_value, set_value, updated_at') \
            .limit(1) \
            .execute()

        has_required_columns = bool(result.data)

        if has_required_columns:
            sample_param = result.data[0]
            print(f"✅ Component parameters table structure:")
            print(f"   - Has current_value column: YES")
            print(f"   - Has set_value column: YES")
            print(f"   - Sample current_value: {sample_param.get('current_value', 'NULL')}")
            print(f"   - Sample set_value: {sample_param.get('set_value', 'NULL')}")
        else:
            print("❌ Component parameters table structure: MISSING COLUMNS")

        return has_required_columns

    except Exception as e:
        print(f"❌ Error validating table structure: {e}")
        return False


async def main():
    """Run quick validation tests."""
    print("\n" + "="*80)
    print("🧪 QUICK PARAMETER SYNCHRONIZATION VALIDATION")
    print("="*80)
    print(f"🕒 Test started: {datetime.now(timezone.utc).isoformat()}")

    test_results = {}

    # Run validation tests
    test_results['table_structure'] = await validate_component_parameters_table_structure()
    test_results['dual_mode_repository'] = await validate_dual_mode_repository_enhancement()
    test_results['transactional_adapter'] = await validate_transactional_adapter_integration()
    test_results['parameter_write_sync'] = await validate_parameter_write_synchronization()

    # Calculate results
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    pass_rate = passed_tests / total_tests if total_tests > 0 else 0

    print("\n" + "="*80)
    print("📊 VALIDATION SUMMARY")
    print("="*80)
    print(f"📈 Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {total_tests - passed_tests}")
    print(f"📊 Pass Rate: {pass_rate:.1%}")

    if pass_rate >= 0.75:
        print("\n🎉 VALIDATION STATUS: EXCELLENT - Implementation on track!")
    elif pass_rate >= 0.5:
        print("\n⚠️  VALIDATION STATUS: GOOD - Some issues need attention")
    else:
        print("\n🚨 VALIDATION STATUS: NEEDS IMPROVEMENT - Critical issues found")

    print("\n" + "="*80)
    print("🔍 DETAILED TEST RESULTS:")
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")

    print("="*80)

    return test_results


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Validation execution failed: {e}")
        sys.exit(1)