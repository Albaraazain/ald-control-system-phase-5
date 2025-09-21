#!/usr/bin/env python3
"""
Comprehensive Security Assessment Report Generator
Aggregates all security test results and generates executive summary.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

class SecurityAssessmentReportGenerator:
    """Generates comprehensive security assessment reports."""

    def __init__(self):
        self.project_root = Path.cwd()
        self.timestamp = datetime.now()

    def load_test_results(self) -> Dict[str, Any]:
        """Load all security test results."""
        results = {}

        # Load individual test results
        result_files = {
            'credential_security': 'security_validation_results.json',
            'sql_injection': 'sql_injection_test_results.json',
            'plc_security': 'plc_security_test_results.json',
            'race_conditions': 'race_condition_security_results.json',
            'auth_monitoring': 'auth_monitoring_security_results.json'
        }

        for test_name, filename in result_files.items():
            file_path = self.project_root / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        results[test_name] = json.load(f)
                except Exception as e:
                    print(f"⚠️ Error loading {filename}: {e}")
                    results[test_name] = {'status': 'ERROR', 'error': str(e)}
            else:
                results[test_name] = {'status': 'NOT_FOUND'}

        return results

    def calculate_overall_security_score(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall security score from all tests."""

        # Security test weights (importance)
        test_weights = {
            'credential_security': 0.25,  # 25% - Critical for preventing data breaches
            'sql_injection': 0.25,       # 25% - Critical for database security
            'plc_security': 0.20,        # 20% - Important for operational security
            'race_conditions': 0.15,     # 15% - Important for data integrity
            'auth_monitoring': 0.15       # 15% - Important for threat detection
        }

        # Status to score mapping
        status_scores = {
            'PASS': 100,
            'EXCELLENT': 100,
            'GOOD': 85,
            'SECURE': 100,
            'ACCEPTABLE': 70,
            'PARTIAL': 60,
            'NEEDS_IMPROVEMENT': 40,
            'FAIL': 0,
            'VULNERABLE': 20,
            'ERROR': 0,
            'NOT_FOUND': 0
        }

        total_weighted_score = 0
        total_weight = 0
        test_scores = {}

        for test_name, weight in test_weights.items():
            if test_name in results:
                test_result = results[test_name]

                # Extract status from different result formats
                if 'overall' in test_result and 'status' in test_result['overall']:
                    status = test_result['overall']['status']
                elif 'status' in test_result:
                    status = test_result['status']
                else:
                    # Try to infer from individual test statuses
                    statuses = []
                    for key, value in test_result.items():
                        if isinstance(value, dict) and 'status' in value:
                            statuses.append(value['status'])

                    if statuses:
                        # Use worst status as overall
                        if 'FAIL' in statuses or 'VULNERABLE' in statuses:
                            status = 'FAIL'
                        elif 'NEEDS_IMPROVEMENT' in statuses:
                            status = 'NEEDS_IMPROVEMENT'
                        elif 'ACCEPTABLE' in statuses:
                            status = 'ACCEPTABLE'
                        elif 'GOOD' in statuses:
                            status = 'GOOD'
                        else:
                            status = 'EXCELLENT'
                    else:
                        status = 'UNKNOWN'

                score = status_scores.get(status, 50)  # Default 50 for unknown
                test_scores[test_name] = {'status': status, 'score': score, 'weight': weight}

                total_weighted_score += score * weight
                total_weight += weight

        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0

        # Determine overall status
        if overall_score >= 95:
            overall_status = 'EXCELLENT'
            risk_level = 'VERY_LOW'
        elif overall_score >= 85:
            overall_status = 'GOOD'
            risk_level = 'LOW'
        elif overall_score >= 70:
            overall_status = 'ACCEPTABLE'
            risk_level = 'MEDIUM'
        elif overall_score >= 50:
            overall_status = 'NEEDS_IMPROVEMENT'
            risk_level = 'HIGH'
        else:
            overall_status = 'CRITICAL'
            risk_level = 'VERY_HIGH'

        return {
            'overall_score': round(overall_score, 1),
            'overall_status': overall_status,
            'risk_level': risk_level,
            'test_scores': test_scores,
            'total_tests': len(test_weights),
            'passed_tests': len([t for t in test_scores.values() if t['score'] >= 85])
        }

    def generate_recommendations(self, results: Dict[str, Any], assessment: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate security recommendations based on test results."""
        recommendations = []

        # Check credential security
        if 'credential_security' in results:
            cred_result = results['credential_security']
            if cred_result.get('credential_security', {}).get('status') == 'FAIL':
                violations = cred_result.get('credential_security', {}).get('credential_violations', [])
                if violations:
                    recommendations.append({
                        'priority': 'CRITICAL',
                        'category': 'Credential Security',
                        'issue': f'Found {len(violations)} credential security violations',
                        'recommendation': 'Remove hardcoded credentials and replace with environment variables or secure credential management',
                        'files_affected': [v.get('file', 'unknown') for v in violations]
                    })

        # Check race conditions
        if 'race_conditions' in results:
            race_result = results['race_conditions']
            if race_result.get('overall', {}).get('critical_issues', 0) > 0:
                critical_issues = race_result.get('overall', {}).get('critical_issues', 0)
                recommendations.append({
                    'priority': 'HIGH',
                    'category': 'Race Conditions',
                    'issue': f'Found {critical_issues} race condition security issues',
                    'recommendation': 'Implement proper locking mechanisms or atomic operations for async functions with global state',
                    'details': 'Unsafe async patterns detected that could lead to data corruption or security vulnerabilities'
                })

        # Check PLC security
        if 'plc_security' in results:
            plc_result = results['plc_security']
            if plc_result.get('overall', {}).get('status') != 'EXCELLENT':
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'PLC Security',
                    'issue': 'PLC communication security could be enhanced',
                    'recommendation': 'Consider implementing network segmentation, VPN tunnels, or Modbus security extensions for production deployment'
                })

        # Check SQL injection protection
        if 'sql_injection' in results:
            sql_result = results['sql_injection']
            if any(test.get('status') == 'FAIL' for test in sql_result.values() if isinstance(test, dict)):
                recommendations.append({
                    'priority': 'CRITICAL',
                    'category': 'SQL Injection',
                    'issue': 'SQL injection vulnerabilities detected',
                    'recommendation': 'Implement parameterized queries and input validation for all database operations'
                })

        # General recommendations based on overall score
        if assessment['overall_score'] < 85:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Overall Security',
                'issue': f'Overall security score ({assessment["overall_score"]}%) below recommended threshold (85%)',
                'recommendation': 'Implement a comprehensive security improvement plan focusing on the highest priority vulnerabilities'
            })

        return recommendations

    def generate_executive_summary(self, assessment: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
        """Generate executive summary for management."""

        summary = f"""
# SECURITY ASSESSMENT EXECUTIVE SUMMARY

**Assessment Date:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**System:** ALD Control System
**Overall Security Score:** {assessment['overall_score']}%
**Security Status:** {assessment['overall_status']}
**Risk Level:** {assessment['risk_level']}

## Key Findings

✅ **Tests Passed:** {assessment['passed_tests']}/{assessment['total_tests']}
📊 **Overall Security Score:** {assessment['overall_score']}%
🎯 **Risk Level:** {assessment['risk_level']}

## Security Test Results Summary

"""

        # Add individual test results
        for test_name, test_data in assessment['test_scores'].items():
            status_emoji = '✅' if test_data['score'] >= 85 else '⚠️' if test_data['score'] >= 70 else '❌'
            summary += f"- **{test_name.replace('_', ' ').title()}:** {status_emoji} {test_data['status']} ({test_data['score']}%)\n"

        summary += "\n## Priority Recommendations\n\n"

        # Add top recommendations
        critical_recs = [r for r in recommendations if r['priority'] == 'CRITICAL']
        high_recs = [r for r in recommendations if r['priority'] == 'HIGH']

        if critical_recs:
            summary += "### CRITICAL (Immediate Action Required)\n"
            for rec in critical_recs:
                summary += f"- **{rec['category']}:** {rec['issue']}\n"
                summary += f"  *Action:* {rec['recommendation']}\n\n"

        if high_recs:
            summary += "### HIGH PRIORITY\n"
            for rec in high_recs:
                summary += f"- **{rec['category']}:** {rec['issue']}\n"
                summary += f"  *Action:* {rec['recommendation']}\n\n"

        # Add conclusion
        if assessment['overall_score'] >= 85:
            summary += """## Conclusion

The ALD Control System demonstrates a **strong security posture** with comprehensive security measures implemented across multiple layers. The system is well-protected against common attack vectors and follows security best practices.

**Management Action:** Continue current security practices and address any remaining recommendations during regular maintenance cycles.
"""
        else:
            summary += """## Conclusion

The ALD Control System requires **immediate security improvements** to meet enterprise security standards. Several critical vulnerabilities have been identified that pose significant risk to system integrity and data security.

**Management Action:** Prioritize security improvements and allocate resources to address critical and high-priority recommendations immediately.
"""

        return summary

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive security assessment report."""
        print("🚀 Generating comprehensive security assessment report...")
        print("=" * 70)

        # Load all test results
        results = self.load_test_results()

        # Calculate overall assessment
        assessment = self.calculate_overall_security_score(results)

        # Generate recommendations
        recommendations = self.generate_recommendations(results, assessment)

        # Generate executive summary
        executive_summary = self.generate_executive_summary(assessment, recommendations)

        # Compile comprehensive report
        comprehensive_report = {
            'metadata': {
                'assessment_date': self.timestamp.isoformat(),
                'system_name': 'ALD Control System',
                'report_version': '1.0',
                'generated_by': 'Security Testing Specialist Agent'
            },
            'executive_summary': executive_summary,
            'overall_assessment': assessment,
            'detailed_results': results,
            'recommendations': recommendations,
            'test_coverage': {
                'credential_security': 'Comprehensive credential exposure and management testing',
                'sql_injection': 'Database injection vulnerability testing',
                'plc_security': 'Industrial control system communication security',
                'race_conditions': 'Concurrent access and state management security',
                'auth_monitoring': 'Authentication mechanisms and security monitoring'
            }
        }

        # Save comprehensive report
        report_file = self.project_root / 'COMPREHENSIVE_SECURITY_ASSESSMENT_REPORT.json'
        with open(report_file, 'w') as f:
            json.dump(comprehensive_report, f, indent=2)

        # Save executive summary as markdown
        summary_file = self.project_root / 'SECURITY_EXECUTIVE_SUMMARY.md'
        with open(summary_file, 'w') as f:
            f.write(executive_summary)

        # Print summary
        print("📋 COMPREHENSIVE SECURITY ASSESSMENT COMPLETE")
        print("=" * 70)
        print(f"🎯 Overall Security Score: {assessment['overall_score']}%")
        print(f"📊 Security Status: {assessment['overall_status']}")
        print(f"⚠️ Risk Level: {assessment['risk_level']}")
        print(f"✅ Tests Passed: {assessment['passed_tests']}/{assessment['total_tests']}")
        print(f"📋 Recommendations: {len(recommendations)}")

        critical_recs = len([r for r in recommendations if r['priority'] == 'CRITICAL'])
        high_recs = len([r for r in recommendations if r['priority'] == 'HIGH'])

        if critical_recs > 0:
            print(f"🔴 Critical Issues: {critical_recs}")
        if high_recs > 0:
            print(f"🟠 High Priority Issues: {high_recs}")

        print(f"\n📄 Comprehensive Report: {report_file}")
        print(f"📄 Executive Summary: {summary_file}")

        if assessment['overall_status'] in ['EXCELLENT', 'GOOD']:
            print("\n🎉 SECURITY ASSESSMENT PASSED!")
        else:
            print("\n⚠️ SECURITY ASSESSMENT REQUIRES ATTENTION!")

        return comprehensive_report

if __name__ == "__main__":
    generator = SecurityAssessmentReportGenerator()
    report = generator.generate_comprehensive_report()

    # Exit with appropriate code
    overall_status = report['overall_assessment']['overall_status']
    exit_code = 0 if overall_status in ['EXCELLENT', 'GOOD'] else 1
    sys.exit(exit_code)