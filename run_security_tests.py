#!/usr/bin/env python3
"""
Main security test runner for ALD control system.

This script runs the complete security testing suite including:
- Credential security scanning
- Database security testing
- PLC security testing
- Race condition testing
- Security automation pipeline
"""
import asyncio
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# Import security test modules
from tests.security.test_credential_security import run_credential_security_scan
from tests.security.test_database_security import run_database_security_audit
from tests.security.test_plc_security import run_plc_security_audit
from tests.security.test_race_condition_security import run_race_condition_security_audit
from tests.security.security_automation import run_security_pipeline


async def main():
    """Main entry point for security testing."""
    parser = argparse.ArgumentParser(description='ALD Control System Security Test Suite')
    parser.add_argument('--test-type',
                       choices=['all', 'credentials', 'database', 'plc', 'race-conditions', 'automation'],
                       default='all',
                       help='Type of security tests to run')
    parser.add_argument('--plc-host', default='127.0.0.1', help='PLC host for network security tests')
    parser.add_argument('--plc-port', type=int, default=502, help='PLC port for network security tests')
    parser.add_argument('--output', help='Output file for test results')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    print("🔒 ALD Control System Security Test Suite")
    print("=" * 50)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test type: {args.test_type}")
    print()

    test_results = {
        'timestamp': datetime.now().isoformat(),
        'test_type': args.test_type,
        'results': {},
        'summary': {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'overall_success': False
        }
    }

    success_count = 0
    total_count = 0

    try:
        if args.test_type in ['all', 'credentials']:
            print("🔍 Running credential security tests...")
            total_count += 1
            try:
                credential_success = run_credential_security_scan()
                test_results['results']['credential_security'] = {
                    'success': credential_success,
                    'description': 'Credential exposure and secrets detection'
                }
                if credential_success:
                    success_count += 1
                    print("✅ Credential security tests passed")
                else:
                    print("❌ Credential security tests failed")
            except Exception as e:
                print(f"💥 Credential security tests error: {e}")
                test_results['results']['credential_security'] = {
                    'success': False,
                    'error': str(e)
                }

        if args.test_type in ['all', 'database']:
            print("\n🛡️ Running database security tests...")
            total_count += 1
            try:
                database_success = run_database_security_audit()
                test_results['results']['database_security'] = {
                    'success': database_success,
                    'description': 'SQL injection and database security'
                }
                if database_success:
                    success_count += 1
                    print("✅ Database security tests passed")
                else:
                    print("❌ Database security tests failed")
            except Exception as e:
                print(f"💥 Database security tests error: {e}")
                test_results['results']['database_security'] = {
                    'success': False,
                    'error': str(e)
                }

        if args.test_type in ['all', 'plc']:
            print("\n🏭 Running PLC security tests...")
            total_count += 1
            try:
                plc_success = run_plc_security_audit(args.plc_host, args.plc_port)
                test_results['results']['plc_security'] = {
                    'success': plc_success,
                    'description': 'PLC communication and network security',
                    'target_host': args.plc_host,
                    'target_port': args.plc_port
                }
                if plc_success:
                    success_count += 1
                    print("✅ PLC security tests passed")
                else:
                    print("❌ PLC security tests failed")
            except Exception as e:
                print(f"💥 PLC security tests error: {e}")
                test_results['results']['plc_security'] = {
                    'success': False,
                    'error': str(e)
                }

        if args.test_type in ['all', 'race-conditions']:
            print("\n⚡ Running race condition security tests...")
            total_count += 1
            try:
                race_success = await run_race_condition_security_audit()
                test_results['results']['race_condition_security'] = {
                    'success': race_success,
                    'description': 'Race condition and timing attack security'
                }
                if race_success:
                    success_count += 1
                    print("✅ Race condition security tests passed")
                else:
                    print("❌ Race condition security tests failed")
            except Exception as e:
                print(f"💥 Race condition security tests error: {e}")
                test_results['results']['race_condition_security'] = {
                    'success': False,
                    'error': str(e)
                }

        if args.test_type in ['all', 'automation']:
            print("\n🚀 Running comprehensive security automation pipeline...")
            total_count += 1
            try:
                automation_success = await run_security_pipeline()
                test_results['results']['security_automation'] = {
                    'success': automation_success,
                    'description': 'Comprehensive security automation pipeline'
                }
                if automation_success:
                    success_count += 1
                    print("✅ Security automation pipeline passed")
                else:
                    print("❌ Security automation pipeline failed")
            except Exception as e:
                print(f"💥 Security automation pipeline error: {e}")
                test_results['results']['security_automation'] = {
                    'success': False,
                    'error': str(e)
                }

    except KeyboardInterrupt:
        print("\n🛑 Security tests interrupted by user")
        test_results['summary']['interrupted'] = True
    except Exception as e:
        print(f"\n💥 Unexpected error in security test suite: {e}")
        test_results['summary']['error'] = str(e)

    # Calculate summary
    test_results['summary']['total_tests'] = total_count
    test_results['summary']['passed_tests'] = success_count
    test_results['summary']['failed_tests'] = total_count - success_count
    test_results['summary']['success_rate'] = (success_count / total_count * 100) if total_count > 0 else 0
    test_results['summary']['overall_success'] = success_count == total_count

    # Print final summary
    print("\n" + "=" * 50)
    print("🔒 Security Test Suite Summary")
    print("=" * 50)
    print(f"Total tests: {total_count}")
    print(f"Passed: {success_count}")
    print(f"Failed: {total_count - success_count}")
    print(f"Success rate: {test_results['summary']['success_rate']:.1f}%")

    if test_results['summary']['overall_success']:
        print("\n🎉 ALL SECURITY TESTS PASSED")
        print("The ALD control system meets security requirements.")
    else:
        print(f"\n⚠️  SECURITY TESTS FAILED")
        print("Security vulnerabilities detected. Review failed tests and implement fixes.")

        # Show failed tests
        print("\nFailed tests:")
        for test_name, result in test_results['results'].items():
            if not result.get('success', False):
                print(f"  - {test_name}: {result.get('description', 'Security test')}")
                if 'error' in result:
                    print(f"    Error: {result['error']}")

    # Save results to file if specified
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(test_results, f, indent=2)

        print(f"\n📊 Test results saved to: {output_path}")

    # Return appropriate exit code
    return 0 if test_results['summary']['overall_success'] else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n💥 Fatal error in security test suite: {e}")
        sys.exit(1)