"""
Hardware Simulator for 3-Terminal Safety Testing

Simulates PLC hardware, valve operations, and parameter control
for safe testing without real hardware interaction.
"""

import asyncio
import pytest
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ValveState:
    """Valve state information."""
    valve_id: int
    is_open: bool
    controlled_by: Optional[str]
    operation_id: Optional[str]
    last_changed: datetime


@dataclass
class ParameterState:
    """Parameter state information."""
    parameter_id: str
    value: float
    last_updated: datetime
    updated_by: Optional[str]
    locked: bool


class HardwareSimulator:
    """Simulates ALD hardware for safety testing."""

    def __init__(self):
        self.valve_states = {}
        self.parameter_states = {}
        self.active_operations = {}
        self.plc_state = "IDLE"  # IDLE, ACTIVE, EMERGENCY, SAFE_SHUTDOWN
        self.emergency_active = False
        self.connection_status = "CONNECTED"

        # Initialize hardware state
        self._initialize_hardware()

    def _initialize_hardware(self):
        """Initialize hardware to safe default state."""
        # Initialize 8 valves, all closed
        for valve_id in range(1, 9):
            self.valve_states[valve_id] = ValveState(
                valve_id=valve_id,
                is_open=False,
                controlled_by=None,
                operation_id=None,
                last_changed=datetime.utcnow()
            )

        # Initialize critical parameters
        parameters = {
            "temperature_1": 25.0,
            "temperature_2": 25.0,
            "pressure_1": 1.0,
            "pressure_2": 1.0,
            "temperature_setpoint": 150.0,
            "pressure_setpoint": 2.0,
            "flow_rate_1": 0.0,
            "flow_rate_2": 0.0
        }

        for param_id, value in parameters.items():
            self.parameter_states[param_id] = ParameterState(
                parameter_id=param_id,
                value=value,
                last_updated=datetime.utcnow(),
                updated_by=None,
                locked=False
            )

    async def get_valve_state(self, valve_id: int) -> Dict[str, Any]:
        """Get current valve state."""
        if valve_id not in self.valve_states:
            raise ValueError(f"Valve {valve_id} not found")

        valve = self.valve_states[valve_id]
        return {
            'valve_id': valve_id,
            'is_open': valve.is_open,
            'controlled_by': valve.controlled_by,
            'operation_id': valve.operation_id,
            'last_changed': valve.last_changed.isoformat()
        }

    async def get_all_valve_states(self) -> Dict[int, Dict[str, Any]]:
        """Get all valve states."""
        result = {}
        for valve_id in self.valve_states:
            result[valve_id] = await self.get_valve_state(valve_id)
        return result

    async def control_valve(
        self,
        valve_id: int,
        is_open: bool,
        controlled_by: str,
        operation_id: str,
        duration_ms: Optional[int] = None
    ) -> bool:
        """Control valve state."""
        if self.emergency_active:
            raise RuntimeError("Cannot control valves during emergency")

        if valve_id not in self.valve_states:
            raise ValueError(f"Valve {valve_id} not found")

        # Check if valve is already controlled by someone else
        current_valve = self.valve_states[valve_id]
        if (current_valve.controlled_by is not None and
            current_valve.controlled_by != controlled_by and
            current_valve.operation_id != operation_id):
            raise RuntimeError(f"Valve {valve_id} is controlled by {current_valve.controlled_by}")

        # Update valve state
        self.valve_states[valve_id] = ValveState(
            valve_id=valve_id,
            is_open=is_open,
            controlled_by=controlled_by,
            operation_id=operation_id,
            last_changed=datetime.utcnow()
        )

        # Record operation
        operation = {
            'operation_id': operation_id,
            'valve_id': valve_id,
            'state': is_open,
            'controlled_by': controlled_by,
            'start_time': time.time(),
            'duration_ms': duration_ms
        }

        self.active_operations[operation_id] = operation

        # Handle timed operations
        if duration_ms and is_open:
            async def close_after_duration():
                await asyncio.sleep(duration_ms / 1000.0)
                self.valve_states[valve_id] = ValveState(
                    valve_id=valve_id,
                    is_open=False,
                    controlled_by=None,
                    operation_id=None,
                    last_changed=datetime.utcnow()
                )
                if operation_id in self.active_operations:
                    del self.active_operations[operation_id]

            asyncio.create_task(close_after_duration())

        return True

    async def get_active_valve_operations(self) -> List[Dict[str, Any]]:
        """Get list of active valve operations."""
        active_ops = []

        for valve_id, valve_state in self.valve_states.items():
            if valve_state.controlled_by is not None:
                active_ops.append({
                    'valve_id': valve_id,
                    'operation_id': valve_state.operation_id,
                    'terminal_id': valve_state.controlled_by,
                    'state': 'open' if valve_state.is_open else 'closed',
                    'last_changed': valve_state.last_changed.isoformat()
                })

        return active_ops

    async def read_parameter(self, parameter_id: str) -> float:
        """Read parameter value."""
        if parameter_id not in self.parameter_states:
            raise ValueError(f"Parameter {parameter_id} not found")

        # Simulate some variation for realistic behavior
        base_value = self.parameter_states[parameter_id].value

        # Add small random variation for temperature sensors
        if "temperature" in parameter_id and not "setpoint" in parameter_id:
            import random
            variation = random.uniform(-0.5, 0.5)
            return base_value + variation

        return base_value

    async def write_parameter(
        self,
        parameter_id: str,
        value: float,
        updated_by: str
    ) -> bool:
        """Write parameter value."""
        if self.emergency_active:
            raise RuntimeError("Cannot write parameters during emergency")

        if parameter_id not in self.parameter_states:
            raise ValueError(f"Parameter {parameter_id} not found")

        current_param = self.parameter_states[parameter_id]
        if current_param.locked:
            raise RuntimeError(f"Parameter {parameter_id} is locked")

        # Update parameter
        self.parameter_states[parameter_id] = ParameterState(
            parameter_id=parameter_id,
            value=value,
            last_updated=datetime.utcnow(),
            updated_by=updated_by,
            locked=False
        )

        return True

    async def get_parameter_state(self, parameter_id: str) -> Dict[str, Any]:
        """Get parameter state information."""
        if parameter_id not in self.parameter_states:
            raise ValueError(f"Parameter {parameter_id} not found")

        param = self.parameter_states[parameter_id]
        return {
            'parameter_id': parameter_id,
            'value': param.value,
            'last_updated': param.last_updated.isoformat(),
            'updated_by': param.updated_by,
            'locked': param.locked
        }

    async def trigger_emergency_shutdown(self, reason: str) -> Dict[str, Any]:
        """Trigger emergency shutdown of hardware."""
        self.emergency_active = True
        self.plc_state = "EMERGENCY"

        # Close all valves immediately
        emergency_time = datetime.utcnow()
        for valve_id in self.valve_states:
            self.valve_states[valve_id] = ValveState(
                valve_id=valve_id,
                is_open=False,
                controlled_by="EMERGENCY_SYSTEM",
                operation_id="EMERGENCY_SHUTDOWN",
                last_changed=emergency_time
            )

        # Clear active operations
        self.active_operations.clear()

        return {
            'status': 'EMERGENCY_SHUTDOWN_COMPLETE',
            'reason': reason,
            'timestamp': emergency_time.isoformat(),
            'valves_closed': len(self.valve_states)
        }

    async def reset_emergency_state(self) -> Dict[str, Any]:
        """Reset emergency state for testing."""
        self.emergency_active = False
        self.plc_state = "IDLE"

        # Reset all valves to normal closed state
        reset_time = datetime.utcnow()
        for valve_id in self.valve_states:
            self.valve_states[valve_id] = ValveState(
                valve_id=valve_id,
                is_open=False,
                controlled_by=None,
                operation_id=None,
                last_changed=reset_time
            )

        return {
            'status': 'EMERGENCY_RESET_COMPLETE',
            'timestamp': reset_time.isoformat()
        }

    async def get_plc_state(self) -> Dict[str, Any]:
        """Get current PLC state."""
        return {
            'state': self.plc_state,
            'emergency_active': self.emergency_active,
            'connection_status': self.connection_status,
            'active_operations': len(self.active_operations),
            'timestamp': datetime.utcnow().isoformat()
        }

    async def is_in_safe_state(self) -> bool:
        """Check if hardware is in safe state."""
        # All valves must be closed
        for valve_state in self.valve_states.values():
            if valve_state.is_open:
                return False

        # No active operations during emergency
        if self.emergency_active and len(self.active_operations) > 0:
            return False

        return True

    async def simulate_hardware_failure(self, failure_type: str) -> Dict[str, Any]:
        """Simulate hardware failure for testing."""
        if failure_type == "plc_disconnect":
            self.connection_status = "DISCONNECTED"
            self.plc_state = "COMMUNICATION_LOST"

        elif failure_type == "valve_stuck":
            # Simulate valve 1 stuck open
            self.valve_states[1] = ValveState(
                valve_id=1,
                is_open=True,
                controlled_by="HARDWARE_FAULT",
                operation_id="VALVE_STUCK",
                last_changed=datetime.utcnow()
            )

        elif failure_type == "sensor_failure":
            # Simulate temperature sensor failure
            self.parameter_states["temperature_1"] = ParameterState(
                parameter_id="temperature_1",
                value=float('nan'),  # Invalid reading
                last_updated=datetime.utcnow(),
                updated_by="SENSOR_FAULT",
                locked=True
            )

        return {
            'failure_type': failure_type,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'FAILURE_INJECTED'
        }

    async def restore_hardware_state(self) -> Dict[str, Any]:
        """Restore hardware to normal state after failure simulation."""
        self.connection_status = "CONNECTED"
        self.plc_state = "IDLE"

        # Reset all states to normal
        self._initialize_hardware()

        return {
            'status': 'HARDWARE_RESTORED',
            'timestamp': datetime.utcnow().isoformat()
        }


