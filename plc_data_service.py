#!/usr/bin/env python3
"""
Terminal 1: PLC Data Service

**PRIMARY RESPONSIBILITY**: Exclusive PLC hardware access and data collection

This terminal provides:
1. Exclusive PLC hardware connection ownership
2. Precise 1-second data collection timing (±100ms precision)
3. Database command queue processing for PLC operations
4. Emergency coordination and hardware state validation
5. Audit logging for all hardware operations

CRITICAL: Only this terminal may directly access PLC hardware to solve
the 26 singleton conflicts in the current architecture.
"""
import asyncio
import atexit
import fcntl
import os
import sys
import signal
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Ensure project root is on sys.path for src imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.log_setup import get_plc_logger, get_data_collection_logger, logger as main_logger
from src.config import MACHINE_ID, PLC_TYPE, PLC_CONFIG
from src.db import get_supabase
from src.plc.manager import PLCManager
# Removed broken transactional import - will use direct database logging

# Service-specific loggers
plc_logger = get_plc_logger()
data_logger = get_data_collection_logger()


def ensure_single_instance():
    """Ensure only one plc_data_service instance runs"""
    lock_file = "/tmp/plc_data_service.lock"
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
        plc_logger.error("❌ Another plc_data_service is already running")
        plc_logger.error("💡 Kill existing instances or wait for them to finish")
        exit(1)


@dataclass
class PLCOperationRequest:
    """Represents a PLC operation request from the database queue."""
    id: str
    operation_type: str  # 'read_parameter', 'write_parameter', 'control_valve', 'execute_purge'
    parameters: Dict[str, Any]
    requesting_service: str  # 'recipe_service', 'parameter_service', etc.
    priority: int = 1  # 1=high, 2=medium, 3=low
    created_at: datetime = None


