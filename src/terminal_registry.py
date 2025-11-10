"""
Terminal Registry - Liveness Management System

Manages terminal instance registration, heartbeat, and health tracking in Supabase.
Prevents duplicate instances and enables monitoring/auto-recovery.

Usage:
    from src.terminal_registry import TerminalRegistry

    # In terminal startup
    registry = TerminalRegistry(
        terminal_type='terminal2',
        machine_id=os.environ.get('MACHINE_ID'),
        environment='production'
    )

    # Register and start heartbeat
    await registry.register()

    # Update metrics during operation
    registry.increment_commands()
    registry.record_error("Error message")

    # Graceful shutdown
    await registry.shutdown()
"""

import os
import sys
import asyncio
import socket
import platform
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import signal

from src.log_setup import logger, get_service_logger
from src.db import get_supabase, get_current_timestamp

# Get dedicated logger for terminal registry
registry_logger = get_service_logger('agents')  # Using agents logger for now, could create terminal_registry logger


class TerminalAlreadyRunningError(Exception):
    """Raised when attempting to start a terminal that's already running"""
    pass


class TerminalRegistry:
    """
    Manages terminal instance lifecycle with Supabase liveness tracking.

    Features:
    - Duplicate prevention via UNIQUE constraint
    - Automatic heartbeat loop
    - Graceful shutdown handling
    - Health metrics tracking
    - Status management
    """

    def __init__(
        self,
        terminal_type: str,
        machine_id: str,
        environment: str = 'production',
        heartbeat_interval: int = 10,
        log_file_path: Optional[str] = None
    ):
        """
        Initialize terminal registry.

        Args:
            terminal_type: Type of terminal ('terminal1', 'terminal2', 'terminal3')
            machine_id: Machine UUID this terminal serves
            environment: Deployment environment ('production', 'development', 'testing')
            heartbeat_interval: Seconds between heartbeats (default 10)
            log_file_path: Path to terminal log file for debugging
        """
        self.terminal_type = terminal_type
        self.machine_id = machine_id
        self.environment = environment
        self.heartbeat_interval = heartbeat_interval
        self.log_file_path = log_file_path

        # Instance tracking
        self.instance_id: Optional[str] = None
        self.hostname = socket.gethostname()
        self.process_id = os.getpid()
        self.python_version = platform.python_version()
        self.git_commit_hash = self._get_git_commit()

        # Health tracking
        self.status = 'starting'
        self.commands_processed = 0
        self.errors_encountered = 0
        self.last_error_message: Optional[str] = None

        # Heartbeat control
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._registered = False

        # Supabase client
        self.supabase = get_supabase()

        registry_logger.info(
            f"🔧 Initializing {terminal_type} registry for machine {machine_id}"
        )

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash if available."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    async def register(self) -> str:
        """
        Register terminal instance in database.

        Returns:
            Terminal instance UUID

        Raises:
            TerminalAlreadyRunningError: If another instance is already running
        """
        if self._registered:
            registry_logger.warning("Terminal already registered")
            return self.instance_id

        try:
            # Check for existing active instance
            existing = self.supabase.table('terminal_instances').select('*').eq(
                'terminal_type', self.terminal_type
            ).eq(
                'machine_id', self.machine_id
            ).in_(
                'status', ['starting', 'healthy', 'degraded', 'stopping']
            ).execute()

            if existing.data:
                existing_instance = existing.data[0]
                existing_pid = existing_instance['process_id']

                # Check if the PID actually exists (process still running)
                try:
                    import os
                    import signal
                    # Send signal 0 to check if process exists (doesn't actually send signal)
                    os.kill(existing_pid, 0)
                    # Process exists - it's truly running
                    process_exists = True
                except (OSError, ProcessLookupError):
                    # Process doesn't exist - stale database entry
                    process_exists = False

                if process_exists:
                    # Process is actually running - block registration
                    error_msg = (
                        f"❌ {self.terminal_type} already running!\n"
                        f"   Instance ID: {existing_instance['id']}\n"
                        f"   Hostname: {existing_instance['hostname']}\n"
                        f"   PID: {existing_instance['process_id']}\n"
                        f"   Status: {existing_instance['status']}\n"
                        f"   Started: {existing_instance['started_at']}\n"
                        f"   Last Heartbeat: {existing_instance['last_heartbeat']}"
                    )
                    registry_logger.error(error_msg)
                    raise TerminalAlreadyRunningError(error_msg)
                else:
                    # Process doesn't exist - clean up stale entry
                    registry_logger.warning(
                        f"⚠️ Found stale {self.terminal_type} entry (PID {existing_pid} not found)\n"
                        f"   Marking as crashed and allowing new registration..."
                    )
                    # Mark as crashed
                    self.supabase.table('terminal_instances').update({
                        'status': 'crashed',
                        'crash_detected_at': 'now()',
                        'last_error_message': 'Process terminated without cleanup (stale PID)'
                    }).eq('id', existing_instance['id']).execute()

            # Register new instance
            record = {
                'terminal_type': self.terminal_type,
                'machine_id': self.machine_id,
                'hostname': self.hostname,
                'process_id': self.process_id,
                'python_version': self.python_version,
                'git_commit_hash': self.git_commit_hash,
                'status': 'starting',
                'environment': self.environment,
                'log_file_path': self.log_file_path,
                'heartbeat_interval_seconds': self.heartbeat_interval,
            }

            result = self.supabase.table('terminal_instances').insert(record).execute()

            if result.data:
                self.instance_id = result.data[0]['id']
                self._registered = True

                registry_logger.info(
                    f"✅ {self.terminal_type} registered successfully\n"
                    f"   Instance ID: {self.instance_id}\n"
                    f"   Hostname: {self.hostname}\n"
                    f"   PID: {self.process_id}"
                )

                # Start heartbeat loop
                await self.start_heartbeat()

                # Register signal handlers for graceful shutdown
                self._setup_signal_handlers()

                # Mark as healthy after successful startup
                await self.set_status('healthy')

                return self.instance_id
            else:
                raise Exception("Failed to register terminal - no data returned")

        except TerminalAlreadyRunningError:
            raise
        except Exception as e:
            registry_logger.error(f"❌ Failed to register terminal: {e}", exc_info=True)
            raise

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            registry_logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
            # Set shutdown event from signal handler (synchronous)
            self._shutdown_event.set()
            # Schedule shutdown coroutine safely
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.shutdown())
            except RuntimeError:
                # No running loop - will be handled by main
                registry_logger.warning("No running event loop, shutdown will be handled by main")

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def start_heartbeat(self):
        """Start background heartbeat task."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            registry_logger.warning("Heartbeat already running")
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        registry_logger.info(f"💓 Heartbeat started (interval: {self.heartbeat_interval}s)")

    async def _heartbeat_loop(self):
        """Background task that sends periodic heartbeats."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                registry_logger.info("💓 Heartbeat cancelled")
                break
            except Exception as e:
                registry_logger.error(f"❌ Heartbeat error: {e}", exc_info=True)
                # Continue heartbeat even on error

    async def _send_heartbeat(self):
        """Send heartbeat update to database with retry logic."""
        if not self._registered or not self.instance_id:
            return

        try:
            # Use retry logic for heartbeat
            from src.resilience import retry_heartbeat

            @retry_heartbeat
            async def _update_heartbeat():
                update = {
                    'last_heartbeat': get_current_timestamp(),
                    'commands_processed': self.commands_processed,
                    'errors_encountered': self.errors_encountered,
                    'last_error_message': self.last_error_message,
                }

                self.supabase.table('terminal_instances').update(update).eq(
                    'id', self.instance_id
                ).execute()

                # Reset missed heartbeats counter on successful heartbeat
                self.supabase.table('terminal_instances').update({
                    'missed_heartbeats': 0
                }).eq('id', self.instance_id).execute()

            await _update_heartbeat()

        except Exception as e:
            registry_logger.error(
                f"❌ CRITICAL: Failed to send heartbeat after retries: {e}\n"
                f"   This may cause terminal to be marked as crashed."
            )

    async def set_status(self, status: str, reason: Optional[str] = None):
        """
        Update terminal status.

        Args:
            status: New status ('starting', 'healthy', 'degraded', 'stopping', 'stopped', 'crashed')
            reason: Optional reason for status change
        """
        if not self._registered:
            return

        old_status = self.status
        self.status = status

        try:
            update = {'status': status}

            if status == 'stopped':
                update['stopped_at'] = get_current_timestamp()
            elif status == 'crashed':
                update['crash_detected_at'] = get_current_timestamp()

            self.supabase.table('terminal_instances').update(update).eq(
                'id', self.instance_id
            ).execute()

            registry_logger.info(f"📊 Status changed: {old_status} → {status}")
            if reason:
                registry_logger.info(f"   Reason: {reason}")

        except Exception as e:
            registry_logger.error(f"Failed to update status: {e}")

    def increment_commands(self, count: int = 1):
        """Increment commands processed counter."""
        self.commands_processed += count

    def record_error(self, error_message: str):
        """Record an error with retry logic."""
        self.errors_encountered += 1
        self.last_error_message = error_message[:500]  # Truncate long errors

        # Update database immediately for errors
        try:
            from src.resilience import retry_database

            # Use sync wrapper for database update
            import asyncio

            async def _update_error():
                @retry_database
                async def _db_update():
                    self.supabase.table('terminal_instances').update({
                        'errors_encountered': self.errors_encountered,
                        'last_error_message': error_message[:500],
                        'last_error_at': get_current_timestamp()
                    }).eq('id', self.instance_id).execute()

                await _db_update()

            # Run in event loop if available, otherwise log warning
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(_update_error())
                else:
                    loop.run_until_complete(_update_error())
            except RuntimeError:
                # No event loop - try direct update
                registry_logger.warning("No event loop for error recording - using direct update")
                self.supabase.table('terminal_instances').update({
                    'errors_encountered': self.errors_encountered,
                    'last_error_message': error_message[:500],
                    'last_error_at': get_current_timestamp()
                }).eq('id', self.instance_id).execute()

        except Exception as e:
            registry_logger.error(f"Failed to record error in database: {e}")

    async def shutdown(self, reason: str = "Graceful shutdown"):
        """
        Gracefully shutdown terminal and cleanup.

        Args:
            reason: Reason for shutdown
        """
        if not self._registered:
            return

        registry_logger.info(f"🛑 Shutting down {self.terminal_type}...")
        registry_logger.info(f"   Reason: {reason}")

        # Signal shutdown event
        self._shutdown_event.set()

        # Update status to stopping (with timeout)
        try:
            await asyncio.wait_for(self.set_status('stopping', reason), timeout=3.0)
        except asyncio.TimeoutError:
            registry_logger.warning("⏱️ Status update timed out during shutdown")

        # Cancel heartbeat task
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await asyncio.wait_for(self._heartbeat_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Final status update (with timeout)
        try:
            await asyncio.wait_for(self.set_status('stopped', reason), timeout=3.0)
        except asyncio.TimeoutError:
            registry_logger.warning("⏱️ Final status update timed out")

        # Final metrics update (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: self.supabase.table('terminal_instances').update({
                        'commands_processed': self.commands_processed,
                        'errors_encountered': self.errors_encountered,
                        'stopped_at': get_current_timestamp()
                    }).eq('id', self.instance_id).execute()
                ),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            registry_logger.warning("⏱️ Final metrics update timed out")
        except Exception as e:
            registry_logger.error(f"Failed final update: {e}")

        self._registered = False

        registry_logger.info(
            f"✅ {self.terminal_type} shutdown complete\n"
            f"   Commands Processed: {self.commands_processed}\n"
            f"   Errors Encountered: {self.errors_encountered}"
        )

    async def __aenter__(self):
        """Context manager entry - register terminal."""
        await self.register()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - shutdown terminal."""
        if exc_type:
            await self.shutdown(f"Exception: {exc_type.__name__}: {exc_val}")
        else:
            await self.shutdown("Normal completion")
        return False  # Don't suppress exceptions
