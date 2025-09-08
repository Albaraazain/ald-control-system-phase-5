#!/usr/bin/env python3
"""
Valve Step Integration Test

Tests valve step execution with database integration including:
- Valve step configuration loading from valve_step_config table
- PLC valve operation calls in simulation mode
- Process execution state updates
- Valve-specific field updates (valve_number, duration_ms)
"""

import asyncio
import json
import uuid
from datetime import datetime

from db import get_supabase, get_current_timestamp
from step_flow.valve_step import execute_valve_step
from plc.manager import plc_manager
from log_setup import logger


class ValveStepIntegrationTest:
    """Integration test specifically for valve step execution."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.test_results = []
        
    async def setup_test_environment(self):
        """Set up test environment with simulation PLC."""
        logger.info("Setting up valve step test environment")
        
        # Initialize PLC in simulation mode
        plc_manager.initialize_simulation()
        
        # Create test recipe
        test_recipe = {
            'name': f'Valve Test Recipe {datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'description': 'Test recipe for valve step integration testing',
            'created_at': get_current_timestamp()
        }
        
        recipe_result = self.supabase.table('recipes').insert(test_recipe).execute()
        self.test_recipe_id = recipe_result.data[0]['id']
        
        # Create test process execution
        test_process = {
            'id': str(uuid.uuid4()),
            'recipe_id': self.test_recipe_id,
            'status': 'running',
            'started_at': get_current_timestamp(),
            'created_at': get_current_timestamp()
        }
        
        process_result = self.supabase.table('process_executions').insert(test_process).execute()
        self.test_process_id = process_result.data[0]['id']
        
        # Initialize process execution state
        initial_state = {
            'execution_id': self.test_process_id,
            'current_step_type': 'setup',
            'current_step_name': 'Valve Test Setup',
            'progress': {
                'total_steps': 0,
                'completed_steps': 0,
                'total_cycles': 0,
                'completed_cycles': 0
            },
            'last_updated': 'now()'
        }
        
        self.supabase.table('process_execution_state').insert(initial_state).execute()
        
    async def test_valve_config_loading(self):
        """Test valve step with valve_step_config table."""
        logger.info("Testing valve step with config table loading")
        
        try:
            # Create valve step
            valve_step_data = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Config Valve Test',
                'type': 'valve',
                'sequence_number': 1,
                'created_at': get_current_timestamp()
            }
            
            step_result = self.supabase.table('recipe_steps').insert(valve_step_data).execute()
            step_id = step_result.data[0]['id']
            
            # Create valve configuration
            valve_config = {
                'step_id': step_id,
                'valve_number': 3,
                'duration_ms': 4500,
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('valve_step_config').insert(valve_config).execute()
            
            # Execute valve step
            await execute_valve_step(self.test_process_id, valve_step_data)
            
            # Verify process execution state
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', self.test_process_id).single().execute()
            state = state_result.data
            
            # Validate valve-specific updates
            assert state['current_step_type'] == 'valve', f"Expected valve step type, got {state['current_step_type']}"
            assert state['current_step_name'] == 'Config Valve Test', f"Expected Config Valve Test, got {state['current_step_name']}"
            assert state['current_valve_number'] == 3, f"Expected valve number 3, got {state['current_valve_number']}"
            assert state['current_valve_duration_ms'] == 4500, f"Expected duration 4500, got {state['current_valve_duration_ms']}"
            
            self.test_results.append({
                'test': 'valve_config_loading',
                'status': 'PASS',
                'message': 'Valve step executed successfully with config table loading',
                'valve_number': 3,
                'duration_ms': 4500
            })
            logger.info("✅ Valve config loading test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'valve_config_loading',
                'status': 'FAIL',
                'message': f'Valve config loading test failed: {str(e)}'
            })
            logger.error(f"❌ Valve config loading test FAILED: {e}")
            
    async def cleanup_test_environment(self):
        """Clean up test data."""
        logger.info("Cleaning up valve step test environment")
        
        try:
            if hasattr(self, 'test_process_id'):
                self.supabase.table('process_execution_state').delete().eq('execution_id', self.test_process_id).execute()
                self.supabase.table('process_executions').delete().eq('id', self.test_process_id).execute()
                
            if hasattr(self, 'test_recipe_id'):
                # Delete step configs first
                steps_result = self.supabase.table('recipe_steps').select('id').eq('recipe_id', self.test_recipe_id).execute()
                for step in steps_result.data:
                    step_id = step['id']
                    self.supabase.table('valve_step_config').delete().eq('step_id', step_id).execute()
                
                # Delete steps and recipe
                self.supabase.table('recipe_steps').delete().eq('recipe_id', self.test_recipe_id).execute()
                self.supabase.table('recipes').delete().eq('id', self.test_recipe_id).execute()
                
        except Exception e:
            logger.error(f"Cleanup failed: {e}")
            
    async def run_all_tests(self):
        """Run all valve step integration tests."""
        logger.info("Starting Valve Step Integration Tests")
        
        try:
            await self.setup_test_environment()
            await self.test_valve_config_loading()
            
        finally:
            await self.cleanup_test_environment()
            
        # Generate summary
        passed_tests = len([t for t in self.test_results if t['status'] == 'PASS'])
        total_tests = len(self.test_results)
        
        logger.info(f"Valve Step Integration Tests Complete: {passed_tests}/{total_tests} PASSED")
        
        return {
            'test_type': 'valve_step_integration',
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'results': self.test_results,
            'timestamp': datetime.now().isoformat()
        }


async def main():
    """Run valve step integration tests."""
    test_runner = ValveStepIntegrationTest()
    results = await test_runner.run_all_tests()
    
    # Save results
    with open('valve_step_integration_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Valve Step Integration Tests Complete: {results['passed_tests']}/{results['total_tests']} PASSED")
    print("Results saved to valve_step_integration_test_results.json")
    
    return results['failed_tests'] == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)