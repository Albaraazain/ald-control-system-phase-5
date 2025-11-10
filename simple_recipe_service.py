#!/usr/bin/env python3
"""
Simple Recipe Service - Terminal 2
Simplified standalone recipe command processor with direct PLC access.

This service:
1. Checks recipe_commands table for pending commands
2. Executes recipes directly using PLC manager
3. Updates recipe status in database
4. No complex coordination - just direct recipe execution

DESIGN PRINCIPLES:
- Direct PLC access (no coordination layer)
- Simple polling for commands
- Reuses existing recipe_flow/step_flow logic
- Self-contained service
"""

import sys
import os
import asyncio
import signal
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.log_setup import get_recipe_flow_logger, set_log_level
from src.config import MACHINE_ID
from src.db import get_supabase, get_current_timestamp, create_async_supabase
from src.plc.manager import plc_manager
from src.recipe_flow.executor import execute_recipe
from src.recipe_flow.continuous_data_recorder import continuous_recorder
from src.command_flow.listener import setup_command_listener
from src.terminal_registry import TerminalRegistry, TerminalAlreadyRunningError


logger = get_recipe_flow_logger()


class SimpleRecipeService:
    """Simple recipe service with direct PLC access"""

    def __init__(self):
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.registry: Optional[TerminalRegistry] = None

    async def initialize(self):
        """Initialize PLC connection and terminal registry"""
        logger.info("🔧 Initializing Simple Recipe Service")

        # Register this terminal instance in liveness system
        log_file_path = "/tmp/terminal2_recipe_service.log"
        self.registry = TerminalRegistry(
            terminal_type='terminal2',
            machine_id=MACHINE_ID,
            environment='production',
            heartbeat_interval=10,
            log_file_path=log_file_path
        )

        try:
            await self.registry.register()
            logger.info("✅ Terminal 2 registered in liveness system")
        except TerminalAlreadyRunningError as e:
            logger.error(str(e))
            raise RuntimeError("Cannot start - Terminal 2 already running")

        # Initialize PLC connection
        logger.debug("🔧 Attempting PLC connection initialization...")
        plc_success = await plc_manager.initialize()
        if not plc_success:
            logger.error("❌ Failed to initialize PLC connection")
            raise RuntimeError("Failed to initialize PLC connection")

        logger.info("✅ PLC connection established successfully")

        # Initialize realtime listener for recipe commands
        try:
            async_supabase = await create_async_supabase()
            await setup_command_listener(async_supabase)
            logger.info("✅ Realtime listener initialized (with polling fallback)")
        except Exception as e:
            logger.warning(f"⚠️ Realtime listener failed to initialize: {e}")
            logger.info("📋 Continuing with polling-only mode")

        logger.debug("🔧 Recipe service initialization complete")

    async def check_for_recipe_commands(self) -> Optional[Dict[str, Any]]:
        """Check database for pending recipe commands"""
        logger.debug("📋 Checking database for pending recipe commands...")
        supabase = get_supabase()

        try:
            # Get pending recipe commands for this machine or global commands
            logger.debug(f"💾 Querying recipe_commands for machine_id={MACHINE_ID} or global commands")
            result = supabase.table('recipe_commands').select('*').in_(
                'status', ['pending', 'queued']
            ).or_(
                f'machine_id.eq.{MACHINE_ID},machine_id.is.null'
            ).order('created_at', desc=False).limit(1).execute()

            if result.data:
                command = result.data[0]
                logger.info(f"🔔 New recipe command detected: ID={command['id']}, type={command.get('type', 'start_recipe')}")
                logger.debug(f"📋 Command details: {command}")
                return command
            else:
                logger.debug("📋 No pending recipe commands found")
                return None

        except Exception as e:
            logger.error(f"❌ Error checking for recipe commands: {e}", exc_info=True)
            return None

    async def execute_recipe_command(self, command: Dict[str, Any]) -> bool:
        """Execute a recipe command directly via PLC"""
        command_id = command['id']
        recipe_step_id = command.get('recipe_step_id')
        command_type = command.get('type', 'start_recipe')

        logger.info(f"🔔 Executing recipe command {command_id} (type: {command_type})")

        supabase = get_supabase()

        try:
            # Mark command as executing
            logger.debug(f"💾 Updating command {command_id} status to 'executing'")
            supabase.table('recipe_commands').update({
                'status': 'executing',
                'executed_at': get_current_timestamp()
            }).eq('id', command_id).execute()
            logger.info(f"🟡 Recipe command {command_id} marked as executing")

            if command_type == 'start_recipe':
                # Start a new recipe execution
                logger.info(f"🎬 Starting recipe execution for command {command_id}")
                success = await self._start_recipe_execution(command)
            elif command_type == 'stop_recipe':
                # Stop current recipe
                logger.info(f"🛑 Stopping recipe execution for command {command_id}")
                success = await self._stop_recipe_execution(command)
            else:
                logger.warning(f"⚠️ Unknown recipe command type: {command_type}")
                success = False

            # Update command status
            if success:
                logger.debug(f"💾 Updating command {command_id} status to 'completed'")
                supabase.table('recipe_commands').update({
                    'status': 'completed'
                }).eq('id', command_id).execute()
                logger.info(f"✅ Recipe command {command_id} completed successfully")

                # Track successful command in liveness system
                if self.registry:
                    self.registry.increment_commands()
            else:
                logger.debug(f"💾 Updating command {command_id} status to 'failed'")
                supabase.table('recipe_commands').update({
                    'status': 'failed',
                    'error_message': 'Recipe execution failed'
                }).eq('id', command_id).execute()
                logger.error(f"❌ Recipe command {command_id} failed")

                # Record error in liveness system
                if self.registry:
                    self.registry.record_error(f"Recipe command {command_id} failed")

            return success

        except Exception as e:
            logger.error(f"❌ Error executing recipe command {command_id}: {e}", exc_info=True)

            # Record error in liveness system
            if self.registry:
                self.registry.record_error(f"Recipe command {command_id} exception: {str(e)}")

            # Mark command as failed
            logger.debug(f"💾 Updating command {command_id} status to 'failed' due to exception")
            supabase.table('recipe_commands').update({
                'status': 'failed',
                'error_message': str(e)
            }).eq('id', command_id).execute()
            logger.error(f"❌ Recipe command {command_id} marked as failed in database")

            return False

    async def _start_recipe_execution(self, command: Dict[str, Any]) -> bool:
        """Start a new recipe execution"""
        logger.info("🎬 Starting new recipe execution")
        supabase = get_supabase()
        parameters = command.get('parameters', {})
        recipe_id = parameters.get('recipe_id')

        logger.debug(f"📋 Recipe execution parameters: {parameters}")

        if not recipe_id:
            logger.error("❌ No recipe_id provided in command parameters")
            return False

        logger.info(f"📋 Processing recipe_id: {recipe_id}")

        try:
            # Get recipe details
            logger.debug(f"💾 Fetching recipe details for ID: {recipe_id}")
            recipe_result = supabase.table('recipes').select('*').eq('id', recipe_id).execute()
            if not recipe_result.data:
                logger.error(f"❌ Recipe {recipe_id} not found in database")
                return False

            recipe = recipe_result.data[0]
            logger.info(f"📋 Recipe loaded: '{recipe['name']}' (version: {recipe.get('version', 'unknown')})")

            # Get recipe steps
            logger.debug(f"💾 Fetching recipe steps for recipe_id: {recipe_id}")
            steps_result = supabase.table('recipe_steps').select('*').eq('recipe_id', recipe_id).order('sequence_number').execute()
            recipe_steps = steps_result.data
            logger.info(f"📋 Recipe has {len(recipe_steps)} steps to execute")

            # Create process execution record
            logger.debug("💾 Creating process execution record")
            process_data = {
                'machine_id': MACHINE_ID,
                'recipe_id': recipe_id,
                'recipe_version': {
                    'id': recipe['id'],
                    'name': recipe['name'],
                    'version': recipe['version'],
                    'steps': recipe_steps
                },
                'status': 'running',
                'start_time': get_current_timestamp(),
                'parameters': parameters
            }

            process_result = supabase.table('process_executions').insert(process_data).execute()
            if not process_result.data:
                logger.error("❌ Failed to create process execution record")
                return False

            process_id = process_result.data[0]['id']
            logger.info(f"✅ Process execution record created: {process_id}")

            # Create process execution state record
            logger.info("💾 Creating process_execution_state record for process: " + process_id)
            try:
                state_data = {
                    'execution_id': process_id,
                    'progress': {'total_steps': len(recipe_steps), 'completed_steps': 0},
                    'last_updated': get_current_timestamp()
                }
                logger.debug(f"💾 State data: {state_data}")
                state_result = supabase.table('process_execution_state').insert(state_data).execute()
                if state_result.data:
                    logger.info(f"✅ Process execution state record created successfully")
                else:
                    logger.error(f"❌ Failed to create process_execution_state - no data returned")
            except Exception as e:
                logger.error(f"❌ Failed to create process_execution_state record: {e}", exc_info=True)
                # Try to continue anyway - the executor may create it
                logger.warning("⚠️ Continuing recipe execution despite state record creation failure")

            # Update machine status
            logger.debug(f"💾 Updating machine {MACHINE_ID} status to 'running'")
            supabase.table('machines_base').update({
                'status': 'running',
                'current_process_id': process_id
            }).eq('id', MACHINE_ID).execute()

            supabase.table('machine_state').update({
                'current_state': 'running',
                'process_id': process_id,
                'state_since': get_current_timestamp()
            }).eq('machine_id', MACHINE_ID).execute()
            logger.info(f"✅ Machine {MACHINE_ID} status updated to 'running'")

            # Start continuous data recording
            logger.debug("🔧 Starting continuous data recording")
            await continuous_recorder.start(process_id)
            logger.info("✅ Continuous data recording started")

            # Execute the recipe using existing executor
            logger.info(f"🎬 Starting recipe execution for process {process_id}")
            await execute_recipe(process_id)

            logger.info(f"🟢 Recipe execution completed for process {process_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error in recipe execution: {e}", exc_info=True)

            # Record error in liveness system
            if self.registry:
                self.registry.record_error(f"Recipe execution error: {str(e)}")

            return False

    async def _stop_recipe_execution(self, command: Dict[str, Any]) -> bool:
        """Stop current recipe execution"""
        logger.info("🛑 Starting recipe stop sequence")
        supabase = get_supabase()

        try:
            # Get current running process
            logger.debug(f"💾 Checking for running process on machine {MACHINE_ID}")
            machine_result = supabase.table('machines').select('current_process_id').eq('id', MACHINE_ID).execute()
            if not machine_result.data or not machine_result.data[0]['current_process_id']:
                logger.warning("⚠️ No running process to stop")
                return True

            process_id = machine_result.data[0]['current_process_id']
            logger.info(f"🛑 Stopping recipe execution for process {process_id}")

            # Stop continuous recording
            logger.debug("🔧 Stopping continuous data recording")
            await continuous_recorder.stop()
            logger.info("✅ Continuous data recording stopped")

            # Update process status
            logger.debug(f"💾 Updating process {process_id} status to 'stopped'")
            supabase.table('process_executions').update({
                'status': 'stopped',
                'end_time': get_current_timestamp()
            }).eq('id', process_id).execute()
            logger.info(f"✅ Process {process_id} marked as stopped")

            # Update machine status
            logger.debug(f"💾 Updating machine {MACHINE_ID} status to 'idle'")
            supabase.table('machines_base').update({
                'status': 'idle',
                'current_process_id': None
            }).eq('id', MACHINE_ID).execute()

            supabase.table('machine_state').update({
                'current_state': 'idle',
                'process_id': None,
                'state_since': get_current_timestamp()
            }).eq('machine_id', MACHINE_ID).execute()
            logger.info(f"✅ Machine {MACHINE_ID} status updated to 'idle'")

            logger.info(f"🛑 Recipe execution stopped successfully for process {process_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error stopping recipe: {e}", exc_info=True)
            return False

    async def run(self):
        """Main service loop"""
        logger.info("🚀 Simple Recipe Service started - polling for commands")
        logger.info(f"👂 Listening for recipe commands for machine_id={MACHINE_ID}")
        logger.info("📋 Realtime listener active with polling fallback (2s interval)")
        self.running = True

        poll_count = 0
        while not self.shutdown_event.is_set():
            try:
                poll_count += 1
                logger.debug(f"📋 Polling cycle {poll_count}: Checking for recipe commands...")

                # Check for pending recipe commands
                command = await self.check_for_recipe_commands()

                if command:
                    logger.info(f"🔔 Processing recipe command found on poll cycle {poll_count}")
                    await self.execute_recipe_command(command)
                    # Reset poll count after processing command
                    poll_count = 0
                else:
                    # Only log polling status periodically to avoid spam
                    if poll_count % 30 == 0:  # Every 60 seconds (30 * 2 seconds)
                        logger.debug(f"👂 Still listening... (completed {poll_count} polling cycles)")

                # Poll every 2 seconds
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"❌ Error in main loop (poll cycle {poll_count}): {e}", exc_info=True)
                logger.debug("⚠️ Waiting 5 seconds before retrying due to error")
                await asyncio.sleep(5)  # Wait longer on error

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🔧 Shutting down Simple Recipe Service...")
        self.running = False
        self.shutdown_event.set()

        # Shutdown terminal registry
        if self.registry:
            await self.registry.shutdown(reason="Service shutdown")
            logger.info("✅ Terminal liveness shutdown complete")

        # Disconnect PLC
        logger.debug("🔧 Disconnecting from PLC...")
        await plc_manager.disconnect()
        logger.info("✅ PLC disconnected")
        logger.info("🔧 Simple Recipe Service shutdown complete")


