#!/usr/bin/env python3
"""
Terminal 3: Clean Parameter Service Implementation

Simple, reliable parameter control service that:
1. Listens for parameter commands from database
2. Writes directly to PLC
3. Optionally verifies writes with read-back (TERMINAL3_VERIFY_WRITES=true)
4. Updates command status

Based on successful manual test patterns.

Performance Notes:
- Production mode (default): ~45-70ms per write operation
- Verification mode: ~95-120ms per write (adds ~50ms for read-back)
- Set TERMINAL3_VERIFY_WRITES=true to enable read-back verification for debugging
"""
import asyncio
import os
import sys
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
# Modbus protocol guarantees write completion before response, so verification
# is redundant for production use. Enable for debugging/testing only.
ENABLE_READ_VERIFICATION = os.getenv('TERMINAL3_VERIFY_WRITES', 'false').lower() == 'true'

# Track processed commands
processed_commands: Set[str] = set()

# Terminal registry instance
terminal_registry: Optional[TerminalRegistry] = None


async def write_and_verify(address: int, value: float, data_type: str = 'float', parameter_id: Optional[str] = None) -> tuple[bool, Optional[float]]:
    """
    Write to PLC and optionally verify with read-back.

    Modbus protocol guarantees write completion before returning, so verification
    is redundant in production. Use TERMINAL3_VERIFY_WRITES=true to enable
    read-back verification for debugging/testing (~50ms overhead per write).

    Args:
        address: Modbus address to write to
        value: Value to write
        data_type: 'float' or 'binary'
        parameter_id: Deprecated parameter (Terminal 1 handles data collection)

    Returns:
        (success, read_back_value) - read_back_value is None unless verification enabled
    """
    try:
        # Ensure PLC is initialized
        if not plc_manager.plc.connected:
            logger.error("❌ PLC not connected")
            return False, None
        
        # Write to PLC
        if data_type == 'binary':
            logger.debug(f"📝 Writing BINARY/COIL: value={bool(value)} to address {address}")
            success = await plc_manager.plc.write_coil(address, bool(value))
        else:
            logger.debug(f"📝 Writing FLOAT/REGISTER: value={float(value)} to address {address} (data_type={data_type})")
            success = await plc_manager.plc.write_float(address, float(value))

        if not success:
            logger.error(f"❌ Write failed to address {address}")
            return False, None

        logger.debug(f"✅ Write succeeded: {value} → address {address}")

        # Optional read-back verification (disabled by default for performance)
        read_value = None
        if ENABLE_READ_VERIFICATION:
            logger.debug("🔍 Verification mode enabled - performing read-back")

            # Small delay for PLC to update
            time.sleep(0.05)

            # Read back for verification
            if data_type == 'binary':
                coils = await plc_manager.plc.read_coils(address, 1)
                read_value = float(coils[0]) if coils else None
            else:
                read_value = await plc_manager.plc.read_float(address)

            if read_value is None:
                logger.warning(f"⚠️  Read-back returned None for address {address}")
                return True, None  # Write succeeded, but couldn't verify

            logger.info(f"📖 Read-back: {read_value} from address {address}")

            # Check tolerance
            tolerance = 0.01
            abs_diff = abs(read_value - value)
            rel_diff = abs_diff / max(abs(value), 0.001)

            if abs_diff > tolerance and rel_diff > tolerance:
                logger.warning(
                    f"⚠️  VERIFICATION FAILED: Wrote {value}, Read {read_value}, "
                    f"Diff: {abs_diff:.4f} ({rel_diff*100:.2f}%)"
                )
                return True, read_value  # Write succeeded, but value doesn't match

            logger.info(
                f"✅ VERIFICATION SUCCESS: Value confirmed at address {address} "
                f"(wrote: {value}, read: {read_value})"
            )

        # Note: Terminal 1 (PLC Data Service) handles all parameter data collection
        # and database updates via 1-second polling. This keeps Terminal 3 fast
        # and maintains single source of truth for time-series data.
        return True, read_value
        
    except Exception as e:
        logger.error(f"❌ Error in write_and_verify: {e}", exc_info=True)
        return False, None


