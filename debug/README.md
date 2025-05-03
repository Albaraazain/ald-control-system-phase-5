# Debugging Tools

This directory contains standalone test scripts to verify individual components of the ALD control system. These scripts are useful for:

1. Testing components in isolation before full system testing
2. Diagnosing issues in the field
3. Verifying PLC communication and hardware interfaces

## Available Test Scripts

| Script | Description | Usage |
| ------ | ----------- | ----- |
| `test_plc_connection.py` | Test basic PLC connectivity | `python test_plc_connection.py` |
| `test_supabase_connection.py` | Test Supabase database connectivity | `python test_supabase_connection.py` |
| `test_parameter_read.py` | Test reading a parameter from PLC | `python test_parameter_read.py [--param-id ID]` |
| `test_parameter_write.py` | Test writing a value to a PLC parameter | `python test_parameter_write.py [--param-id ID] [--value VALUE]` |
| `test_valve_control.py` | Test valve control operations | `python test_valve_control.py VALVE_NUMBER [--close] [--duration MS]` |
| `test_purge.py` | Test purge operations | `python test_purge.py [--duration MS]` |

## Usage Notes

1. **Environment Variables**: All scripts use the existing `.env` file from the parent directory, so make sure it's properly configured.

2. **PLC Simulator**: If testing without a real PLC, you may need to modify `plc/manager.py` to use the simulation PLC.

3. **Troubleshooting Steps**:
   - Check network connectivity to PLC
   - Verify Supabase credentials
   - Check Modbus address configurations
   - Ensure parameter IDs exist in the database

4. **Output**: The scripts use the same logging configuration as the main application, so check console output and the log file for results.

## Examples

Test PLC connection:
```
python test_plc_connection.py
```

Test controlling valve #1, keeping it open for 2 seconds:
```
python test_valve_control.py 1 --duration 2000
```

Test writing value to a parameter:
```
python test_parameter_write.py --param-id abc123 --value 75.5
```