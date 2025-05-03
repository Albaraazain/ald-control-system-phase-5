"""
Test script to write values to specific Modbus addresses with configurable data types.

Usage examples:
  - Write a float value:
    python -m debug.test_modbus_write --address 100 --type float --value 123.45
  
  - Write a binary/coil value:
    python -m debug.test_modbus_write --address 12 --type binary --value 1
  
  - Write an int32 value:
    python -m debug.test_modbus_write --address 200 --type int32 --value 12345
  
  - Write an int16 value:
    python -m debug.test_modbus_write --address 300 --type int16 --value 1000
  
  - Toggle a coil (read, invert, write):
    python -m debug.test_modbus_write --address 12 --type binary --toggle
"""
import os
import sys
import asyncio
import argparse
from dotenv import load_dotenv

# Add parent directory to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_setup import logger
from plc.manager import plc_manager


async def read_modbus_value(address, data_type="binary", slave_id=None):
    """
    Read a value from a specific Modbus address with the given data type.
    
    Args:
        address: The Modbus address to read from
        data_type: The data type to read ('binary', 'float', 'int32', 'int16')
        slave_id: Optional slave ID to use (if None, uses the default)
        
    Returns:
        The value read from the address
    """
    try:
        # Initialize PLC if needed
        if not plc_manager.is_connected():
            success = await plc_manager.initialize()
            if not success:
                logger.error("❌ Failed to connect to PLC")
                return None
            logger.info("✅ Successfully connected to PLC")
        
        # Get the PLC communicator
        plc = plc_manager.plc
        if not plc or not hasattr(plc, 'communicator'):
            logger.error("❌ PLC or communicator not available")
            return None
        
        communicator = plc.communicator
        
        # Store original slave ID if we're changing it
        original_slave_id = None
        if slave_id is not None and communicator.slave_id != slave_id:
            original_slave_id = communicator.slave_id
            communicator.slave_id = slave_id
            logger.info(f"Temporarily changed slave ID from {original_slave_id} to {slave_id}")
        
        # Read the value based on data type
        try:
            address = int(address)
            value = None
            
            if data_type.lower() == "binary":
                logger.info(f"Reading binary value (coil) from address {address}")
                result = communicator.read_coils(address, count=1)
                if result is not None and len(result) > 0:
                    value = result[0]
                    logger.info(f"Binary value at address {address}: {value} ({['OFF', 'ON'][value]})")
                else:
                    logger.error(f"Failed to read binary value from address {address}")
            
            elif data_type.lower() == "float":
                logger.info(f"Reading 32-bit float value from address {address}")
                value = communicator.read_float(address)
                if value is not None:
                    logger.info(f"Float value at address {address}: {value}")
                else:
                    logger.error(f"Failed to read float value from address {address}")
            
            elif data_type.lower() == "int32":
                logger.info(f"Reading 32-bit integer value from address {address}")
                value = communicator.read_integer_32bit(address)
                if value is not None:
                    logger.info(f"32-bit integer value at address {address}: {value}")
                else:
                    logger.error(f"Failed to read 32-bit integer value from address {address}")
            
            elif data_type.lower() == "int16":
                logger.info(f"Reading 16-bit integer value from address {address}")
                result = communicator.client.read_holding_registers(address, count=1, slave=communicator.slave_id)
                if not result.isError():
                    value = result.registers[0]
                    logger.info(f"16-bit integer value at address {address}: {value}")
                else:
                    logger.error(f"Failed to read 16-bit integer value from address {address}: {result}")
            
            else:
                logger.error(f"Unsupported data type: {data_type}")
                return None
            
            return value
            
        finally:
            # Restore original slave ID if it was changed
            if original_slave_id is not None:
                communicator.slave_id = original_slave_id
                logger.info(f"Restored slave ID to {original_slave_id}")
    
    except Exception as e:
        logger.error(f"❌ Error reading Modbus value: {str(e)}", exc_info=True)
        return None