class PLCAccessMonitor:
    """Monitor PLC access for exclusive Terminal 1 validation."""

    def __init__(self):
        self.active_connections = []
        self.unauthorized_attempts = []

    async def register_plc_connection(self, terminal_id: str) -> Dict[str, Any]:
        """Register PLC connection."""
        connection = {
            'terminal_id': terminal_id,
            'connection_time': datetime.utcnow(),
            'status': 'ACTIVE'
        }

        self.active_connections.append(connection)

        return connection

    async def get_active_plc_connections(self) -> List[Dict[str, Any]]:
        """Get list of active PLC connections."""
        return [
            {
                'terminal_id': conn['terminal_id'],
                'connection_time': conn['connection_time'].isoformat(),
                'status': conn['status']
            }
            for conn in self.active_connections
        ]

    async def log_unauthorized_access_attempt(
        self,
        terminal_id: str,
        operation: str
    ) -> Dict[str, Any]:
        """Log unauthorized PLC access attempt."""
        attempt = {
            'terminal_id': terminal_id,
            'operation': operation,
            'timestamp': datetime.utcnow(),
            'blocked': True
        }

        self.unauthorized_attempts.append(attempt)

        return attempt

    async def get_unauthorized_access_attempts(self) -> List[Dict[str, Any]]:
        """Get list of unauthorized access attempts."""
        return [
            {
                'terminal_id': attempt['terminal_id'],
                'operation': attempt['operation'],
                'timestamp': attempt['timestamp'].isoformat(),
                'blocked': attempt['blocked']
            }
            for attempt in self.unauthorized_attempts
        ]


