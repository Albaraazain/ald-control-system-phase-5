"""
Database client configuration for machine control application.
"""
from datetime import datetime, timezone
from supabase import create_client, Client
from supabase import create_async_client

from config import SUPABASE_URL, SUPABASE_KEY
from log_setup import logger

# Singleton instance for the synchronized client
_supabase_client = None

def get_supabase():
    """Get the Supabase client instance (singleton)."""
    global _supabase_client
    if _supabase_client is None:
        logger.info("Initializing Supabase client")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

async def create_async_supabase():
    """Create an asynchronous Supabase client for realtime features."""
    logger.info("Initializing async Supabase client")
    return await create_async_client(SUPABASE_URL, SUPABASE_KEY)

def get_current_timestamp():
    """Get the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()