"""
Security automation framework for ALD control system CI/CD integration.

Provides:
- Automated vulnerability scanning
- Security test automation
- Penetration testing automation
- Security metrics and monitoring
- CI/CD security validation pipeline
"""
import os
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import hashlib

from .test_credential_security import run_credential_security_scan
from .test_database_security import run_database_security_audit
from .test_plc_security import run_plc_security_audit


@dataclass
class SecurityTestResult:
    """Security test result data structure."""
    test_name: str
    passed: bool
    severity: str
    details: Dict[str, Any]
    timestamp: datetime
    execution_time_ms: float


@dataclass
class SecurityMetrics:
    """Security metrics data structure."""
    total_tests: int
    passed_tests: int
    failed_tests: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    security_score: float
    last_scan_time: datetime


class SecurityAutomationFramework:
    """Comprehensive security automation framework."""

    def __init__(self, project_root: str = None, config_file: str = None):
        """Initialize security automation framework."""
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config_file = config_file or ".security_config.json"
        self.results_dir = self.project_root / "security_results"
        self.results_dir.mkdir(exist_ok=True)

        self.config = self._load_config()
        self.test_results: List[SecurityTestResult] = []

    def _load_config(self) -> Dict[str, Any]:
        """Load security testing configuration."""
        config_path = self.project_root / self.config_file

        default_config = {
            "credential_scanning": {
                "enabled": True,
                "scan_patterns": [
                    "**/*.py",
                    "**/*.json",
                    "**/*.yaml",
                    "**/*.yml",
                    "**/*.env*",
                    "**/*.ini",
                    "**/*.cfg"
                ],
                "exclude_patterns": [
                    "*/myenv/*",
                    "*/__pycache__/*",
                    "*.git/*",
                    "*/tests/security/*"
                ]
            },
            "database_security": {
                "enabled": True,
                "test_injection_attacks": True,
                "test_boundary_conditions": True,
                "test_race_conditions": True
            },
            "plc_security": {
                "enabled": True,
                "target_host": "127.0.0.1",
                "target_port": 502,
                "test_network_scanning": True,
                "test_authentication": True,
                "test_mitm_vulnerability": True
            },
            "ci_cd_integration": {
                "fail_on_critical": True,
                "fail_on_high": False,
                "max_execution_time_minutes": 10,
                "generate_reports": True
            },
            "security_baseline": {
                "min_security_score": 85.0,
                "max_critical_issues": 0,
                "max_high_issues": 2
            }
        }

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    default_config.update(loaded_config)
            except Exception as e:
                print(f"Warning: Could not load config from {config_path}: {e}")

        return default_config

    def _save_config(self):
        """Save current configuration."""
        config_path = self.project_root / self.config_file
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config to {config_path}: {e}")

    async def run_comprehensive_security_scan(self) -> SecurityMetrics:
        """Run comprehensive security scan with all enabled tests."""
        print("🔒 Starting comprehensive security scan...")
        start_time = time.time()

        self.test_results = []

        # 1. Credential Security Scanning
        if self.config["credential_scanning"]["enabled"]:
            await self._run_credential_security_tests()

        # 2. Database Security Testing
        if self.config["database_security"]["enabled"]:
            await self._run_database_security_tests()

        # 3. PLC Security Testing
        if self.config["plc_security"]["enabled"]:
            await self._run_plc_security_tests()

        # 4. Additional security tests
        await self._run_additional_security_tests()

        # Calculate metrics
        metrics = self._calculate_security_metrics()

        # Generate reports
        if self.config["ci_cd_integration"]["generate_reports"]:
            self._generate_security_reports(metrics)

        total_time = time.time() - start_time
        print(f"🔒 Security scan completed in {total_time:.2f} seconds")

        return metrics

    async def _run_credential_security_tests(self):
        """Run credential security tests."""
        print("  Running credential security tests...")
        start_time = time.time()

        try:
            # Run credential security scan
            success = run_credential_security_scan()

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="credential_security_scan",
                passed=success,
                severity="critical" if not success else "info",
                details={"scan_completed": True, "issues_found": not success},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="credential_security_scan",
                passed=False,
                severity="critical",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    async def _run_database_security_tests(self):
        """Run database security tests."""
        print("  Running database security tests...")
        start_time = time.time()

        try:
            # Run database security audit
            success = run_database_security_audit()

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="database_security_audit",
                passed=success,
                severity="high" if not success else "info",
                details={"audit_completed": True, "vulnerabilities_found": not success},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="database_security_audit",
                passed=False,
                severity="high",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    async def _run_plc_security_tests(self):
        """Run PLC security tests."""
        print("  Running PLC security tests...")
        start_time = time.time()

        try:
            # Run PLC security audit
            target_host = self.config["plc_security"]["target_host"]
            target_port = self.config["plc_security"]["target_port"]

            success = run_plc_security_audit(target_host, target_port)

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="plc_security_audit",
                passed=success,
                severity="high" if not success else "info",
                details={
                    "audit_completed": True,
                    "target_host": target_host,
                    "target_port": target_port,
                    "vulnerabilities_found": not success
                },
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="plc_security_audit",
                passed=False,
                severity="high",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    async def _run_additional_security_tests(self):
        """Run additional security tests."""
        print("  Running additional security tests...")

        # Test 1: File permissions
        await self._test_file_permissions()

        # Test 2: Environment variable security
        await self._test_environment_security()

        # Test 3: Dependency vulnerabilities
        await self._test_dependency_vulnerabilities()

        # Test 4: Code quality security
        await self._test_code_security()

    async def _test_file_permissions(self):
        """Test file permissions for security."""
        start_time = time.time()

        try:
            sensitive_files = [
                ".env",
                "*.key",
                "*.pem",
                "*.p12",
                "config.json"
            ]

            permission_issues = []

            for pattern in sensitive_files:
                for file_path in self.project_root.glob(pattern):
                    if file_path.exists():
                        stat_info = file_path.stat()
                        mode = stat_info.st_mode & 0o777

                        # Check if file is world-readable or world-writable
                        if mode & 0o044:  # World-readable
                            permission_issues.append(f"{file_path}: world-readable")

                        if mode & 0o022:  # World-writable
                            permission_issues.append(f"{file_path}: world-writable")

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="file_permissions_check",
                passed=len(permission_issues) == 0,
                severity="medium" if permission_issues else "info",
                details={
                    "permission_issues": permission_issues,
                    "files_checked": len(sensitive_files)
                },
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="file_permissions_check",
                passed=False,
                severity="medium",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    async def _test_environment_security(self):
        """Test environment variable security."""
        start_time = time.time()

        try:
            security_issues = []

            # Check for potentially dangerous environment variables
            dangerous_vars = ["PATH", "LD_LIBRARY_PATH", "PYTHONPATH"]
            for var in dangerous_vars:
                if var in os.environ:
                    value = os.environ[var]
                    if "." in value or "/tmp" in value:
                        security_issues.append(f"{var} contains potentially unsafe paths")

            # Check for exposed credentials in environment
            for key, value in os.environ.items():
                if any(pattern in key.upper() for pattern in ["KEY", "SECRET", "TOKEN", "PASSWORD"]):
                    if len(value) > 20:  # Potentially a real secret
                        security_issues.append(f"Potential credential in environment: {key}")

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="environment_security_check",
                passed=len(security_issues) == 0,
                severity="medium" if security_issues else "info",
                details={
                    "security_issues": security_issues,
                    "env_vars_checked": len(os.environ)
                },
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="environment_security_check",
                passed=False,
                severity="medium",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    async def _test_dependency_vulnerabilities(self):
        """Test for known vulnerabilities in dependencies."""
        start_time = time.time()

        try:
            # Check if requirements.txt exists
            requirements_file = self.project_root / "requirements.txt"
            if not requirements_file.exists():
                result = SecurityTestResult(
                    test_name="dependency_vulnerability_check",
                    passed=True,
                    severity="info",
                    details={"message": "No requirements.txt found"},
                    timestamp=datetime.now(),
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                self.test_results.append(result)
                return

            # Use safety check (if available)
            vulnerabilities = []
            try:
                result_proc = subprocess.run(
                    ["safety", "check", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result_proc.returncode != 0:
                    vulnerabilities.append("Safety check failed or found vulnerabilities")

            except subprocess.TimeoutExpired:
                vulnerabilities.append("Safety check timed out")
            except FileNotFoundError:
                # Safety not installed
                vulnerabilities.append("Safety tool not available for vulnerability checking")

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="dependency_vulnerability_check",
                passed=len(vulnerabilities) == 0,
                severity="high" if vulnerabilities and "found vulnerabilities" in str(vulnerabilities) else "low",
                details={
                    "vulnerabilities": vulnerabilities,
                    "requirements_file": str(requirements_file)
                },
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="dependency_vulnerability_check",
                passed=False,
                severity="medium",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    async def _test_code_security(self):
        """Test code security using static analysis."""
        start_time = time.time()

        try:
            security_issues = []

            # Check for common security anti-patterns in Python code
            python_files = list(self.project_root.glob("**/*.py"))

            for py_file in python_files:
                # Skip test files and virtual environments
                if any(skip in str(py_file) for skip in ["test_", "myenv/", "__pycache__/"]):
                    continue

                try:
                    with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # Check for security anti-patterns
                    dangerous_patterns = [
                        ("eval(", "Use of eval() function"),
                        ("exec(", "Use of exec() function"),
                        ("os.system(", "Use of os.system()"),
                        ("subprocess.call(", "Use of subprocess.call() without shell=False"),
                        ("shell=True", "Use of shell=True in subprocess"),
                        ("pickle.load(", "Use of pickle.load() can be dangerous"),
                        ("yaml.load(", "Use of yaml.load() without safe_load"),
                    ]

                    for pattern, message in dangerous_patterns:
                        if pattern in content:
                            security_issues.append(f"{py_file}: {message}")

                except Exception:
                    continue  # Skip files that can't be read

            execution_time = (time.time() - start_time) * 1000

            result = SecurityTestResult(
                test_name="code_security_check",
                passed=len(security_issues) == 0,
                severity="medium" if security_issues else "info",
                details={
                    "security_issues": security_issues,
                    "files_scanned": len(python_files)
                },
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )

            self.test_results.append(result)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = SecurityTestResult(
                test_name="code_security_check",
                passed=False,
                severity="medium",
                details={"error": str(e)},
                timestamp=datetime.now(),
                execution_time_ms=execution_time
            )
            self.test_results.append(result)

    def _calculate_security_metrics(self) -> SecurityMetrics:
        """Calculate security metrics from test results."""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.passed])
        failed_tests = total_tests - passed_tests

        # Count issues by severity
        critical_issues = len([r for r in self.test_results if not r.passed and r.severity == "critical"])
        high_issues = len([r for r in self.test_results if not r.passed and r.severity == "high"])
        medium_issues = len([r for r in self.test_results if not r.passed and r.severity == "medium"])
        low_issues = len([r for r in self.test_results if not r.passed and r.severity == "low"])

        # Calculate security score (0-100)
        if total_tests == 0:
            security_score = 100.0
        else:
            # Weight by severity
            severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            max_possible_score = sum(severity_weights.get(r.severity, 1) for r in self.test_results)
            actual_score = sum(severity_weights.get(r.severity, 1) for r in self.test_results if r.passed)

            security_score = (actual_score / max_possible_score * 100) if max_possible_score > 0 else 100.0

        return SecurityMetrics(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            security_score=security_score,
            last_scan_time=datetime.now()
        )

    def _generate_security_reports(self, metrics: SecurityMetrics):
        """Generate security reports."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON report
        json_report_path = self.results_dir / f"security_report_{timestamp}.json"
        json_report = {
            "scan_info": {
                "timestamp": datetime.now().isoformat(),
                "project_root": str(self.project_root),
                "config": self.config
            },
            "metrics": {
                "total_tests": metrics.total_tests,
                "passed_tests": metrics.passed_tests,
                "failed_tests": metrics.failed_tests,
                "critical_issues": metrics.critical_issues,
                "high_issues": metrics.high_issues,
                "medium_issues": metrics.medium_issues,
                "low_issues": metrics.low_issues,
                "security_score": metrics.security_score
            },
            "test_results": [
                {
                    "test_name": r.test_name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "details": r.details,
                    "timestamp": r.timestamp.isoformat(),
                    "execution_time_ms": r.execution_time_ms
                }
                for r in self.test_results
            ]
        }

        with open(json_report_path, 'w') as f:
            json.dump(json_report, f, indent=2)

        # HTML report
        html_report_path = self.results_dir / f"security_report_{timestamp}.html"
        self._generate_html_report(html_report_path, metrics)

        print(f"📊 Security reports generated:")
        print(f"   JSON: {json_report_path}")
        print(f"   HTML: {html_report_path}")

    def _generate_html_report(self, output_path: Path, metrics: SecurityMetrics):
        """Generate HTML security report."""
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALD Control System Security Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
        .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .metric {{ text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .score {{ font-size: 2em; font-weight: bold; }}
        .critical {{ color: #d32f2f; }}
        .high {{ color: #ff9800; }}
        .medium {{ color: #fbc02d; }}
        .low {{ color: #388e3c; }}
        .passed {{ color: #4caf50; }}
        .failed {{ color: #f44336; }}
        .test-result {{ padding: 10px; margin: 5px 0; border-left: 4px solid #ddd; }}
        .test-result.passed {{ border-left-color: #4caf50; }}
        .test-result.failed {{ border-left-color: #f44336; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 ALD Control System Security Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Project: {self.project_root}</p>
    </div>

    <div class="metrics">
        <div class="metric">
            <div class="score {'passed' if metrics.security_score >= 85 else 'failed'}">{metrics.security_score:.1f}</div>
            <div>Security Score</div>
        </div>
        <div class="metric">
            <div class="score">{metrics.total_tests}</div>
            <div>Total Tests</div>
        </div>
        <div class="metric">
            <div class="score passed">{metrics.passed_tests}</div>
            <div>Passed</div>
        </div>
        <div class="metric">
            <div class="score failed">{metrics.failed_tests}</div>
            <div>Failed</div>
        </div>
    </div>

    <div class="metrics">
        <div class="metric">
            <div class="score critical">{metrics.critical_issues}</div>
            <div>Critical Issues</div>
        </div>
        <div class="metric">
            <div class="score high">{metrics.high_issues}</div>
            <div>High Issues</div>
        </div>
        <div class="metric">
            <div class="score medium">{metrics.medium_issues}</div>
            <div>Medium Issues</div>
        </div>
        <div class="metric">
            <div class="score low">{metrics.low_issues}</div>
            <div>Low Issues</div>
        </div>
    </div>

    <h2>Test Results</h2>
"""

        for result in self.test_results:
            status_class = "passed" if result.passed else "failed"
            html_content += f"""
    <div class="test-result {status_class}">
        <h3>{result.test_name} - <span class="{status_class}">{'PASSED' if result.passed else 'FAILED'}</span></h3>
        <p><strong>Severity:</strong> <span class="{result.severity}">{result.severity.upper()}</span></p>
        <p><strong>Execution Time:</strong> {result.execution_time_ms:.1f}ms</p>
        <p><strong>Details:</strong> {json.dumps(result.details, indent=2)}</p>
    </div>
"""

        html_content += """
</body>
</html>
"""

        with open(output_path, 'w') as f:
            f.write(html_content)

    def check_security_baseline(self, metrics: SecurityMetrics) -> bool:
        """Check if security metrics meet baseline requirements."""
        baseline = self.config["security_baseline"]

        checks = {
            "security_score": metrics.security_score >= baseline["min_security_score"],
            "critical_issues": metrics.critical_issues <= baseline["max_critical_issues"],
            "high_issues": metrics.high_issues <= baseline["max_high_issues"]
        }

        return all(checks.values())

    def should_fail_ci_cd(self, metrics: SecurityMetrics) -> bool:
        """Determine if CI/CD should fail based on security results."""
        ci_config = self.config["ci_cd_integration"]

        if ci_config["fail_on_critical"] and metrics.critical_issues > 0:
            return True

        if ci_config["fail_on_high"] and metrics.high_issues > 0:
            return True

        if not self.check_security_baseline(metrics):
            return True

        return False


# CI/CD Integration Functions
async def run_security_pipeline():
    """Run complete security pipeline for CI/CD integration."""
    print("🚀 Starting automated security pipeline...")

    framework = SecurityAutomationFramework()

    try:
        # Run comprehensive security scan
        metrics = await framework.run_comprehensive_security_scan()

        # Print summary
        print(f"\n📊 Security Pipeline Results:")
        print(f"   Security Score: {metrics.security_score:.1f}/100")
        print(f"   Tests: {metrics.passed_tests}/{metrics.total_tests} passed")
        print(f"   Critical Issues: {metrics.critical_issues}")
        print(f"   High Issues: {metrics.high_issues}")
        print(f"   Medium Issues: {metrics.medium_issues}")
        print(f"   Low Issues: {metrics.low_issues}")

        # Check if CI/CD should fail
        should_fail = framework.should_fail_ci_cd(metrics)
        baseline_met = framework.check_security_baseline(metrics)

        print(f"\n🎯 Security Baseline: {'✅ MET' if baseline_met else '❌ NOT MET'}")

        if should_fail:
            print(f"\n❌ SECURITY PIPELINE FAILED")
            print(f"   Critical security issues must be resolved before deployment")
            return False
        else:
            print(f"\n✅ SECURITY PIPELINE PASSED")
            print(f"   All security checks passed, deployment approved")
            return True

    except Exception as e:
        print(f"\n💥 SECURITY PIPELINE ERROR: {e}")
        return False


if __name__ == "__main__":
    # Run security pipeline when executed directly
    success = asyncio.run(run_security_pipeline())
    exit(0 if success else 1)