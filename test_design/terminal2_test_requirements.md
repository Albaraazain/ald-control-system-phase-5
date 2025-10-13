# Terminal 2 (Recipe Service) - Comprehensive Test Requirements

**Investigation Date**: 2025-10-10
**Service**: `simple_recipe_service.py` (Recipe Command Processing and Execution)
**Architecture**: Standalone polling service with direct PLC access

---

## Executive Summary

Terminal 2 (Recipe Service) is responsible for:
1. Polling `recipe_commands` table for pending/queued commands
2. Executing recipes via direct PLC access using existing recipe_flow/step_flow components
3. Managing process execution state and machine status transitions
4. Coordinating continuous data recording during recipe execution

**Testing Complexity**: HIGH - Recipe execution involves multi-table database coordination, PLC operations, loop iteration, cancellation handling, and state machine transitions.

---

## 1. Recipe Command Processing Edge Cases

### 1.1 Command Polling and Detection

**Code Location**: `simple_recipe_service.py:85-111`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-RCP-001** No pending commands | Empty `recipe_commands` table | Return None, continue polling | N/A |
| **TC-RCP-002** Single pending command | 1 command with `status='pending'` | Return command dict | N/A |
| **TC-RCP-003** Multiple pending commands | 5 commands with different timestamps | Return oldest command (earliest `created_at`) | Returns newest instead of oldest |
| **TC-RCP-004** Queued vs pending commands | Commands with `status='queued'` and `status='pending'` | Both are detected (IN query) | Only pending or only queued detected |
| **TC-RCP-005** Global command (NULL machine_id) | Command with `machine_id=NULL` | Global command detected | Global command ignored |
| **TC-RCP-006** Machine-specific command | Command with `machine_id=MACHINE_ID` | Machine-specific command detected | N/A |
| **TC-RCP-007** Other machine's command | Command with `machine_id='OTHER_MACHINE'` | Command ignored | Wrong machine's command executed |
| **TC-RCP-008** Database query failure | Supabase connection error | Log error, return None, retry after 5s | Service crashes |
| **TC-RCP-009** Database timeout | Query takes >30s | Timeout exception, return None | Hangs indefinitely |
| **TC-RCP-010** Malformed command data | Command missing required fields | Handled gracefully in execution phase | Exception during polling |

### 1.2 Command Execution State Transitions

**Code Location**: `simple_recipe_service.py:112-172`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-RCE-001** Start recipe command | `type='start_recipe'`, valid `recipe_id` | Command marked `executing`, then `completed` | N/A |
| **TC-RCE-002** Stop recipe command | `type='stop_recipe'` | Stop current recipe, mark `completed` | N/A |
| **TC-RCE-003** Unknown command type | `type='invalid_type'` | Mark command as `failed` with error | Command marked `completed` |
| **TC-RCE-004** Command status update race | Two services try to execute same command | Only one succeeds (database atomicity) | Both execute recipe |
| **TC-RCE-005** Executed_at already set | Command has `executed_at` timestamp | Skip command (already claimed) | Execute duplicate |
| **TC-RCE-006** Database update failure during status change | Supabase fails to update `status='executing'` | Exception logged, command marked `failed` | Silent failure |
| **TC-RCE-007** Exception during recipe execution | Recipe execution raises exception | Command marked `failed` with `error_message` | Exception propagates uncaught |
| **TC-RCE-008** Partial command completion | Recipe starts but fails mid-way | Command marked `failed`, process marked `failed` | Command stuck in `executing` |

### 1.3 Command Type Routing

**Code Location**: `simple_recipe_service.py:131-142`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-RCR-001** Missing type field | Command dict without `type` key | Default to `'start_recipe'` (line 116) | Exception |
| **TC-RCR-002** NULL type value | `type=NULL` | Default to `'start_recipe'` | Exception |
| **TC-RCR-003** Empty string type | `type=''` | Treated as unknown, marked failed | Crashes |
| **TC-RCR-004** Case sensitivity | `type='START_RECIPE'` (uppercase) | Converted to lowercase (line 116) | Not matched |
| **TC-RCR-005** Whitespace in type | `type=' start_recipe '` | May not match due to whitespace | Match fails |

