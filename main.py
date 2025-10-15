#!/usr/bin/env python3
"""
Simple ALD Control System - 4 Terminal Design
Main launcher that offers choice between 4 independent terminals.

SIMPLE ARCHITECTURE:
- Terminal 1: PLC Read Service (plc_data_service.py)
- Terminal 2: Recipe Service (simple_recipe_service.py)
- Terminal 3: Parameter Service (parameter_service.py)
- Terminal 4: Component Service (component_service.py)

Each terminal has direct PLC access - NO coordination complexity!

Usage:
  python main.py --terminal 1    # Launch Terminal 1 (PLC Read)
  python main.py --terminal 2    # Launch Terminal 2 (Recipe)
  python main.py --terminal 3    # Launch Terminal 3 (Parameter)
  python main.py --terminal 4    # Launch Terminal 4 (Component)

  # OR use dedicated launchers directly:
  python terminal1_launcher.py --demo
  python terminal2_launcher.py --demo
  python terminal3_launcher.py --demo
  python terminal4_launcher.py --demo
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))


def print_banner():
    """Print simple system banner"""
    print("=" * 60)
    print("🤖 ALD CONTROL SYSTEM - SIMPLE 4-TERMINAL DESIGN")
    print("=" * 60)
    print("✅ ARCHITECTURE: Direct PLC access, no coordination complexity")
    print("✅ DEBUGGING: Easy - each terminal independent")
    print("✅ DEPLOYMENT: Simple - just run the terminal you need")
    print("=" * 60)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="ALD Control System - Simple 4-Terminal Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
TERMINAL OPTIONS:
  --terminal 1    PLC Read Service - Continuous PLC data collection
  --terminal 2    Recipe Service - Recipe command execution
  --terminal 3    Parameter Service - Parameter control commands
  --terminal 4    Component Service - Component control commands

EXAMPLES:
  python main.py --terminal 1 --demo          # Terminal 1 in simulation mode
  python main.py --terminal 2 --plc real      # Terminal 2 with real PLC
  python main.py --terminal 3 --ip 192.168.1.50  # Terminal 3 with specific PLC IP
  python main.py --terminal 4 --demo          # Terminal 4 in simulation mode

DIRECT LAUNCHER ALTERNATIVES:
  python terminal1_launcher.py --demo         # Same as --terminal 1 --demo
  python terminal2_launcher.py --demo         # Same as --terminal 2 --demo
  python terminal3_launcher.py --demo         # Same as --terminal 3 --demo
  python terminal4_launcher.py --demo         # Same as --terminal 4 --demo
        """
    )

    # Terminal selection
    parser.add_argument("--terminal", type=int, choices=[1, 2, 3, 4],
                       help="Terminal to launch (1=PLC Read, 2=Recipe, 3=Parameter, 4=Component)")

    # Common PLC options (passed through to terminal launchers)
    parser.add_argument("--plc", choices=["simulation", "real"], help="PLC backend type")
    parser.add_argument("--demo", action="store_true", help="Shortcut for --plc simulation")
    parser.add_argument("--ip", dest="plc_ip", help="PLC IP address")
    parser.add_argument("--port", dest="plc_port", type=int, help="PLC port (default 502)")
    parser.add_argument("--hostname", dest="plc_hostname", help="PLC mDNS/DNS hostname")
    parser.add_argument("--log-level", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
                       help="Logging level")
    parser.add_argument("--doctor", action="store_true", help="Run connectivity tests and exit")

    # Terminal-specific options
    parser.add_argument("--data-interval", type=float, default=1.0,
                       help="[Terminal 1] Data collection interval in seconds")
    parser.add_argument("--machine-id", help="Override machine ID")

    return parser.parse_args()


def apply_env_overrides(args):
    """Apply command line arguments to environment variables"""
    if args.demo:
        os.environ["PLC_TYPE"] = "simulation"
    if args.plc:
        os.environ["PLC_TYPE"] = args.plc
    if args.plc_ip:
        os.environ["PLC_IP"] = args.plc_ip
    if args.plc_port is not None:
        os.environ["PLC_PORT"] = str(args.plc_port)
    if args.plc_hostname:
        os.environ["PLC_HOSTNAME"] = args.plc_hostname
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level
    if args.machine_id:
        os.environ["MACHINE_ID"] = args.machine_id
    if args.data_interval:
        os.environ["TERMINAL1_DATA_INTERVAL"] = str(args.data_interval)


