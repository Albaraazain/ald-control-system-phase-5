#!/usr/bin/env python3
"""
Pre-commit security validation script for ALD control system.

This script runs essential security checks before commits to prevent
credential exposure and other security issues.
"""
import os
import sys
import subprocess
import re
import json
from pathlib import Path
from typing import List, Dict, Any

class PreCommitSecurityValidator:
    """Pre-commit security validation."""

    def __init__(self):
        """Initialize the validator."""
        self.project_root = Path.cwd()
        self.violations = []

    def run_validation(self) -> bool:
        """Run all pre-commit security validations."""
        print("🔒 Running pre-commit security validation...")

        # 1. Check for credential exposure
        if not self._check_credential_exposure():
            return False

        # 2. Check .gitignore configuration
        if not self._check_gitignore_security():
            return False

        # 3. Check file permissions
        if not self._check_file_permissions():
            return False

        # 4. Check for security anti-patterns
        if not self._check_code_security():
            return False

        # 5. Validate staged files
        if not self._validate_staged_files():
            return False

        print("✅ Pre-commit security validation passed")
        return True

    def _check_credential_exposure(self) -> bool:
        """Check for credential exposure in staged files."""
        print("  Checking for credential exposure...")

        # Get staged files
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=True
            )
            staged_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            print("    Warning: Could not get staged files")
            return True

        # Credential patterns
        credential_patterns = {
            'supabase_key': r'eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*',
            'api_key': r'[Aa][Pp][Ii]_?[Kk][Ee][Yy].*[=:]\s*["\']?[A-Za-z0-9_-]{20,}',
            'password': r'[Pp]assword.*[=:]\s*["\']?[A-Za-z0-9_@$!%*?&]{8,}',
            'secret': r'[Ss]ecret.*[=:]\s*["\']?[A-Za-z0-9_-]{20,}',
            'private_key': r'-----BEGIN.*PRIVATE KEY-----',
        }

        violations_found = False

        for file_path in staged_files:
            if not file_path or not Path(file_path).exists():
                continue

            # Skip binary files and specific file types
            if any(file_path.endswith(ext) for ext in ['.pyc', '.png', '.jpg', '.gif', '.pdf']):
                continue

            try:
                # Get staged content
                result = subprocess.run(
                    ["git", "show", f":{file_path}"],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    continue

                content = result.stdout
                lines = content.split('\n')

                for line_num, line in enumerate(lines, 1):
                    for pattern_name, pattern in credential_patterns.items():
                        matches = re.finditer(pattern, line, re.IGNORECASE)
                        for match in matches:
                            print(f"    ❌ CREDENTIAL EXPOSURE DETECTED:")
                            print(f"       File: {file_path}:{line_num}")
                            print(f"       Pattern: {pattern_name}")
                            print(f"       Content: {match.group()[:20]}...")
                            violations_found = True

            except Exception as e:
                print(f"    Warning: Could not check {file_path}: {e}")

        if violations_found:
            print(f"\n❌ COMMIT BLOCKED: Credential exposure detected!")
            print(f"   Please remove credentials and use environment variables instead.")
            print(f"   Check your .env file is in .gitignore")
            return False

        return True

    def _check_gitignore_security(self) -> bool:
        """Check that .gitignore includes security patterns."""
        print("  Checking .gitignore security configuration...")

        gitignore_path = self.project_root / '.gitignore'
        if not gitignore_path.exists():
            print("    ❌ .gitignore file not found")
            return False

        required_patterns = [
            '.env',
            '*.key',
            '*.pem'
        ]

        try:
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()

            missing_patterns = []
            for pattern in required_patterns:
                if pattern not in gitignore_content:
                    missing_patterns.append(pattern)

            if missing_patterns:
                print(f"    ❌ Missing .gitignore patterns: {missing_patterns}")
                return False

        except Exception as e:
            print(f"    Warning: Could not read .gitignore: {e}")
            return False

        return True

    def _check_file_permissions(self) -> bool:
        """Check file permissions for security."""
        print("  Checking file permissions...")

        # Check .env file permissions if it exists
        env_file = self.project_root / '.env'
        if env_file.exists():
            stat_info = env_file.stat()
            mode = stat_info.st_mode & 0o777

            # .env should not be world-readable
            if mode & 0o044:
                print(f"    ❌ .env file is world-readable (permissions: {oct(mode)})")
                print(f"       Run: chmod 600 .env")
                return False

        return True

    def _check_code_security(self) -> bool:
        """Check for security anti-patterns in staged code."""
        print("  Checking for security anti-patterns...")

        # Get staged Python files
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "*.py"],
                capture_output=True,
                text=True
            )
            staged_py_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return True

        dangerous_patterns = [
            (r'eval\s*\(', 'Use of eval() function'),
            (r'exec\s*\(', 'Use of exec() function'),
            (r'os\.system\s*\(', 'Use of os.system()'),
            (r'shell\s*=\s*True', 'Use of shell=True in subprocess'),
            (r'pickle\.load\s*\(', 'Use of pickle.load()'),
            (r'yaml\.load\s*\((?!.*safe_load)', 'Use of yaml.load() without safe_load'),
        ]

        violations_found = False

        for file_path in staged_py_files:
            if not file_path or not Path(file_path).exists():
                continue

            try:
                # Get staged content
                result = subprocess.run(
                    ["git", "show", f":{file_path}"],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    continue

                content = result.stdout
                lines = content.split('\n')

                for line_num, line in enumerate(lines, 1):
                    for pattern, message in dangerous_patterns:
                        if re.search(pattern, line):
                            print(f"    ⚠️  Security anti-pattern detected:")
                            print(f"       File: {file_path}:{line_num}")
                            print(f"       Issue: {message}")
                            print(f"       Line: {line.strip()}")
                            # Note: These are warnings, not blocking errors
                            # violations_found = True

            except Exception as e:
                print(f"    Warning: Could not check {file_path}: {e}")

        return True  # Don't block on anti-patterns, just warn

    def _validate_staged_files(self) -> bool:
        """Validate that no sensitive files are being committed."""
        print("  Validating staged files...")

        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True
            )
            staged_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return True

        # Files that should never be committed
        forbidden_files = [
            '.env',
            '.env.local',
            '.env.production',
            'config.json',
            '*.key',
            '*.pem',
            '*.p12',
            '*.pfx'
        ]

        blocked_files = []

        for file_path in staged_files:
            if not file_path:
                continue

            # Check against forbidden patterns
            for pattern in forbidden_files:
                if pattern.startswith('*'):
                    # Handle wildcard patterns
                    if file_path.endswith(pattern[1:]):
                        blocked_files.append(file_path)
                else:
                    # Handle exact matches
                    if file_path == pattern or file_path.endswith('/' + pattern):
                        blocked_files.append(file_path)

        if blocked_files:
            print(f"    ❌ COMMIT BLOCKED: Sensitive files detected:")
            for file_path in blocked_files:
                print(f"       {file_path}")
            print(f"    These files should not be committed to version control.")
            print(f"    Add them to .gitignore and remove from staging:")
            print(f"    git reset HEAD {' '.join(blocked_files)}")
            return False

        return True


def main():
    """Main entry point for pre-commit hook."""
    validator = PreCommitSecurityValidator()

    try:
        if validator.run_validation():
            print("🎉 Pre-commit security validation completed successfully")
            sys.exit(0)
        else:
            print("💥 Pre-commit security validation failed")
            print("\nTo bypass this check (NOT RECOMMENDED):")
            print("git commit --no-verify")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Pre-commit validation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Pre-commit validation error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()