"""
Standalone valve control with comprehensive debugging and error handling.
No dependencies on project code - uses only pymodbus directly.
"""
from pymodbus.client import ModbusTcpClient
import time
import socket

# HARDCODED CONFIGURATION
PLC_IP = "10.5.5.80"  # Your PLC IP from .env
PLC_PORT = 502
VALVE_ADDRESS = 10  # Modbus coil address for valve
TIMEOUT = 5  # Connection timeout in seconds

def test_network_connectivity(ip, port):
    """Test if we can reach the PLC network endpoint."""
    print(f"\n=== Testing Network Connectivity ===")
    print(f"Target: {ip}:{port}")
    
    # Test 1: Basic socket connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    
    try:
        result = sock.connect_ex((ip, port))
        if result == 0:
            print(f"✅ Socket connection successful to {ip}:{port}")
            return True
        else:
            print(f"❌ Socket connection failed with error code: {result}")
            return False
    except socket.gaierror:
        print(f"❌ Hostname could not be resolved: {ip}")
        return False
    except socket.error as e:
        print(f"❌ Socket error: {e}")
        return False
    finally:
        sock.close()

def test_modbus_connection():
    """Test Modbus TCP connection with detailed debugging."""
    print(f"\n=== Testing Modbus Connection ===")
    
    # Create client with explicit parameters
    client = ModbusTcpClient(
        host=PLC_IP, 
        port=PLC_PORT,
        timeout=TIMEOUT,
        retries=3,
        retry_on_empty=True,
        close_comm_on_error=False
    )
    
    print(f"Created ModbusTcpClient:")
    print(f"  - Host: {PLC_IP}")
    print(f"  - Port: {PLC_PORT}")
    print(f"  - Timeout: {TIMEOUT}s")
    
    try:
        # Attempt connection
        print(f"\nAttempting to connect...")
        connection_result = client.connect()
        
        if connection_result:
            print(f"✅ Modbus connection successful!")
            print(f"  - Connected: {client.is_socket_open()}")
            
            # Test reading coil status first
            print(f"\n=== Testing Read Operation ===")
            print(f"Reading coil at address {VALVE_ADDRESS}...")
            
            try:
                read_result = client.read_coils(VALVE_ADDRESS, 1)
                
                if hasattr(read_result, 'isError') and read_result.isError():
                    print(f"❌ Read error: {read_result}")
                else:
                    current_state = read_result.bits[0] if hasattr(read_result, 'bits') else False
                    print(f"✅ Current valve state: {'ON' if current_state else 'OFF'}")
                    
                    # Now try to write
                    print(f"\n=== Testing Write Operation ===")
                    print(f"Writing True to coil at address {VALVE_ADDRESS}...")
                    
                    write_result = client.write_coil(VALVE_ADDRESS, True)
                    
                    if hasattr(write_result, 'isError') and write_result.isError():
                        print(f"❌ Write error: {write_result}")
                    else:
                        print(f"✅ Write successful!")
                        
                        # Verify the write
                        time.sleep(0.5)  # Small delay
                        verify_result = client.read_coils(VALVE_ADDRESS, 1)
                        if not verify_result.isError():
                            new_state = verify_result.bits[0]
                            print(f"✅ Verified valve state: {'ON' if new_state else 'OFF'}")
                        
            except Exception as e:
                print(f"❌ Modbus operation error: {e}")
                print(f"  - Error type: {type(e).__name__}")
                
        else:
            print(f"❌ Modbus connection failed!")
            print(f"  - Client socket open: {client.is_socket_open()}")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print(f"  - Error type: {type(e).__name__}")
        import traceback
        print(f"  - Traceback:")
        traceback.print_exc()
        
    finally:
        if client.is_socket_open():
            client.close()
            print(f"\nConnection closed.")

def main():
    """Main debugging function."""
    print("=" * 50)
    print("STANDALONE VALVE CONTROL DEBUGGER")
    print("=" * 50)
    
    # Step 1: Test basic network connectivity
    if not test_network_connectivity(PLC_IP, PLC_PORT):
        print("\n⚠️  Network connectivity test failed!")
        print("\nPossible issues:")
        print("1. PLC IP address is incorrect (current: {})".format(PLC_IP))
        print("2. PLC is not powered on or not on the network")
        print("3. Firewall is blocking port {} (Modbus)".format(PLC_PORT))
        print("4. You're not on the same network as the PLC")
        print("\nDebugging steps:")
        print("1. Ping the PLC: ping {}".format(PLC_IP))
        print("2. Check if port is open: nc -zv {} {}".format(PLC_IP, PLC_PORT))
        print("3. Verify PLC configuration and network settings")
        return
    
    # Step 2: Test Modbus connection
    test_modbus_connection()
    
    print("\n" + "=" * 50)
    print("DEBUGGING COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()