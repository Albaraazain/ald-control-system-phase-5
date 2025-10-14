#!/usr/bin/env python3
"""
Test external setpoint change detection by Terminal 1.

This script:
1. Gets a writable parameter from the database
2. Reads its current set_value
3. Writes a new setpoint value directly to the PLC (simulating external change)
4. Waits for Terminal 1 to detect and synchronize it
5. Verifies the database was updated with the PLC value
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from plc.manager import PLCManager

load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def main():
    """Test external setpoint change detection."""
    print("=" * 80)
    print("EXTERNAL SETPOINT CHANGE DETECTION TEST")
    print("=" * 80)
    
    # Get PLC type from environment
    plc_type = os.getenv('PLC_TYPE', 'real')
    print(f"\n📋 PLC Type: {plc_type}")
    
    # Initialize PLC Manager
    print("\n🔧 Initializing PLC Manager...")
    plc_manager = PLCManager()
    await plc_manager.initialize(plc_type=plc_type)
    print("✅ PLC Manager initialized")
    
    # Find a writable temperature parameter (easier to test with float values)
    print("\n🔍 Finding a writable temperature parameter...")
    result = supabase.table('component_parameters_full').select(
        'id, parameter_name, component_name, set_value, write_modbus_address, data_type'
    ).eq('is_writable', True).eq('data_type', 'float').not_.is_('write_modbus_address', 'null').limit(1).execute()
    
    if not result.data:
        print("❌ No writable float parameters found")
        await plc_manager.disconnect()
        return
    
    param = result.data[0]
    param_id = param['id']
    param_name = f"{param['component_name']}.{param['parameter_name']}"
    original_setpoint = param['set_value'] or 0.0
    write_address = param['write_modbus_address']
    
    print(f"\n✅ Selected parameter: {param_name} (ID: {param_id})")
    print(f"   Current DB set_value: {original_setpoint}")
    print(f"   Write Modbus Address: {write_address}")
    
    # Calculate a new test setpoint (add 5.0 to current value)
    new_setpoint = original_setpoint + 5.0
    print(f"\n📝 New test setpoint: {new_setpoint}")
    
    # Write directly to PLC (simulating external change)
    print(f"\n⚡ Writing new setpoint to PLC at address {write_address}...")
    try:
        await plc_manager.write_parameter(param_id, new_setpoint)
        print(f"✅ Successfully wrote {new_setpoint} to PLC")
    except Exception as e:
        print(f"❌ Failed to write to PLC: {e}")
        await plc_manager.disconnect()
        return
    
    # Verify PLC has the new value
    print(f"\n🔍 Reading back from PLC to verify...")
    plc_value = await plc_manager.read_parameter(param_id)
    print(f"📊 PLC readback value: {plc_value}")
    
    if abs(plc_value - new_setpoint) > 0.01:
        print(f"⚠️  WARNING: PLC value {plc_value} doesn't match written value {new_setpoint}")
    else:
        print("✅ PLC write verified")
    
    # Wait for Terminal 1 to detect and synchronize (it runs every 1 second)
    print(f"\n⏳ Waiting 3 seconds for Terminal 1 to detect external change...")
    await asyncio.sleep(3)
    
    # Check if database was updated
    print(f"\n🔍 Checking database for updated set_value...")
    result = supabase.table('component_parameters').select(
        'set_value'
    ).eq('id', param_id).execute()
    
    db_setpoint = result.data[0]['set_value'] if result.data else None
    print(f"📊 Database set_value: {db_setpoint}")
    
    # Verify synchronization worked
    print(f"\n🎯 Verification:")
    print(f"   Original DB set_value: {original_setpoint}")
    print(f"   New PLC setpoint: {new_setpoint}")
    print(f"   Current DB set_value: {db_setpoint}")
    
    if db_setpoint and abs(db_setpoint - new_setpoint) < 0.01:
        print(f"\n✅ SUCCESS: External change was detected and synchronized!")
        print(f"   Terminal 1 updated database set_value from {original_setpoint} to {db_setpoint}")
    else:
        print(f"\n❌ FAILED: Database was not updated")
        print(f"   Expected: {new_setpoint}, Got: {db_setpoint}")
    
    # Restore original value
    print(f"\n🔄 Restoring original setpoint {original_setpoint}...")
    try:
        await plc_manager.write_parameter(param_id, original_setpoint)
        print(f"✅ Restored original value")
    except Exception as e:
        print(f"⚠️  Failed to restore: {e}")
    
    # Cleanup
    await plc_manager.disconnect()
    print(f"\n✅ Test complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

