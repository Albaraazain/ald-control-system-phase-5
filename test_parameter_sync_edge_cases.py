#!/usr/bin/env python3
"""
Edge case and validation tests for parameter synchronization.

Tests corner cases, error conditions, and validation scenarios
for component_parameters synchronization.
"""

import asyncio
import pytest
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock, patch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.db import get_supabase
from src.config import MACHINE_ID
from src.step_flow.parameter_step import set_parameter_value
from src.plc.manager import plc_manager


class ParameterSyncEdgeCaseTester:
    """Test edge cases and validation scenarios for parameter synchronization."""

    def __init__(self):
        self.supabase = get_supabase()
        self.test_machine_id = MACHINE_ID

    async def test_boundary_conditions(self):
        """Test parameter boundary conditions and validation."""
        logger.info("Testing parameter boundary conditions")

        try:
            # Get a parameter with defined boundaries
            param_result = self.supabase.table('component_parameters') \
                .select('*') \
                .eq('machine_id', self.test_machine_id) \
                .not_.is_('min_value', 'null') \
                .not_.is_('max_value', 'null') \
                .limit(1) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters with boundaries found'}

            param = param_result.data[0]
            param_id = param['id']
            min_val = param['min_value']
            max_val = param['max_value']

            test_results = {}

            # Test 1: Minimum boundary
            try:
                await set_parameter_value(param_id, min_val)
                test_results['min_boundary'] = {'success': True, 'value': min_val}
            except Exception as e:
                test_results['min_boundary'] = {'success': False, 'error': str(e)}

            # Test 2: Maximum boundary
            try:
                await set_parameter_value(param_id, max_val)
                test_results['max_boundary'] = {'success': True, 'value': max_val}
            except Exception as e:
                test_results['max_boundary'] = {'success': False, 'error': str(e)}

            # Test 3: Below minimum (should fail)
            try:
                await set_parameter_value(param_id, min_val - 1)
                test_results['below_min'] = {'success': True, 'error': 'Should have failed!'}
            except Exception as e:
                test_results['below_min'] = {'success': False, 'expected_error': str(e)}

            # Test 4: Above maximum (should fail)
            try:
                await set_parameter_value(param_id, max_val + 1)
                test_results['above_max'] = {'success': True, 'error': 'Should have failed!'}
            except Exception as e:
                test_results['above_max'] = {'success': False, 'expected_error': str(e)}

            return {
                'parameter_tested': param_id,
                'boundaries': {'min': min_val, 'max': max_val},
                'results': test_results
            }

        except Exception as e:
            logger.error(f"Error testing boundary conditions: {e}")
            return {'error': str(e)}

    async def test_null_and_invalid_values(self):
        """Test handling of null and invalid parameter values."""
        logger.info("Testing null and invalid value handling")

        try:
            param_result = self.supabase.table('component_parameters') \
                .select('*') \
                .eq('machine_id', self.test_machine_id) \
                .limit(1) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters found'}

            param = param_result.data[0]
            param_id = param['id']

            test_results = {}

            # Test invalid values
            invalid_values = [None, 'invalid_string', float('inf'), float('-inf'), [1, 2, 3]]

            for i, invalid_val in enumerate(invalid_values):
                test_key = f'invalid_value_{i}'
                try:
                    await set_parameter_value(param_id, invalid_val)
                    test_results[test_key] = {
                        'value': str(invalid_val),
                        'success': True,
                        'error': 'Should have failed!'
                    }
                except Exception as e:
                    test_results[test_key] = {
                        'value': str(invalid_val),
                        'success': False,
                        'expected_error': str(e)
                    }

            return {
                'parameter_tested': param_id,
                'invalid_value_tests': test_results
            }

        except Exception as e:
            logger.error(f"Error testing invalid values: {e}")
            return {'error': str(e)}

    async def test_concurrent_same_parameter(self):
        """Test concurrent operations on the same parameter."""
        logger.info("Testing concurrent operations on same parameter")

        try:
            param_result = self.supabase.table('component_parameters') \
                .select('*') \
                .eq('machine_id', self.test_machine_id) \
                .limit(1) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters found'}

            param = param_result.data[0]
            param_id = param['id']
            safe_value = (param['min_value'] + param['max_value']) / 2

            # Create multiple concurrent operations on same parameter
            async def set_param_with_id(operation_id, value_offset):
                try:
                    test_value = safe_value + value_offset
                    result = await set_parameter_value(param_id, test_value)
                    return {
                        'operation_id': operation_id,
                        'success': True,
                        'value_set': test_value,
                        'result': str(result)
                    }
                except Exception as e:
                    return {
                        'operation_id': operation_id,
                        'success': False,
                        'error': str(e)
                    }

            # Launch 5 concurrent operations
            tasks = [
                set_param_with_id(i, i * 0.1)
                for i in range(5)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_ops = sum(1 for r in results if not isinstance(r, Exception) and r.get('success'))

            # Check final parameter state
            final_result = self.supabase.table('component_parameters') \
                .select('current_value, set_value, updated_at') \
                .eq('id', param_id) \
                .single() \
                .execute()

            return {
                'parameter_tested': param_id,
                'concurrent_operations': len(tasks),
                'successful_operations': successful_ops,
                'final_state': final_result.data,
                'operation_results': [r if not isinstance(r, Exception) else {'error': str(r)} for r in results]
            }

        except Exception as e:
            logger.error(f"Error testing concurrent same parameter: {e}")
            return {'error': str(e)}

    async def test_plc_disconnection_scenarios(self):
        """Test parameter operations when PLC is disconnected."""
        logger.info("Testing PLC disconnection scenarios")

        try:
            param_result = self.supabase.table('component_parameters') \
                .select('*') \
                .eq('machine_id', self.test_machine_id) \
                .limit(1) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters found'}

            param = param_result.data[0]
            param_id = param['id']
            test_value = (param['min_value'] + param['max_value']) / 2

            # Store original PLC connection state
            original_connected = plc_manager.is_connected()
            original_plc = plc_manager.plc

            test_results = {}

            # Test 1: Parameter write with PLC disconnected
            try:
                # Simulate PLC disconnection
                plc_manager.plc = None

                await set_parameter_value(param_id, test_value)
                test_results['write_disconnected'] = {
                    'success': True,
                    'error': 'Should have failed!'
                }
            except Exception as e:
                test_results['write_disconnected'] = {
                    'success': False,
                    'expected_error': str(e)
                }

            # Test 2: Parameter read with PLC disconnected
            try:
                read_result = await plc_manager.read_all_parameters()
                test_results['read_disconnected'] = {
                    'success': True,
                    'result_count': len(read_result) if read_result else 0
                }
            except Exception as e:
                test_results['read_disconnected'] = {
                    'success': False,
                    'expected_error': str(e)
                }

            # Restore original PLC state
            plc_manager.plc = original_plc

            # Test 3: Parameter operation after reconnection
            if original_connected:
                try:
                    await set_parameter_value(param_id, test_value)
                    test_results['write_reconnected'] = {
                        'success': True,
                        'value_set': test_value
                    }
                except Exception as e:
                    test_results['write_reconnected'] = {
                        'success': False,
                        'error': str(e)
                    }

            return {
                'parameter_tested': param_id,
                'original_connection_state': original_connected,
                'disconnection_tests': test_results
            }

        except Exception as e:
            logger.error(f"Error testing PLC disconnection: {e}")
            return {'error': str(e)}

    async def test_database_constraint_violations(self):
        """Test database constraint violations and foreign key integrity."""
        logger.info("Testing database constraint violations")

        try:
            test_results = {}

            # Test 1: Invalid parameter ID
            fake_param_id = '00000000-0000-0000-0000-000000000000'
            try:
                await set_parameter_value(fake_param_id, 100)
                test_results['invalid_param_id'] = {
                    'success': True,
                    'error': 'Should have failed!'
                }
            except Exception as e:
                test_results['invalid_param_id'] = {
                    'success': False,
                    'expected_error': str(e)
                }

            # Test 2: Parameter from different machine
            other_machine_result = self.supabase.table('component_parameters') \
                .select('id') \
                .neq('machine_id', self.test_machine_id) \
                .limit(1) \
                .execute()

            if other_machine_result.data:
                other_param_id = other_machine_result.data[0]['id']
                try:
                    await set_parameter_value(other_param_id, 100)
                    test_results['wrong_machine_param'] = {
                        'success': True,
                        'warning': 'Cross-machine parameter access succeeded'
                    }
                except Exception as e:
                    test_results['wrong_machine_param'] = {
                        'success': False,
                        'expected_error': str(e)
                    }

            return {
                'constraint_violation_tests': test_results
            }

        except Exception as e:
            logger.error(f"Error testing database constraints: {e}")
            return {'error': str(e)}

    async def test_data_consistency_validation(self):
        """Test data consistency between different tables."""
        logger.info("Testing data consistency validation")

        try:
            # Check consistency between component_parameters and parameter_value_history
            param_result = self.supabase.table('component_parameters') \
                .select('id, current_value, set_value, updated_at') \
                .eq('machine_id', self.test_machine_id) \
                .limit(5) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters found'}

            consistency_results = []

            for param in param_result.data:
                param_id = param['id']

                # Get latest value from history
                history_result = self.supabase.table('parameter_value_history') \
                    .select('value, timestamp') \
                    .eq('parameter_id', param_id) \
                    .order('timestamp', desc=True) \
                    .limit(1) \
                    .execute()

                if history_result.data:
                    latest_history = history_result.data[0]

                    consistency_check = {
                        'parameter_id': param_id,
                        'component_current_value': param['current_value'],
                        'component_set_value': param['set_value'],
                        'component_updated_at': param['updated_at'],
                        'history_latest_value': latest_history['value'],
                        'history_timestamp': latest_history['timestamp'],
                        'current_value_matches_history': param['current_value'] == latest_history['value']
                    }

                    consistency_results.append(consistency_check)

            # Calculate consistency metrics
            total_params = len(consistency_results)
            consistent_params = sum(1 for r in consistency_results if r['current_value_matches_history'])

            return {
                'total_parameters_checked': total_params,
                'consistent_parameters': consistent_params,
                'consistency_rate': consistent_params / total_params if total_params > 0 else 0,
                'detailed_results': consistency_results
            }

        except Exception as e:
            logger.error(f"Error testing data consistency: {e}")
            return {'error': str(e)}

    async def run_edge_case_test_suite(self):
        """Run all edge case tests."""
        logger.info("🔍 RUNNING EDGE CASE TEST SUITE 🔍")

        results = {
            'test_timestamp': datetime.now(timezone.utc).isoformat(),
            'test_machine_id': self.test_machine_id
        }

        try:
            results['boundary_conditions'] = await self.test_boundary_conditions()
            results['null_invalid_values'] = await self.test_null_and_invalid_values()
            results['concurrent_same_parameter'] = await self.test_concurrent_same_parameter()
            results['plc_disconnection'] = await self.test_plc_disconnection_scenarios()
            results['database_constraints'] = await self.test_database_constraint_violations()
            results['data_consistency'] = await self.test_data_consistency_validation()

            # Calculate summary
            results['edge_case_summary'] = self._calculate_edge_case_summary(results)

        except Exception as e:
            logger.error(f"Error in edge case test suite: {e}")
            results['fatal_error'] = str(e)

        return results

    def _calculate_edge_case_summary(self, results):
        """Calculate edge case test summary."""
        summary = {
            'total_edge_cases': 0,
            'passed_edge_cases': 0,
            'failed_edge_cases': 0,
            'critical_edge_case_issues': [],
            'edge_case_recommendations': []
        }

        # Analyze each test category
        test_categories = [
            'boundary_conditions',
            'null_invalid_values',
            'concurrent_same_parameter',
            'plc_disconnection',
            'database_constraints',
            'data_consistency'
        ]

        for category in test_categories:
            if category in results and 'error' not in results[category]:
                summary['total_edge_cases'] += 1

                # Evaluate category success
                category_success = self._evaluate_edge_case_success(category, results[category])
                if category_success:
                    summary['passed_edge_cases'] += 1
                else:
                    summary['failed_edge_cases'] += 1

                    # Add specific recommendations
                    if category == 'data_consistency':
                        consistency_rate = results[category].get('consistency_rate', 0)
                        if consistency_rate < 0.9:
                            summary['critical_edge_case_issues'].append(
                                f"Data consistency issue: only {consistency_rate:.1%} consistency rate"
                            )
                            summary['edge_case_recommendations'].append(
                                "Implement real-time current_value synchronization"
                            )

        summary['edge_case_pass_rate'] = (
            summary['passed_edge_cases'] / summary['total_edge_cases']
        ) if summary['total_edge_cases'] > 0 else 0

        return summary

    def _evaluate_edge_case_success(self, category, result):
        """Evaluate if an edge case test was successful."""
        if category == 'boundary_conditions':
            return (
                result.get('results', {}).get('min_boundary', {}).get('success', False) and
                result.get('results', {}).get('max_boundary', {}).get('success', False) and
                not result.get('results', {}).get('below_min', {}).get('success', True) and
                not result.get('results', {}).get('above_max', {}).get('success', True)
            )
        elif category == 'data_consistency':
            return result.get('consistency_rate', 0) > 0.8
        elif category == 'concurrent_same_parameter':
            return result.get('successful_operations', 0) > 0
        else:
            return 'error' not in result


async def main():
    """Main edge case test execution."""
    tester = ParameterSyncEdgeCaseTester()

    try:
        results = await tester.run_edge_case_test_suite()

        print("\n" + "="*80)
        print("🔍 PARAMETER SYNCHRONIZATION EDGE CASE TEST RESULTS 🔍")
        print("="*80)

        if 'edge_case_summary' in results:
            summary = results['edge_case_summary']
            print(f"📊 EDGE CASE SUMMARY:")
            print(f"   Total Edge Cases: {summary['total_edge_cases']}")
            print(f"   Passed: {summary['passed_edge_cases']}")
            print(f"   Failed: {summary['failed_edge_cases']}")
            print(f"   Pass Rate: {summary['edge_case_pass_rate']:.1%}")

            if summary['critical_edge_case_issues']:
                print(f"\n🚨 CRITICAL EDGE CASE ISSUES:")
                for issue in summary['critical_edge_case_issues']:
                    print(f"   • {issue}")

        import json
        print(f"\n📋 DETAILED EDGE CASE RESULTS:")
        print(json.dumps(results, indent=2, default=str))

        return results

    except Exception as e:
        logger.error(f"Edge case test execution failed: {e}")
        return {'error': str(e)}


if __name__ == "__main__":
    asyncio.run(main())