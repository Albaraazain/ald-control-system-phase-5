#!/bin/bash
# Quick deployment script for setpoint responsiveness optimization
# 
# This script restarts the Python backend services with the new optimized defaults:
# - Setpoint refresh: 10s → 0.5s (20x faster)
# - Parameter command polling: 10s → 2s (5x faster)
# - Component command polling: 10s → 2s (5x faster)

set -e  # Exit on error

echo "=========================================="
echo "Setpoint Responsiveness Optimization"
echo "=========================================="
echo ""
echo "This will restart all backend terminals with optimized settings:"
echo "  - Setpoint refresh: 0.5s (was 10s)"
echo "  - Command polling: 2s safety check (was 10s)"
echo ""
echo "Expected improvement: 10x faster UI updates"
echo ""

# Check if we're in the right directory
if [ ! -f "terminal1_launcher.py" ]; then
    echo "❌ Error: Must run from ald-control-system-phase-5-1 directory"
    exit 1
fi

# Confirm with user
read -p "Proceed with restart? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Step 1: Stopping existing terminals..."
echo "----------------------------------------"

# Gracefully stop terminals
pkill -f terminal1_launcher || echo "  Terminal 1 not running"
pkill -f terminal2_launcher || echo "  Terminal 2 not running"
pkill -f terminal3_launcher || echo "  Terminal 3 not running"

# Wait for processes to stop
echo "  Waiting for processes to stop..."
sleep 3

echo "✅ All terminals stopped"
echo ""

echo "Step 2: Starting terminals with optimized settings..."
echo "----------------------------------------"

# Optional: Set custom interval (uncomment to override default 0.5s)
# export SETPOINT_REFRESH_INTERVAL=1.0

# Start Terminal 1 (PLC Data Service with optimized setpoint refresh)
echo "  Starting Terminal 1 (PLC Data Service)..."
python terminal1_launcher.py > /tmp/terminal1_startup.log 2>&1 &
TERM1_PID=$!
sleep 2

# Start Terminal 2 (Recipe Service)
echo "  Starting Terminal 2 (Recipe Service)..."
python terminal2_launcher.py > /tmp/terminal2_startup.log 2>&1 &
TERM2_PID=$!
sleep 2

# Start Terminal 3 (Parameter Control with optimized polling)
echo "  Starting Terminal 3 (Parameter Control)..."
python terminal3_launcher.py > /tmp/terminal3_startup.log 2>&1 &
TERM3_PID=$!
sleep 2

echo "✅ All terminals started"
echo ""

echo "Step 3: Verifying services..."
echo "----------------------------------------"

# Check if processes are running
if ps -p $TERM1_PID > /dev/null; then
    echo "✅ Terminal 1 running (PID: $TERM1_PID)"
else
    echo "❌ Terminal 1 failed to start"
    cat /tmp/terminal1_startup.log
    exit 1
fi

if ps -p $TERM2_PID > /dev/null; then
    echo "✅ Terminal 2 running (PID: $TERM2_PID)"
else
    echo "❌ Terminal 2 failed to start"
    cat /tmp/terminal2_startup.log
    exit 1
fi

if ps -p $TERM3_PID > /dev/null; then
    echo "✅ Terminal 3 running (PID: $TERM3_PID)"
else
    echo "❌ Terminal 3 failed to start"
    cat /tmp/terminal3_startup.log
    exit 1
fi

echo ""
echo "Step 4: Checking configuration..."
echo "----------------------------------------"

# Wait a moment for logs to be written
sleep 3

# Check Terminal 1 logs for new setpoint interval
if grep -q "Setpoint refresh interval: 0.5s" /tmp/terminal1_plc_data_service.log 2>/dev/null; then
    echo "✅ Setpoint refresh interval: 0.5s (optimized)"
elif grep -q "Setpoint refresh interval:" /tmp/terminal1_plc_data_service.log 2>/dev/null; then
    INTERVAL=$(grep "Setpoint refresh interval:" /tmp/terminal1_plc_data_service.log | tail -1 | grep -oP '\d+\.?\d*s')
    echo "ℹ️  Setpoint refresh interval: $INTERVAL (custom)"
else
    echo "⚠️  Could not verify setpoint interval (check logs)"
fi

# Check Terminal 3 logs for polling interval
if grep -q "parameter command polling (interval: 2s" /tmp/terminal3_parameter_control.log 2>/dev/null; then
    echo "✅ Parameter command polling: 2s (optimized)"
elif grep -q "parameter command polling (interval:" /tmp/terminal3_parameter_control.log 2>/dev/null; then
    INTERVAL=$(grep "parameter command polling (interval:" /tmp/terminal3_parameter_control.log | tail -1 | grep -oP '\d+s')
    echo "ℹ️  Parameter command polling: $INTERVAL"
else
    echo "⚠️  Could not verify polling interval (check logs)"
fi

echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
echo "Services Status:"
echo "  Terminal 1 (PID $TERM1_PID): PLC Data Service"
echo "  Terminal 2 (PID $TERM2_PID): Recipe Service"
echo "  Terminal 3 (PID $TERM3_PID): Parameter Control"
echo ""
echo "Expected Improvements:"
echo "  • Setpoint updates: 10s → 0.5s (20x faster)"
echo "  • Command polling: 10s → 2s (5x faster)"
echo "  • UI feedback: ~10x faster overall"
echo ""
echo "Next Steps:"
echo "  1. Open Flutter app and test setpoint changes"
echo "  2. Monitor logs: tail -f /tmp/terminal1_plc_data_service.log"
echo "  3. Verify UI updates within 1-2 seconds"
echo ""
echo "Rollback (if needed):"
echo "  export SETPOINT_REFRESH_INTERVAL=10.0"
echo "  ./scripts/apply_responsiveness_optimization.sh"
echo ""
echo "Documentation: docs/SETPOINT_RESPONSIVENESS_OPTIMIZATION.md"
echo "=========================================="

