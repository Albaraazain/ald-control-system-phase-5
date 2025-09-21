#!/usr/bin/env python3
"""
Architecture Testing Framework Test Runner

Comprehensive test runner for all architecture testing components.
Provides reporting, metrics collection, and test orchestration.
"""

import os
import sys
import pytest
import time
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class TestSuiteResult:
    """Results from a test suite execution"""
    suite_name: str
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    coverage_percent: Optional[float] = None


@dataclass
class ArchitectureTestReport:
    """Complete architecture test report"""
    timestamp: str
    total_duration: float
    overall_status: str
    test_suites: List[TestSuiteResult]
    summary: Dict[str, Any]


class ArchitectureTestRunner:
    """Comprehensive architecture test runner"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.test_root = self.project_root / "tests" / "architecture"
        self.results: List[TestSuiteResult] = []

    def run_dependency_injection_tests(self) -> TestSuiteResult:
        """Run dependency injection testing suite"""
        print("🧪 Running Dependency Injection Tests...")

        test_path = self.test_root / "dependency_injection"
        return self._run_pytest_suite("Dependency Injection", test_path)

    def run_compliance_tests(self) -> TestSuiteResult:
        """Run architectural compliance testing suite"""
        print("🏗️  Running Architectural Compliance Tests...")

        test_path = self.test_root / "compliance"
        return self._run_pytest_suite("Architectural Compliance", test_path)

    def run_integration_tests(self) -> TestSuiteResult:
        """Run component integration testing suite"""
        print("🔗 Running Component Integration Tests...")

        test_path = self.test_root / "integration"
        return self._run_pytest_suite("Component Integration", test_path)

    def run_performance_tests(self) -> TestSuiteResult:
        """Run performance impact testing suite"""
        print("⚡ Running Performance Impact Tests...")

        test_path = self.test_root / "performance"
        return self._run_pytest_suite("Performance Impact", test_path)

    def _run_pytest_suite(self, suite_name: str, test_path: Path) -> TestSuiteResult:
        """Run a pytest suite and collect results"""
        start_time = time.time()

        try:
            # Run pytest with JSON report
            cmd = [
                sys.executable, "-m", "pytest",
                str(test_path),
                "-v",
                "--tb=short",
                "--json-report",
                f"--json-report-file={test_path}/results.json"
            ]

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            duration = time.time() - start_time

            # Parse pytest results
            results_file = test_path / "results.json"
            if results_file.exists():
                with open(results_file, 'r') as f:
                    pytest_results = json.load(f)

                return TestSuiteResult(
                    suite_name=suite_name,
                    passed=pytest_results.get("summary", {}).get("passed", 0),
                    failed=pytest_results.get("summary", {}).get("failed", 0),
                    skipped=pytest_results.get("summary", {}).get("skipped", 0),
                    errors=pytest_results.get("summary", {}).get("error", 0),
                    duration=duration
                )
            else:
                # Fallback if JSON report not available
                return TestSuiteResult(
                    suite_name=suite_name,
                    passed=1 if result.returncode == 0 else 0,
                    failed=0 if result.returncode == 0 else 1,
                    skipped=0,
                    errors=0,
                    duration=duration
                )

        except Exception as e:
            print(f"Error running {suite_name} tests: {str(e)}")
            return TestSuiteResult(
                suite_name=suite_name,
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                duration=time.time() - start_time
            )

    def run_all_tests(self) -> ArchitectureTestReport:
        """Run all architecture test suites"""
        print("🚀 Starting Comprehensive Architecture Testing...")
        print("=" * 60)

        start_time = time.time()

        # Run all test suites
        test_suites = [
            self.run_dependency_injection_tests(),
            self.run_compliance_tests(),
            self.run_integration_tests(),
            self.run_performance_tests()
        ]

        total_duration = time.time() - start_time

        # Calculate summary
        total_passed = sum(suite.passed for suite in test_suites)
        total_failed = sum(suite.failed for suite in test_suites)
        total_skipped = sum(suite.skipped for suite in test_suites)
        total_errors = sum(suite.errors for suite in test_suites)

        overall_status = "PASSED" if total_failed == 0 and total_errors == 0 else "FAILED"

        summary = {
            "total_tests": total_passed + total_failed + total_skipped,
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
            "errors": total_errors,
            "success_rate": (total_passed / (total_passed + total_failed)) * 100 if (total_passed + total_failed) > 0 else 0
        }

        report = ArchitectureTestReport(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_duration=total_duration,
            overall_status=overall_status,
            test_suites=test_suites,
            summary=summary
        )

        self._print_report(report)
        self._save_report(report)

        return report

    def _print_report(self, report: ArchitectureTestReport):
        """Print test report to console"""
        print("\n" + "=" * 60)
        print("📊 ARCHITECTURE TESTING REPORT")
        print("=" * 60)
        print(f"Timestamp: {report.timestamp}")
        print(f"Total Duration: {report.total_duration:.2f} seconds")
        print(f"Overall Status: {report.overall_status}")
        print()

        # Suite-by-suite results
        print("📋 Test Suite Results:")
        print("-" * 60)
        for suite in report.test_suites:
            status_icon = "✅" if suite.failed == 0 and suite.errors == 0 else "❌"
            print(f"{status_icon} {suite.suite_name}")
            print(f"   Passed: {suite.passed}, Failed: {suite.failed}, Skipped: {suite.skipped}, Errors: {suite.errors}")
            print(f"   Duration: {suite.duration:.2f}s")
            print()

        # Summary
        print("📈 Summary:")
        print("-" * 30)
        print(f"Total Tests: {report.summary['total_tests']}")
        print(f"Passed: {report.summary['passed']}")
        print(f"Failed: {report.summary['failed']}")
        print(f"Skipped: {report.summary['skipped']}")
        print(f"Errors: {report.summary['errors']}")
        print(f"Success Rate: {report.summary['success_rate']:.1f}%")

        if report.overall_status == "PASSED":
            print("\n🎉 All architecture tests PASSED!")
        else:
            print("\n⚠️  Some architecture tests FAILED!")

        print("=" * 60)

    def _save_report(self, report: ArchitectureTestReport):
        """Save test report to file"""
        report_file = self.project_root / "architecture_test_report.json"

        try:
            with open(report_file, 'w') as f:
                json.dump(asdict(report), f, indent=2)
            print(f"📄 Report saved to: {report_file}")
        except Exception as e:
            print(f"Failed to save report: {str(e)}")

    def run_specific_test(self, test_pattern: str) -> None:
        """Run specific test matching pattern"""
        print(f"🎯 Running specific test: {test_pattern}")

        cmd = [
            sys.executable, "-m", "pytest",
            str(self.test_root),
            "-v",
            "-k", test_pattern
        ]

        subprocess.run(cmd, cwd=self.project_root)

    def install_test_dependencies(self) -> bool:
        """Install required test dependencies"""
        print("📦 Installing test dependencies...")

        dependencies = [
            "pytest",
            "pytest-asyncio",
            "pytest-json-report",
            "pytest-cov",
            "memory-profiler",
            "psutil"
        ]

        try:
            for dep in dependencies:
                cmd = [sys.executable, "-m", "pip", "install", dep]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    print(f"Failed to install {dep}: {result.stderr}")
                    return False

            print("✅ All test dependencies installed successfully")
            return True

        except Exception as e:
            print(f"Error installing dependencies: {str(e)}")
            return False

    def validate_test_environment(self) -> bool:
        """Validate test environment setup"""
        print("🔍 Validating test environment...")

        issues = []

        # Check Python version
        if sys.version_info < (3, 8):
            issues.append("Python 3.8+ required for architecture testing")

        # Check test directory structure
        required_dirs = [
            self.test_root / "dependency_injection",
            self.test_root / "compliance",
            self.test_root / "integration",
            self.test_root / "performance"
        ]

        for test_dir in required_dirs:
            if not test_dir.exists():
                issues.append(f"Missing test directory: {test_dir}")

        # Check required test files
        required_files = [
            self.test_root / "dependency_injection" / "test_container.py",
            self.test_root / "compliance" / "test_clean_architecture.py",
            self.test_root / "integration" / "test_dual_mode_logging.py",
            self.test_root / "performance" / "test_dependency_injection_performance.py"
        ]

        for test_file in required_files:
            if not test_file.exists():
                issues.append(f"Missing test file: {test_file}")

        if issues:
            print("❌ Test environment validation failed:")
            for issue in issues:
                print(f"   - {issue}")
            return False

        print("✅ Test environment validation passed")
        return True


def main():
    """Main entry point for architecture test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Architecture Testing Framework")
    parser.add_argument("--suite", choices=["di", "compliance", "integration", "performance"],
                       help="Run specific test suite")
    parser.add_argument("--test", help="Run specific test matching pattern")
    parser.add_argument("--install-deps", action="store_true", help="Install test dependencies")
    parser.add_argument("--validate", action="store_true", help="Validate test environment")
    parser.add_argument("--project-root", default=".", help="Project root directory")

    args = parser.parse_args()

    # Get project root
    project_root = os.path.abspath(args.project_root)
    runner = ArchitectureTestRunner(project_root)

    # Install dependencies if requested
    if args.install_deps:
        if not runner.install_test_dependencies():
            sys.exit(1)
        return

    # Validate environment if requested
    if args.validate:
        if not runner.validate_test_environment():
            sys.exit(1)
        return

    # Validate environment before running tests
    if not runner.validate_test_environment():
        print("❌ Test environment validation failed. Run with --install-deps first.")
        sys.exit(1)

    # Run specific test
    if args.test:
        runner.run_specific_test(args.test)
        return

    # Run specific suite
    if args.suite:
        if args.suite == "di":
            result = runner.run_dependency_injection_tests()
        elif args.suite == "compliance":
            result = runner.run_compliance_tests()
        elif args.suite == "integration":
            result = runner.run_integration_tests()
        elif args.suite == "performance":
            result = runner.run_performance_tests()

        if result.failed > 0 or result.errors > 0:
            sys.exit(1)
        return

    # Run all tests
    report = runner.run_all_tests()
    if report.overall_status != "PASSED":
        sys.exit(1)


if __name__ == "__main__":
    main()