# Interface Adapters Layer Implementation for Clean Architecture
# Controllers, Presenters, and External Interface Management

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import logging

# Import application layer components
from application_layer import (
    Command, Query, CommandResult, QueryResult,
    StartRecipeCommand, StopRecipeCommand, SetParameterCommand,
    GetProcessStatusQuery, GetMachineStateQuery, GetCurrentParametersQuery,
    ICommandBus, IQueryBus
)

# Import domain interfaces
from domain_interfaces import (
    MachineState, MachineStatus, ProcessStatus, ParameterValue
)

# Controllers for External Interfaces
class CommandController:
    """Controller for handling external commands from Supabase realtime, CLI, etc."""

    def __init__(
        self,
        command_bus: ICommandBus,
        auth_service: 'IAuthenticationService',
        logger: logging.Logger,
        input_validator: 'IInputValidator'
    ):
        self._command_bus = command_bus
        self._auth_service = auth_service
        self._logger = logger
        self._input_validator = input_validator

    async def handle_supabase_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming commands from Supabase realtime"""

        try:
            # Validate input data
            validation_result = await self._input_validator.validate_command_data(command_data)
            if not validation_result.is_valid:
                return self._create_error_response(
                    "Invalid input data",
                    {"validation_errors": validation_result.errors}
                )

            # Authenticate operator
            operator = await self._auth_service.authenticate(command_data.get('operator_id'))
            if not operator:
                return self._create_error_response("Authentication failed")

            # Parse and execute command
            command = self._parse_command(command_data)
            result = await self._command_bus.execute(command)

            # Log command execution
            await self._log_command_execution(command, result, operator.id)

            # Return formatted response
            return self._format_command_response(result)

        except Exception as e:
            self._logger.error(f"Error handling command: {e}", exc_info=True)
            return self._create_error_response(f"Command execution failed: {str(e)}")

    def _parse_command(self, command_data: Dict[str, Any]) -> Command:
        """Parse command data into appropriate command object"""

        command_type = command_data.get('command_type')
        operator_id = command_data.get('operator_id')

        if command_type == 'start_recipe':
            return StartRecipeCommand(
                recipe_id=command_data['recipe_id'],
                machine_id=command_data['machine_id'],
                operator_id=operator_id,
                parameters_override=command_data.get('parameters_override', {})
            )
        elif command_type == 'stop_recipe':
            return StopRecipeCommand(
                process_id=command_data['process_id'],
                reason=command_data.get('reason', 'Manual stop'),
                operator_id=operator_id
            )
        elif command_type == 'set_parameter':
            return SetParameterCommand(
                parameter_id=command_data['parameter_id'],
                value=float(command_data['value']),
                operator_id=operator_id
            )
        else:
            raise ValueError(f"Unknown command type: {command_type}")

    def _format_command_response(self, result: CommandResult) -> Dict[str, Any]:
        """Format command result for external consumption"""

        response = {
            'success': result.is_success,
            'timestamp': datetime.utcnow().isoformat(),
            'data': result.data or {}
        }

        if not result.is_success:
            response['error'] = result.error_message

        return response

    def _create_error_response(self, error_message: str, additional_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Create standardized error response"""

        response = {
            'success': False,
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }

        if additional_data:
            response.update(additional_data)

        return response

    async def _log_command_execution(self, command: Command, result: CommandResult, operator_id: str):
        """Log command execution for audit trail"""

        log_data = {
            'command_type': type(command).__name__,
            'operator_id': operator_id,
            'success': result.is_success,
            'timestamp': datetime.utcnow().isoformat()
        }

        if result.is_success:
            self._logger.info(f"Command executed successfully: {log_data}")
        else:
            log_data['error'] = result.error_message
            self._logger.warning(f"Command execution failed: {log_data}")

