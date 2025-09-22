#!/usr/bin/env python3
"""
Test script for Simple PLC Read Service

This script runs the service for a few seconds to verify it works correctly.
"""
import asyncio
from plc_read_service import SimplePLCReadService
from src.log_setup import get_service_logger

logger = get_service_logger('plc_read_test')


async def test_service():
    """Test the PLC read service for a few seconds."""
    logger.info("🧪 Testing Simple PLC Read Service for 5 seconds...")

    service = SimplePLCReadService(interval_seconds=1.0)

    try:
        # Start the service in a task
        service_task = asyncio.create_task(service.start())

        # Let it run for 5 seconds
        await asyncio.sleep(5)

        # Stop the service
        service.is_running = False
        await service.stop()

        logger.info("✅ Test completed successfully!")

        # Show status
        status = service.get_status()
        logger.info(f"Final status: {status}")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(test_service()))