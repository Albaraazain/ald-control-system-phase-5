# Cross-Terminal Integration Test Requirements

**Investigation Date**: 2025-10-10
**System**: ALD Control System - 3-Terminal Architecture
**Purpose**: Comprehensive integration test scenarios for multi-terminal operation

## Executive Summary

The ALD control system uses a **3-terminal architecture** where each terminal operates as an independent process with direct PLC access. This investigation identifies critical integration scenarios, failure modes, and testing requirements for multi-terminal operations.

**CRITICAL FINDING**: Terminal 1 creates a NEW PLCManager instance while Terminals 2 & 3 share a global singleton, resulting in 2 separate PLC connections when all terminals run simultaneously.

---

## 1. Multi-Terminal Concurrent Operation Scenarios

### 1.1 Normal Operation - All 3 Terminals Running

**Test Scenario**: `test_all_terminals_concurrent_operation()`

**Setup**:
- Start all 3 terminals simultaneously
- Each terminal in separate process using asyncio.run()
- Shared PLC simulation backend
- Shared Supabase database

**Expected Behavior**:
- Terminal 1 collects PLC data every 1 second
- Terminal 2 polls recipe_commands every 2 seconds
- Terminal 3 polls parameter_control_commands every 1-10 seconds + realtime
- All terminals can read/write PLC simultaneously
- Database writes from all terminals succeed
- No connection pool exhaustion

**Failure Modes to Test**:
- PLC connection storms during simultaneous initialization
- Database connection pool exhaustion (Supabase limits unknown)
- Race conditions on machine_state table updates (Terminal 2 & 3 both write)
- component_parameters table query contention (all terminals read on startup)

**Success Criteria**:
- All terminals report healthy status
- Terminal 1 maintains 1Hz ±100ms timing precision
- Recipe execution completes successfully
- Parameter commands execute within timeout
- No database write failures
- No PLC connection errors

---

### 1.2 Sequential Startup

**Test Scenarios**:
1. `test_terminal_startup_sequence_1_2_3()`
2. `test_terminal_startup_sequence_3_2_1()`
3. `test_terminal_startup_staggered(delay=5s)`

**Purpose**: Validate startup order independence

**Expected Behavior**:
- Each terminal acquires fcntl lock on `/tmp/*_service.lock`
- PLC connections established independently:
  - Terminal 1: NEW PLCManager() instance
  - Terminal 2 & 3: Shared plc_manager singleton
- Database metadata loaded independently
- No startup coordination required

**Failure Modes**:
- fcntl lock conflicts (duplicate terminal detection)
- PLC initialization failures propagate
- Database metadata cache mismatches between terminals
- Environment variable configuration conflicts

---

### 1.3 Terminal Shutdown Sequences

**Test Scenarios**:
1. `test_graceful_shutdown_all_terminals()`
2. `test_single_terminal_crash_while_others_run()`
3. `test_rapid_restart_terminal_1()`

**Graceful Shutdown**:
- SIGINT/SIGTERM handlers trigger cleanup
- fcntl locks released via atexit
- PLC connections disconnected
- Asyncio tasks cancelled
- No orphaned processes

**Abrupt Failure (Terminal Crash)**:
- Other terminals UNAWARE of crash (no IPC)
- fcntl lock persists until process kill detected
- Database state potentially inconsistent
- PLC connection left open (garbage collected eventually)

**Critical Issue**: No cross-terminal health monitoring

---

## 2. PLC Access Contention Scenarios

### 2.1 PLC Connection Architecture

**CRITICAL FINDING**:
- **Terminal 1**: Creates NEW `PLCManager()` instance (plc_data_service.py:73)
- **Terminal 2**: Uses global `plc_manager` singleton (simple_recipe_service.py:35)
- **Terminal 3**: Uses global `plc_manager` singleton (parameter_service.py:32)

**Result**: 2 separate PLC connections when all terminals running

### 2.2 Concurrent PLC Read/Write Scenarios

**Test Scenario**: `test_terminal1_read_terminal3_write_same_param()`

**Setup**:
- Terminal 1 reading all parameters every 1 second
- Terminal 3 writes parameter via command
- Both access same parameter simultaneously