async def process_command(command: dict):
    """Process a single parameter control command."""
    command_id = command['id']
    parameter_name = command.get('parameter_name', 'unknown')
    target_value = command.get('target_value')
    modbus_address = command.get('modbus_address')  # Optional override
    component_parameter_id = command.get('component_parameter_id')
    
    logger.info(f"🔧 Processing command {command_id[:8]}... | {parameter_name} = {target_value}")
    
    if target_value is None:
        logger.error(f"❌ No target_value provided for command {command_id}")
        await update_command_status(command_id, 'failed', 'No target value provided')
        return
    
    # Lookup parameter details from database
    data_type = command.get('data_type')
    parameter_id = component_parameter_id
    write_address = modbus_address  # May be None initially
    read_address = None
    
    try:
        supabase = get_supabase()
        
        # Lookup parameter by ID, name, or address
        if component_parameter_id:
            # Lookup by parameter ID (preferred)
            logger.debug(f"🔍 Looking up parameter by ID: {component_parameter_id[:8]}...")
            result = supabase.table('component_parameters_full')\
                .select('id, data_type, write_modbus_type, read_modbus_type, write_modbus_address, read_modbus_address, component_name')\
                .eq('id', component_parameter_id)\
                .limit(1)\
                .execute()
        elif modbus_address:
            # Lookup by address override
            logger.debug(f"🔍 Looking up parameter by address: {modbus_address}...")
            result = supabase.table('component_parameters_full')\
                .select('id, data_type, write_modbus_type, read_modbus_type, write_modbus_address, read_modbus_address, component_name')\
                .eq('write_modbus_address', modbus_address)\
                .limit(1)\
                .execute()
        elif parameter_name:
            # Lookup by parameter name (fallback)
            logger.debug(f"🔍 Looking up parameter by name: {parameter_name}...")
            result = supabase.table('component_parameters_full')\
                .select('id, data_type, write_modbus_type, read_modbus_type, write_modbus_address, read_modbus_address, component_name')\
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
            write_modbus_type = param_info.get('write_modbus_type', '')
            read_modbus_type = param_info.get('read_modbus_type', '')
            component_name = param_info.get('component_name', 'unknown')
            
            # Use database addresses if not overridden
            write_address = write_address or param_info.get('write_modbus_address')
            read_address = param_info.get('read_modbus_address')
            
            logger.info(f"📋 Parameter found: {parameter_name} ({component_name})")
            logger.debug(
                f"   ID={parameter_id[:8]}..., data_type={data_type}, "
                f"write_type={write_modbus_type}, write_addr={write_address}, read_addr={read_address}"
            )
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
    
    # Log the final configuration being used
    logger.debug(f"🏷️  Using data_type='{data_type}' for address {write_address}")
    
    # Update status to processing
    await update_command_status(command_id, 'processing', None)

    # Convert value to appropriate type for binary operations
    value = int(target_value) if data_type == 'binary' else target_value

    # Write and verify (with database update if parameter_id found)
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
        await update_command_status(command_id, 'completed', None)

        # Track successful command in liveness system
        if terminal_registry:
            terminal_registry.increment_commands()
    else:
        logger.error(f"❌ Command {command_id[:8]}... failed after {duration_ms}ms")
        await update_command_status(command_id, 'failed', 'Write operation failed')

        # Record error in liveness system
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
            logger.debug(f"📝 Updated command {command_id[:8]}... status to {status}")
    except Exception as e:
        logger.error(f"Error updating command status: {e}")


async def poll_commands():
    """Poll for new parameter control commands."""
    logger.info("🔄 Starting command polling...")
    
    while True:
        try:
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
                command_id = command['id']
                processed_commands.add(command_id)
                
                try:
                    await process_command(command)
                except Exception as e:
                    logger.error(f"Error processing command {command_id}: {e}", exc_info=True)
                    await update_command_status(command_id, 'failed', str(e))

                    # Record error in liveness system
                    if terminal_registry:
                        terminal_registry.record_error(f"Command {command_id[:8]} exception: {str(e)}")
            
            # Clean up old processed commands (keep last 1000)
            if len(processed_commands) > 1000:
                processed_commands.clear()
            
        except Exception as e:
            logger.error(f"Error in poll loop: {e}", exc_info=True)
        
        await asyncio.sleep(1.0)  # Poll every second


async def main():
    """Main entry point."""
    global terminal_registry

    logger.info("=" * 60)
    logger.info("🚀 Terminal 3: Clean Parameter Service")
    logger.info("=" * 60)

    try:
        # Register this terminal instance in liveness system
        log_file_path = "/tmp/terminal3_parameter_service.log"
        terminal_registry = TerminalRegistry(
            terminal_type='terminal3',
            machine_id=MACHINE_ID,
            environment='production',
            heartbeat_interval=10,
            log_file_path=log_file_path
        )

        try:
            await terminal_registry.register()
            logger.info("✅ Terminal 3 registered in liveness system")
        except TerminalAlreadyRunningError as e:
            logger.error(str(e))
            raise RuntimeError("Cannot start - Terminal 3 already running")

        # Initialize PLC
        logger.info("🔧 Initializing PLC manager...")
        await plc_manager.initialize()
        logger.info("✅ PLC manager initialized")

        logger.info(f"📋 Machine ID: {MACHINE_ID}")
        logger.info(f"🔌 PLC Type: {type(plc_manager.plc).__name__}")
        logger.info(f"📋 Verification Mode: {'ENABLED (debugging)' if ENABLE_READ_VERIFICATION else 'DISABLED (production)'}")
        if not ENABLE_READ_VERIFICATION:
            logger.info("   💡 Tip: Set TERMINAL3_VERIFY_WRITES=true to enable read-back verification")
        logger.info(f"📋 Terminal Liveness: ENABLED")
        logger.info("=" * 60)
        logger.info("✅ Terminal 3 ready to process commands")
        logger.info("=" * 60)

        # Start polling
        await poll_commands()

    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Terminal 3...")
    except RuntimeError as e:
        # Handle terminal already running error
        if "already running" in str(e):
            logger.error(str(e))
            sys.exit(1)
        else:
            logger.error(f"❌ Fatal runtime error: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        raise
    finally:
        # Graceful shutdown
        if terminal_registry:
            await terminal_registry.shutdown(reason="Service shutdown")
            logger.info("✅ Terminal liveness shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())

