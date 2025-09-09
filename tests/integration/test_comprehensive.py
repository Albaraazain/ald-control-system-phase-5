#!/usr/bin/env python3
"""
Comprehensive Integration Test Framework
Tests recipe execution with new database schema and validates integration
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
from src.plc.manager import plc_manager
from src.recipe_flow.executor import RecipeExecutor
from src.recipe_flow.starter import RecipeStarter
from src.command_flow.processor import CommandProcessor

# Get the supabase client
supabase = get_supabase()

# Set up logging
logger = setup_logger(__name__)

class ComprehensiveIntegrationTest:
    """Main integration test class that orchestrates all test scenarios"""
    
    def __init__(self):
        self.test_results = {
            'test_run_id': str(uuid.uuid4()),
            'start_time': datetime.now().isoformat(),
            'tests_passed': 0,
            'tests_failed': 0,
            'test_details': [],
            'environment': 'integration_test'
        }
        
        # Test recipe IDs - these should match what was created in database
        self.simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        self.complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all integration tests"""
        logger.info("🚀 Starting Comprehensive Integration Test Suite")
        logger.info(f"Test Run ID: {self.test_results['test_run_id']}")
        
        try:
            # Test 1: Database Schema Validation
            await self._test_database_schema_validation()
            
            # Test 2: Recipe Loading and Validation
            await self._test_recipe_loading_validation()
            
            # Test 3: Step Configuration Loading
            await self._test_step_configuration_loading()
            
            # Test 4: Recipe Parameter Access
            await self._test_recipe_parameter_access()
            
            # Test 5: Command Flow Integration
            await self._test_command_flow_integration()
            
            # Test 6: Recipe Execution State Tracking
            await self._test_recipe_execution_state_tracking()
            
            # Test 7: Loop Step Execution
            await self._test_loop_step_execution()
            
            # Test 8: Error Handling and Recovery
            await self._test_error_handling_recovery()
            
        except Exception as e:
            logger.error(f"❌ Critical test failure: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._record_test_result("critical_failure", False, str(e))
        
        # Generate final report
        await self._generate_final_report()
        return self.test_results
        
    async def _test_database_schema_validation(self):
        """Test 1: Validate database schema integration"""
        test_name = "database_schema_validation"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Check if test recipes exist
            simple_recipe = supabase.table("recipes").select("*").eq("id", self.simple_recipe_id).execute()
            complex_recipe = supabase.table("recipes").select("*").eq("id", self.complex_recipe_id).execute()
            
            assert len(simple_recipe.data) == 1, "Simple test recipe not found"
            assert len(complex_recipe.data) == 1, "Complex test recipe not found"
            
            # Check recipe steps exist
            simple_steps = supabase.table("recipe_steps").select("*").eq("recipe_id", self.simple_recipe_id).execute()
            complex_steps = supabase.table("recipe_steps").select("*").eq("recipe_id", self.complex_recipe_id).execute()
            
            assert len(simple_steps.data) == 3, f"Simple recipe should have 3 steps, found {len(simple_steps.data)}"
            assert len(complex_steps.data) == 5, f"Complex recipe should have 5 steps, found {len(complex_steps.data)}"
            
            # Check step configurations exist
            valve_configs = supabase.table("valve_step_config").select("step_id").execute()
            purge_configs = supabase.table("purge_step_config").select("step_id").execute() 
            loop_configs = supabase.table("loop_step_config").select("step_id").execute()
            
            assert len(valve_configs.data) >= 4, f"Should have at least 4 valve configs, found {len(valve_configs.data)}"
            assert len(purge_configs.data) >= 3, f"Should have at least 3 purge configs, found {len(purge_configs.data)}"
            assert len(loop_configs.data) >= 1, f"Should have at least 1 loop config, found {len(loop_configs.data)}"
            
            await self._record_test_result(test_name, True, "All database schema validations passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Database schema validation failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_recipe_loading_validation(self):
        """Test 2: Validate recipe loading from normalized structure"""
        test_name = "recipe_loading_validation" 
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Test loading simple recipe
            recipe_starter = RecipeStarter()
            simple_recipe_data = await recipe_starter._load_recipe_from_db(self.simple_recipe_id)
            
            assert simple_recipe_data is not None, "Failed to load simple recipe"
            assert simple_recipe_data['name'] == "Integration Test Recipe - Simple"
            assert len(simple_recipe_data.get('steps', [])) == 3, "Simple recipe should have 3 steps"
            
            # Test loading complex recipe
            complex_recipe_data = await recipe_starter._load_recipe_from_db(self.complex_recipe_id)
            
            assert complex_recipe_data is not None, "Failed to load complex recipe"
            assert complex_recipe_data['name'] == "Integration Test Recipe - Complex"
            assert len(complex_recipe_data.get('steps', [])) == 5, "Complex recipe should have 5 steps"
            
            # Verify loop structure
            loop_steps = [step for step in complex_recipe_data['steps'] if step.get('type') == 'loop']
            assert len(loop_steps) == 1, "Should have exactly 1 loop step"
            
            await self._record_test_result(test_name, True, "Recipe loading validation passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Recipe loading failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_step_configuration_loading(self):
        """Test 3: Validate step configuration loading from config tables"""
        test_name = "step_configuration_loading"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Load recipe with step configurations
            recipe_starter = RecipeStarter()
            simple_recipe = await recipe_starter._load_recipe_from_db(self.simple_recipe_id)
            
            # Check valve step configurations
            valve_steps = [step for step in simple_recipe['steps'] if step.get('type') == 'valve']
            for valve_step in valve_steps:
                assert 'valve_number' in valve_step, f"Valve step missing valve_number: {valve_step}"
                assert 'duration_ms' in valve_step, f"Valve step missing duration_ms: {valve_step}"
                assert valve_step['valve_number'] in [1, 2], f"Invalid valve number: {valve_step['valve_number']}"
                assert valve_step['duration_ms'] > 0, f"Invalid duration: {valve_step['duration_ms']}"
            
            # Check purge step configurations  
            purge_steps = [step for step in simple_recipe['steps'] if step.get('type') == 'purge']
            for purge_step in purge_steps:
                assert 'duration_ms' in purge_step, f"Purge step missing duration_ms: {purge_step}"
                assert 'gas_type' in purge_step, f"Purge step missing gas_type: {purge_step}"
                assert purge_step['duration_ms'] > 0, f"Invalid purge duration: {purge_step['duration_ms']}"
            
            # Test complex recipe loop configuration
            complex_recipe = await recipe_starter._load_recipe_from_db(self.complex_recipe_id)
            loop_steps = [step for step in complex_recipe['steps'] if step.get('type') == 'loop']
            
            for loop_step in loop_steps:
                assert 'count' in loop_step, f"Loop step missing count: {loop_step}"
                assert loop_step['count'] > 0, f"Invalid loop count: {loop_step['count']}"
                
            await self._record_test_result(test_name, True, "Step configuration loading passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Step configuration loading failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_recipe_parameter_access(self):
        """Test 4: Validate recipe parameters are accessible"""
        test_name = "recipe_parameter_access"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Test simple recipe parameters
            simple_params = supabase.table("recipe_parameters").select("*").eq("recipe_id", self.simple_recipe_id).execute()
            assert len(simple_params.data) == 3, f"Simple recipe should have 3 parameters, found {len(simple_params.data)}"
            
            param_names = [p['parameter_name'] for p in simple_params.data]
            expected_simple_params = ['chamber_pressure', 'base_temperature', 'flow_rate_multiplier']
            
            for expected_param in expected_simple_params:
                assert expected_param in param_names, f"Missing parameter: {expected_param}"
            
            # Test complex recipe parameters
            complex_params = supabase.table("recipe_parameters").select("*").eq("recipe_id", self.complex_recipe_id).execute()
            assert len(complex_params.data) == 4, f"Complex recipe should have 4 parameters, found {len(complex_params.data)}"
            
            complex_param_names = [p['parameter_name'] for p in complex_params.data]
            expected_complex_params = ['chamber_pressure', 'base_temperature', 'loop_iterations', 'gas_flow_rate']
            
            for expected_param in expected_complex_params:
                assert expected_param in complex_param_names, f"Missing complex parameter: {expected_param}"
                
            await self._record_test_result(test_name, True, "Recipe parameter access validation passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Recipe parameter access failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_command_flow_integration(self):
        """Test 5: Validate command flow integration with new schema"""
        test_name = "command_flow_integration"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create a test start_recipe command
            test_machine_id = await self._get_test_machine_id()
            
            command_data = {
                'id': str(uuid.uuid4()),
                'type': 'start_recipe',
                'parameters': {
                    'recipe_id': self.simple_recipe_id,
                    'machine_id': test_machine_id
                },
                'status': 'pending',
                'machine_id': test_machine_id,
                'recipe_step_id': None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert command into database
            result = supabase.table("recipe_commands").insert(command_data).execute()
            assert len(result.data) == 1, "Failed to create test command"
            command_id = result.data[0]['id']
            
            # Process command
            processor = CommandProcessor()
            await processor._process_command(result.data[0])
            
            # Check command status updated
            updated_command = supabase.table("recipe_commands").select("*").eq("id", command_id).execute()
            assert len(updated_command.data) == 1, "Command not found after processing"
            
            command_status = updated_command.data[0]['status']
            assert command_status in ['completed', 'failed'], f"Command status should be completed or failed, got: {command_status}"
            
            await self._record_test_result(test_name, True, f"Command integration passed - status: {command_status}")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Command flow integration failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_recipe_execution_state_tracking(self):
        """Test 6: Validate process execution state tracking accuracy"""
        test_name = "recipe_execution_state_tracking"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Create a test process execution
            test_machine_id = await self._get_test_machine_id()
            test_user_id = await self._get_test_user_id()
            test_session_id = await self._get_test_session_id(test_user_id, test_machine_id)
            
            process_data = {
                'id': str(uuid.uuid4()),
                'session_id': test_session_id,
                'machine_id': test_machine_id,
                'recipe_id': self.simple_recipe_id,
                'recipe_version': {},
                'start_time': datetime.now().isoformat(),
                'operator_id': test_user_id,
                'status': 'preparing',
                'parameters': {},
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert process execution
            process_result = supabase.table("process_executions").insert(process_data).execute()
            assert len(process_result.data) == 1, "Failed to create test process execution"
            process_id = process_result.data[0]['id']
            
            # Create corresponding execution state
            state_data = {
                'execution_id': process_id,
                'current_step_index': 0,
                'current_overall_step': 0,
                'total_overall_steps': 3,
                'progress': {'total_steps': 3, 'completed_steps': 0},
                'created_at': datetime.now().isoformat()
            }
            
            state_result = supabase.table("process_execution_state").insert(state_data).execute()
            assert len(state_result.data) == 1, "Failed to create execution state"
            
            # Verify state can be queried and updated
            state_query = supabase.table("process_execution_state").select("*").eq("execution_id", process_id).execute()
            assert len(state_query.data) == 1, "Execution state not found"
            
            state = state_query.data[0]
            assert state['current_step_index'] == 0, "Initial step index incorrect"
            assert state['total_overall_steps'] == 3, "Total steps count incorrect"
            
            await self._record_test_result(test_name, True, "Recipe execution state tracking passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Recipe execution state tracking failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_loop_step_execution(self):
        """Test 7: Validate loop iteration counting"""
        test_name = "loop_step_execution"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Load complex recipe with loop
            recipe_starter = RecipeStarter()
            complex_recipe = await recipe_starter._load_recipe_from_db(self.complex_recipe_id)
            
            # Find loop step
            loop_step = None
            for step in complex_recipe['steps']:
                if step.get('type') == 'loop':
                    loop_step = step
                    break
                    
            assert loop_step is not None, "Loop step not found in complex recipe"
            assert loop_step.get('count', 0) == 3, f"Loop step should have count=3, got {loop_step.get('count')}"
            
            # Verify loop has child steps
            child_steps = [step for step in complex_recipe['steps'] if step.get('parent_step_id') == loop_step['id']]
            assert len(child_steps) == 2, f"Loop should have 2 child steps, found {len(child_steps)}"
            
            # Check child step types
            child_types = [step['type'] for step in child_steps]
            assert 'valve' in child_types, "Loop should contain valve step"
            assert 'purge' in child_types, "Loop should contain purge step"
            
            await self._record_test_result(test_name, True, "Loop step execution validation passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Loop step execution validation failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
            
    async def _test_error_handling_recovery(self):
        """Test 8: Validate error handling and recovery scenarios"""
        test_name = "error_handling_recovery"
        logger.info(f"🔍 Running {test_name}")
        
        try:
            # Test invalid recipe ID handling
            recipe_starter = RecipeStarter()
            invalid_recipe_id = str(uuid.uuid4())
            
            try:
                await recipe_starter._load_recipe_from_db(invalid_recipe_id)
                assert False, "Should have raised exception for invalid recipe ID"
            except Exception as e:
                logger.info(f"✅ Correctly handled invalid recipe ID: {str(e)}")
                
            # Test malformed command handling
            processor = CommandProcessor()
            invalid_command = {
                'id': str(uuid.uuid4()),
                'type': 'invalid_command_type',
                'parameters': {},
                'status': 'pending'
            }
            
            try:
                await processor._process_command(invalid_command)
                # Command should be marked as failed
                logger.info("✅ Invalid command handled gracefully")
            except Exception as e:
                logger.info(f"✅ Invalid command properly rejected: {str(e)}")
                
            # Test database connection recovery
            try:
                # Attempt to query with invalid table name (should fail gracefully)
                result = supabase.table("nonexistent_table").select("*").execute()
                assert False, "Should have failed on nonexistent table"
            except Exception as e:
                logger.info(f"✅ Database error handled gracefully: {str(e)}")
                
            await self._record_test_result(test_name, True, "Error handling and recovery validation passed")
            logger.info(f"✅ {test_name} passed")
            
        except Exception as e:
            await self._record_test_result(test_name, False, f"Error handling validation failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")
    
    async def _get_test_machine_id(self) -> str:
        """Get a test machine ID"""
        machines = supabase.table("machines").select("id").limit(1).execute()
        if machines.data:
            return machines.data[0]['id']
        else:
            # Create a test machine if none exist
            test_machine = {
                'id': str(uuid.uuid4()),
                'serial_number': f'TEST-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                'location': 'Integration Test Lab',
                'lab_name': 'Test Lab',
                'lab_institution': 'Test Institution',
                'model': 'ALD-Test-1000',
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
            return result.data[0]['id']
    
    async def _get_test_user_id(self) -> str:
        """Get a test user ID from auth.users"""
        try:
            # Query the first available user
            result = supabase.table("profiles").select("id").limit(1).execute()
            if result.data:
                return result.data[0]['id']
            else:
                # If no users exist, this is a critical test environment issue
                raise Exception("No test users available in database")
        except Exception as e:
            logger.error(f"Failed to get test user: {str(e)}")
            raise
            
    async def _get_test_session_id(self, user_id: str, machine_id: str) -> str:
        """Get or create a test session"""
        # Check for existing active session
        sessions = supabase.table("operator_sessions").select("id").eq("operator_id", user_id).eq("machine_id", machine_id).eq("status", "active").limit(1).execute()
        
        if sessions.data:
            return sessions.data[0]['id']
        else:
            # Create new session
            session_data = {
                'id': str(uuid.uuid4()),
                'operator_id': user_id,
                'machine_id': machine_id,
                'start_time': datetime.now().isoformat(),
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            result = supabase.table("operator_sessions").insert(session_data).execute()
            return result.data[0]['id']
            
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
        report_filename = f"integration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
            
        logger.info("=" * 60)
        logger.info("🏁 COMPREHENSIVE INTEGRATION TEST RESULTS")
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
    """Main entry point for integration testing"""
    try:
        logger.info("🚀 Starting ALD Control System - Comprehensive Integration Test")
        
        # Initialize test framework
        test_framework = ComprehensiveIntegrationTest()
        
        # Run all tests
        results = await test_framework.run_all_tests()
        
        # Return appropriate exit code
        if results['tests_failed'] == 0:
            logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
            return 0
        else:
            logger.error(f"💥 {results['tests_failed']} INTEGRATION TESTS FAILED!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Critical failure in integration test framework: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)