# Terminal 1 (PLC Data Service) - Comprehensive Test Requirements

**Service**: `plc_data_service.py` (526 lines)
**Purpose**: Continuous PLC data collection with 1-second precision and database logging
**Investigation Date**: 2025-10-10
**Agent**: worker-190915-998c24

---

## Executive Summary

Terminal 1 PLC Data Service requires comprehensive testing across 5 critical areas:

1. **PLC Connection Management** - Connection lifecycle, failures, recovery, singleton conflicts
2. **Data Collection Timing** - Precision violations, performance degradation, timing drift
3. **Database Operations** - Batch insert failures, metadata caching, no retry logic
4. **Performance & Scalability** - Large parameter sets, 24hr stability, resource leaks
5. **Integration** - Multi-terminal PLC conflicts, database contention

**CRITICAL FINDINGS**:
- ❌ NO retry logic for failed database writes
- ❌ NO PLC connection health monitoring
- ❌ NO transaction support or rollback capability
- ❌ Timing violations logged but never trigger service degradation
- ❌ Stale metadata cache - never refreshed after startup

---

## 1. PLC Connection Edge Cases

### 1.1 Initial Connection Failures

**Test Scenario**: PLC connection fails during service startup
**Code Location**: `plc_data_service.py:112` - `await self.plc_manager.initialize()`
**Current Behavior**: Service continues with warning, logs "⚠️ PLC connection failed - will retry in background"
**Expected Behavior**: Service should implement retry logic with exponential backoff

**Test Cases**:
```python
test_plc_connection_failure_at_startup()
# - PLC simulation not running
# - Invalid PLC_CONFIG settings
# - Network unreachable
# - DNS resolution failure
# Expected: Service continues, metrics show plc_connected=False, no crash

test_plc_connection_retry_mechanism()
# - Verify "retry in background" actually exists (currently doesn't!)
# - Service should retry connection every 30s with exponential backoff
# Expected: Eventually connects when PLC becomes available

test_plc_connection_timeout()
# - PLC responds slowly (>10s)
# - Connection hangs indefinitely
# Expected: Timeout enforced, logged, service continues
```

**Estimated Test Duration**: 2-3 minutes per test

---

### 1.2 Mid-Operation Disconnections

**Test Scenario**: PLC connection lost during active data collection
**Code Location**: `plc_data_service.py:242` - `if not self.plc_manager.is_connected()`
**Current Behavior**: Skips data collection, logs debug message
**Issues**: No reconnection attempt, no circuit breaker, service continues indefinitely

**Test Cases**:
```python
test_plc_disconnection_during_collection()
# - Simulate PLC disconnect after 10 successful collections
# - Verify service detects disconnection (is_connected() returns False)
# - Verify data collection skipped
# - Verify metrics['failed_readings'] incremented
# Expected: Service logs warning, metrics updated, no crash

test_plc_reconnection_after_disconnect()
# - Disconnect PLC
# - Wait 60s
# - Reconnect PLC
# - Verify service resumes collection automatically
# Expected: Service should auto-reconnect (currently DOESN'T - needs implementation)

test_plc_intermittent_connection()
# - Simulate flaky connection (connect/disconnect every 5s)
# - Run for 2 minutes
# Expected: Service stable, successful_readings increases when connected
```

**Estimated Test Duration**: 3-5 minutes per test

---

### 1.3 Singleton Pattern Conflicts

**Test Scenario**: Multiple terminals create PLCManager instances simultaneously
**Code Location**: `src/plc/manager.py:16-22` - Singleton implementation
**CRITICAL ISSUE**: Terminal 1 creates NEW PLCManager, Terminal 2/3 use global singleton

**Test Cases**:
```python
test_terminal1_plc_manager_isolation()
# - Start Terminal 1 with PLCManager instance
# - Start Terminal 2/3 with global plc_manager singleton
# - Verify 2 separate PLC connections created
# - Verify no connection conflicts
# Expected: Either both work OR documented behavior

test_concurrent_plc_initialization()
# - Start all 3 terminals simultaneously
# - Monitor PLC connection count
# Expected: Should handle gracefully, document max connections

test_plc_manager_state_corruption()
# - Terminal 1 disconnects PLC
# - Verify Terminal 2/3 not affected (separate singletons)
# Expected: Isolation confirmed
```

**Estimated Test Duration**: 5 minutes per test

