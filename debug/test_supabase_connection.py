"""
Test script to verify Supabase connection.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_setup import logger
from db import get_supabase, create_async_supabase
from config import MACHINE_ID


async def test_supabase_connection():
    """Test connection to Supabase database."""
    try:
        logger.info("Testing Supabase connection...")
        
        # Test synchronous client
        try:
            logger.info("Testing synchronous client...")
            supabase = get_supabase()
            
            # Simple query to verify connection
            machine = supabase.table('machines').select('*').eq('id', MACHINE_ID).single().execute()
            
            if machine.data:
                logger.info(f"✅ Successfully connected to Supabase (sync client)")
                logger.info(f"Machine data: {machine.data}")
            else:
                logger.warning(f"⚠️ Connected but machine with ID {MACHINE_ID} not found")
                
        except Exception as e:
            logger.error(f"❌ Error with synchronous Supabase client: {str(e)}", exc_info=True)
        
        # Test asynchronous client
        try:
            logger.info("Testing asynchronous client...")
            async_supabase = await create_async_supabase()
            
            # Simple query to verify connection
            machine = await async_supabase.table('machines').select('*').eq('id', MACHINE_ID).single().execute()
            
            if machine.data:
                logger.info(f"✅ Successfully connected to Supabase (async client)")
                logger.info(f"Machine data: {machine.data}")
            else:
                logger.warning(f"⚠️ Connected but machine with ID {MACHINE_ID} not found")
            
        except Exception as e:
            logger.error(f"❌ Error with asynchronous Supabase client: {str(e)}", exc_info=True)
            
    except Exception as e:
        logger.error(f"❌ Error during Supabase connection test: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_supabase_connection())