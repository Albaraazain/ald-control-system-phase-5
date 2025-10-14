#!/usr/bin/env python3
"""
Real-time PLC Valve Monitor

Monitors PLC valve states in real-time to validate Terminal 2 recipe execution.
This script continuously reads valve states from the PLC and displays changes.

Usage:
    python monitor_plc_valves.py [--valves 1,2,3,4,5] [--interval 0.1]
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import List, Dict
import time

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.log_setup import get_plc_logger, set_log_level
from src.plc.manager import plc_manager

logger = get_plc_logger()


class PLCValveMonitor:
    """Real-time PLC valve state monitor"""

    def __init__(self, valve_numbers: List[int], interval: float = 0.1):
        self.valve_numbers = valve_numbers
        self.interval = interval
        self.previous_states: Dict[int, bool] = {}
        self.running = False

    async def read_valve_state(self, valve_number: int) -> bool:
        """Read current state of a valve from PLC"""
        try:
            plc = plc_manager.plc
            if not plc:
                return False

            # Get valve address from cache
            if hasattr(plc, '_valve_cache'):
                valve_meta = plc._valve_cache.get(valve_number)
                if not valve_meta:
                    logger.debug(f"Valve {valve_number} not in cache")
                    return False

                address = valve_meta['address']
                
                # Read coil state from PLC
                if hasattr(plc, 'communicator') and plc.communicator:
                    result = plc.communicator.read_coils(address, count=1)
                    if result and len(result) > 0:
                        return bool(result[0])
                    return False
            
            # Fallback for simulation
            if hasattr(plc, 'is_simulation') and plc.is_simulation:
                if hasattr(plc, 'read_coils'):
                    result = await plc.read_coils(valve_number - 1, count=1)
                    if result and len(result) > 0:
                        return bool(result[0])
                return False
            
            return False

        except Exception as e:
            logger.debug(f"Error reading valve {valve_number}: {e}")
            return False

    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🔍 Starting PLC valve monitoring...")
        logger.info(f"   Monitoring valves: {self.valve_numbers}")
        logger.info(f"   Update interval: {self.interval}s")
        logger.info("   Press Ctrl+C to stop")
        logger.info("")

        self.running = True
        change_count = 0

        while self.running:
            try:
                # Read all valve states
                current_states = {}
                for valve_num in self.valve_numbers:
                    state = await self.read_valve_state(valve_num)
                    current_states[valve_num] = state

                    # Check for state change
                    if valve_num in self.previous_states:
                        if self.previous_states[valve_num] != state:
                            change_count += 1
                            timestamp = time.strftime("%H:%M:%S.%f")[:-3]
                            old_state = "OPEN" if self.previous_states[valve_num] else "CLOSED"
                            new_state = "OPEN" if state else "CLOSED"
                            
                            logger.info(f"🔄 [{timestamp}] Valve {valve_num}: {old_state} → {new_state}")

                # Update previous states
                self.previous_states = current_states

                # Display current states periodically (every 5 seconds)
                if int(time.time()) % 5 == 0 and int(time.time() * 10) % 10 == 0:
                    status_line = " | ".join([
                        f"V{v}: {'🟢' if current_states[v] else '⚪'}"
                        for v in self.valve_numbers
                    ])
                    logger.info(f"📊 [{time.strftime('%H:%M:%S')}] Status: {status_line} (Changes: {change_count})")

                await asyncio.sleep(self.interval)

            except KeyboardInterrupt:
                logger.info("\n⚠️  Stopping monitor...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(1)

    async def start(self):
        """Initialize and start monitoring"""
        try:
            # Initialize PLC
            logger.info("🔧 Initializing PLC connection...")
            if not await plc_manager.initialize():
                logger.error("❌ Failed to initialize PLC")
                return

            logger.info("✅ PLC connected")

            # Initialize valve states
            logger.info("📋 Reading initial valve states...")
            for valve_num in self.valve_numbers:
                state = await self.read_valve_state(valve_num)
                self.previous_states[valve_num] = state
                logger.info(f"   Valve {valve_num}: {'OPEN' if state else 'CLOSED'}")

            logger.info("")

            # Start monitoring
            await self.monitor_loop()

        except Exception as e:
            logger.error(f"❌ Error starting monitor: {e}", exc_info=True)
        finally:
            # Disconnect PLC
            logger.info("🔧 Disconnecting PLC...")
            await plc_manager.disconnect()
            logger.info("✅ Monitor stopped")


def parse_args():
    """Parse command line arguments"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Real-time PLC Valve Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Monitor valves 1-5 with default interval:
    python monitor_plc_valves.py

  Monitor specific valves:
    python monitor_plc_valves.py --valves 1,2,3

  Monitor with faster updates (100ms):
    python monitor_plc_valves.py --interval 0.1
        """
    )

    parser.add_argument(
        "--valves",
        type=str,
        default="1,2,3,4,5",
        help="Comma-separated list of valve numbers to monitor (default: 1,2,3,4,5)"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="Polling interval in seconds (default: 0.1)"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_args()

    # Set log level
    set_log_level(args.log_level)

    # Parse valve numbers
    try:
        valve_numbers = [int(v.strip()) for v in args.valves.split(',')]
    except ValueError:
        logger.error("❌ Invalid valve numbers. Use format: 1,2,3")
        return

    logger.info("=" * 60)
    logger.info("🔍 PLC VALVE MONITOR")
    logger.info("=" * 60)

    # Create and start monitor
    monitor = PLCValveMonitor(valve_numbers, args.interval)
    await monitor.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Monitor stopped by user")

