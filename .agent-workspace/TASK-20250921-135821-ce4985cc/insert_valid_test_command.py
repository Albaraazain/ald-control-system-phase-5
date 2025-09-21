#!/usr/bin/env python3
"""
Insert test vacuum pump parameter command with valid component_parameter_id
"""
import asyncio
import uuid
from datetime import datetime
from supabase import create_client

# Load environment variables
SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNTk5NjM3NSwiZXhwIjoyMDUxNTcyMzc1fQ.k-r8lYAPhf-wbB7jZ_mwFQezBK4-AytiesjoD-OqWnU"
MACHINE_ID = "e3e6e280-0794-459f-84d5-5e468f60746e"

async def insert_test_vacuum_command():
    """Insert a test vacuum pump parameter command with valid component_parameter_id"""

    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        # First, get a valid component_parameter_id
        params_result = supabase.table('component_parameters').select('id').limit(1).execute()

        if not params_result.data:
            print("❌ No component parameters found in database")
            return

        param = params_result.data[0]

        # Generate test command
        command_id = str(uuid.uuid4())

        command_data = {
            'id': command_id,
            'machine_id': MACHINE_ID,
            'parameter_name': 'test_vacuum_pump_speed',  # Custom parameter name
            'target_value': 85.5,  # Test value
            'write_modbus_address': 35,  # Direct modbus address - bypasses component_parameter lookup
            'timeout_ms': 30000,
            'component_parameter_id': param['id']  # Use valid component parameter id
        }

        # Insert the command
        response = supabase.table('parameter_control_commands').insert(command_data).execute()

        print(f"\n✅ SUCCESS: Inserted test vacuum pump command")
        print(f"   Command ID: {command_id}")
        print(f"   Parameter: test_vacuum_pump_speed")
        print(f"   Value: 85.5")
        print(f"   Modbus Address: 35 (direct write)")
        print(f"   Component Param ID: {param['id']}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")

        print(f"\n🔍 EXPECTED BEHAVIOR:")
        print(f"   If main.py command listeners are running, you should see in the logs:")
        print(f"   🔔 PARAMETER COMMAND RECEIVED [POLLING/REALTIME]")
        print(f"   🟡 PARAMETER COMMAND PROCESSING - ID: {command_id}")
        print(f"   🟢 PARAMETER COMMAND EXECUTING")
        print(f"   ✅ PARAMETER COMMAND COMPLETED")

        print(f"\n⚠️ IF NO ENHANCED LOGS APPEAR:")
        print(f"   This confirms command listeners are NOT running")
        print(f"   Only continuous parameter logging is active")

    except Exception as e:
        print(f"❌ Error inserting command: {e}")

if __name__ == "__main__":
    asyncio.run(insert_test_vacuum_command())