#!/usr/bin/env python3
"""
Entry point launcher for the ALD control system.

Adds a simple CLI for:
  - Selecting PLC mode (simulation/real) without editing .env
  - Setting PLC connection (IP/port/hostname/auto-discover)
  - Choosing log level (DEBUG/INFO/etc.)
  - Running a quick "doctor" connectivity test and exiting

Examples:
  - python main.py --demo
  - python main.py --plc real --ip 192.168.1.50 --port 502 --log-level DEBUG
  - python main.py --doctor          # runs connection tests and exits
"""
import sys
import os
import argparse
import asyncio


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="ALD Control System Service")
    parser.add_argument("--plc", choices=["simulation", "real"], help="PLC backend type")
    parser.add_argument("--demo", action="store_true", help="Shortcut for --plc simulation")
    parser.add_argument("--ip", dest="plc_ip", help="PLC IP address")
    parser.add_argument("--port", dest="plc_port", type=int, help="PLC port (default 502)")
    parser.add_argument("--hostname", dest="plc_hostname", help="PLC mDNS/DNS hostname (e.g. plc.local)")
    parser.add_argument("--auto-discover", dest="plc_auto_discover", action="store_true",
                        help="Enable network discovery fallback for DHCP environments")
    parser.add_argument("--byte-order", choices=["abcd", "badc", "cdab", "dcba"], help="PLC byte order")
    parser.add_argument("--log-level", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
                        help="Logging level (default from LOG_LEVEL env or INFO)")
    parser.add_argument("--log-file", help="Path to log file (default: machine_control.log)")
    parser.add_argument("--doctor", action="store_true", help="Run connectivity tests and exit")

    # Connection monitor/health intervals (override env)
    parser.add_argument("--monitor-interval", type=int, help="PLC health check interval (seconds)")
    parser.add_argument("--reconnect-delay", type=int, help="Delay between PLC reconnect attempts (seconds)")
    parser.add_argument("--max-reconnects", type=int, help="Max PLC reconnect attempts before cooldown")
    parser.add_argument("--reconnect-cooldown", type=int, help="Cooldown after max reconnect attempts (seconds)")
    parser.add_argument("--health-update-interval", type=int, help="DB health update interval (seconds)")
    parser.add_argument("--status-log-interval", type=int, help="Periodic status log interval (seconds)")
    return parser.parse_args(argv)


def apply_env_overrides(args):
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

    # Monitor interval overrides
    if args.monitor_interval is not None:
        os.environ["MONITOR_HEALTH_INTERVAL"] = str(args.monitor_interval)
    if args.reconnect_delay is not None:
        os.environ["MONITOR_RECONNECT_DELAY"] = str(args.reconnect_delay)
    if args.max_reconnects is not None:
        os.environ["MONITOR_MAX_RECONNECTS"] = str(args.max_reconnects)
    if args.reconnect_cooldown is not None:
        os.environ["MONITOR_RECONNECT_COOLDOWN"] = str(args.reconnect_cooldown)
    if args.health_update_interval is not None:
        os.environ["HEALTH_UPDATE_INTERVAL"] = str(args.health_update_interval)
    if args.status_log_interval is not None:
        os.environ["STATUS_LOG_INTERVAL"] = str(args.status_log_interval)


def main_cli():
    # Ensure project root on sys.path for `src` imports
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    args = parse_args()
    apply_env_overrides(args)

    # Apply log level dynamically (in case handlers were pre-created elsewhere)
    try:
        from src.log_setup import set_log_level, logger as _logger
        set_log_level(os.environ.get("LOG_LEVEL", "INFO"))
        # Show effective runtime configuration for quick debugging
        plc_type = os.environ.get("PLC_TYPE", "simulation")
        plc_ip = os.environ.get("PLC_IP")
        plc_port = os.environ.get("PLC_PORT")
        plc_host = os.environ.get("PLC_HOSTNAME")
        plc_auto = os.environ.get("PLC_AUTO_DISCOVER", "false")
        log_level = os.environ.get("LOG_LEVEL", "INFO")
        log_file = os.environ.get("LOG_FILE", "machine_control.log")

        _logger.info("ALD Control System starting via CLI")
        _logger.info(
            f"Effective Config -> PLC: {plc_type}, IP: {plc_ip or '-'}, Port: {plc_port or '-'}, "
            f"Hostname: {plc_host or '-'}, Auto-discover: {plc_auto}, LogLevel: {log_level}, LogFile: {log_file}"
        )
    except Exception:
        # Logging setup is best-effort here; service will configure logging as well
        pass

    if args.doctor:
        # Let downstream code know we are running diagnostic-only tests
        os.environ["DOCTOR_MODE"] = "true"
        # Run the connection test suite and exit
        from src.test_connections import run_connection_test
        asyncio.run(run_connection_test())
        return

    # Launch the service
    from src.main import main as service_main
    asyncio.run(service_main())


if __name__ == "__main__":
    main_cli()
