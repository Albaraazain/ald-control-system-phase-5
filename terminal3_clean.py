#!/usr/bin/env python3
"""
Terminal 3: Parameter Service with Realtime + Instant Updates

Features:
1. 🚀 Supabase Realtime for instant command notifications (~0ms delay)
2. 🚀 Immediate database updates for instant UI feedback (~100ms total)
3. ✅ Input validation (NaN, Infinity, type checks)
4. 🔄 Polling fallback if Realtime fails (1s interval)
5. ⚡ Terminal liveness tracking

Performance:
- With Realtime: ~100-200ms end-to-end latency
- Without Realtime (fallback): ~500-1000ms latency
"""
import asyncio
import os
import sys
import signal
import time
from datetime import datetime
from typing import Optional, Set

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.log_setup import get_plc_logger
from src.config import MACHINE_ID
from src.db import get_supabase
from src.plc.manager import plc_manager
from src.connection_monitor import connection_monitor
from src.terminal_registry import TerminalRegistry, TerminalAlreadyRunningError

logger = get_plc_logger()

# Optional verification mode for debugging (adds ~50ms per operation)
ENABLE_READ_VERIFICATION = os.getenv('TERMINAL3_VERIFY_WRITES', 'false').lower() == 'true'

# Shutdown configuration
SHUTDOWN_TIMEOUT = float(os.getenv('SHUTDOWN_TIMEOUT', '30.0'))

# Track processed commands
processed_commands: Set[str] = set()

# Terminal registry instance
terminal_registry: Optional[TerminalRegistry] = None

# Realtime channel reference
realtime_channel = None
realtime_connected = False

# Shutdown coordination
shutdown_event: Optional[asyncio.Event] = None


async def write_and_verify(address: int, value: float, data_type: str = 'float', parameter_id: Optional[str] = None) -> tuple[bool, Optional[float]]:
    """
    Write value to PLC and optionally verify with read-back.
    
    Args:
        address: Modbus address to write to
        value: Value to write
        data_type: Type of data ('float' or 'binary')
        parameter_id: Optional parameter ID for database update
        
    Returns:
        tuple: (success, read_value)
    """
    try:
        # Write to PLC (using plc_manager.plc for direct address access)
        if data_type == 'binary':
            success = await plc_manager.plc.write_coil(address, bool(value))
            logger.debug(f"Wrote binary value {bool(value)} to coil {address}: {'success' if success else 'failed'}")
        else:
            success = await plc_manager.plc.write_float(address, float(value))
            logger.debug(f"Wrote float value {value} to register {address}: {'success' if success else 'failed'}")
        
        if not success:
            return False, None
        
        # Optional read-back verification (disabled by default for performance)
        read_value = None
        if ENABLE_READ_VERIFICATION:
            await asyncio.sleep(0.05)  # 50ms delay for PLC buffer update
            
            if data_type == 'binary':
                # For binary, read back from coil
                coils = await plc_manager.plc.read_coils(address, 1)
                if coils and len(coils) > 0:
                    read_value = float(coils[0])
                    matches = abs(read_value - value) < 0.01
                    if not matches:
                        logger.warning(f"⚠️  Read-back mismatch: wrote {value}, read {read_value}")
                        return False, read_value
            else:
                read_value = await plc_manager.plc.read_float(address)
                if read_value is not None:
                    matches = abs(read_value - value) < 0.01 or abs((read_value - value) / value) < 0.01
                    if not matches:
                        logger.warning(f"⚠️  Read-back mismatch: wrote {value}, read {read_value}")
                        return False, read_value
        
        return True, read_value
        
    except Exception as e:
        logger.error(f"❌ Error in write_and_verify: {e}", exc_info=True)
        return False, None


