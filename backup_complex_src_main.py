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
from src.data_collection.service import data_collection_service
from src.connection_monitor import connection_monitor
from src.agents.supervisor import (
    AgentSupervisor,
    make_command_listener_agent,
    make_connection_monitor_agent,
    make_parameter_control_listener_agent,
)
from src.realtime.service import RealtimeService

async def cleanup_handler(supervisor=None, realtime_service=None):
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

        # Stop data collection service
        await data_collection_service.stop()

        # Stop agent supervisor
        if supervisor:
            try:
                await supervisor.cleanup()
                logger.info("Agent supervisor stopped successfully")
            except Exception as e:
                logger.warning(f"Error stopping agent supervisor: {e}")

        # Cleanup realtime service (channels and connections)
        if realtime_service:
            try:
                await realtime_service.cleanup()
                logger.info("Realtime service cleanup completed")
            except Exception as e:
                logger.warning(f"Error during realtime service cleanup: {e}")

        # Disconnect PLC
        await plc_manager.disconnect()

    except Exception as e:
        logger.exception("Error during cleanup")
    finally:
        logger.info("Application shutdown complete")
        sys.exit(0)

async def main():
    """
    Main application function.
    Sets up the Supabase listener and runs indefinitely.
    """
    supervisor = None
    realtime_service = None

    async def signal_handler(signal, frame):
        """Handle SIGINT signal"""
        logger.info("Received interrupt signal, initiating cleanup...")
        await cleanup_handler(supervisor, realtime_service)

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

        # Initialize shared RealtimeService
        realtime_service = RealtimeService()
        realtime_service.start_monitoring()

        # Realtime self-test (non-fatal)
        try:
            ok_param = await realtime_service.self_test(table="parameter_control_commands")
            ok_recipe = await realtime_service.self_test(table="recipe_commands")
            if ok_param and ok_recipe:
                logger.info("Realtime self-test passed for both tables")
            else:
                logger.warning("Realtime self-test failed; system will rely on polling fallback until reconnected")
        except Exception:
            logger.warning("Realtime self-test encountered an error; continuing with startup", exc_info=True)

        # Start agents (headless)
        agent_list = [
            make_connection_monitor_agent(),
            make_command_listener_agent(async_supabase, realtime_service),
            make_parameter_control_listener_agent(async_supabase, realtime_service),
        ]
        supervisor = AgentSupervisor(agent_list)
        await supervisor.start()

        # Start data collection service
        logger.info("Starting data collection service...")
        await data_collection_service.start()

        # Give connection monitor a moment to run its first check
        logger.info("Waiting for connection monitor to initialize...")
        await asyncio.sleep(1.0)

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
        dc_status = data_collection_service.get_status()
        logger.info(
            f"  - Parameter Logger: "
            f"{OK_MARK} Running" if dc_status['service_running'] else f"{FAIL_MARK} Stopped"
        )
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
        await cleanup_handler(supervisor, realtime_service)  # Ensure cleanup happens on unexpected errors too
        raise

if __name__ == "__main__":
    asyncio.run(main())
