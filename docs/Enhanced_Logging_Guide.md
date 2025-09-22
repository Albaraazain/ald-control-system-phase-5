# Enhanced Service-Specific Logging Guide

## Overview

The ALD Control System now implements service-specific logging to improve debugging, monitoring, and maintenance. Each service component writes to its own dedicated log file while maintaining backward compatibility with existing code.

## Architecture

### Service-Specific Loggers

The enhanced logging system creates dedicated loggers for each major service:

- **command_flow**: Commands, command processing, and execution flow
- **recipe_flow**: Recipe execution, process management, and workflow
- **step_flow**: Individual step execution (valve, purge, parameter, loop)
- **plc**: PLC communication, Modbus operations, and hardware interface
- **data_collection**: Parameter logging, data recording, and metrics
- **security**: Authentication, validation, and security monitoring
- **performance**: Performance metrics, optimization, and resource usage
- **agents**: Agent supervisor, lifecycle management, and coordination
- **realtime**: Supabase realtime connections and subscriptions
- **connection_monitor**: Health checks, connectivity, and system status

### Log File Structure

```
logs/
├── command_flow.log      # Command processing and execution
├── recipe_flow.log       # Recipe execution and workflow
├── step_flow.log         # Individual step operations
├── plc.log              # PLC communication and hardware
├── data_collection.log   # Parameter logging and data recording
├── security.log         # Security operations and validation
├── performance.log      # Performance metrics and optimization
├── agents.log           # Agent management and coordination
├── realtime.log         # Realtime connections and subscriptions
├── connection_monitor.log # System health and connectivity
└── machine_control.log  # Legacy/fallback logger (backward compatibility)
```

## Usage Guide

### Using Service-Specific Loggers

#### New Code (Recommended)
```python
from src.log_setup import get_service_logger

# Get a service-specific logger
logger = get_service_logger('command_flow')

# Use the logger normally
logger.info("Processing start_recipe command")
logger.warning("Recipe validation failed")
logger.error("Command execution error", exc_info=True)
```

#### Legacy Code (Still Supported)
```python
from src.log_setup import logger

# This still works and logs to machine_control.log
logger.info("Legacy logging message")
```

### Service Logger Mapping

When creating new modules, use the appropriate service logger:

```python
# Command Flow modules
from src.log_setup import get_service_logger
logger = get_service_logger('command_flow')

# Recipe Flow modules
from src.log_setup import get_service_logger
logger = get_service_logger('recipe_flow')

# PLC modules
from src.log_setup import get_service_logger
logger = get_service_logger('plc')

# Data Collection modules
from src.log_setup import get_service_logger
logger = get_service_logger('data_collection')
```

## Configuration

### Log Levels

Each service logger respects the global `LOG_LEVEL` environment variable:

```bash
# Set log level for all services
export LOG_LEVEL=DEBUG

# Or via command line
python main.py --log-level DEBUG
```

Supported levels: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`

### Log File Locations

By default, logs are written to the `logs/` directory. Override with environment variables:

```bash
# Change log directory
export LOG_DIR=/var/log/ald-control

# Change specific service log file
export COMMAND_FLOW_LOG_FILE=/custom/path/commands.log
```

### Log Rotation

Service logs use `RotatingFileHandler` with the following defaults:
- **Max file size**: 10 MB per log file
- **Backup count**: 5 files (keeps 5 rotated versions)
- **Total storage**: ~50 MB per service (10MB × 5 backups)

Configure rotation via environment variables:
```bash
export LOG_MAX_BYTES=20971520    # 20 MB
export LOG_BACKUP_COUNT=10       # Keep 10 backups
```

## Log Format

All service logs use a consistent format:
```
2024-09-21 15:30:45,123 - command_flow - INFO - Processing start_recipe command for recipe_id=123
```

Format components:
- **Timestamp**: `YYYY-MM-DD HH:MM:SS,mmm`
- **Service**: Service logger name
- **Level**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Message**: Log message with context

## Operational Markers

The system includes operator-friendly status markers:
- **✅ (OK_MARK)**: Success operations
- **⚠️ (WARN_MARK)**: Warning conditions
- **❌ (FAIL_MARK)**: Error conditions

Use ASCII fallback by setting: `export LOG_MARKERS_ASCII=true`

## Migration from Legacy Logging

### Existing Code
No immediate changes required. Existing imports continue to work:
```python
from src.log_setup import logger  # Still works, logs to machine_control.log
```

### Recommended Updates
For better debugging and monitoring, update modules to use service-specific loggers:

```python
# Before
from src.log_setup import logger

# After
from src.log_setup import get_service_logger
logger = get_service_logger('command_flow')  # Replace with appropriate service
```

### Batch Migration
Use this script to identify files that need updating:
```bash
# Find files still using legacy logger import
grep -r "from src.log_setup import logger" src/
```

## Best Practices

### 1. Choose the Correct Service Logger
- Use `command_flow` for command processing logic
- Use `recipe_flow` for recipe execution workflow
- Use `plc` for hardware communication
- Use `data_collection` for parameter logging
- Use specific service loggers rather than the generic logger

### 2. Include Context in Log Messages
```python
# Good - includes context
logger.info(f"Starting recipe execution: recipe_id={recipe_id}, machine_id={machine_id}")

# Poor - lacks context
logger.info("Starting recipe")
```

### 3. Use Appropriate Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational messages
- **WARNING**: Unexpected but recoverable conditions
- **ERROR**: Error conditions that don't stop the service
- **CRITICAL**: Serious errors that may stop the service

### 4. Use Exception Info for Errors
```python
try:
    # risky operation
    pass
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
```

### 5. Avoid Logging Sensitive Information
```python
# Never log passwords, API keys, or sensitive data
logger.info(f"User authentication failed for user: {username}")  # Good
logger.info(f"Authentication failed: {username}:{password}")     # BAD
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Global log level for all services |
| `LOG_DIR` | `logs` | Directory for log files |
| `LOG_MAX_BYTES` | `10485760` | Max size per log file (10MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of backup files to keep |
| `LOG_MARKERS_ASCII` | `false` | Use ASCII markers instead of emojis |
| `*_LOG_FILE` | `{service}.log` | Override specific service log file |

## Integration with Existing Tools

### Linting and Type Checking
The enhanced logging system works with existing development tools:
```bash
# Lint with service-specific logging
python -m pylint --disable=C0103,C0111 --max-line-length=100 *.py

# Type checking
python -m mypy --ignore-missing-imports .
```

### Testing
Service loggers can be tested individually:
```python
from src.log_setup import get_service_logger

def test_command_flow_logging():
    logger = get_service_logger('command_flow')
    logger.info("Test message")
    # Verify log file content
```

### Monitoring and Alerting
Each service log can be monitored independently:
```bash
# Monitor command flow errors
tail -f logs/command_flow.log | grep ERROR

# Monitor all PLC communication
tail -f logs/plc.log

# Monitor critical issues across all services
tail -f logs/*.log | grep CRITICAL
```