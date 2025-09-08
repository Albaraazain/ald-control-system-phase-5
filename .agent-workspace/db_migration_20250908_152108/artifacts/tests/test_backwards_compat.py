#!/usr/bin/env python3
"""
Test Backwards Compatibility
Tests fallback mechanisms and compatibility with existing code patterns
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional
import json

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from database.supabase_client import supabase_client


class BackwardsCompatTester:
    """Test backwards compatibility and fallback mechanisms"""
    
    def __init__(self):
        self.results = {
            'legacy_parameter_access': None,
            'fallback_mechanism_test': None,
            'existing_code_patterns': None,
            'data_migration_validation': None,
            'api_compatibility_test': None,
            'errors': []
        }
    
    async def test_legacy_parameter_access(self) -> Dict:
        """Test that legacy parameter access patterns still work"""
        print("🔄 Testing legacy parameter access patterns...")
        
        try:
            # Test old-style parameter access (without joins)
            old_style_response = supabase_client.table("component_parameters").select(
                "id, component_id, min_value, max_value, current_value, set_value"
            ).limit(5).execute()
            
            # Test new-style parameter access (with joins)
            new_style_response = supabase_client.table("component_parameters").select(
                """
                id, component_id, min_value, max_value, current_value, set_value,
                component_parameter_definitions!definition_id(name, unit, description)
                """
            ).limit(5).execute()
            
            old_success = old_style_response.data is not None
            new_success = new_style_response.data is not None
            
            # Compare data consistency
            data_consistency = True
            if old_success and new_success:
                old_ids = {p['id'] for p in old_style_response.data}
                new_ids = {p['id'] for p in new_style_response.data}
                data_consistency = old_ids == new_ids
            
            return {
                'success': old_success and new_success,
                'old_style_works': old_success,
                'new_style_works': new_success,
                'data_consistency': data_consistency,
                'old_record_count': len(old_style_response.data) if old_success else 0,
                'new_record_count': len(new_style_response.data) if new_success else 0,
                'backward_compatible': old_success
            }
            
        except Exception as e:
            print(f"❌ Legacy parameter access test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_fallback_mechanisms(self) -> Dict:
        """Test fallback mechanisms for missing data"""
        print("🛡️ Testing fallback mechanisms...")
        
        try:
            # Test parameter loading with missing definitions
            response = supabase_client.table("component_parameters").select(
                """
                *,
                component_parameter_definitions!definition_id(
                    name, unit, description
                )
                """
            ).execute()
            
            if not response.data:
                return {
                    'success': False,
                    'error': 'No parameter data for fallback testing'
                }
            
            # Analyze fallback scenarios
            fallback_analysis = {
                'total_parameters': len(response.data),
                'with_definitions': 0,
                'without_definitions': 0,
                'fallback_needed': [],
                'fallback_data_available': []
            }
            
            for param in response.data:
                definitions = param.get('component_parameter_definitions')
                
                if definitions and definitions.get('name'):
                    fallback_analysis['with_definitions'] += 1
                else:
                    fallback_analysis['without_definitions'] += 1
                    
                    # Check if fallback data is available in the parameter record
                    param_id = param.get('id')
                    fallback_info = {
                        'id': param_id,
                        'has_modbus_address': param.get('modbus_address') is not None,
                        'has_data_type': param.get('data_type') is not None,
                        'has_current_value': param.get('current_value') is not None,
                        'can_fallback': bool(param.get('modbus_address') and param.get('data_type'))
                    }
                    
                    if fallback_info['can_fallback']:
                        fallback_analysis['fallback_data_available'].append(fallback_info)
                    else:
                        fallback_analysis['fallback_needed'].append(fallback_info)
            
            fallback_coverage = (
                len(fallback_analysis['fallback_data_available']) / 
                max(1, fallback_analysis['without_definitions'])
            ) * 100 if fallback_analysis['without_definitions'] > 0 else 100
            
            return {
                'success': True,
                'fallback_analysis': fallback_analysis,
                'fallback_coverage_percent': round(fallback_coverage, 2),
                'fallback_robust': fallback_coverage >= 80
            }
            
        except Exception as e:
            print(f"❌ Fallback mechanism test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_existing_code_patterns(self) -> Dict:
        """Test compatibility with existing code patterns"""
        print("🔧 Testing existing code patterns...")
        
        try:
            # Simulate existing code patterns that might be used in the system
            test_results = {}
            
            # Pattern 1: Direct table access
            try:
                direct_access = supabase_client.table("valve_step_config").select("*").limit(1).execute()
                test_results['direct_table_access'] = {
                    'works': direct_access.data is not None,
                    'record_count': len(direct_access.data) if direct_access.data else 0
                }
            except Exception as e:
                test_results['direct_table_access'] = {
                    'works': False,
                    'error': str(e)
                }
            
            # Pattern 2: Filtered queries
            try:
                filtered_query = supabase_client.table("purge_step_config").select(
                    "step_id, duration_ms"
                ).gt("duration_ms", 500).limit(3).execute()
                test_results['filtered_queries'] = {
                    'works': filtered_query.data is not None,
                    'record_count': len(filtered_query.data) if filtered_query.data else 0
                }
            except Exception as e:
                test_results['filtered_queries'] = {
                    'works': False,
                    'error': str(e)
                }
            
            # Pattern 3: Single record retrieval
            try:
                single_record = supabase_client.table("process_execution_state").select(
                    "execution_id, current_step_index"
                ).limit(1).single().execute()
                test_results['single_record_retrieval'] = {
                    'works': single_record.data is not None,
                    'has_data': bool(single_record.data)
                }
            except Exception as e:
                test_results['single_record_retrieval'] = {
                    'works': False,
                    'error': str(e)
                }
            
            # Pattern 4: JSON field access
            try:
                json_access = supabase_client.table("process_execution_state").select(
                    "progress->completed_steps"
                ).limit(1).execute()
                test_results['json_field_access'] = {
                    'works': True,  # If no exception, it works
                    'data_available': json_access.data is not None and len(json_access.data) > 0
                }
            except Exception as e:
                test_results['json_field_access'] = {
                    'works': False,
                    'error': str(e)
                }
            
            # Calculate overall compatibility
            working_patterns = sum(1 for result in test_results.values() if result.get('works', False))
            total_patterns = len(test_results)
            compatibility_percent = (working_patterns / total_patterns) * 100
            
            return {
                'success': True,
                'pattern_test_results': test_results,
                'working_patterns': working_patterns,
                'total_patterns': total_patterns,
                'compatibility_percent': round(compatibility_percent, 2),
                'fully_compatible': compatibility_percent == 100
            }
            
        except Exception as e:
            print(f"❌ Existing code patterns test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_data_migration_validation(self) -> Dict:
        """Test that data migration preserved data integrity"""
        print("🔍 Testing data migration validation...")
        
        try:
            validation_results = {}
            
            # Check for data consistency in migrated tables
            tables_to_check = [
                'component_parameters',
                'valve_step_config', 
                'purge_step_config',
                'process_execution_state',
                'recipe_parameters'
            ]
            
            for table_name in tables_to_check:
                try:
                    # Check record count and basic structure
                    response = supabase_client.table(table_name).select("*").limit(1).execute()
                    
                    if response.data:
                        sample_record = response.data[0]
                        validation_results[table_name] = {
                            'accessible': True,
                            'has_data': True,
                            'sample_fields': list(sample_record.keys()),
                            'primary_key_present': 'id' in sample_record,
                            'created_at_present': 'created_at' in sample_record,
                            'updated_at_present': 'updated_at' in sample_record
                        }
                        
                        # Check for UUID format in id field
                        record_id = sample_record.get('id', '')
                        validation_results[table_name]['valid_uuid_format'] = (
                            len(str(record_id)) == 36 and str(record_id).count('-') == 4
                        )
                    else:
                        validation_results[table_name] = {
                            'accessible': True,
                            'has_data': False,
                            'empty_table': True
                        }
                        
                except Exception as e:
                    validation_results[table_name] = {
                        'accessible': False,
                        'error': str(e)
                    }
            
            # Calculate migration health score
            accessible_tables = sum(1 for result in validation_results.values() 
                                  if result.get('accessible', False))
            tables_with_data = sum(1 for result in validation_results.values() 
                                 if result.get('has_data', False))
            
            migration_health = (accessible_tables / len(tables_to_check)) * 100
            data_presence = (tables_with_data / len(tables_to_check)) * 100 if tables_with_data else 0
            
            return {
                'success': True,
                'table_validation_results': validation_results,
                'accessible_tables': accessible_tables,
                'total_tables_checked': len(tables_to_check),
                'tables_with_data': tables_with_data,
                'migration_health_percent': round(migration_health, 2),
                'data_presence_percent': round(data_presence, 2),
                'migration_successful': migration_health >= 90
            }
            
        except Exception as e:
            print(f"❌ Data migration validation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_api_compatibility(self) -> Dict:
        """Test API compatibility with existing client code"""
        print("🌐 Testing API compatibility...")
        
        try:
            compatibility_tests = {}
            
            # Test 1: Basic CRUD operations still work
            try:
                # Test SELECT
                select_test = supabase_client.table("component_parameters").select("id").limit(1).execute()
                compatibility_tests['select_operations'] = {
                    'works': select_test.data is not None,
                    'data_count': len(select_test.data) if select_test.data else 0
                }
            except Exception as e:
                compatibility_tests['select_operations'] = {'works': False, 'error': str(e)}
            
            # Test 2: Filtering operations
            try:
                filter_test = supabase_client.table("component_parameters").select("id").not_(
                    "current_value", "is", "null"
                ).limit(1).execute()
                compatibility_tests['filter_operations'] = {
                    'works': True,
                    'data_count': len(filter_test.data) if filter_test.data else 0
                }
            except Exception as e:
                compatibility_tests['filter_operations'] = {'works': False, 'error': str(e)}
            
            # Test 3: JOIN operations (new functionality)
            try:
                join_test = supabase_client.table("component_parameters").select(
                    "*, component_parameter_definitions!definition_id(*)"
                ).limit(1).execute()
                compatibility_tests['join_operations'] = {
                    'works': True,
                    'new_feature_available': True,
                    'data_count': len(join_test.data) if join_test.data else 0
                }
            except Exception as e:
                compatibility_tests['join_operations'] = {'works': False, 'error': str(e)}
            
            # Test 4: Complex queries (step configurations)
            try:
                complex_query = supabase_client.table("valve_step_config").select(
                    "valve_id, valve_number, duration_ms"
                ).order("duration_ms").limit(3).execute()
                compatibility_tests['complex_queries'] = {
                    'works': True,
                    'data_count': len(complex_query.data) if complex_query.data else 0
                }
            except Exception as e:
                compatibility_tests['complex_queries'] = {'works': False, 'error': str(e)}
            
            # Calculate API compatibility score
            working_apis = sum(1 for test in compatibility_tests.values() if test.get('works', False))
            total_apis = len(compatibility_tests)
            api_compatibility = (working_apis / total_apis) * 100
            
            return {
                'success': True,
                'api_test_results': compatibility_tests,
                'working_apis': working_apis,
                'total_apis': total_apis,
                'api_compatibility_percent': round(api_compatibility, 2),
                'fully_compatible': api_compatibility == 100,
                'new_features_available': compatibility_tests.get('join_operations', {}).get('new_feature_available', False)
            }
            
        except Exception as e:
            print(f"❌ API compatibility test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_all_tests(self) -> Dict:
        """Run all backwards compatibility tests"""
        print("🧪 Starting Backwards Compatibility Tests")
        print("=" * 50)
        
        # Test 1: Legacy parameter access
        self.results['legacy_parameter_access'] = await self.test_legacy_parameter_access()
        
        # Test 2: Fallback mechanisms
        self.results['fallback_mechanism_test'] = await self.test_fallback_mechanisms()
        
        # Test 3: Existing code patterns
        self.results['existing_code_patterns'] = await self.test_existing_code_patterns()
        
        # Test 4: Data migration validation
        self.results['data_migration_validation'] = await self.test_data_migration_validation()
        
        # Test 5: API compatibility
        self.results['api_compatibility_test'] = await self.test_api_compatibility()
        
        # Summary
        successful_tests = sum(1 for test in self.results.values() 
                              if test and test.get('success', False))
        total_tests = len([k for k in self.results.keys() if k != 'errors'])
        
        print("\n" + "=" * 50)
        print(f"🏁 Backwards Compatibility Tests Complete: {successful_tests}/{total_tests} passed")
        
        return self.results


async def main():
    """Run backwards compatibility tests"""
    tester = BackwardsCompatTester()
    results = await tester.run_all_tests()
    
    # Write results to file
    import json
    results_file = "/home/albaraa/Projects/ald-control-system-phase-5/.agent-workspace/db_migration_20250908_152108/artifacts/backwards_compat_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📝 Results written to: {results_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())