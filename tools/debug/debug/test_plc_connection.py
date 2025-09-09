"""
Simple test script to verify PLC connection.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_setup import logger
from plc.manager import plc_manager


async def test_plc_connection():
    """Test basic PLC connection and disconnection."""
    try:
        logger.info("Testing PLC connection...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if success:
            logger.info("✅ Successfully connected to PLC")
            
            # Test disconnection
            disconnect_success = await plc_manager.disconnect()
            
            if disconnect_success:
                logger.info("✅ Successfully disconnected from PLC")
            else:
                logger.error("❌ Failed to disconnect from PLC")
        else:
            logger.error("❌ Failed to connect to PLC")
            
    except Exception as e:
        logger.error(f"❌ Error during PLC connection test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_plc_connection())