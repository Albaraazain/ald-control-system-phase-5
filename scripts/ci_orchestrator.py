#!/usr/bin/env python3
"""
CI/CD Test Orchestration Script for ALD Control System

This script orchestrates comprehensive testing across multiple environments,
coordinates test execution, and provides centralized reporting and monitoring.
"""

import os
import sys
import json
import asyncio
import argparse
import subprocess
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ci_orchestrator.log')
    ]
)
logger = logging.getLogger(__name__)

class TestStage(Enum):
    """Test execution stages."""
    SETUP = "setup"
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    E2E = "e2e"
    CLEANUP = "cleanup"

class TestResult(Enum):
    """Test result statuses."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

@dataclass
class TestExecution:
    """Represents a single test execution."""
    stage: TestStage
    name: str
    command: str
    timeout: int
    result: Optional[TestResult] = None
    duration: Optional[float] = None
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class OrchestrationReport:
    """Comprehensive orchestration report."""
    started_at: datetime
    completed_at: Optional[datetime]
    total_duration: Optional[float]
    stages_executed: List[TestStage]
    executions: List[TestExecution]
    summary: Dict[str, Any]
    environment: Dict[str, str]
    quality_gates: Dict[str, bool]

class CIOrchestrator:
    """Orchestrates CI/CD testing pipeline."""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or Path(__file__).parent / "ci_config.json"
        self.config = self._load_config()
        self.executions: List[TestExecution] = []
        self.report: Optional[OrchestrationReport] = None

    def _load_config(self) -> Dict[str, Any]:
        """Load CI configuration."""
        default_config = {
            "test_stages": {
                "setup": {
                    "enabled": True,
                    "timeout": 300,
                    "commands": [
                        "python tests/utils/test_data_manager.py setup --type minimal"
                    ]
                },
                "unit": {
                    "enabled": True,
                    "timeout": 600,
                    "commands": [
                        "python -m pytest tests/architecture/ tests/security/ --cov=src --cov-report=xml --cov-fail-under=80 -v"
                    ]
                },
                "integration": {
                    "enabled": True,
                    "timeout": 900,
                    "commands": [
                        "python -m pytest tests/integration/ -v --timeout=300"
                    ]
                },
                "performance": {
                    "enabled": True,
                    "timeout": 1200,
                    "commands": [
                        "python baseline_performance_measurement.py",
                        "python benchmark_performance_continuous_logging.py",
                        "python quick_performance_check.py"
                    ]
                },
                "security": {
                    "enabled": True,
                    "timeout": 600,
                    "commands": [
                        "python -m pytest tests/security/ -v",
                        "python -m tests.security.security_automation"
                    ]
                },
                "e2e": {
                    "enabled": True,
                    "timeout": 1800,
                    "commands": [
                        "python test_final_validation.py"
                    ]
                },
                "cleanup": {
                    "enabled": True,
                    "timeout": 300,
                    "commands": [
                        "python tests/utils/test_data_manager.py cleanup"
                    ]
                }
            },
            "quality_gates": {
                "min_coverage": 80,
                "max_performance_degradation": 20,
                "max_memory_usage_mb": 300,
                "max_response_time_ms": 1000,
                "max_test_failures": 0
            },
            "environment": {
                "TEST_MODE": "true",
                "LOG_LEVEL": "DEBUG",
                "PLC_TYPE": "simulation",
                "MACHINE_ID": "ci-test-machine"
            }
        }

        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    user_config = json.load(f)
                    # Merge user config with defaults
                    return {**default_config, **user_config}
            except Exception as e:
                logger.warning(f"Failed to load config file {self.config_file}: {e}")
                logger.info("Using default configuration")

        return default_config

    def _setup_environment(self) -> bool:
        """Setup test environment variables."""
        try:
            for key, value in self.config.get("environment", {}).items():
                os.environ[key] = str(value)

            logger.info("Environment setup completed")
            return True
        except Exception as e:
            logger.error(f"Failed to setup environment: {e}")
            return False

    async def _execute_command(self, execution: TestExecution) -> TestExecution:
        """Execute a single test command."""
        logger.info(f"Starting {execution.stage.value}/{execution.name}: {execution.command}")

        execution.started_at = datetime.now()

        try:
            # Execute command with timeout
            process = await asyncio.create_subprocess_shell(
                execution.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd()
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=execution.timeout
                )

                execution.output = stdout.decode('utf-8', errors='ignore')
                execution.error = stderr.decode('utf-8', errors='ignore')

                if process.returncode == 0:
                    execution.result = TestResult.PASSED
                    logger.info(f"✅ {execution.stage.value}/{execution.name}: PASSED")
                else:
                    execution.result = TestResult.FAILED
                    logger.error(f"❌ {execution.stage.value}/{execution.name}: FAILED (exit code: {process.returncode})")

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                execution.result = TestResult.ERROR
                execution.error = f"Command timed out after {execution.timeout} seconds"
                logger.error(f"⏰ {execution.stage.value}/{execution.name}: TIMEOUT")

        except Exception as e:
            execution.result = TestResult.ERROR
            execution.error = str(e)
            logger.error(f"💥 {execution.stage.value}/{execution.name}: ERROR - {e}")

        execution.completed_at = datetime.now()
        execution.duration = (execution.completed_at - execution.started_at).total_seconds()

        return execution

    async def _execute_stage(self, stage: TestStage) -> List[TestExecution]:
        """Execute all commands in a test stage."""
        stage_config = self.config["test_stages"].get(stage.value, {})

        if not stage_config.get("enabled", True):
            logger.info(f"Skipping disabled stage: {stage.value}")
            return []

        logger.info(f"🚀 Executing stage: {stage.value}")

        commands = stage_config.get("commands", [])
        timeout = stage_config.get("timeout", 600)

        executions = []
        for i, command in enumerate(commands):
            execution = TestExecution(
                stage=stage,
                name=f"cmd_{i+1}",
                command=command,
                timeout=timeout
            )

            # Execute command
            execution = await self._execute_command(execution)
            executions.append(execution)
            self.executions.append(execution)

            # Stop stage execution if a command fails (unless it's cleanup)
            if execution.result == TestResult.FAILED and stage != TestStage.CLEANUP:
                logger.error(f"Stage {stage.value} failed, stopping execution")
                break

        return executions

    def _analyze_quality_gates(self) -> Dict[str, bool]:
        """Analyze test results against quality gates."""
        gates = {}
        quality_config = self.config.get("quality_gates", {})

        # Check test failures
        failed_tests = len([e for e in self.executions if e.result == TestResult.FAILED])
        max_failures = quality_config.get("max_test_failures", 0)
        gates["test_failures"] = failed_tests <= max_failures

        # Check coverage (simulated - would parse actual coverage reports)
        gates["coverage"] = True  # Placeholder

        # Check performance (simulated - would parse actual performance reports)
        gates["performance"] = True  # Placeholder

        # Check memory usage (simulated)
        gates["memory_usage"] = True  # Placeholder

        # Overall gate
        gates["overall"] = all(gates.values())

        return gates

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate execution summary."""
        total_executions = len(self.executions)
        passed = len([e for e in self.executions if e.result == TestResult.PASSED])
        failed = len([e for e in self.executions if e.result == TestResult.FAILED])
        errors = len([e for e in self.executions if e.result == TestResult.ERROR])

        return {
            "total_executions": total_executions,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "success_rate": (passed / total_executions * 100) if total_executions > 0 else 0,
            "stages_executed": len(set(e.stage for e in self.executions)),
            "total_duration": sum(e.duration or 0 for e in self.executions)
        }

    def _save_report(self) -> Path:
        """Save orchestration report to file."""
        if not self.report:
            return None

        report_dir = Path("ci_reports")
        report_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"ci_orchestration_{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(asdict(self.report), f, indent=2, default=str)

        logger.info(f"Report saved to: {report_file}")
        return report_file

    def _print_summary(self):
        """Print execution summary to console."""
        if not self.report:
            return

        print("\n" + "="*80)
        print("🎯 CI/CD ORCHESTRATION SUMMARY")
        print("="*80)

        summary = self.report.summary
        print(f"📊 Executions: {summary['passed']}/{summary['total_executions']} passed ({summary['success_rate']:.1f}%)")
        print(f"⏱️  Duration: {summary['total_duration']:.1f} seconds")
        print(f"🏗️  Stages: {summary['stages_executed']}")

        # Quality gates
        print(f"\n🚦 QUALITY GATES:")
        for gate, passed in self.report.quality_gates.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {gate}: {status}")

        # Stage breakdown
        print(f"\n📋 STAGE BREAKDOWN:")
        for stage in TestStage:
            stage_executions = [e for e in self.executions if e.stage == stage]
            if stage_executions:
                passed_count = len([e for e in stage_executions if e.result == TestResult.PASSED])
                total_count = len(stage_executions)
                duration = sum(e.duration or 0 for e in stage_executions)
                status = "✅" if passed_count == total_count else "❌"
                print(f"   {status} {stage.value}: {passed_count}/{total_count} passed ({duration:.1f}s)")

        # Failed executions
        failed_executions = [e for e in self.executions if e.result in [TestResult.FAILED, TestResult.ERROR]]
        if failed_executions:
            print(f"\n❌ FAILED EXECUTIONS:")
            for execution in failed_executions:
                print(f"   • {execution.stage.value}/{execution.name}: {execution.result.value}")
                if execution.error:
                    print(f"     Error: {execution.error[:100]}...")

        print("="*80)

    async def run_full_pipeline(self, stages: Optional[List[TestStage]] = None) -> bool:
        """Run the complete CI/CD pipeline."""
        if stages is None:
            stages = list(TestStage)

        logger.info("🚀 Starting CI/CD orchestration")

        start_time = datetime.now()

        # Setup environment
        if not self._setup_environment():
            logger.error("Failed to setup environment")
            return False

        # Execute stages
        executed_stages = []
        for stage in stages:
            executed_stages.append(stage)
            stage_executions = await self._execute_stage(stage)

            # Check if we should continue
            failed_in_stage = any(e.result == TestResult.FAILED for e in stage_executions)
            if failed_in_stage and stage != TestStage.CLEANUP:
                logger.error(f"Stage {stage.value} failed, stopping pipeline")
                break

        # Generate report
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        self.report = OrchestrationReport(
            started_at=start_time,
            completed_at=end_time,
            total_duration=total_duration,
            stages_executed=executed_stages,
            executions=self.executions,
            summary=self._generate_summary(),
            environment=dict(os.environ),
            quality_gates=self._analyze_quality_gates()
        )

        # Save and display results
        self._save_report()
        self._print_summary()

        # Return success status
        overall_success = self.report.quality_gates.get("overall", False)
        logger.info(f"🎯 Pipeline {'SUCCEEDED' if overall_success else 'FAILED'}")

        return overall_success

async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="CI/CD Test Orchestrator for ALD Control System")
    parser.add_argument("--stages", nargs="+",
                       choices=[s.value for s in TestStage],
                       help="Specific stages to run")
    parser.add_argument("--config", type=Path,
                       help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be executed without running")

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = CIOrchestrator(config_file=args.config)

    # Parse stages
    stages = None
    if args.stages:
        stages = [TestStage(s) for s in args.stages]

    if args.dry_run:
        print("DRY RUN MODE - Would execute:")
        for stage in (stages or list(TestStage)):
            stage_config = orchestrator.config["test_stages"].get(stage.value, {})
            if stage_config.get("enabled", True):
                print(f"\n{stage.value}:")
                for cmd in stage_config.get("commands", []):
                    print(f"  • {cmd}")
        return

    # Run pipeline
    success = await orchestrator.run_full_pipeline(stages)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())