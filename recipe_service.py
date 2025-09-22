#!/usr/bin/env python3
"""
Terminal 2: Recipe Service
Primary responsibility: Recipe command processing and workflow execution

This service handles:
- Recipe command listener for database commands
- Recipe workflow execution and step-by-step processing
- Database coordination with Terminal 1 for hardware operations
- Recipe state management and progress tracking
- Emergency recipe abort coordination

CRITICAL: This terminal NEVER directly accesses PLC hardware.
All hardware operations are requested from Terminal 1 via database coordination.
"""

import sys
import os
import argparse
import asyncio
import atexit
import fcntl
import signal
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.log_setup import get_recipe_flow_logger, set_log_level
from src.config import MACHINE_ID
from src.db import create_async_supabase, get_supabase
from src.recipe_service.listener import RecipeCommandListener
from src.recipe_service.executor import RecipeExecutor
from src.recipe_service.coordinator import DatabaseCoordinator
from src.recipe_service.validation import RecipeServiceValidator
from src.connection_monitor import connection_monitor
from src.realtime.service import RealtimeService


logger = get_recipe_flow_logger()


def ensure_single_instance():
    """Ensure only one recipe_service instance runs"""
    lock_file = "/tmp/recipe_service.lock"
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Write PID to lock file
        os.write(fd, f"{os.getpid()}\n".encode())
        os.fsync(fd)

        # Clean up on exit
        atexit.register(lambda: os.unlink(lock_file) if os.path.exists(lock_file) else None)

        return fd
    except (OSError, IOError):
        logger.error("❌ Another recipe_service is already running")
        logger.error("💡 Kill existing instances or wait for them to finish")
        exit(1)


class RecipeService:
    """
    Main Recipe Service class for Terminal 2.
    Manages recipe command processing and workflow execution.
    """

    def __init__(self, skip_validation=False):
        self.listener = None
        self.executor = None
        self.coordinator = None
        self.realtime_service = None
        self.async_supabase = None
        self.shutdown_event = asyncio.Event()
        self.skip_validation = skip_validation

    async def initialize(self):
        """Initialize all service components"""
        logger.info("Initializing Recipe Service (Terminal 2)")

        # Validate setup before initialization (unless skipped)
        if not self.skip_validation:
            validator = RecipeServiceValidator()
            validation_results = await validator.validate_full_setup()

            if not all(validation_results.values()):
                raise RuntimeError("Recipe Service validation failed - check logs for details")
        else:
            logger.warning("⚠️ Skipping startup validation (development mode)")

        # Create async Supabase client
        logger.info("Creating async Supabase client...")
        self.async_supabase = await create_async_supabase()

        # Initialize realtime service
        self.realtime_service = RealtimeService()
        self.realtime_service.start_monitoring()

        # Realtime self-test
        try:
            ok_recipe = await self.realtime_service.self_test(table="recipe_commands")
            if ok_recipe:
                logger.info("Recipe commands realtime self-test passed")
            else:
                logger.warning("Recipe commands realtime self-test failed; will use polling fallback")
        except Exception:
            logger.warning("Recipe commands realtime self-test error; continuing with startup", exc_info=True)

        # Initialize database coordinator for Terminal 1 communication
        self.coordinator = DatabaseCoordinator()
        await self.coordinator.initialize()

        # Initialize recipe executor
        self.executor = RecipeExecutor(self.coordinator)
        await self.executor.initialize()

        # Initialize recipe command listener
        self.listener = RecipeCommandListener(
            self.async_supabase,
            self.realtime_service,
            self.executor
        )
        await self.listener.initialize()

        logger.info("Recipe Service initialization complete")

    async def start(self):
        """Start the recipe service"""
        logger.info("Starting Recipe Service...")

        # Start all components
        await self.coordinator.start()
        await self.executor.start()
        await self.listener.start()

        logger.info("="*60)
        logger.info("Recipe Service Status:")
        logger.info(f"  - Machine ID: {MACHINE_ID}")
        logger.info(f"  - Recipe Commands: Ready")
        logger.info(f"  - Database Coordination: Active")
        logger.info(f"  - Recipe Executor: Ready")
        logger.info("="*60)
        logger.info("Recipe Service is ready to process commands")

    async def run(self):
        """Main service loop"""
        try:
            # Keep service running until shutdown
            while not self.shutdown_event.is_set():
                await asyncio.sleep(1)

                # Periodic health check every 5 minutes
                if hasattr(self, '_last_health_log'):
                    if asyncio.get_event_loop().time() - self._last_health_log > 300:
                        await self._log_health_status()
                        self._last_health_log = asyncio.get_event_loop().time()
                else:
                    self._last_health_log = asyncio.get_event_loop().time()

        except Exception as e:
            logger.error(f"Error in recipe service main loop: {e}", exc_info=True)
            raise

    async def _log_health_status(self):
        """Log periodic health status"""
        logger.info("[Health Check] Recipe Service running, "
                   f"Coordinator: {self.coordinator.is_healthy()}, "
                   f"Executor: {self.executor.is_healthy()}, "
                   f"Listener: {self.listener.is_healthy()}")

    async def shutdown(self):
        """Graceful shutdown of the service"""
        logger.info("Shutting down Recipe Service...")

        # Signal shutdown
        self.shutdown_event.set()

        # Stop components in reverse order
        if self.listener:
            await self.listener.stop()
        if self.executor:
            await self.executor.stop()
        if self.coordinator:
            await self.coordinator.stop()
        if self.realtime_service:
            await self.realtime_service.cleanup()

        logger.info("Recipe Service shutdown complete")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="ALD Recipe Service (Terminal 2)")
    parser.add_argument("--log-level", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
                       help="Logging level (default: INFO)")
    parser.add_argument("--machine-id", help="Override machine ID")
    parser.add_argument("--skip-validation", action="store_true",
                       help="Skip startup validation (for development)")
    return parser.parse_args()


async def signal_handler(recipe_service, sig):
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    await recipe_service.shutdown()


async def main():
    """Main entry point for Recipe Service"""
    # Ensure only one instance runs
    ensure_single_instance()

    args = parse_args()

    # Set log level
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level
        set_log_level(args.log_level)
    else:
        set_log_level(os.environ.get("LOG_LEVEL", "INFO"))

    # Override machine ID if provided
    if args.machine_id:
        os.environ["MACHINE_ID"] = args.machine_id

    logger.info("Starting ALD Recipe Service (Terminal 2)")
    logger.info(f"Machine ID: {MACHINE_ID}")
    logger.info(f"Log Level: {os.environ.get('LOG_LEVEL', 'INFO')}")

    recipe_service = RecipeService(skip_validation=args.skip_validation)

    # Set up signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda s, f: asyncio.create_task(signal_handler(recipe_service, s)))

    try:
        await recipe_service.initialize()
        await recipe_service.start()
        await recipe_service.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error in Recipe Service: {e}", exc_info=True)
        raise
    finally:
        await recipe_service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())