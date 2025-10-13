# Infrastructure Stress Testing Requirements

**Document Version:** 1.0
**Last Updated:** 2025-10-10
**Author:** Infrastructure Stress Testing Investigation Agent

## Executive Summary

This document defines comprehensive stress testing requirements for the ALD Control System's infrastructure components: database (Supabase), PLC simulation, and supporting infrastructure. Analysis reveals critical gaps in connection pooling, resource limits enforcement, and long-running stability validation.

**Critical Findings:**
- No database connection pooling - singleton pattern creates bottleneck
- PLC simulation has no connection limits or TCP constraints
- Background database writes use `asyncio.create_task()` - exceptions lost silently
- No long-running stability tests (24hr+) exist
- Existing network stress tests cover latency but not resource exhaustion

## 1. Database Stress Test Scenarios

### 1.1 High-Frequency Write Testing

**Objective:** Validate Terminal 1's 1Hz parameter logging under extreme load conditions.

#### Test Scenarios

| Test ID | Scenario | Parameter Count | Target Rate | Duration | Success Criteria |
|---------|----------|----------------|-------------|----------|------------------|
| DB-HF-01 | Baseline Performance | 10 params | 1 Hz | 5 min | <100ms jitter, 0 failures |
| DB-HF-02 | Medium Scale | 50 params | 1 Hz | 10 min | <100ms jitter, <1% failures |
| DB-HF-03 | Large Scale | 100 params | 1 Hz | 10 min | <150ms jitter, <5% failures |
| DB-HF-04 | Extreme Scale | 500 params | 1 Hz | 5 min | Document degradation, <10% failures |
| DB-HF-05 | Overload | 1000 params | 1 Hz | 2 min | Graceful degradation, no crashes |

**Implementation Notes:**
- Monitor `parameter_value_history` table insert latency (p50, p95, p99)
- Track Supabase API response times
- Measure timing violations in Terminal 1 data collection loop
- Record batch insert success/failure rates
- Monitor memory usage during sustained writes

**Expected Behavior:**
- Timing violations should be logged but not crash service
- Failed batch inserts should be tracked in metrics
- No memory leaks during extended operation
- Supabase rate limiting should be detected and handled

**Current Gaps:**
- No retry logic for failed batch inserts
- No dead letter queue for failed data
- Batch size not validated against Supabase limits
- No timeout configuration on `.execute()` calls

### 1.2 Connection Exhaustion Testing

**Objective:** Test behavior when Supabase connection limits are reached.

#### Test Scenarios

| Test ID | Scenario | Concurrent Clients | Operations/sec | Duration | Success Criteria |
|---------|----------|-------------------|----------------|----------|------------------|
| DB-CE-01 | Normal Load | 3 terminals | 10 ops/sec | 5 min | All operations succeed |
| DB-CE-02 | High Load | 3 terminals + 5 tests | 50 ops/sec | 3 min | <5% failures, graceful degradation |
| DB-CE-03 | Connection Storm | 10 simultaneous clients | 100 ops/sec | 1 min | Service remains available |
| DB-CE-04 | Sustained High Load | 3 terminals + 10 tests | 30 ops/sec | 10 min | No connection leaks |

**Implementation Notes:**
- Monitor Supabase connection count via client instrumentation
- Track connection creation/destruction events
- Measure query queue depth
- Record connection timeout errors
- Test both sync (`get_supabase()`) and async (`create_async_supabase()`) clients

**Expected Behavior:**
- Connection reuse through singleton pattern
- Graceful handling when connections unavailable
- No connection leaks after operations complete
- Clear error messages when connection limits hit

**Current Gaps:**
- No connection pooling implementation
- Each operation may create new HTTP request
- No monitoring of active connection count
- No backoff strategy when connections exhausted

### 1.3 Batch Insert Limits

**Objective:** Determine maximum batch size and optimal throughput.

#### Test Scenarios

| Test ID | Batch Size | Frequency | Duration | Measure |
|---------|------------|-----------|----------|---------|
| DB-BI-01 | 10 records | 1 Hz | 5 min | Baseline latency |
| DB-BI-02 | 50 records | 1 Hz | 5 min | Latency increase |
| DB-BI-03 | 100 records | 1 Hz | 5 min | Latency degradation |
| DB-BI-04 | 500 records | 1 Hz | 3 min | Document limits |
| DB-BI-05 | 1000 records | 1 Hz | 1 min | Max batch size |
| DB-BI-06 | 100 records | 10 Hz | 2 min | High frequency stress |

**Measurements:**
- Insert latency (p50, p95, p99)
- Supabase API timeouts
- Partial batch success detection
- Network bandwidth utilization
- Database CPU/memory on Supabase side (if available)

**Expected Findings:**
- Optimal batch size for 1Hz collection
- Maximum batch size before timeout
- Throughput limits (records/second)
- Network bandwidth constraints

**Current Implementation:**
- Terminal 1 performs batch inserts: `plc_data_service.py:370-427`
- Batch size = all parameter values (scales with parameter count)
- No validation of batch size limits
- All-or-nothing insert (no partial success handling)

### 1.4 Query Timeout Testing

**Objective:** Validate behavior under slow database queries.

#### Test Scenarios

| Test ID | Scenario | Injected Latency | Query Type | Success Criteria |
|---------|----------|------------------|------------|------------------|
| DB-QT-01 | Slow Metadata Query | 2 seconds | SELECT component_parameters | Startup completes, timeout logged |
| DB-QT-02 | Slow Polling Query | 5 seconds | Terminal 2/3 polling | Falls back, continues operation |
| DB-QT-03 | Stuck Query | Never returns | Any SELECT | Timeout after configured limit |
| DB-QT-04 | Concurrent Slow Queries | 3 seconds each | Multiple terminals | No cascading failures |

**Implementation Notes:**
- Use database-side query delay injection if available
- Or simulate via network latency (tc netem)
- Monitor query queue buildup
- Test timeout configurations
- Validate graceful degradation

