"""
Database client configuration for machine control application.
"""
from datetime import datetime, timezone
import traceback
from supabase import create_client, Client
from supabase import create_async_client

from .config import SUPABASE_URL, SUPABASE_KEY
from .log_setup import logger

# Singleton instance for the synchronized client
_supabase_client = None

def get_supabase():
    """Get the Supabase client instance (singleton)."""
    global _supabase_client
    if _supabase_client is None:
        try:
            logger.info(f"Initializing Supabase client with URL: {SUPABASE_URL}")
            logger.info(f"API Key (first 10 chars): {SUPABASE_KEY[:10]}...")
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Supabase client: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    return _supabase_client

async def create_async_supabase():
    """Create an asynchronous Supabase client for realtime features."""
    try:
        logger.info(f"Initializing async Supabase client with URL: {SUPABASE_URL}")
        logger.info(f"API Key (first 10 chars): {SUPABASE_KEY[:10]}...")
        client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Async Supabase client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Error initializing async Supabase client: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def get_current_timestamp():
    """Get the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
