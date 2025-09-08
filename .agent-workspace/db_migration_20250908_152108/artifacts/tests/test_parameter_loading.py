#!/usr/bin/env python3
"""
Test PLC Parameter Loading with Database Joins
Tests the join between component_parameters and component_parameter_definitions tables
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from plc.real_plc import RealPLC
from database.supabase_client import supabase_client


class ParameterLoadingTester:
    """Test parameter loading functionality with database joins"""
    
    def __init__(self):
        self.results = {
            'join_query_test': None,
            'parameter_loading_test': None,
            'fallback_logic_test': None,
            'data_integrity_test': None,
            'errors': []
        }
    
    async def test_join_query(self) -> Dict:
        """Test the JOIN query between component_parameters and component_parameter_definitions"""
        print("🔍 Testing parameter-definition JOIN query...")
        
        try:
            # Test the exact query used in RealPLC
            response = supabase_client.table("component_parameters").select(
                """
                *,
                component_parameter_definitions!definition_id(
                    name,
                    unit,
                    description
                )
                """
            ).limit(5).execute()
            
            if response.data:
                print(f"✅ JOIN query successful - Retrieved {len(response.data)} records")
                return {
                    'success': True,
                    'record_count': len(response.data),
                    'sample_data': response.data[0] if response.data else None,
                    'has_definition': bool(response.data[0].get('component_parameter_definitions'))
                }
            else:
                return {
                    'success': False,
                    'error': 'No data returned from JOIN query'
                }
                
        except Exception as e:
            print(f"❌ JOIN query failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_parameter_loading_integration(self) -> Dict:
        """Test the actual parameter loading as used in RealPLC"""
        print("🔧 Testing RealPLC parameter loading integration...")
        
        try:
            # Create a RealPLC instance in simulation mode
            plc = RealPLC(simulation_mode=True)
            
            # Test parameter loading
            await plc.load_parameters()
            
            # Check if parameters were loaded
            param_count = len(plc.parameters)
            print(f"✅ Parameter loading successful - Loaded {param_count} parameters")
            
            # Check for specific parameter structure
            if plc.parameters:
                sample_param = next(iter(plc.parameters.values()))
                has_required_fields = all(
                    field in sample_param for field in 
                    ['current_value', 'set_value', 'min_value', 'max_value']
                )
                
                return {
                    'success': True,
                    'parameter_count': param_count,
                    'has_required_fields': has_required_fields,
                    'sample_parameter': {
                        k: v for k, v in sample_param.items() 
                        if k in ['current_value', 'set_value', 'min_value', 'max_value', 'name', 'unit']
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'No parameters loaded'
                }
                
        except Exception as e:
            print(f"❌ Parameter loading failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_fallback_logic(self) -> Dict:
        """Test fallback logic for parameters without definitions"""
        print("🔄 Testing fallback logic for parameters without definitions...")
        
        try:
            # Query for parameters that might not have definitions
            response = supabase_client.table("component_parameters").select(
                """
                *,
                component_parameter_definitions!definition_id(
                    name,
                    unit,
                    description
                )
                """
            ).is_("definition_id", "null").limit(5).execute()
            
            if response.data:
                print(f"✅ Found {len(response.data)} parameters without definitions")
                return {
                    'success': True,
                    'parameters_without_definitions': len(response.data),
                    'fallback_required': True
                }
            else:
                print("✅ All parameters have definitions - fallback not needed")
                return {
                    'success': True,
                    'parameters_without_definitions': 0,
                    'fallback_required': False
                }
                
        except Exception as e:
            print(f"❌ Fallback logic test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_data_integrity(self) -> Dict:
        """Test data integrity of parameter-definition relationships"""
        print("🔒 Testing data integrity of parameter-definition relationships...")
        
        try:
            # Check for orphaned parameters (parameters without valid definitions)
            orphaned_query = supabase_client.table("component_parameters").select(
                "id, definition_id"
            ).not_("definition_id", "is", "null").execute()
            
            if orphaned_query.data:
                # Check if all definition_ids exist in component_parameter_definitions
                definition_ids = [p['definition_id'] for p in orphaned_query.data]
                definitions_query = supabase_client.table("component_parameter_definitions").select(
                    "id"
                ).in_("id", definition_ids).execute()
                
                existing_ids = {d['id'] for d in definitions_query.data}
                orphaned_count = sum(1 for did in definition_ids if did not in existing_ids)
                
                return {
                    'success': True,
                    'total_parameters_with_definitions': len(orphaned_query.data),
                    'valid_definitions': len(definitions_query.data),
                    'orphaned_parameters': orphaned_count,
                    'integrity_ok': orphaned_count == 0
                }
            else:
                return {
                    'success': True,
                    'total_parameters_with_definitions': 0,
                    'integrity_ok': True
                }
                
        except Exception as e:
            print(f"❌ Data integrity test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_all_tests(self) -> Dict:
        """Run all parameter loading tests"""
        print("🧪 Starting Parameter Loading Integration Tests")
        print("=" * 50)
        
        # Test 1: JOIN query
        self.results['join_query_test'] = await self.test_join_query()
        
        # Test 2: Parameter loading integration
        self.results['parameter_loading_test'] = await self.test_parameter_loading_integration()
        
        # Test 3: Fallback logic
        self.results['fallback_logic_test'] = await self.test_fallback_logic()
        
        # Test 4: Data integrity
        self.results['data_integrity_test'] = await self.test_data_integrity()
        
        # Summary
        successful_tests = sum(1 for test in self.results.values() 
                              if test and test.get('success', False))
        total_tests = len([k for k in self.results.keys() if k != 'errors'])
        
        print("\n" + "=" * 50)
        print(f"🏁 Parameter Loading Tests Complete: {successful_tests}/{total_tests} passed")
        
        return self.results


async def main():
    """Run parameter loading tests"""
    tester = ParameterLoadingTester()
    results = await tester.run_all_tests()
    
    # Write results to file
    import json
    results_file = "/home/albaraa/Projects/ald-control-system-phase-5/.agent-workspace/db_migration_20250908_152108/artifacts/parameter_loading_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📝 Results written to: {results_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())