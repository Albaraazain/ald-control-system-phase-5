#!/usr/bin/env python3
"""
Modbus Debug CLI Tool

A simple command-line interface for directly reading and writing Modbus addresses
using the ALD control system's specific PLC communication setup.

Usage:
    python modbus_debug_cli.py

This tool provides direct access to Modbus operations using the same
communication methods as the main ALD control system.
"""

import asyncio
import sys
import os
from typing import Optional, Dict, Any, List
from pymodbus.client import ModbusTcpClient
import struct

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import PLC_CONFIG, PLC_BYTE_ORDER
from src.log_setup import logger
from src.plc.communicator import PLCCommunicator
from src.plc.manager import plc_manager


class ModbusDebugCLI:
    """CLI interface for direct Modbus debugging."""
    
    def __init__(self):
        self.communicator = None
        self.connected = False
        self.byte_order = PLC_BYTE_ORDER
        self._last_connect_config = PLC_CONFIG
        
    async def connect(self) -> bool:
        """Connect to the PLC using the system's configuration."""
        try:
            print("Connecting to PLC...")
            print(f"Configuration: {PLC_CONFIG}")
            
            # Create communicator with system configuration
            self.communicator = PLCCommunicator(
                plc_ip=PLC_CONFIG['ip_address'],
                port=PLC_CONFIG['port'],
                hostname=PLC_CONFIG.get('hostname'),
                auto_discover=PLC_CONFIG.get('auto_discover', False),
                connection_timeout=10,
                retries=3
            )
            
            # Connect
            success = self.communicator.connect()
            if success:
                self.connected = True
                print(f"✅ Connected to PLC at {self.communicator._current_ip}:{self.communicator.port}")
                print(f"Slave ID: {self.communicator.slave_id}")
                print(f"Byte Order: {self.byte_order}")
                return True
            else:
                print("❌ Failed to connect to PLC")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the PLC."""
        if self.communicator and self.connected:
            self.communicator.disconnect()
            self.connected = False
            print("Disconnected from PLC")

    def _ensure_connection(self) -> bool:
        """Ensure the underlying Modbus socket is connected; attempt reconnect if needed."""
        # If never connected, try full connect
        if not self.connected or not self.communicator:
            return False
        try:
            client_ok = (
                getattr(self.communicator, 'client', None) is not None
                and self.communicator.client.is_socket_open()
            )
        except Exception:
            client_ok = False

        if client_ok:
            return True

        # Attempt a reconnect using the communicator
        print("Reconnecting to PLC...")
        try:
            if self.communicator.connect():
                print(
                    f"✅ Reconnected to PLC at {self.communicator._current_ip}:{self.communicator.port}"
                )
                self.connected = True
                return True
        except Exception as e:
            print(f"❌ Reconnection failed: {e}")
        return False

    def _is_ok_default(self, result) -> bool:
        """Default success predicate: non-None and not Modbus isError()."""
        if result is None:
            return False
        # If it's a Modbus response object with isError(), require not error
        try:
            if hasattr(result, 'isError') and callable(result.isError):
                return not result.isError()
        except Exception:
            pass
        return True

    def _retry_value_op(self, fn, is_ok=None, attempts: int = 2):
        """Run a value-returning op; on failure, reconnect and retry up to attempts."""
        predicate = is_ok or self._is_ok_default
        last_err = None
        for i in range(attempts):
            try:
                result = fn()
                if predicate(result):
                    return result
            except Exception as e:
                last_err = e
            # reconnect then retry
            print("Reconnecting to PLC...")
            try:
                # hard reconnect for reliability
                if self.communicator:
                    self.communicator.disconnect()
                self.connected = False
            except Exception:
                pass
            if self.communicator and self.communicator.connect():
                print(
                    f"✅ Reconnected to PLC at {self.communicator._current_ip}:{self.communicator.port}"
                )
                self.connected = True
            else:
                print("❌ Reconnect attempt failed")
        if last_err:
            print(f"❌ Operation failed after {attempts} attempts: {last_err}")
        return None

    def _retry_bool_op(self, fn, attempts: int = 2) -> bool:
        """Run a bool-returning op; on failure, reconnect and retry up to attempts."""
        last_err = None
        for i in range(attempts):
            try:
                ok = bool(fn())
                if ok:
                    return True
            except Exception as e:
                last_err = e
            # reconnect then retry
            print("Reconnecting to PLC...")
            try:
                if self.communicator:
                    self.communicator.disconnect()
                self.connected = False
            except Exception:
                pass
            if self.communicator and self.communicator.connect():
                print(
                    f"✅ Reconnected to PLC at {self.communicator._current_ip}:{self.communicator.port}"
                )
                self.connected = True
            else:
                print("❌ Reconnect attempt failed")
        if last_err:
            print(f"❌ Operation failed after {attempts} attempts: {last_err}")
        return False
    
    def read_float(self, address: int) -> Optional[float]:
        """Read a 32-bit float from the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return None
        
        try:
            value = self._retry_value_op(
                lambda: self.communicator.read_float(address),
                is_ok=lambda v: v is not None
            )
            if value is not None:
                print(f"📖 Float at address {address}: {value}")
            else:
                print(f"❌ Failed to read float from address {address}")
            return value
        except Exception as e:
            print(f"❌ Error reading float: {e}")
            return None
    
    def write_float(self, address: int, value: float) -> bool:
        """Write a 32-bit float to the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return False
        
        try:
            success = self._retry_bool_op(
                lambda: self.communicator.write_float(address, value)
            )
            if success:
                print(f"✅ Wrote float {value} to address {address}")
            else:
                print(f"❌ Failed to write float {value} to address {address}")
            return success
        except Exception as e:
            print(f"❌ Error writing float: {e}")
            return False
    
    def read_integer_32bit(self, address: int) -> Optional[int]:
        """Read a 32-bit integer from the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return None
        
        try:
            value = self._retry_value_op(
                lambda: self.communicator.read_integer_32bit(address),
                is_ok=lambda v: v is not None
            )
            if value is not None:
                print(f"📖 32-bit integer at address {address}: {value}")
            else:
                print(f"❌ Failed to read 32-bit integer from address {address}")
            return value
        except Exception as e:
            print(f"❌ Error reading 32-bit integer: {e}")
            return None
    
    def write_integer_32bit(self, address: int, value: int) -> bool:
        """Write a 32-bit integer to the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return False
        
        try:
            success = self._retry_bool_op(
                lambda: self.communicator.write_integer_32bit(address, value)
            )
            if success:
                print(f"✅ Wrote 32-bit integer {value} to address {address}")
            else:
                print(f"❌ Failed to write 32-bit integer {value} to address {address}")
            return success
        except Exception as e:
            print(f"❌ Error writing 32-bit integer: {e}")
            return False
    
    def read_integer_16bit(self, address: int) -> Optional[int]:
        """Read a 16-bit integer from the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return None
        
        try:
            def _op():
                return self.communicator.client.read_holding_registers(
                    address, count=1, slave=self.communicator.slave_id
                )
            result = self._retry_value_op(_op, is_ok=lambda r: r is not None and not r.isError())
            if not result.isError():
                value = result.registers[0]
                print(f"📖 16-bit integer at address {address}: {value}")
                return value
            else:
                print(f"❌ Failed to read 16-bit integer from address {address}: {result}")
                return None
        except Exception as e:
            print(f"❌ Error reading 16-bit integer: {e}")
            return None
    
    def write_integer_16bit(self, address: int, value: int) -> bool:
        """Write a 16-bit integer to the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return False
        
        try:
            def _op():
                return self.communicator.client.write_register(
                    address, value, slave=self.communicator.slave_id
                )
            result = self._retry_value_op(_op, is_ok=lambda r: r is not None and not r.isError())
            success = (result is not None and not result.isError())
            if success:
                print(f"✅ Wrote 16-bit integer {value} to address {address}")
            else:
                print(f"❌ Failed to write 16-bit integer {value} to address {address}: {result}")
            return success
        except Exception as e:
            print(f"❌ Error writing 16-bit integer: {e}")
            return False
    
    def read_coil(self, address: int) -> Optional[bool]:
        """Read a coil (binary) value from the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return None
        
        try:
            result = self._retry_value_op(
                lambda: self.communicator.read_coils(address, count=1),
                is_ok=lambda r: isinstance(r, list) and len(r) >= 1
            )
            if result is not None:
                value = result[0]
                print(f"📖 Coil at address {address}: {'ON' if value else 'OFF'}")
                return value
            else:
                print(f"❌ Failed to read coil from address {address}")
                return None
        except Exception as e:
            print(f"❌ Error reading coil: {e}")
            return None
    
    def write_coil(self, address: int, value: bool) -> bool:
        """Write a coil (binary) value to the specified address."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return False
        
        try:
            success = self._retry_bool_op(
                lambda: self.communicator.write_coil(address, value)
            )
            if success:
                print(f"✅ Wrote coil {address}: {'ON' if value else 'OFF'}")
            else:
                print(f"❌ Failed to write coil {address}: {'ON' if value else 'OFF'}")
            return success
        except Exception as e:
            print(f"❌ Error writing coil: {e}")
            return False
    
    def read_holding_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        """Read multiple holding registers."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return None
        
        try:
            def _op():
                return self.communicator.client.read_holding_registers(
                    address, count=count, slave=self.communicator.slave_id
                )
            result = self._retry_value_op(_op, is_ok=lambda r: r is not None and not r.isError())
            if not result.isError():
                values = result.registers
                print(f"📖 Holding registers {address}-{address+count-1}: {values}")
                return values
            else:
                print(f"❌ Failed to read holding registers: {result}")
                return None
        except Exception as e:
            print(f"❌ Error reading holding registers: {e}")
            return None
    
    def write_holding_registers(self, address: int, values: List[int]) -> bool:
        """Write multiple holding registers."""
        if not self.connected or not self._ensure_connection():
            print("❌ Not connected to PLC")
            return False
        
        try:
            def _op():
                return self.communicator.client.write_registers(
                    address, values, slave=self.communicator.slave_id
                )
            result = self._retry_value_op(_op, is_ok=lambda r: r is not None and not r.isError())
            success = (result is not None and not result.isError())
            if success:
                print(f"✅ Wrote holding registers {address}-{address+len(values)-1}: {values}")
            else:
                print(f"❌ Failed to write holding registers: {result}")
            return success
        except Exception as e:
            print(f"❌ Error writing holding registers: {e}")
            return False
    
    def show_known_addresses(self):
        """Display known Modbus addresses from the modbus_addresses file."""
        print("\n📋 Known Modbus Addresses:")
        print("=" * 50)
        
        try:
            with open('modbus_addresses', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        print(f"  {line}")
        except FileNotFoundError:
            print("  No modbus_addresses file found")
        except Exception as e:
            print(f"  Error reading modbus_addresses file: {e}")
    
    def show_menu(self):
        """Display the main menu."""
        print("\n" + "="*60)
        print("🔧 MODBUS DEBUG CLI - ALD Control System")
        print("="*60)
        print("1.  Read Float (32-bit)")
        print("2.  Write Float (32-bit)")
        print("3.  Read 32-bit Integer")
        print("4.  Write 32-bit Integer")
        print("5.  Read 16-bit Integer")
        print("6.  Write 16-bit Integer")
        print("7.  Read Coil (Binary)")
        print("8.  Write Coil (Binary)")
        print("9.  Read Multiple Holding Registers")
        print("10. Write Multiple Holding Registers")
        print("11. Show Known Addresses")
        print("12. Test Connection")
        print("13. Show Configuration")
        print("0.  Exit")
        print("="*60)
    
    async def run(self):
        """Run the CLI main loop."""
        print("🚀 Starting Modbus Debug CLI...")
        
        # Connect to PLC
        if not await self.connect():
            print("❌ Cannot proceed without PLC connection")
            return
        
        try:
            while True:
                self.show_menu()
                try:
                    choice = input("\nEnter your choice (0-13): ").strip()
                except EOFError:
                    print("\nInput closed. Exiting...")
                    break
                
                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '1':
                    await self.handle_read_float()
                elif choice == '2':
                    await self.handle_write_float()
                elif choice == '3':
                    await self.handle_read_32bit_int()
                elif choice == '4':
                    await self.handle_write_32bit_int()
                elif choice == '5':
                    await self.handle_read_16bit_int()
                elif choice == '6':
                    await self.handle_write_16bit_int()
                elif choice == '7':
                    await self.handle_read_coil()
                elif choice == '8':
                    await self.handle_write_coil()
                elif choice == '9':
                    await self.handle_read_multiple_registers()
                elif choice == '10':
                    await self.handle_write_multiple_registers()
                elif choice == '11':
                    self.show_known_addresses()
                elif choice == '12':
                    await self.handle_test_connection()
                elif choice == '13':
                    self.show_configuration()
                else:
                    print("❌ Invalid choice. Please try again.")
                
                try:
                    input("\nPress Enter to continue...")
                except EOFError:
                    print("")
                    break
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
        finally:
            self.disconnect()
    
    async def handle_read_float(self):
        """Handle read float operation."""
        try:
            address = int(input("Enter address: "))
            self.read_float(address)
        except ValueError:
            print("❌ Invalid address. Please enter a number.")
    
    async def handle_write_float(self):
        """Handle write float operation."""
        try:
            address = int(input("Enter address: "))
            value = float(input("Enter value: "))
            self.write_float(address, value)
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
    
    async def handle_read_32bit_int(self):
        """Handle read 32-bit integer operation."""
        try:
            address = int(input("Enter address: "))
            self.read_integer_32bit(address)
        except ValueError:
            print("❌ Invalid address. Please enter a number.")
    
    async def handle_write_32bit_int(self):
        """Handle write 32-bit integer operation."""
        try:
            address = int(input("Enter address: "))
            value = int(input("Enter value: "))
            self.write_integer_32bit(address, value)
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
    
    async def handle_read_16bit_int(self):
        """Handle read 16-bit integer operation."""
        try:
            address = int(input("Enter address: "))
            self.read_integer_16bit(address)
        except ValueError:
            print("❌ Invalid address. Please enter a number.")
    
    async def handle_write_16bit_int(self):
        """Handle write 16-bit integer operation."""
        try:
            address = int(input("Enter address: "))
            value = int(input("Enter value: "))
            self.write_integer_16bit(address, value)
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
    
    async def handle_read_coil(self):
        """Handle read coil operation."""
        try:
            address = int(input("Enter address: "))
            self.read_coil(address)
        except ValueError:
            print("❌ Invalid address. Please enter a number.")
    
    async def handle_write_coil(self):
        """Handle write coil operation."""
        try:
            address = int(input("Enter address: "))
            value_str = input("Enter value (ON/OFF or 1/0): ").strip().upper()
            if value_str in ['ON', '1', 'TRUE']:
                value = True
            elif value_str in ['OFF', '0', 'FALSE']:
                value = False
            else:
                print("❌ Invalid value. Use ON/OFF or 1/0")
                return
            self.write_coil(address, value)
        except ValueError:
            print("❌ Invalid address. Please enter a number.")
    
    async def handle_read_multiple_registers(self):
        """Handle read multiple registers operation."""
        try:
            address = int(input("Enter starting address: "))
            count = int(input("Enter count: "))
            self.read_holding_registers(address, count)
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
    
    async def handle_write_multiple_registers(self):
        """Handle write multiple registers operation."""
        try:
            address = int(input("Enter starting address: "))
            values_str = input("Enter values (comma-separated): ")
            values = [int(x.strip()) for x in values_str.split(',')]
            self.write_holding_registers(address, values)
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
    
    async def handle_test_connection(self):
        """Handle test connection operation."""
        if self.connected:
            print("✅ Connection is active")
            print(f"   IP: {self.communicator._current_ip}")
            print(f"   Port: {self.communicator.port}")
            print(f"   Slave ID: {self.communicator.slave_id}")
        else:
            print("❌ Not connected")
    
    def show_configuration(self):
        """Show current configuration."""
        print("\n📋 Current Configuration:")
        print("=" * 40)
        print(f"PLC IP: {PLC_CONFIG['ip_address']}")
        print(f"PLC Port: {PLC_CONFIG['port']}")
        print(f"Byte Order: {self.byte_order}")
        if PLC_CONFIG.get('hostname'):
            print(f"Hostname: {PLC_CONFIG['hostname']}")
        if PLC_CONFIG.get('auto_discover'):
            print("Auto Discovery: Enabled")
        else:
            print("Auto Discovery: Disabled")


async def main():
    """Main entry point."""
    cli = ModbusDebugCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
