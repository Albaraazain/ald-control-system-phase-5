#!/usr/bin/env python3
"""
Terminal 1 Launcher - PLC Data Service

Command-line launcher for Terminal 1 with the same interface as main.py
but focused exclusively on PLC hardware operations.

Usage:
  python terminal1_launcher.py --plc real --ip 192.168.1.50
  python terminal1_launcher.py --demo  # simulation mode
  python terminal1_launcher.py --doctor  # connection test only
"""
import sys
import os
import argparse
import asyncio

# Ensure project root on sys.path for src imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Terminal 1 - PLC Data Service")
    parser.add_argument("--plc", choices=["simulation", "real"], help="PLC backend type")
    parser.add_argument("--demo", action="store_true", help="Shortcut for --plc simulation")
    parser.add_argument("--ip", dest="plc_ip", help="PLC IP address")
    parser.add_argument("--port", dest="plc_port", type=int, help="PLC port (default 502)")
    parser.add_argument("--hostname", dest="plc_hostname", help="PLC mDNS/DNS hostname")
    parser.add_argument("--auto-discover", dest="plc_auto_discover", action="store_true",
                        help="Enable network discovery fallback")
    parser.add_argument("--byte-order", choices=["abcd", "badc", "cdab", "dcba"], help="PLC byte order")
    parser.add_argument("--log-level", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
                        help="Logging level")
    parser.add_argument("--log-file", help="Path to log file")
    parser.add_argument("--doctor", action="store_true", help="Run connectivity tests and exit")

    # Terminal 1 specific options
    parser.add_argument("--data-interval", type=float, default=1.0,
                        help="Data collection interval in seconds (default: 1.0)")
    parser.add_argument("--timing-precision", type=float, default=0.1,
                        help="Timing precision threshold in seconds (default: 0.1)")
    parser.add_argument("--command-timeout", type=float, default=30.0,
                        help="Default command timeout in seconds (default: 30.0)")
    parser.add_argument("--queue-check-interval", type=float, default=0.1,
                        help="Command queue check interval in seconds (default: 0.1)")

    return parser.parse_args(argv)


def apply_env_overrides(args):
    """Apply command line arguments to environment variables."""
    # PLC type shortcuts
    if args.demo:
        os.environ["PLC_TYPE"] = "simulation"
    if args.plc:
        os.environ["PLC_TYPE"] = args.plc

    # PLC connection overrides
    if args.plc_ip:
        os.environ["PLC_IP"] = args.plc_ip
    if args.plc_port is not None:
        os.environ["PLC_PORT"] = str(args.plc_port)
    if args.plc_hostname:
        os.environ["PLC_HOSTNAME"] = args.plc_hostname
    if args.plc_auto_discover:
        os.environ["PLC_AUTO_DISCOVER"] = "true"
    if args.byte_order:
        os.environ["PLC_BYTE_ORDER"] = args.byte_order

    # Logging overrides
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level
    if args.log_file:
        os.environ["LOG_FILE"] = args.log_file

    # Terminal 1 specific overrides
    if args.data_interval:
        os.environ["TERMINAL1_DATA_INTERVAL"] = str(args.data_interval)
    if args.timing_precision:
        os.environ["TERMINAL1_TIMING_PRECISION"] = str(args.timing_precision)
    if args.command_timeout:
        os.environ["TERMINAL1_COMMAND_TIMEOUT"] = str(args.command_timeout)
    if args.queue_check_interval:
        os.environ["TERMINAL1_QUEUE_CHECK_INTERVAL"] = str(args.queue_check_interval)


def main_cli():
    """Main CLI entry point."""
    args = parse_args()
    apply_env_overrides(args)

    # Apply log level dynamically
    try:
        from src.log_setup import set_log_level, logger as _logger
        set_log_level(os.environ.get("LOG_LEVEL", "INFO"))

        # Show effective configuration
        plc_type = os.environ.get("PLC_TYPE", "simulation")
        plc_ip = os.environ.get("PLC_IP")
        plc_port = os.environ.get("PLC_PORT")
        plc_host = os.environ.get("PLC_HOSTNAME")
        log_level = os.environ.get("LOG_LEVEL", "INFO")

        _logger.info("Terminal 1 - PLC Data Service starting")
        _logger.info(
            f"Config -> PLC: {plc_type}, IP: {plc_ip or '-'}, Port: {plc_port or '-'}, "
            f"Hostname: {plc_host or '-'}, LogLevel: {log_level}"
        )
    except Exception:
        # Logging setup is best-effort
        pass

    if args.doctor:
        # Run connection tests and exit
        os.environ["DOCTOR_MODE"] = "true"
        from src.test_connections import run_connection_test
        asyncio.run(run_connection_test())
        return

    # Import and run Terminal 1 service
    from plc_data_service_standalone import main as plc_service_main
    asyncio.run(plc_service_main())


if __name__ == "__main__":
    main_cli()