class QueryController:
    """Controller for handling read queries from external interfaces"""

    def __init__(
        self,
        query_bus: IQueryBus,
        auth_service: 'IAuthenticationService',
        logger: logging.Logger
    ):
        self._query_bus = query_bus
        self._auth_service = auth_service
        self._logger = logger

    async def get_process_status(self, process_id: str, operator_id: str) -> Dict[str, Any]:
        """Get process status information"""

        try:
            # Authenticate operator
            operator = await self._auth_service.authenticate(operator_id)
            if not operator:
                return self._create_error_response("Authentication failed")

            # Execute query
            query = GetProcessStatusQuery(process_id=process_id)
            result = await self._query_bus.execute(query)

            if result.is_success:
                # Format process data for external consumption
                return {
                    'success': True,
                    'data': ProcessPresenter.present_process_status(result.data),
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return self._create_error_response(result.error_message)

        except Exception as e:
            self._logger.error(f"Error getting process status: {e}", exc_info=True)
            return self._create_error_response(f"Query failed: {str(e)}")

    async def get_machine_state(self, machine_id: str, operator_id: str) -> Dict[str, Any]:
        """Get current machine state"""

        try:
            # Authenticate operator
            operator = await self._auth_service.authenticate(operator_id)
            if not operator:
                return self._create_error_response("Authentication failed")

            # Execute query
            query = GetMachineStateQuery(machine_id=machine_id)
            result = await self._query_bus.execute(query)

            if result.is_success:
                return {
                    'success': True,
                    'data': MachineStatePresenter.present_machine_state(result.data),
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return self._create_error_response(result.error_message)

        except Exception as e:
            self._logger.error(f"Error getting machine state: {e}", exc_info=True)
            return self._create_error_response(f"Query failed: {str(e)}")

    async def get_current_parameters(self, machine_id: str, operator_id: str) -> Dict[str, Any]:
        """Get current parameter values"""

        try:
            # Authenticate operator
            operator = await self._auth_service.authenticate(operator_id)
            if not operator:
                return self._create_error_response("Authentication failed")

            # Execute query
            query = GetCurrentParametersQuery(machine_id=machine_id)
            result = await self._query_bus.execute(query)

            if result.is_success:
                return {
                    'success': True,
                    'data': ParameterPresenter.present_parameters(result.data),
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return self._create_error_response(result.error_message)

        except Exception as e:
            self._logger.error(f"Error getting parameters: {e}", exc_info=True)
            return self._create_error_response(f"Query failed: {str(e)}")

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response"""

        return {
            'success': False,
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }

# Presenters for Data Formatting
class ProcessPresenter:
    """Presenter for process data formatting"""

    @staticmethod
    def present_process_status(process: 'Process') -> Dict[str, Any]:
        """Present process status in external format"""

        return {
            'id': process.id,
            'recipe_id': process.recipe_id,
            'machine_id': process.machine_id,
            'status': process.status.value,
            'started_at': process.started_at.isoformat(),
            'completed_at': process.completed_at.isoformat() if process.completed_at else None,
            'progress_percentage': ProcessPresenter._calculate_progress(process),
            'current_step': ProcessPresenter._get_current_step_name(process),
            'estimated_completion': ProcessPresenter._estimate_completion(process),
            'data_points_count': len(process.data_points) if process.data_points else 0
        }

    @staticmethod
    def _calculate_progress(process: 'Process') -> float:
        """Calculate process progress percentage"""

        if process.status == ProcessStatus.COMPLETED:
            return 100.0
        elif process.status == ProcessStatus.PENDING:
            return 0.0
        elif process.status in [ProcessStatus.ABORTED, ProcessStatus.ERROR]:
            return 0.0
        else:
            # For running processes, calculate based on current step
            # This would require recipe step information
            return 50.0  # Placeholder

    @staticmethod
    def _get_current_step_name(process: 'Process') -> str:
        """Get current step name"""
        # This would require recipe step information
        return "Processing..."  # Placeholder

    @staticmethod
    def _estimate_completion(process: 'Process') -> Optional[str]:
        """Estimate completion time"""
        # This would require recipe duration information
        return None  # Placeholder

class MachineStatePresenter:
    """Presenter for machine state formatting"""

    @staticmethod
    def present_machine_state(state: MachineState) -> Dict[str, Any]:
        """Present machine state in external format"""

        return {
            'status': state.status.value,
            'current_process_id': state.current_process_id,
            'last_heartbeat': state.last_heartbeat.isoformat(),
            'error_message': state.error_message,
            'is_available': state.status == MachineStatus.IDLE,
            'is_processing': state.status == MachineStatus.PROCESSING,
            'health_status': MachineStatePresenter._get_health_status(state)
        }

    @staticmethod
    def _get_health_status(state: MachineState) -> str:
        """Determine overall health status"""

        if state.status == MachineStatus.OFFLINE:
            return "offline"
        elif state.status == MachineStatus.ERROR:
            return "error"
        else:
            # Check last heartbeat
            time_since_heartbeat = (datetime.utcnow() - state.last_heartbeat).total_seconds()
            if time_since_heartbeat > 300:  # 5 minutes
                return "degraded"
            else:
                return "healthy"

class ParameterPresenter:
    """Presenter for parameter data formatting"""

    @staticmethod
    def present_parameters(parameters: List['Parameter']) -> Dict[str, Any]:
        """Present parameters in external format"""

        return {
            'parameters': [
                ParameterPresenter.present_parameter(param)
                for param in parameters
            ],
            'total_count': len(parameters),
            'active_count': len([p for p in parameters if hasattr(p, 'active') and p.active])
        }

    @staticmethod
    def present_parameter(parameter: 'Parameter') -> Dict[str, Any]:
        """Present single parameter in external format"""

        return {
            'id': parameter.id,
            'name': parameter.name,
            'modbus_address': parameter.modbus_address,
            'data_type': parameter.data_type.value,
            'constraints': {
                'min_value': parameter.constraints.min_value,
                'max_value': parameter.constraints.max_value,
                'data_type': parameter.constraints.data_type.value
            },
            'read_frequency': parameter.read_frequency
        }

    @staticmethod
    def present_parameter_values(parameter_values: List[ParameterValue]) -> Dict[str, Any]:
        """Present parameter values in external format"""

        return {
            'values': [
                {
                    'parameter_id': pv.parameter_id,
                    'value': pv.value,
                    'timestamp': pv.timestamp.isoformat(),
                    'quality': pv.quality.value,
                    'source': pv.source
                }
                for pv in parameter_values
            ],
            'timestamp': datetime.utcnow().isoformat(),
            'total_count': len(parameter_values)
        }

# Response Models
@dataclass
class CommandResponse:
    """Response model for command operations"""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@dataclass
class ProcessStatusResponse:
    """Response model for process status"""
    id: str
    recipe_id: str
    machine_id: str
    status: str
    started_at: str
    completed_at: Optional[str]
    progress_percentage: float
    current_step: str
    estimated_completion: Optional[str]
    data_points_count: int

@dataclass
class MachineStateResponse:
    """Response model for machine state"""
    status: str
    current_process_id: Optional[str]
    last_heartbeat: str
    error_message: Optional[str]
    is_available: bool
    is_processing: bool
    health_status: str

@dataclass
class ParameterResponse:
    """Response model for parameters"""
    id: str
    name: str
    modbus_address: int
    data_type: str
    constraints: Dict[str, Any]
    read_frequency: Optional[int]

# External Interface Adapters
class SupabaseRealtimeAdapter:
    """Adapter for Supabase realtime command processing"""

    def __init__(
        self,
        command_controller: CommandController,
        query_controller: QueryController,
        logger: logging.Logger
    ):
        self._command_controller = command_controller
        self._query_controller = query_controller
        self._logger = logger

    async def handle_realtime_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle incoming Supabase realtime events"""

        try:
            if event_type == 'INSERT' and payload.get('table') == 'commands':
                # New command inserted
                command_data = payload['record']
                result = await self._command_controller.handle_supabase_command(command_data)

                # Update command status in database
                await self._update_command_status(command_data['id'], result)

            elif event_type == 'UPDATE' and payload.get('table') == 'commands':
                # Command updated - might be a retry or cancellation
                command_data = payload['record']
                if command_data.get('status') == 'pending':
                    result = await self._command_controller.handle_supabase_command(command_data)
                    await self._update_command_status(command_data['id'], result)

        except Exception as e:
            self._logger.error(f"Error handling realtime event: {e}", exc_info=True)

    async def _update_command_status(self, command_id: str, result: Dict[str, Any]) -> None:
        """Update command status in Supabase"""

        try:
            from src.db import get_supabase
            supabase = get_supabase()

            status = 'completed' if result['success'] else 'error'
            update_data = {
                'status': status,
                'result': result,
                'updated_at': datetime.utcnow().isoformat()
            }

            supabase.table('commands').update(update_data).eq('id', command_id).execute()

        except Exception as e:
            self._logger.error(f"Error updating command status: {e}", exc_info=True)

class WebAPIAdapter:
    """Adapter for REST API interface"""

    def __init__(
        self,
        command_controller: CommandController,
        query_controller: QueryController
    ):
        self._command_controller = command_controller
        self._query_controller = query_controller

    async def handle_command_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle REST API command requests"""

        return await self._command_controller.handle_supabase_command(request_data)

    async def handle_query_request(self, query_type: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle REST API query requests"""

        operator_id = query_params.get('operator_id')

        if query_type == 'process_status':
            return await self._query_controller.get_process_status(
                query_params['process_id'], operator_id
            )
        elif query_type == 'machine_state':
            return await self._query_controller.get_machine_state(
                query_params['machine_id'], operator_id
            )
        elif query_type == 'current_parameters':
            return await self._query_controller.get_current_parameters(
                query_params['machine_id'], operator_id
            )
        else:
            return {
                'success': False,
                'error': f'Unknown query type: {query_type}',
                'timestamp': datetime.utcnow().isoformat()
            }

# Authentication and Authorization Service Interface
class IAuthenticationService(ABC):
    """Interface for authentication service"""

    @abstractmethod
    async def authenticate(self, operator_id: str) -> Optional['Operator']:
        """Authenticate operator and return operator object"""
        pass

    @abstractmethod
    async def authorize(self, operator: 'Operator', operation: str) -> bool:
        """Authorize operator for specific operation"""
        pass

class IInputValidator(ABC):
    """Interface for input validation service"""

    @abstractmethod
    async def validate_command_data(self, command_data: Dict[str, Any]) -> 'ValidationResult':
        """Validate command input data"""
        pass

    @abstractmethod
    async def validate_query_params(self, query_params: Dict[str, Any]) -> 'ValidationResult':
        """Validate query parameters"""
        pass

# Operator Model
@dataclass
class Operator:
    """Operator domain model"""
    id: str
    name: str
    role: str
    permissions: List[str]

# Configuration for Interface Adapters
class InterfaceAdapterConfig:
    """Configuration for interface adapters"""

    def __init__(self):
        self.supabase_table_commands = "commands"
        self.supabase_table_processes = "process_executions"
        self.supabase_table_machines = "machines"
        self.authentication_required = True
        self.input_validation_enabled = True
        self.audit_logging_enabled = True

# Factory for creating interface adapters
class InterfaceAdapterFactory:
    """Factory for creating interface adapters with dependencies"""

    @staticmethod
    def create_command_controller(
        command_bus: ICommandBus,
        auth_service: IAuthenticationService,
        logger: logging.Logger,
        input_validator: IInputValidator
    ) -> CommandController:
        """Create command controller with dependencies"""

        return CommandController(command_bus, auth_service, logger, input_validator)

    @staticmethod
    def create_query_controller(
        query_bus: IQueryBus,
        auth_service: IAuthenticationService,
        logger: logging.Logger
    ) -> QueryController:
        """Create query controller with dependencies"""

        return QueryController(query_bus, auth_service, logger)

    @staticmethod
    def create_supabase_adapter(
        command_controller: CommandController,
        query_controller: QueryController,
        logger: logging.Logger
    ) -> SupabaseRealtimeAdapter:
        """Create Supabase realtime adapter"""

        return SupabaseRealtimeAdapter(command_controller, query_controller, logger)

    @staticmethod
    def create_web_api_adapter(
        command_controller: CommandController,
        query_controller: QueryController
    ) -> WebAPIAdapter:
        """Create Web API adapter"""

        return WebAPIAdapter(command_controller, query_controller)

# This interface adapters layer provides:
# 1. Controllers for external command and query handling
# 2. Presenters for data formatting and response models
# 3. Adapters for external interfaces (Supabase, REST API)
# 4. Authentication and authorization interfaces
# 5. Input validation and security integration
# 6. Comprehensive error handling and logging
# 7. Factory pattern for dependency injection integration