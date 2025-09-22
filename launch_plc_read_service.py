#!/usr/bin/env python3
"""
Launcher for Simple PLC Read Service (Terminal 1)

This launcher provides easy start/stop/status management for the PLC read service.

Usage:
    python launch_plc_read_service.py           # Start the service
    python launch_plc_read_service.py --status  # Check status
    python launch_plc_read_service.py --help    # Show help
"""
import argparse
import asyncio
import sys
from plc_read_service import SimplePLCReadService
from src.log_setup import get_service_logger

logger = get_service_logger('plc_read_launcher')


async def start_service():
    """Start the PLC read service."""
    logger.info("🔧 Terminal 1: Simple PLC Read Service Launcher")

    service = SimplePLCReadService()

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested")
    except Exception as e:
        logger.error(f"❌ Service failed: {e}", exc_info=True)
        return 1
    finally:
        await service.stop()

    return 0


async def check_status():
    """Check the status of PLC connections and configuration."""
    from src.config import is_core_config_ready, missing_required_keys, MACHINE_ID
    from src.plc.manager import plc_manager

    print("\n🔍 Simple PLC Read Service - Status Check")
    print("=" * 50)

    # Check configuration
    if is_core_config_ready():
        print("✅ Configuration: Ready")
        print(f"   Machine ID: {MACHINE_ID}")
    else:
        missing = missing_required_keys()
        print(f"❌ Configuration: Missing {missing}")
        return 1

    # Check PLC connection
    try:
        plc_success = await plc_manager.initialize()
        if plc_success and plc_manager.is_connected():
            print("✅ PLC Connection: Connected")

            # Test reading parameters
            try:
                params = await plc_manager.read_all_parameters()
                param_count = len(params) if params else 0
                print(f"   Parameters available: {param_count}")
            except Exception as e:
                print(f"⚠️  Parameter read test failed: {e}")
        else:
            print("❌ PLC Connection: Failed")
            return 1
    except Exception as e:
        print(f"❌ PLC Connection: Error - {e}")
        return 1
    finally:
        await plc_manager.disconnect()

    # Check database connectivity
    try:
        from src.db import get_supabase
        supabase = get_supabase()

        # Test database query
        result = supabase.table('component_parameters').select('id').limit(1).execute()
        print("✅ Database Connection: Connected")

    except Exception as e:
        print(f"❌ Database Connection: Error - {e}")
        return 1

    print("\n🎉 All systems ready for PLC reading service!")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Simple PLC Read Service Launcher (Terminal 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch_plc_read_service.py           # Start service
  python launch_plc_read_service.py --status  # Check status
  python launch_plc_read_service.py --help    # Show this help
        """
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Check system status and connectivity'
    )

    args = parser.parse_args()

    if args.status:
        return asyncio.run(check_status())
    else:
        return asyncio.run(start_service())


if __name__ == "__main__":
    sys.exit(main())