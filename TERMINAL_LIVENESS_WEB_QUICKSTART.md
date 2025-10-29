# Terminal Liveness Web Dashboard - Quick Start Guide

**Machine**: MACHINE-001 (Lab Room 101)
**Machine UUID**: `e3e6e280-0794-459f-84d5-5e468f60746e`
**Status**: ✅ Web Integration Complete

---

## ✅ What's Ready

The Terminal Liveness Management System is now fully integrated into your Next.js dashboard at `recipe-monitor-app/`:

1. **Backend Integration** ✅
   - TypeScript types (`lib/types/terminal.ts`)
   - React hook (`hooks/use-terminal-status.ts`)
   - Utility functions (`lib/utils/terminal-utils.ts`)

2. **UI Components** ✅
   - TerminalStatusCard component
   - TerminalHealthPanel component

3. **Dashboard Integration** ✅
   - Terminal Health Panel at top of dashboard
   - Real-time updates via Supabase
   - Responsive design (mobile + desktop)

---

## 🚀 Start the Web Dashboard

### 1. Navigate to the app directory
```bash
cd recipe-monitor-app
```

### 2. Install dependencies (if needed)
```bash
npm install
```

### 3. Verify environment variables
Check that `.env.local` has the correct configuration:

```bash
cat .env.local
```

Should show:
```env
NEXT_PUBLIC_SUPABASE_URL=https://yceyfsqusdmcwgkwxcnt.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_MACHINE_ID=e3e6e280-0794-459f-84d5-5e468f60746e
```

✅ **Already configured correctly!**

### 4. Start the development server
```bash
npm run dev
```

### 5. Open in browser
Navigate to: `http://localhost:3000`

You should see:
- ALD Recipe Monitor header
- **Terminal Status panel** (NEW!) showing all 3 terminals
- Control Panel (recipe controls)
- Steps Panel
- Components Panel + Log Panel

---

## 📊 What You'll See

### When Terminals Are Running

The **Terminal Status** panel at the top will show 3 cards:

```
┌─────────────────────────────────────────────────────┐
│ Terminal Status                        [↻ Refresh]  │
├─────────────────────────────────────────────────────┤
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│ │🔄 PLC Data   │  │🍳 Recipe     │  │⚙️ Parameter  │ │
│ │   Service    │  │   Service    │  │   Service    │ │
│ │ ✅ Healthy   │  │ ✅ Healthy   │  │ ✅ Healthy   │ │
│ │              │  │              │  │              │ │
│ │ Up: 5m 32s   │  │ Up: 5m 32s   │  │ Up: 5m 32s   │ │
│ │ Cmd: 124     │  │ Cmd: 0       │  │ Cmd: 0       │ │
│ │ Err: 0       │  │ Err: 0       │  │ Err: 0       │ │
│ │ HB: 2s ago   │  │ HB: 3s ago   │  │ HB: 1s ago   │ │
│ │              │  │              │  │              │ │
│ │ PID: 12345   │  │ PID: 12346   │  │ PID: 12347   │ │
│ │ Host: pi-01  │  │ Host: pi-01  │  │ Host: pi-01  │ │
│ └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────┘
```

### When No Terminals Are Running

You'll see:
```
┌─────────────────────────────────────────────────────┐
│ Terminal Status                        [↻ Refresh]  │
├─────────────────────────────────────────────────────┤
│                                                       │
│        ⚠️ No active terminals detected               │
│                                                       │
└─────────────────────────────────────────────────────┘
```

**This is normal if terminals aren't started yet!**

---

## 🔧 Start the Backend Terminals

To see terminals in the dashboard, you need to start them on the Raspberry Pi:

### SSH to Raspberry Pi
```bash
ssh atomicoat@100.100.138.5
cd ~/ald-control-system-phase-5
source myenv/bin/activate
```

