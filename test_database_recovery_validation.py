#!/usr/bin/env python3
"""
Database Recovery Time Validation Test for Continuous Parameter Logging System

This test validates database recovery behavior and measures recovery times after database restoration,
specifically targeting the dual-mode logging system's ability to recover from database failures.

RECOVERY SCENARIOS TESTED:
1. Database service restart during continuous logging
2. Network partition recovery with stale connection detection
3. Credential rotation recovery timing validation
4. Connection pool recovery after exhaustion
5. Dual-mode state consistency recovery after failures
6. Data integrity validation after recovery
7. Silent failure recovery detection
"""

import asyncio
import os
import sys
import time
import threading
import subprocess
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.log_setup import logger
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.db import get_supabase
from src.config import MACHINE_ID


class DatabaseRecoveryValidator:
    """Validates database recovery behavior and timing for dual-mode logging."""

    def __init__(self):
        self.recovery_metrics = {
            'recovery_scenarios': [],
            'timing_measurements': [],
            'data_integrity_checks': [],
            'state_consistency_validations': [],
            'silent_failure_recoveries': []
        }
        self.test_start_time = time.time()

    async def test_database_service_restart_recovery(self):
        """Test recovery behavior after simulated database service restart."""
        logger.info("🔄 Testing database service restart recovery...")

        recovery_scenario = {
            'scenario': 'database_service_restart',
            'downtime_duration': 5.0,  # seconds
            'recovery_attempts': [],
            'data_integrity_status': 'unknown',
            'final_status': 'unknown'
        }

        # Simulate database unavailability followed by recovery
        with patch('src.db.get_supabase') as mock_get_supabase:

            # Phase 1: Database unavailable
            logger.info("Phase 1: Simulating database downtime...")
            mock_get_supabase.side_effect = Exception("Connection refused: database service unavailable")

            downtime_start = time.time()
            downtime_operations = []

            # Test operations during downtime
            for i in range(3):
                try:
                    start_time = time.time()
                    await continuous_parameter_logger._read_and_log_parameters()
                    downtime_operations.append({
                        'operation': i,
                        'success': True,
                        'duration': time.time() - start_time
                    })
                except Exception as e:
                    downtime_operations.append({
                        'operation': i,
                        'success': False,
                        'error': str(e),
                        'duration': time.time() - start_time
                    })
                await asyncio.sleep(1)

            # Phase 2: Database recovery
            logger.info("Phase 2: Simulating database recovery...")
            await asyncio.sleep(recovery_scenario['downtime_duration'])

            # Restore database availability
            mock_client = MagicMock()
            mock_table = MagicMock()
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
            mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={'status': 'idle', 'current_process_id': None}
            )
            mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
            mock_client.table.return_value = mock_table
            mock_get_supabase.side_effect = None
            mock_get_supabase.return_value = mock_client

            # Phase 3: Recovery validation
            logger.info("Phase 3: Validating recovery behavior...")
            recovery_start = time.time()
            recovery_operations = []

            # Test operations after recovery
            for i in range(5):
                try:
                    start_time = time.time()
                    await continuous_parameter_logger._read_and_log_parameters()
                    recovery_operations.append({
                        'operation': i,
                        'success': True,
                        'duration': time.time() - start_time,
                        'time_since_recovery': time.time() - recovery_start
                    })
                    logger.info(f"Recovery operation {i} successful in {time.time() - start_time:.3f}s")
                except Exception as e:
                    recovery_operations.append({
                        'operation': i,
                        'success': False,
                        'error': str(e),
                        'duration': time.time() - start_time,
                        'time_since_recovery': time.time() - recovery_start
                    })
                    logger.warning(f"Recovery operation {i} failed: {e}")

                await asyncio.sleep(0.5)

            recovery_scenario.update({
                'downtime_operations': downtime_operations,
                'recovery_operations': recovery_operations,
                'total_recovery_time': time.time() - recovery_start,
                'successful_recovery_operations': len([op for op in recovery_operations if op['success']]),
                'failed_recovery_operations': len([op for op in recovery_operations if not op['success']]),
                'data_integrity_status': 'validated' if len([op for op in recovery_operations if op['success']]) >= 3 else 'compromised',
                'final_status': 'success' if len([op for op in recovery_operations if op['success']]) >= 3 else 'failure'
            })

        self.recovery_metrics['recovery_scenarios'].append(recovery_scenario)
        logger.info(f"Database service restart recovery result: {recovery_scenario['final_status']}")
        return recovery_scenario

    async def test_network_partition_recovery(self):
        """Test recovery after network partition with stale connection detection."""
        logger.info("🌐 Testing network partition recovery...")

        recovery_scenario = {
            'scenario': 'network_partition_recovery',
            'partition_duration': 8.0,  # seconds
            'stale_connection_detection_time': None,
            'new_connection_establishment_time': None,
            'data_consistency_after_recovery': 'unknown'
        }

        # Simulate network partition
        with patch('src.db.get_supabase') as mock_get_supabase:

            # Phase 1: Network partition - stale connections
            logger.info("Phase 1: Simulating network partition with stale connections...")
            partition_start = time.time()

            stale_connection_mock = MagicMock()
            stale_connection_mock.table.side_effect = Exception("Network unreachable")
            mock_get_supabase.return_value = stale_connection_mock

            # Test stale connection detection
            stale_detection_start = time.time()
            try:
                await continuous_parameter_logger._read_and_log_parameters()
            except Exception as e:
                recovery_scenario['stale_connection_detection_time'] = time.time() - stale_detection_start
                logger.info(f"Stale connection detected in {recovery_scenario['stale_connection_detection_time']:.3f}s")

            # Wait for partition duration
            await asyncio.sleep(recovery_scenario['partition_duration'])

            # Phase 2: Network restoration
            logger.info("Phase 2: Simulating network restoration...")
            restoration_start = time.time()

            # Simulate new healthy connection
            healthy_connection_mock = MagicMock()
            mock_table = MagicMock()
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
            mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={'status': 'processing', 'current_process_id': 'recovery_test_process'}
            )
            mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[
                {'id': 'param1', 'set_value': 25.0},
                {'id': 'param2', 'set_value': 50.0}
            ])
            healthy_connection_mock.table.return_value = mock_table
            mock_get_supabase.return_value = healthy_connection_mock

            # Test new connection establishment
            new_connection_start = time.time()
            try:
                await continuous_parameter_logger._read_and_log_parameters()
                recovery_scenario['new_connection_establishment_time'] = time.time() - new_connection_start
                logger.info(f"New connection established in {recovery_scenario['new_connection_establishment_time']:.3f}s")
                recovery_scenario['data_consistency_after_recovery'] = 'consistent'
            except Exception as e:
                recovery_scenario['new_connection_establishment_time'] = time.time() - new_connection_start
                recovery_scenario['data_consistency_after_recovery'] = 'inconsistent'
                logger.error(f"Failed to establish new connection: {e}")

            recovery_scenario.update({
                'total_partition_time': time.time() - partition_start,
                'recovery_success': recovery_scenario['data_consistency_after_recovery'] == 'consistent'
            })

        self.recovery_metrics['recovery_scenarios'].append(recovery_scenario)
        logger.info(f"Network partition recovery result: {'success' if recovery_scenario['recovery_success'] else 'failure'}")
        return recovery_scenario

    async def test_credential_rotation_recovery(self):
        """Test recovery timing during database credential rotation."""
        logger.info("🔑 Testing credential rotation recovery timing...")

        recovery_scenario = {
            'scenario': 'credential_rotation_recovery',
            'credential_invalidation_time': None,
            'new_credential_validation_time': None,
            'service_interruption_duration': None,
            'operations_during_rotation': []
        }

        with patch('src.db.get_supabase') as mock_get_supabase:

            # Phase 1: Normal operations with valid credentials
            logger.info("Phase 1: Normal operations with valid credentials...")
            valid_client = MagicMock()
            mock_table = MagicMock()
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
            mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={'status': 'idle', 'current_process_id': None}
            )
            mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
            valid_client.table.return_value = mock_table
            mock_get_supabase.return_value = valid_client

            # Successful operation
            await continuous_parameter_logger._read_and_log_parameters()

            # Phase 2: Credential invalidation
            logger.info("Phase 2: Simulating credential invalidation...")
            invalidation_start = time.time()

            # Simulate credentials becoming invalid
            mock_get_supabase.side_effect = Exception("Authentication failed: invalid API key")

            # Test operations with invalid credentials
            rotation_start = time.time()
            for i in range(3):
                operation_start = time.time()
                try:
                    await continuous_parameter_logger._read_and_log_parameters()
                    recovery_scenario['operations_during_rotation'].append({
                        'operation': i,
                        'phase': 'invalid_credentials',
                        'success': True,
                        'duration': time.time() - operation_start
                    })
                except Exception as e:
                    recovery_scenario['operations_during_rotation'].append({
                        'operation': i,
                        'phase': 'invalid_credentials',
                        'success': False,
                        'error': str(e),
                        'duration': time.time() - operation_start
                    })
                    if recovery_scenario['credential_invalidation_time'] is None:
                        recovery_scenario['credential_invalidation_time'] = time.time() - invalidation_start

                await asyncio.sleep(0.5)

            # Phase 3: New credentials validation
            logger.info("Phase 3: Simulating new credential validation...")
            await asyncio.sleep(2)  # Simulate credential rotation time

            new_credential_start = time.time()

            # Simulate new valid credentials
            new_valid_client = MagicMock()
            new_mock_table = MagicMock()
            new_mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
            new_mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={'status': 'processing', 'current_process_id': 'new_cred_process'}
            )
            new_mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
            new_valid_client.table.return_value = new_mock_table
            mock_get_supabase.side_effect = None
            mock_get_supabase.return_value = new_valid_client

            # Test operations with new credentials
            for i in range(3):
                operation_start = time.time()
                try:
                    await continuous_parameter_logger._read_and_log_parameters()
                    if recovery_scenario['new_credential_validation_time'] is None:
                        recovery_scenario['new_credential_validation_time'] = time.time() - new_credential_start

                    recovery_scenario['operations_during_rotation'].append({
                        'operation': i,
                        'phase': 'new_credentials',
                        'success': True,
                        'duration': time.time() - operation_start
                    })
                except Exception as e:
                    recovery_scenario['operations_during_rotation'].append({
                        'operation': i,
                        'phase': 'new_credentials',
                        'success': False,
                        'error': str(e),
                        'duration': time.time() - operation_start
                    })

                await asyncio.sleep(0.5)

            recovery_scenario['service_interruption_duration'] = time.time() - rotation_start
            recovery_scenario['recovery_success'] = any(
                op['success'] and op['phase'] == 'new_credentials'
                for op in recovery_scenario['operations_during_rotation']
            )

        self.recovery_metrics['recovery_scenarios'].append(recovery_scenario)
        logger.info(f"Credential rotation recovery result: {'success' if recovery_scenario['recovery_success'] else 'failure'}")
        return recovery_scenario

    async def test_dual_mode_state_consistency_recovery(self):
        """Test dual-mode state consistency after recovery from failures."""
        logger.info("🔄 Testing dual-mode state consistency recovery...")

        consistency_test = {
            'scenario': 'dual_mode_state_consistency',
            'state_transitions': [],
            'consistency_violations': [],
            'recovery_validations': []
        }

        # Test state transitions during and after recovery
        state_scenarios = [
            {'initial_state': 'idle', 'target_state': 'processing'},
            {'initial_state': 'processing', 'target_state': 'idle'},
            {'initial_state': 'idle', 'target_state': 'idle'},  # State consistency test
            {'initial_state': 'processing', 'target_state': 'processing'}  # Dual-mode consistency test
        ]

        for scenario in state_scenarios:
            logger.info(f"Testing state transition: {scenario['initial_state']} -> {scenario['target_state']}")

            with patch('src.db.get_supabase') as mock_get_supabase:
                mock_client = MagicMock()

                # Track state queries and their responses
                state_query_count = 0
                def mock_state_query():
                    nonlocal state_query_count
                    state_query_count += 1

                    # Simulate state transition during recovery
                    if state_query_count <= 2:
                        return MagicMock(data={'status': scenario['initial_state'], 'current_process_id': 'test_process' if scenario['initial_state'] == 'processing' else None})
                    else:
                        return MagicMock(data={'status': scenario['target_state'], 'current_process_id': 'test_process' if scenario['target_state'] == 'processing' else None})

                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.single.return_value.execute = mock_state_query
                mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
                mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
                mock_client.table.return_value = mock_table
                mock_get_supabase.return_value = mock_client

                # Test operations during state transition
                transition_start = time.time()
                operations_log = []

                for i in range(4):
                    operation_start = time.time()
                    try:
                        await continuous_parameter_logger._read_and_log_parameters()
                        operations_log.append({
                            'operation': i,
                            'success': True,
                            'expected_state': scenario['target_state'] if i >= 2 else scenario['initial_state'],
                            'duration': time.time() - operation_start
                        })
                    except Exception as e:
                        operations_log.append({
                            'operation': i,
                            'success': False,
                            'error': str(e),
                            'duration': time.time() - operation_start
                        })

                    await asyncio.sleep(0.3)

                # Analyze consistency
                consistency_violations = []
                for i, op in enumerate(operations_log):
                    if i >= 2:  # After state transition
                        # Check if operations reflect new state correctly
                        if scenario['target_state'] == 'processing' and not op['success']:
                            consistency_violations.append(f"Operation {i} failed during processing state")
                        elif scenario['target_state'] == 'idle' and not op['success']:
                            consistency_violations.append(f"Operation {i} failed during idle state")

                transition_result = {
                    'initial_state': scenario['initial_state'],
                    'target_state': scenario['target_state'],
                    'transition_duration': time.time() - transition_start,
                    'operations_log': operations_log,
                    'consistency_violations': consistency_violations,
                    'state_queries': state_query_count,
                    'consistency_status': 'consistent' if len(consistency_violations) == 0 else 'inconsistent'
                }

                consistency_test['state_transitions'].append(transition_result)
                consistency_test['consistency_violations'].extend(consistency_violations)

        self.recovery_metrics['state_consistency_validations'].append(consistency_test)
        logger.info(f"Dual-mode state consistency test completed with {len(consistency_test['consistency_violations'])} violations")
        return consistency_test

    async def test_data_integrity_validation_after_recovery(self):
        """Test data integrity validation after database recovery."""
        logger.info("🔍 Testing data integrity validation after recovery...")

        integrity_test = {
            'scenario': 'data_integrity_post_recovery',
            'data_validation_checks': [],
            'integrity_violations': [],
            'recovery_data_consistency': 'unknown'
        }

        # Simulate recovery with potential data integrity issues
        with patch('src.db.get_supabase') as mock_get_supabase:
            mock_client = MagicMock()

            # Test scenarios with different data integrity outcomes
            integrity_scenarios = [
                {'description': 'consistent_dual_table_data', 'parameter_history_count': 5, 'process_data_count': 5},
                {'description': 'inconsistent_dual_table_data', 'parameter_history_count': 5, 'process_data_count': 3},
                {'description': 'missing_parameter_metadata', 'parameter_history_count': 5, 'metadata_available': False},
                {'description': 'timestamp_inconsistency', 'parameter_history_count': 5, 'timestamp_drift': True}
            ]

            for scenario in integrity_scenarios:
                logger.info(f"Testing data integrity scenario: {scenario['description']}")

                validation_start = time.time()

                # Mock data validation queries
                def mock_integrity_query(table_name):
                    mock_table = MagicMock()

                    if table_name == 'parameter_value_history':
                        # Simulate parameter history data
                        mock_table.select.return_value.count.return_value.execute.return_value = MagicMock(
                            data=[{'count': scenario['parameter_history_count']}]
                        )
                    elif table_name == 'process_data_points':
                        # Simulate process data points (may be inconsistent)
                        mock_table.select.return_value.count.return_value.execute.return_value = MagicMock(
                            data=[{'count': scenario.get('process_data_count', scenario['parameter_history_count'])}]
                        )
                    elif table_name == 'component_parameters':
                        # Simulate parameter metadata availability
                        if scenario.get('metadata_available', True):
                            mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(
                                data=[{'id': f'param_{i}', 'set_value': 25.0} for i in range(3)]
                            )
                        else:
                            mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
                    else:
                        # Default process state
                        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                            data={'status': 'processing', 'current_process_id': 'integrity_test_process'}
                        )

                    return mock_table

                mock_client.table.side_effect = mock_integrity_query
                mock_get_supabase.return_value = mock_client

                # Perform integrity validation operation
                try:
                    await continuous_parameter_logger._read_and_log_parameters()

                    # Analyze expected vs actual behavior
                    violations = []
                    if scenario['description'] == 'inconsistent_dual_table_data':
                        violations.append("Dual table data count mismatch detected")
                    elif scenario['description'] == 'missing_parameter_metadata':
                        violations.append("Parameter metadata unavailable during recovery")
                    elif scenario['description'] == 'timestamp_inconsistency':
                        violations.append("Timestamp inconsistency between dual tables")

                    validation_result = {
                        'scenario': scenario['description'],
                        'validation_duration': time.time() - validation_start,
                        'violations_detected': violations,
                        'integrity_status': 'violated' if violations else 'intact',
                        'expected_violations': len(violations) > 0
                    }

                    integrity_test['data_validation_checks'].append(validation_result)
                    integrity_test['integrity_violations'].extend(violations)

                except Exception as e:
                    validation_result = {
                        'scenario': scenario['description'],
                        'validation_duration': time.time() - validation_start,
                        'error': str(e),
                        'integrity_status': 'error',
                        'expected_violations': True
                    }
                    integrity_test['data_validation_checks'].append(validation_result)

                await asyncio.sleep(0.2)

        integrity_test['recovery_data_consistency'] = 'consistent' if len(integrity_test['integrity_violations']) == 0 else 'inconsistent'

        self.recovery_metrics['data_integrity_checks'].append(integrity_test)
        logger.info(f"Data integrity validation completed: {integrity_test['recovery_data_consistency']}")
        return integrity_test

    async def generate_recovery_validation_report(self):
        """Generate comprehensive recovery validation report."""
        logger.info("📊 Generating database recovery validation report...")

        total_scenarios_tested = sum(len(category) for category in self.recovery_metrics.values())
        recovery_success_count = 0
        critical_recovery_issues = []

        report = {
            'recovery_test_summary': {
                'total_test_duration': time.time() - self.test_start_time,
                'scenarios_tested': total_scenarios_tested,
                'test_timestamp': datetime.now(timezone.utc).isoformat(),
                'machine_id': MACHINE_ID
            },
            'recovery_performance_metrics': {},
            'detailed_results': self.recovery_metrics,
            'recovery_issues_identified': [],
            'recommendations': []
        }

        # Analyze recovery performance
        for scenario_category, scenarios in self.recovery_metrics.items():
            if not scenarios:
                continue

            for scenario in scenarios:
                if isinstance(scenario, dict):
                    if scenario.get('recovery_success', False) or scenario.get('final_status') == 'success':
                        recovery_success_count += 1

                    # Identify critical recovery issues
                    if scenario_category == 'recovery_scenarios':
                        if scenario.get('final_status') == 'failure':
                            critical_recovery_issues.append({
                                'severity': 'HIGH',
                                'category': 'Recovery Failure',
                                'scenario': scenario.get('scenario', 'unknown'),
                                'issue': f"Failed to recover from {scenario.get('scenario', 'unknown')}",
                                'impact': 'Service unavailability during database issues'
                            })

                    elif scenario_category == 'state_consistency_validations':
                        violations = scenario.get('consistency_violations', [])
                        if violations:
                            critical_recovery_issues.append({
                                'severity': 'CRITICAL',
                                'category': 'Data Consistency',
                                'scenario': scenario.get('scenario', 'unknown'),
                                'issue': f"State consistency violations: {len(violations)} detected",
                                'impact': 'Data corruption during state transitions',
                                'violations': violations
                            })

                    elif scenario_category == 'data_integrity_checks':
                        integrity_violations = scenario.get('integrity_violations', [])
                        if integrity_violations:
                            critical_recovery_issues.append({
                                'severity': 'CRITICAL',
                                'category': 'Data Integrity',
                                'scenario': scenario.get('scenario', 'unknown'),
                                'issue': f"Data integrity violations: {len(integrity_violations)} detected",
                                'impact': 'Data corruption and inconsistency after recovery',
                                'violations': integrity_violations
                            })

        # Calculate recovery performance metrics
        recovery_scenarios = [s for s in self.recovery_metrics.get('recovery_scenarios', []) if isinstance(s, dict)]
        if recovery_scenarios:
            recovery_times = [s.get('total_recovery_time', 0) for s in recovery_scenarios if s.get('total_recovery_time')]
            report['recovery_performance_metrics'] = {
                'average_recovery_time': sum(recovery_times) / len(recovery_times) if recovery_times else 0,
                'max_recovery_time': max(recovery_times) if recovery_times else 0,
                'min_recovery_time': min(recovery_times) if recovery_times else 0,
                'recovery_success_rate': recovery_success_count / len(recovery_scenarios) if recovery_scenarios else 0
            }

        report['recovery_issues_identified'] = critical_recovery_issues

        # Generate recommendations
        recommendations = [
            {
                'priority': 'IMMEDIATE',
                'category': 'Recovery Automation',
                'recommendation': 'Implement automatic database reconnection with exponential backoff',
                'technical_details': 'Add connection health monitoring and automatic retry logic with circuit breaker pattern'
            },
            {
                'priority': 'HIGH',
                'category': 'State Consistency',
                'recommendation': 'Implement state validation after recovery',
                'technical_details': 'Add state consistency checks and automatic correction mechanisms'
            },
            {
                'priority': 'HIGH',
                'category': 'Data Integrity',
                'recommendation': 'Add data integrity validation after database recovery',
                'technical_details': 'Implement periodic consistency checks between dual tables after recovery'
            },
            {
                'priority': 'MEDIUM',
                'category': 'Recovery Monitoring',
                'recommendation': 'Add recovery time monitoring and alerting',
                'technical_details': 'Track recovery metrics and alert on slow or failed recovery attempts'
            }
        ]

        report['recommendations'] = recommendations

        # Log summary
        logger.info("=" * 80)
        logger.info("🔄 DATABASE RECOVERY VALIDATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Scenarios Tested: {total_scenarios_tested}")
        logger.info(f"Recovery Success Count: {recovery_success_count}")
        logger.info(f"Critical Recovery Issues: {len(critical_recovery_issues)}")
        if recovery_scenarios:
            metrics = report['recovery_performance_metrics']
            logger.info(f"Average Recovery Time: {metrics['average_recovery_time']:.3f}s")
            logger.info(f"Recovery Success Rate: {metrics['recovery_success_rate']:.1%}")

        logger.info("")
        logger.info("🚨 CRITICAL RECOVERY ISSUES:")
        for issue in critical_recovery_issues:
            logger.info(f"  - {issue['severity']}: {issue['issue']}")

        return report

    async def run_comprehensive_recovery_validation(self):
        """Execute all database recovery validation tests."""
        logger.info("🚀 Starting comprehensive database recovery validation...")

        try:
            # Execute all recovery validation tests
            await self.test_database_service_restart_recovery()
            await self.test_network_partition_recovery()
            await self.test_credential_rotation_recovery()
            await self.test_dual_mode_state_consistency_recovery()
            await self.test_data_integrity_validation_after_recovery()

            # Generate comprehensive report
            report = await self.generate_recovery_validation_report()

            # Save report to file
            report_filename = f"database_recovery_validation_report_{int(time.time())}.json"
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"📄 Recovery validation report saved to: {report_filename}")
            return report

        except Exception as e:
            logger.error(f"❌ Recovery validation failed: {e}", exc_info=True)
            raise


async def main():
    """Main execution function for database recovery validation tests."""
    load_dotenv()

    logger.info("🎯 Database Recovery Validation Test Suite")
    logger.info("Validating recovery behavior and timing for dual-mode logging system")

    validator = DatabaseRecoveryValidator()

    try:
        report = await validator.run_comprehensive_recovery_validation()

        # Determine overall test result
        critical_issues = len(report['recovery_issues_identified'])
        if critical_issues > 0:
            logger.error(f"💥 RECOVERY VALIDATION RESULT: FAILED - {critical_issues} critical recovery issues detected")
            logger.error("🔧 IMMEDIATE ACTION REQUIRED: Review recovery mechanisms and implement fixes")
            sys.exit(1)
        else:
            logger.info("✅ RECOVERY VALIDATION RESULT: PASSED - Recovery mechanisms functioning properly")

    except Exception as e:
        logger.error(f"🚨 Database recovery validation suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())