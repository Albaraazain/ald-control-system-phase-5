"""
Test script to read values from specific Modbus addresses with configurable data types.

Usage examples:
  - Read a float value:
    python -m debug.test_modbus_read --address 100 --type float
  
  - Read a binary/coil value:
    python -m debug.test_modbus_read --address 12 --type binary
  
  - Read an int32 value:
    python -m debug.test_modbus_read --address 200 --type int32
  
  - Read an int16 value:
    python -m debug.test_modbus_read --address 300 --type int16
  
  - Continuously monitor a value every second:
    python -m debug.test_modbus_read --address 12 --type binary --monitor 1.0
"""
import os
import sys
import asyncio
import argparse
import time
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
                logger.info(f"Reading binary value (coil) from address {address} (modbus_type: coil)")
                result = communicator.read_coils(address, count=1)
                if result is not None and len(result) > 0:
                    value = result[0]
                    logger.info(f"Binary value at address {address}: {value} ({['OFF', 'ON'][value]})")
                else:
                    logger.error(f"Failed to read binary value from address {address}")
            
            elif data_type.lower() == "float":
                logger.info(f"Reading 32-bit float value from address {address} (modbus_type: holding)")
                value = communicator.read_float(address)
                if value is not None:
                    logger.info(f"Float value at address {address}: {value}")
                else:
                    logger.error(f"Failed to read float value from address {address}")
            
            elif data_type.lower() == "int32":
                logger.info(f"Reading 32-bit integer value from address {address} (modbus_type: holding)")
                value = communicator.read_integer_32bit(address)
                if value is not None:
                    logger.info(f"32-bit integer value at address {address}: {value}")
                else:
                    logger.error(f"Failed to read 32-bit integer value from address {address}")
            
            elif data_type.lower() == "int16":
                logger.info(f"Reading 16-bit integer value from address {address} (modbus_type: holding)")
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


async def execute_modbus_read_test(address, data_type="binary", slave_id=None, monitor_interval=None):
    """
    Execute the Modbus read test.
    
    Args:
        address: The Modbus address to read from
        data_type: The data type to read
        slave_id: Optional slave ID to use
        monitor_interval: If set, continuously monitor the value at this interval (in seconds)
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
        
        # If monitoring, continuously read the value
        if monitor_interval is not None and monitor_interval > 0:
            logger.info(f"Monitoring Modbus address {address} ({data_type}) every {monitor_interval} seconds...")
            try:
                count = 0
                while True:
                    count += 1
                    value = await read_modbus_value(address, data_type, slave_id)
                    value_str = str(value)
                    if data_type.lower() == "binary":
                        value_str = f"{value} ({'ON' if value else 'OFF'})"
                    
                    logger.info(f"[{count}] Value at address {address}: {value_str}")
                    await asyncio.sleep(monitor_interval)
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
        else:
            # Read the value once
            await read_modbus_value(address, data_type, slave_id)
    
    except Exception as e:
        logger.error(f"❌ Error during Modbus read test: {str(e)}", exc_info=True)
    
    finally:
        # Clean up
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Read a value from a specific Modbus address with configurable data type',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--address', type=int, required=True, help='Modbus address to read from')
    parser.add_argument('--type', choices=['binary', 'float', 'int32', 'int16'], default='binary', 
                        help='Data type to read (default: binary)')
    parser.add_argument('--slave-id', type=int, help='Slave ID to use (default: use PLC\'s default)')
    parser.add_argument('--monitor', type=float, help='Continuously monitor value at this interval in seconds')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(execute_modbus_read_test(
        args.address,
        args.type,
        args.slave_id,
        args.monitor
    ))