async def write_modbus_value(address, value, data_type="binary", slave_id=None):
    """
    Write a value to a specific Modbus address with the given data type.
    
    Args:
        address: The Modbus address to write to
        value: The value to write
        data_type: The data type to write ('binary', 'float', 'int32', 'int16')
        slave_id: Optional slave ID to use (if None, uses the default)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize PLC if needed
        if not plc_manager.is_connected():
            success = await plc_manager.initialize()
            if not success:
                logger.error("❌ Failed to connect to PLC")
                return False
            logger.info("✅ Successfully connected to PLC")
        
        # Get the PLC communicator
        plc = plc_manager.plc
        if not plc or not hasattr(plc, 'communicator'):
            logger.error("❌ PLC or communicator not available")
            return False
        
        communicator = plc.communicator
        
        # Store original slave ID if we're changing it
        original_slave_id = None
        if slave_id is not None and communicator.slave_id != slave_id:
            original_slave_id = communicator.slave_id
            communicator.slave_id = slave_id
            logger.info(f"Temporarily changed slave ID from {original_slave_id} to {slave_id}")
        
        # Ensure value is in the right format
        try:
            address = int(address)
            success = False
            
            if data_type.lower() == "binary":
                # Convert to boolean
                bool_value = bool(int(value))
                state_str = "ON" if bool_value else "OFF"
                logger.info(f"Writing binary value {bool_value} ({state_str}) to address {address} (modbus_type: coil)")
                success = communicator.write_coil(address, bool_value)
            
            elif data_type.lower() == "float":
                # Convert to float
                float_value = float(value)
                logger.info(f"Writing float value {float_value} to address {address} (modbus_type: holding)")
                success = communicator.write_float(address, float_value)
            
            elif data_type.lower() == "int32":
                # Convert to 32-bit int
                int_value = int(value)
                logger.info(f"Writing 32-bit integer value {int_value} to address {address} (modbus_type: holding)")
                success = communicator.write_integer_32bit(address, int_value)
            
            elif data_type.lower() == "int16":
                # Convert to 16-bit int
                int_value = int(value)
                if int_value < 0 or int_value > 65535:
                    logger.warning(f"Value {int_value} is outside valid range for 16-bit unsigned integer")
                
                logger.info(f"Writing 16-bit integer value {int_value} to address {address} (modbus_type: holding)")
                result = communicator.client.write_register(address, int_value, slave=communicator.slave_id)
                success = not result.isError()
                if not success:
                    logger.error(f"Failed to write 16-bit integer: {result}")
            
            else:
                logger.error(f"Unsupported data type: {data_type}")
                return False
            
            if success:
                logger.info(f"✅ Successfully wrote value to address {address}")
            else:
                logger.error(f"❌ Failed to write value to address {address}")
                
            return success
            
        finally:
            # Restore original slave ID if it was changed
            if original_slave_id is not None:
                communicator.slave_id = original_slave_id
                logger.info(f"Restored slave ID to {original_slave_id}")
    
    except Exception as e:
        logger.error(f"❌ Error writing Modbus value: {str(e)}", exc_info=True)
        return False


async def execute_modbus_write_test(address, value=None, data_type="binary", slave_id=None, toggle=False):
    """
    Execute the Modbus write test.
    
    Args:
        address: The Modbus address to write to
        value: The value to write (not used if toggle=True)
        data_type: The data type to write
        slave_id: Optional slave ID to use
        toggle: If True, toggle the existing value (only works for binary type)
    """
    try:
        # Initialize PLC
        success = await plc_manager.initialize()
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
        
        logger.info("✅ Successfully connected to PLC")
        
        # Get the PLC connection details
        plc = plc_manager.plc
        if hasattr(plc, 'communicator'):
            comm = plc.communicator
            logger.info(f"Connected to PLC at {comm.plc_ip}:{comm.port} with slave ID {comm.slave_id}")
            logger.info(f"Using byte order: {comm.byte_order}")
        
        # If toggling, read the current value
        if toggle:
            if data_type.lower() != "binary":
                logger.error("❌ Toggle mode only works with binary data type")
                return
            
            # Read the current value
            current_value = await read_modbus_value(address, data_type, slave_id)
            if current_value is None:
                logger.error("❌ Failed to read current value for toggling")
                return
            
            # Invert the value
            value = not current_value
            logger.info(f"Toggling value from {current_value} to {value}")
        
        # Write the value
        if value is not None:
            success = await write_modbus_value(address, value, data_type, slave_id)
            if success:
                # Read back the value to verify
                logger.info("Reading back value to verify write...")
                readback_value = await read_modbus_value(address, data_type, slave_id)
                
                if readback_value is not None:
                    if data_type.lower() == "binary":
                        bool_value = bool(int(value))
                        if readback_value == bool_value:
                            logger.info(f"✅ Verification successful: value is now {readback_value}")
                        else:
                            logger.error(f"❌ Verification failed: value is {readback_value}, expected {bool_value}")
                    elif data_type.lower() == "float":
                        float_value = float(value)
                        # Allow small floating-point differences
                        if abs(readback_value - float_value) < 0.0001:
                            logger.info(f"✅ Verification successful: value is now {readback_value}")
                        else:
                            logger.error(f"❌ Verification failed: value is {readback_value}, expected {float_value}")
                    else:
                        int_value = int(value)
                        if readback_value == int_value:
                            logger.info(f"✅ Verification successful: value is now {readback_value}")
                        else:
                            logger.error(f"❌ Verification failed: value is {readback_value}, expected {int_value}")
                else:
                    logger.error("❌ Failed to read back value for verification")
            else:
                logger.error(f"❌ Failed to write value {value} to address {address}")
        else:
            logger.error("❌ No value specified to write")
    
    except Exception as e:
        logger.error(f"❌ Error during Modbus write test: {str(e)}", exc_info=True)
    
    finally:
        # Clean up
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Write a value to a specific Modbus address with configurable data type',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--address', type=int, required=True, help='Modbus address to write to')
    parser.add_argument('--type', choices=['binary', 'float', 'int32', 'int16'], default='binary', 
                        help='Data type to write (default: binary)')
    parser.add_argument('--value', help='Value to write')
    parser.add_argument('--slave-id', type=int, help='Slave ID to use (default: use PLC\'s default)')
    parser.add_argument('--toggle', action='store_true', help='Toggle the current value (binary only)')
    args = parser.parse_args()
    
    # Validate arguments
    if not args.toggle and args.value is None:
        parser.error("Either --value or --toggle must be specified")
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(execute_modbus_write_test(
        args.address,
        args.value,
        args.type,
        args.slave_id,
        args.toggle
    ))