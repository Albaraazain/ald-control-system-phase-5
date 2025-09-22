# Log Troubleshooting Guide

## Overview

This guide helps debug issues using the enhanced service-specific logging system in the ALD Control System.

## Quick Reference

### Log File Locations
```bash
# All service logs
ls -la logs/

# Specific service logs
tail -f logs/command_flow.log      # Command processing issues
tail -f logs/recipe_flow.log       # Recipe execution problems
tail -f logs/plc.log              # Hardware communication issues
tail -f logs/data_collection.log   # Parameter logging problems
tail -f logs/connection_monitor.log # Connectivity issues
```

### Common Commands
```bash
# Monitor all errors across services
tail -f logs/*.log | grep ERROR

# Monitor specific service with timestamp
tail -f logs/plc.log | while read line; do echo "$(date): $line"; done

# Search for specific error patterns
grep -r "Connection failed" logs/

# Monitor startup sequence
tail -f logs/machine_control.log logs/command_flow.log logs/plc.log
```

## Troubleshooting by Service

### Command Flow Issues

**Log File:** `logs/command_flow.log`

**Common Issues:**
```bash
# Command not processing
grep "Processing.*command" logs/command_flow.log

# Command status updates failing
grep "status.*error" logs/command_flow.log

# Database connection issues
grep "Supabase\|database" logs/command_flow.log
```

**Example Output:**
```
2024-09-21 15:30:45,123 - [COMMAND_FLOW] - INFO - Processing start_recipe command for recipe_id=123
2024-09-21 15:30:45,145 - [COMMAND_FLOW] - ERROR - Failed to update command status: Connection timeout
```

### Recipe Flow Issues

**Log File:** `logs/recipe_flow.log`

**Common Issues:**
```bash
# Recipe execution failures
grep -A 5 -B 5 "Recipe.*failed\|Recipe.*error" logs/recipe_flow.log

# Step execution problems
grep "Step.*failed\|Step.*error" logs/recipe_flow.log

# Data recording issues
grep "data.*record\|record.*fail" logs/recipe_flow.log
```

**Example Patterns:**
- Recipe validation failures
- Step execution timeouts
- Data recording interruptions
- Process status update errors

### PLC Communication Issues

**Log File:** `logs/plc.log`

**Common Issues:**
```bash
# Connection problems
grep -i "connect\|disconnect\|timeout" logs/plc.log

# Modbus communication errors
grep -i "modbus\|register\|read\|write" logs/plc.log

# Hardware responses
grep -i "response\|value\|parameter" logs/plc.log
```

**Example Troubleshooting:**
```bash
# Check PLC connection status
grep "PLC.*connect" logs/plc.log | tail -10

# Monitor real-time PLC operations
tail -f logs/plc.log | grep -E "(read|write).*register"

# Check for broken pipe errors
grep "Broken pipe\|Connection reset" logs/plc.log
```

### Data Collection Issues

**Log File:** `logs/data_collection.log`

**Common Issues:**
```bash
# Parameter logging failures
grep -i "parameter.*log\|log.*fail" logs/data_collection.log

# Database insert errors
grep -i "insert\|database\|supabase" logs/data_collection.log

# Performance issues
grep -i "slow\|timeout\|performance" logs/data_collection.log
```

### Realtime Issues

**Log File:** `logs/realtime.log`

**Common Issues:**
```bash
# Subscription problems
grep -i "subscribe\|channel\|realtime" logs/realtime.log

# Fallback to polling
grep -i "polling\|fallback" logs/realtime.log

# WebSocket errors
grep -i "websocket\|connection.*lost" logs/realtime.log
```

### Connection Monitor Issues

**Log File:** `logs/connection_monitor.log`

**Common Issues:**
```bash
# Health check failures
grep -i "health.*check\|health.*fail" logs/connection_monitor.log

# Service status changes
grep -i "status.*change\|service.*down" logs/connection_monitor.log

# Reconnection attempts
grep -i "reconnect\|retry" logs/connection_monitor.log
```

## Multi-Service Debugging

### System Startup Issues

Monitor startup sequence across all services:
```bash
# Monitor startup logs in real-time
tail -f logs/machine_control.log logs/command_flow.log logs/plc.log logs/connection_monitor.log

# Check startup sequence completion
grep -h "starting\|started\|ready" logs/*.log | sort
```

### Cross-Service Issues

**Recipe Execution Problems:**
```bash
# Full recipe execution trace
grep -h "recipe.*123" logs/command_flow.log logs/recipe_flow.log logs/step_flow.log | sort

# Data flow issues
grep -h "process.*123" logs/recipe_flow.log logs/data_collection.log | sort
```

**Hardware Communication Chain:**
```bash
# Command → PLC chain
grep -h "valve\|parameter" logs/command_flow.log logs/step_flow.log logs/plc.log | sort
```

### Performance Analysis

