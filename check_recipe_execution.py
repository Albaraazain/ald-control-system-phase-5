#!/usr/bin/env python3
"""
Check the most recent recipe execution to verify step tracking and synchronization.
"""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.db import get_supabase
from src.config import MACHINE_ID

# Load environment variables
load_dotenv()

def check_recent_execution():
    """Check the most recent recipe execution details."""
    
    if not MACHINE_ID:
        print("❌ Missing MACHINE_ID environment variable")
        return False
    
    # Get Supabase client
    supabase = get_supabase()
    
    try:
        # Get the most recent process execution
        print("🔍 Fetching most recent recipe execution...\n")
        
        process_response = supabase.table('process_executions')\
            .select('*')\
            .eq('machine_id', MACHINE_ID)\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if not process_response.data:
            print("❌ No process executions found")
            return False
        
        process = process_response.data[0]
        process_id = process['id']
        
        print("📋 PROCESS EXECUTION:")
        print(f"   ID: {process_id}")
        print(f"   Recipe ID: {process.get('recipe_id')}")
        print(f"   Status: {process.get('status')}")
        print(f"   Created: {process.get('created_at')}")
        print(f"   Parameters: {process.get('parameters')}")
        
        # Get the process execution state
        state_response = supabase.table('process_execution_state')\
            .select('*')\
            .eq('process_execution_id', process_id)\
            .single()\
            .execute()
        
        if state_response.data:
            state = state_response.data
            print("\n📊 PROCESS EXECUTION STATE:")
            print(f"   Process ID: {state.get('process_execution_id')}")
            print(f"   Current Overall Step: {state.get('current_overall_step')}")
            print(f"   Total Overall Steps: {state.get('total_overall_steps')}")  # This is what UI reads!
            print(f"   Current Step Index: {state.get('current_step_index')}")
            print(f"   Progress Data: {state.get('progress')}")
            print(f"   Status: {state.get('status')}")
            
            # Highlight the critical field
            total_steps = state.get('total_overall_steps')
            if total_steps is None or total_steps == 0:
                print("\n⚠️  WARNING: total_overall_steps is NULL or 0 - This causes 'step 0 of 0' in UI!")
            else:
                print(f"\n✅ total_overall_steps is set to: {total_steps}")
        else:
            print("\n❌ No process execution state found")
        
        # Get recipe commands for this execution
        command_response = supabase.table('recipe_commands')\
            .select('*')\
            .eq('machine_id', MACHINE_ID)\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if command_response.data:
            command = command_response.data[0]
            print("\n📨 RECIPE COMMAND:")
            print(f"   Command ID: {command.get('id')}")
            print(f"   Type: {command.get('command_type')}")
            print(f"   Status: {command.get('status')}")
            print(f"   Created: {command.get('created_at')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking execution: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = check_recent_execution()
    sys.exit(0 if success else 1)