---

### 1.4 PLC Factory and Interface Failures

**Test Scenario**: PLCFactory.create_plc() exceptions
**Code Location**: `plc_data_service.py:54` - Exception caught and logged

**Test Cases**:
```python
test_invalid_plc_type()
# - Set PLC_TYPE="invalid"
# - Verify service logs error, returns False from initialize()
# Expected: Service handles gracefully, no crash

test_plc_simulation_database_failure()
# - SimulationPLC._load_parameters() query fails
# - Verify service continues with empty parameter list
# Expected: Logged as warning, service operational

test_plc_read_all_parameters_empty_result()
# - PLC returns empty dict from read_all_parameters()
# - Verify data collection skipped
# Expected: Logged, metrics not updated, no crash
```

**Estimated Test Duration**: 2 minutes per test

---

## 2. Data Collection Timing Edge Cases

### 2.1 Timing Precision Violations

**Test Scenario**: Collection duration exceeds 1.0s target interval
**Code Location**: `plc_data_service.py:216` - Timing violation detection
**Current Behavior**: Logged as warning, metrics['timing_violations'] incremented
**CRITICAL ISSUE**: NO degradation handling - service continues indefinitely

**Test Cases**:
```python
test_collection_exceeds_1_second()
# - Mock PLC read to take 1.2s
# - Verify timing violation logged
# - Verify metrics['timing_violations'] incremented
# - Verify sleep_time = 0 (tight loop)
# Expected: Service continues, timing drift accumulates

test_sustained_timing_violations()
# - Mock PLC read to take 1.5s consistently
# - Run for 60s
# - Verify 60+ timing violations
# - Verify NO service degradation triggered
# Expected: Service logs warnings but continues - NEEDS CIRCUIT BREAKER

test_timing_threshold_exceeded()
# - Simulate 100 consecutive timing violations
# - Verify service SHOULD degrade (reduce collection rate)
# Expected: Currently DOESN'T - needs implementation
```

**Estimated Test Duration**: 2-3 minutes per test

---

### 2.2 Performance Degradation Scenarios

**Test Scenario**: PLC/database latency causes timing violations
**Code Location**: `plc_data_service.py:247` - `await self.plc_manager.read_all_parameters()`

**Test Cases**:
```python
test_plc_read_latency_900ms()
# - Mock PLC read_all_parameters() to take 900ms
# - Verify collection completes in <1.1s (within threshold)
# Expected: No timing violations

test_database_insert_latency_500ms()
# - Mock Supabase insert to take 500ms
# - Mock PLC read to take 400ms
# - Total: 900ms (within threshold)
# Expected: No timing violations

test_combined_latency_exceeds_threshold()
# - Mock PLC read: 700ms
# - Mock DB insert: 600ms
# - Total: 1.3s (exceeds 1.1s threshold)
# Expected: Timing violation logged

test_100_parameter_scale()
# - Load 100 parameters in simulation
# - Measure collection duration
# - Verify < 1.0s with current implementation
# Expected: Baseline performance data for optimization
```

**Estimated Test Duration**: 1-2 minutes per test

---

### 2.3 Loop Timing Control Edge Cases

**Test Scenario**: Edge cases in sleep calculation and timing drift
**Code Location**: `plc_data_service.py:213` - `sleep_time = max(0, interval - elapsed_time)`

**Test Cases**:
```python
test_zero_sleep_time_tight_loop()
# - Collection takes exactly 1.0s
# - Verify sleep_time = 0
# - Verify loop continues immediately
# Expected: No sleep, tight loop, increased CPU usage

test_negative_elapsed_time_clock_skew()
# - Simulate system clock adjustment (NTP sync)
# - Verify max(0, ...) prevents negative sleep
# Expected: Service handles gracefully, no exception

test_rolling_average_calculation_overflow()
# - Run service for 1M collections
# - Verify average_collection_duration doesn't overflow
# Expected: Rolling average stable, no precision loss

test_async_cancelled_during_sleep()
# - Trigger service stop during sleep
# - Verify AsyncCancelledError caught
# - Verify loop exits gracefully
# Expected: Clean shutdown, logged
```

**Estimated Test Duration**: 2 minutes per test

---

## 3. Database Write Edge Cases

### 3.1 Batch Insert Failures

