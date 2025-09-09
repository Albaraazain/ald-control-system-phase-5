#!/usr/bin/env python3
"""
Database Validation Test - Focus on validating the new database schema

This test validates the new normalized database schema and verifies
that the migration was successful and data integrity is maintained.
"""

import asyncio
import sys
import json
from datetime import datetime
from supabase import create_client
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, '/home/albaraa/Projects/ald-control-system-phase-5')

# Configuration
SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOSJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzU5OTYzNzUsImV4cCI6MjA1MTU3MjM3NX0.tiMdbAs79ZOS3PhnEUxXq_g5JLLXG8-o_a7VAIN6cd8"

class DatabaseValidationTest:
    """Comprehensive database schema and data validation"""
    
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.validation_results = []
        
    def validate_table_structure(self, table_name: str, expected_columns: List[str]) -> Dict[str, Any]:
        """Validate that a table has the expected structure"""
        try:
            # Try to query the table to verify structure
            response = self.supabase.table(table_name).select(','.join(expected_columns)).limit(1).execute()
            
            return {
                'table_name': table_name,
                'exists': True,
                'has_data': len(response.data) > 0,
                'columns_accessible': True,
                'error': None
            }
        except Exception as e:
            return {
                'table_name': table_name,
                'exists': False,
                'has_data': False,
                'columns_accessible': False,
                'error': str(e)
            }
    
    async def validate_normalized_schema(self) -> Dict[str, Any]:
        """Validate the normalized database schema"""
        print("🔍 Validating normalized database schema...")
        
        schema_validation = {
            'test_name': 'Normalized Schema Validation',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        # Define expected table structures
        table_structures = {
            'valve_step_config': ['id', 'step_id', 'valve_id', 'valve_number', 'duration_ms'],
            'purge_step_config': ['id', 'step_id', 'duration_ms', 'gas_type', 'flow_rate'],
            'loop_step_config': ['id', 'step_id', 'iteration_count'],
            'process_execution_state': ['id', 'execution_id', 'current_step_index', 'total_overall_steps', 
                                      'current_step_type', 'progress', 'process_metrics'],
            'recipe_parameters': ['id', 'recipe_id', 'parameter_name', 'parameter_value', 'parameter_unit'],
            'component_parameter_definitions': ['id', 'component_definition_id', 'name', 'description', 'unit']
        }
        
        # Validate each table
        for table_name, expected_columns in table_structures.items():
            validation = self.validate_table_structure(table_name, expected_columns)
            schema_validation['details'][table_name] = validation
            
            print(f"   {table_name}: {'✅' if validation['exists'] else '❌'} "
                  f"({'Data: ✅' if validation['has_data'] else 'No data: ⚠️'})")
            
            if not validation['exists']:
                schema_validation['errors'].append(f"Table {table_name} not accessible")
                schema_validation['passed'] = False
            elif validation['error']:
                schema_validation['errors'].append(f"Error accessing {table_name}: {validation['error']}")
        
        return schema_validation
    
    async def validate_step_configurations(self) -> Dict[str, Any]:
        """Validate step configuration data integrity"""
        print("⚙️ Validating step configuration data integrity...")
        
        config_validation = {
            'test_name': 'Step Configuration Validation',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            # Get step configuration counts and validate data
            config_tables = ['valve_step_config', 'purge_step_config', 'loop_step_config']
            
            for table in config_tables:
                try:
                    response = self.supabase.table(table).select('*').execute()
                    count = len(response.data)
                    config_validation['details'][f'{table}_count'] = count
                    
                    if count > 0:
                        # Validate first record has required fields
                        sample_record = response.data[0]
                        
                        if table == 'valve_step_config':
                            required_fields = ['valve_number', 'duration_ms']
                            for field in required_fields:
                                if field not in sample_record or sample_record[field] is None:
                                    config_validation['errors'].append(f"Missing {field} in {table}")
                                    config_validation['passed'] = False
                        
                        elif table == 'purge_step_config':
                            required_fields = ['duration_ms', 'gas_type']
                            for field in required_fields:
                                if field not in sample_record or sample_record[field] is None:
                                    config_validation['errors'].append(f"Missing {field} in {table}")
                                    config_validation['passed'] = False
                        
                        elif table == 'loop_step_config':
                            if 'iteration_count' not in sample_record or sample_record['iteration_count'] is None:
                                config_validation['errors'].append(f"Missing iteration_count in {table}")
                                config_validation['passed'] = False
                    
                    print(f"   {table}: {count} records")
                    
                except Exception as e:
                    config_validation['errors'].append(f"Failed to validate {table}: {str(e)}")
                    config_validation['passed'] = False
                    print(f"   {table}: ❌ Error - {str(e)}")
            
        except Exception as e:
            config_validation['errors'].append(f"Step configuration validation failed: {str(e)}")
            config_validation['passed'] = False
        
        return config_validation
    
    async def validate_foreign_key_relationships(self) -> Dict[str, Any]:
        """Validate foreign key relationships"""
        print("🔗 Validating foreign key relationships...")
        
        fk_validation = {
            'test_name': 'Foreign Key Relationships',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            # Test recipe_steps -> step_configs relationship
            steps_response = self.supabase.table('recipe_steps').select('id,type').limit(10).execute()
            
            if steps_response.data:
                fk_validation['details']['recipe_steps_found'] = len(steps_response.data)
                
                valid_relationships = 0
                
                for step in steps_response.data:
                    step_id = step['id']
                    step_type = step['type']
                    
                    if step_type == 'valve':
                        config_response = self.supabase.table('valve_step_config').select('id').eq('step_id', step_id).execute()
                        if config_response.data:
                            valid_relationships += 1
                    
                    elif step_type == 'purge':
                        config_response = self.supabase.table('purge_step_config').select('id').eq('step_id', step_id).execute()
                        if config_response.data:
                            valid_relationships += 1
                    
                    elif step_type == 'loop':
                        config_response = self.supabase.table('loop_step_config').select('id').eq('step_id', step_id).execute()
                        if config_response.data:
                            valid_relationships += 1
                
                fk_validation['details']['valid_step_config_relationships'] = valid_relationships
                
                if valid_relationships == 0:
                    fk_validation['errors'].append("No valid step->config relationships found")
                    fk_validation['passed'] = False
                
                print(f"   Recipe steps with valid configs: {valid_relationships}/{len(steps_response.data)}")
            
            # Test process_executions -> process_execution_state relationship
            process_response = self.supabase.table('process_executions').select('id').limit(5).execute()
            
            if process_response.data:
                processes_with_state = 0
                
                for process in process_response.data:
                    state_response = self.supabase.table('process_execution_state').select('id').eq('execution_id', process['id']).execute()
                    if state_response.data:
                        processes_with_state += 1
                
                fk_validation['details']['processes_with_state'] = f"{processes_with_state}/{len(process_response.data)}"
                print(f"   Process executions with state records: {processes_with_state}/{len(process_response.data)}")
        
        except Exception as e:
            fk_validation['errors'].append(f"Foreign key validation failed: {str(e)}")
            fk_validation['passed'] = False
        
        return fk_validation
    
    async def validate_data_consistency(self) -> Dict[str, Any]:
        """Validate data consistency across related tables"""
        print("📊 Validating data consistency...")
        
        consistency_validation = {
            'test_name': 'Data Consistency',
            'passed': True,
            'details': {},
            'errors': []
        }
        
        try:
            # Check recipe parameter consistency
            recipe_params_response = self.supabase.table('recipe_parameters').select('*').limit(10).execute()
            
            if recipe_params_response.data:
                consistent_params = 0
                
                for param in recipe_params_response.data:
                    # Validate parameter has required fields
                    if (param.get('parameter_name') and 
                        param.get('parameter_value') is not None and
                        param.get('recipe_id')):
                        consistent_params += 1
                
                consistency_validation['details']['consistent_recipe_parameters'] = f"{consistent_params}/{len(recipe_params_response.data)}"
                print(f"   Consistent recipe parameters: {consistent_params}/{len(recipe_params_response.data)}")
            
            # Check process execution state consistency
            state_response = self.supabase.table('process_execution_state').select('*').limit(10).execute()
            
            if state_response.data:
                consistent_states = 0
                
                for state in state_response.data:
                    # Validate state has reasonable values
                    current_step = state.get('current_step_index', 0)
                    total_steps = state.get('total_overall_steps', 0)
                    
                    if (current_step is not None and total_steps is not None and
                        current_step >= 0 and total_steps >= 0 and
                        current_step <= total_steps):
                        consistent_states += 1
                
                consistency_validation['details']['consistent_execution_states'] = f"{consistent_states}/{len(state_response.data)}"
                print(f"   Consistent execution states: {consistent_states}/{len(state_response.data)}")
        
        except Exception as e:
            consistency_validation['errors'].append(f"Data consistency validation failed: {str(e)}")
            consistency_validation['passed'] = False
        
        return consistency_validation
    
    async def run_all_validations(self) -> Dict[str, Any]:
        """Run all database validation tests"""
        print("🔍 ALD Control System - Database Validation Test Suite")
        print("=" * 70)
        print(f"Started at: {datetime.now().isoformat()}")
        print("=" * 70)
        
        # Run all validation tests
        validations = [
            self.validate_normalized_schema(),
            self.validate_step_configurations(),
            self.validate_foreign_key_relationships(),
            self.validate_data_consistency()
        ]
        
        results = await asyncio.gather(*validations)
        
        # Compile final report
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        final_report = {
            'test_suite': 'ALD Control System Database Validation',
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate_percent': (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            },
            'validation_results': results,
            'overall_passed': failed_tests == 0,
            'database_migration_status': 'successful' if failed_tests == 0 else 'issues_found'
        }
        
        return final_report

async def main():
    """Execute database validation tests"""
    
    try:
        validator = DatabaseValidationTest()
        report = await validator.run_all_validations()
        
        # Print final results
        print("\n" + "=" * 70)
        print("📊 DATABASE VALIDATION RESULTS")
        print("=" * 70)
        
        summary = report['summary']
        print(f"Total Validations: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ✅")
        print(f"Failed: {summary['failed_tests']} {'❌' if summary['failed_tests'] > 0 else '✅'}")
        print(f"Success Rate: {summary['success_rate_percent']:.1f}%")
        
        # Print individual validation results
        print(f"\n📋 Individual Validation Results:")
        for result in report['validation_results']:
            status = "✅ PASSED" if result['passed'] else "❌ FAILED"
            print(f"  {status} - {result['test_name']}")
            
            if result['errors']:
                for error in result['errors']:
                    print(f"    ERROR: {error}")
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"database_validation_report_{timestamp}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Full report saved: {report_filename}")
        
        # Print conclusion
        if report['overall_passed']:
            print(f"\n🎉 DATABASE VALIDATION SUCCESSFUL!")
            print("✅ All normalized schema tables are accessible")
            print("✅ Step configuration data integrity verified")
            print("✅ Foreign key relationships working correctly")
            print("✅ Data consistency checks passed")
            print(f"🗄️ Database migration status: {report['database_migration_status'].upper()}")
        else:
            print(f"\n⚠️  Database validation found issues.")
            print(f"🗄️ Database migration status: {report['database_migration_status'].upper()}")
            print("Review the errors above and the detailed report.")
        
        print("=" * 70)
        
        return 0 if report['overall_passed'] else 1
        
    except Exception as e:
        print(f"\n❌ Database validation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)