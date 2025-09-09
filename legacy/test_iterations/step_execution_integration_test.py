#!/usr/bin/env python3
"""
Comprehensive Step Execution Integration Test

Tests step execution with the new database schema including:
- Valve step execution with valve_step_config loading
- Purge step execution with purge_step_config loading  
- Loop step execution with loop_step_config and child steps
- Process execution state updates during step execution
- Step-specific database field updates
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any

from db import get_supabase, get_current_timestamp
from step_flow.valve_step import execute_valve_step
from step_flow.purge_step import execute_purge_step
from step_flow.loop_step import execute_loop_step
from plc.manager import plc_manager
from log_setup import logger


class StepExecutionIntegrationTest:
    """Comprehensive integration test for step execution with database schema."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.test_results = []
        self.test_process_id = None
        self.test_recipe_id = None
        
    async def setup_test_environment(self):
        """Set up test environment with simulation PLC and test data."""
        logger.info("Setting up test environment")
        
        # Initialize PLC in simulation mode
        plc_manager.initialize_simulation()
        
        # Create test recipe
        test_recipe = {
            'name': f'Integration Test Recipe {datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'description': 'Test recipe for step execution integration testing',
            'created_at': get_current_timestamp()
        }
        
        recipe_result = self.supabase.table('recipes').insert(test_recipe).execute()
        self.test_recipe_id = recipe_result.data[0]['id']
        logger.info(f"Created test recipe: {self.test_recipe_id}")
        
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
        logger.info(f"Created test process: {self.test_process_id}")
        
        # Initialize process execution state
        initial_state = {
            'execution_id': self.test_process_id,
            'current_step_type': 'setup',
            'current_step_name': 'Test Setup',
            'progress': {
                'total_steps': 0,
                'completed_steps': 0,
                'total_cycles': 0,
                'completed_cycles': 0
            },
            'last_updated': 'now()'
        }
        
        self.supabase.table('process_execution_state').insert(initial_state).execute()
        logger.info("Initialized process execution state")
        
    async def test_valve_step_execution(self):
        """Test valve step execution with valve_step_config loading."""
        logger.info("Testing valve step execution")
        
        try:
            # Create test valve step
            valve_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Test Valve Step',
                'type': 'valve',
                'sequence_number': 1,
                'created_at': get_current_timestamp()
            }
            
            step_result = self.supabase.table('recipe_steps').insert(valve_step).execute()
            step_id = step_result.data[0]['id']
            
            # Create valve step configuration
            valve_config = {
                'step_id': step_id,
                'valve_number': 2,
                'duration_ms': 3000,
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('valve_step_config').insert(valve_config).execute()
            
            # Execute valve step
            await execute_valve_step(self.test_process_id, valve_step)
            
            # Verify process execution state was updated
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', self.test_process_id).single().execute()
            state = state_result.data
            
            # Check valve-specific fields
            assert state['current_step_type'] == 'valve', f"Expected valve step type, got {state['current_step_type']}"
            assert state['current_step_name'] == 'Test Valve Step', f"Expected Test Valve Step, got {state['current_step_name']}"
            assert state['current_valve_number'] == 2, f"Expected valve number 2, got {state['current_valve_number']}"
            assert state['current_valve_duration_ms'] == 3000, f"Expected duration 3000, got {state['current_valve_duration_ms']}"
            
            self.test_results.append({
                'test': 'valve_step_execution',
                'status': 'PASS',
                'message': 'Valve step executed successfully with config loading'
            })
            logger.info("✅ Valve step execution test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'valve_step_execution',
                'status': 'FAIL',
                'message': f'Valve step execution failed: {str(e)}'
            })
            logger.error(f"❌ Valve step execution test FAILED: {e}")
            
    async def test_purge_step_execution(self):
        """Test purge step execution with purge_step_config loading."""
        logger.info("Testing purge step execution")
        
        try:
            # Create test purge step
            purge_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Test Purge Step',
                'type': 'purge',
                'sequence_number': 2,
                'created_at': get_current_timestamp()
            }
            
            step_result = self.supabase.table('recipe_steps').insert(purge_step).execute()
            step_id = step_result.data[0]['id']
            
            # Create purge step configuration
            purge_config = {
                'step_id': step_id,
                'duration_ms': 5000,
                'gas_type': 'N2',
                'flow_rate': 100.5,
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('purge_step_config').insert(purge_config).execute()
            
            # Execute purge step
            await execute_purge_step(self.test_process_id, purge_step)
            
            # Verify process execution state was updated
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', self.test_process_id).single().execute()
            state = state_result.data
            
            # Check purge-specific fields
            assert state['current_step_type'] == 'purge', f"Expected purge step type, got {state['current_step_type']}"
            assert state['current_step_name'] == 'Test Purge Step', f"Expected Test Purge Step, got {state['current_step_name']}"
            assert state['current_purge_duration_ms'] == 5000, f"Expected duration 5000, got {state['current_purge_duration_ms']}"
            
            self.test_results.append({
                'test': 'purge_step_execution',
                'status': 'PASS',
                'message': 'Purge step executed successfully with config loading'
            })
            logger.info("✅ Purge step execution test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'purge_step_execution',
                'status': 'FAIL',
                'message': f'Purge step execution failed: {str(e)}'
            })
            logger.error(f"❌ Purge step execution test FAILED: {e}")
            
    async def test_loop_step_execution(self):
        """Test loop step execution with loop_step_config and child steps."""
        logger.info("Testing loop step execution")
        
        try:
            # Create test loop step
            loop_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Test Loop Step',
                'type': 'loop',
                'sequence_number': 3,
                'created_at': get_current_timestamp()
            }
            
            step_result = self.supabase.table('recipe_steps').insert(loop_step).execute()
            loop_step_id = step_result.data[0]['id']
            
            # Create loop step configuration
            loop_config = {
                'step_id': loop_step_id,
                'iteration_count': 2,
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('loop_step_config').insert(loop_config).execute()
            
            # Create child steps
            child_valve_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Loop Child Valve',
                'type': 'valve',
                'sequence_number': 1,
                'parent_step_id': loop_step_id,
                'created_at': get_current_timestamp()
            }
            
            child_purge_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Loop Child Purge',
                'type': 'purge',
                'sequence_number': 2,
                'parent_step_id': loop_step_id,
                'created_at': get_current_timestamp()
            }
            
            child_valve_result = self.supabase.table('recipe_steps').insert(child_valve_step).execute()
            child_purge_result = self.supabase.table('recipe_steps').insert(child_purge_step).execute()
            
            child_valve_id = child_valve_result.data[0]['id']
            child_purge_id = child_purge_result.data[0]['id']
            
            # Create configs for child steps
            child_valve_config = {
                'step_id': child_valve_id,
                'valve_number': 3,
                'duration_ms': 1500,
                'created_at': get_current_timestamp()
            }
            
            child_purge_config = {
                'step_id': child_purge_id,
                'duration_ms': 2000,
                'gas_type': 'Ar',
                'flow_rate': 75.0,
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('valve_step_config').insert(child_valve_config).execute()
            self.supabase.table('purge_step_config').insert(child_purge_config).execute()
            
            # Prepare data structures for loop execution
            all_steps = [child_valve_step, child_purge_step]
            parent_to_child_steps = {
                loop_step_id: [
                    {
                        'id': child_valve_id,
                        'name': 'Loop Child Valve',
                        'type': 'valve',
                        'parameters': {'valve_number': 3, 'duration_ms': 1500}
                    },
                    {
                        'id': child_purge_id,
                        'name': 'Loop Child Purge',
                        'type': 'purge',
                        'parameters': {'duration_ms': 2000}
                    }
                ]
            }
            
            # Execute loop step
            await execute_loop_step(self.test_process_id, loop_step, all_steps, parent_to_child_steps)
            
            # Verify process execution state was updated
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', self.test_process_id).single().execute()
            state = state_result.data
            
            # Check loop-specific fields
            assert state['current_loop_count'] == 2, f"Expected loop count 2, got {state['current_loop_count']}"
            assert state['progress']['total_cycles'] >= 2, f"Expected at least 2 total cycles, got {state['progress']['total_cycles']}"
            assert state['progress']['completed_cycles'] >= 2, f"Expected at least 2 completed cycles, got {state['progress']['completed_cycles']}"
            
            self.test_results.append({
                'test': 'loop_step_execution',
                'status': 'PASS',
                'message': 'Loop step executed successfully with child steps'
            })
            logger.info("✅ Loop step execution test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'loop_step_execution',
                'status': 'FAIL',
                'message': f'Loop step execution failed: {str(e)}'
            })
            logger.error(f"❌ Loop step execution test FAILED: {e}")
            
    async def test_backwards_compatibility(self):
        """Test step execution when configuration tables are missing (fallback to parameters)."""
        logger.info("Testing backwards compatibility")
        
        try:
            # Create valve step WITHOUT valve_step_config (should fallback to parameters)
            fallback_valve_step = {
                'id': str(uuid.uuid4()),
                'recipe_id': self.test_recipe_id,
                'name': 'Fallback Valve Step',
                'type': 'open valve 4',
                'sequence_number': 4,
                'parameters': {
                    'valve_number': 4,
                    'duration_ms': 2500
                },
                'created_at': get_current_timestamp()
            }
            
            self.supabase.table('recipe_steps').insert(fallback_valve_step).execute()
            
            # Execute valve step (should use fallback)
            await execute_valve_step(self.test_process_id, fallback_valve_step)
            
            # Verify process execution state was updated
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', self.test_process_id).single().execute()
            state = state_result.data
            
            # Check that fallback worked
            assert state['current_valve_number'] == 4, f"Expected valve number 4, got {state['current_valve_number']}"
            assert state['current_valve_duration_ms'] == 2500, f"Expected duration 2500, got {state['current_valve_duration_ms']}"
            
            self.test_results.append({
                'test': 'backwards_compatibility',
                'status': 'PASS',
                'message': 'Backwards compatibility test passed - fallback to parameters worked'
            })
            logger.info("✅ Backwards compatibility test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'backwards_compatibility',
                'status': 'FAIL',
                'message': f'Backwards compatibility test failed: {str(e)}'
            })
            logger.error(f"❌ Backwards compatibility test FAILED: {e}")
            
    async def test_progress_tracking(self):
        """Test progress tracking accuracy during step execution."""
        logger.info("Testing progress tracking")
        
        try:
            # Reset progress for clean test
            self.supabase.table('process_execution_state').update({
                'progress': {
                    'total_steps': 0,
                    'completed_steps': 0,
                    'total_cycles': 0,
                    'completed_cycles': 0
                },
                'last_updated': 'now()'
            }).eq('execution_id', self.test_process_id).execute()
            
            # Create a simple sequence of steps
            steps = []
            for i in range(3):
                step = {
                    'id': str(uuid.uuid4()),
                    'recipe_id': self.test_recipe_id,
                    'name': f'Progress Test Step {i+1}',
                    'type': 'valve',
                    'sequence_number': i + 10,
                    'created_at': get_current_timestamp()
                }
                
                result = self.supabase.table('recipe_steps').insert(step).execute()
                step_id = result.data[0]['id']
                steps.append((step_id, step))
                
                # Create valve config
                config = {
                    'step_id': step_id,
                    'valve_number': i + 1,
                    'duration_ms': 1000,
                    'created_at': get_current_timestamp()
                }
                self.supabase.table('valve_step_config').insert(config).execute()
            
            # Execute steps and track progress
            for step_id, step in steps:
                await execute_valve_step(self.test_process_id, step)
                
                # Check progress after each step
                state_result = self.supabase.table('process_execution_state').select('progress').eq('execution_id', self.test_process_id).single().execute()
                progress = state_result.data['progress']
                
                logger.info(f"Progress after step {step['name']}: {progress}")
            
            self.test_results.append({
                'test': 'progress_tracking',
                'status': 'PASS',
                'message': 'Progress tracking test completed successfully'
            })
            logger.info("✅ Progress tracking test PASSED")
            
        except Exception as e:
            self.test_results.append({
                'test': 'progress_tracking',
                'status': 'FAIL',
                'message': f'Progress tracking test failed: {str(e)}'
            })
            logger.error(f"❌ Progress tracking test FAILED: {e}")
            
    async def cleanup_test_environment(self):
        """Clean up test data after tests complete."""
        logger.info("Cleaning up test environment")
        
        try:
            # Delete test data
            if self.test_process_id:
                self.supabase.table('process_execution_state').delete().eq('execution_id', self.test_process_id).execute()
                self.supabase.table('process_executions').delete().eq('id', self.test_process_id).execute()
                
            if self.test_recipe_id:
                # Delete step configs first
                steps_result = self.supabase.table('recipe_steps').select('id').eq('recipe_id', self.test_recipe_id).execute()
                for step in steps_result.data:
                    step_id = step['id']
                    self.supabase.table('valve_step_config').delete().eq('step_id', step_id).execute()
                    self.supabase.table('purge_step_config').delete().eq('step_id', step_id).execute()
                    self.supabase.table('loop_step_config').delete().eq('step_id', step_id).execute()
                
                # Delete steps and recipe
                self.supabase.table('recipe_steps').delete().eq('recipe_id', self.test_recipe_id).execute()
                self.supabase.table('recipes').delete().eq('id', self.test_recipe_id).execute()
                
            logger.info("Test environment cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            
    async def run_all_tests(self):
        """Run all step execution integration tests."""
        logger.info("Starting Step Execution Integration Tests")
        
        try:
            await self.setup_test_environment()
            
            # Run individual tests
            await self.test_valve_step_execution()
            await self.test_purge_step_execution()
            await self.test_loop_step_execution()
            await self.test_backwards_compatibility()
            await self.test_progress_tracking()
            
        finally:
            await self.cleanup_test_environment()
            
        # Generate summary
        passed_tests = len([t for t in self.test_results if t['status'] == 'PASS'])
        total_tests = len(self.test_results)
        
        logger.info(f"Step Execution Integration Tests Complete: {passed_tests}/{total_tests} PASSED")
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'results': self.test_results,
            'timestamp': datetime.now().isoformat()
        }


async def main():
    """Run step execution integration tests."""
    test_runner = StepExecutionIntegrationTest()
    results = await test_runner.run_all_tests()
    
    # Save results to file
    with open('step_execution_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"Step Execution Integration Tests Complete: {results['passed_tests']}/{results['total_tests']} PASSED")
    print(f"Results saved to step_execution_test_results.json")
    
    return results['failed_tests'] == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)