**Test Scenario**: Supabase batch insert failures
**Code Location**: `plc_data_service.py:416` - Batch insert to parameter_value_history
**CRITICAL ISSUE**: NO retry logic, failed insert loses entire 1-second collection cycle

**Test Cases**:
```python
test_batch_insert_timeout()
# - Mock Supabase .execute() to timeout after 30s
# - Verify exception caught and logged
# - Verify metrics['failed_readings'] incremented
# - Verify NO retry attempted
# Expected: Data loss, logged, service continues

test_batch_insert_empty_response()
# - Mock response.data = None
# - Verify logged as error
# - Verify success_count = 0
# Expected: Logged as failure, no retry

test_batch_insert_partial_success()
# - Mock batch insert returns only 50 of 100 records
# - Verify no way to identify which records failed
# Expected: Cannot determine failure reason - NEEDS INVESTIGATION

test_batch_insert_rate_limit()
# - Simulate Supabase rate limiting (429 response)
# - Verify NO backoff strategy implemented
# Expected: Immediate retry fails, data loss

test_batch_insert_network_disconnection()
# - Simulate network failure during insert
# - Verify exception caught
# - Verify NO recovery mechanism
# Expected: Data loss for that cycle
```

**Estimated Test Duration**: 2-3 minutes per test

---

### 3.2 Metadata Cache Edge Cases

**Test Scenario**: Parameter metadata cache staleness and failures
**Code Location**: `plc_data_service.py:271-369` - One-time metadata load
**CRITICAL ISSUE**: Cache NEVER refreshed - stale data persists forever

**Test Cases**:
```python
test_metadata_load_failure_at_startup()
# - Mock component_parameters query to fail
# - Verify parameter_metadata = {} (empty)
# - Verify service continues
# - Verify parameter logging uses fallback names
# Expected: Degraded but operational

test_metadata_cache_staleness()
# - Start service, load 10 parameters
# - Add 5 new parameters to database
# - Wait 5 minutes
# - Verify new parameters NOT in cache
# Expected: New parameters never logged - NEEDS REFRESH MECHANISM

test_parameter_deleted_from_database()
# - Load 10 parameters
# - Delete 1 parameter from database
# - Verify stale entry remains in cache
# - Verify PLC read fails for deleted parameter
# Expected: Should handle gracefully, log warning

test_component_definitions_query_failure()
# - Mock component_definitions query to fail
# - Verify component names default to 'Component_unknown'
# Expected: Degraded logging quality but operational
```

**Estimated Test Duration**: 2-3 minutes per test

---

### 3.3 Database Schema and Validation Edge Cases

**Test Scenario**: Invalid data or schema changes
**Code Location**: `plc_data_service.py:397-402` - Record construction

**Test Cases**:
```python
test_invalid_parameter_id_foreign_key()
# - Mock PLC to return parameter_id not in database
# - Verify batch insert fails entirely
# Expected: Exception logged, entire batch lost

test_duplicate_timestamp_inserts()
# - Attempt to insert same timestamp twice
# - Verify unique constraint handling
# Expected: Should fail gracefully or overwrite

test_float_conversion_failure()
# - Mock PLC to return non-numeric value
# - Verify float(value) raises exception
# Expected: Should skip invalid parameter, log warning

test_batch_size_exceeds_supabase_limit()
# - Load 10,000 parameters
# - Attempt batch insert
# - Verify Supabase request size limit
# Expected: Should batch in chunks - NEEDS IMPLEMENTATION
```

**Estimated Test Duration**: 2 minutes per test

---

## 4. Performance & Scalability Edge Cases

### 4.1 Large Parameter Sets

**Test Scenario**: Performance with 100-1000 parameters
**Code Location**: `plc_data_service.py:247` - read_all_parameters()

**Test Cases**:
```python
test_100_parameters_collection_time()
# - Load 100 parameters in simulation
# - Measure collection duration (PLC read + DB insert)
# - Verify < 1.0s
# Expected: Baseline performance

test_1000_parameters_collection_time()
# - Load 1000 parameters
# - Measure collection duration
# - Expect timing violations
# Expected: Service degrades, needs optimization

test_metadata_lookup_overhead()
# - Profile metadata.get(param_id) calls in batch
# - 100 parameters = 100 dict lookups per second
# Expected: Minimal overhead, O(1) lookup

test_batch_insert_size_scaling()
# - Test batch inserts: 10, 100, 1000 records
# - Measure database latency
# Expected: Linear scaling, identify optimal batch size
```

