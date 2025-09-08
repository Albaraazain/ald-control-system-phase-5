"""
Raw socket valve control - no imports needed.
"""
import socket
import struct

# HARDCODED CONFIGURATION
PLC_IP = "192.168.1.10"  # Change to your PLC IP
PLC_PORT = 502
VALVE_ADDRESS = 10  # Modbus coil address

# Create Modbus TCP packet to write single coil (Function code 5)
transaction_id = 1
protocol_id = 0
unit_id = 1
function_code = 5  # Write Single Coil
value = 0xFF00  # 0xFF00 = ON, 0x0000 = OFF

# Build Modbus TCP message
message = struct.pack('>HHHBBHH',
    transaction_id,  # Transaction ID
    protocol_id,     # Protocol ID (always 0 for Modbus)
    6,              # Length (6 bytes follow)
    unit_id,        # Unit ID
    function_code,  # Function code 5 (Write Single Coil)
    VALVE_ADDRESS,  # Coil address
    value          # Value (0xFF00 = ON)
)

# Send to PLC
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((PLC_IP, PLC_PORT))
sock.send(message)
response = sock.recv(12)
sock.close()

print(f"Sent ON command to valve at address {VALVE_ADDRESS}")
print(f"Response: {response.hex()}")