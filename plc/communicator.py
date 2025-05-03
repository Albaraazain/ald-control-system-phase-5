# File: plc/communicator.py
"""
Provides low-level Modbus TCP communication with PLC.
"""
from pymodbus.client import ModbusTcpClient
import struct
import time
from log_setup import logger
from config import PLC_BYTE_ORDER

class PLCCommunicator:
    """
    A class to handle Modbus TCP communication between the system and PLC.
    Handles low-level communication protocols and data conversion.
    """
    def __init__(self, plc_ip='192.168.1.11', port=502, slave_id=1, byte_order=PLC_BYTE_ORDER):
        """Initialize the PLC communicator with connection parameters."""
        self.plc_ip = plc_ip
        self.port = port
        self.slave_id = slave_id
        self.client = None
        self.debug = True  # Set to False to disable debug messages
        self.byte_order = byte_order
        self.log("INFO", f"Using byte order: {self.byte_order}")
    
    def log(self, level, message):
        """Log messages using the application's logger."""
        if self.debug:
            if level == "DEBUG":
                logger.debug(message)
            elif level == "INFO":
                logger.info(message)
            elif level == "ERROR":
                logger.error(message)
    
    def connect(self):
        """Establish connection to the PLC."""
        self.log("DEBUG", f"Connecting to PLC at {self.plc_ip}:{self.port}")
        self.client = ModbusTcpClient(self.plc_ip, port=self.port)
        
        if self.client.connect():
            self.log("INFO", "Connected to PLC successfully")
            return True
        else:
            self.log("ERROR", "Failed to connect to PLC")
            return False
    
    def disconnect(self):
        """Close the connection to the PLC."""
        if self.client and self.client.is_socket_open():
            self.client.close()
            self.log("INFO", "Disconnected from PLC")
            return True
        return True
    
    def read_float(self, address):
        """
        Read a 32-bit float from the PLC using 'badc' format.
        
        Args:
            address: Starting register address
            
        Returns:
            Float value or None if read failed
        """
        if not self.client or not self.client.is_socket_open():
            self.log("ERROR", "Not connected to PLC")
            return None
            
        self.log("DEBUG", f"Reading float from address {address}")
        result = self.client.read_holding_registers(address, count=2, slave=self.slave_id)
        
        if result.isError():
            self.log("ERROR", f"Failed to read float: {result}")
            return None
            
        # Use the configured byte order
        self.log("DEBUG", f"Raw registers: {result.registers}")
        
        if self.byte_order == 'abcd':  # Big-endian
            raw_data = struct.pack('>HH', result.registers[0], result.registers[1])
            float_value = struct.unpack('>f', raw_data)[0]
        elif self.byte_order == 'badc':  # Big-byte/little-word
            raw_data = struct.pack('>HH', result.registers[1], result.registers[0])
            float_value = struct.unpack('>f', raw_data)[0]
        elif self.byte_order == 'cdab':  # Little-byte/big-word
            raw_data = struct.pack('<HH', result.registers[0], result.registers[1])
            float_value = struct.unpack('<f', raw_data)[0]
        elif self.byte_order == 'dcba':  # Little-endian
            raw_data = struct.pack('<HH', result.registers[1], result.registers[0])
            float_value = struct.unpack('<f', raw_data)[0]
        else:
            # Default to 'badc' if unknown format
            self.log("WARNING", f"Unknown byte order '{self.byte_order}', using 'badc'")
            raw_data = struct.pack('>HH', result.registers[1], result.registers[0])
            float_value = struct.unpack('>f', raw_data)[0]
        self.log("INFO", f"Float value: {float_value}")
        return float_value
    
    def write_float(self, address, value):
        """
        Write a 32-bit float to the PLC using 'badc' format.
        
        Args:
            address: Starting register address
            value: Float value to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self.client.is_socket_open():
            self.log("ERROR", "Not connected to PLC")
            return False
            
        self.log("DEBUG", f"Writing float {value} to address {address}")
        
        # Convert float to configured format
        if self.byte_order == 'abcd':  # Big-endian
            raw_float = struct.pack('>f', value)
            high_word, low_word = struct.unpack('>HH', raw_float)
            registers = [high_word, low_word]
        elif self.byte_order == 'badc':  # Big-byte/little-word
            raw_float = struct.pack('>f', value)
            high_word, low_word = struct.unpack('>HH', raw_float)
            registers = [low_word, high_word]
        elif self.byte_order == 'cdab':  # Little-byte/big-word
            raw_float = struct.pack('<f', value)
            high_word, low_word = struct.unpack('<HH', raw_float)
            registers = [high_word, low_word]
        elif self.byte_order == 'dcba':  # Little-endian
            raw_float = struct.pack('<f', value)
            high_word, low_word = struct.unpack('<HH', raw_float)
            registers = [low_word, high_word]
        else:
            # Default to 'badc' if unknown format
            self.log("WARNING", f"Unknown byte order '{self.byte_order}', using 'badc'")
            raw_float = struct.pack('>f', value)
            high_word, low_word = struct.unpack('>HH', raw_float)
            registers = [low_word, high_word]
        
        self.log("DEBUG", f"Registers in '{self.byte_order}' order: {registers}")
        result = self.client.write_registers(address, registers, slave=self.slave_id)
        
        if result.isError():
            self.log("ERROR", f"Failed to write float: {result}")
            return False
            
        self.log("INFO", f"Successfully wrote float {value} to address {address}")
        return True
    
    def read_integer_32bit(self, address):
        """
        Read a 32-bit integer from the PLC using 'badc' format.
        
        Args:
            address: Starting register address
            
        Returns:
            Integer value or None if read failed
        """
        if not self.client or not self.client.is_socket_open():
            self.log("ERROR", "Not connected to PLC")
            return None
            
        self.log("DEBUG", f"Reading 32-bit integer from address {address}")
        result = self.client.read_holding_registers(address, count=2, slave=self.slave_id)
        
        if result.isError():
            self.log("ERROR", f"Failed to read integer: {result}")
            return None
            
        raw = result.registers
        self.log("DEBUG", f"Raw values: {raw} (hex: [0x{raw[0]:04x}, 0x{raw[1]:04x}])")
        
        # Use the configured byte order
        if self.byte_order == 'abcd':  # Big-endian
            raw_data = struct.pack('>HH', raw[0], raw[1])
            value = struct.unpack('>i', raw_data)[0]
        elif self.byte_order == 'badc':  # Big-byte/little-word
            raw_data = struct.pack('>HH', raw[1], raw[0])
            value = struct.unpack('>i', raw_data)[0]
        elif self.byte_order == 'cdab':  # Little-byte/big-word
            raw_data = struct.pack('<HH', raw[0], raw[1])
            value = struct.unpack('<i', raw_data)[0]
        elif self.byte_order == 'dcba':  # Little-endian
            raw_data = struct.pack('<HH', raw[1], raw[0])
            value = struct.unpack('<i', raw_data)[0]
        else:
            # Default to 'badc' if unknown format
            self.log("WARNING", f"Unknown byte order '{self.byte_order}', using 'badc'")
            raw_data = struct.pack('>HH', raw[1], raw[0])
            value = struct.unpack('>i', raw_data)[0]
        self.log("INFO", f"32-bit Integer value: {value}")
        return value
    
    def write_integer_32bit(self, address, value):
        """
        Write a 32-bit integer to the PLC using 'badc' format.
        
        Args:
            address: Starting register address
            value: Integer value to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self.client.is_socket_open():
            self.log("ERROR", "Not connected to PLC")
            return False
            
        self.log("DEBUG", f"Writing 32-bit integer {value} to address {address}")
        
        # Convert to 32-bit integer using configured byte order
        if self.byte_order == 'abcd':  # Big-endian
            raw_bytes = struct.pack('>i', value)
            high_word, low_word = struct.unpack('>HH', raw_bytes)
            registers = [high_word, low_word]
        elif self.byte_order == 'badc':  # Big-byte/little-word
            raw_bytes = struct.pack('>i', value)
            high_word, low_word = struct.unpack('>HH', raw_bytes)
            registers = [low_word, high_word]
        elif self.byte_order == 'cdab':  # Little-byte/big-word
            raw_bytes = struct.pack('<i', value)
            high_word, low_word = struct.unpack('<HH', raw_bytes)
            registers = [high_word, low_word]
        elif self.byte_order == 'dcba':  # Little-endian
            raw_bytes = struct.pack('<i', value)
            high_word, low_word = struct.unpack('<HH', raw_bytes)
            registers = [low_word, high_word]
        else:
            # Default to 'badc' if unknown format
            self.log("WARNING", f"Unknown byte order '{self.byte_order}', using 'badc'")
            raw_bytes = struct.pack('>i', value)
            high_word, low_word = struct.unpack('>HH', raw_bytes)
            registers = [low_word, high_word]
        
        self.log("DEBUG", f"Registers ({self.byte_order}): {registers} (hex: [0x{registers[0]:04x}, 0x{registers[1]:04x}])")
        result = self.client.write_registers(address, registers, slave=self.slave_id)
        
        if result.isError():
            self.log("ERROR", f"Failed to write integer: {result}")
            return False
            
        self.log("INFO", f"Successfully wrote integer {value} to address {address}")
        return True
    
    def read_coils(self, address, count=1):
        """
        Read binary values (coils) from the PLC.
        
        Args:
            address: Starting coil address
            count: Number of coils to read
            
        Returns:
            List of boolean values or None if read failed
        """
        if not self.client or not self.client.is_socket_open():
            self.log("ERROR", "Not connected to PLC")
            return None
            
        self.log("DEBUG", f"Reading {count} coils from address {address}")
        result = self.client.read_coils(address, count=count, slave=self.slave_id)
        
        if result.isError():
            self.log("ERROR", f"Failed to read coils: {result}")
            return None
            
        self.log("DEBUG", f"Raw coil values: {result.bits}")
        for i, bit in enumerate(result.bits[:count]):
            state = "ON" if bit else "OFF"
            self.log("INFO", f"Coil {address + i}: {state}")
            
        return result.bits[:count]
    
    def write_coil(self, address, value):
        """
        Write a binary value (coil) to the PLC.
        
        Args:
            address: Coil address
            value: Boolean value (True for ON, False for OFF)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self.client.is_socket_open():
            self.log("ERROR", "Not connected to PLC")
            return False
            
        state = "ON" if value else "OFF"
        self.log("DEBUG", f"Writing {state} to coil {address}")
        
        result = self.client.write_coil(address, value, slave=self.slave_id)
        
        if result.isError():
            self.log("ERROR", f"Failed to write coil: {result}")
            return False
            
        self.log("INFO", f"Successfully wrote {state} to coil {address}")
        return True