async def _update_setpoint_immediately(parameter_id: str, new_setpoint: float, parameter_name: str) -> bool:
    """
    🚀 PHASE 2 OPTIMIZATION: IMMEDIATELY update component_parameters.set_value after PLC write.
    
    This provides instant UI feedback without waiting for Terminal 1 to read back from PLC.
    Terminal 1 will still read and verify the value for validation (background).
    
    Args:
        parameter_id: The parameter ID to update
        new_setpoint: The setpoint value that was just written to PLC
        parameter_name: Name for logging
        
    Returns:
        bool: True if update succeeded, False otherwise
    """
    try:
        import math
        
        # Input validation: Check parameter_id
        if not parameter_id or parameter_id == "":
            logger.error("❌ Invalid parameter_id: cannot update setpoint")
            return False
        
        # Input validation: Check value type and validity
        if not isinstance(new_setpoint, (int, float)):
            logger.error(f"❌ Invalid setpoint type: {type(new_setpoint).__name__} (expected float)")
            return False
        
        # Input validation: Check for NaN or Infinity
        if math.isnan(new_setpoint):
            logger.error(f"❌ Invalid setpoint value: NaN (not a number)")
            return False
        if math.isinf(new_setpoint):
            logger.error(f"❌ Invalid setpoint value: Infinity")
            return False
        
        supabase = get_supabase()
        
        # Update set_value field immediately
        result = supabase.table('component_parameters').update({
            'set_value': new_setpoint,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', parameter_id).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"✅ Immediate setpoint database update: {parameter_name} set_value → {new_setpoint}")
            return True
        else:
            logger.warning(f"⚠️ Immediate setpoint update returned no data for parameter {parameter_name}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to immediately update setpoint: {e}", exc_info=True)
        return False


async def process_command(command: dict):
    """Process a single parameter control command."""
    command_id = command['id']
    parameter_name = command.get('parameter_name', 'unknown')
    target_value = command.get('target_value')
    modbus_address = command.get('modbus_address')
    component_parameter_id = command.get('component_parameter_id')
    
    logger.info(f"🔧 Processing command {command_id[:8]}... | {parameter_name} = {target_value}")
    
    if target_value is None:
        logger.error(f"❌ No target_value provided for command {command_id}")
        await update_command_status(command_id, 'failed', 'No target value provided')
        return
    
    # Lookup parameter details from database
    data_type = command.get('data_type')
    parameter_id = component_parameter_id
    write_address = modbus_address
    
    try:
        supabase = get_supabase()
        
        # Lookup parameter by ID, name, or address
        if component_parameter_id:
            result = supabase.table('component_parameters_full')\
                .select('id, data_type, write_modbus_type, write_modbus_address, component_name')\
                .eq('id', component_parameter_id)\
                .limit(1)\
                .execute()
        elif modbus_address:
            result = supabase.table('component_parameters_full')\
                .select('id, data_type, write_modbus_type, write_modbus_address, component_name')\
                .eq('write_modbus_address', modbus_address)\
                .limit(1)\
                .execute()
        elif parameter_name:
            result = supabase.table('component_parameters_full')\
                .select('id, data_type, write_modbus_type, write_modbus_address, component_name')\
                .eq('parameter_name', parameter_name)\
                .limit(1)\
                .execute()
        else:
            logger.error(f"❌ Command must provide component_parameter_id, modbus_address, or parameter_name")
            await update_command_status(command_id, 'failed', 'Missing parameter identification')
            return
        
        if result.data:
            param_info = result.data[0]
            parameter_id = param_info['id']
            data_type = data_type or param_info.get('data_type', 'float')
            component_name = param_info.get('component_name', 'unknown')
            write_address = write_address or param_info.get('write_modbus_address')
            
            logger.info(f"📋 Parameter found: {parameter_name} ({component_name})")
        else:
            error_msg = f"Parameter not found in database"
            logger.error(f"❌ {error_msg}")
            await update_command_status(command_id, 'failed', error_msg)
            return
            
    except Exception as lookup_err:
        error_msg = f"Database lookup error: {lookup_err}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        await update_command_status(command_id, 'failed', error_msg)
        return
    
    # Validate we have a write address
    if write_address is None:
        error_msg = f"No write_modbus_address available for parameter {parameter_name}"
        logger.error(f"❌ {error_msg}")
        await update_command_status(command_id, 'failed', error_msg)
        return
    
    # Update status to processing
    await update_command_status(command_id, 'processing', None)

    # Convert value to appropriate type
    value = int(target_value) if data_type == 'binary' else target_value

    # Write and verify
    start_time = time.time()
    success, read_value = await write_and_verify(
        address=write_address,
        value=value,
        data_type=data_type,
        parameter_id=parameter_id
    )
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Update final status
    if success:
        logger.info(f"✅ Command {command_id[:8]}... completed in {duration_ms}ms")
        
        # 🚀 PHASE 2 OPTIMIZATION: Immediately update database for instant UI feedback
        if parameter_id and data_type != 'binary':
            try:
                await _update_setpoint_immediately(parameter_id, target_value, parameter_name)
                logger.info(f"🚀 Instant UI update: {parameter_name} = {target_value}")
            except Exception as update_err:
                logger.warning(f"⚠️ Immediate setpoint update failed: {update_err}. Terminal 1 will sync in 0.5s.")
        
        await update_command_status(command_id, 'completed', None)

        if terminal_registry:
            terminal_registry.increment_commands()
    else:
        logger.error(f"❌ Command {command_id[:8]}... failed after {duration_ms}ms")
        await update_command_status(command_id, 'failed', 'Write operation failed')

        if terminal_registry:
            terminal_registry.record_error(f"Command {command_id[:8]} write failed")


async def update_command_status(command_id: str, status: str, error_message: Optional[str]):
    """Update command status in database."""
    try:
        supabase = get_supabase()
        
        update_data = {}
        
        if status == 'processing':
            update_data['executed_at'] = datetime.utcnow().isoformat()
        elif status in ['completed', 'failed']:
            update_data['completed_at'] = datetime.utcnow().isoformat()
        
        if error_message:
            update_data['error_message'] = error_message
        
        if update_data:
            supabase.table('parameter_control_commands').update(update_data).eq('id', command_id).execute()
    except Exception as e:
        logger.error(f"Error updating command status: {e}")


def handle_realtime_insert(payload):
    """
    Handle realtime INSERT notification.
    
    This is called instantly when a new command is inserted.
    """
    logger.info("🔔 PARAMETER COMMAND RECEIVED [REALTIME] - Instant notification!")
    
    try:
        record = payload.get("data", {}).get("record")
        if not record:
            logger.error(f"Invalid payload structure: {payload}")
            return
        
        # Filter for this machine
        machine_id = record.get('machine_id')
        if machine_id is not None and machine_id != MACHINE_ID:
            logger.debug(f"Ignoring command for different machine: {machine_id}")
            return
        
        command_id = record["id"]
        
        # Skip if already processed
        if command_id in processed_commands:
            logger.debug(f"Command {command_id} already processed, skipping")
            return
        
        # Skip if already executed
        if record.get("executed_at") is not None:
            logger.debug(f"Command {command_id} already executed, skipping")
            processed_commands.add(command_id)
            return
        
        # Mark as processed and handle
        processed_commands.add(command_id)
        asyncio.create_task(process_command(record))
        
    except Exception as e:
        logger.error(f"Error handling realtime insert: {e}", exc_info=True)


async def setup_realtime():
    """Setup Supabase Realtime subscription for instant command notifications."""
    global realtime_channel, realtime_connected
    
    try:
        from supabase import acreate_client
        
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            logger.warning("⚠️ Supabase credentials not found, using polling only")
            return False
        
        logger.info("🔌 Setting up Realtime subscription...")
        
        # Create async client
        async_supabase = await acreate_client(supabase_url, supabase_key)
        
        # Create channel
        channel_name = f"parameter-commands-{MACHINE_ID}"
        realtime_channel = async_supabase.channel(channel_name)
        
        # Subscribe to INSERT events
        realtime_channel = realtime_channel.on_postgres_changes(
            event="INSERT",
            schema="public",
            table="parameter_control_commands",
            callback=handle_realtime_insert
        )
        
        # Subscribe with timeout
        try:
            await asyncio.wait_for(realtime_channel.subscribe(), timeout=10.0)
            realtime_connected = True
            connection_monitor.update_realtime_status(True)
            logger.info(f"✅ Realtime connected: {channel_name}")
            return True
        except asyncio.TimeoutError:
            logger.warning("⚠️ Realtime subscription timed out after 10s; using polling fallback")
            realtime_connected = False
            connection_monitor.update_realtime_status(False, "subscribe timeout")
            return False
            
    except Exception as e:
        logger.error(f"❌ Realtime setup failed: {e}", exc_info=True)
        realtime_connected = False
        connection_monitor.update_realtime_status(False, str(e))
        return False


async def poll_commands():
    """
    Poll for new parameter control commands.
    
    Polling interval depends on realtime status:
    - Realtime connected: 10s (safety check only)
    - Realtime disconnected: 1s (primary mechanism)
    """
    global shutdown_event
    logger.info("🔄 Starting command polling...")

    while not shutdown_event.is_set():
        try:
            # Adjust polling interval based on realtime status
            poll_interval = 10.0 if realtime_connected else 1.0

            supabase = get_supabase()

            # Query for pending commands
            result = supabase.table('parameter_control_commands')\
                .select('*')\
                .is_('executed_at', 'null')\
                .is_('completed_at', 'null')\
                .order('created_at', desc=False)\
                .limit(10)\
                .execute()

            commands = result.data or []

            # Filter for this machine and global commands
            relevant_commands = [
                cmd for cmd in commands
                if cmd.get('machine_id') in [MACHINE_ID, None]
                and cmd['id'] not in processed_commands
            ]

            for command in relevant_commands:
                # Check shutdown between commands
                if shutdown_event.is_set():
                    logger.info("Shutdown detected in command processing loop")
                    break

                command_id = command['id']
                processed_commands.add(command_id)

                # Log source
                source = "POLLING (realtime backup)" if realtime_connected else "POLLING"
                logger.info(f"🟡 PARAMETER COMMAND RECEIVED [{source}]")

                try:
                    await process_command(command)
                except Exception as e:
                    logger.error(f"Error processing command {command_id}: {e}", exc_info=True)
                    await update_command_status(command_id, 'failed', str(e))

                    if terminal_registry:
                        terminal_registry.record_error(f"Command {command_id[:8]} exception: {str(e)}")

            # Clean up old processed commands
            if len(processed_commands) > 1000:
                processed_commands.clear()

        except asyncio.CancelledError:
            logger.info("Poll loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in poll loop: {e}", exc_info=True)

        # Shutdown-aware sleep for immediate exit on shutdown signal
        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=poll_interval
            )
            # Event was set, exit loop
            logger.info("Shutdown event detected during sleep")
            break
        except asyncio.TimeoutError:
            # Normal timeout, continue loop
            pass

    logger.info("Poll loop exited cleanly")


# Global references for signal handlers
_loop: Optional[asyncio.AbstractEventLoop] = None


def setup_signal_handlers(loop: asyncio.AbstractEventLoop):
    """Setup signal handlers for graceful shutdown."""
    global shutdown_event, _loop
    _loop = loop

    def signal_handler(signum, frame):
        """Handle shutdown signals - called from signal handler thread."""
        signal_name = signal.Signals(signum).name
        logger.info(f"🛑 Received signal {signal_name}, initiating graceful shutdown...")
        # Schedule event.set() on the event loop thread (thread-safe)
        if _loop and shutdown_event:
            _loop.call_soon_threadsafe(shutdown_event.set)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("✅ Signal handlers installed (SIGINT, SIGTERM)")


async def shutdown_terminal():
    """Graceful shutdown with timeout."""
    global terminal_registry, realtime_channel

    logger.info("🛑 Starting graceful shutdown...")
    start_time = asyncio.get_event_loop().time()

    try:
        # Cleanup tasks
        cleanup_tasks = []

        # Cleanup realtime
        if realtime_channel:
            async def cleanup_realtime():
                try:
                    await asyncio.wait_for(
                        realtime_channel.unsubscribe(),
                        timeout=5.0
                    )
                    logger.info("✅ Realtime unsubscribed")
                except asyncio.TimeoutError:
                    logger.warning("⏱️ Realtime unsubscribe timed out")
                except Exception as e:
                    logger.error(f"Realtime cleanup error: {e}")

            cleanup_tasks.append(cleanup_realtime())

        # Cleanup registry
        if terminal_registry:
            async def cleanup_registry():
                try:
                    await asyncio.wait_for(
                        terminal_registry.shutdown(reason="Service shutdown"),
                        timeout=5.0
                    )
                    logger.info("✅ Terminal registry shutdown")
                except asyncio.TimeoutError:
                    logger.warning("⏱️ Registry shutdown timed out")
                except Exception as e:
                    logger.error(f"Registry cleanup error: {e}")

            cleanup_tasks.append(cleanup_registry())

        # Cleanup PLC
        async def cleanup_plc():
            try:
                await asyncio.wait_for(
                    plc_manager.disconnect(),
                    timeout=5.0
                )
                logger.info("✅ PLC disconnected")
            except asyncio.TimeoutError:
                logger.warning("⏱️ PLC disconnect timed out")
            except Exception as e:
                logger.error(f"PLC cleanup error: {e}")

        cleanup_tasks.append(cleanup_plc())

        # Execute all cleanup with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*cleanup_tasks, return_exceptions=True),
                timeout=SHUTDOWN_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Shutdown cleanup timed out after {SHUTDOWN_TIMEOUT}s")

        duration = asyncio.get_event_loop().time() - start_time
        logger.info(f"✅ Graceful shutdown complete in {duration:.2f}s")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


async def main():
    """Main entry point."""
    global terminal_registry, shutdown_event

    logger.info("=" * 60)
    logger.info("🚀 Terminal 3: Parameter Service (Realtime + Instant Updates)")
    logger.info("=" * 60)

    # Initialize shutdown coordination
    shutdown_event = asyncio.Event()
    logger.info(f"📋 Shutdown timeout: {SHUTDOWN_TIMEOUT}s")

    # Setup signal handlers with access to event loop
    loop = asyncio.get_running_loop()
    setup_signal_handlers(loop)

    try:
        # Register this terminal instance
        log_file_path = "/tmp/terminal3_parameter_service.log"
        terminal_registry = TerminalRegistry(
            terminal_type='terminal3',
            machine_id=MACHINE_ID,
            environment='production',
            heartbeat_interval=10,
            log_file_path=log_file_path
        )

        try:
            terminal_registry.register()
            logger.info("✅ Terminal registered in liveness system")
        except TerminalAlreadyRunningError as e:
            logger.error(f"❌ {e}")
            logger.error("Cannot start - Terminal 3 already running")
            return

        # Initialize PLC manager
        await plc_manager.initialize()
        logger.info("✅ PLC manager initialized")
        logger.info(f"📋 Machine ID: {MACHINE_ID}")
        logger.info(f"🔌 PLC Type: {plc_manager.plc.__class__.__name__}")
        logger.info(f"📋 Verification Mode: {'ENABLED' if ENABLE_READ_VERIFICATION else 'DISABLED (production)'}")
        if not ENABLE_READ_VERIFICATION:
            logger.info("   💡 Tip: Set TERMINAL3_VERIFY_WRITES=true to enable read-back verification")
        logger.info(f"📋 Terminal Liveness: ENABLED")

        # Setup Realtime
        realtime_success = await setup_realtime()

        logger.info("=" * 60)
        if realtime_success:
            logger.info("✅ Terminal 3 ready with REALTIME + INSTANT UPDATES! 🚀")
            logger.info("   Expected latency: ~100-200ms")
        else:
            logger.info("✅ Terminal 3 ready with POLLING + INSTANT UPDATES")
            logger.info("   Expected latency: ~500-1000ms")
        logger.info("=" * 60)

        # Start polling (works alongside Realtime as backup)
        await poll_commands()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error in Terminal 3: {e}", exc_info=True)
        if terminal_registry:
            terminal_registry.record_error(f"Fatal: {e}")
    finally:
        # Graceful shutdown with timeout
        await shutdown_terminal()


if __name__ == "__main__":
    asyncio.run(main())

