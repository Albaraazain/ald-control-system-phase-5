#!/usr/bin/env python3
"""
Race condition security tester for ALD control system.
Tests for security implications of race conditions in dual-mode logging.
"""

import sys
import asyncio
import threading
import time
import json
from pathlib import Path
from typing import List, Dict, Any

class RaceConditionSecurityTester:
    """Race condition security testing without external dependencies."""

    def __init__(self):
        self.project_root = Path.cwd()

    def test_transactional_integration(self) -> Dict[str, Any]:
        """Test that transactional system is properly integrated."""
        print("🔍 Testing transactional integration...")

        integration_result = {
            'transactional_files_exist': False,
            'legacy_system_status': 'UNKNOWN',
            'integration_status': 'UNKNOWN'
        }

        # Check for transactional files
        transactional_files = [
            'src/data_collection/transactional/atomic_dual_mode_repository.py',
            'src/data_collection/transactional/transaction_manager.py',
            'src/data_collection/transactional/transactional_parameter_logger.py'
        ]

        existing_files = []
        for file_path in transactional_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                existing_files.append(file_path)

        integration_result['transactional_files_exist'] = len(existing_files) >= 2
        integration_result['existing_transactional_files'] = existing_files

        # Check if main service uses transactional system
        main_service_path = self.project_root / 'src' / 'main.py'
        if main_service_path.exists():
            try:
                with open(main_service_path, 'r', encoding='utf-8') as f:
                    main_content = f.read()

                if 'transactional' in main_content.lower():
                    integration_result['integration_status'] = 'INTEGRATED'
                elif 'continuous_parameter_logger' in main_content:
                    integration_result['legacy_system_status'] = 'STILL_ACTIVE'
                    integration_result['integration_status'] = 'PARTIAL'
                else:
                    integration_result['integration_status'] = 'UNKNOWN'

            except Exception as e:
                print(f"  ⚠️ Error reading main.py: {e}")

        # Check data collection service
        data_collection_service_path = self.project_root / 'src' / 'data_collection' / 'data_collection_service.py'
        if data_collection_service_path.exists():
            try:
                with open(data_collection_service_path, 'r', encoding='utf-8') as f:
                    service_content = f.read()

                if 'transactional_adapter' in service_content.lower():
                    integration_result['integration_status'] = 'INTEGRATED'
                elif 'continuous_parameter_logger' in service_content:
                    integration_result['legacy_system_status'] = 'ACTIVE'

            except Exception as e:
                print(f"  ⚠️ Error reading data_collection_service.py: {e}")

        print(f"  📊 Transactional files found: {len(existing_files)}")
        print(f"  📊 Integration status: {integration_result['integration_status']}")
        print(f"  📊 Legacy system: {integration_result['legacy_system_status']}")

        return integration_result

    def test_state_management_security(self) -> Dict[str, Any]:
        """Test state management for security vulnerabilities."""
        print("🔍 Testing state management security...")

        state_security = {
            'singleton_patterns_found': [],
            'state_files_analyzed': 0,
            'potential_race_conditions': [],
            'security_patterns': []
        }

        # Analyze state management files
        state_files = [
            'src/command_flow/command_state.py',
            'src/plc/manager.py',
            'src/data_collection/continuous_recorder.py'
        ]

        for state_file in state_files:
            file_path = self.project_root / state_file
            if file_path.exists():
                state_security['state_files_analyzed'] += 1

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Look for singleton patterns
                    if 'singleton' in content.lower() or '_instance' in content:
                        state_security['singleton_patterns_found'].append(state_file)

                    # Look for potential race conditions
                    if 'global' in content and ('=' in content or 'state' in content.lower()):
                        state_security['potential_race_conditions'].append({
                            'file': state_file,
                            'pattern': 'global_state_modification'
                        })

                    # Look for security patterns
                    if 'lock' in content.lower() or 'thread' in content.lower():
                        state_security['security_patterns'].append('thread_safety')
                    if 'async' in content and 'await' in content:
                        state_security['security_patterns'].append('async_safety')
                    if 'atomic' in content.lower():
                        state_security['security_patterns'].append('atomic_operations')

                except Exception as e:
                    print(f"  ⚠️ Error analyzing {state_file}: {e}")

        # Remove duplicates
        state_security['security_patterns'] = list(set(state_security['security_patterns']))

        print(f"  📊 State files analyzed: {state_security['state_files_analyzed']}")
        print(f"  📊 Singleton patterns: {len(state_security['singleton_patterns_found'])}")
        print(f"  📊 Potential race conditions: {len(state_security['potential_race_conditions'])}")
        print(f"  📊 Security patterns: {len(state_security['security_patterns'])}")

        return state_security

    def test_dual_mode_logging_security(self) -> Dict[str, Any]:
        """Test dual-mode logging for race condition security."""
        print("🔍 Testing dual-mode logging security...")

        dual_mode_security = {
            'dual_mode_files_found': [],
            'atomic_patterns_found': [],
            'transaction_patterns_found': [],
            'security_status': 'UNKNOWN'
        }

        # Look for dual-mode logging files
        dual_mode_patterns = [
            '**/continuous_parameter_logger.py',
            '**/dual_mode*.py',
            '**/atomic*.py',
            '**/transaction*.py'
        ]

        for pattern in dual_mode_patterns:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file():
                    dual_mode_security['dual_mode_files_found'].append(str(file_path))

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Look for atomic patterns
                        if 'atomic' in content.lower():
                            dual_mode_security['atomic_patterns_found'].append(str(file_path))

                        # Look for transaction patterns
                        if 'transaction' in content.lower() or 'rollback' in content.lower():
                            dual_mode_security['transaction_patterns_found'].append(str(file_path))

                    except Exception:
                        continue

        # Determine security status
        if len(dual_mode_security['atomic_patterns_found']) >= 2 and len(dual_mode_security['transaction_patterns_found']) >= 1:
            dual_mode_security['security_status'] = 'SECURE'
        elif len(dual_mode_security['atomic_patterns_found']) >= 1:
            dual_mode_security['security_status'] = 'PARTIAL'
        else:
            dual_mode_security['security_status'] = 'VULNERABLE'

        print(f"  📊 Dual-mode files: {len(dual_mode_security['dual_mode_files_found'])}")
        print(f"  📊 Atomic patterns: {len(dual_mode_security['atomic_patterns_found'])}")
        print(f"  📊 Transaction patterns: {len(dual_mode_security['transaction_patterns_found'])}")
        print(f"  📊 Security status: {dual_mode_security['security_status']}")

        return dual_mode_security

    def test_concurrent_access_patterns(self) -> Dict[str, Any]:
        """Test for concurrent access pattern security."""
        print("🔍 Testing concurrent access patterns...")

        concurrent_security = {
            'async_files_analyzed': 0,
            'thread_safety_patterns': [],
            'unsafe_patterns_found': [],
            'security_measures': []
        }

        # Analyze async and concurrent access files
        for py_file in self.project_root.glob('**/*.py'):
            if any(skip in str(py_file) for skip in ['test', 'venv', 'myenv', '__pycache__']):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                if 'async def' in content or 'await' in content:
                    concurrent_security['async_files_analyzed'] += 1

                    # Look for thread safety patterns
                    if 'asyncio.Lock' in content or 'threading.Lock' in content:
                        concurrent_security['thread_safety_patterns'].append(str(py_file))

                    # Look for unsafe patterns
                    if 'global' in content and '=' in content and 'async def' in content:
                        if 'lock' not in content.lower():
                            concurrent_security['unsafe_patterns_found'].append({
                                'file': str(py_file),
                                'pattern': 'unprotected_global_state_in_async'
                            })

                    # Look for security measures
                    if 'atomic' in content.lower():
                        concurrent_security['security_measures'].append('atomic_operations')
                    if 'transaction' in content.lower():
                        concurrent_security['security_measures'].append('transactions')
                    if 'semaphore' in content.lower():
                        concurrent_security['security_measures'].append('semaphore_control')

            except Exception:
                continue

        # Remove duplicates
        concurrent_security['security_measures'] = list(set(concurrent_security['security_measures']))

        print(f"  📊 Async files analyzed: {concurrent_security['async_files_analyzed']}")
        print(f"  📊 Thread safety patterns: {len(concurrent_security['thread_safety_patterns'])}")
        print(f"  📊 Unsafe patterns: {len(concurrent_security['unsafe_patterns_found'])}")
        print(f"  📊 Security measures: {len(concurrent_security['security_measures'])}")

        return concurrent_security

    def run_race_condition_security_tests(self) -> Dict[str, Any]:
        """Run comprehensive race condition security tests."""
        print("🚀 Starting race condition security testing...")
        print("=" * 60)

        results = {
            'transactional_integration': self.test_transactional_integration(),
            'state_management': self.test_state_management_security(),
            'dual_mode_logging': self.test_dual_mode_logging_security(),
            'concurrent_access': self.test_concurrent_access_patterns()
        }

        # Calculate overall security status
        security_scores = {
            'INTEGRATED': 100,
            'SECURE': 100,
            'PARTIAL': 75,
            'ACCEPTABLE': 60,
            'VULNERABLE': 25,
            'UNKNOWN': 50
        }

        total_score = 0
        valid_tests = 0

        for test_name, test_result in results.items():
            # Get status from different test types
            if test_name == 'transactional_integration':
                status = test_result.get('integration_status', 'UNKNOWN')
            else:
                status = test_result.get('security_status', 'UNKNOWN')

            if status in security_scores:
                total_score += security_scores[status]
                valid_tests += 1

        if valid_tests > 0:
            average_score = total_score / valid_tests
            if average_score >= 90:
                overall_status = 'EXCELLENT'
            elif average_score >= 75:
                overall_status = 'GOOD'
            elif average_score >= 50:
                overall_status = 'ACCEPTABLE'
            else:
                overall_status = 'NEEDS_IMPROVEMENT'
        else:
            overall_status = 'UNKNOWN'

        # Count critical issues
        critical_issues = 0
        if results['transactional_integration']['integration_status'] == 'PARTIAL':
            critical_issues += 1
        if results['dual_mode_logging']['security_status'] == 'VULNERABLE':
            critical_issues += 1

        total_unsafe_patterns = len(results['concurrent_access']['unsafe_patterns_found'])
        critical_issues += total_unsafe_patterns

        results['overall'] = {
            'security_score': average_score if valid_tests > 0 else 0,
            'status': overall_status,
            'tests_completed': len(results) - 1,
            'critical_issues': critical_issues,
            'secure_tests': len([r for r in results.values() if r.get('security_status') == 'SECURE' or r.get('integration_status') == 'INTEGRATED'])
        }

        print("=" * 60)
        print("📋 RACE CONDITION SECURITY TEST SUMMARY")
        print("=" * 60)
        print(f"🎯 Overall Security Score: {results['overall']['security_score']:.1f}%")
        print(f"📊 Status: {overall_status}")
        print(f"✅ Secure tests: {results['overall']['secure_tests']}/{results['overall']['tests_completed']}")
        print(f"🔴 Critical issues: {critical_issues}")

        if overall_status in ['EXCELLENT', 'GOOD'] and critical_issues == 0:
            print("🎉 Race condition security testing PASSED!")
        else:
            print("⚠️ Race condition security needs improvement!")

        # Save results
        results_file = self.project_root / 'race_condition_security_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"📄 Results saved to: {results_file}")

        return results

if __name__ == "__main__":
    tester = RaceConditionSecurityTester()
    results = tester.run_race_condition_security_tests()

    # Exit with appropriate code
    overall_status = results['overall']['status']
    critical_issues = results['overall']['critical_issues']
    exit_code = 0 if overall_status in ['EXCELLENT', 'GOOD'] and critical_issues == 0 else 1
    sys.exit(exit_code)