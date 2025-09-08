#!/usr/bin/env python3
"""
Test Process State Tracking
Tests process_execution_state table operations and recipe parameter integration
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional
import json

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from database.supabase_client import supabase_client


class ProcessStateTester:
    """Test process execution state tracking functionality"""
    
    def __init__(self):
        self.results = {
            'process_state_structure_test': None,
            'recipe_parameters_test': None,
            'state_update_simulation': None,
            'json_field_validation': None,
            'execution_metrics_test': None,
            'errors': []
        }
    
    async def test_process_state_structure(self) -> Dict:
        """Test process execution state table structure and data"""
        print("📊 Testing process execution state structure...")
        
        try:
            response = supabase_client.table("process_execution_state").select("*").limit(5).execute()
            
            if response.data:
                print(f"✅ Process state query successful - Retrieved {len(response.data)} records")
                
                # Analyze structure of first record
                sample_state = response.data[0]
                required_fields = [
                    'execution_id', 'current_step_index', 'current_overall_step',
                    'current_step', 'progress', 'process_metrics'
                ]
                
                field_analysis = {}
                for field in required_fields:
                    field_analysis[field] = {
                        'present': field in sample_state,
                        'value_type': type(sample_state.get(field)).__name__,
                        'is_null': sample_state.get(field) is None
                    }
                
                # Check JSON fields specifically
                json_fields = ['current_step', 'progress', 'process_metrics']
                json_analysis = {}
                for field in json_fields:
                    value = sample_state.get(field)
                    if value:
                        json_analysis[field] = {
                            'is_dict': isinstance(value, dict),
                            'keys': list(value.keys()) if isinstance(value, dict) else [],
                            'size': len(value) if isinstance(value, (dict, list)) else 0
                        }
                
                return {
                    'success': True,
                    'record_count': len(response.data),
                    'field_analysis': field_analysis,
                    'json_analysis': json_analysis,
                    'sample_execution_id': sample_state.get('execution_id'),
                    'has_step_tracking': bool(sample_state.get('current_step_index') is not None),
                    'has_progress_data': bool(sample_state.get('progress')),
                    'has_metrics': bool(sample_state.get('process_metrics'))
                }
            else:
                return {
                    'success': False,
                    'error': 'No process execution state data found'
                }
                
        except Exception as e:
            print(f"❌ Process state structure test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_recipe_parameters(self) -> Dict:
        """Test recipe parameters table and integration"""
        print("🧪 Testing recipe parameters...")
        
        try:
            response = supabase_client.table("recipe_parameters").select("*").limit(10).execute()
            
            if response.data:
                print(f"✅ Recipe parameters query successful - Retrieved {len(response.data)} records")
                
                # Analyze parameter structure
                sample_param = response.data[0]
                required_fields = ['recipe_id', 'parameter_name', 'parameter_value', 'parameter_type']
                
                field_analysis = {}
                for field in required_fields:
                    field_analysis[field] = {
                        'present': field in sample_param,
                        'value_type': type(sample_param.get(field)).__name__,
                        'sample_value': sample_param.get(field)
                    }
                
                # Analyze parameter types and values
                parameter_types = {}
                for param in response.data:
                    param_type = param.get('parameter_type')
                    if param_type:
                        if param_type not in parameter_types:
                            parameter_types[param_type] = 0
                        parameter_types[param_type] += 1
                
                return {
                    'success': True,
                    'record_count': len(response.data),
                    'field_analysis': field_analysis,
                    'parameter_types': parameter_types,
                    'sample_parameter': sample_param,
                    'has_critical_params': any(p.get('is_critical') for p in response.data)
                }
            else:
                return {
                    'success': False,
                    'error': 'No recipe parameters found'
                }
                
        except Exception as e:
            print(f"❌ Recipe parameters test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_state_update_simulation(self) -> Dict:
        """Simulate state update operations (read-only test)"""
        print("🔄 Testing state update simulation...")
        
        try:
            # Get an existing execution state
            response = supabase_client.table("process_execution_state").select("*").limit(1).execute()
            
            if not response.data:
                return {
                    'success': False,
                    'error': 'No execution state found for simulation'
                }
            
            state = response.data[0]
            execution_id = state['execution_id']
            
            # Test reading current state
            current_state = supabase_client.table("process_execution_state").select(
                "current_step_index, current_overall_step, progress"
            ).eq("execution_id", execution_id).single().execute()
            
            if current_state.data:
                # Simulate what an update would look like
                simulated_update = {
                    'current_step_index': (current_state.data.get('current_step_index', 0) + 1) % 10,
                    'current_overall_step': (current_state.data.get('current_overall_step', 0) + 1) % 20,
                    'progress': {
                        'completed_steps': (current_state.data.get('progress', {}).get('completed_steps', 0) + 1) % 10,
                        'total_steps': 10,
                        'percentage': min(100, ((current_state.data.get('progress', {}).get('completed_steps', 0) + 1) / 10) * 100)
                    }
                }
                
                return {
                    'success': True,
                    'execution_id': execution_id,
                    'current_state': current_state.data,
                    'simulated_update': simulated_update,
                    'update_fields_valid': all(
                        key in ['current_step_index', 'current_overall_step', 'progress']
                        for key in simulated_update.keys()
                    )
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to read current state for simulation'
                }
                
        except Exception as e:
            print(f"❌ State update simulation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_json_field_validation(self) -> Dict:
        """Test JSON field structure and validation"""
        print("🔍 Testing JSON field validation...")
        
        try:
            response = supabase_client.table("process_execution_state").select(
                "current_step, progress, process_metrics"
            ).limit(5).execute()
            
            if not response.data:
                return {
                    'success': False,
                    'error': 'No data for JSON validation'
                }
            
            validation_results = {
                'current_step_validation': [],
                'progress_validation': [],
                'metrics_validation': []
            }
            
            for record in response.data:
                # Validate current_step JSON structure
                current_step = record.get('current_step')
                if current_step:
                    step_validation = {
                        'has_id': 'id' in current_step,
                        'has_type': 'type' in current_step,
                        'has_name': 'name' in current_step,
                        'has_parameters': 'parameters' in current_step,
                        'valid_structure': all(key in current_step for key in ['id', 'type', 'name'])
                    }
                    validation_results['current_step_validation'].append(step_validation)
                
                # Validate progress JSON structure
                progress = record.get('progress')
                if progress:
                    progress_validation = {
                        'has_completed_steps': 'completed_steps' in progress,
                        'has_total_steps': 'total_steps' in progress,
                        'has_percentage': 'percentage' in progress,
                        'valid_numbers': all(
                            isinstance(progress.get(key), (int, float)) 
                            for key in ['completed_steps', 'total_steps'] 
                            if key in progress
                        )
                    }
                    validation_results['progress_validation'].append(progress_validation)
                
                # Validate process_metrics JSON structure
                metrics = record.get('process_metrics')
                if metrics:
                    metrics_validation = {
                        'has_timing': 'timing' in metrics,
                        'has_progress': 'progress' in metrics,
                        'has_performance': 'performance' in metrics,
                        'structure_depth': self._get_json_depth(metrics)
                    }
                    validation_results['metrics_validation'].append(metrics_validation)
            
            return {
                'success': True,
                'validation_summary': {
                    'current_step_records': len(validation_results['current_step_validation']),
                    'progress_records': len(validation_results['progress_validation']),
                    'metrics_records': len(validation_results['metrics_validation'])
                },
                'validation_details': validation_results
            }
            
        except Exception as e:
            print(f"❌ JSON field validation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_json_depth(self, obj, depth=0):
        """Get the maximum depth of a JSON object"""
        if not isinstance(obj, dict):
            return depth
        
        if not obj:
            return depth
        
        return max(self._get_json_depth(v, depth + 1) for v in obj.values())
    
    async def test_execution_metrics(self) -> Dict:
        """Test execution metrics and performance data"""
        print("📈 Testing execution metrics...")
        
        try:
            # Query for records with metrics
            response = supabase_client.table("process_execution_state").select(
                "execution_id, process_metrics, last_updated, created_at"
            ).not_("process_metrics", "is", "null").limit(5).execute()
            
            if response.data:
                metrics_analysis = {
                    'records_with_metrics': len(response.data),
                    'metric_types': set(),
                    'timing_data_available': 0,
                    'performance_data_available': 0
                }
                
                for record in response.data:
                    metrics = record.get('process_metrics', {})
                    
                    # Collect metric types
                    if isinstance(metrics, dict):
                        metrics_analysis['metric_types'].update(metrics.keys())
                        
                        if 'timing' in metrics:
                            metrics_analysis['timing_data_available'] += 1
                        
                        if 'performance' in metrics:
                            metrics_analysis['performance_data_available'] += 1
                
                # Convert set to list for JSON serialization
                metrics_analysis['metric_types'] = list(metrics_analysis['metric_types'])
                
                return {
                    'success': True,
                    'metrics_analysis': metrics_analysis,
                    'sample_metrics': response.data[0].get('process_metrics') if response.data else None
                }
            else:
                return {
                    'success': True,
                    'metrics_analysis': {
                        'records_with_metrics': 0,
                        'note': 'No records with process metrics found'
                    }
                }
                
        except Exception as e:
            print(f"❌ Execution metrics test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_all_tests(self) -> Dict:
        """Run all process state tests"""
        print("🧪 Starting Process State Tests")
        print("=" * 50)
        
        # Test 1: Process state structure
        self.results['process_state_structure_test'] = await self.test_process_state_structure()
        
        # Test 2: Recipe parameters
        self.results['recipe_parameters_test'] = await self.test_recipe_parameters()
        
        # Test 3: State update simulation
        self.results['state_update_simulation'] = await self.test_state_update_simulation()
        
        # Test 4: JSON field validation
        self.results['json_field_validation'] = await self.test_json_field_validation()
        
        # Test 5: Execution metrics
        self.results['execution_metrics_test'] = await self.test_execution_metrics()
        
        # Summary
        successful_tests = sum(1 for test in self.results.values() 
                              if test and test.get('success', False))
        total_tests = len([k for k in self.results.keys() if k != 'errors'])
        
        print("\n" + "=" * 50)
        print(f"🏁 Process State Tests Complete: {successful_tests}/{total_tests} passed")
        
        return self.results


async def main():
    """Run process state tests"""
    tester = ProcessStateTester()
    results = await tester.run_all_tests()
    
    # Write results to file
    import json
    results_file = "/home/albaraa/Projects/ald-control-system-phase-5/.agent-workspace/db_migration_20250908_152108/artifacts/process_state_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📝 Results written to: {results_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())