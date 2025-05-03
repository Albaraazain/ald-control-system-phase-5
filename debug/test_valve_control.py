"""
Test script to control a valve via the PLC.
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


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test controlling a valve via the PLC')
    parser.add_argument('valve_number', type=int, help='Valve number to control')
    parser.add_argument('--close', action='store_true', help='Close the valve (default is to open)')
    parser.add_argument('--duration', type=int, help='Duration in ms to keep valve open before auto-closing')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_valve_control(
        args.valve_number, 
        not args.close,  # If --close is specified, open_valve should be False
        args.duration
    ))