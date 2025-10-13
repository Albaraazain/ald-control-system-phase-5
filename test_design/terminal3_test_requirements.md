# Terminal 3 (Parameter Service) Test Requirements

**Investigation Date:** 2025-10-10
**Agent:** worker-190922-9fa560
**Source File:** `parameter_service.py` (880 lines)
**Architecture:** Direct PLC access, no coordination, realtime + polling fallback

---

## Executive Summary

Terminal 3 (Parameter Service) handles parameter control commands from the database and writes them directly to the PLC. The service has **CRITICAL GAPS** in safety validation and complex fallback logic that must be thoroughly tested. Key concerns include:

- **NO parameter value range validation before PLC writes**
- Complex 4-path write mechanism with inconsistent validation
- Realtime subscription with 10s timeout watchdog + polling fallback
- Retry logic with exponential backoff (3 attempts max)
- Race conditions on command claiming (executed_at field)
- No enforcement of timeout_ms parameter
- Mixed async/sync write methods depending on PLC type

---

## 1. Parameter Command Processing Edge Cases

### 1.1 Invalid Command Payloads

**Test Scenarios:**

1. **Missing Required Fields**
   - Command missing `id` field → Should fail with descriptive error
   - Command missing `parameter_name` field → Should fail
   - Command missing `target_value` field → Should fail
   - Command with NULL for required fields → Should handle gracefully

2. **Machine ID Filtering**
   - Command with `machine_id=NULL` (global) → Should be processed by all machines
   - Command with matching `machine_id` → Should be processed
   - Command with non-matching `machine_id` → Should be ignored
   - Command with invalid `machine_id` format → Should handle error

3. **Command ID Duplication**
   - Process same `command_id` twice → Second attempt should skip (already in `processed_commands` set)
   - `command_id` already has `executed_at` timestamp → Should skip with log
   - Race condition: Two services claim same command → Only one should succeed via `IS NULL` filter

### 1.2 Parameter Lookup Edge Cases

**Test Scenarios:**

4. **component_parameter_id Lookup (Primary Path)**
   - Valid `component_parameter_id` → Should find parameter
   - Invalid `component_parameter_id` not in database → Should fail with clear error
   - `component_parameter_id` with NULL `write_modbus_address` → Should use plc_manager path

5. **parameter_name Lookup (Fallback Path)**
   - Valid unique `parameter_name` → Should find parameter
   - Ambiguous `parameter_name` (multiple matches) → Should prefer writable parameter and log warning
   - Non-existent `parameter_name` → Should fail with descriptive error
   - Empty `parameter_name` string → Should fail

6. **Precedence Handling**
   - Command has both `component_parameter_id` AND `parameter_name` → Should use `component_parameter_id` (primary)
   - Command has neither, only `modbus_address` override → Should use direct address write

### 1.3 Retry Logic and Failure Handling

**Test Scenarios:**

7. **Exponential Backoff**
   - First failure → Retry after 5s (base_delay * 2^0)
   - Second failure → Retry after 10s (base_delay * 2^1)
   - Third failure → Retry after 20s (base_delay * 2^2)
   - Fourth failure → Permanent failure, mark completed with error

8. **Retry State Management**
   - Command fails → Added to `state.failed_commands` dict with count=1
   - Command succeeds after 2 retries → Removed from `state.failed_commands`, added to `processed_commands`
   - Command exceeds `max_retries=3` → Marked failed, added to `processed_commands`, removed from `failed_commands`

9. **Cache Cleanup**
   - `processed_commands` exceeds 100 entries → Cleanup keeps last 50
   - `failed_commands` exceeds 50 entries → Cleanup removes commands with `retry_count >= max_retries`

### 1.4 Timeout Handling

**Test Scenarios:**

10. **timeout_ms Parameter**
   - **CRITICAL BUG**: `timeout_ms` is stored but NEVER enforced during PLC writes
   - Command with `timeout_ms=5000` → Test that write doesn't actually timeout
   - Command with `timeout_ms=100` and slow PLC → Write continues past timeout
   - **Expected Fix**: Add timeout enforcement in future iteration

