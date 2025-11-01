# Machine Table Architecture Analysis

## Current State (Based on Error Logs)

### Tables vs Views

1. **`machine_instances`** - Base table (updatable)
   - Stores individual machine records
   - Columns: id, current_status, current_process_id, updated_at, etc.
   - ✅ Can be updated directly

2. **`machines_base`** - Base table (updatable) - USED BY PYTHON BACKEND
   - Used by Python backend (`simple_recipe_service.py`)
   - Columns: id, status, current_process_id
   - ✅ Can be updated directly

3. **`machines`** - VIEW (not directly updatable)
   - Joins multiple tables (likely `machine_instances` + `machine_types`)
   - ❌ Cannot be updated without INSTEAD OF trigger
   - Used by Flutter app (CAUSING THE ERROR)

## The Problem

**Flutter app** tries to update the `machines` VIEW:
```dart
// BROKEN - Line 508 in start_recipe_use_case.dart
await _machinesRepository.update(machineId, {
  'current_status': 'running',  // ❌ Fails on multi-table view
  'current_process_id': processExecutionId,
});
```

**Error:**
```
PostgrestException: cannot update view "machines", code: 55000
Details: Views that do not select from a single table or view are not automatically updatable.
```

**Python backend** correctly updates the base table:
```python
# WORKING - simple_recipe_service.py
supabase.table('machines_base').update({
    'status': 'running',  # ✅ Works on base table
    'current_process_id': process_id
}).eq('id', MACHINE_ID).execute()
```

## Schema Confusion

There appear to be TWO base tables with overlapping purposes:

1. **`machines_base`** - Used by Python backend
2. **`machine_instances`** - Referenced in Flutter error (might be the same table, different name?)

### Hypothesis 1: They're the Same Table
- `machines_base` might be an alias or the actual name
- `machine_instances` might be old naming that needs cleanup

### Hypothesis 2: They're Different Tables
- `machines_base` = simpler table for basic machine info
- `machine_instances` = more detailed table with full machine data
- `machines` VIEW joins them together

## Required Actions

### 1. Verify Database Schema (HIGH PRIORITY)

Run these queries in Supabase SQL editor:

```sql
-- Check what tables exist
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE '%machine%'
ORDER BY table_type, table_name;

-- Check machines view definition
SELECT definition
FROM pg_views
WHERE viewname = 'machines';

-- Check machines_base structure (if exists)
\d machines_base

-- Check machine_instances structure (if exists)
\d machine_instances
```

### 2. Fix Flutter App (IMMEDIATE)

**Option A: Update Correct Base Table**
```dart
// In start_recipe_use_case.dart:508
Future<void> _updateMachineStatus(...) async {
  // Use machines_base (same as Python) OR machine_instances (if that's the actual table)
  await _supabase
    .from('machines_base')  // or 'machine_instances' - verify which exists!
    .update({
      'status': 'running',  // Note: field might be 'status' not 'current_status'
      'current_process_id': processExecutionId,
      'updated_at': DateTime.now().toIso8601String(),
    })
    .eq('id', machineId);
}
```

**Option B: Create Database Trigger** (if you must keep using the view)
```sql
CREATE OR REPLACE FUNCTION update_machines_view()
RETURNS TRIGGER AS $$
BEGIN
  -- Update the actual base table (whichever one it is)
  UPDATE machines_base  -- or machine_instances
  SET
    status = COALESCE(NEW.current_status, NEW.status, OLD.status),
    current_process_id = COALESCE(NEW.current_process_id, OLD.current_process_id),
    updated_at = NOW()
  WHERE id = OLD.id;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_machines_instead
INSTEAD OF UPDATE ON machines
FOR EACH ROW
EXECUTE FUNCTION update_machines_view();
```

### 3. Standardize Naming (TECHNICAL DEBT)

Choose ONE approach across the entire system:

**Recommendation:**
- Base table: `machine_instances` (more descriptive)
- View: `machines` (for joined/enriched data)
- Update both Python and Flutter to use `machine_instances`

**Changes needed:**
- Update Python: `machines_base` → `machine_instances`
- Update Flutter: `machines` view → `machine_instances` table
- Create migration to rename table if needed

## Impact Analysis

### Current Behavior
1. ✅ Python backend CAN update machine status (uses `machines_base`)
2. ❌ Flutter app CANNOT update machine status (uses `machines` view)
3. ⚠️ Recipe starts but machine status update fails silently

### After Fix
1. ✅ Python backend continues working
2. ✅ Flutter app can update machine status
3. ✅ Machine status correctly shows 'running' when recipe starts

## Testing Checklist

After implementing fix:

- [ ] Recipe starts from Flutter app
- [ ] Machine status updates to 'running'
- [ ] `current_process_id` is set correctly
- [ ] No PostgrestException thrown
- [ ] Python backend still works (if you changed table names)
- [ ] Machine status updates to 'idle' when recipe completes

## Next Steps

1. **IMMEDIATE**: Check Supabase database to verify table names
2. **FIX**: Update Flutter app to use correct base table
3. **TEST**: Verify recipe start/stop flow works end-to-end
4. **CLEANUP**: Standardize table naming across Python and Flutter
5. **DOCUMENT**: Update CLAUDE.md with correct table architecture
