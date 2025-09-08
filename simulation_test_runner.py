#!/usr/bin/env python3
"""
Simulation Test Runner - Comprehensive ALD Control System Testing Framework

This module orchestrates complete simulation tests for the ALD control system,
validating the new database schema and process execution state tracking.
"""

import asyncio
import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging

from supabase import create_client, Client
from dataclasses import dataclass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulation_test_results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Container for test execution results"""
    test_name: str
    passed: bool
    duration_seconds: float
    details: Dict[str, Any]
    error_message: Optional[str] = None

@dataclass
class SimulationConfig:
    """Configuration for simulation testing"""
    machine_id: str
    recipe_id: str
    test_duration_multiplier: float = 0.1  # Speed up tests
    enable_validation: bool = True
    capture_metrics: bool = True

class SimulationTestRunner:
    """Main simulation test orchestrator"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize the simulation test runner"""
        self.supabase = create_client(supabase_url, supabase_key)
        self.test_results: List[TestResult] = []
        self.start_time: Optional[datetime] = None
        
    async def setup_test_environment(self) -> SimulationConfig:
        """Set up the test environment and return configuration"""
        logger.info("Setting up simulation test environment...")
        
        # Find a virtual machine for testing
        machines_response = self.supabase.table('machines').select('*').eq('is_virtual', True).eq('status', 'idle').limit(1).execute()
        
        if not machines_response.data:
            raise ValueError("No available virtual machines found for testing")
            
        machine = machines_response.data[0]
        machine_id = machine['id']
        
        logger.info(f"Using virtual machine: {machine['serial_number']} (ID: {machine_id})")
        
        # Get the comprehensive test recipe
        recipe_response = self.supabase.table('recipes').select('*').eq('name', 'Test ALD Recipe - Short').limit(1).execute()
        
        if not recipe_response.data:
            # If test recipe doesn't exist, use any available recipe
            recipe_response = self.supabase.table('recipes').select('*').limit(1).execute()
            if not recipe_response.data:
                raise ValueError("No recipes available for testing")
        
        recipe = recipe_response.data[0]
        recipe_id = recipe['id']
        
        logger.info(f"Using test recipe: {recipe['name']} (ID: {recipe_id})")
        
        return SimulationConfig(
            machine_id=machine_id,
            recipe_id=recipe_id,
            test_duration_multiplier=0.1,  # 10x speed for testing
            enable_validation=True,
            capture_metrics=True
        )
    
    async def run_simulation_test(self, test_name: str, config: SimulationConfig, 
                                custom_params: Optional[Dict] = None) -> TestResult:
        """Run a single simulation test scenario"""
        test_start_time = time.time()
        logger.info(f"Starting simulation test: {test_name}")
        
        try:
            # Import PLC manager for simulation mode
            sys.path.append('/home/albaraa/Projects/ald-control-system-phase-5')
            from plc.plc_manager import plc_manager
            from recipe_flow.executor import RecipeExecutor
            
            # Set PLC to simulation mode
            await plc_manager.set_simulation_mode(True)
            
            # Create a test process execution record
            process_execution = {
                'machine_id': config.machine_id,
                'recipe_id': config.recipe_id,
                'status': 'preparing',
                'parameters': custom_params or {},
                'operator_id': None,  # System test
                'session_id': None,   # System test
                'start_time': datetime.now(timezone.utc).isoformat(),
                'recipe_version': {}
            }
            
            # Insert the process execution
            process_response = self.supabase.table('process_executions').insert(process_execution).execute()
            
            if not process_response.data:
                raise ValueError("Failed to create process execution record")
                
            process_id = process_response.data[0]['id']
            logger.info(f"Created process execution: {process_id}")
            
            # Initialize the recipe executor
            executor = RecipeExecutor(process_id)
            
            # Start execution and monitor
            execution_task = asyncio.create_task(executor.execute())
            monitor_task = asyncio.create_task(self.monitor_execution(process_id, test_name))
            
            # Wait for execution to complete or timeout
            timeout_seconds = 120  # 2 minutes max per test
            done, pending = await asyncio.wait(
                [execution_task, monitor_task], 
                timeout=timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Validate the execution results
            validation_results = await self.validate_execution_state(process_id, test_name)
            
            test_duration = time.time() - test_start_time
            
            return TestResult(
                test_name=test_name,
                passed=validation_results['passed'],
                duration_seconds=test_duration,
                details={
                    'process_id': process_id,
                    'validation': validation_results,
                    'execution_completed': execution_task.done() and not execution_task.cancelled()
                }
            )
            
        except Exception as e:
            test_duration = time.time() - test_start_time
            logger.error(f"Test {test_name} failed with error: {str(e)}")
            
            return TestResult(
                test_name=test_name,
                passed=False,
                duration_seconds=test_duration,
                details={},
                error_message=str(e)
            )
    
    async def monitor_execution(self, process_id: str, test_name: str):
        """Monitor process execution and log state changes"""
        logger.info(f"Starting execution monitor for {test_name}")
        
        last_state = None
        check_count = 0
        
        while check_count < 600:  # Max 10 minutes of monitoring
            try:
                # Check process execution state
                state_response = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).execute()
                
                if state_response.data:
                    current_state = state_response.data[0]
                    
                    if current_state != last_state:
                        logger.info(f"State update for {test_name}: Step {current_state.get('current_step_index', 'N/A')}, "
                                  f"Type: {current_state.get('current_step_type', 'N/A')}, "
                                  f"Progress: {current_state.get('progress', {})}")
                        last_state = current_state
                
                # Check process execution status
                process_response = self.supabase.table('process_executions').select('status').eq('id', process_id).execute()
                
                if process_response.data:
                    status = process_response.data[0]['status']
                    if status in ['completed', 'failed', 'aborted']:
                        logger.info(f"Process {process_id} finished with status: {status}")
                        break
                
                await asyncio.sleep(1)  # Check every second
                check_count += 1
                
            except Exception as e:
                logger.warning(f"Monitor error for {test_name}: {str(e)}")
                await asyncio.sleep(2)
                check_count += 2
    
    async def validate_execution_state(self, process_id: str, test_name: str) -> Dict[str, Any]:
        """Validate the execution state and database consistency"""
        logger.info(f"Validating execution state for {test_name}")
        
        validation_results = {
            'passed': False,
            'checks': {},
            'errors': []
        }
        
        try:
            # Check 1: Process execution record exists and has proper status
            process_response = self.supabase.table('process_executions').select('*').eq('id', process_id).execute()
            
            if process_response.data:
                process = process_response.data[0]
                validation_results['checks']['process_record_exists'] = True
                validation_results['checks']['process_status'] = process['status']
            else:
                validation_results['errors'].append("Process execution record not found")
                validation_results['checks']['process_record_exists'] = False
            
            # Check 2: Process execution state record exists
            state_response = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).execute()
            
            if state_response.data:
                state = state_response.data[0]
                validation_results['checks']['state_record_exists'] = True
                validation_results['checks']['final_step_index'] = state.get('current_step_index')
                validation_results['checks']['total_steps'] = state.get('total_overall_steps')
                validation_results['checks']['progress_data'] = state.get('progress', {})
            else:
                validation_results['errors'].append("Process execution state record not found")
                validation_results['checks']['state_record_exists'] = False
            
            # Check 3: Process data points were recorded
            data_points_response = self.supabase.table('process_data_points').select('count').eq('process_id', process_id).execute()
            
            if data_points_response.data:
                data_point_count = len(data_points_response.data)
                validation_results['checks']['data_points_recorded'] = data_point_count > 0
                validation_results['checks']['data_point_count'] = data_point_count
            
            # Check 4: Recipe steps were processed correctly
            recipe_response = self.supabase.table('recipe_steps').select('count').eq('recipe_id', process['recipe_id']).execute() if 'process' in locals() else None
            
            if recipe_response and recipe_response.data:
                expected_steps = len(recipe_response.data)
                validation_results['checks']['expected_steps'] = expected_steps
                
                if state_response.data:
                    actual_steps = state_response.data[0].get('total_overall_steps', 0)
                    validation_results['checks']['steps_match'] = actual_steps >= expected_steps
            
            # Overall validation
            critical_checks = ['process_record_exists', 'state_record_exists']
            validation_results['passed'] = all(validation_results['checks'].get(check, False) for check in critical_checks) and len(validation_results['errors']) == 0
            
        except Exception as e:
            validation_results['errors'].append(f"Validation error: {str(e)}")
            validation_results['passed'] = False
        
        logger.info(f"Validation results for {test_name}: {'PASSED' if validation_results['passed'] else 'FAILED'}")
        return validation_results
    
    async def run_comprehensive_tests(self) -> List[TestResult]:
        """Run the complete suite of simulation tests"""
        self.start_time = datetime.now()
        logger.info("Starting comprehensive simulation tests")
        
        # Set up test environment
        config = await self.setup_test_environment()
        
        # Define test scenarios
        test_scenarios = [
            {
                'name': 'Simple Recipe Test',
                'description': 'Test basic recipe execution with valve and purge steps',
                'config': config,
                'custom_params': {'test_mode': 'simple'}
            },
            {
                'name': 'Progress Tracking Test',
                'description': 'Verify real-time progress tracking and state updates',
                'config': config,
                'custom_params': {'test_mode': 'progress_tracking'}
            },
            {
                'name': 'Database State Validation Test',
                'description': 'Validate all database state updates during execution',
                'config': config,
                'custom_params': {'test_mode': 'validation'}
            }
        ]
        
        # Execute all test scenarios
        for scenario in test_scenarios:
            try:
                result = await self.run_simulation_test(
                    scenario['name'], 
                    scenario['config'],
                    scenario['custom_params']
                )
                self.test_results.append(result)
                
                # Add delay between tests to allow cleanup
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Failed to execute test scenario '{scenario['name']}': {str(e)}")
                
                error_result = TestResult(
                    test_name=scenario['name'],
                    passed=False,
                    duration_seconds=0,
                    details={},
                    error_message=str(e)
                )
                self.test_results.append(error_result)
        
        return self.test_results
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.passed)
        failed_tests = total_tests - passed_tests
        
        total_duration = sum(result.duration_seconds for result in self.test_results)
        
        report = {
            'test_summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'total_duration_seconds': total_duration,
                'started_at': self.start_time.isoformat() if self.start_time else None,
                'completed_at': datetime.now().isoformat()
            },
            'test_results': [
                {
                    'test_name': result.test_name,
                    'passed': result.passed,
                    'duration_seconds': result.duration_seconds,
                    'error_message': result.error_message,
                    'details': result.details
                }
                for result in self.test_results
            ]
        }
        
        return report

