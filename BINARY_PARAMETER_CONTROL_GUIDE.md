# Binary Parameter Control Guide

## ✅ Verified Working Configuration

**Pump Parameter (Vacuum Pump):**
- **Component**: Vacuum Pump
- **Parameter Name**: `power_on`
- **Parameter ID**: `9917618c-7325-4771-a771-65b42c6d6c73`
- **Address**: 10
- **Type**: Coil (binary digital output)
- **Database Config**:
  - `data_type`: `binary`
  - `read_modbus_type`: `coil`
  - `write_modbus_type`: `coil`

## ✅ How to Control Binary Parameters Correctly

### Method 1: Using Parameter ID (RECOMMENDED)
```python
from src.db import get_supabase

supabase = get_supabase()

# Turn pump ON
supabase.table('parameter_control_commands').insert({
    'component_parameter_id': '9917618c-7325-4771-a771-65b42c6d6c73',
    'parameter_name': 'power_on',
    'target_value': 1,
    'machine_id': 'ald-ctrl-001'
}).execute()

# Turn pump OFF
supabase.table('parameter_control_commands').insert({
    'component_parameter_id': '9917618c-7325-4771-a771-65b42c6d6c73',
    'parameter_name': 'power_on',
    'target_value': 0,
    'machine_id': 'ald-ctrl-001'
}).execute()
```

### Method 2: Using Parameter Name (if unique)
```python
supabase.table('parameter_control_commands').insert({
    'parameter_name': 'power_on',
    'target_value': 1,
    'machine_id': 'ald-ctrl-001'
}).execute()
```
⚠️ **Warning**: If multiple components have `power_on` parameters, this may target the wrong one!

### Method 3: Using Address Override (Advanced)
```python
supabase.table('parameter_control_commands').insert({
    'parameter_name': 'pump_direct',  # Any name for logging
    'write_modbus_address': 10,
    'data_type': 'binary',  # CRITICAL: Must be 'binary' for coils!
    'target_value': 1,
    'machine_id': 'ald-ctrl-001'
}).execute()
```
⚠️ **Critical**: When using address override, **always set `data_type='binary'`** for coils!

## ❌ Common Mistakes

### Mistake 1: Using Float Type for Binary
```python
# ❌ WRONG - This writes to holding register instead of coil
{
    'write_modbus_address': 10,
    'data_type': 'float',  # Wrong type!
    'target_value': 0
}
```

### Mistake 2: Missing Data Type on Override
```python
# ❌ WRONG - Defaults to 'float'
{
    'write_modbus_address': 10,
    # data_type missing - defaults to 'float'
    'target_value': 0
}
```

### Mistake 3: Using Wrong Parameter Name
```python
# ❌ WRONG - No parameter named 'pump_1' exists
{
    'parameter_name': 'pump_1',  # Should be 'power_on'
    'target_value': 0
}
```

## 🔧 Troubleshooting

### Pump Not Turning Off/On?

1. **Check the command succeeded**:
   ```sql
   SELECT * FROM parameter_control_commands 
   WHERE created_at > NOW() - INTERVAL '1 hour'
   ORDER BY created_at DESC 
   LIMIT 10;
   ```

2. **Look for the correct log messages**:
   - ✅ **Coil write**: "Successfully wrote OFF/ON to coil 10"
   - ❌ **Float write**: "Successfully wrote float 0.0 to address 10"

3. **Test directly from terminal**:
   ```bash
   python test_pump_auto.py
   ```
   This will test both coil and register writes to verify which method controls the pump.

4. **Verify parameter configuration**:
   ```python
   from src.db import get_supabase
   supabase = get_supabase()
   result = supabase.table('component_parameters_full') \
       .select('*') \
       .eq('id', '9917618c-7325-4771-a771-65b42c6d6c73') \
       .execute()
   print(result.data[0])
   ```

## 📋 Binary Parameters in System

All binary (on/off) parameters should use:
- `data_type`: `binary`
- `write_modbus_type`: `coil` (or `holding` if stored in register)

**Confirmed Binary Parameters:**
- Vacuum Pump (`power_on` @ address 10) - coil
- Nitrogen Generator (`power_on` @ address 37) - coil  
- All heaters (`power_on`) - coils
- All valves (`valve_state`) - coils
- Exhaust Gate Valve - coil

## ✅ Verification Test

Run this to verify pump control works:
```bash
python test_pump_auto.py
```

Or test via plc_manager directly:
```python
from src.plc.manager import plc_manager
import asyncio

async def test():
    await plc_manager.initialize()
    
    pump_id = '9917618c-7325-4771-a771-65b42c6d6c73'
    
    await plc_manager.write_parameter(pump_id, 1.0)  # ON
    await asyncio.sleep(2)
    await plc_manager.write_parameter(pump_id, 0.0)  # OFF
    
    await plc_manager.disconnect()

asyncio.run(test())
```

## 🎯 Summary

- ✅ Database is configured correctly
- ✅ Code uses correct COIL writes for binary types
- ✅ Pump responds to COIL writes at address 10
- ⚠️ Always use `component_parameter_id` when possible
- ⚠️ If using address override, set `data_type='binary'`
- ⚠️ Value of 0 = OFF, Value > 0 = ON


























