#!/usr/bin/env python3
"""
Test script for Wide Table RPC insert performance.

This test verifies the insert_parameter_reading_wide RPC function
works correctly and measures its performance.
"""
import asyncio
import os
import sys
import time
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.db import get_supabase
from src.log_setup import logger
from src.parameter_wide_table_mapping import PARAMETER_TO_COLUMN_MAP


async def test_wide_insert():
    """Test wide-format RPC insert with actual parameters."""
    supabase = get_supabase()
    
    logger.info("="*60)
    logger.info("WIDE TABLE RPC INSERT TEST")
    logger.info("="*60)
    
    # Create test data using actual parameter column names
    timestamp = datetime.utcnow().isoformat()
    wide_record = {}
    
    # Add all 51 parameters with test values
    for i, column_name in enumerate(PARAMETER_TO_COLUMN_MAP.values()):
        wide_record[column_name] = float(i * 0.5)
    
    logger.info(f"Testing wide insert with {len(wide_record)} parameters...")
    logger.info(f"Timestamp: {timestamp}")
    
    # Test RPC insert performance
    start_time = time.time()
    try:
        response = supabase.rpc(
            'insert_parameter_reading_wide',
            params={
                'p_timestamp': timestamp,
                'p_params': wide_record
            }
        ).execute()
        
        insert_duration = (time.time() - start_time) * 1000  # Convert to ms
        inserted_count = response.data if response.data else 0
        
        logger.info(f"✅ Wide insert completed in {insert_duration:.2f}ms")
        logger.info(f"✅ Inserted {inserted_count}/{len(wide_record)} parameters")
        
        if inserted_count == len(wide_record):
            logger.info("✅ WIDE INSERT TEST PASSED")
            logger.info("✅ Data inserted successfully into wide table")
            
            return True, insert_duration
        else:
            logger.error(f"❌ TEST FAILED: expected {len(wide_record)}, got {inserted_count}")
            return False, insert_duration
            
    except Exception as e:
        logger.error(f"❌ Wide insert test FAILED with error: {e}", exc_info=True)
        return False, 0


async def test_insert_performance():
    """Run multiple inserts to measure average performance."""
    logger.info("")
    logger.info("="*60)
    logger.info("PERFORMANCE TEST - 10 INSERTS")
    logger.info("="*60)
    
    supabase = get_supabase()
    durations = []
    
    for i in range(10):
        timestamp = datetime.utcnow().isoformat()
        wide_record = {}
        
        # Generate test data
        for j, column_name in enumerate(PARAMETER_TO_COLUMN_MAP.values()):
            wide_record[column_name] = float((i * 51 + j) * 0.1)
        
        # Insert and measure
        start_time = time.time()
        try:
            response = supabase.rpc(
                'insert_parameter_reading_wide',
                params={
                    'p_timestamp': timestamp,
                    'p_params': wide_record
                }
            ).execute()
            
            duration = (time.time() - start_time) * 1000
            durations.append(duration)
            
            logger.info(f"Insert {i+1}/10: {duration:.2f}ms")
            
            # Wait a bit to avoid timestamp conflicts
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Insert {i+1} failed: {e}")
    
    if durations:
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        logger.info("")
        logger.info("="*60)
        logger.info("PERFORMANCE RESULTS")
        logger.info("="*60)
        logger.info(f"Average: {avg_duration:.2f}ms")
        logger.info(f"Min: {min_duration:.2f}ms")
        logger.info(f"Max: {max_duration:.2f}ms")
        logger.info(f"Target: <100ms (vs 180ms for narrow table)")
        
        if avg_duration < 100:
            logger.info("✅ PERFORMANCE TARGET MET!")
        else:
            logger.warning(f"⚠️ Performance above target: {avg_duration:.2f}ms")
        
        logger.info("="*60)


async def main():
    """Run all tests."""
    # Test basic functionality
    success, duration = await test_wide_insert()
    
    if success:
        # Run performance test
        await test_insert_performance()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

