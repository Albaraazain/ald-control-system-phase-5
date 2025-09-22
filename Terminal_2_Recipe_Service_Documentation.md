# Terminal 2: Recipe Service Implementation Guide

## Overview

Terminal 2 (Recipe Service) is a standalone service responsible for recipe command processing and workflow execution in the 3-terminal ALD control system architecture. This service coordinates with Terminal 1 for all hardware operations via database communication.

## Architecture

### Core Components

1. **Recipe Service Entry Point** (`recipe_service.py`)
   - Main service orchestrator
   - Command line interface with validation options
   - Service lifecycle management

2. **Recipe Command Listener** (`src/recipe_service/listener.py`)
   - Monitors `recipe_commands` table for new commands
   - Realtime subscription with polling fallback
   - Command claiming and processing

3. **Recipe Executor** (`src/recipe_service/executor.py`)
   - Routes commands to appropriate handlers
   - Manages command lifecycle and status updates
   - Implements safety validations

4. **Database Coordinator** (`src/recipe_service/coordinator.py`)
   - Handles communication with Terminal 1
   - Hardware operation request/response management
   - Emergency coordination support

5. **Recipe Workflow Engine** (`src/recipe_service/workflow.py`)
   - Step-by-step recipe execution
   - Loop handling and timing coordination
   - Process state management

6. **Service Validator** (`src/recipe_service/validation.py`)
   - Startup validation of database connectivity
   - Configuration and table existence verification
   - Integration readiness checks

## Key Features

### Database Coordination Architecture

Terminal 2 NEVER directly accesses PLC hardware. All hardware operations are coordinated through the `hardware_operations` table:

```
Recipe Service → hardware_operations table → Terminal 1 → PLC Hardware
```

### Supported Commands

- `start_recipe`: Begin recipe execution
- `stop_recipe`: Graceful recipe termination
- `abort_recipe`: Emergency recipe stop
- `pause_recipe`: Pause recipe execution
- `resume_recipe`: Resume paused recipe

### Safety Mechanisms

1. **Machine Availability Validation**: Prevents concurrent recipe starts
2. **Race Condition Prevention**: Atomic command claiming
3. **Emergency Abort Coordination**: High-priority emergency operations
4. **Graceful Degradation**: Handles Terminal 1 communication failures

### Hardware Operation Types

1. **Valve Operations**:
   - `valve_number`, `duration_ms`
   - Timeout: 60 seconds

2. **Parameter Sets**:
   - `parameter_name`, `value`
   - Timeout: 30 seconds

3. **Emergency Abort**:
   - `reason`
   - Timeout: 10 seconds (high priority)

## Installation and Setup

### 1. Environment Setup

```bash
# Activate virtual environment
source myenv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Required environment variables:
- `MACHINE_ID`: Target machine identifier
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `SUPABASE_URL`: Database connection URL
- `SUPABASE_KEY`: Database access key

Optional environment variables:
- `RECIPE_COMMAND_POLL_INTERVAL`: Polling interval (default: 5s)
- `HARDWARE_OPERATION_TIMEOUT`: Default operation timeout (default: 60s)
- `EMERGENCY_OPERATION_TIMEOUT`: Emergency timeout (default: 10s)

### 3. Database Prerequisites

Required tables:
- `machines`: Machine configuration and status
- `machine_state`: Detailed machine state tracking
- `recipes`: Recipe definitions
- `recipe_steps`: Recipe step details
- `recipe_commands`: Command queue for Terminal 2
- `process_executions`: Recipe execution records
- `process_execution_state`: Detailed execution state
- `operator_sessions`: Operator session management
- `hardware_operations`: Terminal 1 coordination

## Usage

### Start Recipe Service

```bash
# Production mode with validation
python recipe_service.py

# Development mode (skip validation)
python recipe_service.py --skip-validation

# With specific log level
python recipe_service.py --log-level DEBUG

# Using launcher script
python launch_recipe_service.py
```

### Command Line Options

- `--log-level`: Set logging level (CRITICAL, ERROR, WARNING, INFO, DEBUG)
- `--machine-id`: Override machine ID
- `--skip-validation`: Skip startup validation (development mode)

## Integration with Terminal 1

### Hardware Operation Flow

1. **Recipe Step Execution**:
   ```
   Recipe Step → Database Coordinator → hardware_operations table
   ```

2. **Terminal 1 Processing**:
   ```
   Terminal 1 monitors hardware_operations → PLC execution → status update
   ```

3. **Completion Handling**:
   ```
   Recipe Service polls operation status → continues to next step
   ```

### Emergency Coordination

Emergency abort operations have special handling:
- **Priority**: Critical priority in operation queue
- **Timeout**: 10-second timeout for fast response
- **Propagation**: Emergency signal reaches Terminal 1 immediately

## Monitoring and Debugging

### Log Files

- Main service logs: `logs/recipe_flow.log`
- Command processing: Look for 🔔, 🟡, 🟢, ✅ emoji markers
- Error tracking: `tail -f logs/recipe_flow.log | grep ERROR`

### Health Checks

The service provides periodic health status:
```
[Health Check] Recipe Service running, Coordinator: True, Executor: True, Listener: True
```

### Validation

Startup validation checks:
- Database connectivity
- Required table existence
- Machine configuration
- Coordination table availability
- Recipe data integrity

## Safety Considerations

### Critical Safety Features

1. **No Direct Hardware Access**: Terminal 2 cannot directly control valves
2. **Coordination Timeout**: All operations have configurable timeouts
3. **Emergency Abort**: High-priority emergency stop mechanism
4. **Machine State Validation**: Prevents unsafe operations
5. **Atomic Command Processing**: Race condition prevention

### Error Handling

- **Database Failures**: Graceful degradation with logging
- **Terminal 1 Unavailable**: Operation timeouts with error reporting
- **Invalid Commands**: Validation and error responses
- **System Shutdown**: Graceful cleanup of active processes

## Development and Testing

### Development Mode

```bash
# Skip validation for faster development iteration
python recipe_service.py --skip-validation --log-level DEBUG
```

### Testing Integration

The service includes comprehensive validation that can be used for testing:

```python
from src.recipe_service.validation import RecipeServiceValidator

validator = RecipeServiceValidator()
results = await validator.validate_full_setup()
```

## Performance Specifications

- **Command Response**: < 100ms for command acknowledgment
- **Hardware Operation Coordination**: Variable based on Terminal 1 processing
- **Emergency Response**: < 500ms for emergency propagation
- **Database Polling**: 5-second intervals (configurable)

## Status and Next Steps

**Current Status**: ✅ Implementation Complete (95%)

**Ready for**:
- Integration testing with Terminal 1
- Database schema deployment
- Safety validation testing
- Production deployment

**Integration Requirements**:
- Terminal 1 must be running and processing `hardware_operations` table
- Database coordination schemas must be deployed
- Terminal discovery service integration (future enhancement)

---

*This documentation covers Terminal 2 Recipe Service implementation. For complete 3-terminal integration, see Terminal 1 PLC Data Service and Terminal 3 Parameter Service documentation.*