#!/usr/bin/env python3
"""
Execute comprehensive parameter synchronization validation based on agent coordination findings.

This script validates:
1. Current state gaps identified by investigator and reviewer agents
2. Implementation progress from implementer agents
3. Performance impact as identified by performance tester
4. Enterprise compliance as validated by compliance auditor

Based on coordination findings:
- Dual-mode repository ALREADY implements component_parameters synchronization
- Continuous logger bypasses transactional repository (critical gap)
- Real PLC has excellent individual parameter current_value updates
- Enterprise-grade compliance with A+ readiness
"""

import asyncio
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import our test modules
sys.path.append(str(Path(__file__).parent))

from test_parameter_synchronization_comprehensive import ParameterSynchronizationTester
from test_parameter_sync_edge_cases import ParameterSyncEdgeCaseTester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParameterSyncValidationExecutor:
    """Execute comprehensive validation based on agent coordination findings."""

    def __init__(self):
        self.comprehensive_tester = ParameterSynchronizationTester()
        self.edge_case_tester = ParameterSyncEdgeCaseTester()
        self.validation_results = {}

    async def validate_agent_findings(self):
        """Validate specific findings from coordinating agents."""
        logger.info("🔍 VALIDATING AGENT COORDINATION FINDINGS 🔍")

        findings_validation = {}

        # 1. Validate investigator finding: dual-mode repository has component_parameters sync
        findings_validation['dual_mode_repository_sync'] = await self._validate_dual_mode_sync()

        # 2. Validate critical gap: continuous logger bypasses transactional repository
        findings_validation['continuous_logger_gap'] = await self._validate_continuous_logger_gap()

        # 3. Validate real PLC current_value patterns
        findings_validation['real_plc_patterns'] = await self._validate_real_plc_patterns()

        # 4. Validate enterprise compliance claims
        findings_validation['enterprise_compliance'] = await self._validate_enterprise_compliance()

        return findings_validation

    async def _validate_dual_mode_sync(self):
        """Validate that dual-mode repository supports component_parameters synchronization."""
        try:
            from src.data_collection.transactional import transactional_logger
            from src.data_collection.transactional.interfaces import DualModeResult

            # Initialize transactional logger
            if not transactional_logger._is_initialized:
                await transactional_logger.initialize()

            # Test atomic operation with component_parameters
            test_params = {'test_param_1': 42.0, 'test_param_2': 100}
            result = await transactional_logger.log_parameters_atomic(test_params)

            # Check if result includes component_updates_count (new field)
            has_component_updates = hasattr(result, 'component_updates_count')

            return {
                'dual_mode_supports_component_sync': has_component_updates,
                'atomic_operation_success': result.success,
                'component_updates_count': getattr(result, 'component_updates_count', 'not_available'),
                'transaction_id': result.transaction_id,
                'finding_validated': has_component_updates and result.success
            }

        except Exception as e:
            logger.error(f"Error validating dual-mode sync: {e}")
            return {'error': str(e), 'finding_validated': False}

    async def _validate_continuous_logger_gap(self):
        """Validate the critical gap in continuous logger."""
        try:
            from src.data_collection.continuous_parameter_logger import ContinuousParameterLogger
            from src.db import get_supabase

            supabase = get_supabase()

            # Get a test parameter
            param_result = supabase.table('component_parameters') \
                .select('id, current_value, updated_at') \
                .limit(1) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters available for testing'}

            param = param_result.data[0]
            initial_current_value = param['current_value']
            initial_updated_at = param['updated_at']

            # Create continuous logger instance
            logger_instance = ContinuousParameterLogger(interval_seconds=1.0)

            # Start it briefly to trigger parameter reading
            await logger_instance.start()
            await asyncio.sleep(2)  # Let it run one cycle
            await logger_instance.stop()

            # Check if component_parameters.current_value was updated
            updated_result = supabase.table('component_parameters') \
                .select('current_value, updated_at') \
                .eq('id', param['id']) \
                .single() \
                .execute()

            final_current_value = updated_result.data['current_value']
            final_updated_at = updated_result.data['updated_at']

            # Gap exists if values weren't updated
            gap_confirmed = (
                initial_current_value == final_current_value and
                initial_updated_at == final_updated_at
            )

            return {
                'continuous_logger_gap_confirmed': gap_confirmed,
                'initial_current_value': initial_current_value,
                'final_current_value': final_current_value,
                'timestamps_unchanged': initial_updated_at == final_updated_at,
                'finding_validated': gap_confirmed  # Gap should exist per agent findings
            }

        except Exception as e:
            logger.error(f"Error validating continuous logger gap: {e}")
            return {'error': str(e), 'finding_validated': False}

    async def _validate_real_plc_patterns(self):
        """Validate real PLC current_value update patterns."""
        try:
            from src.plc.manager import plc_manager
            from src.db import get_supabase

            if not plc_manager.is_connected():
                return {'error': 'PLC not connected', 'finding_validated': None}

            supabase = get_supabase()

            # Get a test parameter
            param_result = supabase.table('component_parameters') \
                .select('id, current_value, updated_at') \
                .limit(1) \
                .execute()

            if not param_result.data:
                return {'error': 'No parameters available for testing'}

            param = param_result.data[0]
            param_id = param['id']
            initial_current_value = param['current_value']
            initial_updated_at = param['updated_at']

            # Read individual parameter (should trigger current_value update in real PLC)
            plc_value = await plc_manager.read_parameter(param_id)

            # Brief delay for async update
            await asyncio.sleep(1)

            # Check if current_value was updated
            updated_result = supabase.table('component_parameters') \
                .select('current_value, updated_at') \
                .eq('id', param_id) \
                .single() \
                .execute()

            final_current_value = updated_result.data['current_value']
            final_updated_at = updated_result.data['updated_at']

            current_value_updated = final_current_value != initial_current_value
            timestamp_updated = final_updated_at != initial_updated_at

            return {
                'individual_parameter_read_success': plc_value is not None,
                'current_value_updated': current_value_updated,
                'timestamp_updated': timestamp_updated,
                'plc_value': plc_value,
                'real_plc_pattern_working': current_value_updated or timestamp_updated,
                'finding_validated': current_value_updated or timestamp_updated
            }

        except Exception as e:
            logger.error(f"Error validating real PLC patterns: {e}")
            return {'error': str(e), 'finding_validated': False}

    async def _validate_enterprise_compliance(self):
        """Validate enterprise compliance claims."""
        try:
            from src.data_collection.transactional_adapter import transactional_parameter_logger_adapter

            # Test health status
            health_status = await transactional_parameter_logger_adapter.get_health_status()

            # Test atomic operation
            atomic_test = await transactional_parameter_logger_adapter.test_atomic_operation()

            # Check for enterprise features
            enterprise_features = {
                'transactional_health': health_status.get('overall_status') == 'healthy',
                'atomic_operations': atomic_test.get('test_successful', False),
                'transaction_tracking': 'transaction_id' in atomic_test,
                'error_handling': 'error_message' in atomic_test,
                'comprehensive_metrics': 'performance_metrics' in health_status
            }

            compliance_score = sum(enterprise_features.values()) / len(enterprise_features)

            return {
                'enterprise_features': enterprise_features,
                'health_status': health_status,
                'atomic_test_result': atomic_test,
                'compliance_score': compliance_score,
                'a_plus_enterprise_ready': compliance_score >= 0.8,
                'finding_validated': compliance_score >= 0.8
            }

        except Exception as e:
            logger.error(f"Error validating enterprise compliance: {e}")
            return {'error': str(e), 'finding_validated': False}

    async def execute_comprehensive_validation(self):
        """Execute complete validation suite."""
        logger.info("🚀 STARTING COMPREHENSIVE PARAMETER SYNCHRONIZATION VALIDATION 🚀")

        start_time = datetime.now(timezone.utc)

        validation_results = {
            'validation_timestamp': start_time.isoformat(),
            'coordination_based_validation': True
        }

        try:
            # 1. Validate agent findings
            logger.info("📋 Phase 1: Validating Agent Coordination Findings")
            validation_results['agent_findings_validation'] = await self.validate_agent_findings()

            # 2. Run comprehensive test suite
            logger.info("🧪 Phase 2: Running Comprehensive Test Suite")
            validation_results['comprehensive_tests'] = await self.comprehensive_tester.run_comprehensive_test_suite()

            # 3. Run edge case tests
            logger.info("🔍 Phase 3: Running Edge Case Test Suite")
            validation_results['edge_case_tests'] = await self.edge_case_tester.run_edge_case_test_suite()

            # 4. Calculate overall validation results
            validation_results['overall_validation'] = self._calculate_overall_validation(validation_results)

            end_time = datetime.now(timezone.utc)
            validation_results['execution_duration'] = str(end_time - start_time)

            return validation_results

        except Exception as e:
            logger.error(f"Comprehensive validation failed: {e}")
            validation_results['fatal_error'] = str(e)
            return validation_results

    def _calculate_overall_validation(self, results):
        """Calculate overall validation results."""
        summary = {
            'agent_findings_validated': 0,
            'total_agent_findings': 0,
            'comprehensive_test_pass_rate': 0,
            'edge_case_pass_rate': 0,
            'critical_issues': [],
            'validation_recommendations': []
        }

        # Analyze agent findings validation
        if 'agent_findings_validation' in results:
            findings = results['agent_findings_validation']
            for finding_key, finding_result in findings.items():
                summary['total_agent_findings'] += 1
                if finding_result.get('finding_validated', False):
                    summary['agent_findings_validated'] += 1

        # Get test pass rates
        if 'comprehensive_tests' in results and 'test_summary' in results['comprehensive_tests']:
            summary['comprehensive_test_pass_rate'] = results['comprehensive_tests']['test_summary'].get('pass_rate', 0)

        if 'edge_case_tests' in results and 'edge_case_summary' in results['edge_case_tests']:
            summary['edge_case_pass_rate'] = results['edge_case_tests']['edge_case_summary'].get('edge_case_pass_rate', 0)

        # Identify critical issues
        if summary['comprehensive_test_pass_rate'] < 0.8:
            summary['critical_issues'].append("Comprehensive test pass rate below 80%")

        if summary['edge_case_pass_rate'] < 0.7:
            summary['critical_issues'].append("Edge case test pass rate below 70%")

        if summary['agent_findings_validated'] < summary['total_agent_findings']:
            summary['critical_issues'].append("Not all agent findings validated")

        # Generate recommendations
        if summary['agent_findings_validated'] == summary['total_agent_findings']:
            summary['validation_recommendations'].append("Agent coordination findings confirmed - implementation on track")

        if summary['comprehensive_test_pass_rate'] > 0.8 and summary['edge_case_pass_rate'] > 0.7:
            summary['validation_recommendations'].append("High test pass rates indicate robust implementation")

        # Calculate overall score
        agent_score = summary['agent_findings_validated'] / max(summary['total_agent_findings'], 1)
        test_score = (summary['comprehensive_test_pass_rate'] + summary['edge_case_pass_rate']) / 2

        summary['overall_validation_score'] = (agent_score + test_score) / 2
        summary['validation_status'] = 'EXCELLENT' if summary['overall_validation_score'] > 0.85 else \
                                      'GOOD' if summary['overall_validation_score'] > 0.7 else \
                                      'NEEDS_IMPROVEMENT'

        return summary

    def print_validation_report(self, results):
        """Print comprehensive validation report."""
        print("\n" + "="*100)
        print("🎯 PARAMETER SYNCHRONIZATION VALIDATION REPORT 🎯")
        print("="*100)

        if 'overall_validation' in results:
            overall = results['overall_validation']
            print(f"🏆 OVERALL VALIDATION STATUS: {overall['validation_status']}")
            print(f"📊 Overall Score: {overall['overall_validation_score']:.1%}")
            print(f"🤝 Agent Findings Validated: {overall['agent_findings_validated']}/{overall['total_agent_findings']}")
            print(f"🧪 Comprehensive Test Pass Rate: {overall['comprehensive_test_pass_rate']:.1%}")
            print(f"🔍 Edge Case Test Pass Rate: {overall['edge_case_pass_rate']:.1%}")

            if overall['critical_issues']:
                print(f"\n🚨 CRITICAL ISSUES:")
                for issue in overall['critical_issues']:
                    print(f"   • {issue}")

            if overall['validation_recommendations']:
                print(f"\n💡 VALIDATION RECOMMENDATIONS:")
                for rec in overall['validation_recommendations']:
                    print(f"   • {rec}")

        # Agent findings validation details
        if 'agent_findings_validation' in results:
            print(f"\n📋 AGENT FINDINGS VALIDATION:")
            for finding, result in results['agent_findings_validation'].items():
                status = "✅ VALIDATED" if result.get('finding_validated') else "❌ NOT VALIDATED"
                print(f"   {finding}: {status}")
                if 'error' in result:
                    print(f"      Error: {result['error']}")

        print(f"\n⏱️  Execution Duration: {results.get('execution_duration', 'Unknown')}")
        print("="*100)


async def main():
    """Main validation execution."""
    validator = ParameterSyncValidationExecutor()

    try:
        results = await validator.execute_comprehensive_validation()

        # Print summary report
        validator.print_validation_report(results)

        # Save detailed results
        import json
        results_file = f"parameter_sync_validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n📄 Detailed results saved to: {results_file}")

        return results

    except Exception as e:
        logger.error(f"Validation execution failed: {e}")
        return {'error': str(e)}


if __name__ == "__main__":
    asyncio.run(main())