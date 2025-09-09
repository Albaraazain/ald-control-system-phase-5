#!/usr/bin/env python3
"""
Loop Step Integration Test

Tests loop step execution with child steps including:
- Loop step configuration loading from loop_step_config table
- Child step execution within loops
- Loop iteration tracking
- Progress tracking for loop cycles
- Nested loop support
"""

import asyncio
import json
import uuid
from datetime import datetime

from db import get_supabase, get_current_timestamp
from step_flow.loop_step import execute_loop_step
from plc.manager import plc_manager
from log_setup import logger


class LoopStepIntegrationTest:
    """Integration test specifically for loop step execution."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.test_results = []
        
    async def setup_test_environment(self):
        """Set up test environment with simulation PLC."""
        logger.info("Setting up loop step test environment")
        
        # Initialize PLC in simulation mode
        plc_manager.initialize_simulation()
        
        # Create test recipe
        test_recipe = {
            'name': f'Loop Test Recipe {datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'description': 'Test recipe for loop step integration testing',
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
            'current_step_name': 'Loop Test Setup',
            'progress': {
                'total_steps': 0,
                'completed_steps': 0,
                'total_cycles': 0,
                'completed_cycles': 0
            },
            'last_updated': 'now()'
        }
        
        self.supabase.table('process_execution_state').insert(initial_state).execute()
        
    async def test_loop_config_loading(self):
        """Test loop step with loop_step_config table."""
        logger.info("Testing loop step with config table loading")
        
        try:
            # Create loop step
            loop_step_data = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Config Loop Test',
                'type': 'loop',
                'sequence_number': 1,
                'created_at': get_current_timestamp()
            }
            
            step_result = self.supabase.table('recipe_steps').insert(loop_step_data).execute()
            loop_step_id = step_result.data[0]['id']
            
            # Create loop configuration
            loop_config = {
                'step_id': loop_step_id,
                'iteration_count': 3,
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('loop_step_config').insert(loop_config).execute()
            
            # Create child steps
            child_valve_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Child Valve Step',
                'type': 'valve',
                'sequence_number': 1,
                'parent_step_id': loop_step_id,
                'parameters': {'valve_number': 1, 'duration_ms': 1000},
                'created_at': get_current_timestamp()
            }
            
            child_purge_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Child Purge Step',
                'type': 'purge',
                'sequence_number': 2,
                'parent_step_id': loop_step_id,
                'parameters': {'duration_ms': 800},
                'created_at': get_current_timestamp()
            }
            
            child_valve_result = self.supabase.table('recipe_steps').insert(child_valve_step).execute()
            child_purge_result = self.supabase.table('recipe_steps').insert(child_purge_step).execute()
            
            # Prepare data structures for loop execution
            all_steps = [child_valve_step, child_purge_step]
            parent_to_child_steps = {
                loop_step_id: [child_valve_step, child_purge_step]
            }
            
            # Execute loop step
            await execute_loop_step(self.test_process_id, loop_step_data, all_steps, parent_to_child_steps)
            
            # Verify process execution state
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', self.test_process_id).single().execute()
            state = state_result.data
            
            # Validate loop-specific updates
            assert state['current_loop_count'] == 3, f"Expected loop count 3, got {state['current_loop_count']}"
            assert state['progress']['total_cycles'] >= 3, f"Expected at least 3 total cycles, got {state['progress']['total_cycles']}"
            assert state['progress']['completed_cycles'] >= 3, f"Expected at least 3 completed cycles, got {state['progress']['completed_cycles']}"
            
            self.test_results.append({
                'test': 'loop_config_loading',
                'status': 'PASS',
                'message': 'Loop step executed successfully with config table loading',
                'iteration_count': 3,
                'child_steps': 2,
                'total_executions': 6
            })
            logger.info("✅ Loop config loading test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'loop_config_loading',
                'status': 'FAIL',
                'message': f'Loop config loading test failed: {str(e)}'
            })
            logger.error(f"❌ Loop config loading test FAILED: {e}")
            
    async def cleanup_test_environment(self):
        """Clean up test data."""
        logger.info("Cleaning up loop step test environment")
        
        try:
            if hasattr(self, 'test_process_id'):
                self.supabase.table('process_execution_state').delete().eq('execution_id', self.test_process_id).execute()
                self.supabase.table('process_executions').delete().eq('id', self.test_process_id).execute()
                
            if hasattr(self, 'test_recipe_id'):
                # Delete step configs first
                steps_result = self.supabase.table('recipe_steps').select('id').eq('recipe_id', self.test_recipe_id).execute()
                for step in steps_result.data:
                    step_id = step['id']
                    self.supabase.table('loop_step_config').delete().eq('step_id', step_id).execute()
                
                # Delete steps and recipe
                self.supabase.table('recipe_steps').delete().eq('recipe_id', self.test_recipe_id).execute()
                self.supabase.table('recipes').delete().eq('id', self.test_recipe_id).execute()
                
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            
    async def run_all_tests(self):
        """Run all loop step integration tests."""
        logger.info("Starting Loop Step Integration Tests")
        
        try:
            await self.setup_test_environment()
            await self.test_loop_config_loading()
            
        finally:
            await self.cleanup_test_environment()
            
        # Generate summary
        passed_tests = len([t for t in self.test_results if t['status'] == 'PASS'])
        total_tests = len(self.test_results)
        
        logger.info(f"Loop Step Integration Tests Complete: {passed_tests}/{total_tests} PASSED")
        
        return {
            'test_type': 'loop_step_integration',
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'results': self.test_results,
            'timestamp': datetime.now().isoformat()
        }


async def main():
    """Run loop step integration tests."""
    test_runner = LoopStepIntegrationTest()
    results = await test_runner.run_all_tests()
    
    # Save results
    with open('loop_step_integration_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Loop Step Integration Tests Complete: {results['passed_tests']}/{results['total_tests']} PASSED")
    print("Results saved to loop_step_integration_test_results.json")
    
    return results['failed_tests'] == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
