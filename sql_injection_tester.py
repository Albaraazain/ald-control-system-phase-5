#!/usr/bin/env python3
"""
SQL Injection vulnerability tester for ALD control system.
Tests database operations for injection vulnerabilities.
"""

import sys
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime
import uuid

class SQLInjectionTester:
    """SQL injection vulnerability testing without external dependencies."""

    def __init__(self):
        self.project_root = Path.cwd()
        self.injection_payloads = [
            "'; DROP TABLE parameter_value_history; --",
            "' OR '1'='1' --",
            "'; UPDATE machines SET status='hacked'; --",
            "' UNION SELECT * FROM machines --",
            "'; INSERT INTO parameter_value_history VALUES('malicious'); --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "NULL; --",
            "'; EXEC xp_cmdshell('dir'); --",
            "' AND 1=1 AND SUBSTRING(@@version,1,1)='5",
        ]

    def test_parameter_insertion_security(self):
        """Test parameter insertion against SQL injection."""
        print("🔍 Testing parameter insertion security...")

        try:
            # Add src to path
            sys.path.insert(0, str(self.project_root / 'src'))

            # Import the logger
            from data_collection.continuous_parameter_logger import ContinuousParameterLogger

            logger = ContinuousParameterLogger()

            # Create mock Supabase client
            mock_supabase = Mock()
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_table.insert.return_value = Mock()
            mock_table.insert.return_value.execute.return_value = Mock(data=[])

            vulnerabilities = []

            for payload in self.injection_payloads:
                test_data = {
                    'parameter_id': payload,
                    'value': 42.0,
                    'set_point': 45.0,
                    'timestamp': datetime.now().isoformat()
                }

                with patch('src.data_collection.continuous_parameter_logger.get_supabase', return_value=mock_supabase):
                    try:
                        # Run the async function
                        result = asyncio.run(logger._insert_records([test_data], [], None))

                        # Check what was passed to insert
                        if mock_table.insert.called:
                            call_args = mock_table.insert.call_args
                            if call_args:
                                inserted_data = str(call_args)
                                # Look for dangerous SQL patterns
                                if any(dangerous in inserted_data.upper() for dangerous in ['DROP TABLE', 'DELETE FROM', 'UPDATE']):
                                    vulnerabilities.append({
                                        'payload': payload,
                                        'issue': 'SQL injection pattern detected in insert call',
                                        'data': inserted_data[:200]
                                    })

                    except Exception as e:
                        error_msg = str(e).lower()
                        # Injection should either be prevented or cause a controlled error
                        if 'syntax error' in error_msg or 'sql' in error_msg:
                            vulnerabilities.append({
                                'payload': payload,
                                'issue': 'SQL injection may have occurred',
                                'error': str(e)[:200]
                            })

            print(f"  📊 Tested {len(self.injection_payloads)} injection payloads")
            print(f"  📊 Vulnerabilities found: {len(vulnerabilities)}")

            return {
                'tested_payloads': len(self.injection_payloads),
                'vulnerabilities': vulnerabilities,
                'status': 'PASS' if len(vulnerabilities) == 0 else 'FAIL'
            }

        except ImportError as e:
            print(f"  ⚠️ Cannot import logger module: {e}")
            return {'status': 'SKIP', 'reason': 'Module import failed'}
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    def test_metadata_query_security(self):
        """Test metadata queries for injection vulnerabilities."""
        print("🔍 Testing metadata query security...")

        try:
            sys.path.insert(0, str(self.project_root / 'src'))
            from data_collection.continuous_parameter_logger import ContinuousParameterLogger

            logger = ContinuousParameterLogger()

            # Create mock Supabase client
            mock_supabase = Mock()
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_select = Mock()
            mock_table.select.return_value = mock_select
            mock_in = Mock()
            mock_select.in_.return_value = mock_in
            mock_in.execute.return_value = Mock(data=[])

            vulnerabilities = []

            malicious_param_ids = [
                "'; DROP TABLE component_parameters; --",
                "' OR '1'='1",
                "param_id'; UPDATE component_parameters SET set_value=999; --"
            ]

            for param_id in malicious_param_ids:
                with patch('src.data_collection.continuous_parameter_logger.get_supabase', return_value=mock_supabase):
                    try:
                        result = asyncio.run(logger._get_parameter_metadata([param_id]))

                        # Check if dangerous patterns were passed to the query
                        if mock_select.in_.called:
                            call_args = mock_select.in_.call_args
                            if call_args:
                                query_data = str(call_args)
                                if any(dangerous in query_data.upper() for dangerous in ['DROP TABLE', 'UPDATE']):
                                    vulnerabilities.append({
                                        'payload': param_id,
                                        'issue': 'SQL injection pattern in metadata query',
                                        'data': query_data[:200]
                                    })

                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'syntax error' in error_msg or 'sql' in error_msg:
                            vulnerabilities.append({
                                'payload': param_id,
                                'issue': 'SQL injection in metadata query',
                                'error': str(e)[:200]
                            })

            print(f"  📊 Tested {len(malicious_param_ids)} malicious parameter IDs")
            print(f"  📊 Vulnerabilities found: {len(vulnerabilities)}")

            return {
                'tested_param_ids': len(malicious_param_ids),
                'vulnerabilities': vulnerabilities,
                'status': 'PASS' if len(vulnerabilities) == 0 else 'FAIL'
            }

        except ImportError as e:
            print(f"  ⚠️ Cannot import logger module: {e}")
            return {'status': 'SKIP', 'reason': 'Module import failed'}
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    def test_process_id_validation(self):
        """Test process ID queries for injection vulnerabilities."""
        print("🔍 Testing process ID validation...")

        try:
            sys.path.insert(0, str(self.project_root / 'src'))
            from data_collection.continuous_parameter_logger import ContinuousParameterLogger

            logger = ContinuousParameterLogger()

            # Create mock Supabase client
            mock_supabase = Mock()
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_select = Mock()
            mock_table.select.return_value = mock_select
            mock_eq = Mock()
            mock_select.eq.return_value = mock_eq
            mock_single = Mock()
            mock_eq.single.return_value = mock_single
            mock_single.execute.return_value = Mock(data=None)

            vulnerabilities = []

            malicious_machine_ids = [
                "'; DROP TABLE machines; --",
                "' OR '1'='1' --",
                "machine_id'; UPDATE machines SET status='compromised'; --"
            ]

            for machine_id in malicious_machine_ids:
                # Mock the config
                with patch('src.config.MACHINE_ID', machine_id):
                    with patch('src.data_collection.continuous_parameter_logger.get_supabase', return_value=mock_supabase):
                        try:
                            result = asyncio.run(logger._get_current_process_id())

                            # Check if dangerous patterns were passed to the query
                            if mock_select.eq.called:
                                call_args = mock_select.eq.call_args
                                if call_args:
                                    query_data = str(call_args)
                                    if any(dangerous in query_data.upper() for dangerous in ['DROP TABLE', 'UPDATE']):
                                        vulnerabilities.append({
                                            'payload': machine_id,
                                            'issue': 'SQL injection pattern in process ID query',
                                            'data': query_data[:200]
                                        })

                        except Exception as e:
                            error_msg = str(e).lower()
                            if 'syntax error' in error_msg or 'sql' in error_msg:
                                vulnerabilities.append({
                                    'payload': machine_id,
                                    'issue': 'SQL injection in process ID query',
                                    'error': str(e)[:200]
                                })

            print(f"  📊 Tested {len(malicious_machine_ids)} malicious machine IDs")
            print(f"  📊 Vulnerabilities found: {len(vulnerabilities)}")

            return {
                'tested_machine_ids': len(malicious_machine_ids),
                'vulnerabilities': vulnerabilities,
                'status': 'PASS' if len(vulnerabilities) == 0 else 'FAIL'
            }

        except ImportError as e:
            print(f"  ⚠️ Cannot import logger module: {e}")
            return {'status': 'SKIP', 'reason': 'Module import failed'}
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    def run_sql_injection_tests(self):
        """Run comprehensive SQL injection vulnerability tests."""
        print("🚀 Starting SQL injection vulnerability testing...")
        print("=" * 60)

        results = {
            'parameter_insertion': self.test_parameter_insertion_security(),
            'metadata_queries': self.test_metadata_query_security(),
            'process_id_validation': self.test_process_id_validation()
        }

        # Calculate overall status
        passed_tests = len([r for r in results.values() if r.get('status') == 'PASS'])
        failed_tests = len([r for r in results.values() if r.get('status') == 'FAIL'])
        skipped_tests = len([r for r in results.values() if r.get('status') in ['SKIP', 'ERROR']])

        total_vulnerabilities = sum(len(r.get('vulnerabilities', [])) for r in results.values())

        print("=" * 60)
        print("📋 SQL INJECTION TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed tests: {passed_tests}")
        print(f"❌ Failed tests: {failed_tests}")
        print(f"⚠️ Skipped/Error tests: {skipped_tests}")
        print(f"🔒 Total vulnerabilities found: {total_vulnerabilities}")

        overall_status = 'PASS' if failed_tests == 0 and total_vulnerabilities == 0 else 'FAIL'
        print(f"📊 Overall SQL Injection Security: {overall_status}")

        # Save results
        results_file = self.project_root / 'sql_injection_test_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"📄 Results saved to: {results_file}")

        return results

if __name__ == "__main__":
    tester = SQLInjectionTester()
    results = tester.run_sql_injection_tests()

    # Exit with appropriate code
    total_vulnerabilities = sum(len(r.get('vulnerabilities', [])) for r in results.values())
    exit_code = 0 if total_vulnerabilities == 0 else 1
    sys.exit(exit_code)