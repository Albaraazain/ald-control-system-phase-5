"""
Standalone valve control - no dependencies on project code.
"""
from pymodbus.client import ModbusTcpClient

# HARDCODED CONFIGURATION
PLC_IP = "10.5.5.80"  # Your PLC IP from .env
PLC_PORT = 502
VALVE_ADDRESS = 10  # Modbus coil address for valve

# Connect and turn on valve
client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
client.connect()

# Write True (1) to turn valve ON
client.write_coil(VALVE_ADDRESS, True)
print(f"Valve at address {VALVE_ADDRESS} turned ON")

client.close()