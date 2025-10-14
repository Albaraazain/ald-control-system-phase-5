# Terminal 2 Recipe Service Testing Guide

This guide provides comprehensive instructions for testing Terminal 2 (Recipe Service) to ensure it properly executes recipes, controls valves, and communicates with the real PLC.

## Overview

Terminal 2 is responsible for:
- Listening for recipe commands in the database
- Executing recipes by processing steps in sequence
- Controlling PLC valves directly (160-350ms per step)
- Logging audit trail to `parameter_control_commands` table
- Updating process execution status in real-time

## Test Tools

### 1. Main Test Suite: `test_terminal2_recipe_execution.py`

**Purpose**: Comprehensive end-to-end test that validates all aspects of Terminal 2 operation.

**What it tests**:
- ✅ Recipe creation and setup
- ✅ Command submission and pickup
- ✅ Recipe execution and step processing
- ✅ PLC valve control
- ✅ Audit trail logging
- ✅ Database consistency

**Usage**:
```bash
# Run with Python virtual environment
source myenv/bin/activate
python test_terminal2_recipe_execution.py
```

**What happens**:
1. Creates a test recipe with 3 valve steps (Valve 1, 2, 3)
2. Submits a recipe command to the database
3. Waits for Terminal 2 to pick up the command
4. Monitors execution progress in real-time
5. Validates PLC connection and valve accessibility
6. Checks audit trail in `parameter_control_commands`
7. Validates database consistency
8. Prints comprehensive test summary

**Expected output**:
```
🚀 TERMINAL 2 RECIPE SERVICE TEST SUITE
============================================================
✅ PASS - Recipe Setup: Created recipe abc123 with 3 valve steps
✅ PASS - Command Submission: Created command def456
✅ PASS - Command Pickup: Command picked up in 2.1s
✅ PASS - Execution Monitoring: Process completed in 5.3s
✅ PASS - PLC Validation: PLC accessible, validated 3 valves
✅ PASS - Audit Trail: Found 3 valve audit records
✅ PASS - Database Consistency: Passed 4/4 consistency checks
============================================================
TOTAL: 7/7 tests passed
🎉 ALL TESTS PASSED! Terminal 2 is working correctly.
```

---

### 2. PLC Valve Monitor: `monitor_plc_valves.py`

**Purpose**: Real-time monitoring of PLC valve states to observe valve control as it happens.

**What it shows**:
- 🔄 Real-time valve state changes (OPEN/CLOSED transitions)
- 📊 Current state of all monitored valves
- ⏱️ Timestamps of state changes
- 📈 Total count of state changes

**Usage**:
```bash
# Monitor default valves 1-5
python monitor_plc_valves.py

# Monitor specific valves
python monitor_plc_valves.py --valves 1,2,3

# Fast updates (100ms interval)
python monitor_plc_valves.py --interval 0.1

# Debug mode
python monitor_plc_valves.py --log-level DEBUG
```

**Expected output**:
```
🔍 PLC VALVE MONITOR
============================================================
   Monitoring valves: [1, 2, 3]
   Update interval: 0.1s
   Press Ctrl+C to stop

📋 Reading initial valve states...
   Valve 1: CLOSED
   Valve 2: CLOSED
   Valve 3: CLOSED

🔄 [14:32:15.123] Valve 1: CLOSED → OPEN
🔄 [14:32:15.623] Valve 1: OPEN → CLOSED
🔄 [14:32:16.124] Valve 2: CLOSED → OPEN
🔄 [14:32:16.624] Valve 2: OPEN → CLOSED
🔄 [14:32:17.125] Valve 3: CLOSED → OPEN
🔄 [14:32:17.625] Valve 3: OPEN → CLOSED

📊 [14:32:20] Status: V1: ⚪ | V2: ⚪ | V3: ⚪ (Changes: 6)
```

---

## Testing Procedure

### Prerequisites

1. **PLC Connection**: Ensure PLC is connected and accessible
2. **Database**: Supabase connection configured
3. **Environment**: Virtual environment activated with all dependencies

```bash
# Activate virtual environment
source myenv/bin/activate

# Verify dependencies
pip install -r requirements.txt
```

### Step-by-Step Testing

#### Test 1: Start Terminal 2

```bash
# Terminal 1 - Start Terminal 2 Recipe Service
python simple_recipe_service.py --log-level INFO
```

**Expected logs**:
```
🤖 SIMPLE RECIPE SERVICE - TERMINAL 2
   Machine ID: machine_001
   Log Level: INFO
   Direct PLC Access: ENABLED
============================================================
🔧 Initializing Recipe Service...
✅ PLC connection established successfully
✅ Realtime listener initialized (with polling fallback)
🚀 Simple Recipe Service started - polling for commands
👂 Listening for recipe commands for machine_id=machine_001
```

#### Test 2: Run Valve Monitor (Optional)

```bash
# Terminal 2 - Start valve monitor
python monitor_plc_valves.py --valves 1,2,3 --interval 0.1
```

Keep this running to observe valve state changes in real-time.

#### Test 3: Run Comprehensive Test

```bash
# Terminal 3 - Run test suite
python test_terminal2_recipe_execution.py
```

**Test will prompt**:
```
⚠️  IMPORTANT: Make sure Terminal 2 (simple_recipe_service.py) is running!
   Start it with: python simple_recipe_service.py --log-level INFO

Is Terminal 2 running? (y/n):
```

Type `y` and press Enter.

#### Test 4: Observe Results

Watch the test progress through:
1. **Recipe Setup** - Creating test recipe and steps
2. **Command Submission** - Submitting recipe command
3. **Command Pickup** - Terminal 2 picks up command within 2s
4. **Execution** - Recipe executes all steps
5. **Validation** - PLC, audit trail, and database checks

