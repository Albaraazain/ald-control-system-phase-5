#!/usr/bin/env python3
"""
Quick script to check for recent vacuum pump parameter commands
"""
import asyncio
import os
from datetime import datetime, timedelta
from supabase import create_client

# Load environment variables
SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNTk5NjM3NSwiZXhwIjoyMDUxNTcyMzc1fQ.k-r8lYAPhf-wbB7jZ_mwFQezBK4-AytiesjoD-OqWnU"

async def check_recent_commands():
    """Check for recent parameter control commands"""

    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Look for commands created in the last 30 minutes
    thirty_minutes_ago = (datetime.now() - timedelta(minutes=30)).isoformat()

    try:
        # Query recent parameter control commands
        response = supabase.table('parameter_control_commands').select('*').gte('created_at', thirty_minutes_ago).order('created_at', desc=True).execute()

        print(f"\n=== RECENT PARAMETER COMMANDS (last 30 minutes) ===")
        print(f"Found {len(response.data)} commands since {thirty_minutes_ago}")

        for cmd in response.data:
            print(f"\n📝 Command ID: {cmd['id']}")
            print(f"   Parameter: {cmd['parameter_name']}")
            print(f"   Value: {cmd['target_value']}")
            print(f"   Created: {cmd['created_at']}")
            print(f"   Status: {cmd['status']}")
            if cmd['executed_at']:
                print(f"   Executed: {cmd['executed_at']}")
            if cmd['completed_at']:
                print(f"   Completed: {cmd['completed_at']}")
            if cmd['error_message']:
                print(f"   Error: {cmd['error_message']}")

        # Search specifically for "vacuum" or "pump" related commands
        print(f"\n=== VACUUM/PUMP SPECIFIC COMMANDS ===")
        vacuum_commands = [cmd for cmd in response.data if 'vacuum' in cmd['parameter_name'].lower() or 'pump' in cmd['parameter_name'].lower()]

        if vacuum_commands:
            print(f"Found {len(vacuum_commands)} vacuum/pump commands:")
            for cmd in vacuum_commands:
                print(f"🔍 {cmd['parameter_name']} = {cmd['target_value']} (Status: {cmd['status']})")
        else:
            print("❌ No vacuum/pump specific commands found")

        # Show all parameter names to help identify the vacuum pump command
        print(f"\n=== ALL PARAMETER NAMES IN RECENT COMMANDS ===")
        param_names = set([cmd['parameter_name'] for cmd in response.data])
        for name in sorted(param_names):
            print(f"  - {name}")

    except Exception as e:
        print(f"❌ Error querying database: {e}")

if __name__ == "__main__":
    asyncio.run(check_recent_commands())