class CommandQueueMonitor:
    """Monitor PLC command queue processing."""

    def __init__(self):
        self.queued_commands = []
        self.processing_order = []

    async def add_command(self, command: Dict[str, Any]) -> str:
        """Add command to queue."""
        command_id = str(uuid.uuid4())
        command['command_id'] = command_id
        command['queue_time'] = datetime.utcnow()
        command['status'] = 'QUEUED'

        self.queued_commands.append(command)

        return command_id

    async def process_command(self, command_id: str, processed_by: str) -> Dict[str, Any]:
        """Mark command as processed."""
        for command in self.queued_commands:
            if command['command_id'] == command_id:
                command['status'] = 'COMPLETED'
                command['processed_by'] = processed_by
                command['process_time'] = datetime.utcnow()

                self.processing_order.append(command.copy())

                return command

        raise ValueError(f"Command {command_id} not found")

    async def wait_for_processing_completion(
        self,
        commands: List[Dict[str, Any]],
        timeout: float = 10.0
    ) -> List[Dict[str, Any]]:
        """Wait for all commands to be processed and return processing order."""
        command_ids = [cmd['command_id'] for cmd in commands]

        start_time = time.time()
        while time.time() - start_time < timeout:
            completed_commands = [
                cmd for cmd in self.processing_order
                if cmd['command_id'] in command_ids
            ]

            if len(completed_commands) == len(command_ids):
                # Sort by processing order
                return sorted(completed_commands, key=lambda x: x['process_time'])

            await asyncio.sleep(0.1)

        raise TimeoutError("Commands did not complete within timeout")


