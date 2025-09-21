#!/usr/bin/env python3
"""
Standalone security validation script for ALD control system.
Executes comprehensive security testing without external dependencies.
"""

import os
import re
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

class SecurityValidator:
    """Comprehensive security validation without external dependencies."""

    def __init__(self):
        self.project_root = Path.cwd()
        self.results = {
            'credential_security': {},
            'database_security': {},
            'plc_security': {},
            'file_permissions': {},
            'configuration_security': {}
        }

    def validate_credential_security(self) -> Dict[str, Any]:
        """Validate credential security measures."""
        print("🔍 Validating credential security...")

        # Check if .env files are properly excluded
        env_files = list(self.project_root.glob('**/.env*'))
        gitignored_env_files = []

        try:
            gitignore_path = self.project_root / '.gitignore'
            if gitignore_path.exists():
                with open(gitignore_path, 'r') as f:
                    gitignore_content = f.read()
                    if '.env' in gitignore_content:
                        gitignored_env_files = [str(f) for f in env_files]
        except Exception as e:
            print(f"  ⚠️ Error reading .gitignore: {e}")

        # Scan for credential patterns in source files
        credential_patterns = {
            'supabase_url': r'https://[a-z0-9]+\.supabase\.co',
            'supabase_key': r'eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*',
            'api_key': r'[Aa][Pp][Ii]_?[Kk][Ee][Yy].*[=:]\s*["\']?[A-Za-z0-9_-]{20,}',
            'password': r'[Pp]assword.*[=:]\s*["\']?[A-Za-z0-9_@$!%*?&]{8,}',
        }

        violations = []
        for pattern_name, pattern in credential_patterns.items():
            for py_file in self.project_root.glob('**/*.py'):
                # Skip test files and virtual environments
                if any(skip in str(py_file) for skip in ['test', 'venv', 'myenv', '__pycache__']):
                    continue

                try:
                    with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            violations.append({
                                'type': pattern_name,
                                'file': str(py_file),
                                'match': match.group()[:50] + '...' if len(match.group()) > 50 else match.group()
                            })
                except Exception:
                    continue

        result = {
            'env_files_found': len(env_files),
            'env_files_gitignored': len(gitignored_env_files),
            'credential_violations': violations,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

        print(f"  📊 Environment files: {len(env_files)} found, {len(gitignored_env_files)} gitignored")
        print(f"  📊 Credential violations: {len(violations)}")
        print(f"  {'✅' if result['status'] == 'PASS' else '❌'} Credential security: {result['status']}")

        return result

    def validate_configuration_security(self) -> Dict[str, Any]:
        """Validate security configuration files."""
        print("🔍 Validating security configuration...")

        config_files = {
            '.security_config.json': self.project_root / '.security_config.json',
            'src/security/security_config.py': self.project_root / 'src' / 'security' / 'security_config.py',
            'src/security/credential_manager.py': self.project_root / 'src' / 'security' / 'credential_manager.py'
        }

        existing_configs = {}
        for name, path in config_files.items():
            if path.exists():
                existing_configs[name] = {
                    'exists': True,
                    'size': path.stat().st_size,
                    'permissions': oct(path.stat().st_mode)[-3:]
                }
            else:
                existing_configs[name] = {'exists': False}

        # Check security configuration content
        security_features = []
        if config_files['.security_config.json'].exists():
            try:
                with open(config_files['.security_config.json'], 'r') as f:
                    config = json.load(f)
                    if config.get('credential_scanning', {}).get('enabled'):
                        security_features.append('credential_scanning')
                    if config.get('database_security', {}).get('enabled'):
                        security_features.append('database_security')
                    if config.get('plc_security', {}).get('enabled'):
                        security_features.append('plc_security')
            except Exception as e:
                print(f"  ⚠️ Error reading security config: {e}")

        result = {
            'config_files': existing_configs,
            'security_features': security_features,
            'status': 'PASS' if len(security_features) >= 3 else 'PARTIAL'
        }

        print(f"  📊 Security configs found: {len([c for c in existing_configs.values() if c.get('exists')])}")
        print(f"  📊 Security features enabled: {len(security_features)}")
        print(f"  {'✅' if result['status'] == 'PASS' else '🔶'} Configuration security: {result['status']}")

        return result

    def validate_database_security(self) -> Dict[str, Any]:
        """Validate database security implementation."""
        print("🔍 Validating database security...")

        # Check for database security test files
        db_security_files = list(self.project_root.glob('**/test_database_security.py'))

        # Check for SQL injection protection patterns in data collection
        data_collection_files = list(self.project_root.glob('**/data_collection/**/*.py'))
        security_patterns = []

        for file in data_collection_files:
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Look for parameterized queries or ORM usage
                    if 'supabase' in content.lower() and ('insert' in content or 'select' in content):
                        if '.insert(' in content or '.select(' in content:
                            security_patterns.append('parameterized_queries')
                    if 'validate' in content.lower() or 'validation' in content.lower():
                        security_patterns.append('input_validation')
            except Exception:
                continue

        result = {
            'security_test_files': len(db_security_files),
            'security_patterns': list(set(security_patterns)),
            'data_collection_files': len(data_collection_files),
            'status': 'PASS' if len(security_patterns) >= 1 else 'NEEDS_IMPROVEMENT'
        }

        print(f"  📊 Database security test files: {len(db_security_files)}")
        print(f"  📊 Security patterns found: {len(set(security_patterns))}")
        print(f"  {'✅' if result['status'] == 'PASS' else '⚠️'} Database security: {result['status']}")

        return result

    def validate_plc_security(self) -> Dict[str, Any]:
        """Validate PLC communication security."""
        print("🔍 Validating PLC communication security...")

        # Check for PLC security test files
        plc_security_files = list(self.project_root.glob('**/test_plc_security.py'))

        # Check PLC communication files for security measures
        plc_files = list(self.project_root.glob('**/plc/**/*.py'))
        security_measures = []

        for file in plc_files:
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'timeout' in content.lower():
                        security_measures.append('connection_timeout')
                    if 'validation' in content.lower() or 'validate' in content.lower():
                        security_measures.append('input_validation')
                    if 'error' in content.lower() and 'handling' in content.lower():
                        security_measures.append('error_handling')
                    if 'retry' in content.lower() or 'reconnect' in content.lower():
                        security_measures.append('retry_logic')
            except Exception:
                continue

        result = {
            'security_test_files': len(plc_security_files),
            'security_measures': list(set(security_measures)),
            'plc_files': len(plc_files),
            'status': 'PASS' if len(set(security_measures)) >= 2 else 'NEEDS_IMPROVEMENT'
        }

        print(f"  📊 PLC security test files: {len(plc_security_files)}")
        print(f"  📊 Security measures found: {len(set(security_measures))}")
        print(f"  {'✅' if result['status'] == 'PASS' else '⚠️'} PLC security: {result['status']}")

        return result

    def validate_file_permissions(self) -> Dict[str, Any]:
        """Validate critical file permissions."""
        print("🔍 Validating file permissions...")

        critical_files = [
            '.security_config.json',
            'src/security/credential_manager.py',
            'src/config.py'
        ]

        permission_results = {}
        for file_name in critical_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                permissions = oct(file_path.stat().st_mode)[-3:]
                permission_results[file_name] = {
                    'permissions': permissions,
                    'secure': permissions in ['600', '644', '755']  # Common secure permissions
                }
            else:
                permission_results[file_name] = {'exists': False}

        secure_files = len([r for r in permission_results.values() if r.get('secure', False)])
        total_files = len([r for r in permission_results.values() if 'permissions' in r])

        result = {
            'file_permissions': permission_results,
            'secure_files': secure_files,
            'total_files': total_files,
            'status': 'PASS' if secure_files == total_files and total_files > 0 else 'PARTIAL'
        }

        print(f"  📊 Critical files checked: {total_files}")
        print(f"  📊 Securely configured: {secure_files}")
        print(f"  {'✅' if result['status'] == 'PASS' else '🔶'} File permissions: {result['status']}")

        return result

    def run_comprehensive_security_validation(self) -> Dict[str, Any]:
        """Run all security validations."""
        print("🚀 Starting comprehensive security validation...")
        print("=" * 60)

        self.results['credential_security'] = self.validate_credential_security()
        self.results['configuration_security'] = self.validate_configuration_security()
        self.results['database_security'] = self.validate_database_security()
        self.results['plc_security'] = self.validate_plc_security()
        self.results['file_permissions'] = self.validate_file_permissions()

        # Calculate overall security score
        scores = {
            'PASS': 100,
            'PARTIAL': 75,
            'NEEDS_IMPROVEMENT': 50,
            'FAIL': 0
        }

        total_score = sum(scores.get(result.get('status', 'FAIL'), 0) for result in self.results.values())
        max_score = len(self.results) * 100
        security_percentage = (total_score / max_score) * 100

        # Determine overall status
        if security_percentage >= 90:
            overall_status = 'EXCELLENT'
        elif security_percentage >= 75:
            overall_status = 'GOOD'
        elif security_percentage >= 60:
            overall_status = 'ACCEPTABLE'
        else:
            overall_status = 'NEEDS_IMPROVEMENT'

        self.results['overall'] = {
            'security_score': security_percentage,
            'status': overall_status,
            'total_checks': len(self.results) - 1,  # Exclude 'overall' itself
            'passed_checks': len([r for r in self.results.values() if r.get('status') == 'PASS'])
        }

        print("=" * 60)
        print("📋 SECURITY VALIDATION SUMMARY")
        print("=" * 60)
        print(f"🎯 Overall Security Score: {security_percentage:.1f}%")
        print(f"📊 Status: {overall_status}")
        print(f"✅ Passed Checks: {self.results['overall']['passed_checks']}/{self.results['overall']['total_checks']}")

        if overall_status in ['EXCELLENT', 'GOOD']:
            print("🎉 Security validation PASSED!")
            return_code = 0
        else:
            print("⚠️ Security validation needs improvement!")
            return_code = 1

        # Save detailed results
        results_file = self.project_root / 'security_validation_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"📄 Detailed results saved to: {results_file}")

        return self.results

if __name__ == "__main__":
    validator = SecurityValidator()
    results = validator.run_comprehensive_security_validation()

    # Exit with appropriate code for CI/CD
    overall_status = results['overall']['status']
    exit_code = 0 if overall_status in ['EXCELLENT', 'GOOD'] else 1
    sys.exit(exit_code)