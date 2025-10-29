# Terminal Liveness Management System - Complete Guide

## Overview

A comprehensive terminal instance management system that prevents duplicates, monitors health, and automatically recovers crashed terminals.

## ✅ System Components

### 1. Database Schema (`supabase/migrations/20251029160500_create_terminal_liveness.sql`)

**Tables**:
- `terminal_instances` - Active/stopped terminal records with health metrics
- `terminal_health_history` - Audit trail of all status changes

**Key Features**:
- UNIQUE constraint prevents duplicate terminals (one per type per machine)
- Automatic heartbeat tracking with missed_heartbeats counter
- Status lifecycle: starting → healthy → stopping → stopped (or crashed)
- Helper functions: `detect_dead_terminals()`, `mark_terminal_crashed()`, `get_terminal_uptime()`

### 2. TerminalRegistry Library (`src/terminal_registry.py`)

**Purpose**: Core library for terminal liveness management

**Features**:
- Duplicate prevention at registration time
- Automatic heartbeat loop (every 10s by default)
- Health metrics tracking (commands_processed, errors_encountered)
- Graceful shutdown with signal handlers (SIGTERM/SIGINT)
- Context manager support (`async with registry: ...`)

**Usage**:
```python
from src.terminal_registry import TerminalRegistry, TerminalAlreadyRunningError

registry = TerminalRegistry(
    terminal_type='terminal2',  # terminal1, terminal2, or terminal3
    machine_id=os.environ.get('MACHINE_ID'),
    environment='production',
    heartbeat_interval=10,
    log_file_path='/tmp/terminal2.log'
)

try:
    await registry.register()  # Raises TerminalAlreadyRunningError if duplicate
except TerminalAlreadyRunningError as e:
    logger.error(str(e))
    sys.exit(1)

# Track operations
registry.increment_commands()  # On success
registry.record_error("Error message")  # On failure

# Graceful shutdown
await registry.shutdown(reason="Service shutdown")
```

### 3. Terminal Services (Integrated)

**Terminal 1**: PLC Data Service (`plc_data_service.py`)
- **Purpose**: Continuous PLC data collection (1-second intervals)
- **Liveness Integration**: ✅ Complete
- **Metrics**: Tracks successful/failed readings

**Terminal 2**: Recipe Service (`simple_recipe_service.py`)
- **Purpose**: Recipe command processing and execution
- **Liveness Integration**: ✅ Complete
- **Metrics**: Tracks recipe commands processed

**Terminal 3**: Parameter Service (`terminal3_clean.py`)
- **Purpose**: Parameter control commands (external writes)
- **Liveness Integration**: ✅ Complete
- **Metrics**: Tracks parameter writes

### 4. Terminal Monitor Service (`terminal_monitor.py`)

**Purpose**: Monitors terminal health and performs automatic recovery

**Features**:
- Dead terminal detection via missed heartbeats
- Automatic terminal restart on crash
- Degraded terminal detection (high error rate)
- Configurable monitoring intervals
- Retry logic with exponential backoff (5s, 15s, 30s)
- Maximum 3 recovery attempts per terminal

**Usage**:
```bash
# Start monitor with defaults (30s check interval, 30s heartbeat timeout)
python terminal_monitor.py

# Custom configuration
python terminal_monitor.py --check-interval 60 --heartbeat-timeout 45

# Disable auto-recovery (monitoring only)
python terminal_monitor.py --no-auto-recovery

# Override machine ID
python terminal_monitor.py --machine-id <uuid>
```

## 🚀 Quick Start Guide

### Step 1: Apply Database Migration

```bash
# Using Supabase MCP tool
# The migration file is: supabase/migrations/20251029160500_create_terminal_liveness.sql

# Or manually via psql
psql <connection_string> < supabase/migrations/20251029160500_create_terminal_liveness.sql
```

### Step 2: Start Terminals (One at a Time)

```bash
# Terminal 1: PLC Data Service
export MACHINE_ID=<your-machine-id>
export PLC_TYPE=simulation
python plc_data_service.py --demo

# Terminal 2: Recipe Service
python simple_recipe_service.py --demo

# Terminal 3: Parameter Service
python terminal3_clean.py
```