class HealthMonitor:
    """Monitor terminal health status."""

    def __init__(self):
        self.terminal_health = {}

    async def update_terminal_health(
        self,
        terminal_id: str,
        status: str,
        last_heartbeat: datetime
    ):
        """Update terminal health status."""
        self.terminal_health[terminal_id] = {
            'status': status,
            'last_heartbeat': last_heartbeat,
            'updated_at': datetime.utcnow()
        }

    async def get_cluster_health(self) -> Dict[str, Any]:
        """Get overall cluster health status."""
        cluster_status = "FULLY_OPERATIONAL"

        # Check if all terminals are healthy
        expected_terminals = ['terminal_1', 'terminal_2', 'terminal_3']
        healthy_terminals = 0

        for terminal_id in expected_terminals:
            if terminal_id in self.terminal_health:
                terminal_health = self.terminal_health[terminal_id]
                if terminal_health['status'] == 'HEALTHY':
                    healthy_terminals += 1

        if healthy_terminals == 0:
            cluster_status = "CLUSTER_DOWN"
        elif healthy_terminals < len(expected_terminals):
            cluster_status = "DEGRADED_OPERATION"

        result = {
            'cluster_status': cluster_status,
            'healthy_terminals': healthy_terminals,
            'total_terminals': len(expected_terminals)
        }

        # Add individual terminal status
        for terminal_id in expected_terminals:
            if terminal_id in self.terminal_health:
                result[terminal_id] = self.terminal_health[terminal_id].copy()
                result[terminal_id]['last_heartbeat'] = result[terminal_id]['last_heartbeat'].isoformat()
                result[terminal_id]['updated_at'] = result[terminal_id]['updated_at'].isoformat()
            else:
                result[terminal_id] = {
                    'status': 'UNKNOWN',
                    'last_heartbeat': None,
                    'updated_at': None
                }

        return result


@pytest.fixture
def hardware_simulator():
    """Provide hardware simulator for testing."""
    return HardwareSimulator()


@pytest.fixture
def plc_access_monitor():
    """Provide PLC access monitor."""
    return PLCAccessMonitor()


@pytest.fixture
def command_queue_monitor():
    """Provide command queue monitor."""
    return CommandQueueMonitor()


@pytest.fixture
def health_monitor():
    """Provide health monitor."""
    return HealthMonitor()