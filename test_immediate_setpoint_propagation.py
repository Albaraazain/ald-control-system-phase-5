#!/usr/bin/env python3
"""
Test immediate setpoint propagation to parameter_readings.

This script verifies the optimization:
- Updates setpoint from 10 ? 11 via parameter_control_commands
- Verifies it appears in parameter_readings within 1 second
- Pattern: Update setpoint ? Immediately insert to parameter_readings ? Return success
"""
import asyncio
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def find_test_parameter():
    """Find a writable float parameter to test with."""
    print("?? Finding a writable float parameter...")
    result = supabase.table('component_parameters_full').select(
        'id, parameter_name, component_name, write_modbus_address, data_type'
    ).eq('is_writable', True).eq('data_type', 'float').not_.is_('write_modbus_address', 'null').limit(1).execute()
    
    if not result.data:
        print("? No writable float parameters found")
        return None
    
    param = result.data[0]
    param_id = param['id']
    param_name = f"{param['component_name']}.{param['parameter_name']}"
    
    print(f"? Selected parameter: {param_name} (ID: {param_id})")
    return param_id, param_name


async def create_setpoint_command(parameter_id: str, target_value: float):
    """Create a parameter_control_command to update setpoint."""
    print(f"\n?? Creating parameter_control_command: setpoint ? {target_value}")
    
    # Get parameter name for the command
    param_result = supabase.table('component_parameters_full').select(
        'parameter_name'
    ).eq('id', parameter_id).execute()
    
    if not param_result.data:
        print(f"? Parameter {parameter_id} not found")
        return None
    
    parameter_name = param_result.data[0]['parameter_name']
    
    # Create command
    result = supabase.table('parameter_control_commands').insert({
        'parameter_name': parameter_name,
        'component_parameter_id': parameter_id,
        'target_value': target_value,
        'machine_id': os.getenv('MACHINE_ID', 'default')
    }).execute()
    
    if result.data:
        command_id = result.data[0]['id']
        print(f"? Created command ID: {command_id}")
        return command_id
    else:
        print("? Failed to create command")
        return None


async def wait_for_command_completion(command_id: str, timeout_seconds: float = 5.0):
    """Wait for command to complete."""
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        result = supabase.table('parameter_control_commands').select(
            'completed_at, error_message'
        ).eq('id', command_id).execute()
        
        if result.data and result.data[0]['completed_at']:
            if result.data[0]['error_message']:
                print(f"? Command failed: {result.data[0]['error_message']}")
                return False
            else:
                print(f"? Command completed successfully")
                return True
        
        await asyncio.sleep(0.2)
    
    print(f"??  Command did not complete within {timeout_seconds}s timeout")
    return False


async def check_parameter_readings(parameter_id: str, expected_value: float, time_window_seconds: float = 2.0):
    """
    Check if the parameter value appears in parameter_readings within the time window.
    
    Args:
        parameter_id: The parameter ID to check
        expected_value: The expected value (should be close to this)
        time_window_seconds: Time window to search within (default 2 seconds)
    
    Returns:
        tuple: (found: bool, timestamp: str, actual_value: float)
    """
    from src.parameter_wide_table_mapping import PARAMETER_TO_COLUMN_MAP
    
    # Get column name for this parameter
    column_name = PARAMETER_TO_COLUMN_MAP.get(parameter_id)
    if not column_name:
        print(f"? Parameter {parameter_id} not in wide table mapping")
        return False, None, None
    
    print(f"\n?? Checking parameter_readings for column {column_name}...")
    
    # Query for recent parameter_readings within the time window
    cutoff_time = datetime.utcnow().isoformat()
    cutoff_earlier = (datetime.utcnow().timestamp() - time_window_seconds)
    
    print(f"   Searching for readings in the last {time_window_seconds} seconds...")
    
    # Query parameter_readings - we need to check the specific column
    # Since Supabase doesn't support dynamic column selection easily, we'll query all recent rows
    result = supabase.rpc(
        'get_recent_parameter_readings',
        params={
            'p_cutoff_time': cutoff_earlier
        }
    ).execute() if hasattr(supabase.rpc, '__call__') else None
    
    # Alternative: Direct table query (may need to adjust based on your schema)
    # For now, let's query the most recent row
    try:
        # Query using timestamp filter - get the most recent row
        result = supabase.table('parameter_readings').select(
            '*'
        ).order('timestamp', desc=True).limit(5).execute()
        
        if result.data:
            print(f"   Found {len(result.data)} recent rows")
            
            # Check each row for our parameter value
            for row in result.data:
                row_time = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                time_diff = (datetime.utcnow().replace(tzinfo=row_time.tzinfo) - row_time).total_seconds()
                
                if 0 <= time_diff <= time_window_seconds:
                    if column_name in row and row[column_name] is not None:
                        actual_value = float(row[column_name])
                        value_diff = abs(actual_value - expected_value)
                        
                        print(f"   ? Found value {actual_value} (expected {expected_value}, diff: {value_diff:.4f}) at {row['timestamp']}")
                        print(f"      Time since insert: {time_diff:.3f}s")
                        
                        if value_diff < 0.1:  # Allow small tolerance
                            return True, row['timestamp'], actual_value
            
            print(f"   ??  Found recent rows but parameter value not matching within tolerance")
        else:
            print(f"   ??  No recent parameter_readings found")
    
    except Exception as e:
        print(f"   ? Error querying parameter_readings: {e}")
    
    return False, None, None