**Current Gaps:**
- No timeout configuration on Supabase client
- Polling queries can stack up if slow
- Metadata cache never refreshes if initial load fails
- No circuit breaker for slow database

### 1.5 Realtime Channel Limits

**Objective:** Test Supabase Realtime subscription limits and behavior.

#### Test Scenarios

| Test ID | Scenario | Channels | Events/sec | Duration | Success Criteria |
|---------|----------|----------|------------|----------|------------------|
| DB-RT-01 | Single Subscription | 1 | 1 event/sec | 5 min | All events received |
| DB-RT-02 | Multiple Terminals | 3 | 10 events/sec | 5 min | No dropped events |
| DB-RT-03 | High Event Rate | 1 | 100 events/sec | 2 min | Document throughput limit |
| DB-RT-04 | Reconnection Storm | 10 rapid connects | N/A | 1 min | All reconnections succeed |
| DB-RT-05 | Sustained Operation | 3 | Variable | 1 hour | No channel disconnections |

**Implementation Notes:**
- Monitor Terminal 3 realtime subscription: `parameter_control_listener.py`
- Test realtime vs polling fallback behavior
- Measure event delivery latency
- Track reconnection attempts and success rate
- Test behavior when realtime unavailable

**Current Implementation:**
- 10-second watchdog timeout on subscription
- Falls back to 1Hz polling if realtime fails
- No monitoring of channel health
- Exceptions in realtime callback create asyncio tasks (may be lost)

## 2. PLC Simulation Stress Test Scenarios

### 2.1 Concurrent Access Testing

**Objective:** Validate thread safety of SimulationPLC under concurrent access.

#### Test Scenarios

| Test ID | Scenario | Concurrent Clients | Operations/sec | Duration | Success Criteria |
|---------|----------|-------------------|----------------|----------|------------------|
| PLC-CA-01 | All 3 Terminals | 3 | 10 reads/sec | 5 min | No race conditions, consistent data |
| PLC-CA-02 | High Concurrency | 10 clients | 50 reads/sec | 3 min | No crashes, values consistent |
| PLC-CA-03 | Mixed Read/Write | 5 readers, 5 writers | 100 ops/sec | 2 min | Write isolation verified |
| PLC-CA-04 | Rapid Connect/Disconnect | 10 clients | 10 cycles/sec | 1 min | No connection leaks |

