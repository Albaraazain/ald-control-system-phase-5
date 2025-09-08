#!/usr/bin/env python3
"""
Performance and Load Testing for ALD Control System
Tests database performance, query execution times, and concurrent access patterns
"""

import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import statistics

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from db import get_supabase
    from log_setup import logger
    from config import MACHINE_ID
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

class PerformanceLoadTester:
    """Performance and load testing for database operations"""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.machine_id = MACHINE_ID
        
    async def execute_performance_tests(self) -> Dict[str, Any]:
        """Execute comprehensive performance and load tests"""
        logger.info("⚡ Starting performance and load testing")
        
        test_results = {
            'test_execution_id': f"performance_test_{int(time.time())}",
            'started_at': datetime.now().isoformat(),
            'machine_id': str(self.machine_id),
            'performance_tests': {},
            'summary': {}
        }
        
        performance_tests = [
            ("Query Response Times", self.test_query_response_times),
            ("Complex Join Performance", self.test_complex_join_performance), 
            ("Concurrent Access Simulation", self.test_concurrent_access),
            ("Large Dataset Queries", self.test_large_dataset_queries),
            ("Insert Performance", self.test_insert_performance),
            ("Update Performance", self.test_update_performance),
            ("Database Connection Load", self.test_connection_load),
        ]
        
        for test_name, test_func in performance_tests:
            logger.info(f"📊 Running: {test_name}")
            try:
                start_time = time.time()
                test_result = await test_func()
                test_duration = time.time() - start_time
                
                test_result['test_duration_seconds'] = test_duration
                test_results['performance_tests'][test_name] = test_result
                
                status = "PASSED" if test_result.get('performance_acceptable', False) else "FAILED"
                logger.info(f"{'✅' if status == 'PASSED' else '⚠️'} {test_name}: {status} ({test_duration:.2f}s)")
                
            except Exception as e:
                logger.error(f"❌ {test_name} failed: {str(e)}")
                test_results['performance_tests'][test_name] = {
                    'performance_acceptable': False,
                    'error': str(e),
                    'test_duration_seconds': 0
                }
        
        # Calculate summary
        test_results['completed_at'] = datetime.now().isoformat()
        test_results['total_duration'] = (
            datetime.fromisoformat(test_results['completed_at'].replace('Z', '+00:00')) - 
            datetime.fromisoformat(test_results['started_at'])
        ).total_seconds()
        test_results['summary'] = self.calculate_performance_summary(test_results['performance_tests'])
        
        # Save results
        report_filename = f"performance_test_results_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(test_results, f, indent=2, default=str)
        
        logger.info(f"📊 Performance test results saved to {report_filename}")
        return test_results
    
    async def test_query_response_times(self) -> Dict[str, Any]:
        """Test basic query response times"""
        logger.info("⏱️ Testing query response times")
        
        query_tests = [
            {
                'name': 'simple_recipe_select',
                'description': 'Select recipes with basic filters',
                'max_acceptable_time': 2.0,
                'query_func': lambda: self.supabase.table('recipes').select('id, name').limit(10).execute()
            },
            {
                'name': 'recipe_with_steps_join',
                'description': 'Recipe with steps count',
                'max_acceptable_time': 3.0,
                'query_func': lambda: self.supabase.table('recipes').select('id, name, recipe_steps(count)').limit(5).execute()
            },
            {
                'name': 'steps_with_configurations',
                'description': 'Steps with configuration details',
                'max_acceptable_time': 4.0,
                'query_func': lambda: self.supabase.table('recipe_steps').select(
                    'id, name, type, valve_step_config(*), purge_step_config(*)'
                ).limit(20).execute()
            },
            {
                'name': 'command_history',
                'description': 'Recent command history',
                'max_acceptable_time': 2.5,
                'query_func': lambda: self.supabase.table('recipe_commands').select(
                    'id, type, status, created_at'
                ).eq('machine_id', self.machine_id).order('created_at', desc=True).limit(50).execute()
            }
        ]
        
        query_results = []
        acceptable_queries = 0
        
        for test in query_tests:
            times = []
            errors = []
            
            # Run each query multiple times for average
            for i in range(3):
                try:
                    start_time = time.time()
                    result = test['query_func']()
                    query_time = time.time() - start_time
                    times.append(query_time)
                    
                    # Verify result has data
                    if not hasattr(result, 'data') or result.data is None:
                        errors.append(f"Run {i+1}: No data returned")
                        
                except Exception as e:
                    errors.append(f"Run {i+1}: {str(e)}")
            
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                acceptable = avg_time <= test['max_acceptable_time']
                
                if acceptable:
                    acceptable_queries += 1
                
                query_result = {
                    'test_name': test['name'],
                    'description': test['description'],
                    'average_time': avg_time,
                    'min_time': min_time,
                    'max_time': max_time,
                    'max_acceptable_time': test['max_acceptable_time'],
                    'performance_acceptable': acceptable,
                    'successful_runs': len(times),
                    'errors': errors
                }
            else:
                query_result = {
                    'test_name': test['name'],
                    'description': test['description'],
                    'performance_acceptable': False,
                    'successful_runs': 0,
                    'errors': errors
                }
            
            query_results.append(query_result)
        
        overall_acceptable = acceptable_queries >= len(query_tests) * 0.8
        
        return {
            'performance_acceptable': overall_acceptable,
            'total_query_tests': len(query_tests),
            'acceptable_queries': acceptable_queries,
            'query_test_results': query_results,
            'performance_criteria': '80% of queries must meet time requirements'
        }
    
    async def test_complex_join_performance(self) -> Dict[str, Any]:
        """Test complex join query performance"""
        logger.info("🔗 Testing complex join performance")
        
        try:
            # Complex join query simulating recipe execution view
            start_time = time.time()
            
            # Get recipes with full details
            recipes_result = self.supabase.table('recipes').select(
                '''
                id, name, description,
                recipe_steps(
                    id, name, type, sequence_number,
                    valve_step_config(valve_number, duration_ms),
                    purge_step_config(gas_type, duration_ms),
                    loop_step_config(iteration_count)
                ),
                recipe_parameters(parameter_name, parameter_value, parameter_type)
                '''
            ).or_('name.ilike.%Test%,name.ilike.%Integration%').limit(3).execute()
            
            complex_query_time = time.time() - start_time
            
            # Verify we got meaningful data
            recipes = recipes_result.data if recipes_result.data else []
            has_nested_data = False
            
            for recipe in recipes:
                if recipe.get('recipe_steps') and recipe.get('recipe_parameters'):
                    has_nested_data = True
                    break
            
            # Performance criteria: Complex queries should complete within 10 seconds
            acceptable_time = 10.0
            performance_acceptable = complex_query_time <= acceptable_time and has_nested_data
            
            return {
                'performance_acceptable': performance_acceptable,
                'complex_query_time': complex_query_time,
                'max_acceptable_time': acceptable_time,
                'recipes_returned': len(recipes),
                'has_nested_data': has_nested_data,
                'performance_criteria': f'Complex joins must complete within {acceptable_time}s with valid nested data'
            }
            
        except Exception as e:
            return {
                'performance_acceptable': False,
                'error': str(e),
                'complex_query_time': 0
            }
    
    async def test_concurrent_access(self) -> Dict[str, Any]:
        """Test concurrent access simulation"""
        logger.info("🔀 Testing concurrent access patterns")
        
        def execute_concurrent_query(query_id: int) -> Dict[str, Any]:
            """Execute a query in concurrent context"""
            try:
                start_time = time.time()
                
                # Different query types for concurrent testing
                if query_id % 3 == 0:
                    # Recipe queries
                    result = self.supabase.table('recipes').select('id, name').limit(5).execute()
                elif query_id % 3 == 1:
                    # Step queries  
                    result = self.supabase.table('recipe_steps').select('id, name, type').limit(10).execute()
                else:
                    # Command queries
                    result = self.supabase.table('recipe_commands').select(
                        'id, type, status'
                    ).eq('machine_id', self.machine_id).limit(5).execute()
                
                query_time = time.time() - start_time
                
                return {
                    'query_id': query_id,
                    'success': True,
                    'query_time': query_time,
                    'result_count': len(result.data) if result.data else 0
                }
                
            except Exception as e:
                return {
                    'query_id': query_id,
                    'success': False,
                    'error': str(e),
                    'query_time': 0
                }
        
        try:
            # Execute concurrent queries
            concurrent_count = 10
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(execute_concurrent_query, i) 
                    for i in range(concurrent_count)
                ]
                
                concurrent_results = [future.result() for future in futures]
            
            total_concurrent_time = time.time() - start_time
            
            # Analyze results
            successful_queries = sum(1 for r in concurrent_results if r['success'])
            query_times = [r['query_time'] for r in concurrent_results if r['success']]
            
            if query_times:
                avg_concurrent_time = statistics.mean(query_times)
                max_concurrent_time = max(query_times)
            else:
                avg_concurrent_time = 0
                max_concurrent_time = 0
            
            # Performance criteria: 90% success rate, average time under 5s
            success_rate = successful_queries / concurrent_count
            performance_acceptable = success_rate >= 0.9 and avg_concurrent_time <= 5.0
            
            return {
                'performance_acceptable': performance_acceptable,
                'concurrent_queries': concurrent_count,
                'successful_queries': successful_queries,
                'success_rate': success_rate,
                'total_execution_time': total_concurrent_time,
                'average_query_time': avg_concurrent_time,
                'max_query_time': max_concurrent_time,
                'concurrent_results': concurrent_results,
                'performance_criteria': '90% success rate with avg time < 5s'
            }
            
        except Exception as e:
            return {
                'performance_acceptable': False,
                'error': str(e),
                'concurrent_queries': 0
            }
    
    async def test_large_dataset_queries(self) -> Dict[str, Any]:
        """Test queries against larger datasets"""
        logger.info("📊 Testing large dataset queries")
        
        large_dataset_tests = [
            {
                'name': 'all_recipes_pagination',
                'description': 'Paginate through all recipes',
                'max_acceptable_time': 5.0,
                'query_func': lambda: self.supabase.table('recipes').select(
                    'id, name, created_at'
                ).order('created_at', desc=True).limit(100).execute()
            },
            {
                'name': 'all_steps_with_type_filter',
                'description': 'All steps filtered by type',
                'max_acceptable_time': 6.0,
                'query_func': lambda: self.supabase.table('recipe_steps').select(
                    'id, name, type, recipe_id'
                ).eq('type', 'valve').limit(200).execute()
            },
            {
                'name': 'command_history_large',
                'description': 'Large command history query',
                'max_acceptable_time': 4.0,
                'query_func': lambda: self.supabase.table('recipe_commands').select(
                    'id, type, status, created_at'
                ).order('created_at', desc=True).limit(500).execute()
            }
        ]
        
        large_query_results = []
        acceptable_large_queries = 0
        
        for test in large_dataset_tests:
            try:
                start_time = time.time()
                result = test['query_func']()
                query_time = time.time() - start_time
                
                result_count = len(result.data) if result.data else 0
                acceptable = query_time <= test['max_acceptable_time']
                
                if acceptable:
                    acceptable_large_queries += 1
                
                large_query_result = {
                    'test_name': test['name'],
                    'description': test['description'],
                    'query_time': query_time,
                    'max_acceptable_time': test['max_acceptable_time'],
                    'result_count': result_count,
                    'performance_acceptable': acceptable
                }
                
            except Exception as e:
                large_query_result = {
                    'test_name': test['name'],
                    'description': test['description'],
                    'performance_acceptable': False,
                    'error': str(e),
                    'query_time': 0,
                    'result_count': 0
                }
            
            large_query_results.append(large_query_result)
        
        overall_acceptable = acceptable_large_queries >= len(large_dataset_tests) * 0.75
        
        return {
            'performance_acceptable': overall_acceptable,
            'total_large_dataset_tests': len(large_dataset_tests),
            'acceptable_large_queries': acceptable_large_queries,
            'large_dataset_results': large_query_results,
            'performance_criteria': '75% of large dataset queries must meet time requirements'
        }
    
    async def test_insert_performance(self) -> Dict[str, Any]:
        """Test insert operation performance"""
        logger.info("➕ Testing insert performance")
        
        try:
            # Test batch command inserts
            test_commands = []
            insert_times = []
            
            # Create test data
            for i in range(5):
                test_command = {
                    'type': f'performance_test_{i}',
                    'parameters': {'test_id': i, 'timestamp': datetime.now().isoformat()},
                    'status': 'pending',
                    'machine_id': self.machine_id
                }
                test_commands.append(test_command)
            
            # Test individual inserts
            for i, command in enumerate(test_commands):
                try:
                    start_time = time.time()
                    result = self.supabase.table('recipe_commands').insert(command).execute()
                    insert_time = time.time() - start_time
                    insert_times.append(insert_time)
                    
                    # Clean up immediately
                    if result.data:
                        command_id = result.data[0]['id']
                        self.supabase.table('recipe_commands').delete().eq('id', command_id).execute()
                        
                except Exception as e:
                    logger.warning(f"Insert test {i} failed: {e}")
            
            if insert_times:
                avg_insert_time = statistics.mean(insert_times)
                max_insert_time = max(insert_times)
                
                # Performance criteria: Average insert time under 2 seconds
                performance_acceptable = avg_insert_time <= 2.0 and len(insert_times) >= 3
            else:
                avg_insert_time = 0
                max_insert_time = 0
                performance_acceptable = False
            
            return {
                'performance_acceptable': performance_acceptable,
                'total_inserts_attempted': len(test_commands),
                'successful_inserts': len(insert_times),
                'average_insert_time': avg_insert_time,
                'max_insert_time': max_insert_time,
                'max_acceptable_avg_time': 2.0,
                'performance_criteria': 'Average insert time < 2s with >60% success rate'
            }
            
        except Exception as e:
            return {
                'performance_acceptable': False,
                'error': str(e),
                'total_inserts_attempted': 0
            }
    
    async def test_update_performance(self) -> Dict[str, Any]:
        """Test update operation performance"""
        logger.info("✏️ Testing update performance")
        
        try:
            # Create a test command to update
            test_command = {
                'type': 'update_performance_test',
                'parameters': {'initial': 'value'},
                'status': 'pending',
                'machine_id': self.machine_id
            }
            
            # Insert test command
            insert_result = self.supabase.table('recipe_commands').insert(test_command).execute()
            
            if not insert_result.data:
                return {
                    'performance_acceptable': False,
                    'error': 'Failed to create test command for update testing',
                    'updates_attempted': 0
                }
            
            command_id = insert_result.data[0]['id']
            update_times = []
            
            # Test multiple updates
            for i in range(3):
                try:
                    start_time = time.time()
                    
                    update_result = self.supabase.table('recipe_commands').update({
                        'parameters': {'update_iteration': i, 'timestamp': datetime.now().isoformat()},
                        'status': 'processing' if i % 2 == 0 else 'pending'
                    }).eq('id', command_id).execute()
                    
                    update_time = time.time() - start_time
                    update_times.append(update_time)
                    
                except Exception as e:
                    logger.warning(f"Update test {i} failed: {e}")
            
            # Clean up test command
            try:
                self.supabase.table('recipe_commands').delete().eq('id', command_id).execute()
            except:
                pass  # Cleanup failure is not critical
            
            if update_times:
                avg_update_time = statistics.mean(update_times)
                max_update_time = max(update_times)
                
                # Performance criteria: Average update time under 1.5 seconds
                performance_acceptable = avg_update_time <= 1.5 and len(update_times) >= 2
            else:
                avg_update_time = 0
                max_update_time = 0
                performance_acceptable = False
            
            return {
                'performance_acceptable': performance_acceptable,
                'updates_attempted': 3,
                'successful_updates': len(update_times),
                'average_update_time': avg_update_time,
                'max_update_time': max_update_time,
                'max_acceptable_avg_time': 1.5,
                'performance_criteria': 'Average update time < 1.5s'
            }
            
        except Exception as e:
            return {
                'performance_acceptable': False,
                'error': str(e),
                'updates_attempted': 0
            }
    
    async def test_connection_load(self) -> Dict[str, Any]:
        """Test database connection under load"""
        logger.info("🔗 Testing database connection load")
        
        try:
            # Test rapid sequential connections
            connection_times = []
            connection_errors = []
            
            for i in range(10):
                try:
                    start_time = time.time()
                    
                    # Test simple query to verify connection
                    result = self.supabase.table('machines').select('id').eq('id', self.machine_id).execute()
                    
                    connection_time = time.time() - start_time
                    connection_times.append(connection_time)
                    
                    if not result.data:
                        connection_errors.append(f"Connection {i}: No data returned")
                        
                except Exception as e:
                    connection_errors.append(f"Connection {i}: {str(e)}")
            
            if connection_times:
                avg_connection_time = statistics.mean(connection_times)
                max_connection_time = max(connection_times)
                min_connection_time = min(connection_times)
                
                # Performance criteria: Average connection time under 3 seconds, 80% success rate
                success_rate = len(connection_times) / 10
                performance_acceptable = avg_connection_time <= 3.0 and success_rate >= 0.8
            else:
                avg_connection_time = 0
                max_connection_time = 0  
                min_connection_time = 0
                success_rate = 0
                performance_acceptable = False
            
            return {
                'performance_acceptable': performance_acceptable,
                'total_connection_tests': 10,
                'successful_connections': len(connection_times),
                'connection_success_rate': success_rate,
                'average_connection_time': avg_connection_time,
                'min_connection_time': min_connection_time,
                'max_connection_time': max_connection_time,
                'connection_errors': connection_errors,
                'performance_criteria': 'Avg connection time < 3s with 80% success rate'
            }
            
        except Exception as e:
            return {
                'performance_acceptable': False,
                'error': str(e),
                'total_connection_tests': 0
            }
    
    def calculate_performance_summary(self, performance_tests: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall performance summary"""
        
        total_tests = len(performance_tests)
        acceptable_performance_tests = sum(
            1 for test in performance_tests.values() 
            if test.get('performance_acceptable', False)
        )
        
        failed_tests = total_tests - acceptable_performance_tests
        
        # Calculate average test duration
        test_durations = [
            test.get('test_duration_seconds', 0) 
            for test in performance_tests.values()
        ]
        avg_test_duration = statistics.mean(test_durations) if test_durations else 0
        
        return {
            'total_performance_tests': total_tests,
            'acceptable_performance_tests': acceptable_performance_tests,
            'failed_performance_tests': failed_tests,
            'performance_success_rate': acceptable_performance_tests / total_tests if total_tests > 0 else 0,
            'overall_performance_acceptable': failed_tests <= 1,  # Allow 1 failure
            'average_test_duration': avg_test_duration,
            'performance_test_results': {
                name: test.get('performance_acceptable', False)
                for name, test in performance_tests.items()
            }
        }

async def main():
    """Main execution function"""
    tester = PerformanceLoadTester()
    results = await tester.execute_performance_tests()
    
    print("\n" + "="*80)
    print("⚡ PERFORMANCE AND LOAD TESTING - COMPLETE")
    print("="*80)
    print(f"Overall Performance: {'✅ ACCEPTABLE' if results['summary']['overall_performance_acceptable'] else '⚠️ NEEDS ATTENTION'}")
    print(f"Success Rate: {results['summary']['performance_success_rate']:.2%}")
    print(f"Tests Passed: {results['summary']['acceptable_performance_tests']}/{results['summary']['total_performance_tests']}")
    print(f"Average Test Duration: {results['summary']['average_test_duration']:.2f}s")
    print("="*80)
    
    # Print individual test results
    for test_name, result in results['performance_tests'].items():
        status = "✅ ACCEPTABLE" if result.get('performance_acceptable', False) else "⚠️ NEEDS ATTENTION"
        duration = result.get('test_duration_seconds', 0)
        print(f"{test_name}: {status} ({duration:.2f}s)")
        
        if not result.get('performance_acceptable', False) and 'error' in result:
            print(f"  Issue: {result['error']}")
    
    print("="*80)
    return results

if __name__ == "__main__":
    asyncio.run(main())