def launch_terminal_1():
    """Launch Terminal 1 - PLC Read Service"""
    print("🔧 Launching Terminal 1 - PLC Read Service")
    print("   Service: plc_data_service.py")
    print("   Function: Continuous PLC data collection every 1 second")
    print("   Database: Updates parameter_value_history table")
    print("-" * 60)

    try:
        from plc_data_service import main as plc_service_main
        asyncio.run(plc_service_main())
    except ImportError as e:
        print(f"❌ Error importing plc_data_service: {e}")
        print("   Make sure plc_data_service.py exists in the project root")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running Terminal 1: {e}")
        sys.exit(1)


def launch_terminal_2():
    """Launch Terminal 2 - Recipe Service"""
    print("🍳 Launching Terminal 2 - Recipe Service")
    print("   Service: simple_recipe_service.py")
    print("   Function: Listen for recipe commands and execute via direct PLC access")
    print("   Database: Monitors recipe_commands table")
    print("-" * 60)

    try:
        from simple_recipe_service import main as recipe_service_main
        asyncio.run(recipe_service_main())
    except ImportError as e:
        print(f"❌ Error importing simple_recipe_service: {e}")
        print("   Make sure simple_recipe_service.py exists in the project root")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running Terminal 2: {e}")
        sys.exit(1)


def launch_terminal_3():
    """Launch Terminal 3 - Parameter Service"""
    print("⚙️ Launching Terminal 3 - Parameter Service")
    print("   Service: parameter_service.py")
    print("   Function: Listen for parameter commands and write via direct PLC access")
    print("   Database: Monitors parameter_control_commands table")
    print("-" * 60)

    try:
        from terminal3_clean import main as parameter_service_main
        asyncio.run(parameter_service_main())
    except ImportError as e:
        print(f"❌ Error importing terminal3_clean: {e}")
        print("   Make sure terminal3_clean.py exists in the project root")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running Terminal 3: {e}")
        sys.exit(1)


def launch_terminal_4():
    """Launch Terminal 4 - Component Service"""
    print("🔧 Launching Terminal 4 - Component Service")
    print("   Service: component_service.py")
    print("   Function: Listen for component commands and control via direct PLC access")
    print("   Database: Monitors component_control_commands table")
    print("-" * 60)

    try:
        from component_service import main as component_service_main
        asyncio.run(component_service_main())
    except ImportError as e:
        print(f"❌ Error importing component_service: {e}")
        print("   Make sure component_service.py exists in the project root")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running Terminal 4: {e}")
        sys.exit(1)


def show_help():
    """Show interactive help for terminal selection"""
    print_banner()
    print("No terminal specified. Please choose a terminal to launch:")
    print()
    print("🔧 TERMINAL 1 - PLC Read Service")
    print("   • Continuous PLC data collection (every 1 second)")
    print("   • Updates parameter_value_history table")
    print("   • Run: python main.py --terminal 1 --demo")
    print()
    print("🍳 TERMINAL 2 - Recipe Service")
    print("   • Listens for recipe commands")
    print("   • Executes recipes with direct PLC control")
    print("   • Run: python main.py --terminal 2 --demo")
    print()
    print("⚙️ TERMINAL 3 - Parameter Service")
    print("   • Listens for parameter control commands")
    print("   • Writes parameters directly to PLC")
    print("   • Run: python main.py --terminal 3 --demo")
    print()
    print("🔧 TERMINAL 4 - Component Service")
    print("   • Listens for component control commands")
    print("   • Controls components directly via PLC")
    print("   • Run: python main.py --terminal 4 --demo")
    print()
    print("💡 TIP: Use --demo for simulation mode, or --plc real for hardware")
    print("💡 TIP: Each terminal can run independently in separate processes")
    print("=" * 60)


def main():
    """Main entry point"""
    args = parse_args()

    # Apply environment overrides
    apply_env_overrides(args)

    # Handle doctor mode
    if args.doctor:
        os.environ["DOCTOR_MODE"] = "true"
        from src.test_connections import run_connection_test
        asyncio.run(run_connection_test())
        return

    if not args.terminal:
        show_help()
        return

    print_banner()

    # Show effective configuration
    plc_type = os.environ.get("PLC_TYPE", "simulation")
    plc_ip = os.environ.get("PLC_IP")
    machine_id = os.environ.get("MACHINE_ID", "default")
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    print(f"Configuration:")
    print(f"  • PLC Type: {plc_type}")
    print(f"  • PLC IP: {plc_ip or 'auto-detect'}")
    print(f"  • Machine ID: {machine_id}")
    print(f"  • Log Level: {log_level}")
    print("=" * 60)

    # Launch the selected terminal
    if args.terminal == 1:
        launch_terminal_1()
    elif args.terminal == 2:
        launch_terminal_2()
    elif args.terminal == 3:
        launch_terminal_3()
    elif args.terminal == 4:
        launch_terminal_4()


if __name__ == "__main__":
    main()
