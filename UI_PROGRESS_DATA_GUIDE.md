# Flutter UI Progress Data Query Guide

## Problem Summary

The Flutter UI is showing empty progress data during recipe execution:
- Total Steps: 0
- Completed Steps: 0
- Current Step Index: null
- Progress Data: {} (empty)

**Root Cause**: The UI is NOT querying the `process_execution_state` table where all progress data lives.

## Database Architecture

The system uses a **two-table design** for process execution tracking:

### Table 1: `process_executions` (Static Metadata)
**Purpose**: Stores basic execution information that doesn't change frequently

**Fields**:
- `id` - Process execution UUID
- `machine_id` - Machine running the process
- `operator_id` - Who started it
- `recipe_id` - Which recipe
- `recipe_version` - Snapshot of recipe at start
- `status` - 'pending', 'running', 'completed', 'failed', 'cancelled'
- `start_time` - When it started
- `end_time` - When it finished (null if running)
- `parameters` - Recipe parameters (JSONB)
- `description` - Optional description
- `error_message` - Error details if failed

**IMPORTANT**: This table does NOT contain:
- ❌ `current_step_index`
- ❌ `total_steps`
- ❌ `completed_steps`
- ❌ `progress_data`

### Table 2: `process_execution_state` (Dynamic Progress Tracking)
**Purpose**: Stores real-time progress that updates every step

**Fields**:
- `id` - State record UUID
- `execution_id` - FK to `process_executions.id`
- `current_step_index` - Which step is currently executing (0-indexed)
- `current_step_name` - Human-readable step name
- `current_step_type` - 'valve', 'purge', 'loop', 'parameter', 'completed'
- `current_overall_step` - Overall step count (accounting for loop expansion)
- `total_overall_steps` - Total steps including loop iterations
- `current_loop_count` - For loop steps: total iterations
- `current_loop_iteration` - For loop steps: current iteration (0-indexed)
- `current_valve_number` - For valve steps: valve number (1-8)
- `current_valve_duration_ms` - For valve steps: duration in milliseconds
- `current_purge_duration_ms` - For purge steps: duration in milliseconds
- `progress` - JSONB field with detailed progress:
  ```json
  {
    "total_steps": 10,
    "completed_steps": 3,
    "total_cycles": 5,
    "completed_cycles": 1
  }
  ```
- `process_metrics` - Additional metrics (JSONB)
- `last_updated` - Timestamp of last update

## Verified Backend Behavior

The Python backend **IS WORKING CORRECTLY**. Example actual database content:

```python
# Process in process_executions table:
{
  "id": "74e544dc-3194-4f21-bb1f-c9ac37269a84",
  "status": "running",
  "recipe_id": "...",
  # ... other static fields
}

# State in process_execution_state table:
{
  "execution_id": "74e544dc-3194-4f21-bb1f-c9ac37269a84",
  "current_step_index": 2,
  "total_overall_steps": 10,
  "current_overall_step": 3,
  "progress": {
    "total_steps": 10,
    "completed_steps": 3,
    "total_cycles": 5,
    "completed_cycles": 1
  },
  "current_step_name": "Valve 1 Pulse",
  "current_step_type": "valve",
  "current_valve_number": 1,
  "current_valve_duration_ms": 5000
}
```

**The data IS there!** The UI just needs to read it.

## How UI Should Query Progress Data

### Option 1: Two Separate Queries (Recommended)

```typescript
// 1. Get basic process info
const { data: processData } = await supabase
  .from('process_executions')
  .select('id, machine_id, recipe_id, status, start_time, end_time, recipes(name, description)')
  .eq('machine_id', MACHINE_ID)
  .eq('status', 'running')
  .maybeSingle();

if (!processData) {
  // No running process
  return null;
}

// 2. Get real-time progress state
const { data: stateData } = await supabase
  .from('process_execution_state')
  .select(`
    current_step_index,
    current_step_name,
    current_step_type,
    current_overall_step,
    total_overall_steps,
    current_loop_count,
    current_loop_iteration,
    current_valve_number,
    current_valve_duration_ms,
    current_purge_duration_ms,
    progress,
    process_metrics,
    last_updated
  `)
  .eq('execution_id', processData.id)
  .maybeSingle();

// 3. Combine the data
const activeProcess = {
  // From process_executions
  id: processData.id,
  recipe_id: processData.recipe_id,
  recipe_name: processData.recipes?.name,
  status: processData.status,
  started_at: processData.start_time,

  // From process_execution_state
  current_step_index: stateData?.current_step_index ?? 0,
  current_step_name: stateData?.current_step_name ?? 'Starting...',
  current_step_type: stateData?.current_step_type ?? null,
  total_steps: stateData?.progress?.total_steps ?? 0,
  completed_steps: stateData?.progress?.completed_steps ?? 0,
  total_cycles: stateData?.progress?.total_cycles ?? 0,
  completed_cycles: stateData?.progress?.completed_cycles ?? 0,
  current_valve_number: stateData?.current_valve_number ?? null,
  current_valve_duration_ms: stateData?.current_valve_duration_ms ?? null,
  // ... etc
};
```

