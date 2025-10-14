# PLCManager Setpoint Methods Fix

## Issue Discovered

When Terminal 1 was running with the new setpoint synchronization code, it encountered this error:

```
Failed to read setpoints: 'PLCManager' object has no attribute 'read_all_setpoints'
```

## Root Cause

The new methods `read_setpoint()` and `read_all_setpoints()` were added to:
- ✅ `src/plc/interface.py` (abstract interface)
- ✅ `src/plc/real_plc.py` (real PLC implementation)
- ✅ `src/plc/simulation.py` (simulation implementation)

But NOT to:
- ❌ `src/plc/manager.py` (PLCManager wrapper class)

## Solution

Added the missing proxy methods to `PLCManager`:

### Method 1: `read_setpoint()`

```python
async def read_setpoint(self, parameter_id: str) -> Optional[float]:
    """
    Read the setpoint value for a parameter from the PLC.
    
    This reads from write_modbus_address to detect external changes.
    """
    if self._plc is None:
        raise RuntimeError("Not connected to PLC")
    
    setpoint = await self._plc.read_setpoint(parameter_id)
    if setpoint is not None:
        logger.debug(f"PLC read setpoint {parameter_id}: {setpoint}")
    return setpoint
```

### Method 2: `read_all_setpoints()`

```python
async def read_all_setpoints(self) -> Dict[str, float]:
    """
    Read all setpoint values from the PLC.
    
    Returns:
        Dict[str, float]: Dictionary of parameter IDs to setpoint values
    """
    if self._plc is None:
        raise RuntimeError("Not connected to PLC")
    
    setpoint_values = await self._plc.read_all_setpoints()
    logger.debug(f"PLC read all setpoints: {len(setpoint_values)} values retrieved")
    return setpoint_values
```

## Why This Happened

The `PLCManager` class acts as a singleton wrapper/proxy around the actual PLC interface implementations. It provides:

1. Singleton pattern for shared PLC connection across terminals
2. Consistent API for all PLC operations
3. Centralized logging for PLC operations

When new methods are added to the PLC interface, they must also be exposed through the manager.

## Impact

This fix allows Terminal 1 to successfully:
- Read setpoints from the PLC every 1 second
- Detect external parameter changes
- Synchronize database with PLC state
- Log external changes with detailed information

## Verification

Terminal 1 now runs without the error and can:
- ✅ Call `plc_manager.read_all_setpoints()`
- ✅ Synchronize setpoints to database
- ✅ Detect external changes (when implemented on real hardware)

## Files Modified

- `src/plc/manager.py` - Added `read_setpoint()` and `read_all_setpoints()` methods

## Lesson Learned

When adding new methods to the PLC interface hierarchy:

1. ✅ Add to `src/plc/interface.py` (abstract base)
2. ✅ Implement in `src/plc/real_plc.py`
3. ✅ Implement in `src/plc/simulation.py`
4. ✅ **Expose through `src/plc/manager.py`** ← This step was initially missed

The manager is the public API that all terminals use, so all new interface methods must be proxied through it.

