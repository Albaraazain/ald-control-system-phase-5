# File: main.py
"""
Main entry point for the machine control application.
Sets up listeners and runs the main application loop.
"""
import asyncio
import os
import signal
import sys
from src.log_setup import logger, OK_MARK, WARN_MARK, FAIL_MARK
from src.db import create_async_supabase, get_supabase
from src.command_flow.listener import setup_command_listener
from src.command_flow.status import update_command_status
from src.config import MACHINE_ID
from src.recipe_flow.stopper import update_process_status, update_machine_status, update_machine_state
from src.command_flow.state import state
from src.plc.manager import plc_manager
from src.recipe_flow.continuous_data_recorder import continuous_recorder
from src.connection_monitor import connection_monitor
from src.agents.supervisor import (
    AgentSupervisor,
    make_command_listener_agent,
    make_connection_monitor_agent,
    make_parameter_control_listener_agent,
)

async def cleanup_handler():
    """Perform cleanup when application is interrupted"""
    logger.info("Beginning cleanup process...")
    supabase = get_supabase()
    
    try:
        # Get current machine status
        machine = supabase.table('machines').select('*').eq('id', MACHINE_ID).single().execute()
        
        if machine.data and machine.data['status'] == 'processing':
            process_id = machine.data['current_process_id']
            if process_id:
                # Stop continuous data recording
                await continuous_recorder.stop()
                
                # Update process status to aborted when cleanup is triggered
                await update_process_status(process_id, 'aborted')
                
                # Update machine status and state
                await update_machine_status(process_id)
                await update_machine_state(process_id)
                
                # Close any potentially open valves
                # In real implementation, this would interface with hardware
                logger.info("Ensuring all valves are closed")
                
                # Update command status if we have a command ID
                if state.current_command_id is not None:
                    await update_command_status(state.current_command_id, 'error', 'Process aborted by user')
                    logger.info(f"Updated command {state.current_command_id} status to error")
                
                logger.info(f"Cleanup completed for process {process_id}")
        
        # Disconnect PLC
        await plc_manager.disconnect()
        
    except Exception as e:
        logger.exception("Error during cleanup")
    finally:
        logger.info("Application shutdown complete")
        sys.exit(0)

async def signal_handler(signal, frame):
    """Handle SIGINT signal"""
    logger.info("Received interrupt signal, initiating cleanup...")
    await cleanup_handler()

async def main():
    """
    Main application function.
    Sets up the Supabase listener and runs indefinitely.
    """
    try:
        logger.info("Starting machine control application")
        
        # Set up signal handler
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(signal_handler(s, f)))
        
        # Initialize PLC connection (non-blocking)
        logger.info("Attempting initial PLC connection...")
        try:
            # Try to connect with a short timeout
            plc_connected = await asyncio.wait_for(
                plc_manager.initialize(),
                timeout=5.0  # 5 second timeout for initial connection
            )
            if plc_connected:
                logger.info(f"{OK_MARK} PLC connection initialized successfully")
            else:
                logger.warning(f"{WARN_MARK} PLC not connected, will retry in background")
        except asyncio.TimeoutError:
            logger.warning(
                f"{WARN_MARK} PLC connection timed out, service will continue and retry in background"
            )
            plc_connected = False
        except Exception as e:
            logger.warning(f"{WARN_MARK} PLC connection failed: {str(e)}, will retry in background")
            plc_connected = False
        
        # Service continues regardless of PLC status
        logger.info(f"Service starting with PLC connected: {plc_connected}")
        
        # Create async Supabase client for realtime features
        logger.info("Creating async Supabase client...")
        async_supabase = await create_async_supabase()

        # Start agents (headless)
        agent_list = [
            make_connection_monitor_agent(),
            make_command_listener_agent(async_supabase),
            make_parameter_control_listener_agent(async_supabase),
        ]
        supervisor = AgentSupervisor(agent_list)
        await supervisor.start()
        
        logger.info("Machine control application running")
        logger.info("="*60)
        logger.info("System Status:")
        logger.info(
            f"  - PLC Connection: "
            f"{OK_MARK} Connected" if connection_monitor.plc_status['connected'] else f"{FAIL_MARK} Disconnected"
        )
        logger.info(
            f"  - Realtime Channels: "
            f"{OK_MARK} Active" if connection_monitor.realtime_status['connected'] else f"{WARN_MARK} Using Polling"
        )
        logger.info(f"  - Machine ID: {MACHINE_ID}")
        logger.info("="*60)
        logger.info("Service is ready to receive commands")
        
        # Keep the application running indefinitely
        # Log status every N seconds (default 5 minutes). Overridable via env/CLI.
        try:
            status_log_interval = int(os.getenv("STATUS_LOG_INTERVAL", "300"))
        except ValueError:
            status_log_interval = 300
        last_status_log = asyncio.get_event_loop().time()
        
        while True:
            await asyncio.sleep(1)
            
            # Periodic status logging
            current_time = asyncio.get_event_loop().time()
            if current_time - last_status_log > status_log_interval:
                logger.info(f"[Health Check] PLC: {connection_monitor.plc_status['connected']}, "
                           f"Realtime: {connection_monitor.realtime_status['connected']}, "
                           f"Uptime: {int(current_time)}s")
                last_status_log = current_time
            
    except Exception as e:
        logger.error(f"Error in main application loop: {str(e)}", exc_info=True)
        await cleanup_handler()  # Ensure cleanup happens on unexpected errors too
        raise

if __name__ == "__main__":
    asyncio.run(main())