### Option 2: Database View (Better Performance)

Create a Supabase view that joins both tables:

```sql
CREATE VIEW process_executions_with_state AS
SELECT
  pe.id,
  pe.machine_id,
  pe.recipe_id,
  pe.status,
  pe.start_time,
  pe.end_time,
  pes.current_step_index,
  pes.current_step_name,
  pes.current_step_type,
  pes.current_overall_step,
  pes.total_overall_steps,
  pes.current_valve_number,
  pes.current_valve_duration_ms,
  pes.progress,
  pes.last_updated
FROM process_executions pe
LEFT JOIN process_execution_state pes ON pes.execution_id = pe.id;
```

Then query the view:

```typescript
const { data } = await supabase
  .from('process_executions_with_state')
  .select('*')
  .eq('machine_id', MACHINE_ID)
  .eq('status', 'running')
  .maybeSingle();
```

## Realtime Subscriptions

Subscribe to BOTH tables for real-time updates:

```typescript
// Subscribe to process_executions for status changes
const processChannel = supabase
  .channel('process-updates')
  .on(
    'postgres_changes',
    {
      event: 'UPDATE',
      schema: 'public',
      table: 'process_executions',
      filter: `machine_id=eq.${MACHINE_ID}`
    },
    (payload) => {
      // Handle status changes, start/end times
      updateProcessStatus(payload.new);
    }
  );

// Subscribe to process_execution_state for progress updates
const stateChannel = supabase
  .channel('state-updates')
  .on(
    'postgres_changes',
    {
      event: 'UPDATE',
      schema: 'public',
      table: 'process_execution_state',
      filter: `execution_id=eq.${currentProcessId}`
    },
    (payload) => {
      // Handle step changes, progress updates
      updateProgressDisplay(payload.new);
    }
  );

await processChannel.subscribe();
await stateChannel.subscribe();
```

## Update Frequency

The backend updates `process_execution_state`:
- **Before each step**: Updates `current_step_index`, `current_step_name`, `current_step_type`, and step-specific fields
- **After each step**: Increments `completed_steps` in the `progress` JSONB
- **During loops**: Updates `current_loop_iteration` on each iteration

This happens every 1-10 seconds depending on step durations, so the UI should see near real-time updates.

## Common Mistakes

### ❌ WRONG: Querying only `process_executions`
```typescript
// This will NOT work - these fields don't exist here!
const { data } = await supabase
  .from('process_executions')
  .select('id, recipe_id, status, current_step_index, total_steps')
  //                                  ^^^^^^^^^^^^^^^  ^^^^^^^^^^^
  //                                  These fields don't exist!
```

### ✅ CORRECT: Query both tables
```typescript
// Get basic info from process_executions
const { data: process } = await supabase
  .from('process_executions')
  .select('id, recipe_id, status');

// Get progress from process_execution_state
const { data: state } = await supabase
  .from('process_execution_state')
  .select('current_step_index, progress')
  .eq('execution_id', process.id);
```

## Debugging Checklist

If the UI shows empty progress data:

1. ✅ Check if `process_executions` record exists for the process
2. ✅ Check if `process_execution_state` record exists (query by `execution_id`)
3. ✅ Verify the `progress` JSONB field is not null/empty
4. ✅ Check `last_updated` timestamp - should be recent for running processes
5. ✅ Verify realtime subscription is connected and listening to the right table
6. ✅ Check if the UI is parsing the `progress` JSONB correctly (it's nested!)

## Example Complete Implementation

See the working example in `hooks/use-dashboard-data.ts` (lines 156-171) which correctly queries both tables:

```typescript
// 1. Get process
const { data: processData } = await supabase
  .from('process_executions')
  .select('id, recipe_id, status, start_time, end_time, recipes(name)')
  .eq('machine_id', MACHINE_ID)
  .eq('status', 'running')
  .maybeSingle();

// 2. Get state
const { data: stateData } = await supabase
  .from('process_execution_state')
  .select('current_step_index, progress')
  .eq('execution_id', processData.id)
  .maybeSingle();

// 3. Combine
return {
  id: processData.id,
  recipe_id: processData.recipe_id,
  status: processData.status,
  current_step_index: stateData?.current_step_index || 0,
  total_steps: stateData?.progress?.total_steps || 0,
  completed_steps: stateData?.progress?.completed_steps || 0,
  recipes: processData.recipes
};
```

## Backend Code References

For reference, here's where the backend updates this data:

- **Initial creation**: `simple_recipe_service.py:257` - Creates `process_execution_state` record
- **Progress initialization**: `src/recipe_flow/executor.py:86-95` - Sets initial progress structure
- **Step updates**: `src/recipe_flow/executor.py:122-146` - Updates state before each step
- **Step completion**: `src/step_flow/executor.py:72-81` - Increments completed_steps
- **Loop iteration**: `src/step_flow/loop_step.py:161-165` - Updates loop progress

All updates go to `process_execution_state` table, never to `process_executions`.
