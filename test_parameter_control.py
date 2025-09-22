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
        
        # Define test commands using correct component_parameter_ids from database
        test_commands = [
            {
                "parameter_name": "power_on",
                "component_parameter_id": "9c53f4ef-5506-4a45-9718-af8a7b233056",
                "target_value": 1,  # Turn ON Nitrogen Generator
                "machine_id": machine_id,
            },
            {
                "parameter_name": "flow",
                "component_parameter_id": "35969620-6843-4130-8eca-d6b62dc74dbf",
                "target_value": 150.5,  # Set MFC 1 flow rate to 150.5 sccm
                "machine_id": machine_id,
            },
            {
                "parameter_name": "power_on",
                "component_parameter_id": "ca61248a-9be5-43d2-a204-df6f15ef4fe7",
                "target_value": 1,  # Turn ON Chamber Heater
                "machine_id": machine_id,
            },
            {
                "parameter_name": "temperature",
                "component_parameter_id": "b6433c16-cb13-4e6a-b5b8-1b1519f0b44b",
                "target_value": 250.0,  # Set Chamber Heater temperature to 250°C
                "machine_id": machine_id,
            },
            {
                "parameter_name": "valve_state",
                "component_parameter_id": "5d2cfe0a-151c-4745-9865-cd78125f93d0",
                "target_value": 1,  # Open Exhaust Gate Valve
                "machine_id": machine_id,
            },
            {
                "parameter_name": "power_on",
                "component_parameter_id": "6c08a1b0-5674-46c1-9fb5-a4c4eca1adf1",
                "target_value": 1,  # Turn ON Frontend Heater
                "machine_id": machine_id,
            }
        ]
        
        # Insert the test commands
        result = supabase.table("parameter_control_commands").insert(test_commands).execute()
        
        if result.data:
            print(f"✅ Successfully created {len(result.data)} test parameter commands:")
            for i, cmd in enumerate(result.data):
                component_name = get_component_name(supabase, cmd['component_parameter_id'])
                print(f"   {i+1}. [{component_name}] {cmd['parameter_name']} = {cmd['target_value']} (ID: {cmd['id']})")
            return True
        else:
            print("❌ Failed to create test commands")
            return False
            
    except Exception as e:
        print(f"❌ Error creating test commands: {str(e)}")
        return False


def get_component_name(supabase, component_parameter_id):
    """
    Get component name for a given component_parameter_id.
    """
    try:
        # First get the component_id from component_parameters
        result = (
            supabase.table("component_parameters")
            .select("component_id")
            .eq("id", component_parameter_id)
            .execute()
        )

        if result.data and result.data[0].get('component_id'):
            component_id = result.data[0]['component_id']

            # Then get the component name from machine_components
            component_result = (
                supabase.table("machine_components")
                .select("name")
                .eq("id", component_id)
                .execute()
            )

            if component_result.data and component_result.data[0].get('name'):
                return component_result.data[0]['name']

        return "Unknown Component"
    except Exception:
        return "Unknown Component"


def show_pending_commands():
    """
    Display all pending parameter control commands.
    """
    try:
        supabase = get_supabase()

        result = (
            supabase.table("parameter_control_commands")
            .select("*")
            .is_("executed_at", None)
            .order("created_at")
            .execute()
        )

        if result.data:
            print(f"\n📋 Found {len(result.data)} pending parameter commands:")
            for cmd in result.data:
                component_name = get_component_name(supabase, cmd['component_parameter_id'])
                print(f"   • [{component_name}] {cmd['parameter_name']} = {cmd['target_value']}")
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
                executed = cmd.get('executed_at')
                completed = cmd.get('completed_at')
                error = cmd.get('error_message')
                if completed:
                    status = 'failed' if error else 'completed'
                elif executed:
                    status = 'executing'
                else:
                    status = 'pending'
                status_emoji = {
                    'pending': '⏳',
                    'executing': '⚡',
                    'completed': '✅',
                    'failed': '❌'
                }.get(status, '❓')
                component_name = get_component_name(supabase, cmd['component_parameter_id'])
                print(f"   {status_emoji} [{component_name}] {cmd['parameter_name']} = {cmd['target_value']} ({status})")
                if error:
                    print(f"      Error: {error}")
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
    Main function with interactive menu or command-line arguments.
    """
    if len(sys.argv) > 1:
        # Command-line mode
        arg = sys.argv[1].lower()
        if arg == 'create':
            print("🔨 Creating test parameter commands...")
            create_parameter_test_commands()
        elif arg == 'pending':
            print("📋 Checking pending commands...")
            show_pending_commands()
        elif arg == 'recent':
            print("📊 Showing recent commands...")
            show_recent_commands()
        elif arg == 'clear':
            clear_all_commands()
        else:
            print("Usage: python test_parameter_control.py [create|pending|recent|clear]")
        return

    # Interactive mode
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
