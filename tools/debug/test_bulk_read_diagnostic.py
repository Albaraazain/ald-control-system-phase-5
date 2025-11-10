#!/usr/bin/env python3
"""
Standalone diagnostic script for bulk read optimization.

Tests:
1. PLC connection
2. Parameter metadata loading
3. Bulk read optimization initialization
4. Bulk read execution with timing
5. Comparison with individual reads
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.plc.real_plc import RealPLC
from src.log_setup import get_plc_logger, get_data_collection_logger
from src.config import PLC_IP, PLC_PORT, PLC_BYTE_ORDER

logger = get_plc_logger()
data_logger = get_data_collection_logger()


async def test_plc_connection():
    """Test basic PLC connection."""
    print("\n" + "="*80)
    print("TEST 1: PLC Connection")
    print("="*80)
    
    plc = RealPLC(
        ip_address=PLC_IP,
        port=PLC_PORT,
        hostname=None,
        auto_discover=False
    )
    
    try:
        success = await plc.initialize()
        if success:
            print("✅ PLC connection successful")
            print(f"   Connected: {plc.connected}")
            print(f"   IP: {plc.ip_address}")
            print(f"   Port: {plc.port}")
            return plc
        else:
            print("❌ PLC connection failed")
            return None
    except Exception as e:
        print(f"❌ PLC connection error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_parameter_loading(plc):
    """Test parameter metadata loading."""
    print("\n" + "="*80)
    print("TEST 2: Parameter Metadata Loading")
    print("="*80)
    
    if not plc:
        print("❌ Skipping - PLC not connected")
        return False
    
    try:
        param_count = len(plc._parameter_cache)
        print(f"✅ Loaded {param_count} parameters")
        
        # Count parameters with read addresses
        params_with_read_addr = sum(
            1 for p in plc._parameter_cache.values()
            if p.get('read_modbus_address') is not None
        )
        print(f"   Parameters with read addresses: {params_with_read_addr}")
        
        # Count by data type
        data_types = {}
        for p in plc._parameter_cache.values():
            dt = p.get('data_type', 'unknown')
            data_types[dt] = data_types.get(dt, 0) + 1
        print(f"   Data types: {data_types}")
        
        # Show sample parameters
        print("\n   Sample parameters (first 5):")
        for i, (param_id, param_meta) in enumerate(list(plc._parameter_cache.items())[:5]):
            print(f"   {i+1}. {param_meta.get('name', 'N/A')} "
                  f"(addr: {param_meta.get('read_modbus_address')}, "
                  f"type: {param_meta.get('data_type')}, "
                  f"modbus_type: {param_meta.get('read_modbus_type')})")
        
        return params_with_read_addr > 0
        
    except Exception as e:
        print(f"❌ Parameter loading error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_bulk_read_optimization(plc):
    """Test bulk read optimization initialization."""
    print("\n" + "="*80)
    print("TEST 3: Bulk Read Optimization Initialization")
    print("="*80)
    
    if not plc:
        print("❌ Skipping - PLC not connected")
        return False
    
    try:
        print(f"   Bulk reads enabled: {plc._use_bulk_reads}")
        print(f"   Bulk read ranges initialized: {plc._bulk_read_ranges is not None}")
        
        if plc._bulk_read_ranges:
            holding_count = len(plc._bulk_read_ranges.get('holding_registers', []))
            coil_count = len(plc._bulk_read_ranges.get('coils', []))
            total_ranges = holding_count + coil_count
            
            print(f"   Holding register ranges: {holding_count}")
            print(f"   Coil ranges: {coil_count}")
            print(f"   Total ranges: {total_ranges}")
            
            # Show sample ranges
            if holding_count > 0:
                print("\n   Sample holding register ranges (first 3):")
                for i, range_info in enumerate(plc._bulk_read_ranges['holding_registers'][:3]):
                    print(f"   {i+1}. Start: {range_info['start_address']}, "
                          f"Count: {range_info['count']}, "
                          f"Parameters: {len(range_info['parameters'])}")
            
            if coil_count > 0:
                print("\n   Sample coil ranges (first 3):")
                for i, range_info in enumerate(plc._bulk_read_ranges['coils'][:3]):
                    print(f"   {i+1}. Start: {range_info['start_address']}, "
                          f"Count: {range_info['count']}, "
                          f"Parameters: {len(range_info['parameters'])}")
            
            return total_ranges > 0
        else:
            print("   ⚠️ Bulk read ranges not initialized")
            return False
            
    except Exception as e:
        print(f"❌ Bulk read optimization error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_bulk_read_execution(plc):
    """Test actual bulk read execution."""
    print("\n" + "="*80)
    print("TEST 4: Bulk Read Execution")
    print("="*80)
    
    if not plc or not plc._bulk_read_ranges:
        print("❌ Skipping - Bulk reads not initialized")
        return None
    
    try:
        # Test bulk read
        start_time = time.time()
        result = await plc.read_all_parameters()
        duration = time.time() - start_time
        
        print(f"✅ Bulk read completed")
        print(f"   Duration: {duration*1000:.0f}ms")
        print(f"   Parameters read: {len(result)}")
        
        # Show sample values
        print("\n   Sample values (first 5):")
        for i, (param_id, value) in enumerate(list(result.items())[:5]):
            param_name = plc._parameter_cache.get(param_id, {}).get('name', 'N/A')
            print(f"   {i+1}. {param_name}: {value}")
        
        return duration
        
    except Exception as e:
        print(f"❌ Bulk read execution error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_individual_reads(plc, sample_size=10):
    """Test individual reads for comparison."""
    print("\n" + "="*80)
    print(f"TEST 5: Individual Reads (sample of {sample_size})")
    print("="*80)
    
    if not plc:
        print("❌ Skipping - PLC not connected")
        return None
    
    try:
        # Get sample parameter IDs
        param_ids = list(plc._parameter_cache.keys())[:sample_size]
        
        start_time = time.time()
        result = {}
        for param_id in param_ids:
            try:
                value = await plc.read_parameter(param_id)
                if value is not None:
                    result[param_id] = value
            except Exception as e:
                print(f"   ⚠️ Error reading {param_id}: {e}")
        
        duration = time.time() - start_time
        avg_per_param = duration / len(param_ids) if param_ids else 0
        
        print(f"✅ Individual reads completed")
        print(f"   Duration: {duration*1000:.0f}ms for {len(param_ids)} parameters")
        print(f"   Average per parameter: {avg_per_param*1000:.1f}ms")
        print(f"   Parameters read: {len(result)}")
        
        return duration
        
    except Exception as e:
        print(f"❌ Individual read error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_parallel_connections(plc):
    """Test if parallel connections are being created."""
    print("\n" + "="*80)
    print("TEST 6: Parallel Connection Test")
    print("="*80)
    
    if not plc or not plc._bulk_read_ranges:
        print("❌ Skipping - Bulk reads not initialized")
        return
    
    try:
        # Check if bulk read ranges exist
        holding_ranges = plc._bulk_read_ranges.get('holding_registers', [])
        coil_ranges = plc._bulk_read_ranges.get('coils', [])
        
        print(f"   Holding register ranges: {len(holding_ranges)}")
        print(f"   Coil ranges: {len(coil_ranges)}")
        
        if len(holding_ranges) > 1:
            print(f"\n   ✅ Multiple ranges detected - parallel connections should be used")
            print(f"   Expected: {len(holding_ranges)} parallel connections (limited by semaphore=4)")
        elif len(holding_ranges) == 1:
            print(f"\n   ⚠️ Only 1 range - no parallelism possible")
        else:
            print(f"\n   ❌ No ranges found")
            
    except Exception as e:
        print(f"❌ Parallel connection test error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all diagnostic tests."""
    print("\n" + "="*80)
    print("BULK READ DIAGNOSTIC TEST")
    print("="*80)
    print(f"PLC IP: {PLC_IP}")
    print(f"PLC Port: {PLC_PORT}")
    print(f"Byte Order: {PLC_BYTE_ORDER}")
    
    plc = None
    try:
        # Test 1: Connection
        plc = await test_plc_connection()
        if not plc:
            print("\n❌ Cannot proceed without PLC connection")
            return
        
        # Test 2: Parameter loading
        params_ok = await test_parameter_loading(plc)
        if not params_ok:
            print("\n⚠️ No parameters with read addresses - bulk reads cannot work")
            return
        
        # Test 3: Bulk read optimization
        bulk_ok = await test_bulk_read_optimization(plc)
        if not bulk_ok:
            print("\n⚠️ Bulk read optimization failed or no ranges created")
            return
        
        # Test 4: Bulk read execution
        bulk_duration = await test_bulk_read_execution(plc)
        
        # Test 5: Individual reads (for comparison)
        individual_duration = await test_individual_reads(plc, sample_size=10)
        
        # Test 6: Parallel connections
        await test_parallel_connections(plc)
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        if bulk_duration and individual_duration:
            speedup = individual_duration / bulk_duration if bulk_duration > 0 else 0
            print(f"Bulk read: {bulk_duration*1000:.0f}ms")
            print(f"Individual (10 params): {individual_duration*1000:.0f}ms")
            print(f"Estimated speedup: {speedup:.1f}x")
        
        if bulk_duration:
            total_params = len(plc._parameter_cache)
            estimated_individual = (individual_duration / 10) * total_params if individual_duration else 0
            print(f"\nEstimated time for all {total_params} parameters:")
            print(f"  Bulk read: {bulk_duration*1000:.0f}ms")
            print(f"  Individual: {estimated_individual*1000:.0f}ms")
            if estimated_individual > 0:
                print(f"  Speedup: {estimated_individual/bulk_duration:.1f}x")
        
    finally:
        if plc:
            await plc.disconnect()
            print("\n✅ Disconnected from PLC")


if __name__ == "__main__":
    asyncio.run(main())