---

## 2. PLC Write Operation Edge Cases

### 2.1 Write Path Selection (4 Distinct Paths)

**Test Scenarios:**

11. **Path 1: Command modbus_address Override**
   - Command has `write_modbus_address` field → Direct write to address, skip parameter lookup
   - Command has `modbus_address` field (legacy) → Direct write to address
   - Override address with `data_type='binary'` → Write to coil using `write_coil()`
   - Override address with `data_type='float'` or missing → Write to holding register
   - Override address invalid (negative, >65535) → Should fail with validation error

12. **Path 2: component_parameter_id → plc_manager.write_parameter()**
   - Valid `component_parameter_id` found → Lookup parameter, call `plc_manager.write_parameter(parameter_id, value)`
   - Parameter not writable (`is_writable=False`) → Should fail or skip
   - Parameter lookup succeeds but PLC write fails → Should trigger fallback to Path 4

13. **Path 3: parameter_name → plc_manager.write_parameter()**
   - Valid unique `parameter_name` → Lookup parameter, call `plc_manager.write_parameter(parameter_id, value)`
   - Ambiguous `parameter_name` → Uses first writable match, logs warning
   - PLC write fails → Should trigger fallback to Path 4

14. **Path 4: Fallback to Direct Address Write**
   - `plc_manager.write_parameter()` fails AND parameter has `write_modbus_address` → Direct write via communicator
   - Fallback for binary parameter → Uses `communicator.write_coil()`
   - Fallback for float parameter → Uses `communicator.write_float()` or `write_integer_32bit()`
   - Fallback when communicator missing write methods → Fails with error
   - Fallback when parameter has NO `write_modbus_address` → Fails permanently

### 2.2 Data Type Handling

**Test Scenarios:**

15. **Binary Data Type (Coils)**
   - Write `target_value=1.0` with `data_type='binary'` → Converts to `True`, writes to coil
   - Write `target_value=0.0` with `data_type='binary'` → Converts to `False`, writes to coil
   - Write `target_value=0.5` with `data_type='binary'` → Converts to `True` (truthy)

16. **Float Data Type (Holding Registers)**
   - Write `target_value=123.45` with `data_type='float'` → Uses `write_float()`
   - Write `target_value=-999.99` → Should write negative float
   - Write `target_value=0.0` → Should write zero

17. **Integer Detection (Holding Registers)**
   - Write `target_value=100.0` (float with `.is_integer()=True`) → Uses `write_integer_32bit()`
   - Write `target_value=100` (int) → Uses `write_integer_32bit()`
   - Write `target_value=100.1` → Uses `write_float()`
   - **Edge Case**: `target_value` is NaN or Inf → `.is_integer()` may raise exception

18. **Missing or Invalid Data Type**
   - Command override path with no `data_type` → Defaults to `'float'`
   - Parameter lookup with NULL `data_type` → Behavior undefined, test fallback
   - Invalid `data_type='foobar'` → Should fail with validation error

### 2.3 PLC Interface Variations (RealPLC vs SimulationPLC)

**Test Scenarios:**

19. **RealPLC with Communicator (Sync Methods)**
   - `plc_manager.plc.communicator.write_coil(addr, bool)` → Sync call, no await
   - `plc_manager.plc.communicator.write_float(addr, float)` → Sync call
   - `plc_manager.plc.communicator.write_integer_32bit(addr, int)` → Sync call
   - Communicator missing method → `hasattr()` check fails, fallback or error

20. **SimulationPLC (Async Methods)**
   - `plc_manager.plc.write_coil(addr, bool)` → Async, requires `await`
   - `plc_manager.plc.write_holding_register(addr, value)` → Async
   - Method call without `await` → Should raise TypeError

21. **Method Availability Detection**
   - `hasattr(plc_manager.plc, 'communicator')` → Determines RealPLC vs SimulationPLC
   - `hasattr(communicator, 'write_float')` → Determines if method available
   - Both checks false → Write fails with "no suitable write method" error

