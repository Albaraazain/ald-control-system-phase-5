#!/usr/bin/env python3
"""
Cleanup script to mark terminal instances as stopped in the database.
Use this when terminals were killed but database still shows them as healthy.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.db import get_supabase
from src.config import MACHINE_ID

# Load environment variables
load_dotenv()

def cleanup_terminal_instances():
    """Mark all terminal instances for this machine as stopped."""
    
    if not MACHINE_ID:
        print("❌ Missing MACHINE_ID environment variable")
        return False
    
    # Get Supabase client
    supabase = get_supabase()
    
    try:
        # Get all terminal instances for this machine that are not stopped
        response = supabase.table('terminal_instances')\
            .select('*')\
            .eq('machine_id', MACHINE_ID)\
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
            .eq('machine_id', MACHINE_ID)\
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

