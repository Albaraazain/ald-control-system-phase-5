#!/usr/bin/env python3
"""
Verify that Terminal 1's setpoint synchronization is working.

This script monitors Terminal 1's log file and checks for:
1. Successful setpoint reads
2. External change detection
3. Database synchronization
"""
import time
import os
from datetime import datetime

LOG_FILE = "/tmp/terminal1_test.log"

def tail_log_file(filepath, num_lines=50):
    """Read the last N lines from a file."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            return lines[-num_lines:]
    except FileNotFoundError:
        return []

def analyze_terminal1_logs():
    """Analyze Terminal 1 logs for setpoint synchronization."""
    print("=" * 80)
    print("TERMINAL 1 SETPOINT SYNCHRONIZATION VERIFICATION")
    print("=" * 80)
    print(f"\n📋 Analyzing logs from: {LOG_FILE}")
    print(f"⏰ Current time: {datetime.now().strftime('%H:%M:%S')}\n")
    
    # Read recent log lines
    lines = tail_log_file(LOG_FILE, num_lines=200)
    
    if not lines:
        print("❌ No log file found. Is Terminal 1 running?")
        return
    
    # Search for key indicators
    setpoint_reads = []
    external_changes = []
    sync_messages = []
    errors = []
    
    for line in lines:
        if "Read" in line and "setpoints from PLC" in line:
            setpoint_reads.append(line.strip())
        elif "External change detected" in line or "🔄" in line:
            external_changes.append(line.strip())
        elif "Synchronized" in line and "setpoint" in line:
            sync_messages.append(line.strip())
        elif "Failed to read setpoints" in line or ("setpoint" in line.lower() and "error" in line.lower()):
            errors.append(line.strip())
    
    # Report findings
    print(f"📊 Setpoint Reads: {len(setpoint_reads)} found")
    if setpoint_reads:
        print(f"   Latest: {setpoint_reads[-1][:100]}...")
    
    print(f"\n🔄 External Changes Detected: {len(external_changes)}")
    if external_changes:
        for change in external_changes[-5:]:  # Show last 5
            print(f"   {change[:120]}")
    else:
        print("   (None detected - this is normal if no external changes occurred)")
    
    print(f"\n✅ Synchronization Messages: {len(sync_messages)}")
    if sync_messages:
        for msg in sync_messages[-3:]:  # Show last 3
            print(f"   {msg[:120]}")
    
    print(f"\n❌ Errors: {len(errors)}")
    if errors:
        for error in errors[-3:]:
            print(f"   {error[:120]}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"{'='*80}")
    
    if setpoint_reads:
        print("✅ Terminal 1 IS reading setpoints from PLC")
        # Extract count from last read message
        if setpoint_reads[-1]:
            import re
            match = re.search(r'Read (\d+) setpoints', setpoint_reads[-1])
            if match:
                count = match.group(1)
                print(f"✅ Reading {count} writable parameters")
    else:
        print("❌ Terminal 1 is NOT reading setpoints")
    
    if not errors:
        print("✅ No setpoint-related errors")
    else:
        print(f"⚠️  Found {len(errors)} setpoint-related errors")
    
    if external_changes:
        print(f"✅ External change detection is WORKING ({len(external_changes)} detected)")
    else:
        print("ℹ️  No external changes detected yet (this is expected if machine is stable)")
    
    print("\n💡 To test external change detection:")
    print("   1. Manually change a parameter setpoint on the PLC/machine interface")
    print("   2. Wait 1-2 seconds for Terminal 1 to detect it")
    print("   3. Run this script again to see the detected change")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_terminal1_logs()