### 2.4 Confirmation Read After Write

**Test Scenarios:**

22. **Successful Confirmation Read**
   - Write succeeds, read returns matching value → Log success with value match
   - Write succeeds, read returns value within 0.001 tolerance → Log success
   - Binary write succeeds, read returns matching bool → Log success

23. **Confirmation Read Failures (Non-Critical)**
   - Write succeeds, read returns different value → Log debug warning but DON'T fail command
   - Write succeeds, read returns NULL → Log debug, command still succeeds
   - Write succeeds, read raises exception → Log exception, command still succeeds
   - **CRITICAL**: Confirmation read failure does NOT trigger retry

24. **No Confirmation Read Path**
   - Command with direct address override → No confirmation read attempted
   - Parameter has no read address → No confirmation read

### 2.5 PLC Connection Failures During Write

**Test Scenarios:**

25. **Connection Check Before Write**
   - PLC disconnected before write → `ensure_plc_connection()` waits up to 30s for reconnection
   - Connection restored within 30s → Write proceeds normally
   - Connection NOT restored after 30s → Command enters retry logic with exponential backoff
   - Retry exhausted after 3 attempts → Command marked failed

26. **Connection Lost During Write**
   - Write starts, PLC disconnects mid-operation → Write fails, triggers retry
   - Write fails due to timeout (if enforced) → Triggers retry
   - Write fails with Modbus exception → Triggers retry

---

## 3. Database Interaction Edge Cases

### 3.1 Realtime Subscription Mechanism

**Test Scenarios:**

27. **Successful Realtime Subscription**
   - Service starts, realtime subscription succeeds within 10s → `connection_monitor.realtime_status['connected']=True`
   - INSERT event received on `parameter_control_commands` → Callback triggers, creates asyncio task
   - Callback processes command successfully → Command executed

28. **Realtime Subscription Timeout (10s Watchdog)**
   - Service starts, realtime subscription takes >10s → Timeout triggers, falls back to polling
   - `connection_monitor.realtime_status['connected']=False` → Polling interval becomes 1s
   - Watchdog timeout logged as warning → Service continues with polling

29. **Realtime Subscription Failure**
   - Supabase realtime unavailable → Subscription raises exception, falls back to polling
   - Realtime channel error callback triggered → `connection_monitor` updated, falls back to polling
   - Network disconnection during subscription → Falls back to polling

30. **Realtime Callback Exception Handling**
   - Callback raises exception during command processing → `asyncio.create_task()` silently loses exception
   - **RISK**: Exceptions in realtime callback are NOT propagated, only logged
   - Test: Insert malformed command via realtime → Verify exception doesn't crash service

### 3.2 Polling Fallback Mechanism

**Test Scenarios:**

31. **Polling Interval Logic**
   - Realtime disconnected → Poll every 1 second
   - Realtime connected → Poll every 10 seconds as safety net
   - Periodic safety poll → Poll every 60 seconds regardless of realtime status

32. **check_pending_parameter_commands() Query**
   - Query `WHERE executed_at IS NULL` → Returns pending commands
   - Filter `machine_id IN (NULL, MACHINE_ID)` → Includes global and local commands
   - Multiple pending commands → Processes in `created_at ASC` order
   - Empty result set → Logs debug, continues

33. **Polling Failure Scenarios**
   - Database query timeout → Logs error, continues to next poll cycle
   - Database connection failure → Logs error, polling continues with next cycle
   - Malformed query result → Logs error, skips malformed records

### 3.3 Command Claiming Race Condition

**Test Scenarios:**

34. **Atomic Command Claiming**
   - Two parameter services (multi-machine setup) try to claim same command → Only one succeeds
   - Claiming uses `.update().eq('id', command_id).is_('executed_at', None)` → Atomic check
   - First service claims → Sets `executed_at`, returns 1 updated row
   - Second service claims → `executed_at` already set, returns 0 rows, skips command

