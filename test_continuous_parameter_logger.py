#!/usr/bin/env python3
"""
Test script for the continuous parameter logger implementation.

This script validates the dual-mode operation of the continuous parameter logging system.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_collection.continuous_parameter_logger import continuous_parameter_logger
from src.plc.manager import plc_manager
from src.db import get_supabase
from src.config import MACHINE_ID
from src.log_setup import logger


async def test_continuous_parameter_logger():
    """Test the continuous parameter logger functionality."""
    logger.info("Starting continuous parameter logger test")

    try:
        # Test 1: Check service status before starting
        status = continuous_parameter_logger.get_status()
        logger.info(f"Initial service status: {status}")
        assert not status['is_running'], "Service should not be running initially"

        # Test 2: Start the service
        logger.info("Starting continuous parameter logger...")
        await continuous_parameter_logger.start()

        status = continuous_parameter_logger.get_status()
        logger.info(f"Service status after start: {status}")
        assert status['is_running'], "Service should be running after start"

        # Test 3: Let it run for a few seconds to collect data
        logger.info("Letting service run for 5 seconds...")
        await asyncio.sleep(5)

        # Test 4: Check if data was logged to database
        supabase = get_supabase()

        # Check parameter_value_history table
        history_result = supabase.table('parameter_value_history').select('*').limit(5).execute()
        logger.info(f"Found {len(history_result.data)} recent records in parameter_value_history")

        # Check if there's a running process
        machine_result = supabase.table('machines').select('status, current_process_id').eq('id', MACHINE_ID).single().execute()
        if machine_result.data:
            machine_status = machine_result.data['status']
            process_id = machine_result.data['current_process_id']
            logger.info(f"Machine status: {machine_status}, Process ID: {process_id}")

            if machine_status == 'processing' and process_id:
                # Check process_data_points table if process is running
                process_result = supabase.table('process_data_points').select('*').eq('process_id', process_id).limit(5).execute()
                logger.info(f"Found {len(process_result.data)} recent records in process_data_points for process {process_id}")

        # Test 5: Stop the service
        logger.info("Stopping continuous parameter logger...")
        await continuous_parameter_logger.stop()

        status = continuous_parameter_logger.get_status()
        logger.info(f"Service status after stop: {status}")
        assert not status['is_running'], "Service should not be running after stop"

        logger.info("✅ All tests passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
        return False

    finally:
        # Ensure service is stopped
        if continuous_parameter_logger.is_running:
            await continuous_parameter_logger.stop()


async def test_plc_connectivity():
    """Test PLC connectivity for parameter reading."""
    logger.info("Testing PLC connectivity...")

    try:
        # Check if PLC is connected
        if not plc_manager.is_connected():
            logger.info("PLC not connected, attempting to initialize...")
            success = await plc_manager.initialize()
            if not success:
                logger.warning("PLC initialization failed - tests will use simulation mode")
                return False

        # Try to read all parameters
        logger.info("Reading all parameters from PLC...")
        parameters = await plc_manager.read_all_parameters()
        logger.info(f"Successfully read {len(parameters)} parameters from PLC")

        # Log first few parameters as example
        for i, (param_id, value) in enumerate(parameters.items()):
            if i < 3:  # Show first 3 parameters
                logger.info(f"  Parameter {param_id}: {value}")
            else:
                break

        return True

    except Exception as e:
        logger.error(f"PLC connectivity test failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    logger.info("="*60)
    logger.info("Continuous Parameter Logger Test Suite")
    logger.info("="*60)

    # Test PLC connectivity first
    plc_ok = await test_plc_connectivity()
    if not plc_ok:
        logger.warning("PLC connectivity issues detected - some tests may not work as expected")

    # Test the continuous parameter logger
    logger_ok = await test_continuous_parameter_logger()

    logger.info("="*60)
    if logger_ok:
        logger.info("🎉 Test suite completed successfully!")
        sys.exit(0)
    else:
        logger.error("💥 Test suite failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())