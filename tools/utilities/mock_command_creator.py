"""
Mock command creator for testing command listener functionality.
Creates various test commands in the Supabase database for integration testing.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from log_setup import logger
from config import MACHINE_ID
from db import get_supabase


class MockCommandCreator:
    """Creates mock commands for testing command listener functionality."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.test_machine_ids = [
            "e3e6e280-0794-459f-84d5-5e468f60746e",  # MACHINE-001
            "af56a11d-a6e7-4b30-b58d-8ad84dd0c2fa",  # VIRTUAL-DEV-001
            "0a08c96e-1ed1-484b-b5b4-f760cce02fe6",  # VIRTUAL-DEV-002
        ]
        self.test_recipe_ids = [
            "364a3703-7eee-42e8-9f1e-015c4c403103",  # hello
            "5c868417-ddcb-4f0a-b684-f1397ccd04e5",  # simple recipe -albaraa
            "72cba4a9-e03d-4023-a7d2-85c975adc2e2",  # aaa
        ]
        
    def create_test_start_recipe_commands(self) -> List[Dict[str, Any]]:
        """Create test start_recipe commands with various parameters."""
        commands = []
        
        # Valid start_recipe command
        commands.append({
            "type": "start_recipe",
            "parameters": {
                "recipe_id": self.test_recipe_ids[0],
                "operator_id": "550e8400-e29b-41d4-a716-446655440000",
                "description": "Integration test recipe execution",
                "process_notes": "Automated test run"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # Start recipe with minimal parameters
        commands.append({
            "type": "start_recipe", 
            "parameters": {
                "recipe_id": self.test_recipe_ids[1]
            },
            "machine_id": self.test_machine_ids[1],
            "status": "pending"
        })
        
        # Start recipe with invalid recipe_id (should fail)
        commands.append({
            "type": "start_recipe",
            "parameters": {
                "recipe_id": "00000000-0000-0000-0000-000000000000"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        return commands
    
    def create_test_stop_recipe_commands(self) -> List[Dict[str, Any]]:
        """Create test stop_recipe commands."""
        commands = []
        
        # Valid stop command
        commands.append({
            "type": "stop_recipe",
            "parameters": {
                "reason": "Integration test stop",
                "emergency": False
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # Emergency stop command
        commands.append({
            "type": "stop_recipe",
            "parameters": {
                "reason": "Emergency test stop",
                "emergency": True
            },
            "machine_id": self.test_machine_ids[1],
            "status": "pending"
        })
        
        return commands
    
    def create_test_set_parameter_commands(self) -> List[Dict[str, Any]]:
        """Create test set_parameter commands."""
        commands = []
        
        # Chamber pressure parameter
        commands.append({
            "type": "set_parameter",
            "parameters": {
                "parameter_name": "chamber_pressure",
                "value": 120.5,
                "unit": "torr"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # Temperature parameter
        commands.append({
            "type": "set_parameter",
            "parameters": {
                "parameter_name": "chamber_temperature",
                "value": 250.0,
                "unit": "celsius"
            },
            "machine_id": self.test_machine_ids[1],
            "status": "pending"
        })
        
        # Invalid parameter (should fail gracefully)
        commands.append({
            "type": "set_parameter",
            "parameters": {
                "parameter_name": "invalid_parameter",
                "value": "invalid_value"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        return commands
    
    def create_test_priority_commands(self) -> List[Dict[str, Any]]:
        """Create commands with different priorities for queue testing."""
        commands = []
        
        # Low priority command
        commands.append({
            "type": "set_parameter",
            "parameters": {
                "parameter_name": "flow_rate",
                "value": 50.0,
                "priority": "low"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # High priority command (should be processed first)
        commands.append({
            "type": "stop_recipe",
            "parameters": {
                "reason": "High priority stop test",
                "priority": "high"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # Medium priority command
        commands.append({
            "type": "set_parameter", 
            "parameters": {
                "parameter_name": "chamber_pressure",
                "value": 100.0,
                "priority": "medium"
            },
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        return commands
    
    def create_test_malformed_commands(self) -> List[Dict[str, Any]]:
        """Create malformed commands to test error handling."""
        commands = []
        
        # Missing required type
        commands.append({
            "parameters": {"test": "value"},
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # Invalid command type
        commands.append({
            "type": "invalid_command_type",
            "parameters": {"test": "value"},
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        # Malformed JSON parameters
        commands.append({
            "type": "set_parameter",
            "parameters": None,
            "machine_id": self.test_machine_ids[0],
            "status": "pending"
        })
        
        return commands
    
    def insert_test_commands(self, commands: List[Dict[str, Any]]) -> List[str]:
        """Insert test commands into the database."""
        inserted_ids = []
        
        for command in commands:
            try:
                # Generate UUID if not present
                if 'id' not in command:
                    command['id'] = str(uuid.uuid4())
                
                # Insert command
                result = self.supabase.table("recipe_commands").insert(command).execute()
                
                if result.data and len(result.data) > 0:
                    command_id = result.data[0]['id']
                    inserted_ids.append(command_id)
                    logger.info(f"Inserted test command: {command_id} - {command['type']}")
                else:
                    logger.error(f"Failed to insert command: {command}")
                    
            except Exception as e:
                logger.error(f"Error inserting command {command}: {str(e)}")
                
        return inserted_ids
    
    def create_command_scenarios(self) -> Dict[str, List[str]]:
        """Create comprehensive test command scenarios."""
        scenarios = {}
        
        # Scenario 1: Valid command flow
        logger.info("Creating valid command flow scenario...")
        valid_commands = (
            self.create_test_start_recipe_commands()[:2] +  # 2 valid start commands
            self.create_test_set_parameter_commands()[:2] +  # 2 valid parameter commands
            self.create_test_stop_recipe_commands()[:1]      # 1 valid stop command
        )
        scenarios['valid_flow'] = self.insert_test_commands(valid_commands)
        
        # Scenario 2: Error handling
        logger.info("Creating error handling scenario...")
        error_commands = (
            self.create_test_start_recipe_commands()[2:3] +  # Invalid recipe ID
            self.create_test_set_parameter_commands()[2:3] + # Invalid parameter
            self.create_test_malformed_commands()             # Malformed commands
        )
        scenarios['error_handling'] = self.insert_test_commands(error_commands)
        
        # Scenario 3: Priority and queuing
        logger.info("Creating priority queuing scenario...")
        priority_commands = self.create_test_priority_commands()
        scenarios['priority_queue'] = self.insert_test_commands(priority_commands)
        
        # Scenario 4: High volume test
        logger.info("Creating high volume scenario...")
        high_volume_commands = []
        for i in range(10):
            high_volume_commands.append({
                "type": "set_parameter",
                "parameters": {
                    "parameter_name": f"test_param_{i}",
                    "value": i * 10.0
                },
                "machine_id": self.test_machine_ids[i % len(self.test_machine_ids)],
                "status": "pending"
            })
        scenarios['high_volume'] = self.insert_test_commands(high_volume_commands)
        
        return scenarios
    
    def cleanup_test_commands(self, command_ids: List[str] = None):
        """Clean up test commands from the database."""
        try:
            if command_ids:
                # Delete specific commands
                for cmd_id in command_ids:
                    result = self.supabase.table("recipe_commands").delete().eq("id", cmd_id).execute()
                    logger.info(f"Cleaned up test command: {cmd_id}")
            else:
                # Delete all test commands (be careful with this!)
                # Only delete commands from test machines
                for machine_id in self.test_machine_ids:
                    result = (
                        self.supabase.table("recipe_commands")
                        .delete()
                        .eq("machine_id", machine_id)
                        .execute()
                    )
                logger.info("Cleaned up all test commands")
                
        except Exception as e:
            logger.error(f"Error cleaning up test commands: {str(e)}")
    
    def get_command_status_summary(self) -> Dict[str, int]:
        """Get summary of command statuses in the database."""
        try:
            result = self.supabase.table("recipe_commands").select("status").execute()
            
            status_counts = {}
            for record in result.data:
                status = record['status']
                status_counts[status] = status_counts.get(status, 0) + 1
                
            return status_counts
            
        except Exception as e:
            logger.error(f"Error getting command status summary: {str(e)}")
            return {}


def main():
    """Main function to create test commands."""
    creator = MockCommandCreator()
    
    print("Creating test command scenarios...")
    scenarios = creator.create_command_scenarios()
    
    print(f"\nCreated command scenarios:")
    for scenario_name, command_ids in scenarios.items():
        print(f"  {scenario_name}: {len(command_ids)} commands")
    
    print(f"\nCommand status summary:")
    status_summary = creator.get_command_status_summary()
    for status, count in status_summary.items():
        print(f"  {status}: {count}")
    
    # Wait for user input before cleanup
    print(f"\nTest commands created. Press Enter to clean up or Ctrl+C to keep them...")
    try:
        input()
        print("Cleaning up test commands...")
        all_command_ids = []
        for ids in scenarios.values():
            all_command_ids.extend(ids)
        creator.cleanup_test_commands(all_command_ids)
        print("Cleanup complete.")
    except KeyboardInterrupt:
        print("\nSkipping cleanup. Test commands remain in database.")


if __name__ == "__main__":
    main()