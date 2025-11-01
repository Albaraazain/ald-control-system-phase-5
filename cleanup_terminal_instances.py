#!/usr/bin/env python3
"""
Cleanup script to mark terminal instances as stopped in the database.
Use this when terminals were killed but database still shows them as healthy.
"""

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def cleanup_terminal_instances():
    """Mark all terminal instances for this machine as stopped."""
    
    # Get Supabase credentials
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    machine_id = os.getenv('MACHINE_ID')
    
    if not all([url, key, machine_id]):
        print("❌ Missing required environment variables:")
        print(f"   SUPABASE_URL: {'✓' if url else '✗'}")
        print(f"   SUPABASE_SERVICE_ROLE_KEY: {'✓' if key else '✗'}")
        print(f"   MACHINE_ID: {'✓' if machine_id else '✗'}")
        return False
    
    # Create Supabase client
    supabase: Client = create_client(url, key)
    
    try:
        # Get all terminal instances for this machine that are not stopped
        response = supabase.table('terminal_instances')\
            .select('*')\
            .eq('machine_id', machine_id)\
            .neq('status', 'stopped')\
            .execute()
        
        if not response.data:
            print("✅ No active terminal instances found to clean up")
            return True
        
        print(f"📋 Found {len(response.data)} terminal instances to clean up:")
        for instance in response.data:
            print(f"   • {instance['terminal_type']} (PID: {instance['process_id']}, Status: {instance['status']})")
        
        # Mark all instances as stopped
        update_response = supabase.table('terminal_instances')\
            .update({'status': 'stopped'})\
            .eq('machine_id', machine_id)\
            .neq('status', 'stopped')\
            .execute()
        
        print(f"\n✅ Successfully marked {len(response.data)} terminal instances as stopped")
        return True
        
    except Exception as e:
        print(f"❌ Error cleaning up terminal instances: {e}")
        return False

if __name__ == '__main__':
    success = cleanup_terminal_instances()
    sys.exit(0 if success else 1)

