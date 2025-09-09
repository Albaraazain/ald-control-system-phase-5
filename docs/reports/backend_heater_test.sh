#!/bin/bash
# Script to control the Backend Heater
# This script:
# 1. Turns on the Backend Heater
# 2. Sets the temperature to 22°C
# 3. Reads the current temperature
# 4. Continuously monitors the temperature

echo "===== BACKEND HEATER CONTROL TEST ====="

echo -e "\n1. Turning on Backend Heater (setting coil 0 to ON)..."
python -m debug.test_modbus_write --address 0 --type binary --value 1

echo -e "\n2. Setting temperature to 22°C (writing to register 2000)..."
python -m debug.test_modbus_write --address 2000 --type float --value 22.0

echo -e "\n3. Reading current temperature from register 2016..."
python -m debug.test_modbus_read --address 2016 --type float

echo -e "\n4. Starting continuous temperature monitoring (press Ctrl+C to stop)..."
echo "   This will show temperature changes as the heater works..."
python -m debug.test_modbus_read --address 2016 --type float --monitor 2.0