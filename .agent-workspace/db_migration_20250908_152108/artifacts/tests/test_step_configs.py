#!/usr/bin/env python3
"""
Test Step Configuration Loading
Tests valve_step_config and purge_step_config table access and integration
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from database.supabase_client import supabase_client
from step_flow.valve_step import ValveStep
from step_flow.purge_step import PurgeStep


class StepConfigTester:
    """Test step configuration loading functionality"""
    
    def __init__(self):
        self.results = {
            'valve_config_test': None,
            'purge_config_test': None,
            'valve_step_integration': None,
            'purge_step_integration': None,
            'config_validation_test': None,
            'errors': []
        }
    
    async def test_valve_config_loading(self) -> Dict:
        """Test valve step configuration loading"""
        print("🚰 Testing valve step configuration loading...")
        
        try:
            response = supabase_client.table("valve_step_config").select("*").limit(10).execute()
            
            if response.data:
                print(f"✅ Valve config query successful - Retrieved {len(response.data)} records")
                
                # Validate required fields
                sample_config = response.data[0]
                required_fields = ['step_id', 'valve_id', 'valve_number', 'duration_ms']
                missing_fields = [field for field in required_fields if field not in sample_config]
                
                return {
                    'success': True,
                    'record_count': len(response.data),
                    'sample_config': sample_config,
                    'required_fields_present': len(missing_fields) == 0,
                    'missing_fields': missing_fields,
                    'has_duration': sample_config.get('duration_ms') is not None,
                    'has_valve_info': all(sample_config.get(f) for f in ['valve_id', 'valve_number'])
                }
            else:
                return {
                    'success': False,
                    'error': 'No valve configuration data found'
                }
                
        except Exception as e:
            print(f"❌ Valve config loading failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_purge_config_loading(self) -> Dict:
        """Test purge step configuration loading"""
        print("💨 Testing purge step configuration loading...")
        
        try:
            response = supabase_client.table("purge_step_config").select("*").limit(10).execute()
            
            if response.data:
                print(f"✅ Purge config query successful - Retrieved {len(response.data)} records")
                
                # Validate required fields
                sample_config = response.data[0]
                required_fields = ['step_id', 'duration_ms', 'gas_type', 'flow_rate']
                missing_fields = [field for field in required_fields if field not in sample_config]
                
                return {
                    'success': True,
                    'record_count': len(response.data),
                    'sample_config': sample_config,
                    'required_fields_present': len(missing_fields) == 0,
                    'missing_fields': missing_fields,
                    'has_duration': sample_config.get('duration_ms') is not None,
                    'has_gas_info': all(sample_config.get(f) for f in ['gas_type', 'flow_rate'])
                }
            else:
                return {
                    'success': False,
                    'error': 'No purge configuration data found'
                }
                
        except Exception as e:
            print(f"❌ Purge config loading failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_valve_step_integration(self) -> Dict:
        """Test ValveStep class integration with valve_step_config"""
        print("🔧 Testing ValveStep integration with configuration...")
        
        try:
            # Get a real step_id from the database
            config_response = supabase_client.table("valve_step_config").select("step_id").limit(1).execute()
            
            if not config_response.data:
                return {
                    'success': False,
                    'error': 'No valve step configurations found for integration test'
                }
            
            step_id = config_response.data[0]['step_id']
            
            # Create ValveStep instance
            valve_step = ValveStep(step_id, simulation_mode=True)
            
            # Test parameter loading
            await valve_step.load_parameters()
            
            # Validate loaded parameters
            has_valve_params = hasattr(valve_step, 'valve_number') and hasattr(valve_step, 'duration_ms')
            valve_number_valid = getattr(valve_step, 'valve_number', None) is not None
            duration_valid = getattr(valve_step, 'duration_ms', None) is not None
            
            return {
                'success': True,
                'step_id': step_id,
                'parameters_loaded': has_valve_params,
                'valve_number_valid': valve_number_valid,
                'duration_valid': duration_valid,
                'valve_number': getattr(valve_step, 'valve_number', None),
                'duration_ms': getattr(valve_step, 'duration_ms', None)
            }
            
        except Exception as e:
            print(f"❌ ValveStep integration test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_purge_step_integration(self) -> Dict:
        """Test PurgeStep class integration with purge_step_config"""
        print("🔧 Testing PurgeStep integration with configuration...")
        
        try:
            # Get a real step_id from the database
            config_response = supabase_client.table("purge_step_config").select("step_id").limit(1).execute()
            
            if not config_response.data:
                return {
                    'success': False,
                    'error': 'No purge step configurations found for integration test'
                }
            
            step_id = config_response.data[0]['step_id']
            
            # Create PurgeStep instance
            purge_step = PurgeStep(step_id, simulation_mode=True)
            
            # Test parameter loading
            await purge_step.load_parameters()
            
            # Validate loaded parameters
            has_purge_params = hasattr(purge_step, 'gas_type') and hasattr(purge_step, 'flow_rate') and hasattr(purge_step, 'duration_ms')
            gas_type_valid = getattr(purge_step, 'gas_type', None) is not None
            flow_rate_valid = getattr(purge_step, 'flow_rate', None) is not None
            duration_valid = getattr(purge_step, 'duration_ms', None) is not None
            
            return {
                'success': True,
                'step_id': step_id,
                'parameters_loaded': has_purge_params,
                'gas_type_valid': gas_type_valid,
                'flow_rate_valid': flow_rate_valid,
                'duration_valid': duration_valid,
                'gas_type': getattr(purge_step, 'gas_type', None),
                'flow_rate': getattr(purge_step, 'flow_rate', None),
                'duration_ms': getattr(purge_step, 'duration_ms', None)
            }
            
        except Exception as e:
            print(f"❌ PurgeStep integration test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_config_validation(self) -> Dict:
        """Test configuration data validation and consistency"""
        print("🔍 Testing configuration data validation...")
        
        try:
            results = {
                'valve_validation': {},
                'purge_validation': {}
            }
            
            # Validate valve configurations
            valve_response = supabase_client.table("valve_step_config").select("*").execute()
            if valve_response.data:
                valid_valves = 0
                invalid_valves = []
                
                for config in valve_response.data:
                    is_valid = True
                    issues = []
                    
                    # Check duration
                    if not config.get('duration_ms') or config['duration_ms'] <= 0:
                        is_valid = False
                        issues.append('Invalid duration_ms')
                    
                    # Check valve number
                    if not config.get('valve_number') or config['valve_number'] <= 0:
                        is_valid = False
                        issues.append('Invalid valve_number')
                    
                    # Check valve_id
                    if not config.get('valve_id'):
                        is_valid = False
                        issues.append('Missing valve_id')
                    
                    if is_valid:
                        valid_valves += 1
                    else:
                        invalid_valves.append({
                            'step_id': config.get('step_id'),
                            'issues': issues
                        })
                
                results['valve_validation'] = {
                    'total_configs': len(valve_response.data),
                    'valid_configs': valid_valves,
                    'invalid_configs': len(invalid_valves),
                    'invalid_details': invalid_valves[:5]  # Limit to first 5
                }
            
            # Validate purge configurations
            purge_response = supabase_client.table("purge_step_config").select("*").execute()
            if purge_response.data:
                valid_purges = 0
                invalid_purges = []
                
                for config in purge_response.data:
                    is_valid = True
                    issues = []
                    
                    # Check duration
                    if not config.get('duration_ms') or config['duration_ms'] <= 0:
                        is_valid = False
                        issues.append('Invalid duration_ms')
                    
                    # Check gas_type
                    if not config.get('gas_type'):
                        is_valid = False
                        issues.append('Missing gas_type')
                    
                    # Check flow_rate
                    if not config.get('flow_rate'):
                        is_valid = False
                        issues.append('Missing flow_rate')
                    
                    if is_valid:
                        valid_purges += 1
                    else:
                        invalid_purges.append({
                            'step_id': config.get('step_id'),
                            'issues': issues
                        })
                
                results['purge_validation'] = {
                    'total_configs': len(purge_response.data),
                    'valid_configs': valid_purges,
                    'invalid_configs': len(invalid_purges),
                    'invalid_details': invalid_purges[:5]  # Limit to first 5
                }
            
            return {
                'success': True,
                'validation_results': results
            }
            
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_all_tests(self) -> Dict:
        """Run all step configuration tests"""
        print("🧪 Starting Step Configuration Tests")
        print("=" * 50)
        
        # Test 1: Valve config loading
        self.results['valve_config_test'] = await self.test_valve_config_loading()
        
        # Test 2: Purge config loading
        self.results['purge_config_test'] = await self.test_purge_config_loading()
        
        # Test 3: Valve step integration
        self.results['valve_step_integration'] = await self.test_valve_step_integration()
        
        # Test 4: Purge step integration
        self.results['purge_step_integration'] = await self.test_purge_step_integration()
        
        # Test 5: Configuration validation
        self.results['config_validation_test'] = await self.test_config_validation()
        
        # Summary
        successful_tests = sum(1 for test in self.results.values() 
                              if test and test.get('success', False))
        total_tests = len([k for k in self.results.keys() if k != 'errors'])
        
        print("\n" + "=" * 50)
        print(f"🏁 Step Configuration Tests Complete: {successful_tests}/{total_tests} passed")
        
        return self.results


async def main():
    """Run step configuration tests"""
    tester = StepConfigTester()
    results = await tester.run_all_tests()
    
    # Write results to file
    import json
    results_file = "/home/albaraa/Projects/ald-control-system-phase-5/.agent-workspace/db_migration_20250908_152108/artifacts/step_config_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📝 Results written to: {results_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())