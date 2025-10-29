# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Raspberry Pi & PLC Connection Setup

### SSH Connection to Raspberry Pi
The control system runs on a Raspberry Pi that connects to the PLC. SSH access is via Tailscale VPN.

**Connection Details:**
- **Pi Tailscale IP**: 100.100.138.5
- **Username**: atomicoat
- **SSH Key**: Uses ED25519 key authentication (no password)
- **Connection command**: `ssh atomicoat@100.100.138.5`

**Setting up SSH keys (if needed):**
```bash
# Generate SSH key on local machine
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "your-machine-to-pi"

# Display public key to add to Pi
cat ~/.ssh/id_ed25519.pub

# On the Pi (via local network access), add the public key:
echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### PLC Configuration
- **PLC IP Address**: 192.168.1.50 (static)
- **PLC Port**: 502 (Modbus TCP)
- **PLC Network**: Connected to Superbox router via Ethernet
- **Pi Connection**: Pi connects to same router via WiFi (192.168.1.x network)
- **Byte Order**: badc (big-byte/little-word)

**Important**: The PLC must be on the same network as the Pi. Verify connectivity:
```bash
ssh atomicoat@100.100.138.5 'ping -c 3 192.168.1.50'
```

### Environment Configuration (.env file)
The `.env` file on the Pi must be configured with:
```bash
SUPABASE_URL=https://yceyfsqusdmcwgkwxcnt.supabase.co
SUPABASE_KEY=your_key_here
SUPABASE_SERVICE_ROLE_KEY=your_key_here
MACHINE_ID=e3e6e280-0794-459f-84d5-5e468f60746e
TEST_OPERATOR_ID=1c6748d7-5cb2-444c-8e2e-416c14f5d6dd

# PLC Configuration
PLC_TYPE=real
PLC_IP=192.168.1.50
PLC_PORT=502
PLC_BYTE_ORDER=badc
```

### Testing PLC Connection
```bash
# From Mac to Pi
ssh atomicoat@100.100.138.5

# On Pi - test PLC connectivity
cd ~/ald-control-system-phase-5
source myenv/bin/activate
python main.py --doctor --plc real
```

Expected output: All tests should pass (Supabase, Health_Table, Realtime, PLC)

## 🚨 CRITICAL: Deploying Code Changes to Raspberry Pi

**NEVER FORGET**: After making code changes, you MUST deploy to the Raspberry Pi!

### Deployment Checklist (DO THIS EVERY TIME)

1. **Commit and push changes**:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Pull on Raspberry Pi**:
   ```bash
   ssh atomicoat@100.100.138.5 'cd ~/ald-control-system-phase-5 && git pull origin main'
   ```

3. **Restart terminals on Pi** (see commands below)

4. **Verify terminals are running with new code**:
   ```bash
   # Check terminal liveness in database
   # Or check tmux output for version/timestamps
   ssh atomicoat@100.100.138.5 'tmux capture-pane -t terminal1 -p | head -30'
   ```

### Why This Matters

- The Pi runs independently from your local machine
- Terminals won't get updates unless you explicitly pull and restart
- Running old code causes confusion and debugging nightmares
- Terminal liveness system helps track what version is actually running

## Running Terminals on Raspberry Pi with tmux

The control system runs as background services using tmux sessions on the Raspberry Pi. This allows terminals to keep running after disconnecting SSH and enables mobile control.

### Starting All Terminals

**⚠️ IMPORTANT: Use the correct commands for each terminal:**
```bash
# Connect to Pi
ssh atomicoat@100.100.138.5
cd ~/ald-control-system-phase-5
source myenv/bin/activate

# Start Terminal 1 (PLC Read Service)
tmux new-session -d -s terminal1
tmux send-keys -t terminal1 "source myenv/bin/activate" C-m
tmux send-keys -t terminal1 "python plc_data_service.py --plc real" C-m

# Start Terminal 2 (Recipe Service)
tmux new-session -d -s terminal2
tmux send-keys -t terminal2 "source myenv/bin/activate" C-m
tmux send-keys -t terminal2 "python simple_recipe_service.py" C-m

# Start Terminal 3 (Parameter Service)
tmux new-session -d -s terminal3
tmux send-keys -t terminal3 "source myenv/bin/activate" C-m
tmux send-keys -t terminal3 "python terminal3_clean.py" C-m
```

**One-liner to restart all terminals:**
```bash
ssh atomicoat@100.100.138.5 'cd ~/ald-control-system-phase-5 && tmux kill-session -t terminal1 2>/dev/null; tmux kill-session -t terminal2 2>/dev/null; tmux kill-session -t terminal3 2>/dev/null; sleep 2 && tmux new-session -d -s terminal1 && tmux send-keys -t terminal1 "source myenv/bin/activate" C-m && sleep 1 && tmux send-keys -t terminal1 "python plc_data_service.py --plc real" C-m && tmux new-session -d -s terminal2 && tmux send-keys -t terminal2 "source myenv/bin/activate" C-m && sleep 1 && tmux send-keys -t terminal2 "python simple_recipe_service.py" C-m && tmux new-session -d -s terminal3 && tmux send-keys -t terminal3 "source myenv/bin/activate" C-m && sleep 1 && tmux send-keys -t terminal3 "python terminal3_clean.py" C-m'
```

### Managing tmux Sessions

**List running sessions:**
```bash
ssh atomicoat@100.100.138.5 'tmux list-sessions'
```

**View terminal output:**
```bash
# Attach to a terminal to see live output
ssh atomicoat@100.100.138.5 -t 'tmux attach-session -t terminal1'
# Press Ctrl+B then D to detach without stopping

