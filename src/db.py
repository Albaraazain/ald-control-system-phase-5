"""
Database client configuration for machine control application.
"""
from datetime import datetime, timezone
import traceback
from supabase import create_client, Client
from supabase import create_async_client

from src.config import SUPABASE_URL, SUPABASE_KEY, is_supabase_config_present
from src.log_setup import logger

# Singleton instance for the synchronized client
_supabase_client = None

# Singleton instance for the async client
_async_supabase_client = None

def get_supabase():
    """Get the Supabase client instance (singleton)."""
    global _supabase_client
    if _supabase_client is None:
        try:
            if not is_supabase_config_present():
                raise ValueError(
                    "Supabase configuration missing: set SUPABASE_URL and SUPABASE_KEY in the environment/.env"
                )
            logger.info(f"Initializing Supabase client with URL: {SUPABASE_URL}")
            # Avoid slicing None; safe because of the check above
            logger.info(f"API Key (first 10 chars): {SUPABASE_KEY[:10]}...")
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Supabase client initialized successfully")
        except Exception:
            logger.exception("Error initializing Supabase client")
            raise
    return _supabase_client

async def create_async_supabase():
    """Create or return the shared asynchronous Supabase client (singleton)."""
    global _async_supabase_client
    if _async_supabase_client is not None:
        return _async_supabase_client
    try:
        if not is_supabase_config_present():
            raise ValueError(
                "Supabase configuration missing: set SUPABASE_URL and SUPABASE_KEY in the environment/.env"
            )
        logger.info(f"Initializing async Supabase client with URL: {SUPABASE_URL}")
        logger.info(f"API Key (first 10 chars): {SUPABASE_KEY[:10]}...")
        _async_supabase_client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Async Supabase client initialized successfully")
        return _async_supabase_client
    except Exception:
        logger.exception("Error initializing async Supabase client")
        raise

def get_current_timestamp():
    """Get the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
