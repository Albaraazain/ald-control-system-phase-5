#!/usr/bin/env python3
"""
Master Test Report Generator
Consolidates all test results into comprehensive reports and dashboards
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4
import markdown
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from jinja2 import Template

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_environment_setup import test_env
from log_setup import setup_logger

class MasterTestReportGenerator:
    """Master test report generator and dashboard creator"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.report_id = str(uuid4())
        self.test_workspace = None
        self.reports_dir = None
        self.charts_dir = None
        
    async def initialize(self) -> bool:
        """Initialize report generator"""
        self.logger.info("🚀 Initializing Master Test Report Generator...")
        
        try:
            # Use existing test environment
            if not test_env.is_ready():
                env_info = await test_env.initialize_environment()
                if env_info["status"] != "ready":
                    raise RuntimeError("Test environment initialization failed")
            
            self.test_workspace = Path(test_env.test_workspace)
            self.reports_dir = self.test_workspace / "master_reports"
            self.charts_dir = self.reports_dir / "charts"
            
            # Create directories
            self.reports_dir.mkdir(exist_ok=True)
            self.charts_dir.mkdir(exist_ok=True)
            (self.reports_dir / "html").mkdir(exist_ok=True)
            (self.reports_dir / "json").mkdir(exist_ok=True)
            
            self.logger.info("✅ Master test report generator initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Report generator initialization failed: {e}")
            return False
    
    async def generate_master_report(self) -> Dict[str, Any]:
        """Generate comprehensive master test report"""
        self.logger.info("📊 Generating Master Test Report...")
        
        report_start = datetime.now()
        
        try:
            # Collect all test results
            all_results = await self._collect_all_test_results()
            
            # Generate executive summary
            executive_summary = await self._generate_executive_summary(all_results)
            
            # Create detailed analysis
            detailed_analysis = await self._generate_detailed_analysis(all_results)
            
            # Generate visualizations
            visualizations = await self._generate_visualizations(all_results)
            
            # Create production readiness assessment
            production_assessment = await self._assess_production_readiness(all_results)
            
            # Generate recommendations and next steps
            recommendations = await self._generate_recommendations(all_results, production_assessment)
            
            # Compile master report
            master_report = {
                "report_id": self.report_id,
                "generation_timestamp": report_start.isoformat(),
                "report_version": "1.0",
                "test_environment": test_env.get_session_info(),
                "executive_summary": executive_summary,
                "detailed_analysis": detailed_analysis,
                "production_readiness": production_assessment,
                "recommendations": recommendations,
                "visualizations": visualizations,
                "raw_results": all_results,
                "appendices": await self._generate_appendices(all_results)
            }
            
            # Generate reports in multiple formats
            await self._generate_json_report(master_report)
            await self._generate_html_report(master_report)
            await self._generate_markdown_report(master_report)
            await self._generate_dashboard(master_report)
            
            report_end = datetime.now()
            master_report["generation_duration_seconds"] = (report_end - report_start).total_seconds()
            
            self.logger.info("✅ Master test report generated successfully")
            return master_report
            
        except Exception as e:
            self.logger.error(f"❌ Master report generation failed: {e}")
            raise
    
    async def _collect_all_test_results(self) -> Dict[str, Any]:
        """Collect results from all test frameworks"""
        self.logger.info("🔍 Collecting all test results...")
        
        all_results = {
            "comprehensive_tests": {},
            "performance_tests": {},
            "migration_validation": {},
            "integration_tests": {},
            "collection_timestamp": datetime.now().isoformat(),
            "collection_summary": {}
        }
        
        try:
            # Look for comprehensive test results
            comprehensive_files = list(self.test_workspace.glob("reports/comprehensive_test_report_*.json"))
            if comprehensive_files:
                latest_comprehensive = max(comprehensive_files, key=lambda p: p.stat().st_mtime)
                with open(latest_comprehensive, 'r') as f:
                    all_results["comprehensive_tests"] = json.load(f)
                self.logger.info(f"📋 Found comprehensive test results: {latest_comprehensive.name}")
            
            # Look for performance test results
            performance_files = list(self.test_workspace.glob("performance/performance_summary_*.json"))
            if performance_files:
                latest_performance = max(performance_files, key=lambda p: p.stat().st_mtime)
                with open(latest_performance, 'r') as f:
                    all_results["performance_tests"] = json.load(f)
                self.logger.info(f"📈 Found performance test results: {latest_performance.name}")
            
            # Look for migration validation results
            migration_files = list(self.test_workspace.glob("migration_validation/migration_validation_report_*.json"))
            if migration_files:
                latest_migration = max(migration_files, key=lambda p: p.stat().st_mtime)
                with open(latest_migration, 'r') as f:
                    all_results["migration_validation"] = json.load(f)
                self.logger.info(f"🔄 Found migration validation results: {latest_migration.name}")
            
            # Look for integration test results
            integration_files = list(self.test_workspace.glob("**/integration_test_*.json"))
            integration_results = []
            for file in integration_files:
                try:
                    with open(file, 'r') as f:
                        integration_results.append(json.load(f))
                except Exception as e:
                    self.logger.warning(f"Could not load integration test file {file}: {e}")
            
            all_results["integration_tests"] = integration_results
            
            # Generate collection summary
            all_results["collection_summary"] = {
                "comprehensive_tests_found": bool(all_results["comprehensive_tests"]),
                "performance_tests_found": bool(all_results["performance_tests"]),
                "migration_validation_found": bool(all_results["migration_validation"]),
                "integration_tests_count": len(all_results["integration_tests"]),
                "total_data_sources": sum([
                    1 if all_results["comprehensive_tests"] else 0,
                    1 if all_results["performance_tests"] else 0,
                    1 if all_results["migration_validation"] else 0,
                    len(all_results["integration_tests"])
                ])
            }
            
            self.logger.info(f"📊 Collected {all_results['collection_summary']['total_data_sources']} test data sources")
            
        except Exception as e:
            self.logger.error(f"Error collecting test results: {e}")
            all_results["collection_error"] = str(e)
        
        return all_results
    
    async def _generate_executive_summary(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary of all test results"""
        self.logger.info("📋 Generating executive summary...")
        
        summary = {
            "overall_status": "UNKNOWN",
            "key_metrics": {},
            "critical_findings": [],
            "success_indicators": [],
            "areas_of_concern": [],
            "confidence_level": "LOW",
            "recommendation": "NEEDS_REVIEW"
        }
        
        try:
            # Aggregate key metrics
            metrics = {}
            status_scores = []  # For calculating overall status
            
            # Comprehensive test metrics
            if all_results.get("comprehensive_tests"):
                comp_tests = all_results["comprehensive_tests"]
                if "summary" in comp_tests:
                    comp_summary = comp_tests["summary"]
                    metrics["comprehensive_tests"] = {
                        "total_tests": comp_summary.get("total_tests", 0),
                        "success_rate": comp_summary.get("success_rate", 0),
                        "status": comp_summary.get("status", "UNKNOWN")
                    }
                    
                    # Score: 100 for PASSED, 50 for PARTIAL, 0 for FAILED
                    score = {"PASSED": 100, "PARTIAL": 50, "FAILED": 0}.get(comp_summary.get("status", "UNKNOWN"), 0)
                    status_scores.append(("comprehensive", score))
                    
                    if comp_summary.get("success_rate", 0) >= 0.95:
                        summary["success_indicators"].append("Comprehensive tests show high success rate (≥95%)")
                    elif comp_summary.get("success_rate", 0) < 0.8:
                        summary["areas_of_concern"].append("Comprehensive tests below 80% success rate")
            
            # Performance test metrics
            if all_results.get("performance_tests"):
                perf_tests = all_results["performance_tests"]
                if "production_readiness" in perf_tests:
                    prod_ready = perf_tests["production_readiness"]
                    metrics["performance_tests"] = {
                        "overall_status": prod_ready.get("overall_status", "UNKNOWN"),
                        "performance_grade": prod_ready.get("performance_grade", "UNKNOWN")
                    }
                    
                    grade_scores = {"EXCELLENT": 100, "GOOD": 85, "ACCEPTABLE": 70, "NEEDS_IMPROVEMENT": 40, "POOR": 10}
                    score = grade_scores.get(prod_ready.get("performance_grade", "UNKNOWN"), 0)
                    status_scores.append(("performance", score))
                    
                    if prod_ready.get("performance_grade") in ["EXCELLENT", "GOOD"]:
                        summary["success_indicators"].append("Performance testing shows good system performance")
                    elif prod_ready.get("performance_grade") in ["NEEDS_IMPROVEMENT", "POOR"]:
                        summary["areas_of_concern"].append("Performance testing indicates optimization needed")
            
            # Migration validation metrics
            if all_results.get("migration_validation"):
                migration = all_results["migration_validation"]
                metrics["migration_validation"] = {
                    "migration_status": migration.get("migration_status", "UNKNOWN"),
                    "production_ready": migration.get("production_ready", False),
                    "success_rate": migration.get("summary", {}).get("success_rate", 0)
                }
                
                # Score based on migration status
                migration_scores = {"PASSED": 100, "WARNINGS": 70, "FAILED": 0}
                score = migration_scores.get(migration.get("migration_status", "UNKNOWN"), 0)
                status_scores.append(("migration", score))
                
                if migration.get("production_ready", False):
                    summary["success_indicators"].append("Database migration validation passed")
                else:
                    summary["areas_of_concern"].append("Database migration validation issues detected")
                
                if migration.get("critical_issues"):
                    summary["critical_findings"].extend(migration["critical_issues"][:3])  # Top 3
            
            # Calculate overall status
            if status_scores:
                avg_score = sum(score for _, score in status_scores) / len(status_scores)
                if avg_score >= 90:
                    summary["overall_status"] = "EXCELLENT"
                    summary["confidence_level"] = "HIGH"
                    summary["recommendation"] = "READY_FOR_PRODUCTION"
                elif avg_score >= 75:
                    summary["overall_status"] = "GOOD"
                    summary["confidence_level"] = "MEDIUM_HIGH"
                    summary["recommendation"] = "READY_WITH_MONITORING"
                elif avg_score >= 60:
                    summary["overall_status"] = "ACCEPTABLE"
                    summary["confidence_level"] = "MEDIUM"
                    summary["recommendation"] = "READY_AFTER_FIXES"
                elif avg_score >= 40:
                    summary["overall_status"] = "NEEDS_IMPROVEMENT"
                    summary["confidence_level"] = "MEDIUM_LOW"
                    summary["recommendation"] = "SIGNIFICANT_WORK_NEEDED"
                else:
                    summary["overall_status"] = "POOR"
                    summary["confidence_level"] = "LOW"
                    summary["recommendation"] = "NOT_READY_FOR_PRODUCTION"
            
            # Set key metrics
            summary["key_metrics"] = metrics
            summary["key_metrics"]["overall_score"] = avg_score if status_scores else 0
            summary["key_metrics"]["status_breakdown"] = dict(status_scores)
            
            # Limit findings to most important
            summary["critical_findings"] = summary["critical_findings"][:5]
            summary["success_indicators"] = summary["success_indicators"][:5]
            summary["areas_of_concern"] = summary["areas_of_concern"][:5]
            
        except Exception as e:
            self.logger.error(f"Error generating executive summary: {e}")
            summary["generation_error"] = str(e)
        
        return summary
    
    async def _generate_detailed_analysis(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed analysis of test results"""
        self.logger.info("🔬 Generating detailed analysis...")
        
        analysis = {
            "test_coverage_analysis": {},
            "quality_metrics": {},
            "performance_analysis": {},
            "reliability_analysis": {},
            "compatibility_analysis": {},
            "trend_analysis": {},
            "risk_assessment": {}
        }
        
        try:
            # Test Coverage Analysis
            coverage = {"categories_tested": [], "coverage_gaps": [], "coverage_score": 0}
            
            test_categories = [
                ("Database Schema", bool(all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("Schema Validation"))),
                ("Integration Tests", bool(all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("Database Integration"))),
                ("Performance Tests", bool(all_results.get("performance_tests"))),
                ("Migration Validation", bool(all_results.get("migration_validation"))),
                ("End-to-End Workflows", bool(all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("End-to-End Workflow"))),
                ("Error Handling", bool(all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("Error Handling"))),
                ("Concurrency", bool(all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("Concurrency")))
            ]
            
            for category, tested in test_categories:
                if tested:
                    coverage["categories_tested"].append(category)
                else:
                    coverage["coverage_gaps"].append(category)
            
            coverage["coverage_score"] = len(coverage["categories_tested"]) / len(test_categories) * 100
            analysis["test_coverage_analysis"] = coverage
            
            # Quality Metrics Analysis
            quality = {"overall_quality": "UNKNOWN", "quality_indicators": []}
            
            if all_results.get("comprehensive_tests", {}).get("summary"):
                comp_summary = all_results["comprehensive_tests"]["summary"]
                success_rate = comp_summary.get("success_rate", 0)
                
                if success_rate >= 0.98:
                    quality["overall_quality"] = "EXCELLENT"
                    quality["quality_indicators"].append("Very high test success rate (≥98%)")
                elif success_rate >= 0.95:
                    quality["overall_quality"] = "GOOD"
                    quality["quality_indicators"].append("High test success rate (≥95%)")
                elif success_rate >= 0.90:
                    quality["overall_quality"] = "ACCEPTABLE"
                    quality["quality_indicators"].append("Acceptable test success rate (≥90%)")
                else:
                    quality["overall_quality"] = "POOR"
                    quality["quality_indicators"].append(f"Low test success rate ({success_rate:.1%})")
            
            analysis["quality_metrics"] = quality
            
            # Performance Analysis
            performance = {"status": "NO_DATA", "key_findings": []}
            
            if all_results.get("performance_tests"):
                perf_data = all_results["performance_tests"]
                performance["status"] = perf_data.get("production_readiness", {}).get("overall_status", "UNKNOWN")
                
                if "performance_analysis" in perf_data:
                    perf_analysis = perf_data["performance_analysis"]
                    
                    avg_throughput = perf_analysis.get("average_throughput_ops_per_sec", 0)
                    max_memory = perf_analysis.get("max_memory_usage_mb", 0)
                    
                    if avg_throughput > 0:
                        performance["key_findings"].append(f"Average throughput: {avg_throughput:.2f} ops/sec")
                    if max_memory > 0:
                        performance["key_findings"].append(f"Peak memory usage: {max_memory:.1f} MB")
                
                # Add load test insights
                if "load_test_results" in perf_data:
                    load_results = perf_data["load_test_results"]
                    if load_results:
                        max_users = max(result.get("concurrent_users", 0) for result in load_results)
                        performance["key_findings"].append(f"Tested up to {max_users} concurrent users")
                
                if "system_limits" in perf_data:
                    limits = perf_data["system_limits"]
                    if limits.get("degradation_point"):
                        performance["key_findings"].append(f"Performance degradation at {limits['degradation_point']} users")
            
            analysis["performance_analysis"] = performance
            
            # Reliability Analysis
            reliability = {"assessment": "UNKNOWN", "evidence": []}
            
            # Check for error handling test results
            if all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("Error Handling"):
                error_tests = all_results["comprehensive_tests"]["results_by_category"]["Error Handling"]
                passed_error_tests = error_tests.get("passed", 0)
                total_error_tests = error_tests.get("total", 1)
                
                if passed_error_tests == total_error_tests and total_error_tests > 0:
                    reliability["assessment"] = "HIGH"
                    reliability["evidence"].append("All error handling tests passed")
                elif passed_error_tests / total_error_tests >= 0.8:
                    reliability["assessment"] = "MEDIUM"
                    reliability["evidence"].append("Most error handling tests passed")
                else:
                    reliability["assessment"] = "LOW"
                    reliability["evidence"].append("Error handling tests show issues")
            
            analysis["reliability_analysis"] = reliability
            
            # Compatibility Analysis
            compatibility = {"status": "UNKNOWN", "findings": []}
            
            if all_results.get("migration_validation"):
                migration = all_results["migration_validation"]
                
                # Look for backward compatibility results
                detailed_results = migration.get("detailed_results", [])
                compat_results = [r for r in detailed_results if r.get("category") == "Compatibility"]
                
                if compat_results:
                    passed_compat = sum(1 for r in compat_results if r.get("status") == "passed")
                    total_compat = len(compat_results)
                    
                    if passed_compat == total_compat:
                        compatibility["status"] = "FULL"
                        compatibility["findings"].append("All compatibility tests passed")
                    elif passed_compat / total_compat >= 0.8:
                        compatibility["status"] = "MOSTLY_COMPATIBLE"
                        compatibility["findings"].append("Most compatibility tests passed")
                    else:
                        compatibility["status"] = "ISSUES_DETECTED"
                        compatibility["findings"].append("Compatibility issues detected")
            
            analysis["compatibility_analysis"] = compatibility
            
            # Risk Assessment
            risk = {"overall_risk": "MEDIUM", "high_risks": [], "medium_risks": [], "low_risks": []}
            
            # Assess risks based on test results
            if all_results.get("migration_validation", {}).get("critical_issues"):
                risk["high_risks"].extend(all_results["migration_validation"]["critical_issues"][:3])
            
            if all_results.get("comprehensive_tests", {}).get("summary", {}).get("failed_tests", 0) > 5:
                risk["medium_risks"].append("Multiple comprehensive test failures")
            
            if all_results.get("performance_tests", {}).get("recommendations"):
                risk["medium_risks"].extend(all_results["performance_tests"]["recommendations"][:2])
            
            # Determine overall risk level
            if risk["high_risks"]:
                risk["overall_risk"] = "HIGH"
            elif len(risk["medium_risks"]) > 3:
                risk["overall_risk"] = "MEDIUM_HIGH"
            elif risk["medium_risks"]:
                risk["overall_risk"] = "MEDIUM"
            else:
                risk["overall_risk"] = "LOW"
            
            analysis["risk_assessment"] = risk
            
        except Exception as e:
            self.logger.error(f"Error generating detailed analysis: {e}")
            analysis["analysis_error"] = str(e)
        
        return analysis
    
    async def _generate_visualizations(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate visualizations for test results"""
        self.logger.info("📊 Generating visualizations...")
        
        visualizations = {
            "charts_created": [],
            "chart_files": {},
            "summary_stats": {}
        }
        
        try:
            # 1. Overall Test Status Dashboard
            await self._create_status_dashboard(all_results)
            visualizations["charts_created"].append("status_dashboard")
            visualizations["chart_files"]["status_dashboard"] = "status_dashboard.html"
            
            # 2. Test Coverage Visualization
            if self._has_comprehensive_data(all_results):
                await self._create_coverage_visualization(all_results)
                visualizations["charts_created"].append("test_coverage")
                visualizations["chart_files"]["test_coverage"] = "test_coverage.html"
            
            # 3. Performance Trends
            if all_results.get("performance_tests"):
                await self._create_performance_visualization(all_results["performance_tests"])
                visualizations["charts_created"].append("performance_trends")
                visualizations["chart_files"]["performance_trends"] = "performance_trends.html"
            
            # 4. Success Rate Analysis
            await self._create_success_rate_analysis(all_results)
            visualizations["charts_created"].append("success_rate_analysis")
            visualizations["chart_files"]["success_rate_analysis"] = "success_rate_analysis.html"
            
            # 5. Risk Heatmap
            await self._create_risk_heatmap(all_results)
            visualizations["charts_created"].append("risk_heatmap")
            visualizations["chart_files"]["risk_heatmap"] = "risk_heatmap.html"
            
            visualizations["summary_stats"] = {
                "total_charts": len(visualizations["charts_created"]),
                "charts_directory": str(self.charts_dir)
            }
            
            self.logger.info(f"📈 Generated {len(visualizations['charts_created'])} visualizations")
            
        except Exception as e:
            self.logger.error(f"Error generating visualizations: {e}")
            visualizations["visualization_error"] = str(e)
        
        return visualizations
    
    async def _create_status_dashboard(self, all_results: Dict[str, Any]) -> None:
        """Create overall status dashboard"""
        # Create status indicators
        statuses = []
        colors = []
        
        # Comprehensive tests status
        if all_results.get("comprehensive_tests", {}).get("summary"):
            comp_status = all_results["comprehensive_tests"]["summary"].get("status", "UNKNOWN")
            statuses.append(f"Comprehensive Tests: {comp_status}")
            colors.append("green" if comp_status == "PASSED" else "orange" if comp_status == "PARTIAL" else "red")
        
        # Performance tests status
        if all_results.get("performance_tests", {}).get("production_readiness"):
            perf_status = all_results["performance_tests"]["production_readiness"].get("overall_status", "UNKNOWN")
            statuses.append(f"Performance Tests: {perf_status}")
            colors.append("green" if perf_status == "READY" else "red")
        
        # Migration validation status
        if all_results.get("migration_validation"):
            migration_status = all_results["migration_validation"].get("migration_status", "UNKNOWN")
            statuses.append(f"Migration Validation: {migration_status}")
            colors.append("green" if migration_status == "PASSED" else "orange" if migration_status == "WARNINGS" else "red")
        
        # Create gauge charts
        fig = make_subplots(
            rows=1, cols=len(statuses),
            subplot_titles=statuses,
            specs=[[{"type": "indicator"}] * len(statuses)]
        )
        
        for i, (status, color) in enumerate(zip(statuses, colors)):
            # Convert status to numeric value for gauge
            value = 100 if "PASSED" in status or "READY" in status else 50 if "PARTIAL" in status or "WARNINGS" in status else 10
            
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=value,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': status.split(":")[0]},
                    gauge={
                        'axis': {'range': [None, 100]},
                        'bar': {'color': color},
                        'steps': [
                            {'range': [0, 50], 'color': "lightgray"},
                            {'range': [50, 100], 'color': "gray"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 90
                        }
                    }
                ),
                row=1, col=i+1
            )
        
        fig.update_layout(
            title="Test Suite Status Dashboard",
            height=400,
            showlegend=False
        )
        
        fig.write_html(self.charts_dir / "status_dashboard.html")
    
    async def _create_coverage_visualization(self, all_results: Dict[str, Any]) -> None:
        """Create test coverage visualization"""
        if not all_results.get("comprehensive_tests", {}).get("results_by_category"):
            return
        
        categories = all_results["comprehensive_tests"]["results_by_category"]
        
        category_names = []
        total_tests = []
        passed_tests = []
        failed_tests = []
        
        for category, results in categories.items():
            category_names.append(category)
            total_tests.append(results.get("total", 0))
            passed_tests.append(results.get("passed", 0))
            failed_tests.append(results.get("failed", 0))
        
        # Create stacked bar chart
        fig = go.Figure(data=[
            go.Bar(name='Passed', x=category_names, y=passed_tests, marker_color='green'),
            go.Bar(name='Failed', x=category_names, y=failed_tests, marker_color='red'),
            go.Bar(name='Skipped', x=category_names, y=[t-p-f for t, p, f in zip(total_tests, passed_tests, failed_tests)], marker_color='gray')
        ])
        
        fig.update_layout(
            barmode='stack',
            title='Test Coverage by Category',
            xaxis_title='Test Categories',
            yaxis_title='Number of Tests',
            height=500
        )
        
        fig.write_html(self.charts_dir / "test_coverage.html")
    
    async def _create_performance_visualization(self, perf_data: Dict[str, Any]) -> None:
        """Create performance visualization"""
        if not perf_data.get("load_test_results"):
            return
        
        load_results = perf_data["load_test_results"]
        
        users = [result["concurrent_users"] for result in load_results]
        response_times = [result["avg_response_time_ms"] for result in load_results]
        throughput = [result["throughput_ops_per_sec"] for result in load_results]
        
        # Create subplot with two y-axes
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Scatter(x=users, y=response_times, name="Response Time (ms)", line=dict(color="red")),
            secondary_y=False,
        )
        
        fig.add_trace(
            go.Scatter(x=users, y=throughput, name="Throughput (ops/sec)", line=dict(color="blue")),
            secondary_y=True,
        )
        
        fig.update_xaxes(title_text="Concurrent Users")
        fig.update_yaxes(title_text="Response Time (ms)", secondary_y=False, title_font_color="red")
        fig.update_yaxes(title_text="Throughput (ops/sec)", secondary_y=True, title_font_color="blue")
        
        fig.update_layout(
            title="Performance vs Load",
            height=500
        )
        
        fig.write_html(self.charts_dir / "performance_trends.html")
    
    async def _create_success_rate_analysis(self, all_results: Dict[str, Any]) -> None:
        """Create success rate analysis visualization"""
        success_rates = []
        labels = []
        
        # Collect success rates from different test types
        if all_results.get("comprehensive_tests", {}).get("summary"):
            success_rates.append(all_results["comprehensive_tests"]["summary"].get("success_rate", 0) * 100)
            labels.append("Comprehensive Tests")
        
        if all_results.get("performance_tests", {}).get("metrics_summary"):
            success_rates.append(all_results["performance_tests"]["metrics_summary"].get("average_success_rate", 0) * 100)
            labels.append("Performance Tests")
        
        if all_results.get("migration_validation", {}).get("summary"):
            success_rates.append(all_results["migration_validation"]["summary"].get("success_rate", 0) * 100)
            labels.append("Migration Validation")
        
        if success_rates:
            # Create horizontal bar chart
            colors = ['green' if rate >= 95 else 'orange' if rate >= 80 else 'red' for rate in success_rates]
            
            fig = go.Figure(go.Bar(
                x=success_rates,
                y=labels,
                orientation='h',
                marker_color=colors,
                text=[f"{rate:.1f}%" for rate in success_rates],
                textposition='inside'
            ))
            
            fig.update_layout(
                title="Success Rate Analysis",
                xaxis_title="Success Rate (%)",
                height=400,
                xaxis=dict(range=[0, 100])
            )
            
            # Add target line at 95%
            fig.add_vline(x=95, line_dash="dash", line_color="red", 
                         annotation_text="Target (95%)", annotation_position="top")
            
            fig.write_html(self.charts_dir / "success_rate_analysis.html")
    
    async def _create_risk_heatmap(self, all_results: Dict[str, Any]) -> None:
        """Create risk assessment heatmap"""
        # Define risk categories and their scores
        risk_categories = ["Database Migration", "Performance", "Reliability", "Compatibility", "Code Integration"]
        risk_levels = ["Low", "Medium", "High", "Critical"]
        
        # Create risk matrix (simplified for demonstration)
        risk_matrix = []
        
        # Assess risks based on test results
        migration_risk = 0  # Low risk
        if all_results.get("migration_validation", {}).get("critical_issues"):
            migration_risk = 3 if len(all_results["migration_validation"]["critical_issues"]) > 2 else 2
        
        performance_risk = 0
        if all_results.get("performance_tests", {}).get("production_readiness", {}).get("performance_grade") in ["NEEDS_IMPROVEMENT", "POOR"]:
            performance_risk = 2
        
        reliability_risk = 1  # Default medium
        if all_results.get("comprehensive_tests", {}).get("summary", {}).get("failed_tests", 0) > 3:
            reliability_risk = 2
        
        compatibility_risk = 0
        code_integration_risk = 1  # Default medium
        
        risk_scores = [migration_risk, performance_risk, reliability_risk, compatibility_risk, code_integration_risk]
        
        # Create heatmap data
        z = [[score] for score in risk_scores]
        
        fig = go.Figure(data=go.Heatmap(
            z=z,
            y=risk_categories,
            x=["Risk Level"],
            colorscale=[[0, 'green'], [0.33, 'yellow'], [0.66, 'orange'], [1, 'red']],
            colorbar=dict(
                tickmode="array",
                tickvals=[0, 1, 2, 3],
                ticktext=risk_levels
            )
        ))
        
        fig.update_layout(
            title="Risk Assessment Heatmap",
            height=400,
            xaxis_title="",
            yaxis_title="Risk Categories"
        )
        
        fig.write_html(self.charts_dir / "risk_heatmap.html")
    
    async def _assess_production_readiness(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Assess production readiness based on all test results"""
        self.logger.info("🎯 Assessing production readiness...")
        
        assessment = {
            "overall_readiness": "NOT_READY",
            "readiness_score": 0,
            "critical_blockers": [],
            "required_actions": [],
            "optional_improvements": [],
            "deployment_risk": "HIGH",
            "confidence_level": "LOW",
            "timeline_estimate": "UNKNOWN"
        }
        
        try:
            # Define readiness criteria
            criteria_scores = {}
            
            # Comprehensive test success rate (weight: 30%)
            if all_results.get("comprehensive_tests", {}).get("summary"):
                comp_summary = all_results["comprehensive_tests"]["summary"]
                success_rate = comp_summary.get("success_rate", 0)
                criteria_scores["comprehensive_tests"] = min(success_rate * 100, 100) * 0.3
                
                if success_rate < 0.95:
                    assessment["critical_blockers"].append("Comprehensive test success rate below 95%")
                if success_rate < 0.9:
                    assessment["required_actions"].append("Fix failing comprehensive tests")
            
            # Performance test results (weight: 25%)
            if all_results.get("performance_tests", {}).get("production_readiness"):
                perf_ready = all_results["performance_tests"]["production_readiness"]
                grade_scores = {"EXCELLENT": 100, "GOOD": 85, "ACCEPTABLE": 70, "NEEDS_IMPROVEMENT": 40, "POOR": 20}
                perf_score = grade_scores.get(perf_ready.get("performance_grade", "POOR"), 0)
                criteria_scores["performance"] = perf_score * 0.25
                
                if perf_ready.get("overall_status") != "READY":
                    assessment["critical_blockers"].append("Performance tests indicate system not ready")
                
                if perf_ready.get("performance_grade") in ["NEEDS_IMPROVEMENT", "POOR"]:
                    assessment["required_actions"].append("Address performance optimization recommendations")
            
            # Migration validation (weight: 25%)
            if all_results.get("migration_validation"):
                migration = all_results["migration_validation"]
                migration_scores = {"PASSED": 100, "WARNINGS": 75, "FAILED": 0}
                migration_score = migration_scores.get(migration.get("migration_status", "FAILED"), 0)
                criteria_scores["migration"] = migration_score * 0.25
                
                if not migration.get("production_ready", False):
                    assessment["critical_blockers"].append("Database migration validation failed")
                
                if migration.get("critical_issues"):
                    assessment["required_actions"].extend(migration["critical_issues"][:3])
            
            # Error handling and reliability (weight: 20%)
            if all_results.get("comprehensive_tests", {}).get("results_by_category", {}).get("Error Handling"):
                error_tests = all_results["comprehensive_tests"]["results_by_category"]["Error Handling"]
                error_success_rate = error_tests.get("passed", 0) / max(error_tests.get("total", 1), 1)
                criteria_scores["reliability"] = error_success_rate * 100 * 0.2
                
                if error_success_rate < 0.9:
                    assessment["required_actions"].append("Improve error handling test coverage")
            
            # Calculate overall readiness score
            assessment["readiness_score"] = sum(criteria_scores.values())
            
            # Determine readiness level
            if assessment["readiness_score"] >= 90 and not assessment["critical_blockers"]:
                assessment["overall_readiness"] = "READY"
                assessment["deployment_risk"] = "LOW"
                assessment["confidence_level"] = "HIGH"
                assessment["timeline_estimate"] = "IMMEDIATE"
            elif assessment["readiness_score"] >= 80 and len(assessment["critical_blockers"]) <= 1:
                assessment["overall_readiness"] = "MOSTLY_READY"
                assessment["deployment_risk"] = "MEDIUM"
                assessment["confidence_level"] = "MEDIUM_HIGH"
                assessment["timeline_estimate"] = "1-2 WEEKS"
            elif assessment["readiness_score"] >= 70:
                assessment["overall_readiness"] = "NEEDS_WORK"
                assessment["deployment_risk"] = "MEDIUM_HIGH"
                assessment["confidence_level"] = "MEDIUM"
                assessment["timeline_estimate"] = "2-4 WEEKS"
            elif assessment["readiness_score"] >= 50:
                assessment["overall_readiness"] = "SIGNIFICANT_ISSUES"
                assessment["deployment_risk"] = "HIGH"
                assessment["confidence_level"] = "LOW"
                assessment["timeline_estimate"] = "1-2 MONTHS"
            else:
                assessment["overall_readiness"] = "NOT_READY"
                assessment["deployment_risk"] = "VERY_HIGH"
                assessment["confidence_level"] = "VERY_LOW"
                assessment["timeline_estimate"] = "2+ MONTHS"
            
            # Add optional improvements
            if assessment["readiness_score"] >= 70:
                assessment["optional_improvements"] = [
                    "Add more edge case testing",
                    "Implement comprehensive monitoring",
                    "Create detailed runbooks",
                    "Set up automated alerting"
                ]
            
            assessment["criteria_breakdown"] = criteria_scores
            
        except Exception as e:
            self.logger.error(f"Error assessing production readiness: {e}")
            assessment["assessment_error"] = str(e)
        
        return assessment
    
    async def _generate_recommendations(self, all_results: Dict[str, Any], production_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive recommendations"""
        self.logger.info("💡 Generating recommendations...")
        
        recommendations = {
            "immediate_actions": [],
            "short_term_improvements": [],
            "long_term_enhancements": [],
            "monitoring_recommendations": [],
            "deployment_strategy": {},
            "rollback_plan": [],
            "success_metrics": []
        }
        
        try:
            # Immediate actions based on critical blockers
            if production_assessment.get("critical_blockers"):
                recommendations["immediate_actions"] = [
                    f"🚫 CRITICAL: {blocker}" for blocker in production_assessment["critical_blockers"][:5]
                ]
            
            # Add required actions
            if production_assessment.get("required_actions"):
                recommendations["immediate_actions"].extend([
                    f"🔧 REQUIRED: {action}" for action in production_assessment["required_actions"][:3]
                ])
            
            # Short-term improvements from test results
            if all_results.get("performance_tests", {}).get("recommendations"):
                recommendations["short_term_improvements"].extend([
                    f"⚡ Performance: {rec}" for rec in all_results["performance_tests"]["recommendations"][:3]
                ])
            
            if all_results.get("migration_validation", {}).get("recommendations"):
                recommendations["short_term_improvements"].extend([
                    f"🔄 Migration: {rec}" for rec in all_results["migration_validation"]["recommendations"][:3]
                ])
            
            # Long-term enhancements
            recommendations["long_term_enhancements"] = [
                "📊 Implement comprehensive application performance monitoring",
                "🧪 Expand automated testing coverage to include more edge cases",
                "📈 Set up continuous performance benchmarking",
                "🔒 Implement advanced security testing",
                "📚 Create comprehensive documentation and runbooks"
            ]
            
            # Monitoring recommendations
            recommendations["monitoring_recommendations"] = [
                "📊 Monitor database query performance and connection pooling",
                "🔍 Set up alerts for failed recipe executions",
                "📈 Track system resource utilization (CPU, memory, disk)",
                "⚠️ Monitor error rates and response times",
                "📋 Implement health checks for all critical services"
            ]
            
            # Deployment strategy based on readiness
            readiness = production_assessment.get("overall_readiness", "NOT_READY")
            
            if readiness == "READY":
                recommendations["deployment_strategy"] = {
                    "approach": "Full deployment with monitoring",
                    "phases": ["Deploy to staging", "Full production deployment"],
                    "rollback_criteria": "Error rate > 5% or performance degradation > 20%"
                }
            elif readiness in ["MOSTLY_READY", "NEEDS_WORK"]:
                recommendations["deployment_strategy"] = {
                    "approach": "Phased deployment with canary testing",
                    "phases": ["Fix critical issues", "Limited user deployment", "Full deployment"],
                    "rollback_criteria": "Any critical functionality failure"
                }
            else:
                recommendations["deployment_strategy"] = {
                    "approach": "Address issues before deployment",
                    "phases": ["Fix all critical blockers", "Rerun validation tests", "Reassess readiness"],
                    "rollback_criteria": "Not applicable - deployment not recommended"
                }
            
            # Rollback plan
            recommendations["rollback_plan"] = [
                "🔄 Maintain database backup before deployment",
                "📋 Document rollback procedures for each component",
                "⚡ Prepare automated rollback scripts",
                "👥 Assign rollback decision authority",
                "📊 Define rollback triggers and monitoring"
            ]
            
            # Success metrics
            recommendations["success_metrics"] = [
                "✅ Zero critical errors in first 24 hours",
                "📈 Response times within 10% of baseline",
                "🔄 All recipe executions complete successfully",
                "📊 Database performance metrics stable",
                "👥 User acceptance testing passes"
            ]
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            recommendations["recommendations_error"] = str(e)
        
        return recommendations
    
    async def _generate_appendices(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate appendices with detailed technical information"""
        appendices = {
            "test_environment_details": test_env.get_session_info(),
            "raw_test_counts": {},
            "error_summaries": {},
            "performance_metrics": {},
            "configuration_details": {}
        }
        
        try:
            # Raw test counts
            if all_results.get("comprehensive_tests", {}).get("summary"):
                appendices["raw_test_counts"]["comprehensive"] = all_results["comprehensive_tests"]["summary"]
            
            if all_results.get("performance_tests", {}).get("metrics_summary"):
                appendices["raw_test_counts"]["performance"] = all_results["performance_tests"]["metrics_summary"]
            
            if all_results.get("migration_validation", {}).get("summary"):
                appendices["raw_test_counts"]["migration"] = all_results["migration_validation"]["summary"]
            
            # Error summaries
            error_summary = {}
            
            if all_results.get("comprehensive_tests", {}).get("detailed_results"):
                failed_tests = [r for r in all_results["comprehensive_tests"]["detailed_results"] 
                              if r.get("status") == "failed"]
                error_summary["comprehensive_test_errors"] = [
                    {"test": t.get("test_name", "Unknown"), "error": t.get("error_message", "Unknown")} 
                    for t in failed_tests[:10]  # Limit to 10
                ]
            
            appendices["error_summaries"] = error_summary
            
        except Exception as e:
            appendices["appendices_error"] = str(e)
        
        return appendices
    
    async def _generate_json_report(self, master_report: Dict[str, Any]) -> None:
        """Generate JSON format report"""
        json_file = self.reports_dir / "json" / f"master_test_report_{self.report_id}.json"
        
        with open(json_file, 'w') as f:
            json.dump(master_report, f, indent=2, default=str)
        
        self.logger.info(f"📄 JSON report saved: {json_file}")
    
    async def _generate_html_report(self, master_report: Dict[str, Any]) -> None:
        """Generate HTML format report"""
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Master Test Report - {{ report.report_id }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        .header { background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .status-excellent { color: #4CAF50; }
        .status-good { color: #8BC34A; }
        .status-acceptable { color: #FF9800; }
        .status-poor { color: #F44336; }
        .section { margin: 20px 0; padding: 15px; border-left: 4px solid #ddd; }
        .critical { border-left-color: #F44336; background: #ffebee; }
        .success { border-left-color: #4CAF50; background: #e8f5e8; }
        .warning { border-left-color: #FF9800; background: #fff3e0; }
        ul, ol { padding-left: 20px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric { background: #f9f9f9; padding: 15px; border-radius: 5px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #333; }
        .metric-label { color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 Master Test Report</h1>
        <p><strong>Report ID:</strong> {{ report.report_id }}</p>
        <p><strong>Generated:</strong> {{ report.generation_timestamp }}</p>
        <p><strong>Overall Status:</strong> 
            <span class="status-{{ report.executive_summary.overall_status.lower() }}">
                {{ report.executive_summary.overall_status }}
            </span>
        </p>
    </div>

    <div class="section success">
        <h2>📋 Executive Summary</h2>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{{ "%.1f"|format(report.executive_summary.key_metrics.overall_score) }}</div>
                <div class="metric-label">Overall Score</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ report.executive_summary.confidence_level }}</div>
                <div class="metric-label">Confidence Level</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ report.executive_summary.recommendation }}</div>
                <div class="metric-label">Recommendation</div>
            </div>
        </div>

        {% if report.executive_summary.success_indicators %}
        <h3>✅ Success Indicators</h3>
        <ul>
        {% for indicator in report.executive_summary.success_indicators %}
            <li>{{ indicator }}</li>
        {% endfor %}
        </ul>
        {% endif %}

        {% if report.executive_summary.areas_of_concern %}
        <h3>⚠️ Areas of Concern</h3>
        <ul>
        {% for concern in report.executive_summary.areas_of_concern %}
            <li>{{ concern }}</li>
        {% endfor %}
        </ul>
        {% endif %}
    </div>

    {% if report.executive_summary.critical_findings %}
    <div class="section critical">
        <h2>🚨 Critical Findings</h2>
        <ul>
        {% for finding in report.executive_summary.critical_findings %}
            <li>{{ finding }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    <div class="section">
        <h2>🎯 Production Readiness Assessment</h2>
        <p><strong>Overall Readiness:</strong> {{ report.production_readiness.overall_readiness }}</p>
        <p><strong>Readiness Score:</strong> {{ "%.1f"|format(report.production_readiness.readiness_score) }}/100</p>
        <p><strong>Deployment Risk:</strong> {{ report.production_readiness.deployment_risk }}</p>
        <p><strong>Timeline Estimate:</strong> {{ report.production_readiness.timeline_estimate }}</p>

        {% if report.production_readiness.critical_blockers %}
        <h3>🚫 Critical Blockers</h3>
        <ul>
        {% for blocker in report.production_readiness.critical_blockers %}
            <li>{{ blocker }}</li>
        {% endfor %}
        </ul>
        {% endif %}
    </div>

    <div class="section">
        <h2>💡 Recommendations</h2>
        
        {% if report.recommendations.immediate_actions %}
        <h3>🚨 Immediate Actions Required</h3>
        <ul>
        {% for action in report.recommendations.immediate_actions %}
            <li>{{ action }}</li>
        {% endfor %}
        </ul>
        {% endif %}

        {% if report.recommendations.short_term_improvements %}
        <h3>📈 Short-term Improvements</h3>
        <ul>
        {% for improvement in report.recommendations.short_term_improvements %}
            <li>{{ improvement }}</li>
        {% endfor %}
        </ul>
        {% endif %}

        <h3>🚀 Deployment Strategy</h3>
        <p><strong>Approach:</strong> {{ report.recommendations.deployment_strategy.approach }}</p>
        {% if report.recommendations.deployment_strategy.phases %}
        <p><strong>Phases:</strong></p>
        <ol>
        {% for phase in report.recommendations.deployment_strategy.phases %}
            <li>{{ phase }}</li>
        {% endfor %}
        </ol>
        {% endif %}
    </div>

    <div class="section">
        <h2>📊 Test Coverage Analysis</h2>
        {% if report.detailed_analysis.test_coverage_analysis %}
        <p><strong>Coverage Score:</strong> {{ "%.1f"|format(report.detailed_analysis.test_coverage_analysis.coverage_score) }}%</p>
        
        {% if report.detailed_analysis.test_coverage_analysis.categories_tested %}
        <h3>✅ Categories Tested</h3>
        <ul>
        {% for category in report.detailed_analysis.test_coverage_analysis.categories_tested %}
            <li>{{ category }}</li>
        {% endfor %}
        </ul>
        {% endif %}

        {% if report.detailed_analysis.test_coverage_analysis.coverage_gaps %}
        <h3>❌ Coverage Gaps</h3>
        <ul>
        {% for gap in report.detailed_analysis.test_coverage_analysis.coverage_gaps %}
            <li>{{ gap }}</li>
        {% endfor %}
        </ul>
        {% endif %}
        {% endif %}
    </div>

    <div class="section">
        <h2>📈 Visualizations</h2>
        {% if report.visualizations.charts_created %}
        <p>Generated {{ report.visualizations.charts_created|length }} visualization(s):</p>
        <ul>
        {% for chart in report.visualizations.charts_created %}
            <li><a href="charts/{{ report.visualizations.chart_files[chart] }}">{{ chart|title }}</a></li>
        {% endfor %}
        </ul>
        {% endif %}
    </div>

    <div class="section">
        <h2>📋 Test Environment Details</h2>
        <p><strong>Session ID:</strong> {{ report.test_environment.session_id }}</p>
        <p><strong>Start Time:</strong> {{ report.test_environment.start_time }}</p>
        <p><strong>Workspace:</strong> {{ report.test_environment.workspace }}</p>
        <p><strong>Setup Complete:</strong> {{ "✅ Yes" if report.test_environment.setup_complete else "❌ No" }}</p>
    </div>

    <footer style="margin-top: 40px; padding: 20px; border-top: 1px solid #ddd; color: #666; text-align: center;">
        <p>Generated by ALD Control System Test Framework v1.0</p>
        <p>Report ID: {{ report.report_id }} | Generated: {{ report.generation_timestamp }}</p>
    </footer>
</body>
</html>
        """
        
        template = Template(html_template)
        html_content = template.render(report=master_report)
        
        html_file = self.reports_dir / "html" / f"master_test_report_{self.report_id}.html"
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        self.logger.info(f"🌐 HTML report saved: {html_file}")
    
    async def _generate_markdown_report(self, master_report: Dict[str, Any]) -> None:
        """Generate Markdown format report"""
        md_content = f"""# 🧪 Master Test Report

**Report ID:** {master_report['report_id']}  
**Generated:** {master_report['generation_timestamp']}  
**Overall Status:** {master_report['executive_summary']['overall_status']}

## 📋 Executive Summary

- **Overall Score:** {master_report['executive_summary']['key_metrics']['overall_score']:.1f}/100
- **Confidence Level:** {master_report['executive_summary']['confidence_level']}
- **Recommendation:** {master_report['executive_summary']['recommendation']}

### ✅ Success Indicators
"""
        
        for indicator in master_report['executive_summary'].get('success_indicators', []):
            md_content += f"- {indicator}\n"
        
        if master_report['executive_summary'].get('areas_of_concern'):
            md_content += "\n### ⚠️ Areas of Concern\n"
            for concern in master_report['executive_summary']['areas_of_concern']:
                md_content += f"- {concern}\n"
        
        if master_report['executive_summary'].get('critical_findings'):
            md_content += "\n## 🚨 Critical Findings\n"
            for finding in master_report['executive_summary']['critical_findings']:
                md_content += f"- {finding}\n"
        
        md_content += f"""
## 🎯 Production Readiness Assessment

- **Overall Readiness:** {master_report['production_readiness']['overall_readiness']}
- **Readiness Score:** {master_report['production_readiness']['readiness_score']:.1f}/100
- **Deployment Risk:** {master_report['production_readiness']['deployment_risk']}
- **Timeline Estimate:** {master_report['production_readiness']['timeline_estimate']}
"""
        
        if master_report['production_readiness'].get('critical_blockers'):
            md_content += "\n### 🚫 Critical Blockers\n"
            for blocker in master_report['production_readiness']['critical_blockers']:
                md_content += f"- {blocker}\n"
        
        md_content += "\n## 💡 Recommendations\n"
        
        if master_report['recommendations'].get('immediate_actions'):
            md_content += "\n### 🚨 Immediate Actions Required\n"
            for action in master_report['recommendations']['immediate_actions']:
                md_content += f"- {action}\n"
        
        if master_report['recommendations'].get('short_term_improvements'):
            md_content += "\n### 📈 Short-term Improvements\n"
            for improvement in master_report['recommendations']['short_term_improvements']:
                md_content += f"- {improvement}\n"
        
        md_content += f"""
### 🚀 Deployment Strategy

**Approach:** {master_report['recommendations']['deployment_strategy'].get('approach', 'Not defined')}
"""
        
        if master_report['recommendations']['deployment_strategy'].get('phases'):
            md_content += "\n**Phases:**\n"
            for i, phase in enumerate(master_report['recommendations']['deployment_strategy']['phases'], 1):
                md_content += f"{i}. {phase}\n"
        
        # Add test coverage section
        if master_report['detailed_analysis'].get('test_coverage_analysis'):
            coverage = master_report['detailed_analysis']['test_coverage_analysis']
            md_content += f"""
## 📊 Test Coverage Analysis

**Coverage Score:** {coverage['coverage_score']:.1f}%

### ✅ Categories Tested
"""
            for category in coverage.get('categories_tested', []):
                md_content += f"- {category}\n"
            
            if coverage.get('coverage_gaps'):
                md_content += "\n### ❌ Coverage Gaps\n"
                for gap in coverage['coverage_gaps']:
                    md_content += f"- {gap}\n"
        
        md_content += f"""
## 📈 Visualizations

Generated {len(master_report['visualizations']['charts_created'])} visualization(s):
"""
        
        for chart in master_report['visualizations']['charts_created']:
            chart_file = master_report['visualizations']['chart_files'][chart]
            md_content += f"- [{chart.title()}](charts/{chart_file})\n"
        
        md_content += f"""
## 📋 Test Environment Details

- **Session ID:** {master_report['test_environment']['session_id']}
- **Start Time:** {master_report['test_environment']['start_time']}
- **Workspace:** {master_report['test_environment']['workspace']}
- **Setup Complete:** {"✅ Yes" if master_report['test_environment']['setup_complete'] else "❌ No"}

---

*Generated by ALD Control System Test Framework v1.0*  
*Report ID: {master_report['report_id']} | Generated: {master_report['generation_timestamp']}*
"""
        
        md_file = self.reports_dir / f"master_test_report_{self.report_id}.md"
        with open(md_file, 'w') as f:
            f.write(md_content)
        
        self.logger.info(f"📝 Markdown report saved: {md_file}")
    
    async def _generate_dashboard(self, master_report: Dict[str, Any]) -> None:
        """Generate interactive dashboard"""
        dashboard_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Execution Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; padding: 20px; 
            background-color: #f5f5f5; 
        }}
        .dashboard-container {{ 
            max-width: 1400px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 10px; 
            padding: 30px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
        }}
        .header {{ 
            text-align: center; 
            margin-bottom: 30px; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border-radius: 10px; 
        }}
        .status-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }}
        .status-card {{ 
            background: #f8f9fa; 
            padding: 20px; 
            border-radius: 8px; 
            text-align: center; 
            border-left: 5px solid #007bff; 
        }}
        .status-excellent {{ border-left-color: #28a745; }}
        .status-good {{ border-left-color: #6f42c1; }}
        .status-warning {{ border-left-color: #ffc107; }}
        .status-danger {{ border-left-color: #dc3545; }}
        .chart-container {{ 
            margin: 20px 0; 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 8px; 
        }}
        .metric-value {{ font-size: 2.5em; font-weight: bold; margin-bottom: 10px; }}
        .metric-label {{ font-size: 1.1em; color: #666; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .alert {{ 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 5px; 
        }}
        .alert-success {{ background: #d4edda; border-left: 5px solid #28a745; }}
        .alert-warning {{ background: #fff3cd; border-left: 5px solid #ffc107; }}
        .alert-danger {{ background: #f8d7da; border-left: 5px solid #dc3545; }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="header">
            <h1>🧪 ALD Control System - Test Execution Dashboard</h1>
            <p>Real-time test results and system health monitoring</p>
            <p><strong>Report ID:</strong> {master_report['report_id']}</p>
            <p><strong>Generated:</strong> {master_report['generation_timestamp']}</p>
        </div>

        <div class="status-grid">
            <div class="status-card status-{master_report['executive_summary']['overall_status'].lower()}">
                <div class="metric-value">{master_report['executive_summary']['overall_status']}</div>
                <div class="metric-label">Overall Status</div>
            </div>
            <div class="status-card">
                <div class="metric-value">{master_report['executive_summary']['key_metrics']['overall_score']:.1f}</div>
                <div class="metric-label">Overall Score</div>
            </div>
            <div class="status-card">
                <div class="metric-value">{master_report['production_readiness']['readiness_score']:.1f}</div>
                <div class="metric-label">Readiness Score</div>
            </div>
            <div class="status-card">
                <div class="metric-value">{master_report['executive_summary']['confidence_level']}</div>
                <div class="metric-label">Confidence Level</div>
            </div>
        </div>
"""
        
        # Add alerts section
        if master_report['executive_summary'].get('critical_findings'):
            dashboard_html += '<div class="section"><h2>🚨 Critical Alerts</h2>'
            for finding in master_report['executive_summary']['critical_findings'][:3]:
                dashboard_html += f'<div class="alert alert-danger">🚫 {finding}</div>'
            dashboard_html += '</div>'
        
        if master_report['executive_summary'].get('areas_of_concern'):
            dashboard_html += '<div class="section"><h2>⚠️ Warnings</h2>'
            for concern in master_report['executive_summary']['areas_of_concern'][:3]:
                dashboard_html += f'<div class="alert alert-warning">⚠️ {concern}</div>'
            dashboard_html += '</div>'
        
        if master_report['executive_summary'].get('success_indicators'):
            dashboard_html += '<div class="section"><h2>✅ Success Indicators</h2>'
            for indicator in master_report['executive_summary']['success_indicators'][:3]:
                dashboard_html += f'<div class="alert alert-success">✅ {indicator}</div>'
            dashboard_html += '</div>'
        
        # Add embedded charts section
        dashboard_html += """
        <div class="section">
            <h2>📊 Interactive Charts</h2>
            <div class="chart-container">
                <iframe src="charts/status_dashboard.html" width="100%" height="400" frameborder="0"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>📈 Quick Actions</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <button onclick="location.reload()" style="padding: 15px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    🔄 Refresh Dashboard
                </button>
                <button onclick="window.open('master_test_report_{}.html')" style="padding: 15px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    📋 View Full Report
                </button>
                <button onclick="window.open('master_test_report_{}.md')" style="padding: 15px; background: #6f42c1; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    📝 Download Markdown
                </button>
            </div>
        </div>

        <div class="section">
            <h2>🎯 Production Readiness</h2>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                <p><strong>Overall Readiness:</strong> {}</p>
                <p><strong>Deployment Risk:</strong> {}</p>
                <p><strong>Timeline Estimate:</strong> {}</p>
                <div style="width: 100%; background-color: #e0e0e0; border-radius: 10px; margin-top: 15px;">
                    <div style="width: {}%; background-color: {}; height: 20px; border-radius: 10px; transition: width 0.5s ease-in-out;">
                    </div>
                </div>
                <p style="text-align: center; margin-top: 10px;">{:.1f}% Ready</p>
            </div>
        </div>
    </div>

    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function() {{
            location.reload();
        }}, 300000);
    </script>
</body>
</html>
        """.format(
            self.report_id, self.report_id, 
            master_report['production_readiness']['overall_readiness'],
            master_report['production_readiness']['deployment_risk'],
            master_report['production_readiness']['timeline_estimate'],
            master_report['production_readiness']['readiness_score'],
            "#28a745" if master_report['production_readiness']['readiness_score'] >= 80 else "#ffc107" if master_report['production_readiness']['readiness_score'] >= 60 else "#dc3545",
            master_report['production_readiness']['readiness_score']
        )
        
        dashboard_file = self.reports_dir / "test_execution_dashboard.html"
        with open(dashboard_file, 'w') as f:
            f.write(dashboard_html)
        
        self.logger.info(f"📈 Interactive dashboard saved: {dashboard_file}")
    
    # Helper methods
    def _has_comprehensive_data(self, all_results: Dict[str, Any]) -> bool:
        """Check if comprehensive test data is available"""
        return bool(all_results.get("comprehensive_tests", {}).get("results_by_category"))

# Global report generator instance
report_generator = MasterTestReportGenerator()

async def main():
    """Main report generation execution"""
    print("📊 Starting Master Test Report Generation...")
    
    try:
        # Initialize report generator
        if not await report_generator.initialize():
            print("❌ Report generator initialization failed")
            return
        
        # Generate master report
        master_report = await report_generator.generate_master_report()
        
        # Print summary
        print("\n" + "="*60)
        print("📋 MASTER TEST REPORT GENERATED")
        print("="*60)
        print(f"Report ID: {master_report['report_id']}")
        print(f"Overall Status: {master_report['executive_summary']['overall_status']}")
        print(f"Overall Score: {master_report['executive_summary']['key_metrics']['overall_score']:.1f}/100")
        print(f"Production Readiness: {master_report['production_readiness']['overall_readiness']}")
        print(f"Confidence Level: {master_report['executive_summary']['confidence_level']}")
        print(f"Recommendation: {master_report['executive_summary']['recommendation']}")
        
        print(f"\n📁 Reports Generated:")
        print(f"  - JSON: reports/json/master_test_report_{master_report['report_id']}.json")
        print(f"  - HTML: reports/html/master_test_report_{master_report['report_id']}.html")
        print(f"  - Markdown: reports/master_test_report_{master_report['report_id']}.md")
        print(f"  - Dashboard: reports/test_execution_dashboard.html")
        
        if master_report['visualizations']['charts_created']:
            print(f"\n📈 Visualizations: {len(master_report['visualizations']['charts_created'])} charts created")
        
        print("="*60)
        
    except Exception as e:
        print(f"❌ Master report generation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())