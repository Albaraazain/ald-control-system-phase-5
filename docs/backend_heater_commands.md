# Backend Heater Control Guide

This guide explains how to control the Backend Heater using the test tools.

## Using the Automated Script

The easiest way is to use the provided script:

```bash
./backend_heater_test.sh
```

This will:
1. Turn on the heater
2. Set temperature to 22°C
3. Read current temperature
4. Monitor temperature continuously

## Manual Commands

If you prefer to run commands individually:

### 1. Turn on the Backend Heater

```bash
python -m debug.test_modbus_write --address 0 --type binary --value 1
```

This writes a value of 1 (ON) to Modbus address 0, which is the power control for the Backend Heater.

### 2. Set the Temperature

```bash
python -m debug.test_modbus_write --address 2000 --type float --value 22.0
```

This sets the temperature setpoint to 22°C by writing a float value to Modbus address 2000.

### 3. Read Current Temperature

```bash
python -m debug.test_modbus_read --address 2016 --type float
```

This reads the current temperature from Modbus address 2016.

### 4. Monitor Temperature Continuously

```bash
python -m debug.test_modbus_read --address 2016 --type float --monitor 2.0
```

This continuously reads the temperature every 2 seconds so you can see it change.

## Turning Off the Heater

When you're done, turn off the heater:

```bash
python -m debug.test_modbus_write --address 0 --type binary --value 0
```

## Troubleshooting

If you encounter errors:

1. **Data Type Issues**: If the commands fail with a data type error, try using a different data type:
   ```bash
   # If float doesn't work, try int32
   python -m debug.test_modbus_write --address 2000 --type int32 --value 22
   python -m debug.test_modbus_read --address 2016 --type int32
   ```

2. **Address Issues**: If the system can't communicate with these addresses, check:
   - The PLC connection (IP, port)
   - The Modbus slave ID (default is 1)
   - If the addresses are correct in the database

3. **Response Time**: Heaters may take time to respond. Monitor the temperature for a few minutes to see changes.

## Parameter Information

Based on your database:

| Parameter | ID | Modbus Address | Data Type |
|-----------|----|--------------:|-----------|
| Power On | 73f16b0e-6a82-4027-a1cf-66bfa16dba69 | 0 | binary |
| Temperature Set | 9c99ed1b-1c30-4536-8ac1-3099f99a5afe | 2000 | float |
| Temperature Read | 62c28aac-7300-4d3d-85c7-f043c3226439 | 2016 | float |