# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Lint/Test Commands

- **Setup Environment**: `python -m venv myenv && source myenv/bin/activate && pip install -r requirements.txt`
- **Run Terminal 1**: `python main.py --terminal 1 --demo` (PLC Read Service)
- **Run Terminal 2**: `python main.py --terminal 2 --demo` (Recipe Service)
- **Run Terminal 3**: `python main.py --terminal 3 --demo` (Parameter Service)
- **Run All Terminals**: Open 3 separate terminal windows and run each service independently
- **Run Debug Tests**: `python debug/test_plc_connection.py` (test scripts for PLC operations, Supabase connection, valve control, etc.)
- **Lint Code**: `python -m pylint --disable=C0103,C0111 --max-line-length=100 *.py`
- **Type Check**: `python -m mypy --ignore-missing-imports .`
- **View Service Logs**: `tail -f logs/command_flow.log` (replace with specific service: plc, recipe_flow, data_collection, etc.)
- **Monitor All Errors**: `tail -f logs/*.log | grep ERROR`
- **Debug Specific Service**: `export LOG_LEVEL_PLC=DEBUG && python main.py` (replace PLC with any service)

## Architecture Overview - SIMPLE 3-TERMINAL DESIGN

This is an Atomic Layer Deposition (ALD) control system with a **SIMPLE 3-TERMINAL ARCHITECTURE** that eliminates coordination complexity and provides direct PLC access for easy debugging.

### 🔧 TERMINAL 1: PLC Read Service (`plc_data_service.py`)
- **Purpose**: Continuous PLC data collection
- **Function**: Reads PLC parameters every 1 second and updates database
- **Database**: Updates `parameter_value_history` table
- **Launch**: `python main.py --terminal 1 --demo` or `python terminal1_launcher.py --demo`
- **Features**: Direct PLC access, simple database inserts, error handling with retry logic

### 🍳 TERMINAL 2: Recipe Service (`simple_recipe_service.py`)
- **Purpose**: Recipe command processing and execution
- **Function**: Listens for recipe commands and executes them via direct PLC access
- **Database**: Monitors `recipe_commands` table, updates `process_executions`
- **Launch**: `python main.py --terminal 2 --demo` or `python terminal2_launcher.py --demo`
- **Features**: Direct PLC access, simple polling, reuses existing recipe_flow components

### ⚙️ TERMINAL 3: Parameter Service (`parameter_service.py`)
- **Purpose**: Parameter control and writing
- **Function**: Listens for parameter commands and writes directly to PLC
- **Database**: Monitors `parameter_control_commands` table
- **Launch**: `python main.py --terminal 3 --demo` or `python terminal3_launcher.py --demo`
- **Features**: Direct PLC access, parameter validation, retry logic

### Key Architecture Benefits

✅ **No Coordination Complexity**: Each terminal operates independently
✅ **Direct PLC Access**: No singleton conflicts, each terminal has its own connection
✅ **Easy Debugging**: Simple to understand, no complex agent coordination
✅ **Independent Operation**: Terminals can run separately without dependencies
✅ **Simplified Deployment**: Just run the terminal you need

### Simple Data Flow

1. **Terminal 1 (PLC Read)**: PLC → Direct Read → Database (parameter_value_history)
2. **Terminal 2 (Recipe)**: Database (recipe_commands) → Direct PLC Execution → Process Updates
3. **Terminal 3 (Parameter)**: Database (parameter_control_commands) → Direct PLC Write

### Key Design Principles

- **Direct PLC Access**: Each terminal has its own PLC connection (no singletons)
- **Simple Polling**: No complex coordination or agent systems
- **Independent Services**: Terminals operate completely independently
- **Easy Debugging**: Each service is self-contained and simple to understand
- **Async/Await**: Non-blocking I/O operations for responsiveness

## Code Style Guidelines

- **Imports**: Group in order: standard library, third-party, local application imports with a blank line between groups
- **Docstrings**: Use triple-quoted docstrings for modules, classes, and functions
- **Types**: Use type hints for function parameters and return values
- **Naming**:
  - Classes: CamelCase
  - Functions/Variables: snake_case
  - Constants: UPPERCASE
- **Error Handling**: Use try/except blocks with specific exceptions, log errors with context
- **Async Pattern**: Use async/await for asynchronous operations, particularly for I/O operations
- **Logging**: Use service-specific loggers from log_setup.py (see Enhanced Logging section), include context in log messages
- **Line Length**: Keep lines under 100 characters
- **Formatting**: 4 spaces for indentation, no tabs
- **Function Parameters**: Use keyword arguments for clarity when calling functions with multiple parameters