### Start All 3 Terminals in Background
```bash
# Terminal 1 (PLC Data Service)
tmux new-session -d -s terminal1
tmux send-keys -t terminal1 "source myenv/bin/activate" C-m
tmux send-keys -t terminal1 "python main.py --terminal 1 --plc real" C-m

# Terminal 2 (Recipe Service)
tmux new-session -d -s terminal2
tmux send-keys -t terminal2 "source myenv/bin/activate" C-m
tmux send-keys -t terminal2 "python main.py --terminal 2 --plc real" C-m

# Terminal 3 (Parameter Service)
tmux new-session -d -s terminal3
tmux send-keys -t terminal3 "source myenv/bin/activate" C-m
tmux send-keys -t terminal3 "python main.py --terminal 3 --plc real" C-m
```

### Verify Terminals Started
```bash
tmux list-sessions
```

Should show:
```
terminal1: 1 windows (created ...)
terminal2: 1 windows (created ...)
terminal3: 1 windows (created ...)
```

---

## ✨ Features

### Real-Time Updates
- Status changes appear instantly (via Supabase Realtime)
- No page refresh needed
- Updates every ~1 second

### Status Indicators

| Status | Color | Emoji | Meaning |
|--------|-------|-------|---------|
| Healthy | 🟢 Green | ✅ | Running normally |
| Starting | 🔵 Blue | 🔄 | Initializing |
| Degraded | 🟡 Yellow | ⚠️ | Issues detected |
| Crashed | 🔴 Red | ❌ | Process died |
| Stopping | 🟠 Orange | 🛑 | Shutting down |
| Stopped | ⚪ Gray | ⏹️ | Stopped gracefully |

### Metrics Displayed
- **Uptime**: How long terminal has been running
- **Commands**: Total commands processed
- **Errors**: Total errors encountered
- **Heartbeat**: Time since last health check

### Responsive Design
- **Mobile**: 1 column (stacked vertically)
- **Desktop**: 3 columns (side by side)

---

## 🔍 Troubleshooting

### Issue: "No active terminals detected"

**Possible Causes**:
1. Terminals not started on Raspberry Pi
2. Wrong machine UUID configured
3. Terminals crashed

**Solutions**:
```bash
# Check if terminals are running on Pi
ssh atomicoat@100.100.138.5 'tmux list-sessions'

# Check terminal status in database (on your Mac)
psql $DATABASE_URL -c "SELECT terminal_type, status, last_heartbeat FROM terminal_instances WHERE machine_id = 'e3e6e280-0794-459f-84d5-5e468f60746e';"

# Or use Supabase dashboard to check terminal_instances table
```

### Issue: Real-time updates not working

**Possible Causes**:
1. Supabase Realtime not enabled
2. Network connectivity issues

**Solutions**:
- Check browser console for errors
- Verify Supabase Realtime is enabled in project settings
- Click the "Refresh" button to manually update

### Issue: Environment variable error

**Error**: `NEXT_PUBLIC_MACHINE_ID is undefined`

**Solution**:
```bash
# Ensure .env.local exists
ls -la recipe-monitor-app/.env.local

# Restart the dev server
# Press Ctrl+C to stop, then:
npm run dev
```

---

## 📖 Documentation

- **Full Integration Guide**: `TERMINAL_LIVENESS_WEB_INTEGRATION_SUMMARY.md`
- **Backend System**: `TERMINAL_LIVENESS_SYSTEM_GUIDE.md`
- **Test Report**: `TERMINAL_LIVENESS_TEST_REPORT.md`
- **Architecture**: `CLAUDE.md`

---

## 🎯 Next Steps

1. **Start terminals** on Raspberry Pi (see above)
2. **Open dashboard** at `http://localhost:3000`
3. **Verify** all 3 terminals appear with green "✅ Healthy" badges
4. **Test** by stopping a terminal and watching it turn red
5. **Monitor** real-time updates as terminals process commands

---

## 📝 Summary

**What's Configured**:
- ✅ Machine 001 UUID: `e3e6e280-0794-459f-84d5-5e468f60746e`
- ✅ Supabase connection working
- ✅ Web dashboard integrated
- ✅ Real-time subscriptions enabled
- ✅ All environment variables set

**What's Needed**:
- Start the 3 terminal services on Raspberry Pi
- Access the web dashboard at localhost:3000

**Ready to Go!** 🚀