**Estimated Test Duration**: 5 minutes per test

---

### 4.2 Long-Running Stability (24hr+)

**Test Scenario**: Memory leaks, resource exhaustion over 24 hours
**Code Location**: Service-wide

**Test Cases**:
```python
test_24hr_continuous_operation()
# - Run service for 24 hours
# - Monitor memory usage every 1 hour
# - 86,400 collections = 86,400 database inserts
# - Verify memory stable (no leaks)
# Expected: Memory < 500MB, no degradation

test_metrics_overflow()
# - Run for 100,000 collections
# - Verify metrics['total_readings'] doesn't overflow
# - Verify average calculation stable
# Expected: No integer overflow, rolling averages work

test_parameter_metadata_cache_growth()
# - Add parameters dynamically during run
# - Monitor cache size
# - Verify cache doesn't grow indefinitely
# Expected: Cache bounded or refreshed periodically - NEEDS IMPLEMENTATION
```

**Estimated Test Duration**: 24+ hours (run overnight)

---

### 4.3 Resource Cleanup and Shutdown

**Test Scenario**: Graceful shutdown and resource cleanup
**Code Location**: `plc_data_service.py:152-180` - stop() method

**Test Cases**:
```python
test_graceful_shutdown_sigterm()
# - Start service
# - Send SIGTERM
# - Verify signal_handler called
# - Verify PLC disconnected
# - Verify metadata cache cleared
# Expected: Clean shutdown, all resources released

test_shutdown_during_data_collection()
# - Trigger shutdown during PLC read
# - Verify current collection completes or aborts cleanly
# Expected: No hanging operations

test_shutdown_during_database_insert()
# - Trigger shutdown during batch insert
# - Verify insert completes or rolls back
# Expected: No partial data, no corruption

test_async_task_cancellation()
# - Verify data_collection_task properly cancelled
# - No orphaned tasks
# Expected: All tasks cleaned up
```

**Estimated Test Duration**: 1-2 minutes per test

---

## 5. Integration with Other Terminals

### 5.1 Multi-Terminal PLC Contention

**Test Scenario**: Terminal 1 PLC access conflicts with Terminal 2/3
**Code Location**: Across terminals
**CRITICAL ISSUE**: Terminal 1 creates NEW PLCManager, Terminal 2/3 share singleton

**Test Cases**:
```python
test_terminal1_vs_terminal23_plc_access()
# - Start all 3 terminals simultaneously
# - Verify 2 separate PLC connections created
# - Monitor Modbus TCP connection count
# - Verify no connection errors
# Expected: Both connections work OR document limitations

test_plc_read_write_conflicts()
# - Terminal 1 reading parameters
# - Terminal 3 writing parameters simultaneously
# - Verify no race conditions
# Expected: Reads/writes isolated, no corruption

test_plc_connection_limit_exceeded()
# - Attempt to create 10 PLC connections
# - Verify Modbus TCP connection limit
# Expected: Graceful failure after limit, documented
```

**Estimated Test Duration**: 5 minutes per test

---

### 5.2 Database Contention

**Test Scenario**: Concurrent database access from Terminal 1 and others
**Code Location**: Multiple terminals accessing Supabase

**Test Cases**:
```python
test_concurrent_parameter_metadata_queries()
# - All 3 terminals query component_parameters simultaneously
# - Verify no deadlocks
# - Measure query latency under load
# Expected: All queries succeed, latency < 500ms

test_terminal1_insert_with_terminal3_update()
# - Terminal 1 inserts parameter_value_history
# - Terminal 3 updates parameter_control_commands
# - Different tables - no contention expected
# Expected: Both succeed, no blocking

test_database_connection_pool_exhaustion()
# - All terminals + tests create connections
# - Verify Supabase connection limit
# Expected: Should handle gracefully, document limits
```

**Estimated Test Duration**: 3-5 minutes per test

---

### 5.3 Single Instance Lock Conflicts

**Test Scenario**: Multiple Terminal 1 instances attempt to start
**Code Location**: `plc_data_service.py:42-61` - fcntl lock

