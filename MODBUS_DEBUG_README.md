# Modbus Debug CLI Tool

A simple command-line interface for directly reading and writing Modbus addresses using the ALD control system's specific PLC communication setup.

## Features

- **Direct Modbus Access**: Read/write using the same communication methods as the main system
- **Multiple Data Types**: Support for floats, 32-bit integers, 16-bit integers, and coils (binary)
- **System Integration**: Uses your existing PLC configuration and byte order settings
- **Interactive Menu**: Easy-to-use command-line interface
- **Known Addresses**: Display addresses from your `modbus_addresses` file

## Usage

```bash
# Run the debug tool
python modbus_debug_cli.py
```

## Menu Options

1. **Read Float (32-bit)** - Read 32-bit floating point values
2. **Write Float (32-bit)** - Write 32-bit floating point values  
3. **Read 32-bit Integer** - Read 32-bit integer values
4. **Write 32-bit Integer** - Write 32-bit integer values
5. **Read 16-bit Integer** - Read 16-bit integer values
6. **Write 16-bit Integer** - Write 16-bit integer values
7. **Read Coil (Binary)** - Read binary/coil values (ON/OFF)
8. **Write Coil (Binary)** - Write binary/coil values (ON/OFF)
9. **Read Multiple Holding Registers** - Read multiple registers at once
10. **Write Multiple Holding Registers** - Write multiple registers at once
11. **Show Known Addresses** - Display addresses from `modbus_addresses` file
12. **Test Connection** - Verify PLC connection status
13. **Show Configuration** - Display current PLC configuration

## Configuration

The tool automatically uses your system's PLC configuration from:
- `PLC_IP` environment variable (default: 192.168.1.100)
- `PLC_PORT` environment variable (default: 502)
- `PLC_BYTE_ORDER` environment variable (default: badc)
- `PLC_HOSTNAME` environment variable (optional)
- `PLC_AUTO_DISCOVER` environment variable (optional)

## Examples

### Reading a Float
```
Enter your choice (0-13): 1
Enter address: 2066
📖 Float at address 2066: 25.5
```

### Writing a Coil
```
Enter your choice (0-13): 8
Enter address: 11
Enter value (ON/OFF or 1/0): ON
✅ Wrote coil 11: ON
```

### Reading Multiple Registers
```
Enter your choice (0-13): 9
Enter starting address: 2066
Enter count: 3
📖 Holding registers 2066-2068: [25, 100, 0]
```

## Known Addresses

Based on your `modbus_addresses` file:
- Pressure gauge on/off: 2072
- Exhaust on/off: 11
- N2 generator on/off: 37
- Pump on/off: 10
- Setpoint MFC: 2066
- Current value read MFC: 2082

## Safety Notes

⚠️ **Warning**: This tool provides direct access to your PLC. Be careful when writing values as they can affect your machine's operation.

- Always verify addresses before writing
- Start with read operations to understand current values
- Use appropriate data types for each address
- Test with non-critical parameters first

## Troubleshooting

### Connection Issues
- Check that your PLC is powered on and accessible
- Verify the IP address and port in your configuration
- Ensure the PLC is on the same network

### Data Type Issues
- Use the correct data type for each address
- Check the byte order configuration
- Verify register addresses are correct

### Permission Issues
- Ensure you have proper permissions to access the PLC
- Check that no other applications are using the PLC connection