## Recent Fixes (Operational Notes)

These changes ensure commands are processed and logged even when Supabase Realtime is slow or unavailable.

- Realtime subscribe made non-blocking with 10s watchdog timeout
  - Files: `src/parameter_control_listener.py`, `src/command_flow/listener.py`
  - What changed: `channel.subscribe()`/`realtime_channel.subscribe()` is wrapped in `asyncio.wait_for(..., timeout=10.0)` and executed in a background task. This prevents service startup from hanging if the realtime handshake stalls. On timeout or error, we immediately fall back to polling and update `connection_monitor` realtime status.
  - Expected logs: Listener readiness includes whether it’s using REALTIME + polling fallback or POLLING ONLY.

- Polling includes global commands
  - Files: `src/parameter_control_listener.py`, `src/command_flow/listener.py`
  - What changed: Pending queries no longer filter by `machine_id` at the SQL layer. Instead, we fetch pending items and filter in-process for commands where `machine_id ∈ {MACHINE_ID, NULL}`. This ensures “global” commands (NULL machine_id) are not ignored.

- Realtime reconnection guarded by timeout
  - File: `src/parameter_control_listener.py`
  - What changed: Reconnection attempts use `asyncio.wait_for(..., timeout=10.0)` with graceful fallback to polling and status reporting via `connection_monitor`.

How to verify after restart
- Startup logs should show listeners ready even if realtime is unavailable.
- Inserting parameter control or recipe commands should produce emoji logs (🔔, 🟡, 🟢, ✅) regardless of realtime status.

## Enhanced Service-Specific Logging

The system implements service-specific logging for improved debugging, monitoring, and maintenance. Each service writes to its own dedicated log file while maintaining backward compatibility.

### Log File Structure
```
logs/
├── command_flow.log         # Command processing and execution
├── recipe_flow.log          # Recipe execution and workflow
├── step_flow.log           # Individual step operations
├── plc.log                 # PLC communication and hardware
├── data_collection.log     # Parameter logging and data recording
├── security.log            # Security operations and validation
├── performance.log         # Performance metrics and optimization
├── agents.log              # Agent management and coordination
├── realtime.log            # Realtime connections and subscriptions
├── connection_monitor.log  # System health and connectivity
└── machine_control.log     # Legacy/fallback logger (backward compatibility)
```

### Usage in New Code (Recommended)
```python
# Use service-specific loggers for better debugging
from src.log_setup import get_service_logger

# For command flow modules
logger = get_service_logger('command_flow')

# For PLC modules
logger = get_service_logger('plc')

# For data collection modules
logger = get_service_logger('data_collection')

# Convenience functions also available
from src.log_setup import get_command_flow_logger, get_plc_logger
logger = get_command_flow_logger()
```

### Legacy Code (Still Supported)
```python
# This still works and logs to machine_control.log
from src.log_setup import logger
logger.info("Legacy logging message")
```

### Log Level Configuration
```bash
# Set log level for all services
export LOG_LEVEL=DEBUG

# Set log level for specific service
export LOG_LEVEL_PLC=DEBUG
export LOG_LEVEL_COMMAND_FLOW=INFO

# Via command line
python main.py --log-level DEBUG
```

### Debugging Commands
```bash
# Monitor specific service errors
tail -f logs/plc.log | grep ERROR

# Monitor command processing
tail -f logs/command_flow.log

# Search across all logs
grep -r "recipe.*failed" logs/

# Monitor startup sequence
tail -f logs/machine_control.log logs/command_flow.log logs/plc.log
```

### Best Practices
1. **Choose the correct service logger** for your module's domain
2. **Include context** in log messages: `logger.info(f"Processing recipe_id={recipe_id}")`
3. **Use appropriate log levels**: DEBUG for diagnostics, INFO for operations, ERROR for failures
4. **Use exception info** for errors: `logger.error("Operation failed", exc_info=True)`
5. **Never log sensitive information** like passwords or API keys

### Documentation
- **Enhanced Logging Guide**: `docs/Enhanced_Logging_Guide.md` - Complete usage guide
- **Troubleshooting Guide**: `docs/Log_Troubleshooting_Guide.md` - Debug patterns and solutions