"""
Test script to control a valve via the PLC.
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


def load_modbus_addresses_from_csv():
    """Load Modbus addresses from CSV file if it exists."""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                           "Atomicoat ModbusAddress01.05.2025.csv")
    
    if not os.path.exists(csv_path):
        logger.info(f"CSV file not found at {csv_path}")
        return {}
    
    valve_addresses = {}
    try:
        with open(csv_path, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header row
            for row in reader:
                if len(row) >= 5:  # Ensure we have enough columns
                    operand = row[0]
                    comment = row[1]
                    modbus_address = row[4]
                    
                    # Check if this is a valve
                    if 'valve' in comment.lower():
                        # Try to extract valve number
                        try:
                            import re
                            match = re.search(r'valve\s*(\d+)', comment.lower())
                            if match:
                                valve_number = int(match.group(1))
                                valve_addresses[valve_number] = {
                                    'operand': operand,
                                    'modbus_address': modbus_address,
                                    'comment': comment
                                }
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Could not extract valve number from {comment}: {e}")
        
        logger.info(f"Loaded {len(valve_addresses)} valve addresses from CSV file")
        for valve_num, valve_data in valve_addresses.items():
            logger.info(f"CSV Valve {valve_num}: Address {valve_data['modbus_address']}, Comment: {valve_data['comment']}")
            
        return valve_addresses
    except Exception as e:
        logger.error(f"Error loading CSV file: {e}")
        return {}


async def test_valve_control(valve_number, open_valve=True, duration_ms=None):
    """Test controlling a valve through the PLC."""
    try:
        logger.info(f"Testing {'opening' if open_valve else 'closing'} valve {valve_number}...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
            
        logger.info("✅ Successfully connected to PLC")
        
        # Control the valve
        try:
            success = await plc_manager.control_valve(valve_number, open_valve, duration_ms)
            
            if success:
                logger.info(f"✅ Successfully {'opened' if open_valve else 'closed'} valve {valve_number}")
                
                if duration_ms is not None and open_valve:
                    logger.info(f"Valve will automatically close after {duration_ms}ms")
                    # Wait a bit longer than the duration to see the auto-close
                    await asyncio.sleep((duration_ms / 1000) + 0.5)
            else:
                logger.error(f"❌ Failed to {'open' if open_valve else 'close'} valve {valve_number}")
                
        except Exception as e:
            logger.error(f"❌ Error controlling valve: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error during valve control test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


async def direct_valve_control(valve_number, open_valve=True, duration_ms=None, modbus_address=None):
    """Control a valve directly using Modbus address from CSV."""
    try:
        logger.info(f"Testing direct {'opening' if open_valve else 'closing'} of valve {valve_number} using Modbus address {modbus_address}...")
        
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
            
        # Control the valve directly using the Modbus address
        try:
            state_str = "open" if open_valve else "close"
            logger.info(f"Attempting to {state_str} valve {valve_number} at Modbus address {modbus_address}")
            
            # Write to the valve coil directly
            success = plc.communicator.write_coil(int(modbus_address), open_valve)
            
            if success:
                logger.info(f"✅ Successfully {'opened' if open_valve else 'closed'} valve {valve_number} at address {modbus_address}")
                
                if duration_ms is not None and open_valve:
                    logger.info(f"Valve will automatically close after {duration_ms}ms")
                    # Wait a bit longer than the duration to see the auto-close
                    await asyncio.sleep((duration_ms / 1000) + 0.5)
                    
                    # Auto-close after duration
                    logger.info(f"Auto-closing valve {valve_number} after {duration_ms}ms")
                    success = plc.communicator.write_coil(int(modbus_address), False)
                    
                    if success:
                        logger.info(f"✅ Successfully auto-closed valve {valve_number}")
                    else:
                        logger.error(f"❌ Failed to auto-close valve {valve_number}")
            else:
                logger.error(f"❌ Failed to {state_str} valve {valve_number}")
                
        except Exception as e:
            logger.error(f"❌ Error controlling valve: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error during direct valve control test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test controlling a valve via the PLC')
    parser.add_argument('valve_number', type=int, help='Valve number to control')
    parser.add_argument('--close', action='store_true', help='Close the valve (default is to open)')
    parser.add_argument('--duration', type=int, help='Duration in ms to keep valve open before auto-closing')
    parser.add_argument('--direct', action='store_true', help='Use direct Modbus control with addresses from CSV')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    if args.direct:
        # Load Modbus addresses from CSV for direct control
        valve_addresses = load_modbus_addresses_from_csv()
        valve_data = valve_addresses.get(args.valve_number)
        
        if valve_data:
            modbus_address = valve_data['modbus_address']
            logger.info(f"Using direct control for valve {args.valve_number} at Modbus address {modbus_address}")
            asyncio.run(direct_valve_control(
                args.valve_number,
                not args.close,
                args.duration,
                modbus_address
            ))
        else:
            logger.error(f"❌ Valve {args.valve_number} not found in CSV file")
    else:
        # Run the regular test using PLC manager
        asyncio.run(test_valve_control(
            args.valve_number, 
            not args.close,  # If --close is specified, open_valve should be False
            args.duration
        ))