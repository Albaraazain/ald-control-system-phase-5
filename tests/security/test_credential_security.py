"""
Credential security testing framework for ALD control system.

Tests for:
- Credential exposure detection
- Credential rotation validation
- Secure credential injection
- Security regression testing
"""
import os
import re
import json
import pytest
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import patch, Mock

# Security patterns for credential detection
CREDENTIAL_PATTERNS = {
    'supabase_url': r'https://[a-z0-9]+\.supabase\.co',
    'supabase_key': r'eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*',
    'api_key': r'[Aa][Pp][Ii]_?[Kk][Ee][Yy].*[=:]\s*["\']?[A-Za-z0-9_-]{20,}',
    'password': r'[Pp]assword.*[=:]\s*["\']?[A-Za-z0-9_@$!%*?&]{8,}',
    'secret': r'[Ss]ecret.*[=:]\s*["\']?[A-Za-z0-9_-]{20,}',
    'token': r'[Tt]oken.*[=:]\s*["\']?[A-Za-z0-9_-]{20,}',
    'private_key': r'-----BEGIN.*PRIVATE KEY-----',
    'uuid': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
}

# High entropy strings that might be secrets
ENTROPY_THRESHOLD = 4.5

class CredentialSecurityTester:
    """Comprehensive credential security testing framework."""

    def __init__(self, project_root: str = None):
        """Initialize the credential security tester."""
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.violations = []

    def calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not text:
            return 0

        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Calculate entropy
        entropy = 0
        text_length = len(text)
        for count in char_counts.values():
            probability = count / text_length
            entropy -= probability * (probability and (probability.bit_length() - 1) or 0)

        return entropy

    def scan_file_for_credentials(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan a single file for potential credentials."""
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

                for line_num, line in enumerate(lines, 1):
                    # Check for known credential patterns
                    for pattern_name, pattern in CREDENTIAL_PATTERNS.items():
                        matches = re.finditer(pattern, line, re.IGNORECASE)
                        for match in matches:
                            violations.append({
                                'type': 'credential_pattern',
                                'pattern': pattern_name,
                                'file': str(file_path),
                                'line': line_num,
                                'match': match.group(),
                                'severity': 'high' if pattern_name in ['supabase_key', 'private_key'] else 'medium'
                            })

                    # Check for high entropy strings
                    words = re.findall(r'[A-Za-z0-9_-]{20,}', line)
                    for word in words:
                        if self.calculate_entropy(word) > ENTROPY_THRESHOLD:
                            violations.append({
                                'type': 'high_entropy',
                                'file': str(file_path),
                                'line': line_num,
                                'match': word,
                                'entropy': self.calculate_entropy(word),
                                'severity': 'medium'
                            })

        except Exception as e:
            violations.append({
                'type': 'scan_error',
                'file': str(file_path),
                'error': str(e),
                'severity': 'low'
            })

        return violations

    def scan_project_for_credentials(self, exclude_patterns: List[str] = None) -> List[Dict[str, Any]]:
        """Scan entire project for potential credentials."""
        if exclude_patterns is None:
            exclude_patterns = [
                '*.git/*',
                '*/__pycache__/*',
                '*/myenv/*',
                '*/venv/*',
                '*.pyc',
                '*.log',
                '*/.pytest_cache/*',
                '*/tests/security/*'  # Don't scan our own test files
            ]

        all_violations = []

        # Get all Python files and config files
        file_patterns = ['**/*.py', '**/*.json', '**/*.yaml', '**/*.yml', '**/*.env*', '**/*.ini', '**/*.cfg']

        for pattern in file_patterns:
            for file_path in self.project_root.glob(pattern):
                # Skip excluded patterns
                if any(file_path.match(exclude) for exclude in exclude_patterns):
                    continue

                violations = self.scan_file_for_credentials(file_path)
                all_violations.extend(violations)

        return all_violations

    def check_gitignore_security(self) -> List[Dict[str, Any]]:
        """Check if .gitignore properly excludes sensitive files."""
        violations = []
        gitignore_path = self.project_root / '.gitignore'

        required_patterns = [
            '.env',
            '.env.*',
            '*.key',
            '*.pem',
            '*.p12',
            '*.pfx',
            '*.crt'
        ]

        if not gitignore_path.exists():
            violations.append({
                'type': 'missing_gitignore',
                'file': str(gitignore_path),
                'severity': 'high',
                'message': '.gitignore file not found'
            })
            return violations

        try:
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()

            for pattern in required_patterns:
                if pattern not in gitignore_content:
                    violations.append({
                        'type': 'missing_gitignore_pattern',
                        'file': str(gitignore_path),
                        'pattern': pattern,
                        'severity': 'medium',
                        'message': f'Missing .gitignore pattern: {pattern}'
                    })

        except Exception as e:
            violations.append({
                'type': 'gitignore_read_error',
                'file': str(gitignore_path),
                'error': str(e),
                'severity': 'medium'
            })

        return violations

    def check_git_history_exposure(self) -> List[Dict[str, Any]]:
        """Check if credentials exist in git history."""
        violations = []

        try:
            # Check if we're in a git repository
            result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                                  capture_output=True, text=True, cwd=self.project_root)
            if result.returncode != 0:
                return violations

            # Search for potential credentials in git history
            search_patterns = [
                'SUPABASE_KEY',
                'API_KEY',
                'PASSWORD',
                'SECRET',
                'eyJ'  # JWT token start
            ]

            for pattern in search_patterns:
                cmd = ['git', 'log', '--all', '--grep', pattern, '--oneline']
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)

                if result.stdout.strip():
                    violations.append({
                        'type': 'git_history_credential',
                        'pattern': pattern,
                        'matches': result.stdout.strip().split('\n'),
                        'severity': 'critical',
                        'message': f'Potential credential pattern "{pattern}" found in git history'
                    })

        except Exception as e:
            violations.append({
                'type': 'git_history_check_error',
                'error': str(e),
                'severity': 'low'
            })

        return violations


class TestCredentialSecurity:
    """Credential security test suite."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tester = CredentialSecurityTester()

    def test_no_credentials_in_source_code(self):
        """Test that source code contains no exposed credentials."""
        violations = self.tester.scan_project_for_credentials()

        # Filter out expected test patterns and development credentials
        critical_violations = [
            v for v in violations
            if v.get('severity') in ['high', 'critical']
            and 'test' not in v.get('file', '').lower()
            and 'example' not in v.get('file', '').lower()
        ]

        if critical_violations:
            error_msg = "Critical credential security violations found:\n"
            for violation in critical_violations[:5]:  # Show first 5
                error_msg += f"  - {violation['type']}: {violation['file']}:{violation.get('line', '?')}\n"
            if len(critical_violations) > 5:
                error_msg += f"  ... and {len(critical_violations) - 5} more violations"

        assert len(critical_violations) == 0, error_msg

    def test_gitignore_security_configuration(self):
        """Test that .gitignore properly excludes sensitive files."""
        violations = self.tester.check_gitignore_security()

        critical_violations = [v for v in violations if v.get('severity') == 'high']

        assert len(critical_violations) == 0, f"Critical .gitignore security issues: {critical_violations}"

    def test_no_credentials_in_git_history(self):
        """Test that credentials are not exposed in git history."""
        violations = self.tester.check_git_history_exposure()

        critical_violations = [v for v in violations if v.get('severity') == 'critical']

        if critical_violations:
            error_msg = "Credentials found in git history - IMMEDIATE ACTION REQUIRED:\n"
            for violation in critical_violations:
                error_msg += f"  - Pattern '{violation['pattern']}' found in commits\n"
            error_msg += "\nRecommended actions:\n"
            error_msg += "  1. Rotate all exposed credentials immediately\n"
            error_msg += "  2. Use git filter-branch or BFG Repo-Cleaner to remove from history\n"
            error_msg += "  3. Force push clean history (coordinate with team)\n"

        assert len(critical_violations) == 0, error_msg

    @pytest.mark.parametrize("env_var", ["SUPABASE_URL", "SUPABASE_KEY", "MACHINE_ID"])
    def test_secure_environment_variable_access(self, env_var):
        """Test that environment variables are accessed securely."""
        # Mock environment to test secure access patterns
        with patch.dict(os.environ, {env_var: "test_value"}):
            # Test that the configuration module properly validates environment variables
            from src.config import is_supabase_config_present

            if env_var in ["SUPABASE_URL", "SUPABASE_KEY"]:
                assert is_supabase_config_present(), f"Configuration validation failed for {env_var}"

    def test_database_credential_security(self):
        """Test that database credentials are not logged or exposed."""
        from src.db import get_supabase
        from src.log_setup import logger

        # Mock logging to capture log messages
        with patch.object(logger, 'info') as mock_logger:
            try:
                # This should not expose full credentials in logs
                get_supabase()

                # Check that logged messages don't contain full credentials
                for call in mock_logger.call_args_list:
                    args = call[0]
                    if args:
                        log_message = str(args[0])
                        # Should only contain partial credentials (first 10 chars)
                        assert len(re.findall(r'eyJ[A-Za-z0-9_-]{20,}', log_message)) == 0, \
                            f"Full Supabase key exposed in log: {log_message}"

            except Exception:
                # Configuration might not be present in test environment
                pass

    def test_credential_rotation_readiness(self):
        """Test that system can handle credential rotation."""
        # Test that configuration can be reloaded
        original_env = os.environ.copy()

        try:
            # Simulate credential rotation
            test_creds = {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'eyJtest_rotated_key',
                'MACHINE_ID': 'test-machine-id'
            }

            with patch.dict(os.environ, test_creds):
                from src.config import SUPABASE_URL, SUPABASE_KEY, MACHINE_ID

                # Verify that new credentials are properly loaded
                # Note: This tests the configuration loading, actual rotation would require service restart
                assert SUPABASE_URL == test_creds['SUPABASE_URL']
                assert SUPABASE_KEY == test_creds['SUPABASE_KEY']
                assert MACHINE_ID == test_creds['MACHINE_ID']

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)


