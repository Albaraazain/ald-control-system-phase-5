# Simple Recipe Service - Terminal 2

## Overview

The Simple Recipe Service (`simple_recipe_service.py`) is a standalone service that executes recipes directly via PLC without complex coordination layers.

## Key Features

### ✅ SIMPLIFIED ARCHITECTURE
- **Direct PLC Access**: Uses `plc_manager` directly, no coordination layer
- **Simple Polling**: Checks `recipe_commands` table every 2 seconds
- **Self-Contained**: No dependencies on other terminals or services
- **Reuses Existing Components**: Leverages proven `recipe_flow` and `step_flow` modules

### 🔄 RECIPE EXECUTION FLOW

1. **Command Detection**: Polls `recipe_commands` table for pending commands
2. **Recipe Initialization**: Creates `process_executions` and `process_execution_state` records
3. **Direct Execution**: Uses existing `execute_recipe()` function with direct PLC access
4. **Status Updates**: Updates machine state and process status in database
5. **Data Recording**: Starts/stops continuous data recording

### 📊 DATABASE INTEGRATION

**Tables Used:**
- `recipe_commands` - Command queue (polling for pending commands)
- `recipes` - Recipe definitions
- `recipe_steps` - Step configurations
- `process_executions` - Process tracking
- `process_execution_state` - Real-time process state
- `machines` - Machine status updates
- `machine_state` - Machine state tracking

**Command Types Supported:**
- `start_recipe` - Execute a recipe
- `stop_recipe` - Abort current recipe execution

### 🚀 USAGE

```bash
# Basic execution
python simple_recipe_service.py

# With debug logging
python simple_recipe_service.py --log-level DEBUG

# With custom machine ID
python simple_recipe_service.py --machine-id TEST_MACHINE

# Using launcher
python launch_simple_recipe_service.py
```

### 🧪 TESTING

To test the service, insert a recipe command:

```sql
INSERT INTO recipe_commands (type, machine_id, parameters, status)
VALUES (
    'start_recipe',
    'your-machine-id',
    '{"recipe_id": "your-recipe-id"}',
    'pending'
);
```

### 📈 MONITORING

Watch logs:
```bash
tail -f logs/recipe_flow.log
```

Check service status via database:
```sql
SELECT * FROM machines WHERE id = 'your-machine-id';
SELECT * FROM process_executions ORDER BY created_at DESC LIMIT 5;
```

## Differences from Complex Service

| Aspect | Complex Service | Simple Service |
|--------|----------------|----------------|
| **Architecture** | 3-tier (coordinator/executor/listener) | Single service class |
| **PLC Access** | Via coordination tables | Direct via `plc_manager` |
| **Command Detection** | Realtime + polling fallback | Simple polling only |
| **Dependencies** | Multiple service components | Self-contained |
| **Startup Time** | Slow (multiple validations) | Fast (direct initialization) |
| **Debugging** | Complex (multiple layers) | Simple (single service) |

## Benefits

1. **🎯 Single Responsibility**: Only handles recipe execution
2. **🔧 Easy Debugging**: Single service, direct PLC access, clear logs
3. **⚡ Fast Startup**: No complex coordination setup
4. **🧩 Modular**: Can run independently of other terminals
5. **📋 Maintainable**: Simple codebase, easy to understand
6. **🔄 Reliable**: Reuses proven recipe execution logic

## Architecture Alignment

This service implements the **user's vision** of a simple 3-terminal system:

- **Terminal 1**: PLC Read Service (parameter monitoring)
- **Terminal 2**: Recipe Service (recipe execution) ← **THIS SERVICE**
- **Terminal 3**: Parameter Service (parameter control)

Each terminal has **direct PLC access** and operates **independently** without complex coordination.