**Test Cases**:
```python
test_second_instance_prevented()
# - Start Terminal 1
# - Attempt to start second Terminal 1 instance
# - Verify second instance fails with error
# Expected: Error logged, "Another plc_data_service is already running"

test_lock_file_cleanup_on_crash()
# - Start Terminal 1
# - Kill -9 (no cleanup)
# - Attempt to start new instance
# - Verify stale lock file handling
# Expected: Should detect stale lock or timeout

test_lock_file_cleanup_on_graceful_shutdown()
# - Start Terminal 1
# - Shutdown gracefully
# - Verify lock file deleted
# Expected: Lock file removed via atexit
```

**Estimated Test Duration**: 2 minutes per test

---

## 6. Additional Edge Cases

### 6.1 Signal Handling

**Test Scenario**: SIGINT, SIGTERM, SIGHUP handling
**Code Location**: `plc_data_service.py:502-503` - Signal handlers

**Test Cases**:
```python
test_sigint_handling()
# - Send SIGINT (Ctrl+C)
# - Verify graceful shutdown
# Expected: Clean exit

test_sigterm_handling()
# - Send SIGTERM (systemd stop)
# - Verify graceful shutdown
# Expected: Clean exit

test_signal_during_critical_section()
# - Signal received during database insert
# - Verify operation completes before shutdown
# Expected: No data loss
```

**Estimated Test Duration**: 1 minute per test

---

### 6.2 Environment Configuration

**Test Scenario**: Invalid configuration handling
**Code Location**: `plc_data_service.py:453-465` - apply_env_overrides()

**Test Cases**:
```python
test_invalid_plc_type_env()
# - Set PLC_TYPE="invalid"
# - Verify service logs error, fails to initialize
# Expected: Graceful failure

test_missing_machine_id()
# - Unset MACHINE_ID
# - Verify service behavior
# Expected: Should fail or use default

test_invalid_log_level()
# - Set LOG_LEVEL="INVALID"
# - Verify defaults to INFO
# Expected: Fallback to safe default
```

**Estimated Test Duration**: 1 minute per test

---

## Test Data Requirements

### Parameter Sets

1. **Minimal**: 5 parameters (temperature, pressure, 3 valves)
2. **Standard**: 50 parameters (representative ALD system)
3. **Large**: 100 parameters (stress test)
4. **Extreme**: 1000 parameters (scalability test)

### Database States

1. **Empty**: No parameters in database
2. **Stale**: Parameters exist but metadata outdated
3. **Invalid**: Malformed parameter definitions
4. **Large**: 10,000+ parameter history records

### Network Conditions

1. **Ideal**: 0ms latency, 0% packet loss
2. **Typical**: 10ms latency, 0.1% packet loss
3. **Degraded**: 100ms latency, 1% packet loss
4. **Severe**: 500ms latency, 5% packet loss
5. **Failure**: Network disconnection

---

## Summary of Critical Issues

| Issue | Severity | Code Location | Impact |
|-------|----------|---------------|---------|
| No database write retry logic | CRITICAL | Line 425 | Data loss on transient failures |
| Stale metadata cache | HIGH | Line 271-369 | New parameters never logged |
| No PLC reconnection logic | HIGH | Line 112-116 | Manual restart required |
| Timing violations not handled | MEDIUM | Line 216-221 | Indefinite degradation |
| Singleton pattern conflicts | MEDIUM | Terminal 1 vs 2/3 | Undocumented behavior |
| No circuit breaker | MEDIUM | Service-wide | No failure isolation |
| No batch size validation | LOW | Line 415 | May exceed Supabase limits |

---

## Estimated Total Test Duration

- **Unit Tests**: ~50 tests × 2 min = 100 minutes
- **Integration Tests**: ~20 tests × 5 min = 100 minutes
- **Stress Tests**: ~5 tests × 30 min = 150 minutes
- **Long-Running Tests**: 1 test × 24 hr = 1440 minutes

**Total**: ~31 hours (can run some tests in parallel)

---

## Recommendations

1. **Implement retry logic** for database writes with exponential backoff
2. **Add PLC connection health monitoring** with auto-reconnect
3. **Implement metadata cache refresh** mechanism (every 5 minutes)
4. **Add circuit breaker** for timing violations (degraded mode after 10 consecutive violations)
5. **Document PLC connection model** (Terminal 1 vs Terminal 2/3 singleton behavior)
6. **Add transaction support** or change-data-capture for database writes
7. **Implement batch size validation** and chunking for large parameter sets
8. **Add dead letter queue** for failed database inserts

---

**End of Document**
