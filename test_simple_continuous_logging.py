#!/usr/bin/env python3
"""
Simple test runner for continuous parameter logging validation.
Quick tests to verify the system is working correctly.

Usage:
    python test_simple_continuous_logging.py
"""

import asyncio
import sys
import time
from datetime import datetime
from src.log_setup import logger
from src.config import MACHINE_ID
from src.db import get_supabase


async def test_basic_functionality():
    """Quick test to verify continuous parameter logging is working."""
    print("🧪 Testing Basic Continuous Parameter Logging Functionality\n")

    supabase = get_supabase()

    # Test 1: Check if tables exist and are accessible
    print("1. Testing database table accessibility...")
    try:
        # Test parameter_value_history table
        pvh_result = supabase.table('parameter_value_history').select('*').limit(1).execute()
        print("   ✅ parameter_value_history table accessible")

        # Test process_data_points table
        pdp_result = supabase.table('process_data_points').select('*').limit(1).execute()
        print("   ✅ process_data_points table accessible")

    except Exception as e:
        print(f"   ❌ Database access failed: {str(e)}")
        return False

    # Test 2: Check for recent parameter logging activity
    print("\n2. Testing for recent parameter logging activity...")
    try:
        # Get count before waiting
        before_result = supabase.table('parameter_value_history').select('id', count='exact').execute()
        before_count = before_result.count or 0
        print(f"   📊 Current parameter_value_history records: {before_count}")

        # Wait for logging cycles (5 seconds should be enough for several 1-second intervals)
        print("   ⏳ Waiting 5 seconds for logging activity...")
        await asyncio.sleep(5)

        # Get count after waiting
        after_result = supabase.table('parameter_value_history').select('id', count='exact').execute()
        after_count = after_result.count or 0
        print(f"   📊 New parameter_value_history records: {after_count}")

        new_records = after_count - before_count
        print(f"   📈 Records added in 5 seconds: {new_records}")

        if new_records >= 3:  # Should have at least 3 records in 5 seconds (1 per second)
            print("   ✅ Parameter logging is active and working")
            return True
        else:
            print("   ⚠️  Low or no logging activity detected")
            return False

    except Exception as e:
        print(f"   ❌ Parameter logging test failed: {str(e)}")
        return False


async def test_data_quality():
    """Test the quality of logged parameter data."""
    print("\n3. Testing parameter data quality...")

    supabase = get_supabase()

    try:
        # Get recent records
        result = supabase.table('parameter_value_history').select('*').order('timestamp', desc=True).limit(10).execute()
        records = result.data or []

        if not records:
            print("   ⚠️  No recent records found to test")
            return False

        print(f"   📋 Analyzing {len(records)} recent records...")

        # Check data quality
        issues = []
        for i, record in enumerate(records):
            if not record.get('parameter_id'):
                issues.append(f"Record {i+1}: Missing parameter_id")
            if record.get('value') is None:
                issues.append(f"Record {i+1}: Missing value")
            if not record.get('timestamp'):
                issues.append(f"Record {i+1}: Missing timestamp")

        if issues:
            print("   ❌ Data quality issues found:")
            for issue in issues:
                print(f"      • {issue}")
            return False
        else:
            print("   ✅ All records have required fields")

        # Check timestamp recency
        latest_record = records[0]
        latest_time = datetime.fromisoformat(latest_record['timestamp'].replace('Z', '+00:00'))
        time_diff = (datetime.utcnow().replace(tzinfo=latest_time.tzinfo) - latest_time).total_seconds()

        if time_diff < 10:  # Latest record should be within 10 seconds
            print(f"   ✅ Latest record is recent ({time_diff:.1f} seconds ago)")
            return True
        else:
            print(f"   ⚠️  Latest record is old ({time_diff:.1f} seconds ago)")
            return False

    except Exception as e:
        print(f"   ❌ Data quality test failed: {str(e)}")
        return False


async def test_timing_consistency():
    """Test timing consistency of parameter logging."""
    print("\n4. Testing timing consistency...")

    supabase = get_supabase()

    try:
        # Get recent records ordered by timestamp
        result = supabase.table('parameter_value_history').select('timestamp').order('timestamp', desc=True).limit(10).execute()
        records = result.data or []

        if len(records) < 3:
            print("   ⚠️  Need at least 3 records to test timing")
            return False

        # Calculate intervals between consecutive records
        intervals = []
        sorted_records = sorted(records, key=lambda x: x['timestamp'])

        for i in range(1, len(sorted_records)):
            prev_time = datetime.fromisoformat(sorted_records[i-1]['timestamp'].replace('Z', '+00:00'))
            curr_time = datetime.fromisoformat(sorted_records[i]['timestamp'].replace('Z', '+00:00'))
            interval = (curr_time - prev_time).total_seconds()
            intervals.append(interval)

        if not intervals:
            print("   ⚠️  Could not calculate intervals")
            return False

        avg_interval = sum(intervals) / len(intervals)
        print(f"   📊 Average interval between records: {avg_interval:.2f} seconds")

        # Check if close to expected 1-second interval
        expected = 1.0
        tolerance = 0.5  # ±0.5 seconds

        if abs(avg_interval - expected) <= tolerance:
            print(f"   ✅ Timing is consistent (expected: {expected}s, tolerance: ±{tolerance}s)")
            return True
        else:
            print(f"   ⚠️  Timing inconsistency detected (expected: {expected}s ± {tolerance}s)")
            return False

    except Exception as e:
        print(f"   ❌ Timing consistency test failed: {str(e)}")
        return False


async def test_process_mode_detection():
    """Test if the system can detect and log during process execution."""
    print("\n5. Testing process mode detection...")

    supabase = get_supabase()

    try:
        # Check for any recent process executions
        result = supabase.table('process_executions').select('*').eq('machine_id', MACHINE_ID).order('created_at', desc=True).limit(5).execute()
        processes = result.data or []

        if not processes:
            print("   ℹ️  No recent process executions found to test")
            print("   💡 Process mode testing requires an active or recent process")
            return True  # Not a failure, just no data to test

        # Check if any process has corresponding data points
        recent_process = processes[0]
        process_id = recent_process['id']

        pdp_result = supabase.table('process_data_points').select('*').eq('process_id', process_id).limit(5).execute()
        data_points = pdp_result.data or []

        if data_points:
            print(f"   ✅ Found {len(data_points)} data points for recent process {process_id}")
            print("   ✅ Process mode detection and logging appears to be working")
            return True
        else:
            print(f"   ⚠️  No data points found for recent process {process_id}")
            print("   💡 This may indicate process mode logging is not active")
            return False

    except Exception as e:
        print(f"   ❌ Process mode detection test failed: {str(e)}")
        return False


async def main():
    """Run all simple tests."""
    print("🚀 Simple Continuous Parameter Logging Validation\n")
    print("="*60)

    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Data Quality", test_data_quality),
        ("Timing Consistency", test_timing_consistency),
        ("Process Mode Detection", test_process_mode_detection)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append(result)
            status = "✅ PASSED" if result else "⚠️  ISSUES"
            print(f"\n{status}: {test_name}")
        except Exception as e:
            print(f"\n❌ ERROR: {test_name} - {str(e)}")
            results.append(False)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    passed = sum(results)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! Continuous parameter logging is working correctly.")
        return 0
    elif passed > total // 2:
        print("⚠️  Some issues detected. System is partially working.")
        return 1
    else:
        print("❌ Major issues detected. System may not be working correctly.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite crashed: {str(e)}")
        sys.exit(1)