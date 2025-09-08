#!/usr/bin/env python3
"""
Run Validation - Simple entry point for comprehensive validation
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def print_banner():
    """Print validation banner"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ALD CONTROL SYSTEM PHASE 5                               ║
║                 COMPREHENSIVE VALIDATION SUITE                              ║
║                                                                              ║
║  🧪 Schema Migration Validation                                             ║
║  📊 Database Integration Testing                                            ║
║  🔄 End-to-End Workflow Testing                                            ║
║  📈 Performance & Load Testing                                              ║
║  📋 Comprehensive Test Reporting                                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

def check_requirements():
    """Check if required dependencies are available"""
    required_modules = [
        'asyncio', 'logging', 'pathlib', 'json', 'datetime',
        'pandas', 'matplotlib', 'plotly', 'psutil'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        print("Please install them using: pip install -r requirements.txt")
        return False
    
    return True

def check_environment():
    """Check if environment is properly configured"""
    issues = []
    
    # Check if we're in the right directory
    current_dir = Path.cwd()
    required_files = [
        'database/database.py',
        'plc/manager.py',
        'log_setup.py'
    ]
    
    for file in required_files:
        if not (current_dir / file).exists():
            issues.append(f"Missing required file: {file}")
    
    # Check if database configuration exists
    env_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY']
    for var in env_vars:
        if not os.getenv(var) and not (current_dir / '.env').exists():
            issues.append(f"Missing environment variable or .env file: {var}")
    
    if issues:
        print("❌ Environment issues detected:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    return True

async def run_validation():
    """Run the comprehensive validation suite"""
    try:
        from execute_comprehensive_validation import validation_executor
        
        print("🚀 Starting comprehensive validation...")
        print("This process will take several minutes to complete.\n")
        
        # Execute validation
        result = await validation_executor.execute_comprehensive_validation()
        
        return result
        
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main entry point"""
    print_banner()
    
    print("🔍 Checking requirements...")
    if not check_requirements():
        sys.exit(1)
    
    print("🔍 Checking environment...")
    if not check_environment():
        sys.exit(1)
    
    print("✅ Environment checks passed\n")
    
    # Run validation
    try:
        result = asyncio.run(run_validation())
        
        if result is None:
            sys.exit(3)  # Execution error
        elif result.get('production_readiness') == 'READY':
            print("\n🎉 VALIDATION SUCCESSFUL - SYSTEM READY FOR PRODUCTION!")
            sys.exit(0)
        elif result.get('production_readiness') in ['MOSTLY_READY', 'NEEDS_WORK']:
            print("\n⚠️ VALIDATION COMPLETED WITH WARNINGS - REVIEW REQUIRED")
            sys.exit(1)
        else:
            print("\n❌ VALIDATION FAILED - CRITICAL ISSUES DETECTED")
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Critical error during validation: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()