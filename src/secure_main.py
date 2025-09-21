"""
Secure Main Entry Point

This module provides a security-hardened main entry point for the ALD control system
that integrates the comprehensive security framework.
"""

import asyncio
import os
import signal
import sys
from typing import Optional

# Security framework
from src.security import (
    start_security_monitoring,
    stop_security_monitoring,
    record_security_event,
    SecurityEvent,
    ThreatLevel,
    SecurityContext,
    get_security_controller,
    check_plc_access,
    check_database_access
)

# Secure configuration
from src.secure_config import get_secure_config

# Core application components
from src.log_setup import logger, OK_MARK, WARN_MARK, FAIL_MARK
from src.db import create_async_supabase, get_supabase
from src.command_flow.listener import setup_command_listener
from src.command_flow.status import update_command_status
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


class SecureApplicationManager:
    """Secure application manager with comprehensive security integration."""

    def __init__(self):
        """Initialize secure application manager."""
        self.config = None
        self.security_initialized = False
        self.services_started = False
        self.cleanup_handlers = []

    async def initialize_security(self):
        """Initialize security framework and monitoring."""
        try:
            with SecurityContext(
                SecurityEvent.CONFIGURATION_TAMPERING,
                "Security framework initialization"
            ):
                # Start security monitoring
                start_security_monitoring()

                # Load secure configuration
                self.config = get_secure_config()

                # Initialize security controller
                security_controller = get_security_controller()

                # Record successful security initialization
                record_security_event(
                    SecurityEvent.AUTHENTICATION_FAILURE,  # Using as general security event
                    ThreatLevel.LOW,
                    "Security framework initialized successfully",
                    metadata={"initialization": "success"}
                )

                self.security_initialized = True
                logger.info(f"{OK_MARK} Security framework initialized")

        except Exception as e:
            # Record security initialization failure
            record_security_event(
                SecurityEvent.CONFIGURATION_TAMPERING,
                ThreatLevel.CRITICAL,
                f"Security framework initialization failed: {str(e)}",
                metadata={"error": str(e), "initialization": "failed"}
            )
            logger.error(f"{FAIL_MARK} Security initialization failed: {e}")
            raise

    async def validate_configuration(self):
        """Validate configuration with security checks."""
        try:
            with SecurityContext(
                SecurityEvent.CONFIGURATION_TAMPERING,
                "Configuration validation"
            ):
                # Check if all required configuration is present
                if not self.config.is_core_config_ready():
                    missing_keys = self.config.missing_required_keys()
                    raise ValueError(f"Missing required configuration: {missing_keys}")

                # Validate database connectivity with security checks
                if not await check_database_access():
                    raise ConnectionError("Database access validation failed")

                # Validate PLC access with security checks
                if not await check_plc_access():
                    logger.warning("PLC access validation failed - continuing in simulation mode")

                logger.info(f"{OK_MARK} Configuration validation completed")

        except Exception as e:
            record_security_event(
                SecurityEvent.CONFIGURATION_TAMPERING,
                ThreatLevel.HIGH,
                f"Configuration validation failed: {str(e)}",
                metadata={"error": str(e)}
            )
            raise

    async def initialize_database(self):
        """Initialize database connection with security monitoring."""
        try:
            with SecurityContext(
                SecurityEvent.DATABASE_ABUSE,
                "Database initialization"
            ):
                # Get secure database configuration
                db_config = self.config.get_database_config()

                # Create async Supabase client
                await create_async_supabase(db_config['url'], db_config['key'])

                # Test database connection
                supabase = get_supabase()
                # Perform a simple query to validate connection
                test_query = supabase.table('machines').select('id').limit(1).execute()

                logger.info(f"{OK_MARK} Database connection established")

        except Exception as e:
            record_security_event(
                SecurityEvent.DATABASE_ABUSE,
                ThreatLevel.HIGH,
                f"Database initialization failed: {str(e)}",
                metadata={"error": str(e)}
            )
            raise

    async def initialize_plc(self):
        """Initialize PLC connection with security monitoring."""
        try:
            with SecurityContext(
                SecurityEvent.SUSPICIOUS_PLC_ACCESS,
                "PLC initialization"
            ):
                # Get secure PLC configuration
                plc_config = self.config.get_plc_config()

                # Initialize PLC manager with secure configuration
                await plc_manager.initialize(
                    plc_type=plc_config['type'],
                    ip_address=plc_config['ip_address'],
                    port=plc_config['port'],
                    byte_order=plc_config['byte_order']
                )

                logger.info(f"{OK_MARK} PLC connection initialized")

        except Exception as e:
            record_security_event(
                SecurityEvent.SUSPICIOUS_PLC_ACCESS,
                ThreatLevel.MEDIUM,
                f"PLC initialization failed: {str(e)}",
                metadata={"error": str(e)}
            )
            # Continue with simulation mode
            logger.warning(f"{WARN_MARK} PLC initialization failed, continuing in simulation mode")

    async def start_services(self):
        """Start application services with security monitoring."""
        try:
            with SecurityContext(
                SecurityEvent.PRIVILEGE_ESCALATION,
                "Service startup"
            ):
                # Start command listener
                await setup_command_listener()

                # Start data collection service
                await data_collection_service.start()

                # Start connection monitor
                connection_monitor.start()

                # Initialize agent supervisor
                supervisor = AgentSupervisor()
                await supervisor.start()

                # Start command listener agent
                command_agent = make_command_listener_agent()
                await supervisor.add_agent(command_agent)

                # Start connection monitor agent
                monitor_agent = make_connection_monitor_agent()
                await supervisor.add_agent(monitor_agent)

                # Start parameter control listener agent
                param_agent = make_parameter_control_listener_agent()
                await supervisor.add_agent(param_agent)

                self.services_started = True
                logger.info(f"{OK_MARK} All services started successfully")

        except Exception as e:
            record_security_event(
                SecurityEvent.PRIVILEGE_ESCALATION,
                ThreatLevel.HIGH,
                f"Service startup failed: {str(e)}",
                metadata={"error": str(e)}
            )
            raise

    async def cleanup_handler(self):
        """Perform secure cleanup when application is interrupted."""
        logger.info("Beginning secure cleanup process...")

        try:
            with SecurityContext(
                SecurityEvent.CONFIGURATION_TAMPERING,
                "Application cleanup"
            ):
                supabase = get_supabase()
                machine_id = self.config.machine_id

                # Get current machine status
                machine = supabase.table('machines').select('*').eq('id', machine_id).single().execute()

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

                        logger.info("Process stopped and cleaned up during shutdown")

                # Stop data collection service
                if self.services_started:
                    await data_collection_service.stop()
                    connection_monitor.stop()
                    logger.info("Services stopped")

                # Stop security monitoring
                if self.security_initialized:
                    record_security_event(
                        SecurityEvent.AUTHENTICATION_FAILURE,
                        ThreatLevel.LOW,
                        "Application shutdown completed",
                        metadata={"shutdown": "success"}
                    )
                    stop_security_monitoring()

                logger.info(f"{OK_MARK} Secure cleanup completed")

        except Exception as e:
            record_security_event(
                SecurityEvent.CONFIGURATION_TAMPERING,
                ThreatLevel.MEDIUM,
                f"Cleanup process failed: {str(e)}",
                metadata={"error": str(e)}
            )
            logger.error(f"Error during cleanup: {e}")

    async def run(self):
        """Run the secure application."""
        try:
            # Initialize security framework
            await self.initialize_security()

            # Validate configuration
            await self.validate_configuration()

            # Initialize database
            await self.initialize_database()

            # Initialize PLC
            await self.initialize_plc()

            # Start services
            await self.start_services()

            logger.info(f"{OK_MARK} ALD Control System started successfully with security monitoring")

            # Main application loop
            while True:
                await asyncio.sleep(1)

                # Health check with security monitoring
                if not self.services_started:
                    record_security_event(
                        SecurityEvent.NETWORK_ANOMALY,
                        ThreatLevel.HIGH,
                        "Service failure detected",
                        metadata={"health_check": "failed"}
                    )
                    break

        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
        except Exception as e:
            record_security_event(
                SecurityEvent.CONFIGURATION_TAMPERING,
                ThreatLevel.CRITICAL,
                f"Application failure: {str(e)}",
                metadata={"error": str(e), "failure": "critical"}
            )
            logger.error(f"{FAIL_MARK} Application failed: {e}")
            raise
        finally:
            await self.cleanup_handler()


async def main():
    """Secure main entry point."""
    # Set up signal handlers for graceful shutdown
    app_manager = SecureApplicationManager()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(app_manager.cleanup_handler())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the secure application
    await app_manager.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)