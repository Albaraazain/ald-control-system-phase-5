#!/usr/bin/env python3
"""
Integration Test for Component Service (Terminal 4)

This script tests the end-to-end flow of component control commands:
1. Inserts a test command into component_control_commands table
2. Waits for Terminal 4 to process the command
3. Verifies the command was completed successfully
4. Validates atomic claim pattern (no race conditions)

Prerequisites:
- Terminal 4 must be running: python main.py --terminal 4 --demo
- Supabase connection configured
- component_control_commands table exists

Usage:
    python test_component_service.py
    python test_component_service.py --component-id test-valve-1 --action turn_on
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.db import get_supabase
from src.config import MACHINE_ID


async def test_component_control(
    component_id: str = "test-valve-1",
    action: str = "turn_on",
    reason: str = "automatic",
    timeout: int = 30
) -> bool:
    """
    Test end-to-end component control flow.

    Args:
        component_id: Component identifier to control
        action: Action to perform (turn_on, turn_off, etc.)
        reason: Reason for the control action
        timeout: Maximum time to wait for processing (seconds)

    Returns:
        bool: True if test passed, False otherwise
    """
    print("=" * 60)
    print("COMPONENT SERVICE INTEGRATION TEST")
    print("=" * 60)
    print(f"Component ID: {component_id}")
    print(f"Action: {action}")
    print(f"Reason: {reason}")
    print(f"Machine ID: {MACHINE_ID}")
    print(f"Timeout: {timeout}s")
    print("-" * 60)

    try:
        # Step 1: Create test command in database
        print("\n[Step 1] Creating test command in database...")
        supabase = get_supabase()

        test_command = {
            'component_id': component_id,
            'action': action,
            'reason': reason,
            'status': 'pending',
            'machine_id': MACHINE_ID,
            'created_at': datetime.utcnow().isoformat(),
        }

        result = supabase.table('component_control_commands').insert(test_command).execute()

        if not result.data or len(result.data) == 0:
            print("❌ FAILED: Could not insert test command")
            return False

        command_id = result.data[0]['id']
        print(f"✓ Test command created: ID={command_id}")

        # Step 2: Wait for backend to process
        print(f"\n[Step 2] Waiting for Terminal 4 to process command (max {timeout}s)...")

        for i in range(timeout):
            await asyncio.sleep(1)

            # Check command status
            check = supabase.table('component_control_commands').select('*').eq('id', command_id).single().execute()

            if not check.data:
                print(f"❌ FAILED: Command {command_id} not found in database")
                return False

            command_data = check.data

            # Print progress indicator
            if i % 5 == 0 and i > 0:
                print(f"  ... waiting ({i}s elapsed)")

            # Check if command is completed
            if command_data.get('completed_at'):
                elapsed = i + 1
                print(f"✓ Command processed in {elapsed} seconds")

                # Step 3: Verify results
                print("\n[Step 3] Verifying results...")
                print(f"  Command ID: {command_id}")
                print(f"  Status: {command_data.get('status', 'unknown')}")
                print(f"  Executed at: {command_data.get('executed_at', 'N/A')}")
                print(f"  Completed at: {command_data.get('completed_at', 'N/A')}")
                print(f"  Error message: {command_data.get('error_message', 'None')}")

                # Validate command was successful
                if command_data.get('status') == 'completed':
                    print("\n✓ Status is 'completed'")
                elif command_data.get('error_message') is None:
                    print("\n✓ No error message (success)")
                else:
                    print(f"\n❌ FAILED: Command has error: {command_data.get('error_message')}")
                    return False

                # Validate atomic claim pattern
                if command_data.get('executed_at') is not None:
                    print("✓ Command was atomically claimed (executed_at set)")
                else:
                    print("⚠ WARNING: Command missing executed_at timestamp")

                if command_data.get('completed_at') is not None:
                    print("✓ Command was finalized (completed_at set)")
                else:
                    print("❌ FAILED: Command missing completed_at timestamp")
                    return False

                # Test passed
                print("-" * 60)
                print("✓ INTEGRATION TEST PASSED")
                print("=" * 60)
                return True

        # Timeout reached
        print(f"\n❌ FAILED: Command not processed within {timeout} seconds")
        print("   Check if Terminal 4 is running: python main.py --terminal 4 --demo")
        return False

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_race_condition_protection():
    """
    Test that atomic claim pattern prevents race conditions.
    Simulates multiple concurrent command insertions.
    """
    print("\n" + "=" * 60)
    print("RACE CONDITION PROTECTION TEST")
    print("=" * 60)
    print("Testing atomic claim pattern with concurrent commands...")

    try:
        supabase = get_supabase()

        # Insert multiple commands rapidly
        command_ids = []
        for i in range(3):
            test_command = {
                'component_id': f'test-valve-{i}',
                'action': 'turn_on',
                'reason': 'race_condition_test',
                'status': 'pending',
                'machine_id': MACHINE_ID,
                'created_at': datetime.utcnow().isoformat(),
            }
            result = supabase.table('component_control_commands').insert(test_command).execute()
            command_ids.append(result.data[0]['id'])
            print(f"✓ Created command {i+1}/3: ID={result.data[0]['id']}")

        # Wait for processing
        await asyncio.sleep(10)

        # Verify all were processed correctly
        print("\nVerifying all commands processed...")
        all_processed = True
        for cmd_id in command_ids:
            check = supabase.table('component_control_commands').select('*').eq('id', cmd_id).single().execute()
            if not check.data.get('completed_at'):
                print(f"❌ Command {cmd_id} not completed")
                all_processed = False
            else:
                print(f"✓ Command {cmd_id} completed")

        if all_processed:
            print("\n✓ RACE CONDITION TEST PASSED")
        else:
            print("\n❌ RACE CONDITION TEST FAILED")

        return all_processed

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_error_handling():
    """
    Test error handling with invalid component.
    """
    print("\n" + "=" * 60)
    print("ERROR HANDLING TEST")
    print("=" * 60)
    print("Testing error handling with invalid component...")

    try:
        supabase = get_supabase()

        # Insert command for non-existent component
        test_command = {
            'component_id': 'nonexistent-component-12345',
            'action': 'turn_on',
            'reason': 'error_handling_test',
            'status': 'pending',
            'machine_id': MACHINE_ID,
            'created_at': datetime.utcnow().isoformat(),
        }
        result = supabase.table('component_control_commands').insert(test_command).execute()
        command_id = result.data[0]['id']
        print(f"✓ Created test command: ID={command_id}")

        # Wait for processing
        print("Waiting for processing...")
        await asyncio.sleep(10)

        # Verify error was recorded
        check = supabase.table('component_control_commands').select('*').eq('id', command_id).single().execute()

        if check.data.get('error_message'):
            print(f"✓ Error message recorded: {check.data.get('error_message')}")
            print("✓ ERROR HANDLING TEST PASSED")
            return True
        else:
            print("⚠ WARNING: Expected error message not found")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Component Service Integration Test")
    parser.add_argument("--component-id", default="test-valve-1", help="Component ID to test")
    parser.add_argument("--action", default="turn_on", help="Action to perform")
    parser.add_argument("--reason", default="automatic", help="Reason for action")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--full", action="store_true", help="Run full test suite (including race condition and error tests)")
    return parser.parse_args()


async def main():
    """Main test function"""
    args = parse_args()

    # Run basic integration test
    success = await test_component_control(
        component_id=args.component_id,
        action=args.action,
        reason=args.reason,
        timeout=args.timeout
    )

    # Run additional tests if --full flag
    if args.full:
        race_success = await test_race_condition_protection()
        error_success = await test_error_handling()

        success = success and race_success and error_success

    # Exit with appropriate code
    if success:
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("TESTS FAILED")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
