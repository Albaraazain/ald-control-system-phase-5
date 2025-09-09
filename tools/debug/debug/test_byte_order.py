"""
Test script to identify correct byte order for PLC communication.
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
from plc.communicator import PLCCommunicator

async def test_byte_orders(address=0):
    """Test reading a value with different byte orders."""
    try:
        logger.info(f"Testing byte orders for register at address {address}...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
            
        logger.info("✅ Successfully connected to PLC")
        
        # Get the communicator
        communicator = None
        for plc in plc_manager._plcs.values():
            if hasattr(plc, 'communicator') and isinstance(plc.communicator, PLCCommunicator):
                communicator = plc.communicator
                break
                
        if not communicator:
            logger.error("❌ No PLC communicator found")
            return
            
        # Save original byte order if it exists
        original_byte_order = getattr(communicator, 'byte_order', None)
        
        # Test all byte orders
        byte_orders = ['abcd', 'badc', 'cdab', 'dcba']
        results = {}
        
        for order in byte_orders:
            # Set byte order - temporarily patch the class for testing
            setattr(communicator, 'byte_order', order)
            try:
                # Read registers directly
                result = communicator.client.read_holding_registers(address, count=2, slave=communicator.slave_id)
                
                if hasattr(result, 'isError') and result.isError():
                    logger.error(f"❌ Failed to read registers with {order}: {result}")
                    continue
                    
                raw = result.registers
                logger.info(f"Raw registers: {raw} (hex: [0x{raw[0]:04x}, 0x{raw[1]:04x}])")
                
                # Try different byte orders manually
                if order == 'abcd':  # Big-endian
                    import struct
                    raw_data = struct.pack('>HH', raw[0], raw[1])
                    float_val = struct.unpack('>f', raw_data)[0]
                    int32_val = struct.unpack('>i', raw_data)[0]
                elif order == 'badc':  # Big-byte/little-word
                    import struct
                    raw_data = struct.pack('>HH', raw[1], raw[0])
                    float_val = struct.unpack('>f', raw_data)[0]
                    int32_val = struct.unpack('>i', raw_data)[0]
                elif order == 'cdab':  # Little-byte/big-word
                    import struct
                    raw_data = struct.pack('<HH', raw[0], raw[1])
                    float_val = struct.unpack('<f', raw_data)[0]
                    int32_val = struct.unpack('<i', raw_data)[0]
                elif order == 'dcba':  # Little-endian
                    import struct
                    raw_data = struct.pack('<HH', raw[1], raw[0])
                    float_val = struct.unpack('<f', raw_data)[0]
                    int32_val = struct.unpack('<i', raw_data)[0]
                
                results[order] = {
                    'raw': raw,
                    'as_float': float_val,
                    'as_int32': int32_val
                }
                
                logger.info(f"Byte order {order}:")
                logger.info(f"  Float: {float_val}")
                logger.info(f"  Int32: {int32_val}")
                
            except Exception as e:
                logger.error(f"❌ Error with byte order {order}: {str(e)}")
                
        # Restore original byte order if it existed
        if original_byte_order is not None:
            setattr(communicator, 'byte_order', original_byte_order)
        
        # Print summary
        logger.info("\n--- RESULTS SUMMARY ---")
        for order in byte_orders:
            if order in results:
                logger.info(f"Byte order {order}:")
                logger.info(f"  Float: {results[order]['as_float']}")
                logger.info(f"  Int32: {results[order]['as_int32']}")
            
    except Exception as e:
        logger.error(f"❌ Error testing byte orders: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test different byte orders')
    parser.add_argument('--address', type=int, default=0, help='Register address to read')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_byte_orders(args.address))