35. **Race Condition Edge Cases**
   - Command claimed but service crashes before processing → Command stuck with `executed_at` set but no `completed_at`
   - Manual database intervention sets `executed_at=NULL` → Command reprocessed
   - Command claimed twice due to database replication lag → Both services process, verify idempotency

### 3.4 Command Finalization

**Test Scenarios:**

36. **Successful Command Finalization**
   - Command succeeds → Sets `completed_at=now()`, no error_message
   - `finalize_parameter_command()` returns success → Command removed from retry tracking

37. **Failed Command Finalization**
   - Command fails after max retries → Sets `completed_at=now()`, `error_message="Failed to write..."`
   - Finalization database update fails → Logs error but marks command as processed locally

38. **No Explicit Status Field**
   - Command completion inferred from `completed_at IS NOT NULL`
   - Command with `completed_at=NULL` and `executed_at!=NULL` → Assumed in-progress or stuck
   - Test query logic: `WHERE completed_at IS NULL` to detect stuck commands

### 3.5 Connection Monitor Integration

**Test Scenarios:**

39. **Realtime Status Synchronization**
   - `connection_monitor.realtime_status['connected']` → Determines polling interval
   - Realtime status desync (monitor says connected but channel closed) → Test recovery
   - Manual `update_realtime_status(False)` → Triggers polling at 1s interval

40. **PLC Status from Connection Monitor**
   - `connection_monitor.plc_status['connected']` → Used by `ensure_plc_connection()`
   - PLC status desync (monitor says connected but manager says disconnected) → Test recovery
   - Connection monitor updates PLC status → Service reacts appropriately

---

## 4. Safety and Validation Edge Cases

### 4.1 CRITICAL: Missing Parameter Value Validation

**Test Scenarios:**

41. **No Min/Max Bounds Checking**
   - **BUG**: Service writes ANY value to PLC without checking `min_value`/`max_value` from parameter table
   - Write `target_value=9999` to parameter with `max_value=100` → Should be rejected but ISN'T
   - Write `target_value=-9999` to parameter with `min_value=0` → Should be rejected but ISN'T
   - **Comparison**: SimulationPLC clamps values (lines 214-217), but parameter_service bypasses this when using direct address writes

42. **No Safety-Critical Parameter Protection**
   - Write extreme value to temperature parameter → No validation, writes directly to PLC
   - Write dangerous pressure value → No validation
   - Test: Identify safety-critical parameters, attempt out-of-bounds writes, verify NO protection

43. **No Parameter Dependency Validation**
   - Write Parameter A while Parameter B requires specific state → No validation
   - Write conflicting parameters simultaneously → No detection

### 4.2 Write Permission Validation

**Test Scenarios:**

44. **is_writable Check**
   - Parameter with `is_writable=True` → Should be writable
   - Parameter with `is_writable=False` → Behavior undefined, test if write attempted or skipped
   - Parameter with NULL `is_writable` → Test fallback behavior

45. **No Role-Based Access Control**
   - Any command can write to any writable parameter → No user/role validation
   - No distinction between operator-level and engineer-level parameters

### 4.3 Rate Limiting and Concurrency

**Test Scenarios:**

46. **No Rate Limiting on Parameter Writes**
   - Rapid parameter writes (10 commands/sec to same parameter) → All processed, no throttling
   - Rapid writes to different parameters → No throttling
   - Test: Burst 100 commands in 1 second, verify all are processed

47. **Concurrent Parameter Writes**
   - Terminal 3 writes parameter A while Terminal 1 reads parameter A → No synchronization
   - Two commands write to same parameter simultaneously → Both processed in order, last write wins
   - Command writes parameter during recipe execution (Terminal 2 controls same parameter) → No conflict detection

### 4.4 Inconsistent Validation Across Write Paths

**Test Scenarios:**

48. **Path 1 (Direct Address) Bypasses ALL Validation**
   - Direct address write with override → Bypasses parameter table lookup, no min/max check, no is_writable check
   - Direct address write to non-existent address → Writes to PLC without validation

