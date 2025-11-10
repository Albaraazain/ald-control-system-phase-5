"""
Database client configuration for machine control application.
"""
from datetime import datetime, timezone
import traceback
import time
import asyncio
from supabase import create_client, Client
from supabase import create_async_client

from src.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, is_supabase_config_present
from src.log_setup import logger

# Singleton instance for the synchronized client
_supabase_client = None

# Singleton instance for the async client
_async_supabase_client = None

def get_supabase():
    """Get the Supabase client instance (singleton) with retry logic."""
    global _supabase_client
    if _supabase_client is None:
        if not is_supabase_config_present():
            raise ValueError(
                "Supabase configuration missing: set SUPABASE_URL and SUPABASE_KEY in the environment/.env"
            )

        # Retry logic: 5 attempts with exponential backoff
        max_attempts = 5
        base_delay = 2

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Initializing Supabase client (attempt {attempt}/{max_attempts})...")
                logger.info(f"URL: {SUPABASE_URL}")
                api_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
                logger.info(f"API Key (first 10 chars): {api_key[:10]}...")

                _supabase_client = create_client(SUPABASE_URL, api_key)
                logger.info("✅ Supabase client initialized successfully")
                break

            except Exception as e:
                if attempt == max_attempts:
                    logger.error(f"❌ Failed to initialize Supabase client after {max_attempts} attempts")
                    logger.exception("Final error:")
                    raise

                delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(
                    f"⚠️ Supabase init failed (attempt {attempt}/{max_attempts}): {e}\n"
                    f"   Retrying in {delay}s..."
                )
                time.sleep(delay)

    return _supabase_client

async def create_async_supabase():
    """Create or return the shared asynchronous Supabase client (singleton) with retry logic."""
    global _async_supabase_client
    if _async_supabase_client is not None:
        return _async_supabase_client

    if not is_supabase_config_present():
        raise ValueError(
            "Supabase configuration missing: set SUPABASE_URL and SUPABASE_KEY in the environment/.env"
        )

    # Retry logic: 5 attempts with exponential backoff
    max_attempts = 5
    base_delay = 2

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Initializing async Supabase client (attempt {attempt}/{max_attempts})...")
            logger.info(f"URL: {SUPABASE_URL}")
            api_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
            logger.info(f"API Key (first 10 chars): {api_key[:10]}...")

            _async_supabase_client = await create_async_client(SUPABASE_URL, api_key)
            logger.info("✅ Async Supabase client initialized successfully")
            return _async_supabase_client

        except Exception as e:
            if attempt == max_attempts:
                logger.error(f"❌ Failed to initialize async Supabase client after {max_attempts} attempts")
                logger.exception("Final error:")
                raise

            delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
            logger.warning(
                f"⚠️ Async Supabase init failed (attempt {attempt}/{max_attempts}): {e}\n"
                f"   Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)

    return _async_supabase_client

def get_current_timestamp():
    """Get the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
