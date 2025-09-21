#!/usr/bin/env python3
"""
Check parameter_control_commands table schema
"""
import asyncio
from supabase import create_client

# Load environment variables
SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNTk5NjM3NSwiZXhwIjoyMDUxNTcyMzc1fQ.k-r8lYAPhf-wbB7jZ_mwFQezBK4-AytiesjoD-OqWnU"

async def check_schema():
    """Check the schema by looking at existing records"""

    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        # Query one record to see the structure
        response = supabase.table('parameter_control_commands').select('*').limit(1).execute()

        if response.data:
            print("=== PARAMETER_CONTROL_COMMANDS SCHEMA ===")
            record = response.data[0]
            for key, value in record.items():
                print(f"  {key}: {type(value).__name__} = {value}")
        else:
            print("No records found in parameter_control_commands table")

    except Exception as e:
        print(f"❌ Error querying schema: {e}")

if __name__ == "__main__":
    asyncio.run(check_schema())