async def main():
    """Test immediate setpoint propagation."""
    print("=" * 80)
    print("IMMEDIATE SETPOINT PROPAGATION TEST")
    print("=" * 80)
    print("\nTesting: Setpoint 10 ? 11 update with immediate parameter_readings insert")
    print("Pattern: Update setpoint ? Immediately insert to parameter_readings ? Return success\n")
    
    # Find a test parameter
    param_info = await find_test_parameter()
    if not param_info:
        return
    
    parameter_id, param_name = param_info
    
    # Step 1: Set initial setpoint to 10
    print("\n" + "=" * 80)
    print("STEP 1: Set setpoint to 10")
    print("=" * 80)
    command_id_10 = await create_setpoint_command(parameter_id, 10.0)
    if not command_id_10:
        return
    
    success = await wait_for_command_completion(command_id_10, timeout_seconds=5.0)
    if not success:
        print("? Initial setpoint command failed")
        return
    
    # Verify it's in parameter_readings
    found, timestamp, value = await check_parameter_readings(parameter_id, 10.0, time_window_seconds=3.0)
    if found:
        print(f"? Initial setpoint 10.0 confirmed in parameter_readings")
    else:
        print(f"??  Initial setpoint 10.0 not found in parameter_readings (may still be propagating)")
    
    # Wait a moment before next update
    print("\n? Waiting 1 second before next update...")
    await asyncio.sleep(1.0)
    
    # Step 2: Update setpoint to 11
    print("\n" + "=" * 80)
    print("STEP 2: Update setpoint to 11 (TEST: Should appear within 1 second)")
    print("=" * 80)
    start_time = time.time()
    
    command_id_11 = await create_setpoint_command(parameter_id, 11.0)
    if not command_id_11:
        return
    
    success = await wait_for_command_completion(command_id_11, timeout_seconds=5.0)
    if not success:
        print("? Setpoint update command failed")
        return
    
    command_time = time.time() - start_time
    print(f"\n??  Command completed in {command_time:.3f}s")
    
    # Step 3: Immediately check parameter_readings (within 1 second)
    print("\n" + "=" * 80)
    print("STEP 3: Verify immediate propagation to parameter_readings")
    print("=" * 80)
    
    # Check within 1 second window
    found, timestamp, actual_value = await check_parameter_readings(parameter_id, 11.0, time_window_seconds=1.0)
    
    total_time = time.time() - start_time
    print(f"\n??  Total time from command creation: {total_time:.3f}s")
    
    if found:
        print("\n" + "=" * 80)
        print("? TEST PASSED: Setpoint 11.0 found in parameter_readings within 1 second!")
        print("=" * 80)
        print(f"   Actual value: {actual_value}")
        print(f"   Expected: 11.0")
        print(f"   Timestamp: {timestamp}")
        print(f"   Propagation time: < 1 second ?")
    else:
        print("\n" + "=" * 80)
        print("? TEST FAILED: Setpoint 11.0 NOT found in parameter_readings within 1 second")
        print("=" * 80)
        print("   The optimization may not be working correctly.")
        print("   Check:")
        print("   1. Is parameter_control_listener running?")
        print("   2. Check logs for immediate insert errors")
        print("   3. Verify RPC function insert_parameter_reading_wide exists")


if __name__ == "__main__":
    asyncio.run(main())
