#!/usr/bin/env python3
"""
Test script to measure PLC bulk read performance improvements.

Compares:
1. Individual reads (baseline)
2. Bulk reads (optimized)

Expected results:
- Individual reads: ~250-570ms for 51 parameters
- Bulk reads: ~50-100ms for 51 parameters (4-8x faster)
"""
import asyncio
import time
import os
import sys
from typing import Dict

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.plc.manager import plc_manager
from src.config import PLC_TYPE, PLC_CONFIG
from src.log_setup import logger


async def test_individual_reads(iterations: int = 10) -> Dict:
    """Test individual read performance (baseline)."""
    logger.info("=" * 60)
    logger.info("TEST 1: Individual Reads (Baseline)")
    logger.info("=" * 60)
    
    # Temporarily disable bulk reads
    if hasattr(plc_manager._plc, '_use_bulk_reads'):
        original_setting = plc_manager._plc._use_bulk_reads
        plc_manager._plc._use_bulk_reads = False
    
    times = []
    
    for i in range(iterations):
        start = time.time()
        
        result = await plc_manager.read_all_parameters()
        
        elapsed = time.time() - start
        times.append(elapsed)
        
        logger.info(
            f"Iteration {i+1}/{iterations}: {len(result)} parameters in {elapsed*1000:.1f}ms"
        )
    
    # Restore original setting
    if hasattr(plc_manager._plc, '_use_bulk_reads'):
        plc_manager._plc._use_bulk_reads = original_setting
    
    avg_time = sum(times) / len(times) * 1000
    min_time = min(times) * 1000
    max_time = max(times) * 1000
    
    logger.info("-" * 60)
    logger.info(f"📊 Individual Reads Summary:")
    logger.info(f"  Average: {avg_time:.1f}ms")
    logger.info(f"  Min: {min_time:.1f}ms")
    logger.info(f"  Max: {max_time:.1f}ms")
    logger.info(f"  Parameters: {len(result)}")
    logger.info("-" * 60)
    
    return {
        'method': 'individual',
        'avg_ms': avg_time,
        'min_ms': min_time,
        'max_ms': max_time,
        'param_count': len(result),
        'times': times
    }


async def test_bulk_reads(iterations: int = 10) -> Dict:
    """Test bulk read performance (optimized)."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 2: Bulk Reads (Optimized)")
    logger.info("=" * 60)
    
    # Ensure bulk reads are enabled
    if hasattr(plc_manager._plc, '_use_bulk_reads'):
        plc_manager._plc._use_bulk_reads = True
    
    times = []
    
    for i in range(iterations):
        start = time.time()
        
        result = await plc_manager.read_all_parameters()
        
        elapsed = time.time() - start
        times.append(elapsed)
        
        logger.info(
            f"Iteration {i+1}/{iterations}: {len(result)} parameters in {elapsed*1000:.1f}ms"
        )
    
    avg_time = sum(times) / len(times) * 1000
    min_time = min(times) * 1000
    max_time = max(times) * 1000
    
    logger.info("-" * 60)
    logger.info(f"📊 Bulk Reads Summary:")
    logger.info(f"  Average: {avg_time:.1f}ms")
    logger.info(f"  Min: {min_time:.1f}ms")
    logger.info(f"  Max: {max_time:.1f}ms")
    logger.info(f"  Parameters: {len(result)}")
    logger.info("-" * 60)
    
    return {
        'method': 'bulk',
        'avg_ms': avg_time,
        'min_ms': min_time,
        'max_ms': max_time,
        'param_count': len(result),
        'times': times
    }


async def main():
    """Run performance comparison tests."""
    logger.info("🔧 PLC Bulk Read Performance Test")
    logger.info(f"PLC Type: {PLC_TYPE}")
    logger.info(f"PLC Config: {PLC_CONFIG}")
    logger.info("")
    
    # Initialize PLC
    logger.info("Initializing PLC connection...")
    if not await plc_manager.initialize(PLC_TYPE, PLC_CONFIG):
        logger.error("Failed to initialize PLC")
        return 1
    
    logger.info("✅ PLC connected successfully")
    logger.info("")
    
    # Check if bulk reads are supported
    if not hasattr(plc_manager._plc, '_use_bulk_reads'):
        logger.warning("⚠️ Bulk reads not supported by current PLC implementation")
        logger.info("Running individual reads test only...")
        individual_results = await test_individual_reads(iterations=10)
        return 0
    
    # Run tests
    individual_results = await test_individual_reads(iterations=10)
    await asyncio.sleep(1)  # Brief pause between tests
    
    bulk_results = await test_bulk_reads(iterations=10)
    
    # Calculate improvement
    logger.info("")
    logger.info("=" * 60)
    logger.info("📈 PERFORMANCE COMPARISON")
    logger.info("=" * 60)
    
    speedup = individual_results['avg_ms'] / bulk_results['avg_ms']
    time_saved = individual_results['avg_ms'] - bulk_results['avg_ms']
    
    logger.info(f"Individual Reads: {individual_results['avg_ms']:.1f}ms (baseline)")
    logger.info(f"Bulk Reads:       {bulk_results['avg_ms']:.1f}ms (optimized)")
    logger.info("-" * 60)
    logger.info(f"⚡ Speedup:       {speedup:.1f}x faster")
    logger.info(f"⏱️  Time Saved:    {time_saved:.1f}ms per cycle")
    logger.info(f"📊 Parameters:    {bulk_results['param_count']}")
    logger.info("")
    
    # Annual savings calculation (assuming 1 read per second)
    seconds_per_year = 365 * 24 * 60 * 60
    total_time_saved_hours = (time_saved / 1000 * seconds_per_year) / 3600
    
    logger.info(f"💰 Time Savings at 1 read/second:")
    logger.info(f"  Per hour:  {time_saved / 1000 * 3600:.1f} seconds")
    logger.info(f"  Per day:   {time_saved / 1000 * 86400:.1f} seconds")
    logger.info(f"  Per year:  {total_time_saved_hours:.1f} hours")
    logger.info("=" * 60)
    
    # Determine if optimization is successful
    if speedup >= 3.0:
        logger.info("✅ EXCELLENT: Bulk reads provide significant performance improvement!")
    elif speedup >= 2.0:
        logger.info("✅ GOOD: Bulk reads provide notable performance improvement")
    elif speedup >= 1.5:
        logger.info("⚠️ MODERATE: Bulk reads provide some improvement")
    else:
        logger.info("❌ WARNING: Bulk reads not providing expected improvement")
    
    # Disconnect
    await plc_manager.disconnect()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