**Expected Behavior** (Simulation PLC):
- Reads and writes are non-blocking (in-memory dict)
- No mutex protection on parameter dict
- Potential race condition on dict access

**Expected Behavior** (Real PLC):
- Modbus TCP protocol handles concurrent access
- PLC firmware may serialize requests
- Network latency affects timing

**Test Variations**:
1. Terminal 1 read + Terminal 2 recipe valve operation
2. Terminal 1 read + Terminal 3 parameter write
3. Terminal 2 recipe execution + Terminal 3 parameter override
4. All 3 terminals accessing PLC simultaneously

**Metrics to Capture**:
- PLC operation latency under contention
- Failed PLC operations count
- Timing precision violations in Terminal 1
- Modbus TCP connection errors

---

### 2.3 PLC Connection Limits

**Test Scenario**: `test_plc_max_concurrent_connections()`

**Investigation Required**:
- Modbus TCP typically allows 1-5 concurrent connections
- pyModbusTCP server limits unknown
- Simulation PLC has no enforced limits (memory-based)

**Test Approach**:
- Create 2-10 PLCManager instances
- Attempt simultaneous connections
- Measure connection failures

**Expected Failure Point**:
- Real Modbus TCP PLC: 2-5 connections
- Simulation PLC: No limit (but performance degrades)

---

## 3. Database Contention Scenarios

### 3.1 Database Access Patterns

| Terminal | Tables Written | Write Pattern | Tables Read | Read Pattern |
|----------|----------------|---------------|-------------|--------------|
| Terminal 1 | parameter_value_history | Batch insert every 1s (all params) | component_parameters, component_definitions | One-time cache load on startup |
| Terminal 2 | process_executions, process_execution_state, machine_state, machines, recipe_commands | Multi-table updates during recipe start/stop | recipes, recipe_steps, recipe_commands | Poll recipe_commands every 2s |
| Terminal 3 | parameter_control_commands | Update executed_at & completed_at | parameter_control_commands, component_parameters_full | Poll every 1-10s + realtime subscription |

### 3.2 Race Condition Scenarios

**Test Scenario**: `test_machine_state_concurrent_update()`

**Setup**:
- Terminal 2 starts recipe (sets machine_state.current_state='running')
- Terminal 3 processes parameter command (may update machine_state)
- Both terminals update simultaneously

**Problem**:
- No distributed locking on database
- Supabase uses eventual consistency
- Last write wins (no conflict resolution)

