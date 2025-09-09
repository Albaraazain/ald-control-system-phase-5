"""
Test script to write a value to a specific parameter on the PLC.
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


async def test_parameter_write(parameter_id=None, value=None):
    """Test writing a value to a parameter on the PLC."""
    try:
        logger.info("Testing parameter writing...")
        
        # Initialize PLC
        success = await plc_manager.initialize()
        
        if not success:
            logger.error("❌ Failed to connect to PLC")
            return
            
        logger.info("✅ Successfully connected to PLC")
        
        # If no parameter_id provided, fetch the first available writable parameter from DB
        if parameter_id is None:
            try:
                supabase = get_supabase()
                result = supabase.table('component_parameters').select('*') \
                    .not_is('modbus_address', None) \
                    .eq('is_writable', True) \
                    .limit(1).execute()
                
                if result.data:
                    parameter_id = result.data[0]['id']
                    param_name = result.data[0]['name']
                    min_value = result.data[0]['min_value']
                    max_value = result.data[0]['max_value']
                    current_value = result.data[0]['current_value']
                    
                    logger.info(f"Selected parameter: {param_name} (ID: {parameter_id})")
                    logger.info(f"Valid range: {min_value} to {max_value}")
                    logger.info(f"Current value: {current_value}")
                    
                    # If no value is provided, use a default value within the valid range
                    if value is None:
                        # Use midpoint of range or increment current value
                        if min_value is not None and max_value is not None:
                            value = (min_value + max_value) / 2
                        elif current_value is not None:
                            # Increment by 10% of current value (or 1 if current value is 0)
                            value = current_value + max(1, current_value * 0.1)
                        else:
                            value = 1  # Default value if nothing else works
                            
                        logger.info(f"Using default value: {value}")
                else:
                    logger.error("❌ No writable parameters found in the database")
                    return
            except Exception as e:
                logger.error(f"❌ Error fetching parameter from database: {str(e)}")
                return
        
        if value is None:
            logger.error("❌ No value specified and couldn't determine a default value")
            return
            
        # Read the current value first
        try:
            current_value = await plc_manager.read_parameter(parameter_id)
            logger.info(f"Current parameter value: {current_value}")
        except Exception as e:
            logger.error(f"❌ Error reading current parameter value: {str(e)}")
            
        # Write the new value
        try:
            success = await plc_manager.write_parameter(parameter_id, value)
            
            if success:
                logger.info(f"✅ Successfully wrote value {value} to parameter")
                
                # Read back the value to verify
                new_value = await plc_manager.read_parameter(parameter_id)
                logger.info(f"New parameter value: {new_value}")
                
                if abs(float(new_value) - float(value)) < 0.0001:
                    logger.info("✅ Value verification successful")
                else:
                    logger.warning(f"⚠️ Value verification failed. Expected: {value}, Read: {new_value}")
            else:
                logger.error("❌ Failed to write parameter value")
                
        except Exception as e:
            logger.error(f"❌ Error writing parameter: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error during parameter write test: {str(e)}", exc_info=True)
        
    finally:
        # Ensure cleanup happens
        if plc_manager.is_connected():
            await plc_manager.disconnect()
            logger.info("Disconnected from PLC")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test writing a value to a parameter on the PLC')
    parser.add_argument('--param-id', help='Parameter ID to write to (optional)')
    parser.add_argument('--value', type=float, help='Value to write (optional)')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_parameter_write(args.param_id, args.value))