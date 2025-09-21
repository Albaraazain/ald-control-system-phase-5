# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Lint/Test Commands

- **Setup Environment**: `python -m venv myenv && source myenv/bin/activate && pip install -r requirements.txt`
- **Run Application**: `python main.py`
- **Run Debug Tests**: `python debug/test_plc_connection.py` (test scripts for PLC operations, Supabase connection, valve control, etc.)
- **Lint Code**: `python -m pylint --disable=C0103,C0111 --max-line-length=100 *.py`
- **Type Check**: `python -m mypy --ignore-missing-imports .`

## Architecture Overview

This is an Atomic Layer Deposition (ALD) control system that manages hardware operations through a multi-layer architecture:

### Core Components

1. **Command Flow** (`command_flow/`)
   - Listens for commands from Supabase database
   - Processes commands (start_recipe, stop_recipe, set_parameter)
   - Maintains command state and status updates

2. **Recipe Flow** (`recipe_flow/`)
   - Executes ALD recipes with multiple steps
   - Manages process lifecycle (starter, executor, stopper)
   - Records process data points continuously during execution

3. **Step Flow** (`step_flow/`)
   - Implements individual recipe steps (valve, purge, parameter, loop)
   - Handles step execution with timing and parameter control

4. **PLC Communication** (`plc/`)
   - Abstract interface for PLC operations
   - Real PLC implementation using Modbus TCP/IP with robust error handling
   - Simulation mode for testing without hardware
   - Manager pattern for centralized PLC access
   - Automatic reconnection and retry logic for broken pipe errors

5. **Data Collection** (`data_collection/`)
   - Continuous parameter logging service with dual-mode operation
   - Reads all parameters with read_modbus_address every second
   - Idle mode: logs to parameter_value_history table
   - Process mode: logs to both parameter_value_history AND process_data_points tables

### Data Flow

1. **Command Processing**: Supabase → Command Listener → Command Processor → Recipe/Step Execution
2. **Hardware Control**: Recipe Steps → PLC Manager → PLC Interface → Modbus Communication → Physical Hardware
3. **Data Recording**:
   - Process Mode: PLC Values → Continuous Recorder → Process Data Points + Parameter Value History
   - Idle Mode: PLC Values → Continuous Parameter Logger → Parameter Value History

### Key Design Patterns

- **Abstract Factory**: PLC interface with real/simulation implementations
- **Manager Pattern**: Centralized PLC access through plc_manager singleton
- **Async/Await**: All I/O operations use asyncio for non-blocking execution
- **State Management**: Global state tracking for current command and process
- **Service Pattern**: Long-running asyncio services for continuous operations
- **Dual-Mode Logging**: Automatic switching between idle and process data logging modes

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
- **Logging**: Use the logger from log_setup.py, include context in log messages
- **Line Length**: Keep lines under 100 characters
- **Formatting**: 4 spaces for indentation, no tabs
- **Function Parameters**: Use keyword arguments for clarity when calling functions with multiple parameters