**Identify Bottlenecks:**
```bash
# Database operations
grep -h -i "database\|insert\|query" logs/*.log | grep -E "slow|timeout|[0-9]+ms"

# Network operations
grep -h -i "network\|tcp\|socket" logs/*.log | grep -E "slow|timeout|error"

# Processing delays
grep -h -i "processing\|execute" logs/*.log | grep -E "slow|delay|timeout"
```

## Log Analysis Tools

### Automated Log Analysis

Create monitoring scripts:
```bash
#!/bin/bash
# monitor_errors.sh
tail -f logs/*.log | grep --line-buffered -E "(ERROR|CRITICAL)" | while read line; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') ALERT: $line"
done
```

### Log Aggregation

Combine related logs for complex debugging:
```bash
# Recipe execution timeline
function recipe_timeline() {
    local recipe_id=$1
    grep -h "recipe.*$recipe_id" logs/command_flow.log logs/recipe_flow.log logs/step_flow.log | sort
}

# PLC operation sequence
function plc_operations() {
    local timeframe=$1  # e.g., "15:30:00"
    grep "$timeframe" logs/plc.log | grep -E "(read|write|connect)"
}
```

### Performance Monitoring

```bash
# Log file growth monitoring
function log_growth() {
    while true; do
        du -sh logs/*.log
        sleep 60
    done
}

# Error rate monitoring
function error_rate() {
    local service=$1
    grep -c ERROR logs/${service}.log
}
```

## Environment-Specific Debugging

### Development Environment

Enable debug logging for specific services:
```bash
export LOG_LEVEL_COMMAND_FLOW=DEBUG
export LOG_LEVEL_PLC=DEBUG
python main.py
```

### Production Environment

Focus on critical issues:
```bash
# Monitor critical errors only
tail -f logs/*.log | grep CRITICAL

# System health summary
grep -h -c -E "(ERROR|WARNING)" logs/*.log
```

### Docker Environment

Access logs in containerized deployments:
```bash
# Container logs
docker logs ald-control-system -f

# Mounted log directory
docker exec ald-control-system tail -f /app/logs/plc.log
```

## Common Error Patterns

### Startup Errors
```
[COMMAND_FLOW] - ERROR - Failed to initialize command listener: Connection refused
[PLC] - ERROR - PLC connection timeout after 5.0 seconds
[REALTIME] - WARNING - Realtime self-test failed; system will rely on polling
```

**Solution:** Check network connectivity, PLC availability, and Supabase configuration.

### Runtime Errors
```
[RECIPE_FLOW] - ERROR - Recipe execution failed: Step timeout
[DATA_COLLECTION] - ERROR - Failed to insert parameter data: Database connection lost
[PLC] - ERROR - Modbus read failed: Connection reset by peer
```

**Solution:** Verify hardware connections, database connectivity, and system resources.

### Performance Issues
```
[DATA_COLLECTION] - WARNING - Parameter logging falling behind: 150ms delay
[PERFORMANCE] - WARNING - Database pool exhausted: 20/20 connections in use
[PLC] - WARNING - Slow response time: 2500ms for register read
```

**Solution:** Review system load, database configuration, and network latency.

## Emergency Procedures

### System Unresponsive

1. Check all service logs for errors:
```bash
grep -h "CRITICAL\|ERROR" logs/*.log | tail -20
```

2. Verify core services:
```bash
grep -h "health.*check" logs/connection_monitor.log | tail -5
```

3. Check system resources:
```bash
ps aux | grep python
df -h logs/
```

### Data Loss Prevention

Monitor data collection service:
```bash
# Check for recording gaps
grep -i "stop\|start.*record" logs/data_collection.log

# Verify continuous logging
tail -f logs/data_collection.log | grep "parameter.*value"
```

### Emergency Shutdown

Monitor cleanup process:
```bash
# During shutdown
tail -f logs/machine_control.log | grep -i "cleanup\|shutdown"

# Verify process stopping
grep -i "process.*abort\|process.*stop" logs/recipe_flow.log
```

## Best Practices for Debugging

1. **Start with the right service log** - Use service-specific logs rather than searching all logs
2. **Use timestamps** - Correlate events across services using timestamps
3. **Check error context** - Look at logs before and after errors (use `-A` and `-B` grep options)
4. **Monitor in real-time** - Use `tail -f` for active debugging
5. **Search patterns, not exact matches** - Use regex patterns for flexible searching
6. **Combine with system monitoring** - Check CPU, memory, and network alongside logs
7. **Save debugging sessions** - Redirect output to files for later analysis

## Log Rotation and Maintenance

Monitor log rotation:
```bash
# Check current log sizes
ls -lh logs/*.log

# Check rotated logs
ls -lh logs/*.log.*

# Verify rotation is working
grep -i "rotat" logs/*.log
```

Clean old logs:
```bash
# Remove logs older than 30 days
find logs/ -name "*.log.*" -mtime +30 -delete

# Archive old logs
tar -czf logs_archive_$(date +%Y%m%d).tar.gz logs/*.log.*
```