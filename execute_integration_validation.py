#!/usr/bin/env python3
"""
Execute Integration Validation 
Comprehensive validation runner for ALD control system integration tests
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from db import get_supabase
    from log_setup import logger
    from config import MACHINE_ID
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

class IntegrationValidationRunner:
    """Comprehensive integration validation runner"""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.machine_id = MACHINE_ID
        self.validation_results = {}
        
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all integration validation tests"""
        logger.info("🚀 Starting comprehensive integration validation")
        
        validation_results = {
            'validation_id': f"integration_validation_{int(time.time())}",
            'started_at': datetime.now().isoformat(),
            'machine_id': str(self.machine_id),
            'validations': {},
            'summary': {}
        }
        
        validation_tests = [
            ("Database Connectivity", self.test_database_connectivity),
            ("Recipe Data Validation", self.validate_recipe_data),
            ("Step Configuration Validation", self.validate_step_configurations),
            ("Command System Integration", self.validate_command_system),
            ("Process Execution Structure", self.validate_process_execution_structure),
            ("Data Consistency Checks", self.validate_data_consistency),
        ]
        
        for test_name, test_func in validation_tests:
            logger.info(f"📋 Running: {test_name}")
            try:
                test_result = await test_func()
                validation_results['validations'][test_name] = test_result
                
                status = "PASSED" if test_result.get('success', False) else "FAILED"
                logger.info(f"{'✅' if status == 'PASSED' else '❌'} {test_name}: {status}")
                
            except Exception as e:
                logger.error(f"❌ {test_name} failed with error: {str(e)}")
                validation_results['validations'][test_name] = {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
        
        # Calculate summary
        validation_results['completed_at'] = datetime.now().isoformat()
        validation_results['summary'] = self.calculate_validation_summary(validation_results['validations'])
        
        # Save results
        report_filename = f"integration_validation_results_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(validation_results, f, indent=2, default=str)
        
        logger.info(f"📊 Validation results saved to {report_filename}")
        return validation_results
    
    async def test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity and basic operations"""
        logger.info("🔗 Testing database connectivity")
        
        try:
            # Test machine connectivity
            machine_result = self.supabase.table('machines').select('id, status').eq('id', self.machine_id).execute()
            
            if not machine_result.data:
                return {
                    'success': False,
                    'error': 'Machine not found in database',
                    'machine_id': str(self.machine_id)
                }
            
            # Test table access
            table_tests = []
            test_tables = ['recipes', 'recipe_steps', 'recipe_parameters', 'recipe_commands']
            
            for table_name in test_tables:
                try:
                    result = self.supabase.table(table_name).select('id').limit(1).execute()
                    table_tests.append({
                        'table': table_name,
                        'accessible': True,
                        'has_data': len(result.data) > 0 if result.data else False
                    })
                except Exception as e:
                    table_tests.append({
                        'table': table_name,
                        'accessible': False,
                        'error': str(e)
                    })
            
            accessible_tables = sum(1 for test in table_tests if test['accessible'])
            
            return {
                'success': accessible_tables == len(test_tables),
                'machine_found': True,
                'machine_status': machine_result.data[0]['status'],
                'table_access_tests': table_tests,
                'accessible_tables': accessible_tables,
                'total_tables_tested': len(test_tables)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'machine_found': False
            }
    
    async def validate_recipe_data(self) -> Dict[str, Any]:
        """Validate recipe data completeness and quality"""
        logger.info("🧪 Validating recipe data")
        
        try:
            # Get test recipes
            recipes_result = self.supabase.table('recipes').select(
                'id, name, description, created_at'
            ).or_('name.ilike.%Test%,name.ilike.%Integration%,name.ilike.%Simulation%').execute()
            
            recipes = recipes_result.data if recipes_result.data else []
            
            if not recipes:
                return {
                    'success': False,
                    'error': 'No test recipes found',
                    'total_recipes': 0
                }
            
            # Validate each recipe
            recipe_validations = []
            for recipe in recipes:
                recipe_id = recipe['id']
                
                # Get steps for this recipe
                steps_result = self.supabase.table('recipe_steps').select(
                    'id, name, type, sequence_number'
                ).eq('recipe_id', recipe_id).execute()
                
                steps = steps_result.data if steps_result.data else []
                
                # Get parameters for this recipe
                params_result = self.supabase.table('recipe_parameters').select(
                    'parameter_name, parameter_value, parameter_type'
                ).eq('recipe_id', recipe_id).execute()
                
                parameters = params_result.data if params_result.data else []
                
                recipe_validation = {
                    'recipe_id': recipe_id,
                    'recipe_name': recipe['name'],
                    'has_steps': len(steps) > 0,
                    'step_count': len(steps),
                    'has_parameters': len(parameters) > 0,
                    'parameter_count': len(parameters),
                    'complete': len(steps) > 0 and len(parameters) > 0
                }
                
                recipe_validations.append(recipe_validation)
            
            complete_recipes = sum(1 for r in recipe_validations if r['complete'])
            
            return {
                'success': complete_recipes > 0,
                'total_test_recipes': len(recipes),
                'complete_recipes': complete_recipes,
                'recipe_validations': recipe_validations,
                'completeness_rate': complete_recipes / len(recipes) if recipes else 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_recipes': 0
            }
    
    async def validate_step_configurations(self) -> Dict[str, Any]:
        """Validate step configurations are properly linked"""
        logger.info("⚙️ Validating step configurations")
        
        try:
            # Get test recipe steps
            test_recipes_result = self.supabase.table('recipes').select('id').or_(
                'name.ilike.%Test%,name.ilike.%Integration%,name.ilike.%Simulation%'
            ).execute()
            
            if not test_recipes_result.data:
                return {
                    'success': False,
                    'error': 'No test recipes found',
                    'total_steps': 0
                }
            
            recipe_ids = [r['id'] for r in test_recipes_result.data]
            
            # Get steps for test recipes
            steps_result = self.supabase.table('recipe_steps').select(
                'id, name, type, recipe_id'
            ).in_('recipe_id', recipe_ids).execute()
            
            steps = steps_result.data if steps_result.data else []
            
            if not steps:
                return {
                    'success': False,
                    'error': 'No steps found for test recipes',
                    'total_steps': 0
                }
            
            # Check configuration tables
            config_validations = []
            
            for step in steps:
                step_id = step['id']
                step_type = step['type']
                
                config_validation = {
                    'step_id': step_id,
                    'step_name': step['name'],
                    'step_type': step_type,
                    'configured': False,
                    'config_details': None
                }
                
                # Check appropriate configuration table
                if step_type == 'valve':
                    config_result = self.supabase.table('valve_step_config').select(
                        'valve_number, duration_ms'
                    ).eq('step_id', step_id).execute()
                    
                    if config_result.data:
                        config_validation['configured'] = True
                        config_validation['config_details'] = config_result.data[0]
                
                elif step_type == 'purge':
                    config_result = self.supabase.table('purge_step_config').select(
                        'gas_type, duration_ms, flow_rate'
                    ).eq('step_id', step_id).execute()
                    
                    if config_result.data:
                        config_validation['configured'] = True
                        config_validation['config_details'] = config_result.data[0]
                
                elif step_type == 'loop':
                    config_result = self.supabase.table('loop_step_config').select(
                        'iteration_count, inner_steps'
                    ).eq('step_id', step_id).execute()
                    
                    if config_result.data:
                        config_validation['configured'] = True
                        config_validation['config_details'] = config_result.data[0]
                
                elif step_type == 'parameter':
                    # Parameter steps don't need separate configuration
                    config_validation['configured'] = True
                    config_validation['config_details'] = {'type': 'parameter_step'}
                
                config_validations.append(config_validation)
            
            configured_steps = sum(1 for c in config_validations if c['configured'])
            configuration_rate = configured_steps / len(config_validations) if config_validations else 0
            
            return {
                'success': configuration_rate >= 0.8,  # 80% configuration rate required
                'total_steps': len(config_validations),
                'configured_steps': configured_steps,
                'configuration_rate': configuration_rate,
                'step_configurations': config_validations
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_steps': 0
            }
    
    async def validate_command_system(self) -> Dict[str, Any]:
        """Validate command system integration"""
        logger.info("🔄 Validating command system")
        
        try:
            # Check recent commands
            commands_result = self.supabase.table('recipe_commands').select(
                'id, type, parameters, status, machine_id, created_at'
            ).eq('machine_id', self.machine_id).order('created_at', desc=True).limit(10).execute()
            
            commands = commands_result.data if commands_result.data else []
            
            # Validate command structure
            command_validations = []
            valid_commands = 0
            
            for command in commands:
                validation = {
                    'command_id': command['id'],
                    'command_type': command['type'],
                    'has_parameters': command['parameters'] is not None,
                    'valid_status': command['status'] in ['pending', 'processing', 'completed', 'failed'],
                    'valid': False
                }
                
                # Basic validation checks
                has_type = command['type'] and command['type'].strip()
                valid_machine_id = command['machine_id'] == self.machine_id
                
                validation['valid'] = (
                    has_type and 
                    valid_machine_id and 
                    validation['valid_status']
                )
                
                if validation['valid']:
                    valid_commands += 1
                
                command_validations.append(validation)
            
            # Test command creation capability
            test_command_success = False
            try:
                test_command_result = self.supabase.table('recipe_commands').insert({
                    'type': 'test_validation',
                    'parameters': {'test': 'integration_validation'},
                    'status': 'pending',
                    'machine_id': self.machine_id
                }).execute()
                
                if test_command_result.data:
                    # Clean up test command
                    test_id = test_command_result.data[0]['id']
                    self.supabase.table('recipe_commands').delete().eq('id', test_id).execute()
                    test_command_success = True
                    
            except Exception as test_error:
                logger.warning(f"Test command creation failed: {test_error}")
            
            command_validity_rate = valid_commands / len(commands) if commands else 1.0
            
            return {
                'success': command_validity_rate >= 0.8 and test_command_success,
                'total_commands_checked': len(commands),
                'valid_commands': valid_commands,
                'command_validity_rate': command_validity_rate,
                'test_command_creation': test_command_success,
                'command_validations': command_validations
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_commands_checked': 0
            }
    
    async def validate_process_execution_structure(self) -> Dict[str, Any]:
        """Validate process execution table structure and functionality"""
        logger.info("🎯 Validating process execution structure")
        
        try:
            # Test process_executions table
            pe_result = self.supabase.table('process_executions').select(
                'id, recipe_id, status, started_at'
            ).limit(5).execute()
            
            process_executions = pe_result.data if pe_result.data else []
            
            # Test process_execution_state table if process executions exist
            state_records = []
            if process_executions:
                pe_ids = [pe['id'] for pe in process_executions]
                state_result = self.supabase.table('process_execution_state').select(
                    'id, process_execution_id, current_step_id, progress_percentage'
                ).in_('process_execution_id', pe_ids).limit(10).execute()
                
                state_records = state_result.data if state_result.data else []
            
            # Test creation capability
            test_creation_success = False
            try:
                # Get a test recipe
                test_recipe_result = self.supabase.table('recipes').select('id').limit(1).execute()
                
                if test_recipe_result.data:
                    test_recipe_id = test_recipe_result.data[0]['id']
                    
                    # Create test process execution
                    test_pe_result = self.supabase.table('process_executions').insert({
                        'recipe_id': test_recipe_id,
                        'status': 'test',
                        'started_at': datetime.now().isoformat()
                    }).execute()
                    
                    if test_pe_result.data:
                        test_pe_id = test_pe_result.data[0]['id']
                        
                        # Test state creation
                        test_state_result = self.supabase.table('process_execution_state').insert({
                            'process_execution_id': test_pe_id,
                            'progress_percentage': 0,
                            'step_start_time': datetime.now().isoformat()
                        }).execute()
                        
                        if test_state_result.data:
                            test_creation_success = True
                            
                            # Clean up test records
                            self.supabase.table('process_execution_state').delete().eq(
                                'process_execution_id', test_pe_id
                            ).execute()
                        
                        self.supabase.table('process_executions').delete().eq('id', test_pe_id).execute()
                        
            except Exception as test_error:
                logger.warning(f"Test process execution creation failed: {test_error}")
            
            return {
                'success': test_creation_success,
                'process_executions_accessible': len(process_executions) >= 0,
                'state_records_accessible': len(state_records) >= 0,
                'total_process_executions': len(process_executions),
                'total_state_records': len(state_records),
                'test_creation_successful': test_creation_success
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'process_executions_accessible': False
            }
    
    async def validate_data_consistency(self) -> Dict[str, Any]:
        """Validate basic data consistency"""
        logger.info("🔒 Validating data consistency")
        
        try:
            consistency_checks = []
            
            # Check 1: Recipes have steps
            recipes_result = self.supabase.table('recipes').select('id').limit(10).execute()
            recipes = recipes_result.data if recipes_result.data else []
            
            recipes_with_steps = 0
            for recipe in recipes:
                steps_result = self.supabase.table('recipe_steps').select('id').eq(
                    'recipe_id', recipe['id']
                ).limit(1).execute()
                
                if steps_result.data:
                    recipes_with_steps += 1
            
            recipes_consistency = {
                'check': 'recipes_have_steps',
                'total_recipes': len(recipes),
                'recipes_with_steps': recipes_with_steps,
                'consistent': recipes_with_steps > 0 if recipes else True
            }
            consistency_checks.append(recipes_consistency)
            
            # Check 2: Steps have valid types
            steps_result = self.supabase.table('recipe_steps').select('id, type').limit(20).execute()
            steps = steps_result.data if steps_result.data else []
            
            valid_types = {'valve', 'purge', 'loop', 'parameter'}
            valid_step_types = sum(1 for step in steps if step['type'] in valid_types)
            
            step_types_consistency = {
                'check': 'steps_have_valid_types',
                'total_steps': len(steps),
                'valid_step_types': valid_step_types,
                'consistent': valid_step_types == len(steps) if steps else True
            }
            consistency_checks.append(step_types_consistency)
            
            # Overall consistency
            all_consistent = all(check['consistent'] for check in consistency_checks)
            
            return {
                'success': all_consistent,
                'consistency_checks': consistency_checks,
                'all_checks_consistent': all_consistent,
                'total_consistency_checks': len(consistency_checks)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'consistency_checks': []
            }
    
    def calculate_validation_summary(self, validations: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall validation summary"""
        
        total_validations = len(validations)
        successful_validations = sum(1 for v in validations.values() if v.get('success', False))
        failed_validations = total_validations - successful_validations
        
        return {
            'total_validations': total_validations,
            'successful_validations': successful_validations,
            'failed_validations': failed_validations,
            'success_rate': successful_validations / total_validations if total_validations > 0 else 0,
            'overall_success': failed_validations == 0,
            'validation_results': {
                name: result.get('success', False) 
                for name, result in validations.items()
            }
        }

async def main():
    """Main execution function"""
    runner = IntegrationValidationRunner()
    results = await runner.run_comprehensive_validation()
    
    print("\n" + "="*80)
    print("🔍 INTEGRATION VALIDATION - COMPLETE")
    print("="*80)
    print(f"Overall Success: {'✅ PASSED' if results['summary']['overall_success'] else '❌ FAILED'}")
    print(f"Success Rate: {results['summary']['success_rate']:.2%}")
    print(f"Validations: {results['summary']['successful_validations']}/{results['summary']['total_validations']}")
    print("="*80)
    
    # Print individual validation results
    for validation_name, result in results['validations'].items():
        status = "✅ PASSED" if result.get('success', False) else "❌ FAILED"
        print(f"{validation_name}: {status}")
        
        if not result.get('success', False) and 'error' in result:
            print(f"  Error: {result['error']}")
    
    print("="*80)
    return results

if __name__ == "__main__":
    asyncio.run(main())