### Step 3: Start Terminal Monitor (Optional but Recommended)

```bash
# In a separate terminal/tmux session
python terminal_monitor.py
```

## 📊 Monitoring & Debugging

### Check Active Terminals

```sql
-- View all active terminals
SELECT * FROM active_terminals;

-- View terminals for specific machine
SELECT * FROM terminal_instances
WHERE machine_id = '<machine-id>'
AND status IN ('starting', 'healthy', 'degraded');
```

### Check Terminal Health History

```sql
-- View status changes for a terminal
SELECT
    previous_status,
    new_status,
    reason,
    uptime_seconds,
    created_at
FROM terminal_health_history
WHERE terminal_instance_id = '<terminal-id>'
ORDER BY created_at DESC;
```

### Detect Dead Terminals

```sql
-- Find terminals with missed heartbeats (30s timeout)
SELECT * FROM detect_dead_terminals(30);
```

### Terminal Health Summary

```sql
-- Last 24 hours summary
SELECT * FROM terminal_health_summary;
```

## 🔍 Common Operations

### Manually Mark Terminal as Crashed

```sql
SELECT mark_terminal_crashed(
    '<terminal-instance-id>',
    'Manual crash marking for testing'
);
```

### Get Terminal Uptime

```sql
SELECT get_terminal_uptime('<terminal-instance-id>');
```

### Force Stop a Terminal

```bash
# Find the terminal PID from database
# Then send SIGTERM for graceful shutdown
kill -TERM <pid>

# Or force kill (not recommended - will be marked as crashed)
kill -9 <pid>
```

## 🎯 Testing Scenarios

### Test 1: Duplicate Prevention

```bash
# Start Terminal 2
python simple_recipe_service.py --demo

# Try to start another Terminal 2 (should fail)
python simple_recipe_service.py --demo
# Expected: TerminalAlreadyRunningError with details of existing instance
```

### Test 2: Heartbeat Monitoring

```bash
# Start a terminal
python simple_recipe_service.py --demo

# Monitor heartbeats in database (should update every ~10s)
watch -n 2 "psql <conn> -c \"SELECT terminal_type, last_heartbeat, \
    EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_ago \
    FROM terminal_instances WHERE status = 'healthy'\""
```

### Test 3: Graceful Shutdown

```bash
# Start a terminal
python simple_recipe_service.py --demo

# Send SIGTERM
pkill -TERM -f simple_recipe_service

# Check database - status should be 'stopped', stopped_at should be set
```

### Test 4: Crash Detection

```bash
# Start terminal monitor
python terminal_monitor.py --heartbeat-timeout 30

# Start a terminal
python simple_recipe_service.py --demo

# Kill terminal ungracefully (simulates crash)
pkill -9 -f simple_recipe_service

# Wait 30+ seconds - monitor should detect and mark as crashed
# If auto-recovery enabled, it will attempt restart
```

### Test 5: Auto-Recovery

```bash
# Start monitor with auto-recovery (default)
python terminal_monitor.py

# In another terminal, start Terminal 2
python simple_recipe_service.py --demo

# Kill Terminal 2 (simulate crash)
pkill -9 -f simple_recipe_service

# Monitor logs should show:
# 1. Dead terminal detected
# 2. Marked as crashed
# 3. Recovery initiated
# 4. Terminal restarted successfully
```

## 📋 Status Reference

### Terminal Status Values

- `starting` - Terminal is initializing
- `healthy` - Terminal running normally
- `degraded` - Terminal running but experiencing issues (high error rate)
- `stopping` - Terminal shutting down gracefully
- `stopped` - Terminal stopped gracefully
- `crashed` - Terminal died unexpectedly (detected by missed heartbeats)

### Status Transitions

Normal lifecycle:
```
starting → healthy → stopping → stopped
```

Crash scenario:
```
starting → healthy → [missed heartbeats] → crashed
```

Recovery:
```
crashed → [monitor restarts] → starting → healthy
```

## 🔧 Configuration Options

### TerminalRegistry

- `terminal_type`: 'terminal1', 'terminal2', or 'terminal3'
- `machine_id`: Machine UUID
- `environment`: 'production', 'development', or 'testing'
- `heartbeat_interval`: Seconds between heartbeats (default 10)
- `log_file_path`: Optional log file path for debugging

