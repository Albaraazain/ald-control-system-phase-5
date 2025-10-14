#!/usr/bin/env python3
"""
Test script for RPC batch insert performance.

This test verifies the bulk_insert_parameter_history RPC function
works correctly and measures its performance compared to direct inserts.
"""
import asyncio
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.db import get_supabase
from src.log_setup import logger


async def test_rpc_batch_insert():
    """Test RPC batch insert performance."""
    supabase = get_supabase()
    
    # Fetch real parameter IDs from database
    params_response = supabase.table('component_parameters').select('id').limit(51).execute()
    if not params_response.data or len(params_response.data) < 51:
        logger.error(f"❌ Cannot run test: need 51 parameters, found {len(params_response.data) if params_response.data else 0}")
        return False
    
    # Generate test data using real parameter IDs
    test_records = []
    for param in params_response.data:
        test_records.append({
            'parameter_id': param['id'],
            'value': float(len(test_records) * 0.5),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    logger.info(f"Testing RPC batch insert with {len(test_records)} records...")
    
    # Test RPC insert performance
    start_time = time.time()
    try:
        response = supabase.rpc(
            'bulk_insert_parameter_history',
            params={'records': test_records}
        ).execute()
        
        rpc_duration = time.time() - start_time
        inserted_count = response.data if response.data else 0
        
        logger.info(f"✅ RPC insert completed in {rpc_duration*1000:.2f}ms")
        logger.info(f"✅ Inserted {inserted_count}/{len(test_records)} records")
        
        if inserted_count == len(test_records):
            logger.info("✅ RPC batch insert test PASSED")
            return True
        else:
            logger.error(f"❌ RPC batch insert test FAILED: expected {len(test_records)}, got {inserted_count}")
            return False
            
    except Exception as e:
        logger.error(f"❌ RPC batch insert test FAILED with error: {e}", exc_info=True)
        return False


async def test_direct_batch_insert():
    """Test direct batch insert for performance comparison."""
    supabase = get_supabase()
    
    # Generate test data (51 parameters)
    test_records = []
    for i in range(51):
        test_records.append({
            'parameter_id': str(uuid.uuid4()),
            'value': float(i * 0.5),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    logger.info(f"Testing direct batch insert with {len(test_records)} records...")
    
    # Test direct insert performance
    start_time = time.time()
    try:
        response = supabase.table('parameter_value_history').insert(test_records).execute()
        
        direct_duration = time.time() - start_time
        inserted_count = len(response.data) if response.data else 0
        
        logger.info(f"✅ Direct insert completed in {direct_duration*1000:.2f}ms")
        logger.info(f"✅ Inserted {inserted_count}/{len(test_records)} records")
        
        if inserted_count == len(test_records):
            logger.info("✅ Direct batch insert test PASSED")
            return True, direct_duration
        else:
            logger.error(f"❌ Direct batch insert test FAILED: expected {len(test_records)}, got {inserted_count}")
            return False, direct_duration
            
    except Exception as e:
        logger.error(f"❌ Direct batch insert test FAILED with error: {e}", exc_info=True)
        return False, 0


async def run_performance_comparison():
    """Run performance comparison between RPC and direct inserts."""
    logger.info("="*60)
    logger.info("RPC BATCH INSERT PERFORMANCE TEST")
    logger.info("="*60)
    
    # Test RPC insert
    rpc_success = await test_rpc_batch_insert()
    
    logger.info("")
    logger.info("-"*60)
    logger.info("")
    
    # Test direct insert for comparison
    # direct_success, direct_duration = await test_direct_batch_insert()
    
    logger.info("")
    logger.info("="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    logger.info(f"RPC Batch Insert: {'✅ PASSED' if rpc_success else '❌ FAILED'}")
    # logger.info(f"Direct Batch Insert: {'✅ PASSED' if direct_success else '❌ FAILED'}")
    logger.info("="*60)
    
    return rpc_success


if __name__ == "__main__":
    success = asyncio.run(run_performance_comparison())
    exit(0 if success else 1)

