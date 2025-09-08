#!/usr/bin/env python3
"""
Execute Comprehensive Validation
Master execution script for complete ALD control system validation
"""

import asyncio
import logging
import sys
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_environment_setup import test_env
from comprehensive_test_suite import test_suite
from performance_load_testing import performance_tester
from schema_migration_validator import migration_validator
from master_test_report_generator import report_generator
from log_setup import setup_logger

class ComprehensiveValidationExecutor:
    """Master executor for complete system validation"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.execution_start_time = datetime.now()
        self.execution_results = {}
        self.validation_successful = False
        
    async def execute_comprehensive_validation(self) -> Dict[str, Any]:
        """Execute complete validation suite"""
        self.logger.info("🚀 Starting Comprehensive ALD Control System Validation...")
        
        print("\n" + "="*80)
        print("🧪 ALD CONTROL SYSTEM - COMPREHENSIVE VALIDATION SUITE")
        print("="*80)
        print(f"Start Time: {self.execution_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Execution ID: {test_env.test_session_id}")
        print("="*80 + "\n")
        
        try:
            # Phase 1: Environment Setup and Initialization
            print("📋 PHASE 1: ENVIRONMENT SETUP AND INITIALIZATION")
            print("-" * 50)
            
            setup_result = await self._phase_1_setup()
            self.execution_results["phase_1_setup"] = setup_result
            
            if not setup_result["success"]:
                self.logger.error("❌ Phase 1 failed - aborting validation")
                return await self._generate_failure_report("Environment setup failed")
            
            print("✅ Phase 1 completed successfully\n")
            
            # Phase 2: Schema Migration Validation
            print("📋 PHASE 2: SCHEMA MIGRATION VALIDATION")
            print("-" * 50)
            
            migration_result = await self._phase_2_migration_validation()
            self.execution_results["phase_2_migration"] = migration_result
            
            if not migration_result["success"]:
                self.logger.warning("⚠️ Phase 2 has critical issues - continuing with caution")
            
            print("✅ Phase 2 completed\n")
            
            # Phase 3: Comprehensive Test Suite
            print("📋 PHASE 3: COMPREHENSIVE TEST SUITE")
            print("-" * 50)
            
            comprehensive_result = await self._phase_3_comprehensive_tests()
            self.execution_results["phase_3_comprehensive"] = comprehensive_result
            
            if not comprehensive_result["success"]:
                self.logger.warning("⚠️ Phase 3 has test failures - continuing")
            
            print("✅ Phase 3 completed\n")
            
            # Phase 4: Performance and Load Testing
            print("📋 PHASE 4: PERFORMANCE AND LOAD TESTING")
            print("-" * 50)
            
            performance_result = await self._phase_4_performance_testing()
            self.execution_results["phase_4_performance"] = performance_result
            
            if not performance_result["success"]:
                self.logger.warning("⚠️ Phase 4 has performance issues - continuing")
            
            print("✅ Phase 4 completed\n")
            
            # Phase 5: Master Report Generation
            print("📋 PHASE 5: MASTER REPORT GENERATION")
            print("-" * 50)
            
            report_result = await self._phase_5_report_generation()
            self.execution_results["phase_5_reporting"] = report_result
            
            if not report_result["success"]:
                self.logger.error("⚠️ Phase 5 report generation issues")
            
            print("✅ Phase 5 completed\n")
            
            # Phase 6: Final Assessment and Recommendations
            print("📋 PHASE 6: FINAL ASSESSMENT")
            print("-" * 50)
            
            final_assessment = await self._phase_6_final_assessment()
            self.execution_results["phase_6_assessment"] = final_assessment
            
            print("✅ Phase 6 completed\n")
            
            # Generate execution summary
            execution_summary = await self._generate_execution_summary()
            
            # Print final results
            await self._print_final_results(execution_summary)
            
            return execution_summary
            
        except Exception as e:
            self.logger.error(f"❌ Critical error during validation execution: {e}")
            return await self._generate_failure_report(f"Critical execution error: {str(e)}")
        
        finally:
            # Cleanup
            await self._cleanup()
    
    async def _phase_1_setup(self) -> Dict[str, Any]:
        """Phase 1: Environment setup and initialization"""
        phase_start = time.time()
        
        try:
            print("🔧 Initializing test environment...")
            
            # Initialize test environment
            env_info = await test_env.initialize_environment()
            
            if env_info["status"] != "ready":
                return {
                    "success": False,
                    "error": "Test environment initialization failed",
                    "details": env_info
                }
            
            print(f"  ✅ Test environment ready")
            print(f"  📁 Workspace: {env_info['workspace']}")
            print(f"  🗄️ Database: {env_info['database_connection']}")
            print(f"  🔌 PLC Manager: {env_info['plc_manager']}")
            
            # Validate database schema
            print("🔍 Validating database schema...")
            schema_validation = env_info.get("schema_validation", {})
            
            if schema_validation.get("overall_status") == "valid":
                print("  ✅ Database schema validation passed")
            else:
                print(f"  ⚠️ Database schema issues: {schema_validation.get('overall_status', 'unknown')}")
            
            # Check test data availability
            print("📊 Checking test data availability...")
            test_machines = await test_env.get_test_machines()
            test_recipes = await test_env.get_test_recipes()
            
            print(f"  📱 Available machines: {len(test_machines)}")
            print(f"  📋 Available recipes: {len(test_recipes)}")
            
            if len(test_machines) == 0 or len(test_recipes) == 0:
                print("  ⚠️ Limited test data available - some tests may be skipped")
            
            phase_duration = time.time() - phase_start
            
            return {
                "success": True,
                "duration_seconds": phase_duration,
                "environment_info": env_info,
                "test_data": {
                    "machines": len(test_machines),
                    "recipes": len(test_recipes)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - phase_start
            }
    
    async def _phase_2_migration_validation(self) -> Dict[str, Any]:
        """Phase 2: Schema migration validation"""
        phase_start = time.time()
        
        try:
            print("🔄 Initializing migration validator...")
            
            if not await migration_validator.initialize():
                return {
                    "success": False,
                    "error": "Migration validator initialization failed"
                }
            
            print("🔍 Running migration validation...")
            migration_report = await migration_validator.validate_complete_migration()
            
            # Print key results
            print(f"  📊 Migration Status: {migration_report['migration_status']}")
            print(f"  🎯 Production Ready: {'✅ Yes' if migration_report['production_ready'] else '❌ No'}")
            print(f"  📈 Success Rate: {migration_report['summary']['success_rate']:.1%}")
            print(f"  ✅ Passed: {migration_report['summary']['passed']}")
            print(f"  ❌ Failed: {migration_report['summary']['failed']}")
            print(f"  ⚠️ Warnings: {migration_report['summary']['warnings']}")
            
            if migration_report.get("critical_issues"):
                print(f"  🚨 Critical Issues: {len(migration_report['critical_issues'])}")
                for issue in migration_report['critical_issues'][:3]:
                    print(f"    - {issue}")
            
            phase_duration = time.time() - phase_start
            
            return {
                "success": migration_report['migration_status'] != 'FAILED',
                "duration_seconds": phase_duration,
                "migration_report": migration_report,
                "critical_issues": len(migration_report.get('critical_issues', [])),
                "production_ready": migration_report.get('production_ready', False)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - phase_start
            }
    
    async def _phase_3_comprehensive_tests(self) -> Dict[str, Any]:
        """Phase 3: Comprehensive test suite execution"""
        phase_start = time.time()
        
        try:
            print("🧪 Initializing comprehensive test suite...")
            
            if not await test_suite.initialize():
                return {
                    "success": False,
                    "error": "Test suite initialization failed"
                }
            
            print("🔄 Running comprehensive test suite...")
            print("   This may take several minutes...")
            
            test_metrics = await test_suite.run_complete_test_suite()
            
            # Print key results
            print(f"  📊 Test Status: {test_metrics.status}")
            print(f"  📈 Success Rate: {test_metrics.success_rate:.1%}")
            print(f"  📋 Total Tests: {test_metrics.total_tests}")
            print(f"  ✅ Passed: {test_metrics.passed_tests}")
            print(f"  ❌ Failed: {test_metrics.failed_tests}")
            print(f"  ⏭️ Skipped: {test_metrics.skipped_tests}")
            print(f"  ⏱️ Duration: {test_metrics.total_duration_seconds:.1f}s")
            
            if test_metrics.failed_tests > 0:
                print("  ⚠️ Some tests failed - check detailed results")
            
            phase_duration = time.time() - phase_start
            
            return {
                "success": test_metrics.status != "FAILED",
                "duration_seconds": phase_duration,
                "test_metrics": test_metrics,
                "success_rate": test_metrics.success_rate,
                "failed_tests": test_metrics.failed_tests
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - phase_start
            }
    
    async def _phase_4_performance_testing(self) -> Dict[str, Any]:
        """Phase 4: Performance and load testing"""
        phase_start = time.time()
        
        try:
            print("📈 Initializing performance tester...")
            
            if not await performance_tester.initialize():
                return {
                    "success": False,
                    "error": "Performance tester initialization failed"
                }
            
            print("🏃 Running performance test suite...")
            print("   This includes load testing and may take several minutes...")
            
            performance_summary = await performance_tester.run_performance_test_suite()
            
            # Print key results
            print(f"  📊 Performance Status: {performance_summary['production_readiness']['overall_status']}")
            print(f"  🎯 Performance Grade: {performance_summary['production_readiness']['performance_grade']}")
            print(f"  📋 Total Tests: {performance_summary['metrics_summary']['total_tests']}")
            print(f"  📈 Avg Success Rate: {performance_summary['metrics_summary']['average_success_rate']:.1%}")
            
            if performance_summary.get('performance_analysis'):
                perf_analysis = performance_summary['performance_analysis']
                if perf_analysis.get('average_throughput_ops_per_sec'):
                    print(f"  ⚡ Avg Throughput: {perf_analysis['average_throughput_ops_per_sec']:.2f} ops/sec")
                if perf_analysis.get('max_memory_usage_mb'):
                    print(f"  💾 Peak Memory: {perf_analysis['max_memory_usage_mb']:.1f} MB")
            
            if performance_summary.get('system_limits'):
                limits = performance_summary['system_limits']
                if limits.get('max_concurrent_users_tested'):
                    print(f"  👥 Max Users Tested: {limits['max_concurrent_users_tested']}")
                if limits.get('degradation_point'):
                    print(f"  ⚠️ Degradation Point: {limits['degradation_point']} users")
            
            if performance_summary.get('recommendations'):
                print(f"  💡 Recommendations: {len(performance_summary['recommendations'])}")
            
            phase_duration = time.time() - phase_start
            
            return {
                "success": performance_summary['production_readiness']['overall_status'] == "READY",
                "duration_seconds": phase_duration,
                "performance_summary": performance_summary,
                "performance_grade": performance_summary['production_readiness']['performance_grade'],
                "recommendations_count": len(performance_summary.get('recommendations', []))
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - phase_start
            }
    
    async def _phase_5_report_generation(self) -> Dict[str, Any]:
        """Phase 5: Master report generation"""
        phase_start = time.time()
        
        try:
            print("📊 Initializing master report generator...")
            
            if not await report_generator.initialize():
                return {
                    "success": False,
                    "error": "Report generator initialization failed"
                }
            
            print("📋 Generating comprehensive master report...")
            print("   Collecting all test results and generating visualizations...")
            
            master_report = await report_generator.generate_master_report()
            
            # Print key results
            print(f"  📊 Overall Status: {master_report['executive_summary']['overall_status']}")
            print(f"  🎯 Overall Score: {master_report['executive_summary']['key_metrics']['overall_score']:.1f}/100")
            print(f"  📈 Confidence Level: {master_report['executive_summary']['confidence_level']}")
            print(f"  💡 Recommendation: {master_report['executive_summary']['recommendation']}")
            print(f"  🚀 Production Ready: {'✅ Yes' if master_report['production_readiness']['overall_readiness'] == 'READY' else '❌ No'}")
            
            # Print report locations
            report_id = master_report['report_id']
            workspace = test_env.test_workspace
            print(f"\n  📁 Reports generated:")
            print(f"    - HTML: {workspace}/master_reports/html/master_test_report_{report_id}.html")
            print(f"    - JSON: {workspace}/master_reports/json/master_test_report_{report_id}.json")
            print(f"    - Markdown: {workspace}/master_reports/master_test_report_{report_id}.md")
            print(f"    - Dashboard: {workspace}/master_reports/test_execution_dashboard.html")
            
            if master_report['visualizations']['charts_created']:
                print(f"    - Charts: {len(master_report['visualizations']['charts_created'])} visualizations")
            
            phase_duration = time.time() - phase_start
            
            return {
                "success": True,
                "duration_seconds": phase_duration,
                "master_report": master_report,
                "report_id": report_id,
                "overall_score": master_report['executive_summary']['key_metrics']['overall_score'],
                "production_readiness": master_report['production_readiness']['overall_readiness']
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - phase_start
            }
    
    async def _phase_6_final_assessment(self) -> Dict[str, Any]:
        """Phase 6: Final assessment and recommendations"""
        phase_start = time.time()
        
        try:
            print("🎯 Conducting final assessment...")
            
            # Analyze all phase results
            assessment = {
                "overall_success": True,
                "critical_issues": [],
                "warnings": [],
                "recommendations": [],
                "deployment_readiness": "UNKNOWN",
                "risk_level": "MEDIUM"
            }
            
            # Check each phase
            for phase_name, phase_result in self.execution_results.items():
                if not phase_result.get("success", True):
                    assessment["overall_success"] = False
                    assessment["critical_issues"].append(f"{phase_name}: {phase_result.get('error', 'Unknown error')}")
            
            # Assess deployment readiness
            if assessment["overall_success"]:
                # Check specific criteria
                migration_ready = self.execution_results.get("phase_2_migration", {}).get("production_ready", False)
                comprehensive_success = self.execution_results.get("phase_3_comprehensive", {}).get("success_rate", 0) >= 0.95
                performance_ready = self.execution_results.get("phase_4_performance", {}).get("success", False)
                
                if migration_ready and comprehensive_success and performance_ready:
                    assessment["deployment_readiness"] = "READY"
                    assessment["risk_level"] = "LOW"
                elif migration_ready and comprehensive_success:
                    assessment["deployment_readiness"] = "MOSTLY_READY"
                    assessment["risk_level"] = "MEDIUM"
                    assessment["warnings"].append("Performance testing shows issues")
                elif migration_ready:
                    assessment["deployment_readiness"] = "NEEDS_WORK"
                    assessment["risk_level"] = "MEDIUM_HIGH"
                    assessment["warnings"].append("Comprehensive tests or performance issues")
                else:
                    assessment["deployment_readiness"] = "NOT_READY"
                    assessment["risk_level"] = "HIGH"
                    assessment["critical_issues"].append("Database migration issues")
            else:
                assessment["deployment_readiness"] = "NOT_READY"
                assessment["risk_level"] = "HIGH"
            
            # Generate recommendations
            if assessment["deployment_readiness"] == "READY":
                assessment["recommendations"] = [
                    "✅ System is ready for production deployment",
                    "📊 Implement comprehensive monitoring post-deployment",
                    "📋 Prepare rollback procedures as precaution"
                ]
            elif assessment["deployment_readiness"] == "MOSTLY_READY":
                assessment["recommendations"] = [
                    "🔧 Address minor performance issues before deployment",
                    "📊 Deploy with enhanced monitoring",
                    "⚠️ Prepare for potential performance optimization"
                ]
            elif assessment["deployment_readiness"] == "NEEDS_WORK":
                assessment["recommendations"] = [
                    "🛠️ Address failed tests and performance issues",
                    "🧪 Rerun validation after fixes",
                    "⏰ Allow 1-2 weeks for fixes and revalidation"
                ]
            else:
                assessment["recommendations"] = [
                    "🚫 DO NOT DEPLOY - Critical issues must be resolved",
                    "🔧 Address all critical issues first",
                    "🧪 Complete revalidation required after fixes"
                ]
            
            # Print assessment
            print(f"  📊 Overall Success: {'✅ Yes' if assessment['overall_success'] else '❌ No'}")
            print(f"  🚀 Deployment Readiness: {assessment['deployment_readiness']}")
            print(f"  ⚠️ Risk Level: {assessment['risk_level']}")
            
            if assessment["critical_issues"]:
                print(f"  🚨 Critical Issues: {len(assessment['critical_issues'])}")
            
            if assessment["warnings"]:
                print(f"  ⚠️ Warnings: {len(assessment['warnings'])}")
            
            phase_duration = time.time() - phase_start
            
            return {
                "success": True,
                "duration_seconds": phase_duration,
                "assessment": assessment
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - phase_start
            }
    
    async def _generate_execution_summary(self) -> Dict[str, Any]:
        """Generate comprehensive execution summary"""
        execution_end_time = datetime.now()
        total_duration = (execution_end_time - self.execution_start_time).total_seconds()
        
        summary = {
            "execution_id": test_env.test_session_id,
            "start_time": self.execution_start_time.isoformat(),
            "end_time": execution_end_time.isoformat(),
            "total_duration_seconds": total_duration,
            "phase_results": self.execution_results,
            "overall_success": True,
            "validation_status": "UNKNOWN",
            "production_readiness": "UNKNOWN",
            "critical_blockers": [],
            "recommendations": [],
            "next_steps": []
        }
        
        try:
            # Determine overall success
            failed_phases = [name for name, result in self.execution_results.items() 
                            if not result.get("success", True)]
            
            summary["overall_success"] = len(failed_phases) == 0
            
            # Get final assessment if available
            if "phase_6_assessment" in self.execution_results:
                assessment = self.execution_results["phase_6_assessment"].get("assessment", {})
                summary["validation_status"] = "PASSED" if assessment.get("overall_success", False) else "FAILED"
                summary["production_readiness"] = assessment.get("deployment_readiness", "UNKNOWN")
                summary["critical_blockers"] = assessment.get("critical_issues", [])
                summary["recommendations"] = assessment.get("recommendations", [])
            
            # Generate next steps
            if summary["production_readiness"] == "READY":
                summary["next_steps"] = [
                    "🚀 Proceed with production deployment",
                    "📊 Implement monitoring and alerting",
                    "📋 Execute deployment checklist",
                    "👥 Notify stakeholders of deployment"
                ]
            elif summary["production_readiness"] in ["MOSTLY_READY", "NEEDS_WORK"]:
                summary["next_steps"] = [
                    "🔧 Address identified issues",
                    "🧪 Rerun affected test categories",
                    "📊 Validate fixes before deployment",
                    "⏰ Plan deployment timeline"
                ]
            else:
                summary["next_steps"] = [
                    "🚫 DO NOT DEPLOY to production",
                    "🛠️ Fix all critical issues",
                    "🧪 Execute complete revalidation",
                    "📋 Review system architecture if needed"
                ]
            
            # Add phase timings
            phase_timings = {}
            for phase_name, result in self.execution_results.items():
                phase_timings[phase_name] = result.get("duration_seconds", 0)
            
            summary["phase_timings"] = phase_timings
            summary["longest_phase"] = max(phase_timings.keys(), key=lambda k: phase_timings[k]) if phase_timings else None
            
        except Exception as e:
            self.logger.error(f"Error generating execution summary: {e}")
            summary["summary_error"] = str(e)
        
        return summary
    
    async def _print_final_results(self, execution_summary: Dict[str, Any]) -> None:
        """Print final validation results"""
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE VALIDATION COMPLETE")
        print("="*80)
        
        print(f"Execution ID: {execution_summary['execution_id']}")
        print(f"Start Time: {execution_summary['start_time']}")
        print(f"End Time: {execution_summary['end_time']}")
        print(f"Total Duration: {execution_summary['total_duration_seconds']:.1f} seconds")
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"Validation Status: {execution_summary['validation_status']}")
        print(f"Production Readiness: {execution_summary['production_readiness']}")
        print(f"Overall Success: {'✅ Yes' if execution_summary['overall_success'] else '❌ No'}")
        
        # Phase Results Summary
        print(f"\n📋 PHASE RESULTS:")
        for phase_name, result in execution_summary['phase_results'].items():
            status_icon = "✅" if result.get('success', False) else "❌"
            duration = result.get('duration_seconds', 0)
            print(f"  {status_icon} {phase_name.replace('_', ' ').title()}: {duration:.1f}s")
        
        # Critical Issues
        if execution_summary.get('critical_blockers'):
            print(f"\n🚨 CRITICAL BLOCKERS ({len(execution_summary['critical_blockers'])}):")
            for blocker in execution_summary['critical_blockers']:
                print(f"  - {blocker}")
        
        # Recommendations
        if execution_summary.get('recommendations'):
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in execution_summary['recommendations']:
                print(f"  {rec}")
        
        # Next Steps
        if execution_summary.get('next_steps'):
            print(f"\n🔄 NEXT STEPS:")
            for step in execution_summary['next_steps']:
                print(f"  {step}")
        
        # Report Locations
        if 'phase_5_reporting' in execution_summary['phase_results']:
            report_result = execution_summary['phase_results']['phase_5_reporting']
            if report_result.get('success') and report_result.get('report_id'):
                report_id = report_result['report_id']
                workspace = test_env.test_workspace
                print(f"\n📁 DETAILED REPORTS:")
                print(f"  - Dashboard: {workspace}/master_reports/test_execution_dashboard.html")
                print(f"  - HTML Report: {workspace}/master_reports/html/master_test_report_{report_id}.html")
                print(f"  - JSON Data: {workspace}/master_reports/json/master_test_report_{report_id}.json")
                print(f"  - Markdown: {workspace}/master_reports/master_test_report_{report_id}.md")
        
        # Final Status
        print(f"\n" + "="*80)
        if execution_summary['production_readiness'] == 'READY':
            print("🎉 SYSTEM READY FOR PRODUCTION DEPLOYMENT!")
        elif execution_summary['production_readiness'] in ['MOSTLY_READY', 'NEEDS_WORK']:
            print("⚠️ SYSTEM NEEDS ATTENTION BEFORE DEPLOYMENT")
        else:
            print("❌ SYSTEM NOT READY FOR PRODUCTION - CRITICAL ISSUES MUST BE RESOLVED")
        print("="*80)
    
    async def _generate_failure_report(self, error_message: str) -> Dict[str, Any]:
        """Generate failure report for critical errors"""
        return {
            "execution_id": test_env.test_session_id,
            "start_time": self.execution_start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "overall_success": False,
            "validation_status": "FAILED",
            "production_readiness": "NOT_READY",
            "critical_error": error_message,
            "phase_results": self.execution_results,
            "recommendations": [
                "🚫 DO NOT DEPLOY - Critical validation failure",
                "🔧 Investigate and fix the critical error",
                "🧪 Restart complete validation after fixes"
            ]
        }
    
    async def _cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if hasattr(test_env, 'cleanup_environment'):
                await test_env.cleanup_environment()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

# Global validation executor
validation_executor = ComprehensiveValidationExecutor()

async def main():
    """Main execution function"""
    try:
        # Execute comprehensive validation
        execution_summary = await validation_executor.execute_comprehensive_validation()
        
        # Set exit code based on results
        if execution_summary.get('production_readiness') == 'READY':
            sys.exit(0)  # Success
        elif execution_summary.get('production_readiness') in ['MOSTLY_READY', 'NEEDS_WORK']:
            sys.exit(1)  # Warning
        else:
            sys.exit(2)  # Critical failure
            
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)  # Execution error

if __name__ == "__main__":
    asyncio.run(main())