### Terminal Monitor

- `--check-interval`: Seconds between health checks (default 30)
- `--heartbeat-timeout`: Seconds before terminal considered dead (default 30)
- `--no-auto-recovery`: Disable automatic restart
- `--restart-delay`: Seconds to wait before restart (default 5)
- `--machine-id`: Override machine ID

## 🚨 Troubleshooting

### Problem: Terminal won't start (duplicate error)

**Solution**: Check for existing instance
```sql
SELECT * FROM terminal_instances
WHERE terminal_type = 'terminal2'
AND machine_id = '<machine-id>'
AND status IN ('starting', 'healthy', 'degraded', 'stopping');
```

If found, either:
1. Wait for it to stop gracefully
2. Kill the process: `kill -TERM <pid>`
3. Manually mark as crashed if process is dead

### Problem: Heartbeats not updating

**Check**:
1. Terminal logs for registry errors
2. Database connection (network issues?)
3. Supabase service status

### Problem: Monitor not detecting dead terminals

**Check**:
1. `heartbeat_timeout` is > heartbeat_interval
2. Database function `detect_dead_terminals` exists
3. Monitor logs for errors

### Problem: Auto-recovery failing

**Check**:
1. Terminal launch commands in `terminal_monitor.py` are correct
2. Environment variables (MACHINE_ID, PLC_TYPE) are set
3. Terminal logs at `/tmp/terminal*_recovery_*.log`

## 📈 Metrics & Analytics

### Commands Processed by Terminal

```sql
SELECT
    terminal_type,
    COUNT(*) as instances,
    SUM(commands_processed) as total_commands,
    AVG(commands_processed) as avg_per_instance
FROM terminal_instances
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY terminal_type;
```

### Error Rates

```sql
SELECT
    terminal_type,
    SUM(errors_encountered) as total_errors,
    SUM(commands_processed) as total_commands,
    CASE
        WHEN SUM(commands_processed) > 0
        THEN ROUND(100.0 * SUM(errors_encountered) / SUM(commands_processed), 2)
        ELSE 0
    END as error_rate_percent
FROM terminal_instances
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY terminal_type;
```

### Average Uptime

```sql
SELECT
    terminal_type,
    AVG(EXTRACT(EPOCH FROM (COALESCE(stopped_at, NOW()) - started_at))) / 60 as avg_uptime_minutes
FROM terminal_instances
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY terminal_type;
```

### Crash Frequency

```sql
SELECT
    terminal_type,
    COUNT(*) as crash_count,
    MIN(crash_detected_at) as first_crash,
    MAX(crash_detected_at) as last_crash
FROM terminal_instances
WHERE status = 'crashed'
AND crash_detected_at > NOW() - INTERVAL '7 days'
GROUP BY terminal_type;
```

## 🎓 Best Practices

1. **Always use the Terminal Monitor** in production for automatic recovery
2. **Set reasonable timeouts**: heartbeat_timeout should be 2-3x heartbeat_interval
3. **Monitor the monitor**: Keep an eye on monitor logs for recovery attempts
4. **Review health history** regularly to identify patterns
5. **Set up alerts** for high error rates or frequent crashes
6. **Test recovery** in development before deploying to production
7. **Keep terminal launch commands updated** in terminal_monitor.py
8. **Use graceful shutdown** (SIGTERM) instead of SIGKILL when possible

## 📞 Support

For issues with the Terminal Liveness System:

1. Check terminal logs in `/tmp/terminal*.log`
2. Query `terminal_instances` and `terminal_health_history` tables
3. Review monitor logs for recovery attempts
4. Check database for missed heartbeats: `SELECT * FROM detect_dead_terminals(30)`

## 🔗 Related Files

- **Database Migration**: `supabase/migrations/20251029160500_create_terminal_liveness.sql`
- **Core Library**: `src/terminal_registry.py`
- **Monitor Service**: `terminal_monitor.py`
- **Terminal 1**: `plc_data_service.py`
- **Terminal 2**: `simple_recipe_service.py`
- **Terminal 3**: `terminal3_clean.py`
- **Recipe Audit Guide**: `RECIPE_EXECUTION_AUDIT_GUIDE.md`
