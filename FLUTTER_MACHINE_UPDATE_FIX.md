# Flutter Machine Status Update Fix

## Problem

When starting a recipe, the Flutter app attempts to update machine status but fails with:

```
PostgrestException: cannot update view "machines", code: 55000
Details: Views that do not select from a single table or view are not automatically updatable.
```

**Location**: `start_recipe_use_case.dart:508` in `_updateMachineStatus()`

## Root Cause

The `machines` view joins multiple tables:
- `machine_instances` (base table with status, current_process_id, etc.)
- `machine_types` (reference table with machine type info)

PostgreSQL cannot automatically update multi-table views.

## Solution

### Option 1: Update Base Table Directly (RECOMMENDED)

Change the Flutter code to update `machine_instances` instead of `machines`:

**Before (BROKEN):**
```dart
Future<void> _updateMachineStatus(...) async {
  await _machinesRepository.update(
    machineId,
    {
      'current_status': 'running',
      'current_process_id': processExecutionId,
      'updated_at': DateTime.now().toIso8601String(),
    },
  );
}
```

**After (FIXED):**
```dart
Future<void> _updateMachineStatus(...) async {
  // Use machine_instances repository instead
  await _supabase
    .from('machine_instances')
    .update({
      'current_status': 'running',
      'current_process_id': processExecutionId,
      'updated_at': DateTime.now().toIso8601String(),
    })
    .eq('id', machineId);
}
```

### Option 2: Create INSTEAD OF Trigger (Alternative)

If you want to keep updating through the view, create an `INSTEAD OF UPDATE` trigger on the `machines` view:

```sql
-- Create trigger function
CREATE OR REPLACE FUNCTION update_machines_view()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE machine_instances
  SET
    current_status = COALESCE(NEW.current_status, OLD.current_status),
    current_process_id = COALESCE(NEW.current_process_id, OLD.current_process_id),
    updated_at = NOW()
  WHERE id = OLD.id;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to view
CREATE TRIGGER update_machines_instead
INSTEAD OF UPDATE ON machines
FOR EACH ROW
EXECUTE FUNCTION update_machines_view();
```

## Recommended Approach

**Use Option 1** - Update `machine_instances` directly because:
1. ✅ More explicit and clear what table is being modified
2. ✅ No database schema changes required
3. ✅ Better performance (no trigger overhead)
4. ✅ Easier to debug and maintain

## Files to Modify in Flutter App

1. `lib/features/process/use_cases/process_control/start_recipe_use_case.dart`
   - Line ~508: `_updateMachineStatus()` method
   - Change from `machines` repository to `machine_instances` table

2. Any other places that update machine status:
   - Search for: `.from('machines').update(`
   - Replace with: `.from('machine_instances').update(`

## Testing

After fix, verify:
```dart
// 1. Machine status updates successfully
// 2. No PostgrestException thrown
// 3. Recipe starts and machine shows 'running' status
// 4. current_process_id is set correctly
```

## Related Files in Python Backend

The Python backend correctly uses `machine_instances`:
- [machine_control_service.py](machine_control_service.py) - Uses `machine_instances` table
- No issues on backend side - this is Flutter-only problem
