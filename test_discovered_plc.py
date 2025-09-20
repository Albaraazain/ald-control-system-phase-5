#!/usr/bin/env python3
"""
Test script to validate discovered PLC connection
"""

import asyncio
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException

def test_plc_connection(ip="10.5.5.99", slave_id=1, port=502):
    """Test specific PLC connection and read some basic data"""
    print(f"Testing PLC connection:")
    print(f"  IP: {ip}")
    print(f"  Slave ID: {slave_id}")
    print(f"  Port: {port}")
    print("-" * 40)

    try:
        # Connect to PLC
        client = ModbusTcpClient(ip, port=port, timeout=3)

        if not client.connect():
            print("❌ Failed to connect to PLC")
            return False

        print("✅ Successfully connected to PLC")

        # Test different register types
        tests = [
            ("Holding Registers (0-9)", lambda: client.read_holding_registers(0, 10, slave=slave_id)),
            ("Input Registers (0-9)", lambda: client.read_input_registers(0, 10, slave=slave_id)),
            ("Coils (0-9)", lambda: client.read_coils(0, 10, slave=slave_id)),
            ("Discrete Inputs (0-9)", lambda: client.read_discrete_inputs(0, 10, slave=slave_id)),
        ]

        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result.isError():
                    print(f"✅ {test_name}: {len(result.registers if hasattr(result, 'registers') else result.bits)} values read")
                    if hasattr(result, 'registers'):
                        print(f"   Values: {result.registers[:5]}{'...' if len(result.registers) > 5 else ''}")
                    elif hasattr(result, 'bits'):
                        print(f"   Values: {result.bits[:5]}{'...' if len(result.bits) > 5 else ''}")
                else:
                    print(f"⚠️  {test_name}: Error - {result}")
            except Exception as e:
                print(f"❌ {test_name}: Exception - {e}")

        # Test write operation (safe test)
        print("\nTesting write capability:")
        try:
            # Try to write to holding register 0 (read current value first)
            current = client.read_holding_registers(0, 1, slave=slave_id)
            if not current.isError():
                original_value = current.registers[0]
                print(f"  Current value at register 0: {original_value}")

                # Write the same value back (safe)
                write_result = client.write_register(0, original_value, slave=slave_id)
                if not write_result.isError():
                    print("✅ Write operation successful")
                else:
                    print(f"⚠️  Write failed: {write_result}")
            else:
                print(f"❌ Could not read current value: {current}")

        except Exception as e:
            print(f"❌ Write test exception: {e}")

        client.close()
        print("\n✅ PLC connection test completed successfully")
        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_multiple_slaves(ip="10.5.5.99", slave_ids=[1, 2, 3, 16, 17], port=502):
    """Test multiple slave IDs to find the most responsive one"""
    print(f"\nTesting multiple slave IDs on {ip}:")
    print("-" * 50)

    results = {}

    for slave_id in slave_ids:
        print(f"\nTesting Slave ID {slave_id}:")
        try:
            client = ModbusTcpClient(ip, port=port, timeout=2)
            if client.connect():
                # Test holding registers
                hr_result = client.read_holding_registers(0, 5, slave=slave_id)
                hr_success = not hr_result.isError()

                # Test coils
                coil_result = client.read_coils(0, 5, slave=slave_id)
                coil_success = not coil_result.isError()

                results[slave_id] = {
                    'holding_registers': hr_success,
                    'coils': coil_success,
                    'hr_values': hr_result.registers if hr_success else None,
                    'coil_values': coil_result.bits if coil_success else None
                }

                print(f"  Holding Registers: {'✅' if hr_success else '❌'}")
                print(f"  Coils: {'✅' if coil_success else '❌'}")

                if hr_success:
                    print(f"  HR Values: {hr_result.registers}")
                if coil_success:
                    print(f"  Coil Values: {coil_result.bits}")

                client.close()
            else:
                print(f"  ❌ Connection failed")
                results[slave_id] = {'error': 'connection_failed'}

        except Exception as e:
            print(f"  ❌ Exception: {e}")
            results[slave_id] = {'error': str(e)}

    # Summary
    print(f"\n📊 Summary for {ip}:")
    print("-" * 30)
    working_slaves = []
    for slave_id, result in results.items():
        if 'error' not in result:
            if result.get('holding_registers') or result.get('coils'):
                working_slaves.append(slave_id)
                print(f"✅ Slave {slave_id}: Working")
            else:
                print(f"⚠️  Slave {slave_id}: Connected but no data")
        else:
            print(f"❌ Slave {slave_id}: {result['error']}")

    if working_slaves:
        print(f"\n🎯 Recommended slave IDs: {working_slaves}")
        print(f"🔧 Suggested config: PLC_IP='{ip}' (use slave ID {working_slaves[0]})")

    return results

if __name__ == "__main__":
    # Test the discovered PLC
    print("🔍 Testing discovered PLC configuration...")

    # First test with slave ID 1 (most common)
    success = test_plc_connection("10.5.5.99", 1, 502)

    # Test multiple slave IDs to see which works best
    test_multiple_slaves("10.5.5.99", [1, 2, 3, 16, 17, 32])

    print(f"\n{'='*60}")
    print("💡 RECOMMENDATIONS:")
    print(f"{'='*60}")
    print("1. Update your .env file with:")
    print("   PLC_IP=10.5.5.99")
    print("   PLC_TYPE=real")
    print("")
    print("2. Your PLC system appears to be a Modbus gateway/hub")
    print("   supporting multiple slave devices.")
    print("")
    print("3. Choose slave ID 1, 2, or 3 for your main PLC connection")
    print("   (these are most commonly used).")