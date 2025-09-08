#!/usr/bin/env python3
"""
Execute Simulation Tests - Run the comprehensive ALD control system tests

This script executes the complete simulation test suite using real Supabase credentials.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to path
sys.path.insert(0, '/home/albaraa/Projects/ald-control-system-phase-5')

# Supabase configuration
SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzU5OTYzNzUsImV4cCI6MjA1MTU3MjM3NX0.tiMdbAs79ZOS3PhnEUxXq_g5JLLXG8-o_a7VAIN6cd8"

async def main():
    """Execute the comprehensive simulation tests"""
    
    print("🚀 Starting ALD Control System Comprehensive Simulation Tests")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print("=" * 80)
    
    try:
        # Import the comprehensive test suite
        from comprehensive_simulation_test import ComprehensiveSimulationTest
        
        # Initialize and run tests
        test_suite = ComprehensiveSimulationTest(SUPABASE_URL, SUPABASE_KEY)
        report = await test_suite.run_comprehensive_tests()
        
        # Print final results
        print("\n" + "=" * 80)
        print("🎉 SIMULATION TEST SUITE COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
        summary = report['test_results_summary']
        print(f"📊 Test Results:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Passed: {summary['passed_tests']} ✅")
        print(f"   Failed: {summary['failed_tests']} {'❌' if summary['failed_tests'] > 0 else '✅'}")
        print(f"   Success Rate: {summary['success_rate_percentage']:.1f}%")
        print(f"   Duration: {summary['total_test_duration_seconds']:.2f}s")
        
        validation = report['validation_summary']
        print(f"\n🔍 Validation Results:")
        print(f"   Total Validations: {validation['total_validations']}")
        print(f"   Passed: {validation['passed_validations']} ✅")
        print(f"   Failed: {validation['failed_validations']} {'❌' if validation['failed_validations'] > 0 else '✅'}")
        
        print(f"\n📋 Recommendations:")
        for i, rec in enumerate(report.get('recommendations', []), 1):
            print(f"   {i}. {rec}")
        
        # Save final report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"final_simulation_report_{timestamp}.json"
        
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Complete report saved: {report_file}")
        
        return 0 if summary['failed_tests'] == 0 and validation['failed_validations'] == 0 else 1
        
    except Exception as e:
        print(f"\n❌ TEST EXECUTION FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    print(f"\nExiting with code: {exit_code}")
    sys.exit(exit_code)