# Capture recent output without attaching
ssh atomicoat@100.100.138.5 'tmux capture-pane -t terminal1 -p | tail -50'
```

**Stop a terminal:**
```bash
ssh atomicoat@100.100.138.5 'tmux kill-session -t terminal1'
```

**Stop all terminals:**
```bash
ssh atomicoat@100.100.138.5 'tmux kill-session -t terminal1; tmux kill-session -t terminal2; tmux kill-session -t terminal3'
```

**Restart a terminal:**
```bash
# Kill and restart (example for terminal1)
ssh atomicoat@100.100.138.5 'tmux kill-session -t terminal1 2>/dev/null; cd ~/ald-control-system-phase-5 && tmux new-session -d -s terminal1 && tmux send-keys -t terminal1 "source myenv/bin/activate" C-m && sleep 1 && tmux send-keys -t terminal1 "python plc_data_service.py --plc real" C-m'
```

### Terminal Liveness System

All terminals now report to the `terminal_instances` table in Supabase with automatic heartbeat tracking.

**Check terminal status via Supabase:**
```sql
-- View active terminals on Raspberry Pi
SELECT terminal_type, hostname, process_id, status, started_at,
       last_heartbeat, commands_processed, errors_encountered
FROM terminal_instances
WHERE machine_id = 'e3e6e280-0794-459f-84d5-5e468f60746e'
  AND status IN ('starting', 'healthy', 'degraded')
ORDER BY terminal_type;

-- Check heartbeat freshness (should be < 15 seconds ago)
SELECT terminal_type,
       EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
FROM terminal_instances
WHERE machine_id = 'e3e6e280-0794-459f-84d5-5e468f60746e'
  AND status = 'healthy';
```

**Features:**
- Duplicate prevention: Only one instance of each terminal type per machine
- 10-second heartbeat intervals
- Automatic crash detection if heartbeats stop
- Tracks commands processed and errors encountered
- Web monitoring dashboard available

**Documentation:** See `TERMINAL_LIVENESS_SYSTEM_GUIDE.md` for complete details.

### Monitoring Terminals

**Check system status:**
```bash
# View all log files
ssh atomicoat@100.100.138.5 'tail -30 ~/ald-control-system-phase-5/logs/*.log'

# Monitor live logs
ssh atomicoat@100.100.138.5 'tail -f ~/ald-control-system-phase-5/logs/machine_control.log'
```

**Verify terminals are processing:**
```bash
# Check if terminals are responding to commands
ssh atomicoat@100.100.138.5 'cd ~/ald-control-system-phase-5 && source myenv/bin/activate && python main.py --doctor --plc real'
```

## Build/Lint/Test Commands

- **Setup Environment**: `python -m venv myenv && source myenv/bin/activate && pip install -r requirements.txt`
- **Run Terminal 1 (Local)**: `python main.py --terminal 1 --demo` (PLC Read Service - simulation)
- **Run Terminal 1 (Real PLC)**: `python main.py --terminal 1 --plc real`
- **Run Terminal 2 (Local)**: `python main.py --terminal 2 --demo` (Recipe Service - simulation)
- **Run Terminal 2 (Real PLC)**: `python main.py --terminal 2 --plc real`
- **Run Terminal 3 (Local)**: `python main.py --terminal 3 --demo` (Parameter Service - simulation)
- **Run Terminal 3 (Real PLC)**: `python main.py --terminal 3 --plc real`
- **Test PLC Connection**: `python main.py --doctor --plc real`
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
- **Hybrid Architecture**: Recipe execution writes PLC DIRECTLY for performance (160-350ms per step), then logs audit trail to `parameter_control_commands` AFTER write completes. This hybrid approach provides fast execution + full traceability without routing through Terminal 3.

### ⚙️ TERMINAL 3: Parameter Service (`terminal3_clean.py`)
- **Purpose**: Parameter control and writing for EXTERNAL commands
- **Function**: Listens for parameter commands and writes directly to PLC
- **Database**: Monitors `parameter_control_commands` table
- **Launch**: `python main.py --terminal 3 --demo` or `python terminal3_launcher.py --demo`
- **Features**: Direct PLC access, parameter validation, retry logic, optional verification mode
- **Performance**: ~45-75ms per write operation (optimized from 220-295ms)
  - Production mode (default): Fast writes leveraging Modbus protocol guarantees
  - Verification mode: Enable with `TERMINAL3_VERIFY_WRITES=true` for debugging (~50ms overhead)
- **Scope**: Handles EXTERNAL manual parameter commands from operators/systems. Does NOT process recipe commands - recipes use direct PLC access (Terminal 2) for speed, then audit to this table for traceability.
- **Optimization Notes**: See `OPTIMIZATION_NOTES.md` for details on 79-80% performance improvement

### Key Architecture Benefits

✅ **No Coordination Complexity**: Each terminal operates independently
✅ **Direct PLC Access**: No singleton conflicts, each terminal has its own connection
✅ **Easy Debugging**: Simple to understand, no complex agent coordination
✅ **Independent Operation**: Terminals can run separately without dependencies
✅ **Simplified Deployment**: Just run the terminal you need

### Simple Data Flow

1. **Terminal 1 (PLC Read)**: PLC → Direct Read → Database (parameter_value_history)
2. **Terminal 2 (Recipe)**: Database (recipe_commands) → Direct PLC Execution → Process Updates + Audit Trail (parameter_control_commands)
3. **Terminal 3 (Parameter)**: Database (parameter_control_commands) → Direct PLC Write (external commands only)

**Note**: Terminal 2 uses a hybrid architecture - it writes to PLC directly (fast path: 160-350ms), then logs to parameter_control_commands for audit trail (async background task). Terminal 3 handles external commands only, not recipe-driven changes.

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
- proceed with the one that makes sense, that one that ensure proper implementation longterm, the one that is not mock or a fallback., all must be real actual functional decisions, for getting the app not just to run but run properly./