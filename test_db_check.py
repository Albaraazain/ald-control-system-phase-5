#!/usr/bin/env python3
"""
Simple database check to see if continuous parameter logging is working.
"""

import os
import sys
import json
import asyncio
import time
from datetime import datetime, timedelta

# Set up environment variables
os.environ['SUPABASE_URL'] = 'https://yceyfsqusdmcwgkwxcnt.supabase.co'
os.environ['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNTk5NjM3NSwiZXhwIjoyMDUxNTcyMzc1fQ.k-r8lYAPhf-wbB7jZ_mwFQezBK4-AytiesjoD-OqWnU'
os.environ['MACHINE_ID'] = 'e3e6e280-0794-459f-84d5-5e468f60746e'

# Try direct database access
try:
    import supabase

    # Create client
    client = supabase.create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_KEY']
    )

    print("🧪 Testing Continuous Parameter Logging Database Activity")
    print("="*60)

    # Test 1: Check if tables exist
    print("\n1. Testing database table accessibility...")

    try:
        pvh_result = client.table('parameter_value_history').select('*').limit(1).execute()
        print("   ✅ parameter_value_history table accessible")
    except Exception as e:
        print(f"   ❌ parameter_value_history access failed: {str(e)}")

    try:
        pdp_result = client.table('process_data_points').select('*').limit(1).execute()
        print("   ✅ process_data_points table accessible")
    except Exception as e:
        print(f"   ❌ process_data_points access failed: {str(e)}")

    # Test 2: Check recent activity
    print("\n2. Checking for recent parameter logging activity...")

    # Get count of records in the last 5 minutes
    cutoff_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

    try:
        recent_pvh = client.table('parameter_value_history').select('*').gte('timestamp', cutoff_time).execute()
        recent_count = len(recent_pvh.data) if recent_pvh.data else 0
        print(f"   📊 Recent parameter_value_history records (last 5 min): {recent_count}")

        if recent_count > 0:
            print("   ✅ Parameter logging activity detected!")

            # Show latest record
            latest = client.table('parameter_value_history').select('*').order('timestamp', desc=True).limit(1).execute()
            if latest.data:
                latest_record = latest.data[0]
                latest_time = latest_record['timestamp']
                time_diff = (datetime.utcnow() - datetime.fromisoformat(latest_time.replace('Z', '+00:00'))).total_seconds()
                print(f"   📅 Latest record: {time_diff:.1f} seconds ago")
                print(f"   📋 Parameter ID: {latest_record['parameter_id']}")
                print(f"   📊 Value: {latest_record['value']}")
        else:
            print("   ⚠️  No recent parameter logging activity detected")

    except Exception as e:
        print(f"   ❌ Error checking recent activity: {str(e)}")

    # Test 3: Check for process mode activity
    print("\n3. Checking for process mode logging...")

    try:
        # Check for recent process executions
        recent_processes = client.table('process_executions').select('*').eq('machine_id', os.environ['MACHINE_ID']).order('created_at', desc=True).limit(5).execute()

        if recent_processes.data:
            print(f"   📋 Found {len(recent_processes.data)} recent process executions")

            # Check if any have corresponding data points
            for process in recent_processes.data[:2]:  # Check first 2
                process_id = process['id']
                pdp_count = client.table('process_data_points').select('*', count='exact').eq('process_id', process_id).execute()
                count = pdp_count.count or 0
                print(f"   📊 Process {process_id[:8]}... has {count} data points")

                if count > 0:
                    print("   ✅ Process mode logging detected!")
                    break
        else:
            print("   ℹ️  No recent process executions found")

    except Exception as e:
        print(f"   ❌ Error checking process mode: {str(e)}")

    # Test 4: Live monitoring
    print("\n4. Live monitoring test (10 seconds)...")

    try:
        before_count = client.table('parameter_value_history').select('*', count='exact').execute().count or 0
        print(f"   📊 Starting count: {before_count}")
        print("   ⏳ Waiting 10 seconds...")

        time.sleep(10)

        after_count = client.table('parameter_value_history').select('*', count='exact').execute().count or 0
        new_records = after_count - before_count

        print(f"   📊 Ending count: {after_count}")
        print(f"   📈 New records in 10 seconds: {new_records}")

        if new_records >= 8:  # Should have ~10 records in 10 seconds at 1 per second
            print("   ✅ Live logging is working at expected rate!")
        elif new_records > 0:
            print("   ⚠️  Some logging activity but below expected rate")
        else:
            print("   ❌ No new logging activity detected")

    except Exception as e:
        print(f"   ❌ Live monitoring failed: {str(e)}")

    print("\n" + "="*60)
    print("Database check completed!")

except ImportError:
    print("❌ Supabase package not available. Install with: pip install supabase")
except Exception as e:
    print(f"❌ Database check failed: {str(e)}")