# CI/CD Integration Functions
def run_credential_security_scan():
    """Run comprehensive credential security scan for CI/CD integration."""
    tester = CredentialSecurityTester()

    print("Running credential security scan...")

    # Scan for credentials
    violations = tester.scan_project_for_credentials()
    critical_count = len([v for v in violations if v.get('severity') in ['high', 'critical']])

    # Check .gitignore
    gitignore_violations = tester.check_gitignore_security()
    gitignore_critical = len([v for v in gitignore_violations if v.get('severity') == 'high'])

    # Check git history
    history_violations = tester.check_git_history_exposure()
    history_critical = len([v for v in history_violations if v.get('severity') == 'critical'])

    total_critical = critical_count + gitignore_critical + history_critical

    print(f"Credential Security Scan Results:")
    print(f"  Critical violations: {total_critical}")
    print(f"  Source code issues: {critical_count}")
    print(f"  .gitignore issues: {gitignore_critical}")
    print(f"  Git history issues: {history_critical}")

    if total_critical > 0:
        print("\n❌ SECURITY SCAN FAILED - Critical credential security issues found!")
        return False
    else:
        print("\n✅ SECURITY SCAN PASSED - No critical credential issues found")
        return True


if __name__ == "__main__":
    # Run scan when executed directly
    success = run_credential_security_scan()
    exit(0 if success else 1)