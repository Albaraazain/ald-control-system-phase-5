#!/usr/bin/env python3
"""
Authentication and Security Monitoring tester for ALD control system.
Tests authentication mechanisms and security monitoring capabilities.
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

class AuthMonitoringSecurityTester:
    """Authentication and monitoring security testing."""

    def __init__(self):
        self.project_root = Path.cwd()

    def test_authentication_mechanisms(self) -> Dict[str, Any]:
        """Test authentication and authorization mechanisms."""
        print("🔍 Testing authentication mechanisms...")

        auth_result = {
            'supabase_auth_configured': False,
            'credential_management_found': False,
            'authentication_patterns': [],
            'authorization_patterns': [],
            'security_status': 'UNKNOWN'
        }

        # Check for authentication files
        auth_files = [
            'src/security/credential_manager.py',
            'src/config.py',
            'src/secure_config.py'
        ]

        for auth_file in auth_files:
            file_path = self.project_root / auth_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Look for authentication patterns
                    if 'supabase' in content.lower():
                        auth_result['supabase_auth_configured'] = True
                        auth_result['authentication_patterns'].append('supabase_authentication')

                    if 'credential' in content.lower() and ('manage' in content.lower() or 'valid' in content.lower()):
                        auth_result['credential_management_found'] = True
                        auth_result['authentication_patterns'].append('credential_management')

                    if 'token' in content.lower() or 'jwt' in content.lower():
                        auth_result['authentication_patterns'].append('token_based_auth')

                    if 'permission' in content.lower() or 'authorize' in content.lower():
                        auth_result['authorization_patterns'].append('permission_based_access')

                    if 'machine_id' in content.lower():
                        auth_result['authorization_patterns'].append('machine_based_auth')

                    if 'validate' in content.lower() and ('input' in content.lower() or 'credential' in content.lower()):
                        auth_result['authentication_patterns'].append('input_validation')

                except Exception as e:
                    print(f"  ⚠️ Error reading {auth_file}: {e}")

        # Remove duplicates
        auth_result['authentication_patterns'] = list(set(auth_result['authentication_patterns']))
        auth_result['authorization_patterns'] = list(set(auth_result['authorization_patterns']))

        # Determine security status
        auth_score = 0
        if auth_result['supabase_auth_configured']:
            auth_score += 30
        if auth_result['credential_management_found']:
            auth_score += 25
        if len(auth_result['authentication_patterns']) >= 3:
            auth_score += 25
        if len(auth_result['authorization_patterns']) >= 1:
            auth_score += 20

        if auth_score >= 80:
            auth_result['security_status'] = 'EXCELLENT'
        elif auth_score >= 60:
            auth_result['security_status'] = 'GOOD'
        elif auth_score >= 40:
            auth_result['security_status'] = 'ACCEPTABLE'
        else:
            auth_result['security_status'] = 'NEEDS_IMPROVEMENT'

        print(f"  📊 Supabase auth: {'✅' if auth_result['supabase_auth_configured'] else '❌'}")
        print(f"  📊 Credential management: {'✅' if auth_result['credential_management_found'] else '❌'}")
        print(f"  📊 Auth patterns: {len(auth_result['authentication_patterns'])}")
        print(f"  📊 Authorization patterns: {len(auth_result['authorization_patterns'])}")
        print(f"  📊 Auth security: {auth_result['security_status']}")

        return auth_result

    def test_security_monitoring_system(self) -> Dict[str, Any]:
        """Test security monitoring and alerting system."""
        print("🔍 Testing security monitoring system...")

        monitoring_result = {
            'monitoring_module_found': False,
            'threat_detection_capabilities': [],
            'alert_mechanisms': [],
            'security_events_defined': 0,
            'real_time_monitoring': False,
            'status': 'UNKNOWN'
        }

        # Check for monitoring files
        monitoring_files = [
            'src/security/monitoring.py',
            'src/security/rate_limiter.py',
            'src/log_setup.py'
        ]

        for monitoring_file in monitoring_files:
            file_path = self.project_root / monitoring_file
            if file_path.exists():
                monitoring_result['monitoring_module_found'] = True

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Look for threat detection capabilities
                    if 'threat' in content.lower():
                        monitoring_result['threat_detection_capabilities'].append('threat_assessment')
                    if 'intrusion' in content.lower():
                        monitoring_result['threat_detection_capabilities'].append('intrusion_detection')
                    if 'anomaly' in content.lower():
                        monitoring_result['threat_detection_capabilities'].append('anomaly_detection')
                    if 'rate_limit' in content.lower():
                        monitoring_result['threat_detection_capabilities'].append('rate_limiting')
                    if 'ip_block' in content.lower() or 'blacklist' in content.lower():
                        monitoring_result['threat_detection_capabilities'].append('ip_blocking')

                    # Look for alert mechanisms
                    if 'alert' in content.lower():
                        monitoring_result['alert_mechanisms'].append('alerting_system')
                    if 'log' in content.lower() and ('security' in content.lower() or 'warn' in content.lower()):
                        monitoring_result['alert_mechanisms'].append('security_logging')
                    if 'email' in content.lower() or 'notification' in content.lower():
                        monitoring_result['alert_mechanisms'].append('notification_system')

                    # Count security events
                    if 'SecurityEvent' in content or 'Event' in content:
                        # Count enum values or event types
                        event_count = content.count('=') if 'class' in content and 'Event' in content else 0
                        monitoring_result['security_events_defined'] = max(monitoring_result['security_events_defined'], event_count)

                    # Check for real-time monitoring
                    if 'async' in content and ('monitor' in content.lower() or 'watch' in content.lower()):
                        monitoring_result['real_time_monitoring'] = True

                except Exception as e:
                    print(f"  ⚠️ Error reading {monitoring_file}: {e}")

        # Remove duplicates
        monitoring_result['threat_detection_capabilities'] = list(set(monitoring_result['threat_detection_capabilities']))
        monitoring_result['alert_mechanisms'] = list(set(monitoring_result['alert_mechanisms']))

        # Determine status
        monitoring_score = 0
        if monitoring_result['monitoring_module_found']:
            monitoring_score += 20
        if len(monitoring_result['threat_detection_capabilities']) >= 3:
            monitoring_score += 30
        if len(monitoring_result['alert_mechanisms']) >= 2:
            monitoring_score += 25
        if monitoring_result['security_events_defined'] >= 5:
            monitoring_score += 15
        if monitoring_result['real_time_monitoring']:
            monitoring_score += 10

        if monitoring_score >= 80:
            monitoring_result['status'] = 'EXCELLENT'
        elif monitoring_score >= 60:
            monitoring_result['status'] = 'GOOD'
        elif monitoring_score >= 40:
            monitoring_result['status'] = 'ACCEPTABLE'
        else:
            monitoring_result['status'] = 'NEEDS_IMPROVEMENT'

        print(f"  📊 Monitoring module: {'✅' if monitoring_result['monitoring_module_found'] else '❌'}")
        print(f"  📊 Threat detection: {len(monitoring_result['threat_detection_capabilities'])} capabilities")
        print(f"  📊 Alert mechanisms: {len(monitoring_result['alert_mechanisms'])}")
        print(f"  📊 Security events: {monitoring_result['security_events_defined']}")
        print(f"  📊 Real-time monitoring: {'✅' if monitoring_result['real_time_monitoring'] else '❌'}")
        print(f"  📊 Monitoring status: {monitoring_result['status']}")

        return monitoring_result

    def test_configuration_security(self) -> Dict[str, Any]:
        """Test configuration security measures."""
        print("🔍 Testing configuration security...")

        config_security = {
            'secure_config_files': [],
            'environment_protection': False,
            'validation_mechanisms': [],
            'security_features': [],
            'status': 'UNKNOWN'
        }

        # Check security configuration files
        config_files = [
            '.security_config.json',
            'src/security/security_config.py',
            'src/secure_config.py'
        ]

        for config_file in config_files:
            file_path = self.project_root / config_file
            if file_path.exists():
                config_security['secure_config_files'].append(config_file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Look for environment protection
                    if 'env' in content.lower() and ('protect' in content.lower() or 'secure' in content.lower()):
                        config_security['environment_protection'] = True

                    # Look for validation mechanisms
                    if 'validate' in content.lower():
                        config_security['validation_mechanisms'].append('input_validation')
                    if 'sanitize' in content.lower():
                        config_security['validation_mechanisms'].append('input_sanitization')
                    if 'encrypt' in content.lower():
                        config_security['validation_mechanisms'].append('encryption')

                    # Look for security features
                    if 'rate_limit' in content.lower():
                        config_security['security_features'].append('rate_limiting')
                    if 'timeout' in content.lower():
                        config_security['security_features'].append('timeout_protection')
                    if 'permission' in content.lower():
                        config_security['security_features'].append('permission_control')
                    if 'monitor' in content.lower():
                        config_security['security_features'].append('monitoring')

                except Exception as e:
                    print(f"  ⚠️ Error reading {config_file}: {e}")

        # Remove duplicates
        config_security['validation_mechanisms'] = list(set(config_security['validation_mechanisms']))
        config_security['security_features'] = list(set(config_security['security_features']))

        # Determine status
        config_score = 0
        if len(config_security['secure_config_files']) >= 2:
            config_score += 30
        if config_security['environment_protection']:
            config_score += 25
        if len(config_security['validation_mechanisms']) >= 2:
            config_score += 25
        if len(config_security['security_features']) >= 3:
            config_score += 20

        if config_score >= 80:
            config_security['status'] = 'EXCELLENT'
        elif config_score >= 60:
            config_security['status'] = 'GOOD'
        elif config_score >= 40:
            config_security['status'] = 'ACCEPTABLE'
        else:
            config_security['status'] = 'NEEDS_IMPROVEMENT'

        print(f"  📊 Secure config files: {len(config_security['secure_config_files'])}")
        print(f"  📊 Environment protection: {'✅' if config_security['environment_protection'] else '❌'}")
        print(f"  📊 Validation mechanisms: {len(config_security['validation_mechanisms'])}")
        print(f"  📊 Security features: {len(config_security['security_features'])}")
        print(f"  📊 Config security: {config_security['status']}")

        return config_security

    def run_auth_monitoring_security_tests(self) -> Dict[str, Any]:
        """Run comprehensive authentication and monitoring security tests."""
        print("🚀 Starting authentication and monitoring security testing...")
        print("=" * 70)

        results = {
            'authentication': self.test_authentication_mechanisms(),
            'monitoring': self.test_security_monitoring_system(),
            'configuration': self.test_configuration_security()
        }

        # Calculate overall security status
        security_scores = {
            'EXCELLENT': 100,
            'GOOD': 80,
            'ACCEPTABLE': 60,
            'NEEDS_IMPROVEMENT': 40,
            'UNKNOWN': 20
        }

        total_score = 0
        valid_tests = 0

        for test_result in results.values():
            status = test_result.get('status', test_result.get('security_status', 'UNKNOWN'))
            if status in security_scores:
                total_score += security_scores[status]
                valid_tests += 1

        if valid_tests > 0:
            average_score = total_score / valid_tests
            if average_score >= 90:
                overall_status = 'EXCELLENT'
            elif average_score >= 75:
                overall_status = 'GOOD'
            elif average_score >= 60:
                overall_status = 'ACCEPTABLE'
            else:
                overall_status = 'NEEDS_IMPROVEMENT'
        else:
            overall_status = 'UNKNOWN'

        results['overall'] = {
            'security_score': average_score if valid_tests > 0 else 0,
            'status': overall_status,
            'tests_completed': len(results) - 1,
            'excellent_tests': len([r for r in results.values() if r.get('status', r.get('security_status')) == 'EXCELLENT']),
            'good_tests': len([r for r in results.values() if r.get('status', r.get('security_status')) == 'GOOD'])
        }

        print("=" * 70)
        print("📋 AUTHENTICATION & MONITORING SECURITY SUMMARY")
        print("=" * 70)
        print(f"🎯 Overall Security Score: {results['overall']['security_score']:.1f}%")
        print(f"📊 Status: {overall_status}")
        print(f"✅ Excellent tests: {results['overall']['excellent_tests']}")
        print(f"🟡 Good tests: {results['overall']['good_tests']}")
        print(f"📊 Total tests: {results['overall']['tests_completed']}")

        if overall_status in ['EXCELLENT', 'GOOD']:
            print("🎉 Authentication and monitoring security testing PASSED!")
        else:
            print("⚠️ Authentication and monitoring security needs improvement!")

        # Save results
        results_file = self.project_root / 'auth_monitoring_security_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"📄 Results saved to: {results_file}")

        return results

if __name__ == "__main__":
    tester = AuthMonitoringSecurityTester()
    results = tester.run_auth_monitoring_security_tests()

    # Exit with appropriate code
    overall_status = results['overall']['status']
    exit_code = 0 if overall_status in ['EXCELLENT', 'GOOD'] else 1
    sys.exit(exit_code)