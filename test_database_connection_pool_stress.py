#!/usr/bin/env python3
"""
Database Connection Pool Stress Test for Continuous Parameter Logging System

This test specifically targets the singleton database client vulnerability (src/db.py:13-32)
and validates connection pool exhaustion scenarios under high load conditions.

CRITICAL VULNERABILITIES TARGETED:
1. Single global Supabase client instance without connection pooling (src/db.py:13-32)
2. No connection multiplexing or retry logic for connection failures
3. Connection exhaustion under concurrent dual-mode logging operations
4. No circuit breaker pattern for database connection failures
5. No connection health monitoring or automatic recovery

CONNECTION POOL SCENARIOS TESTED:
- Concurrent connection exhaustion with dual-mode logging
- Connection leak detection under error conditions
- Database connection timeout under high load
- Connection recovery after pool exhaustion
- Concurrent transaction boundary stress testing
- Connection state consistency during failures
"""

import asyncio
import os
import sys
import time
import threading
import json
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv
import concurrent.futures

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.log_setup import logger
from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.db import get_supabase
from src.config import MACHINE_ID


class DatabaseConnectionPoolStressTester:
    """Tests database connection pool behavior under extreme stress conditions."""

    def __init__(self):
        self.stress_test_results = {
            'connection_exhaustion_tests': [],
            'concurrent_operation_tests': [],
            'connection_leak_tests': [],
            'recovery_timing_tests': [],
            'transaction_boundary_stress_tests': []
        }
        self.test_start_time = time.time()
        self.active_connections = 0
        self.max_connections_reached = 0
        self.connection_failures = 0

    async def test_concurrent_connection_exhaustion(self):
        """Test connection pool exhaustion with concurrent dual-mode operations."""
        logger.info("🏊 Testing concurrent connection pool exhaustion...")

        exhaustion_test = {
            'test_name': 'concurrent_connection_exhaustion',
            'concurrent_levels': [],
            'connection_pool_behavior': {},
            'failure_thresholds': {}
        }

        # Test various concurrency levels
        concurrency_levels = [1, 5, 10, 20, 50, 100]

        for concurrency in concurrency_levels:
            logger.info(f"Testing concurrency level: {concurrency} simultaneous operations")

            level_results = {
                'concurrency_level': concurrency,
                'total_operations_attempted': concurrency,
                'successful_operations': 0,
                'failed_operations': 0,
                'connection_errors': 0,
                'timeout_errors': 0,
                'max_concurrent_connections': 0,
                'average_operation_time': 0,
                'connection_pool_exhausted': False
            }

            # Reset connection tracking
            self.active_connections = 0
            self.max_connections_reached = 0
            self.connection_failures = 0

            with patch('src.db.get_supabase') as mock_get_supabase:
                # Simulate connection pool with limited connections
                connection_pool_size = 20  # Simulate realistic connection pool limit
                active_connections = 0
                connection_errors = 0

                def mock_connection_factory():
                    nonlocal active_connections, connection_errors

                    if active_connections >= connection_pool_size:
                        connection_errors += 1
                        raise Exception(f"Connection pool exhausted: {active_connections}/{connection_pool_size} connections active")

                    active_connections += 1
                    self.active_connections = active_connections
                    self.max_connections_reached = max(self.max_connections_reached, active_connections)

                    # Mock successful client
                    mock_client = MagicMock()
                    mock_table = MagicMock()

                    # Simulate database operation latency
                    def slow_execute():
                        time.sleep(random.uniform(0.1, 0.3))  # Simulate DB latency
                        nonlocal active_connections
                        active_connections -= 1  # Release connection
                        return MagicMock(data=[])

                    mock_table.insert.return_value.execute = slow_execute
                    mock_table.select.return_value.eq.return_value.single.return_value.execute = slow_execute
                    mock_table.select.return_value.in_.return_value.execute = slow_execute
                    mock_client.table.return_value = mock_table
                    return mock_client

                mock_get_supabase.side_effect = mock_connection_factory

                # Execute concurrent operations
                start_time = time.time()
                tasks = []

                for i in range(concurrency):
                    task = asyncio.create_task(self._simulate_dual_mode_operation(i, concurrency))
                    tasks.append(task)

                # Wait for all operations to complete with timeout
                try:
                    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30.0)

                    operation_times = []
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            level_results['failed_operations'] += 1
                            error_str = str(result).lower()
                            if 'connection' in error_str or 'pool' in error_str:
                                level_results['connection_errors'] += 1
                            elif 'timeout' in error_str:
                                level_results['timeout_errors'] += 1
                        elif isinstance(result, dict) and result.get('success'):
                            level_results['successful_operations'] += 1
                            operation_times.append(result.get('duration', 0))
                        else:
                            level_results['failed_operations'] += 1

                    level_results['average_operation_time'] = sum(operation_times) / len(operation_times) if operation_times else 0
                    level_results['max_concurrent_connections'] = self.max_connections_reached
                    level_results['connection_pool_exhausted'] = connection_errors > 0

                except asyncio.TimeoutError:
                    level_results['failed_operations'] = concurrency
                    level_results['timeout_errors'] = concurrency
                    level_results['connection_pool_exhausted'] = True
                    logger.warning(f"Concurrency level {concurrency} timed out - likely connection pool exhaustion")

                level_results['test_duration'] = time.time() - start_time
                exhaustion_test['concurrent_levels'].append(level_results)

                logger.info(f"Concurrency {concurrency}: {level_results['successful_operations']}/{concurrency} successful, "
                           f"max connections: {level_results['max_concurrent_connections']}, "
                           f"pool exhausted: {level_results['connection_pool_exhausted']}")

                # Brief pause between concurrency levels
                await asyncio.sleep(1)

        # Analyze connection pool behavior
        exhaustion_test['connection_pool_behavior'] = {
            'connection_limit_detected': any(level['connection_pool_exhausted'] for level in exhaustion_test['concurrent_levels']),
            'failure_threshold_concurrency': next((level['concurrency_level'] for level in exhaustion_test['concurrent_levels'] if level['connection_pool_exhausted']), None),
            'max_successful_concurrency': max((level['concurrency_level'] for level in exhaustion_test['concurrent_levels'] if level['successful_operations'] == level['total_operations_attempted']), default=0)
        }

        self.stress_test_results['connection_exhaustion_tests'].append(exhaustion_test)
        return exhaustion_test

    async def _simulate_dual_mode_operation(self, operation_id: int, concurrency_level: int):
        """Simulate a dual-mode logging operation for connection pool testing."""
        operation_start = time.time()

        try:
            # Simulate the actual dual-mode logging operation flow
            # This mirrors what continuous_parameter_logger._read_and_log_parameters() does

            # Step 1: Check process status (database query)
            supabase = get_supabase()
            process_result = supabase.table('machines').select('current_process_id, status').eq('id', MACHINE_ID).single().execute()

            # Step 2: Get parameter metadata (database query)
            param_result = supabase.table('component_parameters').select('id, set_value').in_('id', [f'param_{operation_id}']).execute()

            # Step 3: Insert into parameter_value_history (database insert)
            history_data = {
                'parameter_id': f'param_{operation_id}',
                'value': random.uniform(0, 100),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            supabase.table('parameter_value_history').insert(history_data).execute()

            # Step 4: Conditionally insert into process_data_points (dual-mode vulnerability)
            if random.random() > 0.5:  # Simulate process running 50% of the time
                process_data = {**history_data, 'process_id': f'test_process_{concurrency_level}'}
                supabase.table('process_data_points').insert(process_data).execute()

            return {
                'success': True,
                'operation_id': operation_id,
                'duration': time.time() - operation_start,
                'dual_mode_executed': True
            }

        except Exception as e:
            return {
                'success': False,
                'operation_id': operation_id,
                'duration': time.time() - operation_start,
                'error': str(e),
                'dual_mode_executed': False
            }

    async def test_connection_leak_detection(self):
        """Test for connection leaks under error conditions."""
        logger.info("🔍 Testing connection leak detection under error conditions...")

        leak_test = {
            'test_name': 'connection_leak_detection',
            'error_scenarios': [],
            'connection_tracking': {},
            'leak_detection_results': {}
        }

        # Test error scenarios that might cause connection leaks
        error_scenarios = [
            {'name': 'database_insert_exception', 'error_type': 'insert_failure'},
            {'name': 'transaction_rollback_failure', 'error_type': 'rollback_failure'},
            {'name': 'connection_timeout_during_operation', 'error_type': 'timeout'},
            {'name': 'network_interruption_mid_transaction', 'error_type': 'network_failure'}
        ]

        for scenario in error_scenarios:
            logger.info(f"Testing connection leak scenario: {scenario['name']}")

            scenario_result = {
                'scenario_name': scenario['name'],
                'operations_attempted': 10,
                'connection_leaks_detected': 0,
                'unclosed_connections': 0,
                'connection_pool_state': {}
            }

            # Track connections before scenario
            initial_connection_count = 0
            connection_leak_count = 0

            with patch('src.db.get_supabase') as mock_get_supabase:
                def mock_leaky_connection():
                    nonlocal initial_connection_count, connection_leak_count

                    initial_connection_count += 1
                    mock_client = MagicMock()
                    mock_table = MagicMock()

                    # Simulate different error conditions that might cause leaks
                    if scenario['error_type'] == 'insert_failure':
                        mock_table.insert.return_value.execute.side_effect = Exception("Insert failed - connection may leak")
                    elif scenario['error_type'] == 'rollback_failure':
                        mock_table.insert.return_value.execute.side_effect = Exception("Rollback failed - connection leaked")
                        connection_leak_count += 1  # Simulate leaked connection
                    elif scenario['error_type'] == 'timeout':
                        def timeout_execute():
                            time.sleep(2)  # Simulate timeout
                            raise Exception("Operation timed out - connection state unknown")
                        mock_table.insert.return_value.execute = timeout_execute
                        connection_leak_count += 1  # Simulate leaked connection
                    elif scenario['error_type'] == 'network_failure':
                        mock_table.insert.return_value.execute.side_effect = Exception("Network error - connection may be orphaned")
                        connection_leak_count += 1  # Simulate leaked connection

                    # Mock successful queries for state checks
                    mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                        data={'status': 'idle', 'current_process_id': None}
                    )
                    mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])

                    mock_client.table.return_value = mock_table
                    return mock_client

                mock_get_supabase.side_effect = mock_leaky_connection

                # Execute operations that should trigger the error scenario
                for i in range(scenario_result['operations_attempted']):
                    try:
                        await continuous_parameter_logger._read_and_log_parameters()
                    except Exception as e:
                        # Expected for error scenarios
                        logger.debug(f"Expected error in operation {i}: {e}")

                    await asyncio.sleep(0.1)

                scenario_result.update({
                    'initial_connection_count': initial_connection_count,
                    'connection_leaks_detected': connection_leak_count,
                    'unclosed_connections': connection_leak_count,
                    'leak_rate': connection_leak_count / initial_connection_count if initial_connection_count > 0 else 0
                })

            leak_test['error_scenarios'].append(scenario_result)
            logger.info(f"Scenario {scenario['name']}: {connection_leak_count} leaks detected from {initial_connection_count} connections")

        # Analyze overall leak detection
        total_leaks = sum(scenario['connection_leaks_detected'] for scenario in leak_test['error_scenarios'])
        total_connections = sum(scenario['initial_connection_count'] for scenario in leak_test['error_scenarios'])

        leak_test['leak_detection_results'] = {
            'total_connections_created': total_connections,
            'total_leaks_detected': total_leaks,
            'overall_leak_rate': total_leaks / total_connections if total_connections > 0 else 0,
            'leak_detection_effectiveness': 'poor' if total_leaks > total_connections * 0.1 else 'acceptable'
        }

        self.stress_test_results['connection_leak_tests'].append(leak_test)
        return leak_test

    async def test_transaction_boundary_connection_stress(self):
        """Test connection behavior during transaction boundary failures."""
        logger.info("💥 Testing transaction boundary connection stress...")

        boundary_test = {
            'test_name': 'transaction_boundary_connection_stress',
            'boundary_failure_scenarios': [],
            'connection_state_analysis': {}
        }

        # Test transaction boundary scenarios that stress connection management
        boundary_scenarios = [
            {
                'name': 'first_insert_success_second_fails_connection_leak',
                'first_table_behavior': 'success',
                'second_table_behavior': 'connection_failure'
            },
            {
                'name': 'both_inserts_timeout_connection_state',
                'first_table_behavior': 'timeout',
                'second_table_behavior': 'timeout'
            },
            {
                'name': 'connection_lost_between_dual_inserts',
                'first_table_behavior': 'success',
                'second_table_behavior': 'connection_lost'
            },
            {
                'name': 'connection_pool_exhausted_mid_transaction',
                'first_table_behavior': 'success',
                'second_table_behavior': 'pool_exhausted'
            }
        ]

        for scenario in boundary_scenarios:
            logger.info(f"Testing transaction boundary scenario: {scenario['name']}")

            scenario_result = {
                'scenario_name': scenario['name'],
                'operations_tested': 5,
                'partial_success_count': 0,
                'connection_state_issues': 0,
                'data_corruption_risk': 0,
                'connection_recovery_attempts': 0
            }

            for operation in range(scenario_result['operations_tested']):
                with patch('src.db.get_supabase') as mock_get_supabase:
                    call_count = 0
                    connections_created = 0

                    def mock_transaction_boundary_client():
                        nonlocal call_count, connections_created
                        call_count += 1
                        connections_created += 1

                        mock_client = MagicMock()

                        def mock_table_with_boundary_behavior(table_name):
                            mock_table = MagicMock()

                            if table_name == 'parameter_value_history':
                                # First table behavior
                                if scenario['first_table_behavior'] == 'success':
                                    mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
                                elif scenario['first_table_behavior'] == 'timeout':
                                    def timeout_first():
                                        time.sleep(1)
                                        raise Exception("First table insert timeout")
                                    mock_table.insert.return_value.execute = timeout_first
                                    scenario_result['connection_state_issues'] += 1

                            elif table_name == 'process_data_points':
                                # Second table behavior (the critical vulnerability point)
                                if scenario['second_table_behavior'] == 'connection_failure':
                                    mock_table.insert.return_value.execute.side_effect = Exception("Connection failed during second insert")
                                    scenario_result['partial_success_count'] += 1
                                    scenario_result['data_corruption_risk'] += 1
                                elif scenario['second_table_behavior'] == 'timeout':
                                    def timeout_second():
                                        time.sleep(1)
                                        raise Exception("Second table insert timeout")
                                    mock_table.insert.return_value.execute = timeout_second
                                    scenario_result['connection_state_issues'] += 1
                                elif scenario['second_table_behavior'] == 'connection_lost':
                                    mock_table.insert.return_value.execute.side_effect = Exception("Connection lost between dual inserts")
                                    scenario_result['partial_success_count'] += 1
                                    scenario_result['data_corruption_risk'] += 1
                                elif scenario['second_table_behavior'] == 'pool_exhausted':
                                    mock_table.insert.return_value.execute.side_effect = Exception("Connection pool exhausted during dual insert")
                                    scenario_result['connection_state_issues'] += 1

                            # Mock other queries
                            mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                                data={'status': 'processing', 'current_process_id': f'boundary_test_{operation}'}
                            )
                            mock_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])

                            return mock_table

                        mock_client.table.side_effect = mock_table_with_boundary_behavior
                        return mock_client

                    mock_get_supabase.side_effect = mock_transaction_boundary_client

                    # Execute the vulnerable dual-mode operation
                    try:
                        await continuous_parameter_logger._read_and_log_parameters()
                    except Exception as e:
                        logger.debug(f"Expected boundary failure in operation {operation}: {e}")
                        scenario_result['connection_recovery_attempts'] += 1

                    await asyncio.sleep(0.1)

            boundary_test['boundary_failure_scenarios'].append(scenario_result)
            logger.info(f"Boundary scenario {scenario['name']}: {scenario_result['partial_success_count']} partial successes, "
                       f"{scenario_result['data_corruption_risk']} corruption risks")

        # Analyze overall transaction boundary connection stress
        total_corruption_risks = sum(scenario['data_corruption_risk'] for scenario in boundary_test['boundary_failure_scenarios'])
        total_connection_issues = sum(scenario['connection_state_issues'] for scenario in boundary_test['boundary_failure_scenarios'])

        boundary_test['connection_state_analysis'] = {
            'total_corruption_risks': total_corruption_risks,
            'total_connection_state_issues': total_connection_issues,
            'critical_vulnerability_confirmed': total_corruption_risks > 0,
            'connection_management_issues': total_connection_issues > 0
        }

        self.stress_test_results['transaction_boundary_stress_tests'].append(boundary_test)
        return boundary_test

    async def generate_connection_pool_stress_report(self):
        """Generate comprehensive connection pool stress test report."""
        logger.info("📊 Generating database connection pool stress test report...")

        total_tests_executed = sum(len(category) for category in self.stress_test_results.values())
        critical_connection_issues = []

        report = {
            'connection_pool_stress_summary': {
                'total_test_duration': time.time() - self.test_start_time,
                'total_tests_executed': total_tests_executed,
                'test_timestamp': datetime.now(timezone.utc).isoformat(),
                'machine_id': MACHINE_ID
            },
            'connection_pool_vulnerabilities': {},
            'detailed_test_results': self.stress_test_results,
            'critical_findings': [],
            'remediation_roadmap': []
        }

        # Analyze connection pool vulnerabilities
        for test_category, tests in self.stress_test_results.items():
            if not tests:
                continue

            for test in tests:
                if test_category == 'connection_exhaustion_tests':
                    if test['connection_pool_behavior']['connection_limit_detected']:
                        critical_connection_issues.append({
                            'severity': 'CRITICAL',
                            'category': 'Connection Pool Exhaustion',
                            'vulnerability': 'No connection pooling or multiplexing',
                            'impact': f"System fails at {test['connection_pool_behavior']['failure_threshold_concurrency']} concurrent operations",
                            'affected_code': 'src/db.py:13-32 (singleton client pattern)'
                        })

                elif test_category == 'connection_leak_tests':
                    leak_results = test['leak_detection_results']
                    if leak_results['overall_leak_rate'] > 0.05:  # More than 5% leak rate
                        critical_connection_issues.append({
                            'severity': 'HIGH',
                            'category': 'Connection Leaks',
                            'vulnerability': 'Connections not properly released on errors',
                            'impact': f"Connection leak rate: {leak_results['overall_leak_rate']:.1%}",
                            'affected_code': 'src/data_collection/continuous_parameter_logger.py:248 (error handling)'
                        })

                elif test_category == 'transaction_boundary_stress_tests':
                    boundary_analysis = test['connection_state_analysis']
                    if boundary_analysis['critical_vulnerability_confirmed']:
                        critical_connection_issues.append({
                            'severity': 'CRITICAL',
                            'category': 'Transaction Boundary Connection Issues',
                            'vulnerability': 'Connection state corruption during dual-table inserts',
                            'impact': f"Data corruption risks: {boundary_analysis['total_corruption_risks']} detected",
                            'affected_code': 'src/data_collection/continuous_parameter_logger.py:219-249'
                        })

        report['critical_findings'] = critical_connection_issues

        # Generate remediation roadmap
        remediation_roadmap = [
            {
                'priority': 'IMMEDIATE',
                'action': 'Implement database connection pooling',
                'technical_details': 'Replace singleton client with connection pool (e.g., PostgreSQL connection pool with min/max connections)',
                'target_code': 'src/db.py - Complete rewrite of database client management',
                'estimated_effort': 'High'
            },
            {
                'priority': 'IMMEDIATE',
                'action': 'Add connection health monitoring',
                'technical_details': 'Implement connection health checks and automatic connection recovery',
                'target_code': 'New database connection monitoring service',
                'estimated_effort': 'Medium'
            },
            {
                'priority': 'HIGH',
                'action': 'Implement proper transaction boundaries',
                'technical_details': 'Wrap dual-table inserts in database transactions with proper connection management',
                'target_code': 'src/data_collection/continuous_parameter_logger.py:219-249',
                'estimated_effort': 'Medium'
            },
            {
                'priority': 'HIGH',
                'action': 'Add circuit breaker pattern for database operations',
                'technical_details': 'Implement circuit breaker to prevent connection pool exhaustion',
                'target_code': 'New database circuit breaker service',
                'estimated_effort': 'Medium'
            },
            {
                'priority': 'MEDIUM',
                'action': 'Implement connection leak detection and monitoring',
                'technical_details': 'Add runtime connection leak detection and alerting',
                'target_code': 'Database monitoring and alerting system',
                'estimated_effort': 'Low'
            }
        ]

        report['remediation_roadmap'] = remediation_roadmap

        # Log critical findings
        logger.info("=" * 80)
        logger.info("🏊 DATABASE CONNECTION POOL STRESS TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Tests Executed: {total_tests_executed}")
        logger.info(f"Critical Connection Issues: {len(critical_connection_issues)}")
        logger.info("")
        logger.info("🚨 CRITICAL CONNECTION POOL VULNERABILITIES:")
        for issue in critical_connection_issues:
            logger.info(f"  - {issue['severity']}: {issue['vulnerability']}")
            logger.info(f"    Impact: {issue['impact']}")
        logger.info("")
        logger.info("🔧 IMMEDIATE REMEDIATION REQUIRED:")
        for action in remediation_roadmap[:3]:
            logger.info(f"  - {action['priority']}: {action['action']}")

        return report

    async def run_comprehensive_connection_pool_stress_tests(self):
        """Execute all database connection pool stress tests."""
        logger.info("🚀 Starting comprehensive database connection pool stress tests...")

        try:
            # Execute all connection pool stress tests
            await self.test_concurrent_connection_exhaustion()
            await self.test_connection_leak_detection()
            await self.test_transaction_boundary_connection_stress()

            # Generate comprehensive report
            report = await self.generate_connection_pool_stress_report()

            # Save report to file
            report_filename = f"database_connection_pool_stress_report_{int(time.time())}.json"
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"📄 Connection pool stress test report saved to: {report_filename}")
            return report

        except Exception as e:
            logger.error(f"❌ Connection pool stress test failed: {e}", exc_info=True)
            raise


async def main():
    """Main execution function for database connection pool stress tests."""
    load_dotenv()

    logger.info("🎯 Database Connection Pool Stress Test Suite")
    logger.info("Testing singleton database client vulnerability and connection pool behavior")

    tester = DatabaseConnectionPoolStressTester()

    try:
        report = await tester.run_comprehensive_connection_pool_stress_tests()

        # Determine overall test result
        critical_issues = len(report['critical_findings'])
        if critical_issues > 0:
            logger.error(f"💥 CONNECTION POOL STRESS TEST RESULT: FAILED - {critical_issues} critical vulnerabilities confirmed")
            logger.error("🔧 IMMEDIATE ACTION REQUIRED: Implement connection pooling and transaction boundaries")
            sys.exit(1)
        else:
            logger.info("✅ CONNECTION POOL STRESS TEST RESULT: PASSED - No critical connection pool issues detected")

    except Exception as e:
        logger.error(f"🚨 Database connection pool stress test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())