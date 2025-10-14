#!/usr/bin/env python3
"""
Automated test script to control pump at address 10.
Tests both COIL and HOLDING REGISTER writes.
"""
import time
import os
from pymodbus.client import ModbusTcpClient

# Configuration
PLC_IP = os.getenv("PLC_IP", "10.5.5.90")
PLC_PORT = int(os.getenv("PLC_PORT", 502))
PUMP_ADDRESS = 10

print("🔧 AUTOMATED PUMP CONTROL TEST")
print("="*60)
print(f"PLC IP: {PLC_IP}")
print(f"PLC Port: {PLC_PORT}")
print(f"Pump Address: {PUMP_ADDRESS}")
print("="*60)

client = ModbusTcpClient(PLC_IP, port=PLC_PORT)

# Connect
print(f"\n📡 Connecting to PLC...")
if not client.connect():
    print("❌ Failed to connect to PLC")
    exit(1)
print("✅ Connected to PLC")

# ============================================================
# TEST 1: COIL WRITES (Digital Output)
# ============================================================
print(f"\n{'='*60}")
print("TEST 1: COIL WRITES (Digital Output)")
print("="*60)

try:
    # Turn OFF via coil
    print(f"\n[1] Writing FALSE to COIL {PUMP_ADDRESS} (OFF)...")
    result = client.write_coil(PUMP_ADDRESS, False)
    if result.isError():
        print(f"   ❌ Write failed: {result}")
    else:
        print(f"   ✅ Write successful")
    
    # Read back coil
    result = client.read_coils(PUMP_ADDRESS, count=1)
    if not result.isError():
        state = result.bits[0]
        print(f"   📖 Coil readback: {state} ({'ON' if state else 'OFF'})")
    
    time.sleep(2)
    
    # Turn ON via coil
    print(f"\n[2] Writing TRUE to COIL {PUMP_ADDRESS} (ON)...")
    result = client.write_coil(PUMP_ADDRESS, True)
    if result.isError():
        print(f"   ❌ Write failed: {result}")
    else:
        print(f"   ✅ Write successful")
    
    # Read back coil
    result = client.read_coils(PUMP_ADDRESS, count=1)
    if not result.isError():
        state = result.bits[0]
        print(f"   📖 Coil readback: {state} ({'ON' if state else 'OFF'})")
    
    time.sleep(2)
    
    # Turn OFF via coil again
    print(f"\n[3] Writing FALSE to COIL {PUMP_ADDRESS} (OFF)...")
    result = client.write_coil(PUMP_ADDRESS, False)
    if result.isError():
        print(f"   ❌ Write failed: {result}")
    else:
        print(f"   ✅ Write successful")
    
    # Read back coil
    result = client.read_coils(PUMP_ADDRESS, count=1)
    if not result.isError():
        state = result.bits[0]
        print(f"   📖 Coil readback: {state} ({'ON' if state else 'OFF'})")
    
    print("\n✅ COIL test complete - Did you see the pump turn ON then OFF?")

except Exception as e:
    print(f"❌ COIL test failed with exception: {e}")

time.sleep(3)

# ============================================================
# TEST 2: HOLDING REGISTER WRITES
# ============================================================
print(f"\n{'='*60}")
print("TEST 2: HOLDING REGISTER WRITES")
print("="*60)

try:
    # Write 0 to register
    print(f"\n[1] Writing 0 to HOLDING REGISTER {PUMP_ADDRESS} (OFF)...")
    result = client.write_register(PUMP_ADDRESS, 0)
    if result.isError():
        print(f"   ❌ Write failed: {result}")
    else:
        print(f"   ✅ Write successful")
    
    # Read back register
    result = client.read_holding_registers(PUMP_ADDRESS, count=1)
    if not result.isError():
        value = result.registers[0]
        print(f"   📖 Register readback: {value}")
    
    time.sleep(2)
    
    # Write 1 to register
    print(f"\n[2] Writing 1 to HOLDING REGISTER {PUMP_ADDRESS} (ON)...")
    result = client.write_register(PUMP_ADDRESS, 1)
    if result.isError():
        print(f"   ❌ Write failed: {result}")
    else:
        print(f"   ✅ Write successful")
    
    # Read back register
    result = client.read_holding_registers(PUMP_ADDRESS, count=1)
    if not result.isError():
        value = result.registers[0]
        print(f"   📖 Register readback: {value}")
    
    time.sleep(2)
    
    # Write 0 to register again
    print(f"\n[3] Writing 0 to HOLDING REGISTER {PUMP_ADDRESS} (OFF)...")
    result = client.write_register(PUMP_ADDRESS, 0)
    if result.isError():
        print(f"   ❌ Write failed: {result}")
    else:
        print(f"   ✅ Write successful")
    
    # Read back register
    result = client.read_holding_registers(PUMP_ADDRESS, count=1)
    if not result.isError():
        value = result.registers[0]
        print(f"   📖 Register readback: {value}")
    
    print("\n✅ REGISTER test complete - Did you see the pump turn ON then OFF?")

except Exception as e:
    print(f"❌ REGISTER test failed with exception: {e}")

# Cleanup
client.close()
print("\n" + "="*60)
print("🏁 ALL TESTS COMPLETE")
print("="*60)
print("\n📋 RESULTS INTERPRETATION:")
print("   If TEST 1 (COIL) worked → Use data_type='binary' + write_modbus_type='coil'")
print("   If TEST 2 (REGISTER) worked → Use data_type='binary' + write_modbus_type='holding'")
print("   If NEITHER worked → Address 10 may not be the pump, or pump may be controlled elsewhere")
print("\n🔌 Disconnected from PLC")