**Monitor Terminal 2 logs** for detailed execution:
```bash
# In another terminal
tail -f logs/recipe_flow.log
```

---

## Validation Points

### 1. Command Flow
- ✅ Recipe command transitions: `pending` → `executing` → `completed`
- ✅ Command picked up within polling interval (2s)
- ✅ Process execution record created

### 2. Recipe Execution
- ✅ All recipe steps execute in sequence
- ✅ Each valve step completes successfully
- ✅ Process status updates correctly

### 3. PLC Control
- ✅ Valves open and close via Modbus TCP/IP
- ✅ Valve durations respected (500ms per valve)
- ✅ PLC connection remains stable

### 4. Audit Trail
- ✅ Valve commands logged to `parameter_control_commands`
- ✅ Each valve operation creates audit record
- ✅ Timestamps recorded correctly

### 5. Database Consistency
- ✅ Process execution marked complete
- ✅ Machine status reset to idle
- ✅ Process execution state shows 100% progress
- ✅ Recipe command marked complete

---

## Troubleshooting

### Issue: Command not picked up

**Symptoms**: Test hangs at "Waiting for command pickup"

**Solutions**:
1. Check Terminal 2 is running: `ps aux | grep simple_recipe_service`
2. Check database connection in Terminal 2 logs
3. Verify recipe_commands table has pending record:
   ```sql
   SELECT * FROM recipe_commands WHERE status = 'pending' ORDER BY created_at DESC LIMIT 5;
   ```

### Issue: PLC connection failed

**Symptoms**: "Failed to initialize PLC" error

**Solutions**:
1. Check PLC IP and port in environment variables
2. Verify PLC is powered on and accessible
3. Test PLC connection:
   ```bash
   python debug/test_plc_connection.py
   ```

### Issue: Valves not operating

**Symptoms**: No valve state changes observed

**Solutions**:
1. Check valve cache loaded correctly in Terminal 2 logs
2. Verify valve parameters exist in database:
   ```sql
   SELECT * FROM component_parameters WHERE component_name LIKE '%Valve%';
   ```
3. Check Modbus addresses are correct
4. Run monitor to confirm valve accessibility

### Issue: Audit trail missing

**Symptoms**: Test fails on audit trail validation

**Solutions**:
1. Check `parameter_control_commands` table exists
2. Verify background task execution (may take 1-3 seconds)
3. Check Terminal 2 logs for audit logging errors
4. Query recent audit records:
   ```sql
   SELECT * FROM parameter_control_commands 
   WHERE parameter_name LIKE 'Valve_%' 
   ORDER BY created_at DESC LIMIT 10;
   ```

---

## Performance Benchmarks

### Expected Timing (Real PLC)

- **Command Pickup**: 0.5 - 2 seconds
- **Valve Operation**: 160 - 350ms per valve step
- **Total Recipe (3 valves)**: 2 - 5 seconds
- **Audit Logging**: 1 - 3 seconds (background)

### Expected Timing (Simulation)

- **Command Pickup**: 0.5 - 2 seconds
- **Valve Operation**: ~500ms per valve step (matches duration_ms)
- **Total Recipe (3 valves)**: 2 - 3 seconds
- **Audit Logging**: 1 - 3 seconds (background)

---

## Database Queries for Manual Validation

### Check recent recipe commands
```sql
SELECT 
    id,
    status,
    type,
    created_at,
    executed_at,
    parameters->>'recipe_id' as recipe_id
FROM recipe_commands
WHERE machine_id = 'machine_001'
ORDER BY created_at DESC
LIMIT 10;
```

### Check process executions
```sql
SELECT 
    id,
    status,
    start_time,
    end_time,
    EXTRACT(EPOCH FROM (end_time - start_time)) as duration_seconds
FROM process_executions
WHERE machine_id = 'machine_001'
ORDER BY start_time DESC
LIMIT 10;
```

### Check valve audit trail
```sql
SELECT 
    parameter_name,
    target_value,
    executed_at,
    completed_at,
    machine_id
FROM parameter_control_commands
WHERE parameter_name LIKE 'Valve_%'
    AND machine_id = 'machine_001'
ORDER BY executed_at DESC
LIMIT 20;
```

### Check machine state
```sql
SELECT 
    status,
    current_process_id,
    updated_at
FROM machines
WHERE id = 'machine_001';

SELECT 
    current_state,
    process_id,
    state_since
FROM machine_state
WHERE machine_id = 'machine_001';
```

---

## Success Criteria

A successful test run should show:

✅ **All 7 tests pass** in the test suite
✅ **Valve state changes** visible in monitor (if running)
✅ **Terminal 2 logs** show recipe execution steps
✅ **Database records** show completed process
✅ **Machine status** returns to `idle`
✅ **Audit trail** contains 3 valve records
✅ **No errors** in any logs

---

## Next Steps

After successful testing:

1. **Production Deployment**: Terminal 2 is ready for production use
2. **Integration Testing**: Test with real ALD recipes
3. **Performance Tuning**: Monitor and optimize if needed
4. **Documentation**: Update operational procedures

---

## Additional Resources

- **Terminal 2 Documentation**: `Terminal_2_Recipe_Service_Documentation.md`
- **Architecture Overview**: `CLAUDE.md` (3-Terminal Architecture section)
- **PLC Interface**: `src/plc/real_plc.py`
- **Recipe Executor**: `src/recipe_flow/executor.py`
- **Valve Step Logic**: `src/step_flow/valve_step.py`

---

## Contact

For issues or questions:
- Check logs in `logs/recipe_flow.log`
- Review this guide's troubleshooting section
- Examine Terminal 2 source code for detailed behavior