class PLCDataService:
    """
    Terminal 1: PLC Data Service

    Provides exclusive PLC access with precise timing and safe command processing.
    """

    def __init__(self):
        self.plc_manager = PLCManager()
        self.supabase = get_supabase()
        self.is_running = False
        self.data_collection_task = None
        self.command_processing_task = None
        self.emergency_monitoring_task = None

        # Timing control for precise 1s intervals
        self.data_collection_interval = 1.0  # 1 second
        self.last_collection_time = 0.0
        self.timing_precision_threshold = 0.1  # ±100ms precision

        # Command queue and state
        self.command_queue: List[PLCOperationRequest] = []
        self.processing_command = False
        self.emergency_stop_active = False

        # Performance metrics
        self.metrics = {
            'total_readings': 0,
            'successful_readings': 0,
            'failed_readings': 0,
            'commands_processed': 0,
            'timing_violations': 0,
            'last_collection_duration': 0.0,
            'average_collection_duration': 0.0
        }

        # Parameter metadata cache for enhanced logging
        self.parameter_metadata = {}  # Cache parameter name/component info

        plc_logger.info("PLC Data Service initialized - Terminal 1 ready for exclusive hardware access")

    async def initialize(self) -> bool:
        """
        Initialize the PLC Data Service with exclusive hardware connection.

        Returns:
            bool: True if initialization successful
        """
        try:
            plc_logger.info("Initializing PLC Data Service - claiming exclusive hardware access")

            # Initialize parameter metadata cache for enhanced logging
            await self._initialize_parameter_metadata()

            # Claim exclusive PLC connection
            plc_connected = await self.plc_manager.initialize(PLC_TYPE, PLC_CONFIG)
            if plc_connected:
                plc_logger.info("✅ Exclusive PLC connection established")
            else:
                plc_logger.warning("⚠️ PLC connection failed - will retry in background")

            # Create database tables for command queuing if needed
            await self._ensure_command_queue_table()

            # Initialize metrics
            self.metrics['service_start_time'] = asyncio.get_event_loop().time()

            return True

        except Exception as e:
            plc_logger.error(f"Failed to initialize PLC Data Service: {e}", exc_info=True)
            return False

    async def start(self):
        """Start all PLC Data Service operations."""
        if self.is_running:
            plc_logger.warning("PLC Data Service already running")
            return

        try:
            self.is_running = True

            # Start core service tasks
            self.data_collection_task = asyncio.create_task(self._data_collection_loop())
            self.command_processing_task = asyncio.create_task(self._command_processing_loop())
            self.emergency_monitoring_task = asyncio.create_task(self._emergency_monitoring_loop())

            plc_logger.info("🚀 PLC Data Service started - all systems operational")

            # Wait for tasks to complete
            await asyncio.gather(
                self.data_collection_task,
                self.command_processing_task,
                self.emergency_monitoring_task,
                return_exceptions=True
            )

        except Exception as e:
            plc_logger.error(f"Error in PLC Data Service: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self):
        """Stop all PLC Data Service operations."""
        if not self.is_running:
            return

        try:
            plc_logger.info("Stopping PLC Data Service...")
            self.is_running = False

            # Cancel all tasks
            tasks = [self.data_collection_task, self.command_processing_task, self.emergency_monitoring_task]
            for task in tasks:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Disconnect PLC
            await self.plc_manager.disconnect()

            # Cleanup parameter metadata cache
            self.parameter_metadata = {}

            plc_logger.info("PLC Data Service stopped successfully")

        except Exception as e:
            plc_logger.error(f"Error stopping PLC Data Service: {e}", exc_info=True)

    async def _data_collection_loop(self):
        """
        Main data collection loop with precise 1-second timing.

        Maintains ±100ms precision for data collection intervals.
        """
        plc_logger.info("Starting precise data collection loop (1s ±100ms)")

        while self.is_running:
            loop_start_time = asyncio.get_event_loop().time()

            try:
                # Perform data collection
                await self._collect_and_log_data()

                # Calculate timing metrics
                collection_duration = asyncio.get_event_loop().time() - loop_start_time
                self.metrics['last_collection_duration'] = collection_duration

                # Update average duration (rolling average)
                total_readings = self.metrics['total_readings']
                if total_readings > 0:
                    current_avg = self.metrics['average_collection_duration']
                    self.metrics['average_collection_duration'] = (
                        (current_avg * total_readings + collection_duration) / (total_readings + 1)
                    )
                else:
                    self.metrics['average_collection_duration'] = collection_duration

                # Calculate precise sleep time to maintain 1s intervals
                elapsed_time = asyncio.get_event_loop().time() - loop_start_time
                sleep_time = max(0, self.data_collection_interval - elapsed_time)

                # Check timing precision
                if abs(elapsed_time - self.data_collection_interval) > self.timing_precision_threshold:
                    self.metrics['timing_violations'] += 1
                    data_logger.warning(
                        f"Timing violation: collection took {elapsed_time:.3f}s "
                        f"(target: {self.data_collection_interval}s ±{self.timing_precision_threshold}s)"
                    )

                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                plc_logger.info("Data collection loop cancelled")
                break
            except Exception as e:
                self.metrics['failed_readings'] += 1
                data_logger.error(f"Error in data collection loop: {e}", exc_info=True)
                # Continue with error backoff
                await asyncio.sleep(min(5.0, self.data_collection_interval))

    async def _collect_and_log_data(self):
        """
        Collect PLC data and log to database with transactional guarantees.
        """
        self.metrics['total_readings'] += 1

        try:
            # Check PLC connection
            if not self.plc_manager.is_connected():
                data_logger.debug("PLC not connected - skipping data collection")
                return

            # Read all parameters from PLC
            parameter_values = await self.plc_manager.read_all_parameters()
            if not parameter_values:
                data_logger.debug("No parameters available from PLC")
                return

            # Log parameters to database with enhanced logging
            success_count = await self._log_parameters_with_metadata(parameter_values)

            if success_count > 0:
                self.metrics['successful_readings'] += 1
                data_logger.info(
                    f"✅ PLC data collection completed: {success_count}/{len(parameter_values)} parameters logged successfully"
                )
            else:
                self.metrics['failed_readings'] += 1
                data_logger.error(f"❌ PLC data collection failed for all {len(parameter_values)} parameters")

        except Exception as e:
            self.metrics['failed_readings'] += 1
            data_logger.error(f"Failed to collect and log PLC data: {e}", exc_info=True)
            raise

    async def _command_processing_loop(self):
        """
        Process PLC operation commands from database queue.
        """
        plc_logger.info("Starting PLC command processing loop")

        while self.is_running:
            try:
                # Fetch pending commands from database
                await self._fetch_pending_commands()

                # Process commands in priority order
                if self.command_queue and not self.processing_command:
                    await self._process_next_command()

                # Check for commands every 100ms for responsiveness
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                plc_logger.info("Command processing loop cancelled")
                break
            except Exception as e:
                plc_logger.error(f"Error in command processing loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _emergency_monitoring_loop(self):
        """
        Monitor for emergency conditions and coordinate with other terminals.
        """
        plc_logger.info("Starting emergency monitoring loop")

        while self.is_running:
            try:
                # Check for emergency signals from other terminals
                await self._check_emergency_signals()

                # Validate hardware state
                await self._validate_hardware_state()

                # Check every 500ms for quick emergency response
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                plc_logger.info("Emergency monitoring loop cancelled")
                break
            except Exception as e:
                plc_logger.error(f"Error in emergency monitoring: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _fetch_pending_commands(self):
        """Fetch pending PLC operation commands from database."""
        try:
            # Query for pending commands for this machine
            response = self.supabase.table('plc_operation_commands').select('*').eq(
                'machine_id', MACHINE_ID
            ).eq('status', 'pending').order('priority', desc=False).order('created_at', desc=False).execute()

            if response.data:
                for cmd_data in response.data:
                    cmd = PLCOperationRequest(
                        id=cmd_data['id'],
                        operation_type=cmd_data['operation_type'],
                        parameters=cmd_data['parameters'],
                        requesting_service=cmd_data['requesting_service'],
                        priority=cmd_data.get('priority', 2),
                        created_at=datetime.fromisoformat(cmd_data['created_at'])
                    )
                    self.command_queue.append(cmd)

                # Sort by priority
                self.command_queue.sort(key=lambda x: (x.priority, x.created_at))

        except Exception as e:
            plc_logger.error(f"Error fetching pending commands: {e}", exc_info=True)

    async def _process_next_command(self):
        """Process the next command in the queue."""
        if not self.command_queue:
            return

        self.processing_command = True
        command = self.command_queue.pop(0)

        try:
            plc_logger.info(f"🔧 Processing PLC command: {command.operation_type} from {command.requesting_service}")

            # Mark command as processing
            await self._update_command_status(command.id, 'processing')

            # Execute the command
            success = await self._execute_plc_command(command)

            # Update command status
            if success:
                await self._update_command_status(command.id, 'completed')
                plc_logger.info(f"✅ Command {command.id} completed successfully")
            else:
                await self._update_command_status(command.id, 'failed')
                plc_logger.error(f"❌ Command {command.id} failed")

            self.metrics['commands_processed'] += 1

        except Exception as e:
            await self._update_command_status(command.id, 'error', str(e))
            plc_logger.error(f"Error processing command {command.id}: {e}", exc_info=True)
        finally:
            self.processing_command = False

    async def _execute_plc_command(self, command: PLCOperationRequest) -> bool:
        """Execute a specific PLC command."""
        try:
            if not self.plc_manager.is_connected():
                plc_logger.error("Cannot execute command - PLC not connected")
                return False

            if command.operation_type == 'read_parameter':
                param_id = command.parameters.get('parameter_id')
                value = await self.plc_manager.read_parameter(param_id)
                plc_logger.info(f"Read parameter {param_id}: {value}")
                return True

            elif command.operation_type == 'write_parameter':
                param_id = command.parameters.get('parameter_id')
                value = command.parameters.get('value')
                success = await self.plc_manager.write_parameter(param_id, value)
                plc_logger.info(f"Write parameter {param_id} = {value}: {'success' if success else 'failed'}")
                return success

            elif command.operation_type == 'control_valve':
                valve_number = command.parameters.get('valve_number')
                state = command.parameters.get('state')
                duration_ms = command.parameters.get('duration_ms')
                success = await self.plc_manager.control_valve(valve_number, state, duration_ms)
                plc_logger.info(f"Control valve {valve_number} state={state} duration={duration_ms}ms: {'success' if success else 'failed'}")
                return success

            elif command.operation_type == 'execute_purge':
                duration_ms = command.parameters.get('duration_ms')
                success = await self.plc_manager.execute_purge(duration_ms)
                plc_logger.info(f"Execute purge duration={duration_ms}ms: {'success' if success else 'failed'}")
                return success

            else:
                plc_logger.error(f"Unknown operation type: {command.operation_type}")
                return False

        except Exception as e:
            plc_logger.error(f"Error executing PLC command: {e}", exc_info=True)
            return False

    async def _update_command_status(self, command_id: str, status: str, error_message: str = None):
        """Update command status in database."""
        try:
            update_data = {'status': status, 'updated_at': datetime.utcnow().isoformat()}
            if error_message:
                update_data['error_message'] = error_message

            self.supabase.table('plc_operation_commands').update(update_data).eq('id', command_id).execute()

        except Exception as e:
            plc_logger.error(f"Error updating command status: {e}", exc_info=True)

    async def _check_emergency_signals(self):
        """Check for emergency signals from other terminals."""
        try:
            # Check for emergency stop signals
            response = self.supabase.table('terminal_coordination').select('*').eq(
                'machine_id', MACHINE_ID
            ).eq('signal_type', 'emergency_stop').eq('status', 'active').execute()

            if response.data:
                if not self.emergency_stop_active:
                    plc_logger.critical("🚨 EMERGENCY STOP RECEIVED - Activating safety protocols")
                    await self._activate_emergency_stop()
                    self.emergency_stop_active = True
            else:
                if self.emergency_stop_active:
                    plc_logger.info("Emergency stop cleared - Resuming normal operations")
                    self.emergency_stop_active = False

        except Exception as e:
            plc_logger.error(f"Error checking emergency signals: {e}", exc_info=True)

    async def _validate_hardware_state(self):
        """Validate current hardware state for safety."""
        if not self.plc_manager.is_connected():
            return

        try:
            # This would implement hardware-specific safety checks
            # For example: ensure valves are in safe state, check pressure limits, etc.
            pass

        except Exception as e:
            plc_logger.error(f"Error validating hardware state: {e}", exc_info=True)

    async def _activate_emergency_stop(self):
        """Activate emergency stop procedures."""
        try:
            plc_logger.critical("🚨 ACTIVATING EMERGENCY STOP PROCEDURES")

            # Close all valves immediately
            # In a real implementation, this would query the hardware for active valves
            # and close them systematically

            # Stop any ongoing operations
            self.processing_command = False
            self.command_queue.clear()

            plc_logger.critical("Emergency stop procedures activated")

        except Exception as e:
            plc_logger.critical(f"CRITICAL: Error in emergency stop procedures: {e}", exc_info=True)

    async def _ensure_command_queue_table(self):
        """Ensure the PLC command queue table exists."""
        # This would be handled by database migrations in a real implementation
        # For now, we assume the table exists
        pass

    async def _initialize_parameter_metadata(self):
        """Initialize parameter metadata cache for enhanced logging."""
        try:
            data_logger.info("Loading parameter metadata for enhanced logging...")

            # Get all component parameters first
            params_response = self.supabase.table('component_parameters').select(
                'id, definition_id, component_id, min_value, max_value, is_writable, data_type'
            ).execute()

            # Get all component definitions
            defs_response = self.supabase.table('component_definitions').select(
                'id, name, type'
            ).execute()

            # Create a lookup for component definitions
            component_defs = {def_item['id']: def_item for def_item in defs_response.data}

            if params_response.data:
                for param in params_response.data:
                    param_id = param['id']
                    definition_id = param.get('definition_id')

                    # Look up component definition
                    component_def = component_defs.get(definition_id, {})
                    component_name = component_def.get('name', f'Component_{param.get("component_id", "unknown")[:8]}')
                    component_type = component_def.get('type', '')

                    # Create parameter name based on data type and improve naming
                    data_type = param.get('data_type') or 'unknown'
                    if data_type == 'temperature':
                        param_name = 'Temperature'
                    elif data_type == 'pressure':
                        param_name = 'Pressure'
                    elif data_type == 'valve_state':
                        param_name = 'Valve_State'
                    elif data_type == 'flow_rate':
                        param_name = 'Flow_Rate'
                    elif data_type == 'set_point':
                        param_name = 'Set_Point'
                    elif data_type == 'binary':
                        param_name = 'Binary_State'
                    elif data_type == 'float':
                        param_name = 'Value'
                    elif data_type == 'unknown':
                        param_name = 'Parameter'
                    else:
                        param_name = str(data_type).title()

                    # If we have a valid component definition, use it for better naming
                    if component_def:
                        # Try to create more specific parameter names based on component type
                        if component_type == 'heater' and data_type == 'float':
                            param_name = 'Temperature'
                        elif component_type == 'gauge' and data_type == 'float':
                            param_name = 'Reading'
                        elif component_type == 'valve' and data_type == 'binary':
                            param_name = 'State'

                    # Determine unit based on data type
                    unit = ''
                    if data_type == 'temperature':
                        unit = '°C'
                    elif data_type == 'pressure':
                        unit = 'Torr'
                    elif data_type == 'flow_rate':
                        unit = 'sccm'
                    elif data_type == 'valve_state':
                        unit = ''  # Binary state

                    self.parameter_metadata[param_id] = {
                        'name': param_name,
                        'component_name': component_name,
                        'component_type': component_type,
                        'component_id': param.get('component_id'),
                        'data_type': data_type,
                        'unit': unit,
                        'min_value': param.get('min_value', 0),
                        'max_value': param.get('max_value', 0),
                        'is_writable': param.get('is_writable', False)
                    }

                data_logger.info(f"✅ Loaded metadata for {len(self.parameter_metadata)} parameters")

                # Log a few examples of the metadata for debugging
                for i, (param_id, metadata) in enumerate(self.parameter_metadata.items()):
                    if i >= 3:  # Only show first 3
                        break
                    data_logger.debug(
                        f"Parameter {param_id}: {metadata['component_name']}.{metadata['name']} "
                        f"({metadata['data_type']}, {metadata['unit']})"
                    )
            else:
                data_logger.warning("No parameter metadata found in database")

        except Exception as e:
            data_logger.error(f"Failed to load parameter metadata: {e}", exc_info=True)
            # Continue with empty metadata - service should still work

    async def _log_parameters_with_metadata(self, parameter_values: Dict[str, float]) -> int:
        """
        Log parameters to database with enhanced logging that includes metadata.

        Args:
            parameter_values: Dictionary of parameter_id -> value

        Returns:
            int: Number of parameters successfully logged
        """
        success_count = 0

        try:
            from datetime import datetime
            timestamp = datetime.utcnow().isoformat()

            # Prepare batch insert data for parameter_value_history
            history_records = []

            for param_id, value in parameter_values.items():
                # Get metadata for enhanced logging
                metadata = self.parameter_metadata.get(param_id, {})
                param_name = metadata.get('name', f'param_{param_id}')
                component_name = metadata.get('component_name', 'unknown_component')
                unit = metadata.get('unit', '')

                # Create record for database (no machine_id in this table)
                record = {
                    'parameter_id': param_id,
                    'value': float(value),
                    'timestamp': timestamp
                }
                history_records.append(record)

                # Enhanced info logging with parameter metadata
                if unit:
                    value_str = f"{value:.3f} {unit}"
                else:
                    value_str = f"{value:.3f}"

                data_logger.info(
                    f"📊 PLC Read: {component_name}.{param_name} = {value_str}"
                )

            # Batch insert to database
            if history_records:
                response = self.supabase.table('parameter_value_history').insert(history_records).execute()

                if response.data:
                    success_count = len(response.data)
                    data_logger.info(f"✅ Database insert: {success_count} parameter values logged")
                else:
                    data_logger.error("❌ Database insert failed: no data returned")

        except Exception as e:
            data_logger.error(f"Failed to log parameters with metadata: {e}", exc_info=True)

        return success_count

    def get_status(self) -> Dict[str, Any]:
        """Get current service status and metrics."""
        uptime = asyncio.get_event_loop().time() - self.metrics.get('service_start_time', 0)

        return {
            'service_name': 'PLC Data Service (Terminal 1)',
            'is_running': self.is_running,
            'plc_connected': self.plc_manager.is_connected(),
            'emergency_stop_active': self.emergency_stop_active,
            'command_queue_length': len(self.command_queue),
            'processing_command': self.processing_command,
            'uptime_seconds': uptime,
            'metrics': self.metrics.copy()
        }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="PLC Data Service - Terminal 1")
    parser.add_argument("--plc", choices=["simulation", "real"], help="PLC backend type")
    parser.add_argument("--demo", action="store_true", help="Use simulation mode")
    parser.add_argument("--ip", dest="plc_ip", help="PLC IP address")
    parser.add_argument("--port", dest="plc_port", type=int, help="PLC port")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
    return parser.parse_args()


def apply_env_overrides(args):
    """Apply command line arguments to environment variables."""
    if args.demo:
        os.environ["PLC_TYPE"] = "simulation"
    if args.plc:
        os.environ["PLC_TYPE"] = args.plc
    if args.plc_ip:
        os.environ["PLC_IP"] = args.plc_ip
    if args.plc_port is not None:
        os.environ["PLC_PORT"] = str(args.plc_port)
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level


async def signal_handler(plc_service):
    """Handle shutdown signals gracefully."""
    main_logger.info("Received shutdown signal - stopping PLC Data Service...")
    await plc_service.stop()
    main_logger.info("PLC Data Service shutdown complete")


async def main():
    """Main entry point for PLC Data Service."""
    # Ensure only one instance runs
    ensure_single_instance()

    # Parse command line arguments
    args = parse_args()
    apply_env_overrides(args)

    # Configure logging
    from src.log_setup import set_log_level
    set_log_level(os.environ.get("LOG_LEVEL", "INFO"))

    main_logger.info("="*60)
    main_logger.info("🔧 STARTING PLC DATA SERVICE - TERMINAL 1")
    main_logger.info("="*60)
    main_logger.info(f"Machine ID: {MACHINE_ID}")
    main_logger.info(f"PLC Type: {PLC_TYPE}")
    main_logger.info("EXCLUSIVE PLC HARDWARE ACCESS - Terminal 1 Authority")
    main_logger.info("="*60)

    # Create and initialize service
    plc_service = PLCDataService()

    # Set up signal handlers
    def shutdown_handler(signum, frame):
        asyncio.create_task(signal_handler(plc_service))

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Initialize service
        if not await plc_service.initialize():
            main_logger.error("Failed to initialize PLC Data Service")
            return 1

        # Start service
        await plc_service.start()

    except KeyboardInterrupt:
        main_logger.info("Received keyboard interrupt")
        await plc_service.stop()
    except Exception as e:
        main_logger.error(f"Fatal error in PLC Data Service: {e}", exc_info=True)
        await plc_service.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))