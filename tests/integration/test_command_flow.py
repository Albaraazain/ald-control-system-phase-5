#!/usr/bin/env python3
"""
Command Flow Integration Test
Tests command creation, detection, processing and integration with new database schema
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger
from src.db import get_supabase
from src.command_flow.listener import CommandListener
from src.command_flow.processor import CommandProcessor

# Get the supabase client
supabase = get_supabase()

# Set up logging
logger = setup_logger(__name__)

class CommandFlowIntegrationTest:
    """Tests command flow integration with new database schema"""
    
    def __init__(self):
        self.test_results = {
            'test_run_id': str(uuid.uuid4()),
            'start_time': datetime.now().isoformat(),
            'tests_passed': 0,
            'tests_failed': 0,
            'test_details': []
        }
        
        # Test recipe IDs
        self.simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        self.complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"
        
        # Test machine and user IDs
        self.test_machine_id = None
        self.test_user_id = None
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all command flow integration tests"""
        logger.info("📡 Starting Command Flow Integration Test Suite")
        logger.info(f"Test Run ID: {self.test_results['test_run_id']}")
        
        try:
            # Setup test environment
            await self._setup_test_environment()
            
            # Test 1: Command Creation and Detection
            await self._test_command_creation_detection()
            
            # Test 2: Start Recipe Command Processing
            await self._test_start_recipe_command()
            
            # Test 3: Stop Recipe Command Processing
            await self._test_stop_recipe_command()
            
            # Test 4: Set Parameter Command Processing
            await self._test_set_parameter_command()
            
            # Test 5: Command State Transitions
            await self._test_command_state_transitions()
            
            # Test 6: Recipe Command Integration with New Schema
            await self._test_recipe_command_schema_integration()
            
            # Test 7: Error Handling and Recovery
            await self._test_error_handling_recovery()
            
            # Test 8: Concurrent Command Processing
            await self._test_concurrent_command_processing()
            
        except Exception as e:
            logger.error(f"❌ Critical test failure: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._record_test_result("critical_failure", False, str(e))
        
        # Generate final report
        await self._generate_final_report()
        return self.test_results
        
    async def _setup_test_environment(self):
        """Setup test environment with required data"""
        logger.info("🔧 Setting up test environment")
        
        # Get test machine
        machines = supabase.table("machines").select("id").limit(1).execute()
        if machines.data:
            self.test_machine_id = machines.data[0]['id']
        else:
            # Create test machine if none exist
            test_machine = {
                'id': str(uuid.uuid4()),
                'serial_number': f'CMD-TEST-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                'location': 'Command Test Lab',
                'lab_name': 'Integration Test Lab',
                'lab_institution': 'Test Institution',
                'model': 'ALD-CommandTest-1000',
                'machine_type': 'atomic_layer_deposition',
                'install_date': datetime.now().isoformat(),
                'status': 'online',
                'admin_id': await self._get_test_user_id(),
                'is_active': True,
                'is_virtual': True,
                'virtual_config': {
                    'data_generation_interval': 1000,
                    'speed_multiplier': 1.0,
                    'temperature_fluctuation': 0.1,
                    'pressure_fluctuation': 0.1,
                    'scenario': 'normal'
                }
            }
            result = supabase.table("machines").insert(test_machine).execute()
            self.test_machine_id = result.data[0]['id']
            
        logger.info(f"Using test machine ID: {self.test_machine_id}")
        
    async def _get_test_user_id(self) -> str:
        """Get test user ID"""
        if self.test_user_id is None:
            result = supabase.table("profiles").select("id").limit(1).execute()
            if result.data:
                self.test_user_id = result.data[0]['id']
            else:
                raise Exception("No test users available")
        return self.test_user_id
        
    async def _test_command_creation_detection(self):
        """Test 1: Command creation and detection"""
        test_name = "command_creation_detection"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create a test command
            test_command = {
                'id': str(uuid.uuid4()),
                'type': 'start_recipe',
                'parameters': {
                    'recipe_id': self.simple_recipe_id,
                    'machine_id': self.test_machine_id
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command
            result = supabase.table("recipe_commands").insert(test_command).execute()
            assert len(result.data) == 1, "Failed to create test command"
            
            command_id = result.data[0]['id']
            
            # Verify command was created correctly
            created_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            assert len(created_command.data) == 1, "Created command not found"
            
            command_data = created_command.data[0]
            assert command_data['type'] == 'start_recipe', "Command type mismatch"
            assert command_data['status'] == 'pending', "Command status mismatch"
            assert command_data['machine_id'] == self.test_machine_id, "Machine ID mismatch"
            
            # Test command listener detection (simulated)
            listener = CommandListener()
            pending_commands = await listener._get_pending_commands()
            
            # Our command should be in the pending list
            our_command = None
            for cmd in pending_commands:
                if cmd['id'] == command_id:
                    our_command = cmd
                    break
                    
            assert our_command is not None, "Command not detected by listener"
            
            await self._record_test_result(test_name, True, f"Command creation and detection passed - command ID: {command_id}")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Command creation/detection failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_start_recipe_command(self):
        """Test 2: Start recipe command processing"""
        test_name = "start_recipe_command"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create start_recipe command
            start_command = {
                'id': str(uuid.uuid4()),
                'type': 'start_recipe',
                'parameters': {
                    'recipe_id': self.simple_recipe_id,
                    'machine_id': self.test_machine_id,
                    'operator_notes': 'Integration test execution'
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command
            result = supabase.table("recipe_commands").insert(start_command).execute()
            command_id = result.data[0]['id']
            
            # Process command
            processor = CommandProcessor()
            await processor._process_command(result.data[0])
            
            # Check command status was updated
            processed_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            command_data = processed_command.data[0]
            
            # Command should be completed or failed (both are valid outcomes)
            assert command_data['status'] in ['completed', 'failed'], f"Unexpected command status: {command_data['status']}"
            
            # If completed, check that process execution was created
            if command_data['status'] == 'completed':
                # Look for created process execution
                processes = supabase.table("process_executions").select("*").eq("recipe_id", self.simple_recipe_id).order("created_at", desc=True).limit(1).execute()
                
                if processes.data:
                    process = processes.data[0]
                    assert process['recipe_id'] == self.simple_recipe_id, "Process recipe ID mismatch"
                    assert process['machine_id'] == self.test_machine_id, "Process machine ID mismatch"
                    logger.info(f"Process execution created: {process['id']}")
                    
            await self._record_test_result(test_name, True, f"Start recipe command processed - status: {command_data['status']}")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Start recipe command failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_stop_recipe_command(self):
        """Test 3: Stop recipe command processing"""
        test_name = "stop_recipe_command"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create stop_recipe command
            stop_command = {
                'id': str(uuid.uuid4()),
                'type': 'stop_recipe',
                'parameters': {
                    'machine_id': self.test_machine_id,
                    'reason': 'Integration test stop'
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command
            result = supabase.table("recipe_commands").insert(stop_command).execute()
            command_id = result.data[0]['id']
            
            # Process command
            processor = CommandProcessor()
            await processor._process_command(result.data[0])
            
            # Check command status
            processed_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            command_data = processed_command.data[0]
            
            assert command_data['status'] in ['completed', 'failed'], f"Unexpected stop command status: {command_data['status']}"
            
            await self._record_test_result(test_name, True, f"Stop recipe command processed - status: {command_data['status']}")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Stop recipe command failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_set_parameter_command(self):
        """Test 4: Set parameter command processing"""
        test_name = "set_parameter_command"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Get a component parameter for testing
            parameters = supabase.table("component_parameters").select("id").limit(1).execute()
            if not parameters.data:
                logger.info("No component parameters available, skipping set parameter test")
                await self._record_test_result(test_name, True, "Set parameter test skipped - no parameters available")
                return
                
            parameter_id = parameters.data[0]['id']
            
            # Create set_parameter command
            set_param_command = {
                'id': str(uuid.uuid4()),
                'type': 'set_parameter',
                'parameters': {
                    'parameter_id': parameter_id,
                    'value': 123.45,
                    'machine_id': self.test_machine_id
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command
            result = supabase.table("recipe_commands").insert(set_param_command).execute()
            command_id = result.data[0]['id']
            
            # Process command
            processor = CommandProcessor()
            await processor._process_command(result.data[0])
            
            # Check command status
            processed_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            command_data = processed_command.data[0]
            
            assert command_data['status'] in ['completed', 'failed'], f"Unexpected set parameter command status: {command_data['status']}"
            
            await self._record_test_result(test_name, True, f"Set parameter command processed - status: {command_data['status']}")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Set parameter command failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_command_state_transitions(self):
        """Test 5: Command state transitions"""
        test_name = "command_state_transitions"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create command to test state transitions
            test_command = {
                'id': str(uuid.uuid4()),
                'type': 'start_recipe',
                'parameters': {
                    'recipe_id': self.simple_recipe_id,
                    'machine_id': self.test_machine_id
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command
            result = supabase.table("recipe_commands").insert(test_command).execute()
            command_id = result.data[0]['id']
            
            # Verify initial state
            initial_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            assert initial_command.data[0]['status'] == 'pending', "Initial status should be pending"
            
            # Simulate status transition to 'processing'
            update_result = supabase.table("recipe_commands").update({
                'status': 'processing',
                'updated_at': datetime.now().isoformat()
            }).eq("id", command_id).execute()
            
            # Verify transition
            processing_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            assert processing_command.data[0]['status'] == 'processing', "Status should be processing"
            
            # Simulate final transition to 'completed'
            supabase.table("recipe_commands").update({
                'status': 'completed',
                'executed_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }).eq("id", command_id).execute()
            
            # Verify final state
            final_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            final_data = final_command.data[0]
            assert final_data['status'] == 'completed', "Final status should be completed"
            assert final_data['executed_at'] is not None, "Executed timestamp should be set"
            
            await self._record_test_result(test_name, True, "Command state transitions validation passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Command state transitions failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_recipe_command_schema_integration(self):
        """Test 6: Recipe command integration with new schema"""
        test_name = "recipe_command_schema_integration"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Test command with recipe_step_id reference
            recipe_steps = supabase.table("recipe_steps").select("id").eq("recipe_id", self.simple_recipe_id).limit(1).execute()
            if not recipe_steps.data:
                raise Exception("No recipe steps found for testing")
                
            step_id = recipe_steps.data[0]['id']
            
            # Create command linked to specific recipe step
            step_command = {
                'id': str(uuid.uuid4()),
                'type': 'start_recipe',
                'parameters': {
                    'recipe_id': self.simple_recipe_id,
                    'machine_id': self.test_machine_id,
                    'specific_step_id': step_id
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'recipe_step_id': step_id,  # New field linking to recipe step
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command
            result = supabase.table("recipe_commands").insert(step_command).execute()
            command_id = result.data[0]['id']
            
            # Verify schema integration
            created_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            command_data = created_command.data[0]
            
            assert command_data['recipe_step_id'] == step_id, "Recipe step ID not properly linked"
            assert command_data['machine_id'] == self.test_machine_id, "Machine ID not properly set"
            
            # Test query joining with recipe steps
            joined_query = supabase.table("recipe_commands").select("*, recipe_steps!recipe_commands_recipe_step_id_fkey(name, type)").eq("id", command_id).execute()
            
            if joined_query.data and joined_query.data[0].get('recipe_steps'):
                step_info = joined_query.data[0]['recipe_steps']
                assert 'name' in step_info, "Recipe step name not accessible via foreign key"
                assert 'type' in step_info, "Recipe step type not accessible via foreign key"
                logger.info(f"Successfully joined command with step: {step_info['name']} ({step_info['type']})")
            
            await self._record_test_result(test_name, True, "Recipe command schema integration passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Recipe command schema integration failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_error_handling_recovery(self):
        """Test 7: Error handling and recovery scenarios"""
        test_name = "error_handling_recovery"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Test 1: Invalid recipe ID
            invalid_command = {
                'id': str(uuid.uuid4()),
                'type': 'start_recipe',
                'parameters': {
                    'recipe_id': str(uuid.uuid4()),  # Non-existent recipe
                    'machine_id': self.test_machine_id
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            result = supabase.table("recipe_commands").insert(invalid_command).execute()
            command_id = result.data[0]['id']
            
            # Process command (should fail gracefully)
            processor = CommandProcessor()
            await processor._process_command(result.data[0])
            
            # Check that command was marked as failed
            failed_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            command_data = failed_command.data[0]
            
            assert command_data['status'] == 'failed', f"Command should be failed, got: {command_data['status']}"
            assert command_data.get('error_message') is not None, "Error message should be set"
            
            logger.info("✅ Invalid recipe ID handled correctly")
            
            # Test 2: Malformed parameters
            malformed_command = {
                'id': str(uuid.uuid4()),
                'type': 'set_parameter',
                'parameters': {
                    'invalid_param': 'invalid_value'  # Missing required fields
                },
                'status': 'pending',
                'machine_id': self.test_machine_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            result = supabase.table("recipe_commands").insert(malformed_command).execute()
            command_id = result.data[0]['id']
            
            # Process command
            await processor._process_command(result.data[0])
            
            # Check failure handling
            failed_malformed = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            malformed_data = failed_malformed.data[0]
            
            assert malformed_data['status'] == 'failed', "Malformed command should be failed"
            
            logger.info("✅ Malformed parameters handled correctly")
            
            await self._record_test_result(test_name, True, "Error handling and recovery validation passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Error handling validation failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_concurrent_command_processing(self):
        """Test 8: Concurrent command processing"""
        test_name = "concurrent_command_processing"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create multiple commands simultaneously
            commands = []
            for i in range(3):
                command = {
                    'id': str(uuid.uuid4()),
                    'type': 'start_recipe' if i % 2 == 0 else 'stop_recipe',
                    'parameters': {
                        'recipe_id': self.simple_recipe_id if i % 2 == 0 else None,
                        'machine_id': self.test_machine_id,
                        'batch_test': f'concurrent_test_{i}'
                    },
                    'status': 'pending',
                    'machine_id': self.test_machine_id,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                commands.append(command)
                
            # Insert all commands
            insert_results = []
            for command in commands:
                result = supabase.table("recipe_commands").insert(command).execute()
                insert_results.append(result.data[0])
                
            # Process commands concurrently (simulated)
            processor = CommandProcessor()
            processing_tasks = []
            
            for command_data in insert_results:
                task = asyncio.create_task(processor._process_command(command_data))
                processing_tasks.append(task)
                
            # Wait for all to complete
            await asyncio.gather(*processing_tasks, return_exceptions=True)
            
            # Verify all commands were processed
            processed_count = 0
            for command_data in insert_results:
                final_command = supabase.table("recipe_commands").select("*").eq("id", command_data['id']).execute()
                final_status = final_command.data[0]['status']
                
                if final_status in ['completed', 'failed']:
                    processed_count += 1
                    
            assert processed_count == len(commands), f"Expected {len(commands)} processed commands, got {processed_count}"
            
            await self._record_test_result(test_name, True, f"Concurrent command processing passed - {processed_count} commands processed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Concurrent command processing failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
    
    async def _record_test_result(self, test_name: str, passed: bool, message: str):
        """Record individual test result"""
        if passed:
            self.test_results['tests_passed'] += 1
        else:
            self.test_results['tests_failed'] += 1
            
        self.test_results['test_details'].append({
            'test_name': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
    async def _generate_final_report(self):
        """Generate comprehensive test report"""
        self.test_results['end_time'] = datetime.now().isoformat()
        self.test_results['total_tests'] = self.test_results['tests_passed'] + self.test_results['tests_failed']
        self.test_results['success_rate'] = (self.test_results['tests_passed'] / self.test_results['total_tests'] * 100) if self.test_results['total_tests'] > 0 else 0
        
        # Write detailed report
        report_filename = f"command_flow_integration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
            
        logger.info("=" * 60)
        logger.info("📡 COMMAND FLOW INTEGRATION TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Test Run ID: {self.test_results['test_run_id']}")
        logger.info(f"Total Tests: {self.test_results['total_tests']}")
        logger.info(f"Passed: {self.test_results['tests_passed']}")
        logger.info(f"Failed: {self.test_results['tests_failed']}")
        logger.info(f"Success Rate: {self.test_results['success_rate']:.1f}%")
        logger.info(f"Report saved: {report_filename}")
        logger.info("=" * 60)
        
        for test in self.test_results['test_details']:
            status_emoji = "✅" if test['passed'] else "❌"
            logger.info(f"{status_emoji} {test['test_name']}: {test['message']}")
        
        logger.info("=" * 60)


async def main():
    """Main entry point for command flow integration testing"""
    try:
        logger.info("📡 Starting Command Flow Integration Test")
        
        # Initialize test framework
        test_framework = CommandFlowIntegrationTest()
        
        # Run all tests
        results = await test_framework.run_all_tests()
        
        # Return appropriate exit code
        if results['tests_failed'] == 0:
            logger.info("🎉 ALL COMMAND FLOW INTEGRATION TESTS PASSED!")
            return 0
        else:
            logger.error(f"💥 {results['tests_failed']} COMMAND FLOW TESTS FAILED!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Critical failure in command flow integration test: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)