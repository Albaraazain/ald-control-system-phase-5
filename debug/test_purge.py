"""
Test script to execute a purge operation via the PLC.
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


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test a purge operation via the PLC')
    parser.add_argument('--duration', type=int, default=5000, help='Purge duration in milliseconds (default: 5000)')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_purge(args.duration))