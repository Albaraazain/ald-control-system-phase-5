"""
Test script to read a specific parameter from the PLC.
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
from db import get_supabase


async def test_parameter_read(parameter_id=None):
    """Test reading a parameter from the PLC."""
    try:
        logger.info("Testing parameter reading...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
            
        logger.info("✅ Successfully connected to PLC")
        
        # If no parameter_id provided, fetch the first available parameter from DB
        if parameter_id is None:
            try:
                supabase = get_supabase()
                result = supabase.table('component_parameters').select('*').not_is('modbus_address', None).limit(1).execute()
                
                if result.data:
                    parameter_id = result.data[0]['id']
                    logger.info(f"Selected parameter: {result.data[0]['name']} (ID: {parameter_id})")
                else:
                    logger.error("❌ No parameters found in the database")
                    return
            except Exception as e:
                logger.error(f"❌ Error fetching parameter from database: {str(e)}")
                return
        
        # Read the parameter
        try:
            value = await plc_manager.read_parameter(parameter_id)
            logger.info(f"✅ Parameter value: {value}")
        except Exception as e:
            logger.error(f"❌ Error reading parameter: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error during parameter read test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test reading a parameter from the PLC')
    parser.add_argument('--param-id', help='Parameter ID to read (optional)')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_parameter_read(args.param_id))