---

## 2. Recipe Execution Edge Cases

### 2.1 Recipe Loading and Validation

**Code Location**: `simple_recipe_service.py:173-204`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-REL-001** Missing recipe_id in parameters | Command parameters without `recipe_id` | Return False, log error (line 183) | Exception |
| **TC-REL-002** Recipe_id is NULL | `parameters={'recipe_id': NULL}` | Return False, log error | Exception |
| **TC-REL-003** Recipe not found in database | `recipe_id` doesn't exist in `recipes` table | Return False, log error (line 193) | Exception |
| **TC-REL-004** Recipe with empty result | Query returns empty array | Return False, log error | IndexError |
| **TC-REL-005** Recipe missing version field | Recipe dict without `version` key | Still proceeds (version access doesn't fail) | May cause issues downstream |
| **TC-REL-006** Recipe with NULL version | `recipe['version'] = NULL` | Logs "version: unknown" (line 197) | N/A |
| **TC-REL-007** Recipe steps query failure | Database error fetching `recipe_steps` | Exception raised, recipe fails | Silent failure |
| **TC-REL-008** Recipe with zero steps | `recipe_steps = []` | Proceeds but completes immediately | Division by zero in progress |
| **TC-REL-009** Recipe steps missing sequence_number | Steps without `sequence_number` | Ordering may fail (line 201) | Exception |
| **TC-REL-010** Duplicate sequence numbers | Two steps with same `sequence_number` | Undefined ordering | Steps skipped or duplicated |

### 2.2 Process Execution Record Creation

**Code Location**: `simple_recipe_service.py:206-237`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-PER-001** Standard process creation | Valid recipe and steps | `process_executions` record created with ID | N/A |
| **TC-PER-002** Database insert failure | Supabase insert fails | Return False, log error (line 223) | Exception |
| **TC-PER-003** Insert returns empty data | `process_result.data = []` | Return False (line 223) | IndexError on line 226 |
| **TC-PER-004** Large recipe_version JSON | Recipe with 1000+ steps | JSON stored successfully | Size limit exceeded |
| **TC-PER-005** Recipe version JSON serialization failure | Recipe contains non-serializable objects | Exception during insert | Silent data corruption |
| **TC-PER-006** Process_execution_state creation failure | State insert fails after process creation | Process exists but no state record | Orphaned process record |
| **TC-PER-007** Machine status update failure | Update to `machines` table fails | Process created but machine status inconsistent | Race condition |
| **TC-PER-008** Machine_state update failure | Update to `machine_state` table fails | Process created but state inconsistent | Race condition |
| **TC-PER-009** Continuous recorder start failure | `continuous_recorder.start()` raises exception | Exception propagates, recipe fails | Service crashes |
| **TC-PER-010** Race condition on current_process_id | Two recipes try to start simultaneously | Second recipe should fail (machine busy) | Both recipes start |

### 2.3 Loop Step Edge Cases

**Code Location**: `src/recipe_flow/executor.py:36-126`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-LSE-001** Loop with count=0 | Loop step with `parameters.count=0` | Skip loop, execute 0 iterations | Infinite loop or crash |
| **TC-LSE-002** Loop with count=1 | Loop step with `parameters.count=1` | Execute child steps once | N/A |
| **TC-LSE-003** Loop with large count | Loop step with `parameters.count=10000` | Execute 10000 iterations (may take time) | Integer overflow or timeout |
| **TC-LSE-004** Loop with negative count | `parameters.count=-5` | ValueError or skip loop | Infinite loop |
| **TC-LSE-005** Loop with non-integer count | `parameters.count=5.7` | Cast to int (5) or error | Exception |
| **TC-LSE-006** Loop missing count parameter | Loop step without `parameters.count` | KeyError, recipe fails | Assumed default value |
| **TC-LSE-007** Nested loops | Loop step contains child loop steps | Nested loops execute correctly | Not supported, fails |
| **TC-LSE-008** Loop with no child steps | Loop step with no `parent_step_id` references | Execute loop 0 times | Exception |
| **TC-LSE-009** Loop child steps out of sequence | Child steps with incorrect `sequence_number` | Sorted correctly (line 165-166) | Wrong execution order |
| **TC-LSE-010** Loop step count arithmetic overflow | Total steps calculation overflows | Exception or incorrect progress | Progress tracking broken |

### 2.4 Step Execution and Routing

**Code Location**: `src/step_flow/executor.py:24-89`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-SER-001** Valve step without valve_number | Valve step missing `parameters.valve_number` | Raise ValueError (line 54) | Exception uncaught |
| **TC-SER-002** Valve step with invalid valve_number | `valve_number=999` (out of range) | Handled by valve executor | Wrong valve opened |
| **TC-SER-003** Purge step missing parameters | Purge step with `parameters={}` | Tolerated (line 42), uses defaults | Exception |
| **TC-SER-004** Purge step missing duration_ms | Purge without `parameters.duration_ms` | Handled by purge executor | Infinite purge |
| **TC-SER-005** Unknown step type | `step['type'] = 'custom_step'` | Raise ValueError (line 70) | Silent skip |
| **TC-SER-006** Step type case mismatch | `type='VALVE'` instead of `'valve'` | Converted to lowercase (line 24) | Not matched |
| **TC-SER-007** Missing step type field | Step dict without `type` key | KeyError | Exception |
| **TC-SER-008** NULL step type | `step['type'] = NULL` | Exception during lowercase | Crash |
| **TC-SER-009** Set parameter step | `type='set parameter'` | Execute parameter step | Not matched (expects 'set parameter') |
| **TC-SER-010** Step execution exception | Step executor raises exception | Exception propagates (line 87) | Uncaught, recipe fails |

### 2.5 Cancellation and Interruption

**Code Location**: `src/recipe_flow/executor.py:70-143`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-CAN-001** Cancel before first step | `is_cancelled()` returns True before loop | Exit early, don't mark completed (line 132-136) | Recipe marked completed |
| **TC-CAN-002** Cancel during step execution | Cancel signal during step | Step completes, then check cancellation | Step interrupted mid-execution |
| **TC-CAN-003** Cancel between steps | Cancel after step A, before step B | Stop at step A, don't execute step B | Step B executes |
| **TC-CAN-004** Multiple cancel signals | Cancel called multiple times | Handled gracefully, single exit | Exception |
| **TC-CAN-005** Cancel during loop iteration | Cancel mid-loop | Exit loop early | Loop completes all iterations |
| **TC-CAN-006** Cancel with recorder running | Cancel while `continuous_recorder` active | Recorder stopped (line 134) | Recorder keeps running |
| **TC-CAN-007** Cancel clears flag | After cancel, flag is cleared (line 143) | Next recipe can start | Cancel flag persists |
| **TC-CAN-008** Cancellation with pending database writes | Cancel during database update | Updates may be incomplete | Inconsistent state |

---

## 3. Database Integration Edge Cases

### 3.1 Multi-Table State Transitions

**Code Location**: `simple_recipe_service.py:239-251, executor.py:171-227`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-DBM-001** Atomic completion success | Recipe completes normally | Both `machines` and `machine_state` updated atomically (line 208) | N/A |
| **TC-DBM-002** Atomic completion failure | `atomic_complete_machine_state()` fails | Fallback to dual table updates (line 212-226) | Inconsistent state |
| **TC-DBM-003** Fallback updates partial failure | First table updates, second fails | Inconsistent state (machine vs machine_state) | Silent failure |
| **TC-DBM-004** Process execution status update | Update `process_executions.status='completed'` | Updated successfully | Update fails silently |
| **TC-DBM-005** Process execution state finalization | Update `process_execution_state` with completion | Updated successfully | State stuck in old step |
| **TC-DBM-006** Machine current_process_id cleared | `machines.current_process_id=NULL` on completion | Cleared successfully | Process ID persists |
| **TC-DBM-007** Error state transition | Recipe fails, error state set | Both tables updated to error (line 262-263) | Only one table updated |
| **TC-DBM-008** Error with long error message | `error_message` > 100 characters | Truncated in state (line 254), full in execution | Database field overflow |

### 3.2 Progress Tracking Updates

**Code Location**: `src/recipe_flow/executor.py:48-94, step_executor.py:30-84`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-PRT-001** Progress initialization | Recipe starts with 10 steps | `total_steps=10, completed_steps=0` (line 50-54) | N/A |
| **TC-PRT-002** Loop progress calculation | Loop with count=5, 3 child steps | `total_steps=15` (5*3) | Arithmetic error |
| **TC-PRT-003** Mixed loops and regular steps | Recipe with 2 loops + 3 regular steps | Correct total calculation | Incorrect count |
| **TC-PRT-004** Progress increment after step | Non-loop step completes | `completed_steps += 1` (line 76) | Progress not updated |
| **TC-PRT-005** Progress update database failure | `process_execution_state` update fails | Logged but execution continues (line 111) | Silent failure |
| **TC-PRT-006** Progress with zero total_steps | Empty recipe | Division by zero in UI? | Crash |
| **TC-PRT-007** Completed exceeds total | Bug causes `completed_steps > total_steps` | Progress > 100% | Exception |
| **TC-PRT-008** Progress query failure | Cannot read current progress | Uses default `{total_steps:0, completed_steps:0}` (line 34) | Exception |

### 3.3 Recipe Command Finalization

**Code Location**: `simple_recipe_service.py:143-170`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-RCF-001** Successful recipe completion | Recipe completes without errors | Command marked `status='completed'` (line 147) | N/A |
| **TC-RCF-002** Failed recipe execution | Recipe raises exception | Command marked `status='failed'` with error (line 154) | Status not updated |
| **TC-RCF-003** Database update failure on completion | Update to `recipe_commands` fails | Exception logged, command stuck in `executing` | Silent failure |
| **TC-RCF-004** Concurrent command updates | Two processes try to update same command | Database handles conflict (last write wins) | Data corruption |
| **TC-RCF-005** Command finalization with NULL error | Success case has `error_message=NULL` | NULL accepted | Field required |
| **TC-RCF-006** Long error message | `error_message` > 1000 characters | Truncated or stored fully | Database overflow |

---

## 4. Recipe Flow Edge Cases

### 4.1 Parent-Child Step Mapping

**Code Location**: `src/recipe_flow/executor.py:145-168`

| Test Scenario | Input | Expected Behavior | Failure Mode |
|--------------|-------|-------------------|--------------|
| **TC-PCM-001** No parent-child relationships | All steps have `parent_step_id=NULL` | Empty parent_to_child_steps dict | N/A |
| **TC-PCM-002** Single parent with multiple children | 1 loop step, 5 child steps | Dict maps parent ID to 5 children | N/A |
| **TC-PCM-003** Multiple parents | 3 loop steps, each with children | Dict has 3 entries | N/A |
| **TC-PCM-004** Orphaned child step | Child step with non-existent `parent_step_id` | Child added to dict but parent never found | Exception during execution |
| **TC-PCM-005** Child steps out of order | Child steps with sequence [3, 1, 2] | Sorted correctly (line 165-166) | Wrong execution order |
| **TC-PCM-006** Circular parent-child reference | Step A references Step B, Step B references Step A | Infinite recursion? | Crash |
| **TC-PCM-007** NULL parent_step_id vs missing field | Explicit NULL vs missing field | Both treated as no parent | Different behavior |

### 4.2 Step Type-Specific Edge Cases

| Step Type | Test Scenario | Expected Behavior | Failure Mode |
|-----------|--------------|-------------------|--------------|
| **Valve** | Valve number out of range (1-100) | Handled by valve executor | Wrong valve or crash |
| **Valve** | Duration_ms = 0 | Open valve for 0ms (no-op) | Exception |
| **Valve** | Duration_ms negative | ValueError or skip | Infinite duration |
| **Valve** | Missing valve_number parameter | ValueError raised (line 54) | Exception |
| **Purge** | Missing gas_type | Default or error in purge executor | Exception |
| **Purge** | Invalid gas_type | Handled by purge executor | Wrong gas |
| **Purge** | Duration_ms = 0 | Purge for 0ms (no-op) | Exception |
| **Purge** | Duration_ms > 1 hour | Long purge, recipe blocked | Timeout |
| **Set Parameter** | Parameter not found | Error in parameter executor | Exception |
| **Set Parameter** | Invalid target value | Validation in parameter executor | Invalid value written |
| **Loop** | Nested loops (loop within loop) | Not explicitly supported, may work | Undefined behavior |
| **Loop** | Loop count arithmetic overflow | Integer overflow in line 41, 122-124 | Crash |

---

## 5. Concurrent Execution Scenarios

### 5.1 Multi-Recipe Queuing

| Test Scenario | Expected Behavior | Failure Mode |
|--------------|-------------------|--------------|
| **TC-MRQ-001** Two recipes queued, one machine | Second waits until first completes | Both start simultaneously |
| **TC-MRQ-002** Recipe queued while one running | Second recipe starts after first completes | Second recipe fails (machine busy) |
| **TC-MRQ-003** Stop command during recipe | Current recipe stops, machine idle | Stop ignored |
| **TC-MRQ-004** New start command while recipe running | Second recipe fails or waits | Overwrites running recipe |
| **TC-MRQ-005** Multiple stop commands | Handled gracefully | Exception |

### 5.2 Terminal Interaction Edge Cases

| Test Scenario | Expected Behavior | Failure Mode |
|--------------|-------------------|--------------|
| **TC-TIE-001** Recipe execution while Terminal 1 reading | Both operate independently (shared PLC singleton) | PLC read/write conflict |
| **TC-TIE-002** Recipe execution while Terminal 3 writing | Parameter writes during recipe | PLC contention |
| **TC-TIE-003** All 3 terminals start simultaneously | All initialize PLC connections | PLC connection storm |
| **TC-TIE-004** Terminal 1 crashes during recipe | Recipe continues (no dependency) | Recipe fails |
| **TC-TIE-005** Terminal 3 crashes during recipe | Recipe continues | Recipe relies on T3 for parameter control |

---

## 6. Recipe Test Data Structures

### 6.1 Simple Recipe (No Loops)

```python
simple_recipe_command = {
    "id": "cmd-001",
    "type": "start_recipe",
    "machine_id": "machine-123",
    "status": "pending",
    "parameters": {
        "recipe_id": "recipe-simple-001"
    },
    "created_at": "2025-10-10T12:00:00Z"
}

simple_recipe = {
    "id": "recipe-simple-001",
    "name": "Simple 3-Step Recipe",
    "version": "1.0",
    "steps": []  # Loaded separately
}

simple_recipe_steps = [
    {"id": "step-001", "recipe_id": "recipe-simple-001", "sequence_number": 1,
     "type": "valve", "name": "Open Valve 1", "parameters": {"valve_number": 1, "duration_ms": 5000}},
    {"id": "step-002", "recipe_id": "recipe-simple-001", "sequence_number": 2,
     "type": "purge", "name": "Purge with N2", "parameters": {"gas_type": "N2", "duration_ms": 10000}},
    {"id": "step-003", "recipe_id": "recipe-simple-001", "sequence_number": 3,
     "type": "valve", "name": "Close Valve 1", "parameters": {"valve_number": 1, "duration_ms": 0}}
]
```

**Expected Execution Time**: ~15 seconds
**Expected Total Steps**: 3
**Expected Progress Updates**: 3 (one per step)

### 6.2 Recipe with Single Loop

```python
loop_recipe_command = {
    "id": "cmd-002",
    "type": "start_recipe",
    "machine_id": "machine-123",
    "status": "pending",
    "parameters": {
        "recipe_id": "recipe-loop-001"
    },
    "created_at": "2025-10-10T12:05:00Z"
}

loop_recipe_steps = [
    {"id": "step-001", "recipe_id": "recipe-loop-001", "sequence_number": 1,
     "type": "loop", "name": "Main Loop", "parameters": {"count": 5}, "parent_step_id": None},
    {"id": "step-002", "recipe_id": "recipe-loop-001", "sequence_number": 2,
     "type": "valve", "name": "Open Valve 2", "parameters": {"valve_number": 2, "duration_ms": 1000},
     "parent_step_id": "step-001"},
    {"id": "step-003", "recipe_id": "recipe-loop-001", "sequence_number": 3,
     "type": "purge", "name": "Short Purge", "parameters": {"gas_type": "Ar", "duration_ms": 2000},
     "parent_step_id": "step-001"}
]
```

**Expected Execution Time**: ~15 seconds (5 iterations * 3s each)
**Expected Total Steps**: 10 (5 iterations * 2 child steps)
**Expected Loop Iterations**: 5

### 6.3 Complex Recipe (Multiple Loops + Regular Steps)

```python
complex_recipe_steps = [
    {"id": "step-001", "sequence_number": 1, "type": "valve", "name": "Initialize", "parameters": {"valve_number": 1, "duration_ms": 1000}, "parent_step_id": None},
    {"id": "step-002", "sequence_number": 2, "type": "loop", "name": "Deposition Loop", "parameters": {"count": 10}, "parent_step_id": None},
    {"id": "step-003", "sequence_number": 3, "type": "valve", "name": "Precursor Pulse", "parameters": {"valve_number": 3, "duration_ms": 500}, "parent_step_id": "step-002"},
    {"id": "step-004", "sequence_number": 4, "type": "purge", "name": "Purge 1", "parameters": {"gas_type": "N2", "duration_ms": 3000}, "parent_step_id": "step-002"},
    {"id": "step-005", "sequence_number": 5, "type": "valve", "name": "Oxidant Pulse", "parameters": {"valve_number": 4, "duration_ms": 500}, "parent_step_id": "step-002"},
    {"id": "step-006", "sequence_number": 6, "type": "purge", "name": "Purge 2", "parameters": {"gas_type": "N2", "duration_ms": 3000}, "parent_step_id": "step-002"},
    {"id": "step-007", "sequence_number": 7, "type": "loop", "name": "Anneal Loop", "parameters": {"count": 3}, "parent_step_id": None},
    {"id": "step-008", "sequence_number": 8, "type": "set parameter", "name": "Set Temp High", "parameters": {"parameter_name": "Temperature", "value": 500}, "parent_step_id": "step-007"},
    {"id": "step-009", "sequence_number": 9, "type": "purge", "name": "Anneal Hold", "parameters": {"gas_type": "Ar", "duration_ms": 5000}, "parent_step_id": "step-007"},
    {"id": "step-010", "sequence_number": 10, "type": "valve", "name": "Finalize", "parameters": {"valve_number": 1, "duration_ms": 0}, "parent_step_id": None}
]
```

**Expected Total Steps**: 1 + (10*4) + (3*2) + 1 = 48 steps
**Expected Execution Time**: ~2 minutes
**Expected Loop Counts**: 10 (deposition) + 3 (anneal)

### 6.4 Edge Case Recipes

```python
# Empty recipe (zero steps)
empty_recipe_steps = []

# Single loop, zero iterations
zero_loop_steps = [
    {"id": "step-001", "sequence_number": 1, "type": "loop", "name": "Zero Loop", "parameters": {"count": 0}, "parent_step_id": None}
]

# Recipe with only loop, no children
orphan_loop_steps = [
    {"id": "step-001", "sequence_number": 1, "type": "loop", "name": "Orphan Loop", "parameters": {"count": 5}, "parent_step_id": None}
]

# Malformed steps (missing required fields)
malformed_steps = [
    {"id": "step-001", "type": "valve", "name": "Broken Valve"},  # Missing parameters
    {"id": "step-002", "type": "purge", "parameters": {}},  # Missing name
    {"id": "step-003", "parameters": {"valve_number": 1}}  # Missing type
]
```

---

## 7. Expected Execution Flows

### 7.1 Successful Recipe Execution Flow

```
1. Polling detects command (status='pending')
2. Mark command executing (status='executing', executed_at=now)
3. Load recipe from database (recipes table)
4. Load recipe steps (recipe_steps table)
5. Create process_execution record (status='running')
6. Create process_execution_state record
7. Update machine status (status='running', current_process_id=process_id)
8. Update machine_state (current_state='running', process_id=process_id)
9. Start continuous_recorder
10. Execute each top-level step sequentially:
    - Update process_execution_state with current step
    - Execute step (valve/purge/parameter/loop)
    - Update progress (completed_steps++)
    - Record process data
11. Stop continuous_recorder
12. Update process_execution (status='completed', end_time=now)
13. Update process_execution_state (current_step_type='completed')
14. Atomically update machines and machine_state to idle
15. Mark recipe_command as completed (status='completed')
```

**Expected Database Writes**: ~15-20 (depending on recipe length)
**Expected Duration**: Recipe-dependent (5s - 10min typical)

### 7.2 Failed Recipe Execution Flow

```
1. Polling detects command
2. Mark command executing
3. Load recipe (FAILS - recipe not found)
4. Exception caught in execute_recipe_command()
5. Mark command as failed (status='failed', error_message='...')
6. No process_execution created
7. No machine status changes
```

**Expected Database Writes**: 2 (executed_at, then failed status)
**Expected Duration**: <1 second

### 7.3 Cancelled Recipe Flow

```
1-10. Same as successful flow
11. Cancellation signal received (is_cancelled=True)
12. Exit execute_recipe loop early
13. Stop continuous_recorder
14. Do NOT mark process as completed
15. Do NOT update machine state
16. Recipe command remains in 'executing' status (or separate cancellation handling)
```

**Expected Behavior**: Recipe stops mid-execution, machine in inconsistent state?
**Gap**: No explicit cancel handling in simple_recipe_service.py

---

## 8. Failure Recovery Expectations

### 8.1 Database Failures

| Failure Point | Recovery Mechanism | Current Gaps |
|--------------|-------------------|--------------|
| Recipe query fails | Log error, return False, skip command | Command stuck in executing |
| Process creation fails | Log error, return False, mark command failed | N/A |
| State update fails | Logged (line 111), execution continues | State inconsistent |
| Command status update fails | Exception logged, may retry next poll | Command stuck |
| Atomic state update fails | Fallback to dual update (line 212-226) | Fallback can also fail |

### 8.2 PLC Failures

| Failure Point | Recovery Mechanism | Current Gaps |
|--------------|-------------------|--------------|
| PLC initialization fails | Raises RuntimeError, service exits | No retry |
| PLC disconnects during recipe | Exception propagates, recipe fails | No reconnect attempt |
| PLC write fails (step execution) | Exception propagates, recipe fails | No step retry |
| PLC read fails (confirmation) | Depends on step executor | May not fail recipe |

### 8.3 Service Failures

| Failure Point | Recovery Mechanism | Current Gaps |
|--------------|-------------------|--------------|
| Service crashes mid-recipe | No recovery, restart required | Process stuck in 'running' |
| Service killed (SIGTERM) | Graceful shutdown (line 368) | In-flight recipe may fail |
| Service killed (SIGKILL) | No cleanup | Process stuck |
| Continuous recorder fails to start | Exception propagates, recipe fails | N/A |
| Continuous recorder fails to stop | Logged but execution continues | Recorder may keep running |

---

## 9. Timing and Duration Estimates

### 9.1 Performance Benchmarks

| Operation | Expected Duration | Threshold |
|-----------|------------------|-----------|
| Poll for commands | <100ms | <500ms |
| Load recipe from DB | <200ms | <1s |
| Create process record | <300ms | <1s |
| Start continuous recorder | <100ms | <500ms |
| Execute valve step (5s) | ~5s | 5s ± 100ms |
| Execute purge step (10s) | ~10s | 10s ± 200ms |
| Update progress | <50ms | <200ms |
| Complete recipe (DB updates) | <500ms | <2s |
| Stop continuous recorder | <200ms | <1s |

### 9.2 Recipe Duration Estimates

| Recipe Type | Steps | Duration | Notes |
|-------------|-------|----------|-------|
| Simple (3 steps) | 3 | ~15s | 3 valve/purge steps |
| Medium (1 loop, 5 iterations) | 10 | ~30s | 5 * (2 steps * 3s) |
| Complex (multiple loops, 48 steps) | 48 | ~2-3min | ALD deposition recipe |
| Stress test (large loop, 1000 steps) | 1000 | ~15-20min | 1000 * 1s steps |

---

## 10. Test Execution Strategy

### 10.1 Unit Tests

- Mock database (Supabase client)
- Mock PLC manager
- Mock continuous recorder
- Test command polling logic
- Test command routing
- Test recipe loading
- Test process creation
- Test error handling

**Estimated Tests**: 50-60 unit tests
**Coverage Target**: >90%

### 10.2 Integration Tests

- Real database (test instance)
- Simulated PLC
- Real continuous recorder
- End-to-end recipe execution
- Multi-step recipes
- Loop execution
- Cancellation
- Database state transitions

**Estimated Tests**: 20-30 integration tests
**Duration**: 5-10 minutes total

### 10.3 System Tests

- All 3 terminals running
- Real database
- Simulated PLC
- Multi-recipe execution
- Concurrent recipe queuing
- Terminal interaction testing
- Failure injection

**Estimated Tests**: 10-15 system tests
**Duration**: 30-60 minutes total

---

## 11. Critical Gaps and Risks

### 11.1 High Priority Gaps

1. **No explicit cancellation handling in simple_recipe_service.py**
   - Cancellation exists in executor.py but recipe_commands table has no cancel command type
   - Stopped recipes leave process in running state

2. **No timeout enforcement on recipe execution**
   - Long-running recipes can block service indefinitely
   - No max recipe duration configured

3. **No retry logic for transient failures**
   - Database transient errors fail recipe permanently
   - PLC transient errors fail recipe permanently

4. **Atomic state update fallback can fail silently**
   - If atomic update fails AND fallback fails, state inconsistent
   - No alerting or monitoring

5. **No recipe queue depth limit**
   - Infinite queued commands can accumulate
   - No FIFO enforcement guarantee

### 11.2 Medium Priority Gaps

1. Recipe validation is minimal (only checks existence)
2. No recipe version conflict handling
3. Loop count validation is weak
4. No step execution timeout
5. Progress calculation can overflow with large loops
6. Continuous recorder errors are not retried

### 11.3 Low Priority Gaps

1. No recipe execution metrics/telemetry
2. No recipe dry-run or validation mode
3. No recipe execution history pruning
4. Error messages not truncated consistently
5. No recipe execution duration limits

---

## 12. Test Coverage Requirements

| Category | Coverage Target | Priority |
|----------|----------------|----------|
| Recipe command polling | 100% | HIGH |
| Command routing | 100% | HIGH |
| Recipe loading | 100% | HIGH |
| Process creation | 95% | HIGH |
| Step execution routing | 100% | HIGH |
| Loop execution | 95% | MEDIUM |
| Cancellation handling | 90% | MEDIUM |
| Error handling | 90% | HIGH |
| Database state transitions | 95% | HIGH |
| Progress tracking | 85% | MEDIUM |

**Overall Target Coverage**: >90%

---

## Appendix A: Code References

- **simple_recipe_service.py**: Main service file (423 lines)
- **src/recipe_flow/executor.py**: Recipe execution orchestrator (280 lines)
- **src/step_flow/executor.py**: Step routing (89 lines)
- **src/step_flow/loop_step.py**: Loop execution logic
- **src/step_flow/valve_step.py**: Valve step execution
- **src/step_flow/purge_step.py**: Purge step execution
- **src/step_flow/parameter_step.py**: Parameter set execution
- **src/recipe_flow/continuous_data_recorder.py**: Continuous recording
- **src/recipe_flow/cancellation.py**: Cancellation management

---

## Appendix B: Database Schema Dependencies

### Tables Read
- `recipes` (recipe metadata)
- `recipe_steps` (step definitions)
- `recipe_commands` (command queue)

### Tables Written
- `recipe_commands` (status updates)
- `process_executions` (process lifecycle)
- `process_execution_state` (progress tracking)
- `machines` (machine status)
- `machine_state` (machine state)

---

**END OF DOCUMENT**
