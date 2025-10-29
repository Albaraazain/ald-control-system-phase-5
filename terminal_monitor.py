#!/usr/bin/env python3
"""
Terminal Monitor Service

Monitors all terminal instances for health and automatically recovers crashed terminals.

Features:
- Dead terminal detection (missed heartbeats)
- Automatic terminal restart on crash
- Health status reporting
- Alert logging for operational issues
- Configurable monitoring intervals

Usage:
    python terminal_monitor.py --check-interval 30 --heartbeat-timeout 30
"""

import asyncio
import os
import sys
import argparse
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.log_setup import get_service_logger
from src.db import get_supabase
from src.config import MACHINE_ID

logger = get_service_logger('agents')


class TerminalMonitor:
    """
    Terminal Monitor Service

    Monitors terminal instances and performs automatic recovery for crashed terminals.
    """

    def __init__(
        self,
        machine_id: str,
        check_interval: int = 30,
        heartbeat_timeout: int = 30,
        auto_recovery: bool = True,
        restart_delay: int = 5
    ):
        """
        Initialize Terminal Monitor.

        Args:
            machine_id: Machine UUID to monitor terminals for
            check_interval: Seconds between health checks (default 30)
            heartbeat_timeout: Seconds before considering terminal dead (default 30)
            auto_recovery: Enable automatic terminal restart (default True)
            restart_delay: Seconds to wait before restarting crashed terminal (default 5)
        """
        self.machine_id = machine_id
        self.check_interval = check_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.auto_recovery = auto_recovery
        self.restart_delay = restart_delay

        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.supabase = get_supabase()

        # Terminal launch commands
        self.terminal_commands = {
            'terminal1': f'python plc_data_service.py --demo',
            'terminal2': f'python simple_recipe_service.py --demo',
            'terminal3': f'python terminal3_clean.py'
        }

        # Recovery tracking
        self.recovery_attempts: Dict[str, int] = {}
        self.max_recovery_attempts = 3
        self.recovery_backoff = [5, 15, 30]  # Seconds between retries

        logger.info(f"🔍 Terminal Monitor initialized for machine {machine_id}")
        logger.info(f"   Check interval: {check_interval}s")
        logger.info(f"   Heartbeat timeout: {heartbeat_timeout}s")
        logger.info(f"   Auto-recovery: {'ENABLED' if auto_recovery else 'DISABLED'}")

    async def start(self):
        """Start the terminal monitor service."""
        if self.is_running:
            logger.warning("Terminal Monitor already running")
            return

        try:
            self.is_running = True
            logger.info("🚀 Terminal Monitor started")

            # Start monitoring loop
            self.monitor_task = asyncio.create_task(self._monitoring_loop())
            await self.monitor_task

        except Exception as e:
            logger.error(f"Error in Terminal Monitor: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self):
        """Stop the terminal monitor service."""
        if not self.is_running:
            return

        try:
            logger.info("🛑 Stopping Terminal Monitor...")
            self.is_running = False

            # Cancel monitor task
            if self.monitor_task and not self.monitor_task.done():
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass

            logger.info("✅ Terminal Monitor stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping Terminal Monitor: {e}", exc_info=True)

    async def _monitoring_loop(self):
        """Main monitoring loop that checks terminal health."""
        logger.info(f"🔄 Monitoring loop started (checking every {self.check_interval}s)")

        while self.is_running:
            try:
                # Check for dead terminals
                dead_terminals = await self._detect_dead_terminals()

                if dead_terminals:
                    logger.warning(f"⚠️  Detected {len(dead_terminals)} dead terminal(s)")

                    for terminal in dead_terminals:
                        await self._handle_dead_terminal(terminal)
                else:
                    logger.debug("✅ All terminals healthy")

                # Check for degraded terminals
                degraded_terminals = await self._detect_degraded_terminals()

                if degraded_terminals:
                    logger.warning(f"⚠️  Detected {len(degraded_terminals)} degraded terminal(s)")
                    for terminal in degraded_terminals:
                        logger.warning(
                            f"   Terminal {terminal['terminal_type']} (PID: {terminal['process_id']}): "
                            f"{terminal['errors_encountered']} errors"
                        )

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                # Continue monitoring despite errors
                await asyncio.sleep(self.check_interval)

    async def _detect_dead_terminals(self) -> List[Dict]:
        """
        Detect terminals that have missed heartbeats.

        Returns:
            List of dead terminal records
        """
        try:
            # Use database function to detect dead terminals
            result = self.supabase.rpc(
                'detect_dead_terminals',
                params={'heartbeat_timeout_seconds': self.heartbeat_timeout}
            ).execute()

            dead_terminals = result.data if result.data else []

            # Filter for our machine
            return [
                t for t in dead_terminals
                if t['machine_id'] == self.machine_id
            ]

        except Exception as e:
            logger.error(f"Error detecting dead terminals: {e}", exc_info=True)
            return []

    async def _detect_degraded_terminals(self) -> List[Dict]:
        """
        Detect terminals in degraded state (high error rate).

        Returns:
            List of degraded terminal records
        """
        try:
            result = self.supabase.table('terminal_instances').select('*').eq(
                'machine_id', self.machine_id
            ).eq(
                'status', 'degraded'
            ).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error detecting degraded terminals: {e}", exc_info=True)
            return []

    async def _handle_dead_terminal(self, terminal: Dict):
        """
        Handle a dead terminal by marking it as crashed and attempting recovery.

        Args:
            terminal: Terminal record from detect_dead_terminals
        """
        terminal_id = terminal['terminal_id']
        terminal_type = terminal['terminal_type']
        process_id = terminal['process_id']
        seconds_since_heartbeat = terminal['seconds_since_heartbeat']

        logger.error(
            f"💀 Dead terminal detected: {terminal_type}\n"
            f"   Terminal ID: {terminal_id}\n"
            f"   PID: {process_id}\n"
            f"   Last heartbeat: {seconds_since_heartbeat}s ago"
        )

        # Mark terminal as crashed
        try:
            self.supabase.rpc(
                'mark_terminal_crashed',
                params={
                    'terminal_instance_id': terminal_id,
                    'crash_reason': f'Missed heartbeats (timeout: {seconds_since_heartbeat}s)'
                }
            ).execute()

            logger.info(f"✅ Marked {terminal_type} as crashed in database")

        except Exception as e:
            logger.error(f"Failed to mark terminal as crashed: {e}", exc_info=True)

        # Attempt auto-recovery if enabled
        if self.auto_recovery:
            await self._attempt_recovery(terminal_type, terminal_id)
        else:
            logger.warning(f"⚠️  Auto-recovery disabled - manual intervention required for {terminal_type}")

    async def _attempt_recovery(self, terminal_type: str, terminal_id: str):
        """
        Attempt to restart a crashed terminal.

        Args:
            terminal_type: Type of terminal to restart
            terminal_id: Terminal instance ID that crashed
        """
        # Track recovery attempts
        attempts = self.recovery_attempts.get(terminal_type, 0)

        if attempts >= self.max_recovery_attempts:
            logger.error(
                f"❌ Maximum recovery attempts ({self.max_recovery_attempts}) reached for {terminal_type}\n"
                f"   Manual intervention required"
            )
            return

        self.recovery_attempts[terminal_type] = attempts + 1
        delay = self.recovery_backoff[min(attempts, len(self.recovery_backoff) - 1)]

        logger.info(
            f"🔄 Attempting recovery for {terminal_type} (attempt {attempts + 1}/{self.max_recovery_attempts})\n"
            f"   Waiting {delay}s before restart..."
        )

        await asyncio.sleep(delay)

        # Get launch command
        command = self.terminal_commands.get(terminal_type)
        if not command:
            logger.error(f"❌ No launch command configured for {terminal_type}")
            return

        # Launch terminal in background
        try:
            # Set environment variables
            env = os.environ.copy()
            env['MACHINE_ID'] = self.machine_id
            env['PLC_TYPE'] = 'simulation'

            # Launch terminal as background process
            process = await asyncio.create_subprocess_shell(
                f"{command} > /tmp/{terminal_type}_recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log 2>&1 &",
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            logger.info(
                f"✅ Recovery initiated for {terminal_type}\n"
                f"   Command: {command}\n"
                f"   The terminal should self-register within 10s"
            )

            # Wait a bit to see if it registers successfully
            await asyncio.sleep(10)

            # Check if terminal registered
            result = self.supabase.table('terminal_instances').select('*').eq(
                'terminal_type', terminal_type
            ).eq(
                'machine_id', self.machine_id
            ).eq(
                'status', 'healthy'
            ).order('started_at', desc=True).limit(1).execute()

            if result.data:
                logger.info(f"✅ {terminal_type} recovered successfully!")
                # Reset recovery attempts on success
                self.recovery_attempts[terminal_type] = 0
            else:
                logger.warning(f"⚠️  {terminal_type} recovery uncertain - will check on next monitoring cycle")

        except Exception as e:
            logger.error(f"❌ Failed to restart {terminal_type}: {e}", exc_info=True)

    def get_status(self) -> Dict:
        """Get current monitor status."""
        return {
            'service_name': 'Terminal Monitor',
            'is_running': self.is_running,
            'machine_id': self.machine_id,
            'check_interval': self.check_interval,
            'heartbeat_timeout': self.heartbeat_timeout,
            'auto_recovery': self.auto_recovery,
            'recovery_attempts': self.recovery_attempts.copy()
        }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Terminal Monitor Service")
    parser.add_argument(
        "--check-interval",
        type=int,
        default=30,
        help="Seconds between health checks (default 30)"
    )
    parser.add_argument(
        "--heartbeat-timeout",
        type=int,
        default=30,
        help="Seconds before considering terminal dead (default 30)"
    )
    parser.add_argument(
        "--no-auto-recovery",
        action="store_true",
        help="Disable automatic terminal restart"
    )
    parser.add_argument(
        "--restart-delay",
        type=int,
        default=5,
        help="Seconds to wait before restarting crashed terminal (default 5)"
    )
    parser.add_argument(
        "--machine-id",
        help="Override machine ID from environment"
    )
    return parser.parse_args()


async def signal_handler(monitor):
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal - stopping Terminal Monitor...")
    await monitor.stop()


async def main():
    """Main entry point for Terminal Monitor."""
    args = parse_args()

    # Use machine ID from args or environment
    machine_id = args.machine_id or MACHINE_ID

    logger.info("=" * 60)
    logger.info("🔍 TERMINAL MONITOR SERVICE")
    logger.info("=" * 60)
    logger.info(f"Machine ID: {machine_id}")
    logger.info(f"Check Interval: {args.check_interval}s")
    logger.info(f"Heartbeat Timeout: {args.heartbeat_timeout}s")
    logger.info(f"Auto-recovery: {'DISABLED' if args.no_auto_recovery else 'ENABLED'}")
    logger.info("=" * 60)

    # Create monitor
    monitor = TerminalMonitor(
        machine_id=machine_id,
        check_interval=args.check_interval,
        heartbeat_timeout=args.heartbeat_timeout,
        auto_recovery=not args.no_auto_recovery,
        restart_delay=args.restart_delay
    )

    # Set up signal handlers
    def shutdown_handler(signum, frame):
        asyncio.create_task(signal_handler(monitor))

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Start monitor
        await monitor.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await monitor.stop()
    except Exception as e:
        logger.error(f"Fatal error in Terminal Monitor: {e}", exc_info=True)
        await monitor.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
