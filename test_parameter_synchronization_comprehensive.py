#!/usr/bin/env python3
"""
Comprehensive test suite for parameter table synchronization.

Tests both current state and proposed synchronization enhancements for
component_parameters.current_value and set_value updates across all PLC operations.

Based on gap analysis findings:
- CRITICAL GAP: current_value not updated during PLC reads
- PARTIAL COMPLIANCE: set_value updated in some operations but not others
- SOLUTION: Extend transactional dual-mode logging for atomic synchronization
"""

import asyncio
import pytest
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, patch

# Test framework setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import system under test
from src.db import get_supabase
from src.config import MACHINE_ID
from src.data_collection.service import data_collection_service
from src.data_collection.transactional_adapter import transactional_parameter_logger_adapter
from src.step_flow.parameter_step import set_parameter_value
from src.plc.manager import plc_manager
from src.parameter_control_listener import ParameterControlListener


class ParameterSynchronizationTester:
    """Comprehensive test suite for parameter table synchronization."""

    def __init__(self):
        self.supabase = get_supabase()
        self.test_parameters = []
        self.test_machine_id = MACHINE_ID
        self.baseline_metrics = {}

    async def setup_test_environment(self):
        """Set up test environment with clean state."""
        logger.info("Setting up parameter synchronization test environment")

        # Get test parameters from database
        result = self.supabase.table('component_parameters') \
            .select('*') \
            .eq('machine_id', self.test_machine_id) \
            .limit(10) \
            .execute()

        self.test_parameters = result.data if result.data else []

        if not self.test_parameters:
            logger.error("No test parameters found in database")
            return False

        logger.info(f"Found {len(self.test_parameters)} test parameters")
        return True

    async def test_current_state_gaps(self):
        """Test current state to validate identified gaps."""
        logger.info("=== TESTING CURRENT STATE GAPS ===")

        test_results = {
            'current_value_gap': await self._test_current_value_gap(),
            'set_value_partial_compliance': await self._test_set_value_partial_compliance(),
            'transactional_integration': await self._test_transactional_integration()
        }

        return test_results

    async def _test_current_value_gap(self):
        """Test the critical gap: current_value not updated during PLC reads."""
        logger.info("Testing current_value gap in continuous parameter logging")

        try:
            # Get initial parameter state
            param = self.test_parameters[0]
            param_id = param['id']

            initial_result = self.supabase.table('component_parameters') \
                .select('current_value, updated_at') \
                .eq('id', param_id) \
                .single() \
                .execute()

            initial_current_value = initial_result.data['current_value']
            initial_updated_at = initial_result.data['updated_at']

            # Simulate PLC read operation (current continuous logging)
            if plc_manager.is_connected():
                parameter_values = await plc_manager.read_all_parameters()

                # Wait for continuous logging cycle
                await asyncio.sleep(2)

                # Check if current_value was updated
                updated_result = self.supabase.table('component_parameters') \
                    .select('current_value, updated_at') \
                    .eq('id', param_id) \
                    .single() \
                    .execute()

                updated_current_value = updated_result.data['current_value']
                updated_updated_at = updated_result.data['updated_at']

                gap_exists = (
                    initial_current_value == updated_current_value and
                    initial_updated_at == updated_updated_at
                )

                return {
                    'gap_confirmed': gap_exists,
                    'initial_value': initial_current_value,
                    'final_value': updated_current_value,
                    'parameter_id': param_id,
                    'plc_read_count': len(parameter_values) if parameter_values else 0,
                    'message': 'CRITICAL GAP CONFIRMED: PLC reads do not update current_value' if gap_exists
                              else 'Gap not confirmed - current_value was updated'
                }
            else:
                return {
                    'gap_confirmed': None,
                    'message': 'PLC not connected - cannot test read operations'
                }

        except Exception as e:
            logger.error(f"Error testing current_value gap: {e}")
            return {'error': str(e)}

    async def _test_set_value_partial_compliance(self):
        """Test partial compliance: set_value updated in some operations but not others."""
        logger.info("Testing set_value partial compliance across different operations")

        try:
            param = self.test_parameters[0]
            param_id = param['id']
            test_value = param['min_value'] + 1  # Safe test value

            test_results = {}

            # Test 1: Recipe parameter step (should update set_value)
            try:
                initial_set_value = param['set_value']
                await set_parameter_value(param_id, test_value)

                updated_result = self.supabase.table('component_parameters') \
                    .select('set_value') \
                    .eq('id', param_id) \
                    .single() \
                    .execute()

                new_set_value = updated_result.data['set_value']

                test_results['recipe_parameter_step'] = {
                    'set_value_updated': new_set_value == test_value,
                    'initial_value': initial_set_value,
                    'final_value': new_set_value,
                    'compliant': new_set_value == test_value
                }

            except Exception as e:
                test_results['recipe_parameter_step'] = {'error': str(e)}

            # Test 2: Direct PLC write (check for missing updates)
            try:
                if plc_manager.plc:
                    # Direct PLC write without going through parameter step
                    plc_success = await plc_manager.plc.write_parameter(param_id, test_value + 1)

                    # Check if set_value was updated (it shouldn't be in current implementation)
                    await asyncio.sleep(0.5)  # Brief delay

                    direct_result = self.supabase.table('component_parameters') \
                        .select('set_value') \
                        .eq('id', param_id) \
                        .single() \
                        .execute()

                    direct_set_value = direct_result.data['set_value']

                    test_results['direct_plc_write'] = {
                        'plc_write_success': plc_success,
                        'set_value_updated': direct_set_value == test_value + 1,
                        'final_value': direct_set_value,
                        'gap_confirmed': plc_success and direct_set_value != test_value + 1
                    }

            except Exception as e:
                test_results['direct_plc_write'] = {'error': str(e)}

            return test_results

        except Exception as e:
            logger.error(f"Error testing set_value partial compliance: {e}")
            return {'error': str(e)}

    async def _test_transactional_integration(self):
        """Test integration with existing transactional logging system."""
        logger.info("Testing transactional system integration")

        try:
            # Test transactional adapter health
            health_status = await transactional_parameter_logger_adapter.get_health_status()

            # Test atomic operation capability
            atomic_test = await transactional_parameter_logger_adapter.test_atomic_operation()

            # Test dual-mode logging
            if data_collection_service.is_running:
                service_status = data_collection_service.get_status()
            else:
                service_status = {'service_running': False}

            return {
                'transactional_health': health_status,
                'atomic_test_result': atomic_test,
                'service_status': service_status,
                'integration_ready': health_status.get('overall_status') == 'healthy'
            }

        except Exception as e:
            logger.error(f"Error testing transactional integration: {e}")
            return {'error': str(e)}

    async def test_synchronization_scenarios(self):
        """Test proposed synchronization enhancement scenarios."""
        logger.info("=== TESTING SYNCHRONIZATION ENHANCEMENT SCENARIOS ===")

        test_results = {
            'concurrent_operations': await self._test_concurrent_operations(),
            'transaction_atomicity': await self._test_transaction_atomicity(),
            'rollback_scenarios': await self._test_rollback_scenarios(),
            'dual_mode_consistency': await self._test_dual_mode_consistency()
        }

        return test_results

    async def _test_concurrent_operations(self):
        """Test concurrent read/write operations with synchronization."""
        logger.info("Testing concurrent parameter operations")

        try:
            # Create multiple concurrent parameter operations
            params = self.test_parameters[:3]  # Use first 3 parameters

            async def concurrent_read_write(param):
                param_id = param['id']
                test_value = param['min_value'] + 2

                # Concurrent operations
                read_task = asyncio.create_task(plc_manager.read_parameter(param_id))
                write_task = asyncio.create_task(set_parameter_value(param_id, test_value))

                read_result, write_result = await asyncio.gather(
                    read_task, write_task, return_exceptions=True
                )

                return {
                    'param_id': param_id,
                    'read_success': not isinstance(read_result, Exception),
                    'write_success': not isinstance(write_result, Exception),
                    'read_result': read_result if not isinstance(read_result, Exception) else str(read_result),
                    'write_result': write_result if not isinstance(write_result, Exception) else str(write_result)
                }

            # Run concurrent operations on multiple parameters
            concurrent_tasks = [concurrent_read_write(param) for param in params]
            results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)

            successful_operations = sum(1 for r in results if not isinstance(r, Exception))

            return {
                'total_operations': len(params),
                'successful_operations': successful_operations,
                'results': [r if not isinstance(r, Exception) else {'error': str(r)} for r in results],
                'concurrency_success_rate': successful_operations / len(params) if params else 0
            }

        except Exception as e:
            logger.error(f"Error testing concurrent operations: {e}")
            return {'error': str(e)}

    async def _test_transaction_atomicity(self):
        """Test transaction atomicity with parameter synchronization."""
        logger.info("Testing transaction atomicity")

        try:
            # Test atomic parameter logging
            test_parameters = {
                param['id']: param['current_value'] or 0
                for param in self.test_parameters[:3]
            }

            # Use transactional logger
            from src.data_collection.transactional import transactional_logger

            if not transactional_logger._is_initialized:
                await transactional_logger.initialize()

            result = await transactional_logger.log_parameters_atomic(
                test_parameters, self.test_machine_id
            )

            return {
                'atomic_operation_success': result.success,
                'transaction_id': result.transaction_id,
                'history_count': result.history_count,
                'process_count': result.process_count,
                'error_message': result.error_message,
                'atomicity_confirmed': result.success and result.transaction_id != 'error'
            }

        except Exception as e:
            logger.error(f"Error testing transaction atomicity: {e}")
            return {'error': str(e)}

    async def _test_rollback_scenarios(self):
        """Test transaction rollback scenarios."""
        logger.info("Testing transaction rollback scenarios")

        try:
            # Simulate a scenario that should trigger rollback
            param = self.test_parameters[0]
            param_id = param['id']

            # Store initial state
            initial_result = self.supabase.table('component_parameters') \
                .select('current_value, set_value') \
                .eq('id', param_id) \
                .single() \
                .execute()

            initial_state = initial_result.data

            # Attempt operation that should fail (value out of range)
            invalid_value = param['max_value'] + 1000  # Way out of range

            try:
                await set_parameter_value(param_id, invalid_value)
                rollback_triggered = False
            except Exception as e:
                rollback_triggered = True
                rollback_error = str(e)

            # Check if state was preserved
            final_result = self.supabase.table('component_parameters') \
                .select('current_value, set_value') \
                .eq('id', param_id) \
                .single() \
                .execute()

            final_state = final_result.data

            state_preserved = (
                initial_state['current_value'] == final_state['current_value'] and
                initial_state['set_value'] == final_state['set_value']
            )

            return {
                'rollback_triggered': rollback_triggered,
                'state_preserved': state_preserved,
                'initial_state': initial_state,
                'final_state': final_state,
                'rollback_error': rollback_error if rollback_triggered else None,
                'rollback_working': rollback_triggered and state_preserved
            }

        except Exception as e:
            logger.error(f"Error testing rollback scenarios: {e}")
            return {'error': str(e)}

    async def _test_dual_mode_consistency(self):
        """Test dual-mode operation consistency (idle vs process running)."""
        logger.info("Testing dual-mode operation consistency")

        try:
            # Check current machine state
            state_result = self.supabase.table('machines') \
                .select('current_process_id, status') \
                .eq('id', self.test_machine_id) \
                .single() \
                .execute()

            current_state = state_result.data
            is_processing = current_state.get('current_process_id') is not None

            # Test parameter logging in current mode
            test_params = {param['id']: param['current_value'] or 0 for param in self.test_parameters[:2]}

            # Use transactional adapter to log parameters
            if not transactional_parameter_logger_adapter.is_running:
                await transactional_parameter_logger_adapter.start()

            # Read parameters using the adapter's method
            await transactional_parameter_logger_adapter._read_and_log_parameters_transactional()

            # Check parameter_value_history logging
            history_result = self.supabase.table('parameter_value_history') \
                .select('*') \
                .eq('machine_id', self.test_machine_id) \
                .order('timestamp', desc=True) \
                .limit(5) \
                .execute()

            # Check process_data_points logging (if in process mode)
            process_result = None
            if is_processing:
                process_result = self.supabase.table('process_data_points') \
                    .select('*') \
                    .eq('process_id', current_state['current_process_id']) \
                    .order('timestamp', desc=True) \
                    .limit(5) \
                    .execute()

            return {
                'machine_state': current_state,
                'is_processing': is_processing,
                'history_logging': len(history_result.data) if history_result.data else 0,
                'process_logging': len(process_result.data) if process_result and process_result.data else 0,
                'dual_mode_working': (
                    len(history_result.data) > 0 if history_result.data else False
                ) and (
                    not is_processing or (process_result and len(process_result.data) > 0)
                )
            }

        except Exception as e:
            logger.error(f"Error testing dual-mode consistency: {e}")
            return {'error': str(e)}

    async def run_comprehensive_test_suite(self):
        """Run the complete comprehensive test suite."""
        logger.info("🚀 STARTING COMPREHENSIVE PARAMETER SYNCHRONIZATION TEST SUITE 🚀")

        # Setup
        setup_success = await self.setup_test_environment()
        if not setup_success:
            return {'error': 'Failed to setup test environment'}

        # Run all test categories
        results = {
            'test_timestamp': datetime.now(timezone.utc).isoformat(),
            'test_machine_id': self.test_machine_id,
            'test_parameter_count': len(self.test_parameters),
            'setup_success': setup_success
        }

        try:
            # Test current state gaps
            results['current_state_gaps'] = await self.test_current_state_gaps()

            # Test synchronization scenarios
            results['synchronization_scenarios'] = await self.test_synchronization_scenarios()

            # Calculate overall results
            results['test_summary'] = self._calculate_test_summary(results)

        except Exception as e:
            logger.error(f"Error in comprehensive test suite: {e}")
            results['fatal_error'] = str(e)

        return results

    def _calculate_test_summary(self, results):
        """Calculate overall test summary."""
        summary = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'critical_issues': [],
            'recommendations': []
        }

        # Analyze current state gaps
        if 'current_state_gaps' in results:
            gaps = results['current_state_gaps']

            # Current value gap
            if 'current_value_gap' in gaps:
                summary['total_tests'] += 1
                if gaps['current_value_gap'].get('gap_confirmed'):
                    summary['failed_tests'] += 1
                    summary['critical_issues'].append(
                        "CRITICAL: current_value not updated during PLC reads"
                    )
                    summary['recommendations'].append(
                        "Implement current_value synchronization in transactional dual-mode repository"
                    )
                else:
                    summary['passed_tests'] += 1

            # Set value compliance
            if 'set_value_partial_compliance' in gaps:
                summary['total_tests'] += 1
                compliance = gaps['set_value_partial_compliance']

                recipe_compliant = compliance.get('recipe_parameter_step', {}).get('compliant', False)
                direct_gap = compliance.get('direct_plc_write', {}).get('gap_confirmed', False)

                if recipe_compliant and not direct_gap:
                    summary['passed_tests'] += 1
                else:
                    summary['failed_tests'] += 1
                    if direct_gap:
                        summary['critical_issues'].append(
                            "ISSUE: Direct PLC writes don't update set_value"
                        )
                        summary['recommendations'].append(
                            "Ensure all PLC write operations update set_value consistently"
                        )

        # Analyze synchronization scenarios
        if 'synchronization_scenarios' in results:
            scenarios = results['synchronization_scenarios']

            for scenario_name, scenario_result in scenarios.items():
                summary['total_tests'] += 1

                if 'error' in scenario_result:
                    summary['failed_tests'] += 1
                    summary['critical_issues'].append(f"ERROR in {scenario_name}: {scenario_result['error']}")
                else:
                    # Evaluate scenario success based on specific criteria
                    scenario_success = self._evaluate_scenario_success(scenario_name, scenario_result)
                    if scenario_success:
                        summary['passed_tests'] += 1
                    else:
                        summary['failed_tests'] += 1

        summary['pass_rate'] = (summary['passed_tests'] / summary['total_tests']) if summary['total_tests'] > 0 else 0

        return summary

    def _evaluate_scenario_success(self, scenario_name, result):
        """Evaluate if a scenario test was successful."""
        if scenario_name == 'concurrent_operations':
            return result.get('concurrency_success_rate', 0) > 0.8
        elif scenario_name == 'transaction_atomicity':
            return result.get('atomicity_confirmed', False)
        elif scenario_name == 'rollback_scenarios':
            return result.get('rollback_working', False)
        elif scenario_name == 'dual_mode_consistency':
            return result.get('dual_mode_working', False)

        return False


async def main():
    """Main test execution function."""
    tester = ParameterSynchronizationTester()

    try:
        results = await tester.run_comprehensive_test_suite()

        # Print results
        print("\n" + "="*80)
        print("🧪 PARAMETER SYNCHRONIZATION TEST RESULTS 🧪")
        print("="*80)

        if 'test_summary' in results:
            summary = results['test_summary']
            print(f"📊 SUMMARY:")
            print(f"   Total Tests: {summary['total_tests']}")
            print(f"   Passed: {summary['passed_tests']}")
            print(f"   Failed: {summary['failed_tests']}")
            print(f"   Pass Rate: {summary['pass_rate']:.1%}")

            if summary['critical_issues']:
                print(f"\n🚨 CRITICAL ISSUES:")
                for issue in summary['critical_issues']:
                    print(f"   • {issue}")

            if summary['recommendations']:
                print(f"\n💡 RECOMMENDATIONS:")
                for rec in summary['recommendations']:
                    print(f"   • {rec}")

        print(f"\n📋 DETAILED RESULTS:")
        import json
        print(json.dumps(results, indent=2, default=str))

        return results

    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return {'error': str(e)}


if __name__ == "__main__":
    asyncio.run(main())