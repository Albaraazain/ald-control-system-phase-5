#!/usr/bin/env python3
"""
Test script for parameter control commands.
This script can be used to create test parameter control commands in the database
to test the parameter control listener functionality.
"""

import asyncio
import sys
import os

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.db import get_supabase
from src.config import MACHINE_ID
from src.log_setup import logger


def create_parameter_test_commands():
    """
    Create test parameter control commands for different types of parameters.
    """
    try:
        supabase = get_supabase()
        
        # Get the first machine ID if MACHINE_ID is not set
        machine_id = MACHINE_ID
        if not machine_id:
            machines = supabase.table('machines').select('id').limit(1).execute()
            if machines.data:
                machine_id = machines.data[0]['id']
            else:
                print("No machines found in database!")
                return False
        
        print(f"Creating test commands for machine: {machine_id}")
        
        # Define test commands for different parameter types
        test_commands = [
            {
                "parameter_name": "pump_1",
                "parameter_type": "binary",
                "target_value": 1,  # Turn ON
                "modbus_address": 100,
                "modbus_type": "coil",
                "machine_id": machine_id,
                "priority": 1
            },
            {
                "parameter_name": "pump_2", 
                "parameter_type": "binary",
                "target_value": 0,  # Turn OFF
                "modbus_address": 101,
                "modbus_type": "coil",
                "machine_id": machine_id,
                "priority": 1
            },
            {
                "parameter_name": "nitrogen_generator",
                "parameter_type": "binary", 
                "target_value": 1,  # Turn ON
                "modbus_address": 102,
                "modbus_type": "coil",
                "machine_id": machine_id,
                "priority": 2  # Higher priority
            },
            {
                "parameter_name": "mfc_1_flow_rate",
                "parameter_type": "flow_rate",
                "target_value": 150.5,  # Set flow rate to 150.5 sccm
                "modbus_address": 200,
                "modbus_type": "holding_register",
                "machine_id": machine_id,
                "priority": 0
            },
            {
                "parameter_name": "chamber_heater",
                "parameter_type": "binary",
                "target_value": 1,  # Turn ON
                "modbus_address": 103,
                "modbus_type": "coil",
                "machine_id": machine_id,
                "priority": 1
            },
            {
                "parameter_name": "pressure_setpoint",
                "parameter_type": "pressure",
                "target_value": 0.75,  # Set pressure to 0.75 torr
                "modbus_address": 201,
                "modbus_type": "holding_register",
                "machine_id": machine_id,
                "priority": 1
            }
        ]
        
        # Insert the test commands
        result = supabase.table("parameter_control_commands").insert(test_commands).execute()
        
        if result.data:
            print(f"✅ Successfully created {len(result.data)} test parameter commands:")
            for i, cmd in enumerate(result.data):
                print(f"   {i+1}. {cmd['parameter_name']} = {cmd['target_value']} (ID: {cmd['id']})")
            return True
        else:
            print("❌ Failed to create test commands")
            return False
            
    except Exception as e:
        print(f"❌ Error creating test commands: {str(e)}")
        return False


def show_pending_commands():
    """
    Display all pending parameter control commands.
    """
    try:
        supabase = get_supabase()
        
        result = (
            supabase.table("parameter_control_commands")
            .select("*")
            .eq("status", "pending")
            .order("priority", desc=True)
            .order("created_at")
            .execute()
        )
        
        if result.data:
            print(f"\n📋 Found {len(result.data)} pending parameter commands:")
            for cmd in result.data:
                print(f"   • {cmd['parameter_name']} = {cmd['target_value']} "
                      f"(Priority: {cmd['priority']}, Type: {cmd['parameter_type']})")
        else:
            print("\n✅ No pending parameter commands found")
            
    except Exception as e:
        print(f"❌ Error fetching pending commands: {str(e)}")


def show_recent_commands():
    """
    Display recent parameter control commands and their status.
    """
    try:
        supabase = get_supabase()
        
        result = (
            supabase.table("parameter_control_commands")
            .select("*")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        
        if result.data:
            print(f"\n📊 Last 10 parameter commands:")
            for cmd in result.data:
                status_emoji = {
                    'pending': '⏳',
                    'executing': '⚡',
                    'completed': '✅',
                    'failed': '❌'
                }.get(cmd['status'], '❓')
                
                print(f"   {status_emoji} {cmd['parameter_name']} = {cmd['target_value']} "
                      f"({cmd['status']})")
                if cmd['error_message']:
                    print(f"      Error: {cmd['error_message']}")
        else:
            print("\n✅ No parameter commands found")
            
    except Exception as e:
        print(f"❌ Error fetching recent commands: {str(e)}")


def clear_all_commands():
    """
    Clear all parameter control commands from the database.
    Use with caution!
    """
    try:
        response = input("⚠️  Are you sure you want to clear ALL parameter commands? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
            
        supabase = get_supabase()
        
        # Delete all commands
        result = supabase.table("parameter_control_commands").delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        
        print(f"✅ Cleared all parameter control commands")
        
    except Exception as e:
        print(f"❌ Error clearing commands: {str(e)}")


def main():
    """
    Main function with interactive menu.
    """
    print("🔧 Parameter Control Test Script")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Create test parameter commands")
        print("2. Show pending commands")
        print("3. Show recent commands")
        print("4. Clear all commands")
        print("5. Exit")
        
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == '1':
                print("\n🔨 Creating test parameter commands...")
                create_parameter_test_commands()
                
            elif choice == '2':
                print("\n📋 Checking pending commands...")
                show_pending_commands()
                
            elif choice == '3':
                print("\n📊 Showing recent commands...")
                show_recent_commands()
                
            elif choice == '4':
                clear_all_commands()
                
            elif choice == '5':
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please select 1-5.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    main()