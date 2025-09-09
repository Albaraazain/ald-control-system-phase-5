# File: main.py
"""
Main entry point for the machine control application.
Sets up listeners and runs the main application loop.
"""
import asyncio
import signal
import sys
from src.log_setup import logger
from src.db import create_async_supabase, get_supabase
from src.command_flow.listener import setup_command_listener
from src.parameter_control_listener import setup_parameter_control_listener
from src.command_flow.status import update_command_status
from src.config import MACHINE_ID
from src.recipe_flow.stopper import update_process_status, update_machine_status, update_machine_state
from src.command_flow.state import state
from src.plc.manager import plc_manager
from src.recipe_flow.continuous_data_recorder import continuous_recorder

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
        logger.error(f"Error during cleanup: {str(e)}")
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
        
        # Initialize PLC connection
        await plc_manager.initialize()
        
        # Create async Supabase client for realtime features
        async_supabase = await create_async_supabase()
        
        # Set up command listener
        await setup_command_listener(async_supabase)
        
        # Set up parameter control listener
        await setup_parameter_control_listener(async_supabase)
        
        logger.info("Machine control application running")
        
        # Keep the application running indefinitely
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in main application loop: {str(e)}", exc_info=True)
        await cleanup_handler()  # Ensure cleanup happens on unexpected errors too
        raise

if __name__ == "__main__":
    asyncio.run(main())