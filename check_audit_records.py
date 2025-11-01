#!/usr/bin/env python3
"""Check audit trail records in database"""

import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_KEY')
)

machine_id = os.environ.get('MACHINE_ID')

print("\n🔍 Current Audit Trail Configuration:\n")

# Check parameter_control_commands table structure
print("📋 parameter_control_commands table columns:")
result = supabase.table('parameter_control_commands').select('*').limit(1).execute()
if result.data:
    print(f"   Columns: {', '.join(result.data[0].keys())}")
else:
    print("   (No data to show columns)")

# Check recent audit records
print("\n📊 Recent valve audit records (last 3):")
result = supabase.table('parameter_control_commands').select(
    '*'
).eq('machine_id', machine_id).like('parameter_name', 'Valve_%').order('created_at', desc=True).limit(3).execute()

for record in result.data:
    print(f"\n   Valve: {record['parameter_name']}")
    print(f"   Target Value: {record['target_value']}")
    print(f"   Executed At: {record.get('executed_at', 'N/A')}")
    print(f"   Completed At: {record.get('completed_at', 'N/A')}")
    print(f"   Created At: {record['created_at']}")
    # Check if process_id exists
    if 'process_id' in record:
        print(f"   Process ID: {record.get('process_id', 'N/A')}")
    if 'recipe_id' in record:
        print(f"   Recipe ID: {record.get('recipe_id', 'N/A')}")
    if 'step_id' in record:
        print(f"   Step ID: {record.get('step_id', 'N/A')}")

print("\n\n❌ Current Limitations:")
print("   - No process_id: Can't link valve operation to process execution")
print("   - No recipe_id: Can't link valve operation to recipe")
print("   - No step_id: Can't link valve operation to specific recipe step")
print("   - No duration_ms: Can't see how long valve was open")
print("   - No actual_value: Can't verify what was actually written to PLC")

print("\n\n✅ What We Could Track:")
print("   - process_id: Link to process_executions table")
print("   - recipe_id: Link to recipes table")
print("   - step_id: Link to recipe_steps table")
print("   - duration_ms: How long valve was commanded to stay open")
print("   - initiated_by: 'recipe' vs 'manual' vs 'emergency'")
print("   - step_sequence: Order within recipe execution")
print("   - plc_write_time_ms: How long the PLC write took")
print("   - verification_result: Did we verify the write succeeded?")
