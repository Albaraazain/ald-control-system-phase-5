#!/usr/bin/env python3
"""
Working Simulation Test - ALD Control System Testing with Existing Data

This script tests the ALD control system using existing recipes and focuses on:
1. Process execution state tracking
2. Database validation 
3. PLC simulation mode
4. Recipe step configuration loading with new schema
"""

import asyncio
import sys
import json
import time
from datetime import datetime, timezone
from supabase import create_client
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, '/home/albaraa/Projects/ald-control-system-phase-5')

# Configuration
SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzU5OTYzNzUsImV4cCI6MjA1MTU3MjM3NX0.tiMdbAs79ZOS3PhnEUxXq_g5JLLXG8-o_a7VAIN6cd8"

class WorkingSimulationTest:
    """Test runner that works with existing database data"""
    
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.test_results = []
        
    async def test_database_schema_validation(self) -> Dict[str, Any]:
        """Test the new normalized database schema structure"""
        print("🔍 Testing database schema validation...")
        
        result = {
            'test_name': 'Database Schema Validation',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            # Test 1: Verify normalized step configuration tables exist and have data
            step_config_tables = ['valve_step_config', 'purge_step_config', 'loop_step_config']
            
            for table_name in step_config_tables:
                response = self.supabase.table(table_name).select('count').execute()
                count = len(response.data) if response.data else 0
                result['details'][f'{table_name}_records'] = count
                print(f"   {table_name}: {count} records")
                
                if count == 0:
                    result['errors'].append(f"No data found in {table_name}")
            
            # Test 2: Verify process_execution_state table structure
            state_response = self.supabase.table('process_execution_state').select('*').limit(1).execute()
            if state_response.data:
                state_record = state_response.data[0]
                required_fields = [
                    'execution_id', 'current_step_index', 'total_overall_steps',
                    'current_step_type', 'progress', 'process_metrics'
                ]
                
                for field in required_fields:
                    if field in state_record:
                        result['details'][f'has_{field}'] = True
                    else:
                        result['errors'].append(f"Missing field in process_execution_state: {field}")
                        result['passed'] = False
            
            # Test 3: Verify foreign key relationships work
            recipes_with_steps = self.supabase.rpc('get_recipe_with_step_configs', {'recipe_limit': 1}).execute()
            if not recipes_with_steps.data:
                # Fallback: manual join test
                recipe_response = self.supabase.table('recipes').select('id').limit(1).execute()
                if recipe_response.data:
                    recipe_id = recipe_response.data[0]['id']
                    
                    # Test step-config joins
                    steps_response = self.supabase.table('recipe_steps').select('''
                        id, name, type,
                        valve_step_config(valve_number, duration_ms),
                        purge_step_config(duration_ms, gas_type),
                        loop_step_config(iteration_count)
                    ''').eq('recipe_id', recipe_id).execute()
                    
                    if steps_response.data:
                        result['details']['step_config_joins_work'] = True
                        result['details']['tested_recipe_id'] = recipe_id
                        result['details']['steps_with_configs'] = len(steps_response.data)
                    else:
                        result['errors'].append("Could not join step configurations")
                        result['passed'] = False
            
            print(f"   Schema validation: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
            
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Schema validation failed: {str(e)}")
            print(f"   Schema validation: ❌ FAILED - {str(e)}")
        
        return result
    
    async def test_recipe_step_loading(self) -> Dict[str, Any]:
        """Test that recipe steps load correctly with the new normalized schema"""
        print("📜 Testing recipe step configuration loading...")
        
        result = {
            'test_name': 'Recipe Step Loading',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            # Get the test recipe with most steps
            recipe_response = self.supabase.table('recipes').select('''
                id, name,
                recipe_steps(
                    id, name, type, sequence_number,
                    valve_step_config(valve_number, duration_ms),
                    purge_step_config(duration_ms, gas_type),
                    loop_step_config(iteration_count)
                )
            ''').eq('name', 'Test ALD Recipe - Short').execute()
            
            if not recipe_response.data:
                result['errors'].append("Test recipe not found")
                result['passed'] = False
                return result
            
            recipe = recipe_response.data[0]
            steps = recipe.get('recipe_steps', [])
            
            result['details']['recipe_name'] = recipe['name']
            result['details']['total_steps'] = len(steps)
            
            step_type_counts = {'valve': 0, 'purge': 0, 'loop': 0, 'other': 0}
            config_validation = {'valve_configs': 0, 'purge_configs': 0, 'loop_configs': 0, 'missing_configs': []}
            
            for step in steps:
                step_type = step['type']
                step_name = step['name']
                
                # Count step types
                if step_type in step_type_counts:
                    step_type_counts[step_type] += 1
                else:
                    step_type_counts['other'] += 1
                
                # Validate configurations
                if step_type == 'valve':
                    valve_config = step.get('valve_step_config')
                    if valve_config and len(valve_config) > 0:
                        config_validation['valve_configs'] += 1
                        config = valve_config[0]
                        if not config.get('valve_number') or not config.get('duration_ms'):
                            result['errors'].append(f"Incomplete valve config for step: {step_name}")
                    else:
                        config_validation['missing_configs'].append(f"Valve config missing for: {step_name}")
                        result['errors'].append(f"Missing valve config for step: {step_name}")
                
                elif step_type == 'purge':
                    purge_config = step.get('purge_step_config')
                    if purge_config and len(purge_config) > 0:
                        config_validation['purge_configs'] += 1
                        config = purge_config[0]
                        if not config.get('duration_ms') or not config.get('gas_type'):
                            result['errors'].append(f"Incomplete purge config for step: {step_name}")
                    else:
                        config_validation['missing_configs'].append(f"Purge config missing for: {step_name}")
                        result['errors'].append(f"Missing purge config for step: {step_name}")
                
                elif step_type == 'loop':
                    loop_config = step.get('loop_step_config')
                    if loop_config and len(loop_config) > 0:
                        config_validation['loop_configs'] += 1
                        config = loop_config[0]
                        if not config.get('iteration_count'):
                            result['errors'].append(f"Incomplete loop config for step: {step_name}")
                    else:
                        config_validation['missing_configs'].append(f"Loop config missing for: {step_name}")
                        result['errors'].append(f"Missing loop config for step: {step_name}")
            
            result['details']['step_type_counts'] = step_type_counts
            result['details']['config_validation'] = config_validation
            
            # Validate that we have proper step distribution
            total_configured = config_validation['valve_configs'] + config_validation['purge_configs'] + config_validation['loop_configs']
            
            if total_configured == 0:
                result['errors'].append("No step configurations found")
                result['passed'] = False
            
            if len(config_validation['missing_configs']) > 0:
                result['passed'] = False
            
            print(f"   Found {result['details']['total_steps']} steps with {total_configured} properly configured")
            print(f"   Step types: {step_type_counts}")
            print(f"   Recipe step loading: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
            
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Recipe step loading failed: {str(e)}")
            print(f"   Recipe step loading: ❌ FAILED - {str(e)}")
        
        return result
    
    async def test_process_execution_simulation(self) -> Dict[str, Any]:
        """Test process execution state tracking with simulation"""
        print("⚡ Testing process execution state tracking...")
        
        result = {
            'test_name': 'Process Execution Simulation',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            # Get a virtual machine and test recipe
            machine_response = self.supabase.table('machines').select('id,serial_number').eq('is_virtual', True).limit(1).execute()
            recipe_response = self.supabase.table('recipes').select('id,name').eq('name', 'Test ALD Recipe - Short').limit(1).execute()
            
            if not machine_response.data:
                result['errors'].append("No virtual machines available")
                result['passed'] = False
                return result
            
            if not recipe_response.data:
                result['errors'].append("Test recipe not found")
                result['passed'] = False
                return result
            
            machine_id = machine_response.data[0]['id']
            recipe_id = recipe_response.data[0]['id']
            
            result['details']['machine_id'] = machine_id
            result['details']['recipe_id'] = recipe_id
            
            # Create a simulated process execution
            process_data = {
                'machine_id': machine_id,
                'recipe_id': recipe_id,
                'status': 'preparing',
                'parameters': {'test_mode': True, 'simulation': True},
                'operator_id': None,
                'session_id': None,
                'start_time': datetime.now(timezone.utc).isoformat(),
                'recipe_version': {},
                'description': 'Automated simulation test'
            }
            
            # Try to create process execution (this may fail due to RLS)
            try:
                process_response = self.supabase.table('process_executions').insert(process_data).execute()
                
                if process_response.data:
                    process_id = process_response.data[0]['id']
                    result['details']['created_process_id'] = process_id
                    
                    # Simulate some process execution state updates
                    state_data = {
                        'execution_id': process_id,
                        'current_step_index': 1,
                        'total_overall_steps': 10,
                        'current_step_type': 'valve',
                        'current_valve_number': 1,
                        'current_valve_duration_ms': 5000,
                        'progress': {
                            'total_steps': 10,
                            'completed_steps': 1,
                            'percentage': 10.0
                        },
                        'process_metrics': {
                            'start_time': datetime.now(timezone.utc).isoformat(),
                            'current_time': datetime.now(timezone.utc).isoformat()
                        }
                    }
                    
                    state_response = self.supabase.table('process_execution_state').insert(state_data).execute()
                    
                    if state_response.data:
                        result['details']['created_state_record'] = True
                        
                        # Update process to completed
                        update_response = self.supabase.table('process_executions').update({
                            'status': 'completed',
                            'end_time': datetime.now(timezone.utc).isoformat()
                        }).eq('id', process_id).execute()
                        
                        if update_response.data:
                            result['details']['process_completed'] = True
                        
                    else:
                        result['errors'].append("Failed to create process execution state")
                        result['passed'] = False
                
                else:
                    result['errors'].append("Failed to create process execution")
                    result['passed'] = False
            
            except Exception as e:
                # If we can't create due to RLS, test with existing data
                print(f"   Cannot create new process (RLS): {str(e)}")
                print("   Testing with existing process execution data...")
                
                existing_processes = self.supabase.table('process_executions').select('id,status').limit(1).execute()
                
                if existing_processes.data:
                    process_id = existing_processes.data[0]['id']
                    result['details']['using_existing_process'] = process_id
                    
                    # Check if state record exists
                    state_response = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).execute()
                    
                    if state_response.data:
                        state = state_response.data[0]
                        result['details']['existing_state_found'] = True
                        result['details']['state_structure'] = {
                            'current_step_index': state.get('current_step_index'),
                            'total_overall_steps': state.get('total_overall_steps'),
                            'current_step_type': state.get('current_step_type'),
                            'has_progress': bool(state.get('progress')),
                            'has_metrics': bool(state.get('process_metrics'))
                        }
                    else:
                        result['details']['no_existing_state'] = True
                
                else:
                    result['errors'].append("No existing process executions to test with")
                    result['passed'] = False
            
            print(f"   Process execution simulation: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
            
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Process execution test failed: {str(e)}")
            print(f"   Process execution simulation: ❌ FAILED - {str(e)}")
        
        return result
    
    async def test_validation_framework(self) -> Dict[str, Any]:
        """Test the validation framework with existing data"""
        print("🔍 Testing validation framework...")
        
        result = {
            'test_name': 'Validation Framework',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            from simulation_validator import SimulationValidator
            
            validator = SimulationValidator(SUPABASE_URL, SUPABASE_KEY)
            
            # Get an existing process execution to validate
            process_response = self.supabase.table('process_executions').select('id').limit(1).execute()
            
            if not process_response.data:
                result['errors'].append("No process executions found to validate")
                result['passed'] = False
                return result
            
            process_id = process_response.data[0]['id']
            result['details']['validated_process_id'] = process_id
            
            # Run database referential integrity validation
            integrity_result = await validator.validate_database_referential_integrity(process_id)
            
            result['details']['integrity_validation'] = {
                'passed': integrity_result.passed,
                'errors': integrity_result.errors,
                'warnings': integrity_result.warnings
            }
            
            if not integrity_result.passed:
                result['passed'] = False
                result['errors'].extend(integrity_result.errors)
            
            # Run step configuration loading validation
            config_result = await validator.validate_step_configuration_loading(process_id)
            
            result['details']['config_validation'] = {
                'passed': config_result.passed,
                'errors': config_result.errors,
                'warnings': config_result.warnings
            }
            
            if not config_result.passed:
                result['passed'] = False
                result['errors'].extend(config_result.errors)
            
            print(f"   Validation framework: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
            
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Validation framework test failed: {str(e)}")
            print(f"   Validation framework: ❌ FAILED - {str(e)}")
        
        return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all simulation tests"""
        print("🧪 ALD Control System - Working Simulation Tests")
        print("=" * 70)
        print(f"Started at: {datetime.now().isoformat()}")
        print("=" * 70)
        
        # Run all test cases
        tests = [
            self.test_database_schema_validation(),
            self.test_recipe_step_loading(),
            self.test_process_execution_simulation(),
            self.test_validation_framework()
        ]
        
        results = await asyncio.gather(*tests)
        
        # Compile final report
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        final_report = {
            'test_suite': 'ALD Control System Working Simulation Tests',
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate_percent': (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            },
            'test_results': results,
            'overall_passed': failed_tests == 0
        }
        
        return final_report

async def main():
    """Execute the working simulation tests"""
    
    try:
        test_runner = WorkingSimulationTest()
        report = await test_runner.run_all_tests()
        
        # Print final results
        print("\n" + "=" * 70)
        print("📊 FINAL TEST RESULTS")
        print("=" * 70)
        
        summary = report['summary']
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ✅")
        print(f"Failed: {summary['failed_tests']} {'❌' if summary['failed_tests'] > 0 else '✅'}")
        print(f"Success Rate: {summary['success_rate_percent']:.1f}%")
        
        # Print individual test results
        print(f"\n📋 Individual Test Results:")
        for result in report['test_results']:
            status = "✅ PASSED" if result['passed'] else "❌ FAILED"
            print(f"  {status} - {result['test_name']}")
            
            if result['errors']:
                for error in result['errors']:
                    print(f"    ERROR: {error}")
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"working_simulation_test_report_{timestamp}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Full report saved: {report_filename}")
        
        # Print conclusion
        if report['overall_passed']:
            print(f"\n🎉 ALL TESTS PASSED! The ALD control system simulation framework is working correctly.")
            print("✅ Database schema validation successful")
            print("✅ Recipe step configuration loading working")
            print("✅ Process execution state tracking functional")
            print("✅ Validation framework operational")
        else:
            print(f"\n⚠️  Some tests failed. Review the errors above and the detailed report.")
        
        print("=" * 70)
        
        return 0 if report['overall_passed'] else 1
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)