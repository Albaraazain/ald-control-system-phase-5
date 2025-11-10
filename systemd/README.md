# ALD Control System - systemd Auto-Start

This directory contains systemd user service files for automatic startup and crash recovery of the ALD control system terminals on the Raspberry Pi.

## Why systemd Instead of tmux?

**Previous approach**: Manual tmux sessions
- Required SSH login to start
- No auto-restart on crashes
- systemd couldn't track Python processes inside tmux

**New approach**: systemd manages Python processes directly
- Auto-starts on boot (no SSH needed)
- Auto-restarts on crashes (10s delay, max 5 attempts in 5 minutes)
- Proper process tracking and management
- Integrated logging via journalctl

**tmux is still available** for manual debugging if needed.

## Installation

On the Raspberry Pi:

```bash
cd ~/ald-control-system-phase-5
git pull origin main
chmod +x systemd/install.sh
./systemd/install.sh
```

This will:
1. Copy service files to `~/.config/systemd/user/`
2. Enable user lingering (services run without SSH login)
3. Enable services for auto-start at boot

## Starting Services

```bash
# Start all terminals
systemctl --user start ald-terminal1 ald-terminal2 ald-terminal3

# Or individually
systemctl --user start ald-terminal1
```

## Monitoring Services

### Check Status
```bash
# All services
systemctl --user status ald-terminal*

# Specific service
systemctl --user status ald-terminal1
```

### View Logs
```bash
# Follow logs in real-time (like tail -f)
journalctl --user -u ald-terminal1 -f

# Last 50 lines
journalctl --user -u ald-terminal1 -n 50

# All terminals combined
journalctl --user -u ald-terminal* -f

# Logs since boot
journalctl --user -u ald-terminal1 -b

# Logs from last hour
journalctl --user -u ald-terminal1 --since "1 hour ago"
```

### Check Terminal Health in Database
```sql
SELECT terminal_type, status, last_heartbeat,
       EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
FROM terminal_instances
WHERE machine_id = 'e3e6e280-0794-459f-84d5-5e468f60746e'
ORDER BY terminal_type;
```

## Managing Services

### Restart
```bash
# Restart specific terminal
systemctl --user restart ald-terminal1

# Restart all terminals
systemctl --user restart ald-terminal1 ald-terminal2 ald-terminal3
```

### Stop
```bash
# Stop specific terminal
systemctl --user stop ald-terminal1

# Stop all terminals
systemctl --user stop ald-terminal1 ald-terminal2 ald-terminal3
```

### Disable Auto-Start
```bash
systemctl --user disable ald-terminal1
```

### Re-enable Auto-Start
```bash
systemctl --user enable ald-terminal1
```

## After Code Changes

When you update code on the Pi:

```bash
cd ~/ald-control-system-phase-5
git pull origin main

# Restart services to use new code
systemctl --user restart ald-terminal1 ald-terminal2 ald-terminal3

# Verify they're running with new code
journalctl --user -u ald-terminal1 -n 20
```

## Service Configuration

Each service file (`ald-terminal{1,2,3}.service`) contains:

- **Auto-restart policy**: `Restart=on-failure` with 10s delay
- **Crash protection**: Max 5 restarts in 5 minutes (prevents restart loops)
- **Network dependency**: Waits for network before starting
- **Logging**: All output goes to systemd journal
- **Working directory**: `/home/atomicoat/ald-control-system-phase-5`
- **Python environment**: Uses venv at `myenv/bin/python`

## Debugging with tmux (Optional)

You can still use tmux for interactive debugging:

```bash
# Create tmux session manually
tmux new-session -d -s debug-terminal1
tmux send-keys -t debug-terminal1 "cd ~/ald-control-system-phase-5" C-m
tmux send-keys -t debug-terminal1 "source myenv/bin/activate" C-m
tmux send-keys -t debug-terminal1 "python plc_data_service.py --plc real" C-m

# Attach to see output
tmux attach-session -t debug-terminal1
```

But for normal operations, use systemd services + journalctl.

## Troubleshooting

### Services won't start at boot
```bash
# Check if lingering is enabled
loginctl show-user atomicoat | grep Linger

# Should show: Linger=yes
# If not, enable it:
loginctl enable-linger atomicoat
```

### Service keeps restarting
```bash
# Check why it's failing
journalctl --user -u ald-terminal1 -n 100

# Check if it hit start limit
systemctl --user status ald-terminal1
# Look for "start request repeated too quickly"

# Reset start limit and try again
systemctl --user reset-failed ald-terminal1
systemctl --user start ald-terminal1
```

### Service not auto-restarting after crash
Check restart policy in service file:
```bash
systemctl --user cat ald-terminal1 | grep Restart
```

Should show:
- `Restart=on-failure`
- `RestartSec=10`

### View service dependencies
```bash
systemctl --user list-dependencies ald-terminal1
```

## Migration from tmux

If you have tmux sessions running, stop them before starting systemd services:

```bash
# Stop all tmux sessions
tmux kill-session -t terminal1
tmux kill-session -t terminal2
tmux kill-session -t terminal3

# Start systemd services
systemctl --user start ald-terminal1 ald-terminal2 ald-terminal3
```

## Performance Notes

systemd services have identical performance to tmux approach:
- Same Python processes
- Same PLC communication
- Same database operations

The only difference is how the process is managed (systemd vs tmux).
