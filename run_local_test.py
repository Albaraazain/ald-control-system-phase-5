#!/usr/bin/env python3
"""
Local testing script for ALD Control System.
Runs the system in simulation mode for development and testing.
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def setup_test_environment(use_real_plc=False, plc_ip=None):
    """Set up environment variables for local testing."""
    
    # Check if .env file exists
    env_file = project_root / '.env'
    if not env_file.exists():
        print("❌ Error: .env file not found!")
        print("Please create a .env file with the following variables:")
        print("  SUPABASE_URL=your_supabase_url")
        print("  SUPABASE_KEY=your_supabase_key")
        print("  MACHINE_ID=your_machine_id")
        sys.exit(1)
    
    # Set PLC mode
    if use_real_plc:
        os.environ["PLC_TYPE"] = "real"
        if plc_ip:
            os.environ["PLC_IP"] = plc_ip
        print(f"🔧 Running in REAL PLC mode (IP: {plc_ip or 'from .env'})")
    else:
        os.environ["PLC_TYPE"] = "simulation"
        print("🔧 Running in SIMULATION mode (no PLC required)")
    
    # Set log level for better debugging
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    print("=" * 60)
    print("ALD Control System - Local Test Mode")
    print("=" * 60)
    print(f"Project Root: {project_root}")
    print(f"PLC Type: {os.environ.get('PLC_TYPE')}")
    if use_real_plc:
        print(f"PLC IP: {os.environ.get('PLC_IP', 'Not set')}")
    print("=" * 60)

def main():
    """Main entry point for local testing."""
    parser = argparse.ArgumentParser(description='Run ALD Control System locally for testing')
    parser.add_argument(
        '--real-plc',
        action='store_true',
        help='Use real PLC connection instead of simulation'
    )
    parser.add_argument(
        '--plc-ip',
        type=str,
        help='PLC IP address (only used with --real-plc)'
    )
    parser.add_argument(
        '--quick-test',
        action='store_true',
        help='Run a quick test of connections and exit'
    )
    
    args = parser.parse_args()
    
    # Setup test environment
    setup_test_environment(use_real_plc=args.real_plc, plc_ip=args.plc_ip)
    
    if args.quick_test:
        # Run quick connection test
        from src.test_connections import run_connection_test
        asyncio.run(run_connection_test())
    else:
        # Run the main application
        from src.main import main as run_main
        try:
            print("\n✅ Starting ALD Control System...")
            print("Press Ctrl+C to stop\n")
            asyncio.run(run_main())
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down gracefully...")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()