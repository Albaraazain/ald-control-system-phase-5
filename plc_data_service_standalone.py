#!/usr/bin/env python3
"""
Terminal 1: PLC Data Service

Continuous PLC data collection with optimized bulk reads.
- Direct PLC connection (no singleton)
- Parallel bulk reads for fast performance (39-45ms)
- Simple 1-second collection loop
- Wide table format database writes
"""

import asyncio
import os
import sys
import signal
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.log_setup import get_plc_logger, get_data_collection_logger
from src.config import MACHINE_ID, PLC_TYPE, PLC_CONFIG
from src.db import get_supabase
from src.plc.real_plc import RealPLC
from src.parameter_wide_table_mapping import PARAMETER_TO_COLUMN_MAP
from src.terminal_registry import TerminalRegistry, TerminalAlreadyRunningError

logger = get_plc_logger()
data_logger = get_data_collection_logger()


class PLCDataService:
    """PLC data collection service with direct connection and bulk reads."""
    
    def __init__(self):
        self.plc: Optional[RealPLC] = None
        self.supabase = get_supabase()
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.registry: Optional[TerminalRegistry] = None
        
        # Timing
        self.collection_interval = 1.0
        self._next_deadline: Optional[float] = None
        
        # Metrics
        self.total_readings = 0
        self.failed_readings = 0
        self.last_duration = 0.0
        
        logger.info("PLC Data Service initialized")
    
    async def initialize(self) -> bool:
        """Initialize PLC connection and terminal registry."""
        try:
            logger.info("Connecting to PLC...")
            
            # Register this terminal instance in liveness system
            log_file_path = "/tmp/terminal1_plc_data_service.log"
            self.registry = TerminalRegistry(
                terminal_type='terminal1',
                machine_id=MACHINE_ID,
                environment='production',
                heartbeat_interval=10,
                log_file_path=log_file_path
            )
            
            try:
                await self.registry.register()
                logger.info("✅ Terminal 1 registered in liveness system")
            except TerminalAlreadyRunningError as e:
                logger.error(str(e))
                raise RuntimeError("Cannot start - Terminal 1 already running")
            
            # Create PLC instance directly
            ip_address = PLC_CONFIG.get('ip_address', '192.168.1.50')
            port = PLC_CONFIG.get('port', 502)
            hostname = PLC_CONFIG.get('hostname')
            auto_discover = PLC_CONFIG.get('auto_discover', False)
            
            self.plc = RealPLC(
                ip_address=ip_address,
                port=port,
                hostname=hostname,
                auto_discover=auto_discover
            )
            
            success = await self.plc.initialize()
            if success:
                logger.info("✅ PLC connected and bulk reads initialized")
                return True
            else:
                logger.error("❌ Failed to connect to PLC")
                if self.registry:
                    await self.registry.set_status('degraded', 'PLC connection unavailable')
                return False
                
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"❌ Initialization error: {e}", exc_info=True)
            if self.registry:
                await self.registry.set_status('degraded', f'Initialization error: {e}')
            return False
    
    async def read_all_parameters(self) -> Dict[str, float]:
        """Read all parameters using bulk reads."""
        if not self.plc or not self.plc.connected:
            return {}
        
        try:
            # Use bulk reads (should be fast)
            result = await self.plc.read_all_parameters()
            return result
        except Exception as e:
            logger.error(f"Error reading parameters: {e}", exc_info=True)
            return {}
    
    async def write_to_database(self, parameter_values: Dict[str, float], timestamp: str):
        """Write parameter values to database using wide table format."""
        if not parameter_values:
            return
        
        try:
            # Build WIDE-FORMAT record (single row with all parameters)
            wide_record = {'timestamp': timestamp}
            
            for param_id, value in parameter_values.items():
                # Get column name from mapping
                column_name = PARAMETER_TO_COLUMN_MAP.get(param_id)
                
                if column_name is None:
                    data_logger.debug(f"Parameter {param_id} not in wide table mapping - skipping")
                    continue
                
                # Add to wide record
                wide_record[column_name] = float(value)
            
            # Insert single wide record
            if len(wide_record) > 1:
                self.supabase.table('parameter_readings').insert(wide_record).execute()
                data_logger.debug(f"✅ Wrote {len(wide_record) - 1} parameter values to database (wide format)")
        
        except Exception as e:
            logger.error(f"Error writing to database: {e}", exc_info=True)
            self.failed_readings += 1
    
    async def collection_loop(self):
        """Main collection loop with precise 1-second timing."""
        logger.info("Starting collection loop (1s intervals)")
        
        loop = asyncio.get_event_loop()
        self._next_deadline = loop.time()
        
        while not self.shutdown_event.is_set():
            loop_start = loop.time()
            
            try:
                # Read all parameters
                read_start = time.time()
                parameter_values = await self.read_all_parameters()
                read_duration = time.time() - read_start
                
                if parameter_values:
                    # Write to database
                    from datetime import datetime, timezone
                    timestamp = datetime.now(timezone.utc).isoformat()
                    await self.write_to_database(parameter_values, timestamp)
                    
                    self.total_readings += 1
                    self.last_duration = loop.time() - loop_start
                    
                    # Track successful reading
                    if self.registry:
                        self.registry.increment_commands()
                    
                    data_logger.info(
                        f"✅ Collection #{self.total_readings}: "
                        f"{len(parameter_values)} params in {read_duration*1000:.0f}ms, "
                        f"total={self.last_duration*1000:.0f}ms"
                    )
                else:
                    logger.warning("No parameters read")
                    self.failed_readings += 1
                    if self.registry:
                        self.registry.record_error("No parameters read")
                
            except Exception as e:
                logger.error(f"Error in collection loop: {e}", exc_info=True)
                self.failed_readings += 1
                if self.registry:
                    self.registry.record_error(f"Collection loop error: {e}")
            
            # Calculate sleep time for next iteration
            self._next_deadline += self.collection_interval
            now = loop.time()
            sleep_time = max(0, self._next_deadline - now)
            
            # Check timing precision
            elapsed = now - loop_start
            if abs(elapsed - self.collection_interval) > 0.2:
                logger.warning(
                    f"⚠️ Timing violation: {elapsed:.3f}s (target: {self.collection_interval}s)"
                )
            
            # Sleep until next deadline
            if sleep_time > 0:
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=sleep_time
                    )
                    # Shutdown event was set
                    break
                except asyncio.TimeoutError:
                    pass
            else:
                if abs(self._next_deadline - now) > 1.0:
                    logger.warning(f"⚠️ Behind schedule, resetting deadline")
                    self._next_deadline = now + self.collection_interval
        
        logger.info("Collection loop stopped")
    
    async def start(self):
        """Start the service."""
        if not await self.initialize():
            raise RuntimeError("Failed to initialize service")
        
        self.running = True
        logger.info("🚀 PLC Data Service started")
        
        # Run collection loop
        await self.collection_loop()
    
    async def stop(self):
        """Stop the service."""
        logger.info("Stopping service...")
        self.running = False
        self.shutdown_event.set()
        
        if self.plc:
            await self.plc.disconnect()
        
        if self.registry:
            await self.registry.shutdown(reason="Service shutdown")
        
        logger.info(f"✅ Service stopped. Total readings: {self.total_readings}, Failed: {self.failed_readings}")


async def main():
    """Main entry point."""
    # Setup global exception handlers
    from src.resilience.error_handlers import (
        setup_global_exception_handler,
        setup_asyncio_exception_handler
    )
    
    logger.info("=" * 60)
    logger.info("🔧 PLC DATA SERVICE - TERMINAL 1")
    logger.info(f"   Machine ID: {MACHINE_ID}")
    logger.info(f"   Terminal Liveness: ENABLED")
    logger.info("=" * 60)
    
    service = PLCDataService()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(service.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await service.start()
        
        # Setup exception handlers now that we have registry
        if service.registry:
            setup_global_exception_handler(
                registry=service.registry,
                logger=logger
            )
            setup_asyncio_exception_handler(
                registry=service.registry,
                logger=logger
            )
            logger.info("✅ Global exception handlers installed")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except RuntimeError as e:
        if "already running" in str(e):
            logger.error(str(e))
            sys.exit(1)
        else:
            logger.error(f"Fatal runtime error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())

