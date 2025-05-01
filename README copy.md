# Machine Control System

A flow-oriented system for controlling industrial machines through recipe execution.

## Project Structure

The project is organized in a flow-oriented manner that follows the natural progression of data and control:

```
machine_control/
├── main.py                # Entry point that ties everything together
├── config.py              # Configuration settings and constants
├── logging.py             # Logging setup
├── db.py                  # Database connection handling
├── command_flow/          # Everything related to command processing flow
│   ├── __init__.py
│   ├── listener.py        # Listens for incoming commands
│   ├── processor.py       # Processes commands by type
│   └── status.py          # Updates command statuses
├── recipe_flow/           # Everything related to recipe execution flow
│   ├── __init__.py
│   ├── starter.py         # Handles starting recipes
│   ├── stopper.py         # Handles stopping recipes
│   ├── executor.py        # Main recipe execution logic
│   └── data_recorder.py   # Records process data points
└── step_flow/             # Everything related to step execution flow
    ├── __init__.py
    ├── executor.py        # Base step execution logic
    ├── purge_step.py      # Purge-specific step logic
    ├── valve_step.py      # Valve-specific step logic
    ├── parameter_step.py  # Parameter-specific step logic
    └── loop_step.py       # Loop-specific step logic
```

## How It Works

1. **Command Processing Flow:**
   - The system listens for commands in the database using Supabase realtime
   - When a command arrives, it is routed to the appropriate handler
   - Command execution status is tracked and updated

2. **Recipe Execution Flow:**
   - Recipe commands trigger the creation of a process execution
   - The recipe's steps are executed in sequence
   - Process data is recorded during execution

3. **Step Execution Flow:**
   - Each recipe step is executed based on its type
   - Different step types have specific execution logic
   - Loop steps can execute child steps multiple times

## Environment Variables

Required environment variables (in a `.env` file):
- `SUPABASE_URL`: URL of your Supabase instance
- `SUPABASE_KEY`: API key for Supabase
- `MACHINE_ID`: Unique identifier for this machine

## Getting Started

1. Create a `.env` file with the required environment variables
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python main.py`

## Supported Command Types

- `start_recipe`: Start execution of a recipe
- `stop_recipe`: Stop a running recipe
- `set_parameter`: Set a specific machine parameter

## Supported Step Types

- `purge`: Run a purging operation for a specified duration
- `valve`: Control a valve for a specified duration
- `set parameter`: Change a parameter value
- `loop`: Repeat a set of child steps multiple times