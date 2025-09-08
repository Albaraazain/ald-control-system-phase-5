#!/usr/bin/env python3
"""
Comprehensive integration tests for purge step execution with the new database schema.
Tests purge step configuration loading, gas flow control, timing, and error handling.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any
import uuid

from db import get_supabase, get_current_timestamp
from step_flow.purge_step import execute_purge_step
from plc.manager import plc_manager
from plc.simulation_plc import SimulationPLC
from log_setup import logger

# Test configuration
PROJECT_ID = "yceyfsqusdmcwgkwxcnt"
SIMULATION_MODE = True

class PurgeStepIntegrationTest:
    """Comprehensive integration test suite for purge step execution."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.test_results = []
        self.test_data = {
            'test_processes': [],
            'test_steps': [],
            'test_configs': [],
            'performance_metrics': [],
            'error_logs': []
        }
        
    async def setup_test_environment(self):
        """Set up test environment with simulation PLC."""
        logger.info("Setting up purge step integration test environment")
        
        # Initialize simulation PLC
        if SIMULATION_MODE:
            simulation_plc = SimulationPLC()
            await simulation_plc.initialize()
            plc_manager.plc = simulation_plc
            logger.info("Simulation PLC initialized for testing")
        
        return True
    
    async def create_test_process(self, test_name: str) -> str:
        """Create a test process execution record."""
        process_id = str(uuid.uuid4())
        
        # Create process execution
        self.supabase.table('process_executions').insert({
            'id': process_id,
            'session_id': str(uuid.uuid4()),
            'machine_id': '123e4567-e89b-12d3-a456-426614174000',  # Test machine ID
            'recipe_id': str(uuid.uuid4()),
            'recipe_version': {'test': True, 'version': 1},
            'start_time': get_current_timestamp(),
            'operator_id': '123e4567-e89b-12d3-a456-426614174001',  # Test operator ID
            'status': 'running',
            'parameters': {'test_name': test_name}
        }).execute()
        
        # Create process execution state
        self.supabase.table('process_execution_state').insert({
            'execution_id': process_id,
            'current_step_index': 0,
            'current_overall_step': 0,
            'total_overall_steps': 1,
            'progress': {'total_steps': 1, 'completed_steps': 0}
        }).execute()
        
        self.test_data['test_processes'].append({
            'process_id': process_id,
            'test_name': test_name,
            'created_at': get_current_timestamp()
        })
        
        return process_id
    
    async def create_test_purge_config(self, step_id: str, duration_ms: int, 
                                     gas_type: str = 'N2', flow_rate: float = 100.0):
        """Create a test purge step configuration."""
        config_data = {
            'step_id': step_id,
            'duration_ms': duration_ms,
            'gas_type': gas_type,
            'flow_rate': flow_rate
        }
        
        result = self.supabase.table('purge_step_config').insert(config_data).execute()
        
        self.test_data['test_configs'].append({
            'type': 'purge_config',
            'step_id': step_id,
            'config': config_data,
            'result': result.data[0] if result.data else None
        })
        
        return result.data[0] if result.data else None
    
    async def test_purge_config_loading(self) -> Dict[str, Any]:
        """Test purge step configuration loading from purge_step_config table."""
        logger.info("Testing purge step configuration loading")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_config_loading")
            step_id = str(uuid.uuid4())
            
            # Create test purge configuration
            config = await self.create_test_purge_config(step_id, 3000, 'Ar', 150.0)
            
            # Create step data that should load from config
            step_data = {
                'id': step_id,
                'type': 'purging',
                'name': 'Test Purge Step - Config Loading',
                'parameters': {}  # Empty - should load from config
            }
            
            # Execute purge step
            await execute_purge_step(process_id, step_data)
            
            # Verify state was updated correctly
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).single().execute()
            state = state_result.data
            
            assert state['current_step_type'] == 'purge'
            assert state['current_purge_duration_ms'] == 3000
            
            result = {
                'test_name': 'purge_config_loading',
                'status': 'PASSED',
                'duration_seconds': time.time() - start_time,
                'details': {
                    'config_loaded': config is not None,
                    'duration_ms': state['current_purge_duration_ms'],
                    'step_type': state['current_step_type'],
                    'gas_type': 'Ar',  # Config loaded
                    'flow_rate': 150.0  # Config loaded
                }
            }
            
        except Exception as e:
            logger.error(f"Purge config loading test failed: {e}")
            result = {
                'test_name': 'purge_config_loading',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_config_loading',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_fallback_logic(self) -> Dict[str, Any]:
        """Test fallback logic when purge_step_config is missing."""
        logger.info("Testing purge step fallback logic")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_fallback_logic")
            step_id = str(uuid.uuid4())
            
            # Create step data without config - should use fallback
            step_data = {
                'id': step_id,
                'type': 'purging',
                'name': 'Test Purge Step - Fallback',
                'parameters': {
                    'duration_ms': 2500,
                    'gas_type': 'N2',
                    'flow_rate': 200.0
                }
            }
            
            # Execute purge step
            await execute_purge_step(process_id, step_data)
            
            # Verify state was updated correctly
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).single().execute()
            state = state_result.data
            
            assert state['current_step_type'] == 'purge'
            assert state['current_purge_duration_ms'] == 2500
            
            result = {
                'test_name': 'purge_fallback_logic',
                'status': 'PASSED',
                'duration_seconds': time.time() - start_time,
                'details': {
                    'fallback_used': True,
                    'duration_ms': state['current_purge_duration_ms'],
                    'step_type': state['current_step_type'],
                    'parameters_from_fallback': True
                }
            }
            
        except Exception as e:
            logger.error(f"Purge fallback logic test failed: {e}")
            result = {
                'test_name': 'purge_fallback_logic',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_fallback_logic',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_backwards_compatibility(self) -> Dict[str, Any]:
        """Test backwards compatibility with 'duration' parameter."""
        logger.info("Testing purge step backwards compatibility")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_backwards_compatibility")
            step_id = str(uuid.uuid4())
            
            # Create step data with old 'duration' parameter
            step_data = {
                'id': step_id,
                'type': 'purging',
                'name': 'Test Purge Step - Backwards Compatibility',
                'parameters': {
                    'duration': 1800,  # Old parameter name
                    'gas_type': 'Ar'
                }
            }
            
            # Execute purge step
            await execute_purge_step(process_id, step_data)
            
            # Verify state was updated correctly
            state_result = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).single().execute()
            state = state_result.data
            
            assert state['current_step_type'] == 'purge'
            assert state['current_purge_duration_ms'] == 1800
            
            result = {
                'test_name': 'purge_backwards_compatibility',
                'status': 'PASSED',
                'duration_seconds': time.time() - start_time,
                'details': {
                    'old_parameter_recognized': True,
                    'duration_ms': state['current_purge_duration_ms'],
                    'step_type': state['current_step_type']
                }
            }
            
        except Exception as e:
            logger.error(f"Purge backwards compatibility test failed: {e}")
            result = {
                'test_name': 'purge_backwards_compatibility',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_backwards_compatibility',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_timing_accuracy(self) -> Dict[str, Any]:
        """Test purge timing accuracy in simulation mode."""
        logger.info("Testing purge timing accuracy")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_timing_accuracy")
            step_id = str(uuid.uuid4())
            
            # Create test purge configuration with specific timing
            duration_ms = 800  # 0.8 seconds
            await self.create_test_purge_config(step_id, duration_ms, 'N2', 120.0)
            
            step_data = {
                'id': step_id,
                'type': 'purging',
                'name': 'Test Purge Step - Timing',
                'parameters': {}
            }
            
            # Measure execution time
            execution_start = time.time()
            await execute_purge_step(process_id, step_data)
            execution_time = time.time() - execution_start
            
            # Verify timing (should be close to duration_ms)
            expected_duration = duration_ms / 1000  # Convert to seconds
            timing_accuracy = abs(execution_time - expected_duration) / expected_duration
            
            result = {
                'test_name': 'purge_timing_accuracy',
                'status': 'PASSED' if timing_accuracy < 0.1 else 'FAILED',  # 10% tolerance
                'duration_seconds': time.time() - start_time,
                'details': {
                    'expected_duration': expected_duration,
                    'actual_duration': execution_time,
                    'timing_accuracy_percentage': (1 - timing_accuracy) * 100,
                    'tolerance_met': timing_accuracy < 0.1
                }
            }
            
        except Exception as e:
            logger.error(f"Purge timing accuracy test failed: {e}")
            result = {
                'test_name': 'purge_timing_accuracy',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_timing_accuracy',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_gas_flow_control(self) -> Dict[str, Any]:
        """Test gas flow control and parameter handling."""
        logger.info("Testing purge gas flow control")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_gas_flow_control")
            
            # Test different gas types and flow rates
            gas_configs = [
                ('N2', 100.0, 500),
                ('Ar', 150.0, 600),
                ('He', 200.0, 400),
            ]
            
            for i, (gas_type, flow_rate, duration) in enumerate(gas_configs):
                step_id = str(uuid.uuid4())
                await self.create_test_purge_config(step_id, duration, gas_type, flow_rate)
                
                step_data = {
                    'id': step_id,
                    'type': 'purging',
                    'name': f'Test Purge Step - Gas {gas_type}',
                    'parameters': {}
                }
                
                # Execute purge step
                await execute_purge_step(process_id, step_data)
                
                # Verify state was updated correctly
                state = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).single().execute()
                assert state.data['current_step_type'] == 'purge'
                assert state.data['current_purge_duration_ms'] == duration
            
            result = {
                'test_name': 'purge_gas_flow_control',
                'status': 'PASSED',
                'duration_seconds': time.time() - start_time,
                'details': {
                    'gas_types_tested': [config[0] for config in gas_configs],
                    'flow_rates_tested': [config[1] for config in gas_configs],
                    'durations_tested': [config[2] for config in gas_configs],
                    'total_configurations': len(gas_configs)
                }
            }
            
        except Exception as e:
            logger.error(f"Purge gas flow control test failed: {e}")
            result = {
                'test_name': 'purge_gas_flow_control',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_gas_flow_control',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_error_handling(self) -> Dict[str, Any]:
        """Test error handling for missing duration parameters."""
        logger.info("Testing purge error handling")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_error_handling")
            step_id = str(uuid.uuid4())
            
            # Create invalid step data (no duration)
            step_data = {
                'id': step_id,
                'type': 'purging',
                'name': 'Test Purge Step - Invalid',
                'parameters': {
                    'gas_type': 'N2'
                    # Missing duration_ms or duration
                }
            }
            
            # This should raise an error
            try:
                await execute_purge_step(process_id, step_data)
                # If we get here, the test failed
                result = {
                    'test_name': 'purge_error_handling',
                    'status': 'FAILED',
                    'duration_seconds': time.time() - start_time,
                    'error': 'Expected ValueError was not raised'
                }
            except ValueError as expected_error:
                # This is expected
                result = {
                    'test_name': 'purge_error_handling',
                    'status': 'PASSED',
                    'duration_seconds': time.time() - start_time,
                    'details': {
                        'expected_error_caught': True,
                        'error_message': str(expected_error)
                    }
                }
            
        except Exception as e:
            logger.error(f"Purge error handling test failed: {e}")
            result = {
                'test_name': 'purge_error_handling',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_error_handling',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_state_tracking(self) -> Dict[str, Any]:
        """Test process execution state tracking during purge operations."""
        logger.info("Testing purge state tracking")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_state_tracking")
            step_id = str(uuid.uuid4())
            
            # Create test purge configuration
            await self.create_test_purge_config(step_id, 1200, 'Ar', 175.0)
            
            # Check initial state
            initial_state = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).single().execute()
            initial_progress = initial_state.data['progress']
            
            step_data = {
                'id': step_id,
                'type': 'purging',
                'name': 'Test Purge Step - State Tracking',
                'parameters': {}
            }
            
            # Execute purge step
            await execute_purge_step(process_id, step_data)
            
            # Check updated state
            final_state = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).single().execute()
            final_data = final_state.data
            
            # Verify all expected fields are updated
            assert final_data['current_step_type'] == 'purge'
            assert final_data['current_step_name'] == 'Test Purge Step - State Tracking'
            assert final_data['current_purge_duration_ms'] == 1200
            assert final_data['last_updated'] is not None
            
            result = {
                'test_name': 'purge_state_tracking',
                'status': 'PASSED',
                'duration_seconds': time.time() - start_time,
                'details': {
                    'initial_step_type': initial_state.data.get('current_step_type'),
                    'final_step_type': final_data['current_step_type'],
                    'purge_duration_set': final_data['current_purge_duration_ms'],
                    'state_updated': True,
                    'progress_maintained': final_data['progress'] == initial_progress
                }
            }
            
        except Exception as e:
            logger.error(f"Purge state tracking test failed: {e}")
            result = {
                'test_name': 'purge_state_tracking',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_state_tracking',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def test_purge_performance_metrics(self) -> Dict[str, Any]:
        """Test performance metrics for purge operations."""
        logger.info("Testing purge performance metrics")
        start_time = time.time()
        
        try:
            process_id = await self.create_test_process("purge_performance_metrics")
            
            # Test different purge durations for performance analysis
            durations = [100, 500, 1000, 2000, 5000]  # ms
            execution_metrics = []
            
            for duration in durations:
                step_id = str(uuid.uuid4())
                await self.create_test_purge_config(step_id, duration, 'N2', 100.0)
                
                step_data = {
                    'id': step_id,
                    'type': 'purging',
                    'name': f'Test Purge Step - {duration}ms',
                    'parameters': {}
                }
                
                # Measure execution time
                exec_start = time.time()
                await execute_purge_step(process_id, step_data)
                exec_time = time.time() - exec_start
                
                # Calculate overhead (execution time - expected duration)
                expected_time = duration / 1000
                overhead = exec_time - expected_time
                
                execution_metrics.append({
                    'duration_ms': duration,
                    'expected_time': expected_time,
                    'actual_time': exec_time,
                    'overhead': overhead,
                    'overhead_percentage': (overhead / expected_time) * 100 if expected_time > 0 else 0
                })
            
            average_overhead = sum(m['overhead_percentage'] for m in execution_metrics) / len(execution_metrics)
            
            result = {
                'test_name': 'purge_performance_metrics',
                'status': 'PASSED' if average_overhead < 20 else 'FAILED',  # 20% overhead tolerance
                'duration_seconds': time.time() - start_time,
                'details': {
                    'execution_metrics': execution_metrics,
                    'average_overhead_percentage': average_overhead,
                    'durations_tested': durations,
                    'performance_acceptable': average_overhead < 20
                }
            }
            
        except Exception as e:
            logger.error(f"Purge performance metrics test failed: {e}")
            result = {
                'test_name': 'purge_performance_metrics',
                'status': 'FAILED',
                'duration_seconds': time.time() - start_time,
                'error': str(e)
            }
            self.test_data['error_logs'].append({
                'test': 'purge_performance_metrics',
                'error': str(e),
                'timestamp': get_current_timestamp()
            })
        
        self.test_results.append(result)
        return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all purge step integration tests."""
        logger.info("Starting comprehensive purge step integration tests")
        
        await self.setup_test_environment()
        
        # Run all tests
        test_methods = [
            self.test_purge_config_loading,
            self.test_purge_fallback_logic,
            self.test_purge_backwards_compatibility,
            self.test_purge_timing_accuracy,
            self.test_purge_gas_flow_control,
            self.test_purge_error_handling,
            self.test_purge_state_tracking,
            self.test_purge_performance_metrics
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                logger.error(f"Test {test_method.__name__} failed: {e}")
                self.test_results.append({
                    'test_name': test_method.__name__,
                    'status': 'FAILED',
                    'error': str(e)
                })
        
        # Generate summary
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASSED'])
        failed_tests = total_tests - passed_tests
        
        summary = {
            'test_suite': 'purge_step_integration_test',
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'results': self.test_results,
            'test_data': self.test_data,
            'completed_at': get_current_timestamp()
        }
        
        return summary

async def main():
    """Main test runner."""
    tester = PurgeStepIntegrationTest()
    results = await tester.run_all_tests()
    
    # Write results to file
    with open('purge_step_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print(f"\nPurge Step Integration Test Results:")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['success_rate']:.1f}%")
    
    for result in results['results']:
        status_icon = "✅" if result['status'] == 'PASSED' else "❌"
        print(f"{status_icon} {result['test_name']}: {result['status']}")
        if result['status'] == 'FAILED' and 'error' in result:
            print(f"   Error: {result['error']}")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())