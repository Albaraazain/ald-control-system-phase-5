"""
Test script to execute a purge operation via the PLC.
"""
import os
import sys
import asyncio
import argparse
import csv
from dotenv import load_dotenv

# Add parent directory to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_setup import logger
from plc.manager import plc_manager


def load_modbus_address_from_csv(operation_type='purge'):
    """Load Modbus address for purge operation from CSV file if it exists."""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                           "Atomicoat ModbusAddress01.05.2025.csv")
    
    if not os.path.exists(csv_path):
        logger.info(f"CSV file not found at {csv_path}")
        return None
    
    try:
        with open(csv_path, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header row
            
            for row in reader:
                if len(row) >= 5:  # Ensure we have enough columns
                    operand = row[0]
                    comment = row[1]
                    modbus_address = row[4]
                    
                    # Look for purge operation (this will need to be adjusted based on your CSV structure)
                    if operation_type.lower() in comment.lower():
                        logger.info(f"Found {operation_type} operation in CSV - Operand: {operand}, "
                                   f"Comment: {comment}, Modbus Address: {modbus_address}")
                        return modbus_address
        
        logger.warning(f"No {operation_type} operation found in CSV file")
        return None
    except Exception as e:
        logger.error(f"Error loading CSV file: {e}")
        return None


async def test_purge(duration_ms=5000):
    """Test executing a purge operation through the PLC."""
    try:
        logger.info(f"Testing purge operation with duration {duration_ms}ms...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
            
        logger.info("✅ Successfully connected to PLC")
        
        # Execute the purge
        try:
            success = await plc_manager.execute_purge(duration_ms)
            
            if success:
                logger.info(f"✅ Successfully started purge operation for {duration_ms}ms")
                
                # Wait for purge to complete (add a small buffer)
                logger.info(f"Waiting for purge to complete...")
                await asyncio.sleep((duration_ms / 1000) + 1)
                
                logger.info("Purge should now be complete")
            else:
                logger.error("❌ Failed to start purge operation")
                
        except Exception as e:
            logger.error(f"❌ Error executing purge: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error during purge test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


async def direct_purge(duration_ms=5000, modbus_address=None):
    """Test executing a purge operation using a direct Modbus address."""
    try:
        logger.info(f"Testing direct purge operation with duration {duration_ms}ms using Modbus address {modbus_address}...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
            
        logger.info("✅ Successfully connected to PLC")
        
        # Get the PLC object
        plc = plc_manager.plc
        
        # Check if we have a valid PLC and communicator
        if not plc or not hasattr(plc, 'communicator'):
            logger.error("❌ PLC or communicator not available")
            return
        
        # Execute the purge directly
        try:
            # Determine if we're dealing with a coil (binary) or register
            # For simplicity, we'll assume it's a coil (this might need to be adjusted)
            logger.info(f"Attempting to trigger purge at Modbus address {modbus_address}")
            
            # Set the purge coil to true
            success = plc.communicator.write_coil(int(modbus_address), True)
            
            if success:
                logger.info(f"✅ Successfully started purge operation for {duration_ms}ms")
                
                # Wait for purge to complete (add a small buffer)
                logger.info(f"Waiting for purge to complete...")
                await asyncio.sleep((duration_ms / 1000) + 1)
                
                # Reset the purge coil
                logger.info("Purge duration complete, resetting purge coil")
                success = plc.communicator.write_coil(int(modbus_address), False)
                
                if success:
                    logger.info("✅ Successfully reset purge coil")
                else:
                    logger.error("❌ Failed to reset purge coil")
                
                logger.info("Purge should now be complete")
            else:
                logger.error("❌ Failed to start purge operation")
                
        except Exception as e:
            logger.error(f"❌ Error executing purge: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error during direct purge test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test a purge operation via the PLC')
    parser.add_argument('--duration', type=int, default=5000, help='Purge duration in milliseconds (default: 5000)')
    parser.add_argument('--direct', action='store_true', help='Use direct Modbus control with address from CSV')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    if args.direct:
        # Load Modbus address from CSV for direct control
        modbus_address = load_modbus_address_from_csv('purge')
        
        if modbus_address:
            logger.info(f"Using direct control for purge at Modbus address {modbus_address}")
            asyncio.run(direct_purge(args.duration, modbus_address))
        else:
            logger.error("❌ Purge operation not found in CSV file")
    else:
        # Run the regular test using PLC manager
        asyncio.run(test_purge(args.duration))