def parse_args():
    """Parse command line arguments"""
    import argparse
    parser = argparse.ArgumentParser(description="Simple Recipe Service")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       default="INFO", help="Logging level")
    parser.add_argument("--machine-id", help="Override machine ID")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")
    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_args()

    # Set log level
    set_log_level(args.log_level)

    # Override machine ID if provided
    if args.machine_id:
        os.environ["MACHINE_ID"] = args.machine_id

    # Setup global exception handlers to catch crashes
    from src.resilience.error_handlers import (
        setup_global_exception_handler,
        setup_asyncio_exception_handler
    )

    logger.info("=" * 60)
    logger.info("🤖 SIMPLE RECIPE SERVICE - TERMINAL 2")
    logger.info(f"   Machine ID: {MACHINE_ID}")
    logger.info(f"   Log Level: {args.log_level}")
    logger.info(f"   Direct PLC Access: ENABLED")
    logger.info(f"   Terminal Liveness: ENABLED")
    logger.info("=" * 60)

    service = SimpleRecipeService()

    # Set up signal handlers - must not create tasks from signal context
    def signal_handler_sync(signum, frame):
        """Handle shutdown signals synchronously"""
        logger.info(f"⚠️ Received signal {signum}, initiating shutdown...")
        service.shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler_sync)
    signal.signal(signal.SIGTERM, signal_handler_sync)

    try:
        logger.info("🔧 Initializing Recipe Service...")
        await service.initialize()

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

        logger.info("🚀 Starting Recipe Service main loop...")
        await service.run()
    except KeyboardInterrupt:
        logger.info("⚠️ Received keyboard interrupt")
    except RuntimeError as e:
        # Handle terminal already running error
        if "already running" in str(e):
            logger.error(str(e))
            sys.exit(1)
        else:
            logger.error(f"❌ Fatal runtime error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())