**Expected Issues**:
- Lost updates (one terminal's write overwritten)
- Inconsistent machine state across terminals
- process_id mismatches

**Test Variations**:
1. Concurrent updates to machines table
2. Concurrent updates to machine_state table
3. Concurrent recipe_commands status updates
4. Concurrent parameter_control_commands claiming (executed_at timestamp)

---

### 3.3 Connection Pool Exhaustion

**Test Scenario**: `test_supabase_connection_pool_exhaustion()`

**Current Architecture**:
- Singleton `_supabase_client` via `get_supabase()`
- Singleton `_async_supabase_client` via `create_async_supabase()`
- **NO connection pooling** - each operation creates HTTP request
- 28 files perform database writes

**Test Approach**:
1. All 3 terminals running + load test client
2. Simulate high request rate:
   - Terminal 1: 100 params/sec batch inserts
   - Terminal 2: Recipe execution with 50 steps
   - Terminal 3: 10 parameter commands/sec
   - Load client: 50 concurrent queries/sec
3. Monitor for connection failures

**Expected Failure Point**:
- Supabase connection limit (unknown - needs research)
- HTTP connection pool exhaustion
- Query timeout failures
- Rate limiting (429 errors)

**Metrics to Capture**:
- Requests/sec when failures start
- Connection timeout errors
- Database query latency percentiles (p50, p95, p99)
- Failed transaction count

---

### 3.4 Realtime Subscription Conflicts

**Test Scenario**: `test_realtime_subscription_limits()`

**Setup**:
- Terminal 3 uses async Supabase realtime subscription
- Multiple Terminal 3 instances (if single-instance lock fails)
- Load test with rapid INSERT events

**Investigation Required**:
- Supabase realtime channel limits per connection
- Message throughput limits
- Reconnection storm behavior

**Expected Issues**:
- Channel limit exhaustion
- Message delivery delays under load
- Reconnection storms after network interruption
- Realtime fallback to polling creates DB load

---

## 4. State Consistency Requirements

### 4.1 Parameter Value Consistency

**Requirement**: Parameter values must be eventually consistent across terminals

**Test Scenario**: `test_parameter_value_propagation()`

**Flow**:
1. Terminal 3 writes parameter value via command
2. Measure latency until Terminal 1 reads new value
3. Verify Terminal 2 recipe sees updated value

**Expected Latency**:
- Write to PLC: <100ms
- Terminal 1 read: 0-1000ms (next collection cycle)
- Terminal 2 recipe sees: Immediately (direct PLC read)

**Consistency Issues**:
- Terminal 1 metadata cache never refreshes (parameter definitions)
- No cache invalidation mechanism
- Database writes may lag PLC state

---

### 4.2 Machine State Consistency

**Requirement**: machine_state and machines tables must reflect actual system state

**Test Scenario**: `test_machine_state_consistency_under_load()`

**Flow**:
1. Terminal 2 starts recipe (status='running')
2. Terminal 2 crashes mid-recipe
3. Verify machine_state accurately reflects crash

**Expected Behavior**:
- Machine state becomes stale
- No automatic recovery
- Manual intervention required

**Failure Mode**:
- Terminal 2 crash leaves machine_state='running'
- Terminal 1 & 3 unaware of crash
- Recipe execution stuck
- process_executions table never updated to 'failed'

---

## 5. Failure Propagation Paths

### 5.1 Terminal Failure Impact Matrix

| Failure | Terminal 1 Impact | Terminal 2 Impact | Terminal 3 Impact |
|---------|-------------------|-------------------|-------------------|
| Terminal 1 crash | N/A | None (unaware) | None (unaware) |
| Terminal 2 crash | None (unaware) | N/A | None (unaware) |
| Terminal 3 crash | None (unaware) | None (unaware) | N/A |
| PLC connection lost | Data collection stops, logs errors | Recipe execution fails | Parameter writes fail, retry logic engages |
| Database unavailable | Metadata cache stale, batch inserts fail | Cannot poll commands, cannot update state | Cannot poll commands, realtime fails, falls back to failed polling |
| Realtime service down | No impact | No impact | Falls back to 1s polling |

**KEY FINDING**: Terminal failures do NOT propagate - complete isolation

### 5.2 Cascading Failure Scenarios

**Test Scenario**: `test_database_failure_cascade()`

**Flow**:
1. Supabase becomes unavailable
2. All terminals attempt reconnection
3. Reconnection storms amplify load
4. Service degradation

**Expected Behavior**:
- Terminal 1: Continues reading PLC, batch inserts fail silently
- Terminal 2: Polling fails, no recipe execution possible
- Terminal 3: Realtime fails, polling fails, commands stuck

**No Circuit Breaker**: All terminals retry indefinitely

---

## 6. End-to-End Workflow Testing

### 6.1 Complete Recipe Execution with Data Collection

**Test Scenario**: `test_recipe_execution_with_data_collection()`

**Flow**:
1. Start all 3 terminals
2. Insert recipe command (start_recipe)
3. Terminal 2 detects command, starts recipe
4. Recipe has 10 steps including valve operations and parameter changes
5. Terminal 1 collects data throughout execution (60s)
6. Terminal 3 processes parameter override mid-recipe
7. Recipe completes successfully
8. Verify data collection coverage (no gaps)

**Success Criteria**:
- Recipe completes all 10 steps
- Terminal 1 collected ~60 data points (1Hz × 60s)
- No timing precision violations
- Parameter override applied correctly
- Database state consistent (process_executions, parameter_value_history)
- No PLC connection errors

**Failure Scenarios to Inject**:
- Database timeout during recipe execution
- PLC connection lost mid-recipe
- Terminal 3 crashes during parameter override
- High PLC read latency causing timing violations

---

### 6.2 Multiple Concurrent Recipes

**Test Scenario**: `test_multiple_sequential_recipes()`

**Flow**:
1. Execute Recipe A (30s duration)
2. While Recipe A running, insert Recipe B command
3. Terminal 2 queues Recipe B
4. After Recipe A completes, Recipe B starts
5. Terminal 1 collects data throughout
6. Verify no data gaps during recipe transitions

**Expected Behavior**:
- Recipe B waits for Recipe A completion
- machine_state correctly transitions
- No data loss during transition
- Continuous data recorder properly starts/stops

---

### 6.3 Recovery from Failure Points

**Test Scenarios**:

1. **`test_recovery_terminal1_crash_during_recipe()`**
   - Terminal 1 crashes mid-recipe
   - Terminal 2 continues recipe execution
   - Parameter data lost for crash duration
   - Terminal 1 restart resumes data collection

2. **`test_recovery_terminal2_crash_during_recipe()`**
   - Terminal 2 crashes mid-recipe
   - Machine stuck in 'running' state
   - Manual intervention required
   - Terminal 2 restart requires recipe cancellation

3. **`test_recovery_terminal3_crash_with_pending_commands()`**
   - Terminal 3 crashes with 5 pending parameter commands
   - Commands remain in database (executed_at=NULL)
   - Terminal 3 restart processes pending commands
   - Retry logic correctly resumes

4. **`test_recovery_database_outage()`**
   - Supabase unavailable for 30 seconds
   - All terminals continue PLC operations
   - Database writes queue or fail
   - After recovery, verify data consistency

5. **`test_recovery_plc_connection_lost_all_terminals()`**
   - PLC simulator crashes
   - All terminals detect disconnection
   - Reconnection attempts synchronized or storm?
   - After PLC restart, all terminals reconnect

---

## 7. Test Orchestration Requirements

### 7.1 Multi-Process Test Harness

**Requirements**:
- Launch 3 terminal processes from pytest
- Capture stdout/stderr from each terminal
- Monitor terminal health (process alive, fcntl locks)
- Inject failures (SIGKILL, network interruption, database unavailability)
- Collect metrics from all terminals
- Verify database state consistency

**Implementation Approach**:
```python
@pytest.fixture
async def three_terminals(plc_simulation, supabase_test_db):
    """Launch all 3 terminals as subprocesses"""
    terminal1 = subprocess.Popen([
        sys.executable, "main.py", "--terminal", "1", "--demo"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    terminal2 = subprocess.Popen([
        sys.executable, "main.py", "--terminal", "2", "--demo"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    terminal3 = subprocess.Popen([
        sys.executable, "main.py", "--terminal", "3", "--demo"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for all terminals to be ready (check fcntl locks)
    await wait_for_terminals_ready([terminal1, terminal2, terminal3])

    yield {
        "terminal1": terminal1,
        "terminal2": terminal2,
        "terminal3": terminal3
    }

    # Cleanup
    for term in [terminal1, terminal2, terminal3]:
        term.terminate()
        term.wait(timeout=10)
```

### 7.2 Failure Injection Framework

**Requirements**:
- Network latency injection (tc/netem on Linux)
- Process kill (SIGKILL, SIGTERM)
- Database unavailability simulation (block Supabase URL)
- PLC simulator crash/restart
- Clock skew simulation (timing precision tests)

**Tools**:
- pytest fixtures for subprocess management
- `tc` command for network simulation (requires root)
- `iptables` for connection blocking
- psutil for process monitoring
- Custom database proxy for controlled failures

---

## 8. Test Execution Strategy

### 8.1 Test Categories

1. **Unit Tests** (existing): Mock-based tests for individual terminal logic
2. **Integration Tests**: Multi-terminal scenarios with real PLC simulation
3. **Stress Tests**: High-load scenarios, connection pool limits
4. **Failure Tests**: Chaos engineering - inject random failures
5. **End-to-End Tests**: Complete workflows with all terminals

### 8.2 Parallel vs Serial Execution

**Serial Tests** (must run sequentially):
- Multi-terminal startup/shutdown tests (fcntl lock conflicts)
- Database stress tests (shared Supabase instance)
- PLC connection limit tests

**Parallel Tests** (can run concurrently):
- Individual terminal unit tests
- Mock-based integration tests
- Read-only database query tests

### 8.3 Test Duration Estimates

| Test Category | Test Count (est) | Duration per Test | Total Duration |
|---------------|------------------|-------------------|----------------|
| Multi-terminal concurrent | 10 | 60-120s | 10-20 min |
| PLC contention | 8 | 30-60s | 4-8 min |
| Database contention | 12 | 30-90s | 6-18 min |
| State consistency | 6 | 60-180s | 6-18 min |
| Failure propagation | 10 | 60-120s | 10-20 min |
| End-to-end workflows | 8 | 120-300s | 16-40 min |
| **Total** | **54** | - | **52-124 min** |

**Recommendation**: Run integration tests in CI with 2-hour timeout

---

## 9. Critical Issues Identified

### 9.1 CRITICAL: Inconsistent PLC Connection Pattern

**Issue**: Terminal 1 creates NEW PLCManager, Terminal 2/3 share singleton

**Impact**:
- 2 separate PLC connections when all terminals running
- Modbus TCP connection limit may be exceeded
- Inconsistent PLC state visibility

**Recommendation**: Enforce consistent singleton pattern OR implement connection pool

### 9.2 WARNING: No Terminal Health Monitoring

**Issue**: Terminal crashes are invisible to other terminals

**Impact**:
- Stale database state (machine_state='running' after crash)
- No automatic recovery
- Manual intervention required

**Recommendation**: Implement health check mechanism (database heartbeat table)

### 9.3 WARNING: No Database Connection Pooling

**Issue**: Singleton Supabase client, no pooling, 28 write locations

**Impact**:
- Connection exhaustion under load
- No automatic retry/backoff
- Rate limiting failures (429 errors)

**Recommendation**: Implement connection pool with retry logic

### 9.4 INFO: No Distributed Locking

**Issue**: Concurrent updates to machine_state and machines tables

**Impact**:
- Lost updates (last write wins)
- State inconsistencies

**Recommendation**: Implement optimistic locking or Supabase RLS policies

---

## 10. Test Implementation Priorities

### Priority 1 (Immediate):
1. `test_all_terminals_concurrent_operation()` - Validate basic multi-terminal functionality
2. `test_terminal1_read_terminal3_write_same_param()` - PLC contention baseline
3. `test_machine_state_concurrent_update()` - Database race condition
4. `test_recipe_execution_with_data_collection()` - End-to-end workflow

### Priority 2 (Next Sprint):
5. Terminal failure/recovery tests
6. Database connection pool exhaustion
7. PLC connection limit testing
8. Realtime subscription stress tests

### Priority 3 (Long-term):
9. Long-running stability tests (24hr+)
10. Chaos engineering framework
11. Performance benchmarking suite
12. Memory leak detection

---

## 11. Success Metrics

**Integration Test Coverage Goals**:
- ✅ All terminal startup combinations tested
- ✅ All PLC contention scenarios covered
- ✅ All database race conditions identified
- ✅ All failure propagation paths validated
- ✅ End-to-end workflows passing consistently

**Performance Benchmarks**:
- Terminal 1 timing precision: 95th percentile < 100ms violation
- Recipe execution success rate: >99% under normal load
- Parameter command latency: <500ms average
- Database write success rate: >99.9%
- PLC operation success rate: >99.9%

**System Reliability**:
- MTBF (Mean Time Between Failures): >168 hours (1 week)
- MTTR (Mean Time To Recovery): <5 minutes for common failures
- Data loss tolerance: <1% under catastrophic failure

---

## Conclusion

The 3-terminal architecture provides **simplicity** and **debugging ease** but introduces **integration complexity** due to terminal independence. Comprehensive integration testing is critical to validate multi-terminal operation, identify race conditions, and ensure system reliability.

**Key Recommendations**:
1. Fix PLC connection pattern inconsistency (Priority 1)
2. Implement health monitoring across terminals (Priority 2)
3. Add database connection pooling and retry logic (Priority 2)
4. Create multi-process test harness for integration tests (Priority 1)
5. Establish performance benchmarks and SLIs (Priority 3)

**Next Steps**:
- Review findings with development team
- Prioritize critical issue fixes
- Implement Priority 1 integration tests
- Establish CI pipeline for integration test execution