async def main():
    """Main entry point for simulation testing"""
    # Supabase configuration - you should set these as environment variables
    SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
    SUPABASE_KEY = "your_supabase_key_here"  # This should be provided via environment variable
    
    try:
        # Initialize and run tests
        runner = SimulationTestRunner(SUPABASE_URL, SUPABASE_KEY)
        test_results = await runner.run_comprehensive_tests()
        
        # Generate and save report
        report = runner.generate_test_report()
        
        # Save report to file
        report_filename = f"simulation_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Log summary
        logger.info("=" * 80)
        logger.info("SIMULATION TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {report['test_summary']['total_tests']}")
        logger.info(f"Passed: {report['test_summary']['passed_tests']}")
        logger.info(f"Failed: {report['test_summary']['failed_tests']}")
        logger.info(f"Success Rate: {report['test_summary']['success_rate']:.1f}%")
        logger.info(f"Total Duration: {report['test_summary']['total_duration_seconds']:.2f} seconds")
        logger.info(f"Report saved: {report_filename}")
        logger.info("=" * 80)
        
        # Print individual results
        for result in test_results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            logger.info(f"{status} - {result.test_name} ({result.duration_seconds:.2f}s)")
            if result.error_message:
                logger.info(f"   Error: {result.error_message}")
        
        return 0 if all(result.passed for result in test_results) else 1
        
    except Exception as e:
        logger.error(f"Simulation test runner failed: {str(e)}")
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)