**Implementation Notes:**
- Test concurrent access to `current_values` dict
- Test concurrent access to `set_values` dict
- Verify value consistency across readers
- Test write isolation (writer A doesn't corrupt writer B)
- Monitor for deadlocks

**Critical Issue:**
- **No mutex protection on shared dictionaries**
- `src/plc/simulation.py:39-44` - Dict access without locks
- Race conditions likely under concurrent writes
- Background DB writes (`asyncio.create_task`) may conflict

### 2.2 Parameter Scale Testing

**Objective:** Test SimulationPLC performance with large parameter sets.

#### Test Scenarios

| Test ID | Parameter Count | Operation | Target Latency | Success Criteria |
|---------|----------------|-----------|----------------|------------------|
| PLC-PS-01 | 100 params | read_all_parameters() | <500ms | Meets Terminal 1 timing |
| PLC-PS-02 | 500 params | read_all_parameters() | <1000ms | Acceptable degradation |
| PLC-PS-03 | 1000 params | read_all_parameters() | <2000ms | Document limits |
| PLC-PS-04 | 100 params | _load_parameters() | <2000ms | Startup acceptable |
| PLC-PS-05 | 500 params | _load_parameters() | <5000ms | Startup completes |

**Measurements:**
- `read_all_parameters()` latency distribution
- Memory usage vs parameter count
- Database query performance during `_load_parameters()`
- Fluctuation calculation overhead

**Current Implementation:**
- No limit on parameter count
- `read_all_parameters()` is O(n) - calls `read_parameter()` for each
- Each `read_parameter()` can trigger DB query if not cached
- Memory grows unbounded with parameters

### 2.3 Background DB Write Failure Detection

**Objective:** Test silent failure detection when background writes fail.

#### Test Scenarios

| Test ID | Scenario | Failure Mode | Duration | Expected Behavior |
|---------|----------|--------------|----------|-------------------|
| PLC-BG-01 | Database Unavailable | Connection refused | 5 min | Detect failures, log errors |
| PLC-BG-02 | Database Timeout | Slow queries | 3 min | Track failure rate |
| PLC-BG-03 | Invalid Data | Foreign key violation | 2 min | Identify problematic writes |
| PLC-BG-04 | Sustained Failures | 100% failure rate | 5 min | Implement backoff/circuit breaker |

**Implementation Notes:**
- Monitor `_update_parameter_set_value()` failures
- Test valve set_value updates during PLC issues
- Verify error logging captures failures
- Test error accumulation and reporting

**Critical Issue:**
- `asyncio.create_task()` loses exceptions (lines 265, 314, 324)
- No tracking of background write success/failure
- No retry mechanism for failed writes
- No circuit breaker when DB consistently fails

### 2.4 Connection Storm Testing

**Objective:** Test rapid PLC initialization/deinitialization cycles.

#### Test Scenarios

| Test ID | Scenario | Cycles | Rate | Success Criteria |
|---------|----------|--------|------|------------------|
| PLC-CS-01 | Normal Restart | 10 | 1/min | All succeed |
| PLC-CS-02 | Rapid Restart | 50 | 1/sec | >90% succeed |
| PLC-CS-03 | Concurrent Init | 10 simultaneous | N/A | No DB deadlock |
| PLC-CS-04 | Failed Init Recovery | 20 (inject failures) | 1/sec | Graceful handling |

**Implementation Notes:**
- Test `initialize()` → `disconnect()` cycles
- Monitor `_load_parameters()` DB query performance
- Test behavior when DB unavailable during init
- Verify cache cleanup between cycles

**Current Behavior:**
- Each `initialize()` queries entire `component_parameters` table
- No connection pooling to DB
- Cache never cleared - stale data accumulates
- Empty parameter list logged as warning, continues

### 2.5 Memory Leak Detection

**Objective:** Validate no memory leaks during 24hr+ operation.

#### Test Scenarios

| Test ID | Scenario | Duration | Operations | Memory Threshold |
|---------|----------|----------|------------|------------------|
| PLC-ML-01 | Continuous Reads | 24 hours | 86,400 reads | <10% growth |
| PLC-ML-02 | Continuous Writes | 24 hours | 86,400 writes | <10% growth |
| PLC-ML-03 | Mixed Operations | 72 hours | 259,200 mixed | <15% growth |
| PLC-ML-04 | Parameter Churn | 12 hours | Add/remove params | Dict cleanup verified |

**Measurements:**
- Python process RSS (resident set size)
- Dictionary sizes (`current_values`, `set_values`, `param_metadata`)
- `non_fluctuating_params` set size
- Background task queue depth

**Risk Areas:**
- Dicts never pruned when parameters removed
- `non_fluctuating_params` set grows indefinitely
- Valve cache never cleared
- Background tasks may accumulate if DB slow

### 2.6 Real PLC vs Simulation Comparison

**Key Differences:**

| Aspect | Real PLC (pyModbusTCP) | SimulationPLC | Stress Test Impact |
|--------|----------------------|---------------|-------------------|
| Connection Limit | ~5 TCP connections | Unlimited | Simulation unrealistic |
| Network Latency | 10-100ms typical | 0ms (dict access) | No latency stress |
| Timeout Enforcement | TCP timeouts apply | No timeouts | No timeout handling tested |
| Connection Pool | Limited by Modbus | Unlimited | Resource exhaustion not tested |
| Bandwidth | ~10 Kbps typical | Memory speed | Throughput limits not tested |

**Recommendation:** Create `RealPLCStressTest` separate from simulation tests to validate actual Modbus TCP constraints.

## 3. Long-Running Stability Test Scenarios

### 3.1 24-Hour Continuous Operation

**Objective:** Validate system stability during 24-hour uninterrupted operation.

#### Test Configuration

```python
Duration: 24 hours
Terminals: All 3 running
Load Profile:
  - Terminal 1: 1 Hz parameter collection (86,400 cycles)
  - Terminal 2: 1 recipe/hour (24 recipes)
  - Terminal 3: 10 parameter commands/hour (240 commands)
Monitoring Interval: 5 minutes
```

**Measurements:**
- Memory usage (RSS) per terminal
- CPU utilization per terminal
- Database connection count
- Timing violations in Terminal 1
- Failed operations count
- Log file sizes
- Disk I/O

**Success Criteria:**
- No crashes or hangs
- Memory growth <20%
- Timing violations <5%
- All operations eventually succeed (allowing retries)
- Log rotation functions correctly

**Failure Scenarios to Inject:**
- Hour 8: Database slow query (5 seconds)
- Hour 12: PLC connection loss (2 minutes)
- Hour 16: Supabase rate limit hit
- Hour 20: Network latency spike (500ms)

### 3.2 72-Hour Soak Test

**Objective:** Detect slow memory leaks and resource exhaustion.

#### Test Configuration

```python
Duration: 72 hours (3 days)
Terminals: All 3 running
Load Profile: Same as 24-hour test
Failure Injection: Random failures every 4 hours
Checkpoints: Every 12 hours
```

**Measurements:**
- Same as 24-hour test
- Resource leak detection (file handles, sockets, threads)
- Database table growth rate
- Log aggregation and rotation
- Performance degradation over time

**Success Criteria:**
- Linear resource growth (no exponential leaks)
- Performance within 10% of hour-1 baseline
- All background tasks complete
- No zombie processes or threads

### 3.3 Memory Leak Detection

**Objective:** Identify and quantify memory leaks.

#### Tools and Techniques

1. **Python `tracemalloc` Integration**
```python
# Add to each terminal's main():
import tracemalloc
tracemalloc.start()
# Snapshot every 1 hour, compare growth
```

2. **`memory_profiler` Decorator on Hot Paths**
```python
@profile
async def collect_and_log_parameters(self):
    # Terminal 1 data collection loop
```

3. **External Monitoring**
- `psutil` for RSS tracking
- `objgraph` for Python object growth
- OS-level monitoring (Activity Monitor, htop)

**Test Scenarios:**

| Test ID | Duration | Focus Area | Leak Detection Method |
|---------|----------|------------|---------------------|
| ML-01 | 6 hours | Terminal 1 data collection | tracemalloc snapshots |
| ML-02 | 6 hours | Terminal 2 recipe execution | objgraph after each recipe |
| ML-03 | 6 hours | Terminal 3 command processing | RSS growth rate |
| ML-04 | 12 hours | All terminals concurrent | Multi-process monitoring |

**Common Leak Sources:**
- Unclosed database connections
- Background asyncio tasks never awaited
- Dict/cache growth without pruning
- Event listeners not unsubscribed
- File handles not closed

### 3.4 Connection Leak Detection

**Objective:** Ensure no connection leaks to PLC or database.

#### Test Scenarios

| Test ID | Component | Duration | Operations | Leak Detection |
|---------|-----------|----------|------------|---------------|
| CL-01 | Supabase Connections | 6 hours | 21,600 queries | Connection count stable |
| CL-02 | PLC Connections | 6 hours | 21,600 reads | No TCP sockets leaked |
| CL-03 | Realtime Channels | 6 hours | 10 reconnects | Channel cleanup verified |
| CL-04 | File Handles | 12 hours | Continuous logging | `lsof` count stable |

**Monitoring Commands:**
```bash
# Monitor open files
lsof -p <PID> | wc -l

# Monitor TCP connections
netstat -an | grep ESTABLISHED | wc -l

# Monitor Python objects
python -c "import gc; print(len(gc.get_objects()))"
```

**Success Criteria:**
- Connection count returns to baseline after operations
- No TCP sockets in CLOSE_WAIT state
- File handle count stable
- Python object count stable

### 3.5 Log File Rotation

**Objective:** Validate log rotation under continuous operation.

#### Test Scenarios

| Test ID | Log Volume | Rotation Policy | Duration | Success Criteria |
|---------|-----------|-----------------|----------|------------------|
| LR-01 | High (DEBUG) | 100MB or daily | 24 hours | No disk full, readable logs |
| LR-02 | Medium (INFO) | Daily | 72 hours | 3 rotated files exist |
| LR-03 | Extreme | 10MB | 6 hours | Rapid rotation stable |
| LR-04 | Multiple Services | 50MB each | 24 hours | Independent rotation |

**Verification:**
- Log files rotated correctly
- No data loss during rotation
- Compressed archives created
- Old logs cleaned up per retention policy
- Disk space monitoring alerts work

**Current Implementation:**
- Enhanced logging: `docs/Enhanced_Logging_Guide.md`
- 10 separate log files (per service)
- No explicit rotation policy configured
- Risk: Logs grow unbounded

### 3.6 Resource Cleanup on Shutdown

**Objective:** Verify graceful shutdown and resource cleanup.

#### Test Scenarios

| Test ID | Shutdown Method | Expected Behavior |
|---------|----------------|-------------------|
| RC-01 | SIGTERM (graceful) | All connections closed, logs flushed, tasks completed |
| RC-02 | SIGINT (Ctrl+C) | Same as SIGTERM |
| RC-03 | SIGKILL (forced) | Cleanup on restart, no corruption |
| RC-04 | Exception-triggered | Exception logged, cleanup attempt made |

**Verification Steps:**
1. Send signal to process
2. Wait for shutdown (max 30 seconds)
3. Verify:
   - PLC connection closed
   - Database connections closed
   - Realtime channels unsubscribed
   - Log files flushed
   - Lock files removed
   - Background tasks cancelled
   - Temporary files cleaned

**Current Implementation:**
- Signal handlers in Terminal 1: `plc_data_service.py:85-105`
- Single instance locks use `fcntl`
- Async cleanup in `__aexit__` methods
- No explicit connection pool cleanup

## 4. Failure Injection Testing

### 4.1 Network Latency Injection

**Existing Implementation:** `tools/debug/test_network_latency_stress.py`

**Enhancement Requirements:**

| Scenario | Current Coverage | Enhancement Needed |
|----------|-----------------|-------------------|
| High Latency (500-5000ms) | ✅ Implemented | Add concurrent terminal testing |
| Packet Loss (5-50%) | ✅ Implemented | Add recovery time measurement |
| Jitter (variable latency) | ✅ Implemented | Add adaptive timing tests |
| Bandwidth Throttling | ✅ Implemented | Add sustained throttling (hours) |

**New Test Scenarios:**

| Test ID | Injection Method | Duration | Terminals Affected | Expected Behavior |
|---------|-----------------|----------|-------------------|-------------------|
| FI-NL-01 | tc netem delay 1000ms | 5 min | All 3 | Timing violations logged, continued operation |
| FI-NL-02 | tc netem loss 20% | 3 min | All 3 | Retries succeed, no data loss |
| FI-NL-03 | Variable latency 100-1000ms | 10 min | Terminal 1 | Adaptive timing compensation |
| FI-NL-04 | Sustained 500ms latency | 1 hour | All 3 | Long-term stability verified |

### 4.2 Database Timeout Injection

**Objective:** Test behavior when database operations timeout.

#### Injection Methods

1. **Query-level timeout simulation:**
```python
# Mock slow query
original_execute = supabase.table().select().execute
def slow_execute(*args, **kwargs):
    await asyncio.sleep(5)  # Simulate slow query
    return original_execute(*args, **kwargs)
```

2. **Connection-level timeout:**
```python
# Set aggressive timeout
supabase_client = create_client(url, key, timeout=1)
```

3. **Network-level delay:**
```bash
# Add latency to Supabase endpoint
tc qdisc add dev eth0 root netem delay 5000ms
```

#### Test Scenarios

| Test ID | Timeout Type | Duration | Expected Behavior |
|---------|-------------|----------|-------------------|
| FI-DT-01 | Query timeout (5s) | 5 min | Timeout logged, operation retried or skipped |
| FI-DT-02 | Connection timeout (1s) | 3 min | New connection attempted, fallback to cached data |
| FI-DT-03 | Batch insert timeout | 2 min | Partial data saved or logged for retry |
| FI-DT-04 | Metadata query timeout | Startup | Startup completes with degraded mode or fails gracefully |

**Success Criteria:**
- Timeouts detected and logged
- Services continue operating (possibly degraded)
- No silent failures
- Circuit breaker engages after repeated timeouts

### 4.3 PLC Response Delay Injection

**Objective:** Test behavior when PLC operations are slow.

#### Injection Methods

1. **Simulation-level delay:**
```python
# In SimulationPLC.read_parameter():
async def read_parameter(self, parameter_id):
    await asyncio.sleep(random.uniform(0.5, 2.0))  # Inject delay
    return self.current_values[parameter_id]
```

2. **Network-level delay (Real PLC):**
```bash
# Delay traffic to PLC IP
tc qdisc add dev eth0 root netem delay 1000ms
```

#### Test Scenarios

| Test ID | PLC Delay | Operations | Expected Behavior |
|---------|-----------|-----------|-------------------|
| FI-PD-01 | 500ms per read | read_all_parameters() | Terminal 1 timing violations, continued operation |
| FI-PD-02 | 2000ms per write | parameter command | Command retried, eventual success |
| FI-PD-03 | Random 100-1000ms | Mixed operations | Adaptive behavior, no crashes |
| FI-PD-04 | Sustained 1000ms | 10 minutes | Long-term degradation measured |

**Current Gaps:**
- No timeout enforcement on PLC operations
- Terminal 1 will drift timing if PLC slow
- No circuit breaker for consistently slow PLC

### 4.4 Random Disconnection Testing

**Objective:** Test resilience to unexpected connection losses.

#### Test Scenarios

| Test ID | Disconnection Type | Frequency | Duration | Expected Behavior |
|---------|-------------------|-----------|----------|-------------------|
| FI-RD-01 | PLC disconnect | 1/hour | 2 minutes | Auto-reconnect, minimal data loss |
| FI-RD-02 | Database disconnect | 1/hour | 5 minutes | Fallback to cached data, retry on reconnect |
| FI-RD-03 | Realtime channel drop | 1/hour | 1 minute | Fall back to polling, no command loss |
| FI-RD-04 | Multiple simultaneous | 1/2 hours | 3 minutes | Coordinated recovery, no cascading failures |

**Injection Methods:**
```python
# Randomly close connections
def inject_disconnections(target_component, rate_per_hour):
    while True:
        await asyncio.sleep(3600 / rate_per_hour)
        await target_component.disconnect()
        logger.info("INJECTED: Disconnection for testing")
```

**Success Criteria:**
- Automatic reconnection within 30 seconds
- No data corruption
- Services degrade gracefully
- Recovery is automatic (no manual intervention)

### 4.5 Partial Failure Scenarios

**Objective:** Test behavior when only some components fail.

#### Test Scenarios

| Test ID | Failing Component | Working Components | Duration | Expected Behavior |
|---------|------------------|-------------------|----------|-------------------|
| FI-PF-01 | PLC only | Database, Terminals | 10 min | Terminals continue, degrade PLC-dependent features |
| FI-PF-02 | Database only | PLC, Terminals | 10 min | Cache-based operation, queue writes for retry |
| FI-PF-03 | Terminal 1 crash | Terminals 2, 3 | 10 min | T2/T3 continue independently |
| FI-PF-04 | Realtime channel | Polling, PLC | 10 min | Fall back to polling immediately |
| FI-PF-05 | 2 of 3 terminals | 1 terminal | 30 min | Single terminal maintains core functionality |

**Verification:**
- Independent terminal operation verified
- No cascading failures
- Partial system functionality maintained
- Recovery when failed components restart

## 5. Performance Benchmarking Requirements

### 5.1 Data Collection Throughput

**Objective:** Establish baseline performance metrics for Terminal 1.

#### Benchmark Tests

| Benchmark ID | Parameter Count | Target | Measurement |
|-------------|----------------|--------|-------------|
| BENCH-DC-01 | 10 params | 1 Hz, <50ms cycle time | Baseline |
| BENCH-DC-02 | 50 params | 1 Hz, <100ms cycle time | Acceptable |
| BENCH-DC-03 | 100 params | 1 Hz, <200ms cycle time | Target |
| BENCH-DC-04 | 500 params | 1 Hz, <500ms cycle time | Maximum |
| BENCH-DC-05 | 100 params | 10 Hz, <100ms cycle time | High frequency |

**Metrics to Capture:**
- PLC read latency (p50, p95, p99)
- Database batch insert latency
- Total cycle time (read + process + write)
- Timing precision (jitter)
- CPU utilization
- Memory usage

**Baseline Establishment:**
- Run each benchmark 10 times
- Calculate mean and standard deviation
- Establish p95 thresholds
- Document on bare-metal and VM environments

### 5.2 Recipe Execution Performance

**Objective:** Establish baseline for Terminal 2 recipe execution.

#### Benchmark Tests

| Benchmark ID | Recipe Complexity | Target Time | Measurement |
|-------------|------------------|-------------|-------------|
| BENCH-RE-01 | 5 steps, no loops | <10 seconds | Simple recipe |
| BENCH-RE-02 | 20 steps, 1 loop (10 iter) | <2 minutes | Medium complexity |
| BENCH-RE-03 | 50 steps, 3 nested loops | <10 minutes | Complex recipe |
| BENCH-RE-04 | 10 valve operations | <30 seconds | I/O intensive |
| BENCH-RE-05 | 100 parameter writes | <1 minute | Parameter intensive |

**Metrics to Capture:**
- Recipe startup time (command received → execution starts)
- Step execution time (by step type)
- Loop overhead
- Database update latency (process_execution_state)
- Total recipe execution time
- Cancellation response time

### 5.3 Parameter Write Latency

**Objective:** Establish baseline for Terminal 3 parameter control.

#### Benchmark Tests

| Benchmark ID | Command Type | Target Latency | Measurement |
|-------------|--------------|----------------|-------------|
| BENCH-PW-01 | Single parameter write | <500ms | E2E latency |
| BENCH-PW-02 | 10 concurrent writes | <2 seconds | Concurrent handling |
| BENCH-PW-03 | Batch of 100 writes | <30 seconds | Throughput |
| BENCH-PW-04 | Write with confirmation | <1 second | Including read-back |

**Latency Breakdown:**
- Command polling/realtime detection: T1
- Command processing and validation: T2
- PLC write operation: T3
- Confirmation read (if enabled): T4
- Database finalization: T5
- **Total E2E latency:** T1 + T2 + T3 + T4 + T5

**Metrics:**
- Command detection latency (inserted → detected)
- Processing time per command
- PLC write latency
- Confirmation read latency
- Database update latency
- Retry attempts and success rate

### 5.4 End-to-End Latency

**Objective:** Measure complete workflow latency across terminals.

#### Benchmark Workflows

| Workflow ID | Description | Components | Target Latency |
|------------|-------------|------------|----------------|
| E2E-01 | Parameter command → PLC write → data logged | T3 → PLC → T1 → DB | <5 seconds |
| E2E-02 | Recipe start → first step → logged | T2 → Recipe executor → T1 | <10 seconds |
| E2E-03 | Recipe start → completion → final log | T2 → Full recipe → T1 | <5 minutes (for 2-minute recipe) |
| E2E-04 | External API → parameter write → confirmation | API → T3 → PLC → T1 | <10 seconds |

**Tracing Implementation:**
```python
# Add trace IDs to commands
trace_id = str(uuid.uuid4())
command = {
    'id': command_id,
    'trace_id': trace_id,
    'timestamp_created': time.time()
}

# Log at each stage
logger.info(f"TRACE:{trace_id} stage=command_created ts={ts}")
logger.info(f"TRACE:{trace_id} stage=command_detected ts={ts}")
logger.info(f"TRACE:{trace_id} stage=plc_write_start ts={ts}")
# ... etc
```

**Analysis:**
- Extract trace logs
- Calculate stage latencies
- Identify bottlenecks
- Generate latency distribution charts

### 5.5 Resource Utilization Profiling

**Objective:** Profile CPU, memory, I/O usage under various loads.

#### Profiling Scenarios

| Profile ID | Load Level | Duration | Measurement Focus |
|-----------|-----------|----------|-------------------|
| PROF-01 | Idle (no operations) | 1 hour | Baseline resource usage |
| PROF-02 | Light (10 params, 1 recipe/hr) | 1 hour | Minimal load |
| PROF-03 | Normal (100 params, 1 recipe/hr, 10 cmds/hr) | 4 hours | Target load |
| PROF-04 | Heavy (500 params, 1 recipe/10min, 100 cmds/hr) | 2 hours | Peak load |
| PROF-05 | Extreme (1000 params, continuous recipes, 1000 cmds/hr) | 30 min | Stress load |

**Tools:**
1. **Python cProfile:**
```bash
python -m cProfile -o profile.stats main.py
# Analyze with snakeviz
snakeviz profile.stats
```

2. **py-spy (sampling profiler):**
```bash
py-spy record -o profile.svg -- python main.py
```

3. **memory_profiler:**
```bash
python -m memory_profiler main.py
```

4. **External monitoring:**
```bash
# psutil-based monitoring
python tools/monitor_resources.py --pid <PID> --interval 5
```

**Metrics to Collect:**
- CPU usage (per terminal, per thread)
- Memory usage (RSS, heap, stack)
- Disk I/O (reads/writes, bytes)
- Network I/O (packets, bytes)
- Context switches
- System calls
- GC statistics (collections, pause time)

## 6. Known Supabase Limits (Research Required)

**This section requires research and testing to populate:**

### 6.1 API Rate Limits

| Limit Type | Free Tier | Pro Tier | Enterprise |
|-----------|-----------|----------|-----------|
| Requests/sec | **TBD** | **TBD** | **TBD** |
| Requests/day | **TBD** | **TBD** | Unlimited |
| Concurrent connections | **TBD** | **TBD** | **TBD** |

**Testing Approach:**
```python
# Gradually increase request rate until 429 (Too Many Requests) received
for rate in [10, 50, 100, 500, 1000]:
    result = await test_rate_limit(requests_per_sec=rate)
    if result.status_code == 429:
        logger.info(f"Rate limit hit at {rate} req/sec")
        break
```

### 6.2 Connection Limits

| Connection Type | Limit | Notes |
|----------------|-------|-------|
| Concurrent HTTP connections | **TBD** | Test with connection pool |
| Realtime channels per client | **TBD** | Test with multiple subscriptions |
| Realtime clients per project | **TBD** | Test with multiple terminals |

### 6.3 Batch Operation Limits

| Operation | Max Batch Size | Notes |
|-----------|---------------|-------|
| INSERT (batch) | **TBD** | Test with parameter_value_history |
| SELECT (limit) | **TBD** | Test with large result sets |
| UPDATE (batch) | **TBD** | Test with multiple updates |

### 6.4 Query Timeout Defaults

| Query Type | Default Timeout | Configurable? |
|-----------|----------------|--------------|
| SELECT | **TBD** | **TBD** |
| INSERT | **TBD** | **TBD** |
| UPDATE | **TBD** | **TBD** |
| Realtime subscription | 10s (code-configured) | Yes |

### 6.5 Realtime Channel Limits

| Limit Type | Value | Notes |
|-----------|-------|-------|
| Channels per client | **TBD** | Current: 1 per terminal |
| Events per second | **TBD** | Test with high command volume |
| Message size | **TBD** | Test with large command payloads |
| Reconnection throttling | **TBD** | Test rapid reconnects |

**Research Actions:**
1. Consult Supabase documentation
2. Contact Supabase support for tier limits
3. Empirical testing to determine practical limits
4. Document findings in `docs/supabase_limits.md`

## 7. Modbus Protocol Stress Limits (Research Required)

**This section requires research and testing with real PLC hardware:**

### 7.1 Modbus TCP Connection Limits

| Limit Type | Typical Value | Notes |
|-----------|--------------|-------|
| Concurrent TCP connections | ~5 | Depends on PLC model |
| Max registers per read | 125 | Modbus protocol limit |
| Max coils per read | 2000 | Modbus protocol limit |
| Max registers per write | 123 | Modbus protocol limit |
| Max coils per write | 1968 | Modbus protocol limit |

### 7.2 Modbus TCP Throughput

| Metric | Typical Value | Notes |
|--------|--------------|-------|
| Reads per second | 10-100 | Depends on network latency |
| Writes per second | 10-50 | Slower than reads |
| Bandwidth | ~10 Kbps | Low bandwidth protocol |
| Latency | 10-100ms | Network + PLC processing |

### 7.3 Testing Approach with Real PLC

```python
# Test concurrent connection limit
async def test_plc_connection_limit():
    connections = []
    for i in range(20):  # Try up to 20 connections
        try:
            plc = RealPLC(host="192.168.1.10", port=502)
            success = await plc.initialize()
            if success:
                connections.append(plc)
                logger.info(f"Connection {i+1} succeeded")
            else:
                logger.info(f"Connection limit reached at {i}")
                break
        except Exception as e:
            logger.error(f"Connection {i+1} failed: {e}")
            break
    return len(connections)
```

**Research Actions:**
1. Test with actual PLC hardware
2. Document PLC model and firmware version
3. Measure real-world limits
4. Compare with simulation behavior
5. Update tests to match real PLC constraints

## 8. Test Infrastructure Requirements

### 8.1 Test Environment Setup

**Required Infrastructure:**

1. **Database Setup:**
   - Dedicated Supabase test project
   - Test data seeding scripts
   - Automated teardown/cleanup
   - Isolated from production

2. **PLC Simulation:**
   - Enhanced SimulationPLC with configurable limits
   - Failure injection hooks
   - Performance monitoring
   - Concurrent access support

3. **Load Generation:**
   - Configurable load generators per terminal
   - Coordinated multi-terminal testing
   - Metrics collection and aggregation
   - Real-time monitoring dashboard

4. **Monitoring Stack:**
   - Prometheus + Grafana (optional but recommended)
   - Custom metrics exporter
   - Log aggregation (Loki or ELK)
   - Alert manager for threshold breaches

### 8.2 Test Execution Framework

**Directory Structure:**
```
tests/
├── stress/
│   ├── database/
│   │   ├── test_high_frequency_writes.py
│   │   ├── test_connection_exhaustion.py
│   │   ├── test_batch_limits.py
│   │   ├── test_query_timeouts.py
│   │   └── test_realtime_channels.py
│   ├── plc_simulation/
│   │   ├── test_concurrent_access.py
│   │   ├── test_parameter_scale.py
│   │   ├── test_background_failures.py
│   │   ├── test_connection_storm.py
│   │   └── test_memory_leaks.py
│   ├── stability/
│   │   ├── test_24hour_operation.py
│   │   ├── test_72hour_soak.py
│   │   ├── test_memory_leak_detection.py
│   │   ├── test_connection_leak_detection.py
│   │   └── test_log_rotation.py
│   ├── failure_injection/
│   │   ├── test_network_latency.py  # Enhance existing
│   │   ├── test_database_timeout.py
│   │   ├── test_plc_delay.py
│   │   ├── test_random_disconnection.py
│   │   └── test_partial_failures.py
│   └── benchmarks/
│       ├── test_data_collection_throughput.py
│       ├── test_recipe_execution_performance.py
│       ├── test_parameter_write_latency.py
│       ├── test_e2e_latency.py
│       └── test_resource_utilization.py
```

**Test Markers:**
```python
# pytest markers for stress tests
@pytest.mark.stress
@pytest.mark.stress_database
@pytest.mark.stress_plc
@pytest.mark.stability
@pytest.mark.benchmark
@pytest.mark.slow  # >10 minutes
@pytest.mark.very_slow  # >1 hour
@pytest.mark.requires_root  # For tc netem
@pytest.mark.requires_real_plc  # For hardware tests
```

**Execution Commands:**
```bash
# Run all stress tests (fast ones only)
pytest tests/stress -m "stress and not slow"

# Run 24-hour stability test
pytest tests/stress/stability/test_24hour_operation.py -v

# Run database stress tests only
pytest tests/stress/database/ -v

# Run benchmarks and generate report
pytest tests/stress/benchmarks/ --benchmark-only --benchmark-autosave

# Run with coverage
pytest tests/stress --cov=src --cov-report=html
```

### 8.3 Metrics Collection

**Prometheus Metrics to Export:**

```python
# Terminal 1 metrics
terminal1_collection_duration_seconds = Histogram(...)
terminal1_timing_violations_total = Counter(...)
terminal1_parameters_collected_total = Counter(...)
terminal1_batch_insert_duration_seconds = Histogram(...)
terminal1_batch_insert_failures_total = Counter(...)

# Terminal 2 metrics
terminal2_recipe_execution_duration_seconds = Histogram(...)
terminal2_step_execution_duration_seconds = Histogram(...)
terminal2_recipe_failures_total = Counter(...)

# Terminal 3 metrics
terminal3_command_detection_latency_seconds = Histogram(...)
terminal3_plc_write_duration_seconds = Histogram(...)
terminal3_command_failures_total = Counter(...)

# Infrastructure metrics
database_query_duration_seconds = Histogram(...)
database_connection_pool_size = Gauge(...)
plc_read_duration_seconds = Histogram(...)
plc_write_duration_seconds = Histogram(...)
```

### 8.4 Expected Thresholds

**Performance Thresholds (to be refined after benchmarking):**

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| Terminal 1 cycle time | >100ms | >150ms |
| Terminal 1 timing violations | >5% | >10% |
| Batch insert latency (p95) | >300ms | >500ms |
| Parameter write latency (E2E) | >1s | >2s |
| Recipe execution overhead | >10% | >20% |
| Memory growth rate | >5% per hour | >10% per hour |
| Connection count growth | >10% per hour | >20% per hour |
| Failed operation rate | >1% | >5% |

**Alert Rules:**
```yaml
# Example Prometheus alert rules
groups:
  - name: ald_control_system_alerts
    rules:
      - alert: HighTimingViolationRate
        expr: rate(terminal1_timing_violations_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Terminal 1 timing violations exceeding 5%"

      - alert: DatabaseInsertFailureSpike
        expr: rate(terminal1_batch_insert_failures_total[1m]) > 0.1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database insert failures spiking"

      - alert: MemoryLeakDetected
        expr: rate(process_resident_memory_bytes[1h]) > 10485760  # 10MB/hr
        for: 6h
        labels:
          severity: warning
        annotations:
          summary: "Potential memory leak detected"
```

## 9. Monitoring Requirements

### 9.1 Real-Time Monitoring

**Dashboard Panels:**

1. **Terminal 1 Dashboard:**
   - Current collection rate (Hz)
   - Cycle time distribution (p50, p95, p99)
   - Timing violations per hour
   - Parameters collected per cycle
   - Batch insert success rate
   - Batch insert latency

2. **Terminal 2 Dashboard:**
   - Active recipes count
   - Recipe execution time distribution
   - Step execution time by type
   - Recipe failure rate
   - Database update latency

3. **Terminal 3 Dashboard:**
   - Command queue depth
   - Command detection latency
   - PLC write latency
   - Command success rate
   - Retry attempts distribution

4. **Infrastructure Dashboard:**
   - CPU usage per terminal
   - Memory usage per terminal
   - Database connection count
   - PLC connection status
   - Network I/O
   - Disk I/O
   - Log file sizes

### 9.2 Historical Trending

**Metrics to Track Over Time:**
- Performance degradation (compare week-over-week)
- Resource utilization trends
- Error rate trends
- Capacity planning projections

**Retention Policies:**
- Raw metrics: 7 days
- 5-minute aggregates: 30 days
- 1-hour aggregates: 1 year
- Daily summaries: Indefinite

## 10. Success Criteria Summary

### 10.1 Database Stress Tests

- ✅ Terminal 1 maintains 1Hz collection rate with 100 parameters (<5% timing violations)
- ✅ System handles 3 terminals + 10 test clients without connection exhaustion
- ✅ Batch inserts up to 500 records succeed within 1 second (p95)
- ✅ Slow queries timeout gracefully and fall back to cached data
- ✅ Realtime channels handle 100 events/sec without message loss

### 10.2 PLC Simulation Stress Tests

- ✅ Concurrent access from 10 clients shows no race conditions
- ✅ 500 parameters loaded and read in <1 second
- ✅ Background DB write failures are detected and logged
- ✅ 50 rapid init/disconnect cycles complete without DB deadlock
- ✅ 24-hour operation shows <10% memory growth

### 10.3 Long-Running Stability Tests

- ✅ 24-hour operation completes without crashes
- ✅ 72-hour soak test shows linear (not exponential) resource growth
- ✅ No memory leaks detected via tracemalloc
- ✅ No connection leaks detected via lsof/netstat
- ✅ Log rotation functions correctly under continuous operation

### 10.4 Failure Injection Tests

- ✅ 1000ms network latency: system continues with timing violations logged
- ✅ Database timeout: falls back to cached data, recovers on reconnect
- ✅ PLC slow response: retries succeed, no crashes
- ✅ Random disconnections: auto-reconnect within 30 seconds
- ✅ Partial failures: unaffected components continue operating

### 10.5 Performance Benchmarks

- ✅ Terminal 1: 100 params at 1Hz with <200ms cycle time (p95)
- ✅ Terminal 2: 20-step recipe completes in <2 minutes
- ✅ Terminal 3: Parameter write E2E latency <1 second (p95)
- ✅ E2E workflow latency <10 seconds (parameter command → logged)
- ✅ CPU usage <50% under normal load
- ✅ Memory usage stable (<10% growth per 24 hours)

## 11. References and Related Documents

### Internal Documentation
- `test_design/terminal1_test_requirements.md` - Terminal 1 edge cases
- `test_design/terminal2_test_requirements.md` - Terminal 2 edge cases
- `test_design/terminal3_test_requirements.md` - Terminal 3 edge cases
- `test_design/integration_test_requirements.md` - Cross-terminal integration
- `test_design/test_framework_architecture.md` - Overall test framework
- `docs/Enhanced_Logging_Guide.md` - Service-specific logging
- `docs/Log_Troubleshooting_Guide.md` - Debug patterns

### Existing Test Files
- `tools/debug/test_network_latency_stress.py` - Network stress testing
- `src/data_collection/performance_monitor.py` - Performance monitoring infrastructure
- `tests/conftest.py` - Test fixtures and utilities
- `tests/integration/` - Integration test examples

### External Resources
- Supabase Documentation: https://supabase.com/docs
- Modbus Protocol Specification: https://modbus.org/specs.php
- pytest Documentation: https://docs.pytest.org
- pytest-asyncio: https://github.com/pytest-dev/pytest-asyncio
- Prometheus Python Client: https://github.com/prometheus/client_python

## 12. Next Steps and Implementation Priorities

### Phase 1: Critical Infrastructure (Week 1-2)
1. Implement connection pooling for Supabase (if possible)
2. Add timeout configuration to all database operations
3. Fix background DB write exception handling (`asyncio.create_task` → proper error handling)
4. Add mutex protection to SimulationPLC shared dictionaries
5. Implement basic stress test framework structure

### Phase 2: Database Stress Tests (Week 3-4)
1. Implement high-frequency write tests (DB-HF series)
2. Implement connection exhaustion tests (DB-CE series)
3. Implement batch insert limit tests (DB-BI series)
4. Add basic monitoring and metrics collection

### Phase 3: PLC and Stability Tests (Week 5-6)
1. Implement PLC concurrent access tests (PLC-CA series)
2. Implement parameter scale tests (PLC-PS series)
3. Implement 24-hour stability test
4. Add memory leak detection tooling

### Phase 4: Failure Injection (Week 7-8)
1. Enhance existing network latency tests
2. Implement database timeout injection
3. Implement PLC delay injection
4. Implement random disconnection testing

### Phase 5: Benchmarking and Documentation (Week 9-10)
1. Establish performance baselines
2. Run full benchmark suite
3. Document thresholds and expectations
4. Create monitoring dashboards
5. Generate comprehensive test report

---

**Document Status:** COMPLETE
**Implementation Status:** NOT STARTED
**Priority:** HIGH - Critical infrastructure gaps identified