49. **Path 2/3 (plc_manager) Has Partial Validation**
   - Uses parameter lookup → Can check is_writable (if implemented)
   - Goes through plc_manager → May apply validation (but currently doesn't)

50. **Path 4 (Fallback) Bypasses Validation**
   - Fallback direct address write → Same as Path 1, no validation

---

## 5. Integration with Other Terminals

### 5.1 Concurrent Operation with Terminal 1 (PLC Read Service)

**Test Scenarios:**

51. **Parameter Write During Data Collection**
   - Terminal 3 writes parameter while Terminal 1 reads all parameters → No synchronization
   - Write completes mid-read → Terminal 1 may read stale or new value, no consistency guarantee
   - Confirmation read by Terminal 3 conflicts with Terminal 1 read → Both succeed independently

52. **PLC Manager Singleton Contention**
   - Terminal 1 uses NEW PLCManager instance → Separate PLC connection
   - Terminal 3 uses GLOBAL plc_manager singleton → Shared PLC connection with Terminal 2
   - **Inconsistency**: Terminal 1 has separate connection, Terminal 2/3 share connection
   - Test: Start all 3 terminals, verify connection count (expect 2 connections, not 3 singletons)

### 5.2 Concurrent Operation with Terminal 2 (Recipe Service)

**Test Scenarios:**

53. **Parameter Write During Recipe Execution**
   - Recipe step writes parameter (e.g., "set parameter" step) → Uses Terminal 2
   - Terminal 3 writes same parameter simultaneously via command → Both writes succeed, last write wins
   - No coordination between Terminal 2 recipe parameter writes and Terminal 3 command writes

54. **Recipe Cancellation During Parameter Write**
   - Terminal 3 writing parameter when recipe cancelled → Write continues, no rollback
   - Recipe step depends on parameter value just written by Terminal 3 → May read stale or new value

### 5.3 Database Contention

**Test Scenarios:**

55. **Simultaneous parameter_control_commands Writes**
   - Multiple commands inserted simultaneously → All picked up by polling or realtime
   - Database transaction isolation level unknown → Test for lost updates

56. **Simultaneous machine_state Updates**
   - Terminal 2 updates machine_state during recipe → Sets machine state
   - Terminal 3 may also update machine_state (if implemented) → Potential conflict
   - No distributed locking → Last write wins

---

## 6. Testing Strategy and Recommendations

### 6.1 Test Categories

1. **Unit Tests**
   - Mock PLC manager, database client
   - Test each write path independently
   - Test retry logic with controlled failures
   - Test data type conversion logic
   - Test command claiming race condition logic

2. **Integration Tests**
   - Use SimulationPLC (not mocks)
   - Use real database (Supabase test instance)
   - Test realtime subscription + polling fallback
   - Test multi-terminal concurrent operation
   - Test confirmation reads after writes

3. **Safety Tests**
   - **CRITICAL**: Test that out-of-bounds writes are NOT prevented (document bug)
   - Test write permission validation
   - Test parameter write during recipe execution
   - Test rapid parameter changes

4. **Stress Tests**
   - Burst 100 commands in 1 second
   - Sustained 10 commands/sec for 10 minutes
   - Test retry exhaustion under persistent PLC failure
   - Test database connection pool exhaustion
   - Test realtime subscription reconnection storms

5. **End-to-End Tests**
   - Start all 3 terminals
   - Insert parameter command
   - Verify write to PLC
   - Verify confirmation read
   - Verify command finalization

### 6.2 Critical Bugs to Document

1. **NO MIN/MAX PARAMETER VALIDATION** - Service writes any value without bounds checking
2. **TIMEOUT_MS NOT ENFORCED** - Parameter stored but never used
3. **CONFIRMATION READ FAILURES DON'T TRIGGER RETRIES** - Value mismatch logged but ignored
4. **REALTIME CALLBACK EXCEPTIONS SILENTLY LOST** - asyncio.create_task() swallows errors
5. **INCONSISTENT VALIDATION ACROSS WRITE PATHS** - Direct address writes bypass all validation
6. **NO RATE LIMITING** - Unlimited parameter write frequency
7. **PLC MANAGER INCONSISTENCY** - Terminal 1 creates new instance, Terminal 2/3 share singleton

### 6.3 Test Execution Priority

**Priority 1 (Immediate):**
- Test #41: No min/max bounds checking (SAFETY CRITICAL)
- Test #42: No safety-critical parameter protection
- Test #34: Command claiming race condition
- Test #28: Realtime subscription timeout fallback
- Test #51: Concurrent writes with Terminal 1 reads

**Priority 2 (High):**
- Test #11-14: All 4 write paths
- Test #19-20: RealPLC vs SimulationPLC interface variations
- Test #53: Parameter write during recipe execution
- Test #7-9: Retry logic and exponential backoff

**Priority 3 (Medium):**
- Test #22-24: Confirmation read scenarios
- Test #31-33: Polling fallback mechanism
- Test #46-47: Rate limiting and concurrency

**Priority 4 (Low):**
- Test #15-18: Data type handling edge cases
- Test #36-38: Command finalization
- Test #45: Write permission validation

---

## 7. Test Data Requirements

### 7.1 Database Test Data

**component_parameters_full table:**
- Parameter with valid `write_modbus_address`, `min_value`, `max_value`, `is_writable=True`
- Parameter with NULL `write_modbus_address` (plc_manager path only)
- Parameter with `is_writable=False`
- Multiple parameters with same `parameter_name` (ambiguous lookup)
- Parameter with `data_type='binary'`
- Parameter with `data_type='float'`
- Safety-critical parameter (e.g., `max_temp`)

**parameter_control_commands table:**
- Valid command with `component_parameter_id`
- Valid command with `parameter_name` only
- Valid command with `modbus_address` override
- Command with `machine_id=NULL` (global)
- Command with matching `machine_id`
- Command with non-matching `machine_id`
- Command with `executed_at` already set
- Command with `completed_at` already set
- Command with invalid `target_value` (out of bounds)

### 7.2 PLC Simulation Test Data

- Parameter address 100: Float, range [0.0, 100.0]
- Parameter address 200: Binary (coil)
- Parameter address 300: Integer, range [0, 1000]
- Unassigned address 999: Should allow write but not associated with parameter

---

## 8. Expected Test Outcomes

### 8.1 Passing Tests

- Valid commands processed successfully
- Retry logic succeeds after transient failures
- Realtime fallback to polling works seamlessly
- Command claiming race condition handled atomically
- All 4 write paths succeed when configured correctly

### 8.2 Failing Tests (Document as Bugs)

- Out-of-bounds parameter values written to PLC (NO VALIDATION)
- Timeout_ms parameter ignored (NOT ENFORCED)
- Confirmation read failures don't trigger retries (SILENT MISMATCH)
- Direct address writes bypass all safety checks (INCONSISTENT VALIDATION)

### 8.3 Performance Benchmarks

- Command processing latency <100ms (p95)
- Retry with exponential backoff completes within 40s (3 retries: 5s + 10s + 20s)
- Realtime subscription reconnection <10s
- Polling fallback latency <2s (1s interval + processing time)
- Concurrent write throughput >10 commands/sec

---

## 9. Conclusion

Terminal 3 Parameter Service has **critical safety validation gaps** that must be tested and documented. The complex 4-path write mechanism, retry logic, and realtime+polling fallback create numerous edge cases. Priority should be given to safety tests (parameter bounds validation, safety-critical parameter protection) and concurrency tests (multi-terminal integration, race conditions).

**RECOMMENDED ACTIONS:**
1. Implement min/max parameter validation BEFORE PLC writes
2. Enforce timeout_ms parameter during write operations
3. Make confirmation read failures trigger retries (or make them optional)
4. Add rate limiting for rapid parameter changes
5. Standardize PLC manager singleton usage across all terminals
6. Add comprehensive test coverage for all 4 write paths and edge cases identified above
