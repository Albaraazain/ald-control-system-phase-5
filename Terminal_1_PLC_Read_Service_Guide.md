# Terminal 1: Simple PLC Read Service

## Overview

This is a **SIMPLE** service that:
- ✅ Reads PLC parameters every 1 second
- ✅ Updates the `parameter_value_history` database table
- ✅ NO coordination with other terminals
- ✅ NO complex architecture
- ✅ Direct PLC access via `plc_manager`

## Files Created

1. **`plc_read_service.py`** - Main service implementation
2. **`launch_plc_read_service.py`** - Easy launcher with status checking
3. **`test_plc_read_service.py`** - Test script to verify functionality

## Quick Start

### Check Status
```bash
python launch_plc_read_service.py --status
```

### Start the Service
```bash
python launch_plc_read_service.py
```

### Test for 5 Seconds
```bash
python test_plc_read_service.py
```

## What It Does

1. **Initialize PLC Connection**: Uses existing `plc_manager` for PLC connectivity
2. **Read Loop**: Every 1 second, reads all parameters via `plc_manager.read_all_parameters()`
3. **Database Update**: Inserts parameter values into `parameter_value_history` table
4. **Error Handling**: Graceful error handling with retry logic and backoff

## Database Schema

The service writes to the `parameter_value_history` table with these fields:
- `parameter_id` - ID of the parameter
- `value` - Current parameter value
- `timestamp` - When the reading was taken

## Key Features

- **Zero Coordination**: No communication with other terminals
- **Direct PLC Access**: Each service has its own PLC connection
- **Simple Architecture**: ~150 lines of straightforward code
- **Robust Error Handling**: Handles PLC disconnections gracefully
- **Easy Debugging**: Clear logging and status reporting

## Architecture Simplification

This replaces the complex `data_collection` service that had:
- ❌ Transactional dual-mode repository
- ❌ ACID compliance overhead
- ❌ Complex coordination between services
- ❌ Multiple abstraction layers

With a simple service that just:
- ✅ Reads PLC → Updates database → Repeat

## Configuration

The service uses existing configuration from:
- Environment variables (`SUPABASE_URL`, `SUPABASE_KEY`, `MACHINE_ID`)
- PLC configuration from `src/config.py`

## Logging

Service-specific logging to `logs/plc_read.log` (when enhanced logging is configured).

## Next Steps

This is Terminal 1 of the 3-terminal architecture:
- **Terminal 1**: PLC Read Service (this service) ✅ COMPLETE
- **Terminal 2**: Recipe Service (simple_recipe_service.py) ✅ COMPLETE
- **Terminal 3**: Parameter Service (parameter_service.py) 🔄 IN PROGRESS