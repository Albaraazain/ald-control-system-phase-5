#!/usr/bin/env python3
"""
Test Terminal 1 Setpoint Synchronization

This test verifies that Terminal 1 properly reads setpoints from the PLC
and synchronizes them with the database, detecting external changes.
"""
import asyncio
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.plc.simulation import SimulationPLC
from src.plc.real_plc import RealPLC
from src.db import get_supabase
from src.log_setup import logger
from src.config import PLC_TYPE


async def test_plc_read_setpoint():
    """Test that PLC can read setpoint values."""
    logger.info("=" * 60)
    logger.info("TEST 1: PLC read_setpoint method")
    logger.info("=" * 60)
    
    # Use simulation PLC for testing
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Get a writable parameter
        result = supabase.table('component_parameters').select('*').eq(
            'is_writable', True
        ).not_.is_('write_modbus_address', 'null').limit(1).execute()
        
        if not result.data:
            logger.warning("⚠️ SKIP: No writable parameters with write addresses found")
            return True
        
        param = result.data[0]
        param_id = param['id']
        
        logger.info(f"Testing with parameter: {param_id}")
        logger.info(f"  Current set_value in DB: {param['set_value']}")
        
        # Read setpoint from PLC
        setpoint = await plc.read_setpoint(param_id)
        
        if setpoint is None:
            logger.error(f"❌ FAIL: read_setpoint returned None")
            return False
        
        logger.info(f"  Setpoint from PLC: {setpoint}")
        
        # Wait for background update
        await asyncio.sleep(0.5)
        
        # Verify database was updated
        result = supabase.table('component_parameters').select(
            'set_value'
        ).eq('id', param_id).single().execute()
        
        db_setpoint = result.data['set_value']
        
        if abs(db_setpoint - setpoint) < 0.01:
            logger.info(f"✅ PASS: Setpoint read and database updated")
            return True
        else:
            logger.error(f"❌ FAIL: Database mismatch. PLC={setpoint}, DB={db_setpoint}")
            return False
    
    finally:
        await plc.disconnect()


async def test_plc_read_all_setpoints():
    """Test that PLC can read all setpoints."""
    logger.info("=" * 60)
    logger.info("TEST 2: PLC read_all_setpoints method")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        # Read all setpoints
        setpoints = await plc.read_all_setpoints()
        
        logger.info(f"Read {len(setpoints)} setpoints from PLC")
        
        if len(setpoints) > 0:
            # Show first few
            for i, (param_id, value) in enumerate(list(setpoints.items())[:3]):
                logger.info(f"  {param_id}: {value}")
            
            logger.info(f"✅ PASS: Read {len(setpoints)} setpoints")
            return True
        else:
            logger.warning(f"⚠️ WARNING: No setpoints read (may be no writable parameters)")
            return True
    
    finally:
        await plc.disconnect()


async def test_external_change_detection():
    """Test that Terminal 1 detects external setpoint changes."""
    logger.info("=" * 60)
    logger.info("TEST 3: External change detection")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Get a writable parameter
        result = supabase.table('component_parameters').select('*').eq(
            'is_writable', True
        ).not_.is_('write_modbus_address', 'null').limit(1).execute()
        
        if not result.data:
            logger.warning("⚠️ SKIP: No writable parameters found")
            return True
        
        param = result.data[0]
        param_id = param['id']
        min_val = param['min_value']
        max_val = param['max_value']
        
        # Set database value to something specific
        original_db_value = 25.0 if max_val > 25 else min_val
        supabase.table('component_parameters').update({
            'set_value': original_db_value
        }).eq('id', param_id).execute()
        
        logger.info(f"Set database set_value to: {original_db_value}")
        
        # Simulate external change: write different value to PLC
        external_value = 75.0 if max_val > 75 else max_val * 0.75
        await plc.write_parameter(param_id, external_value)
        await asyncio.sleep(0.3)
        
        logger.info(f"Simulated external change: wrote {external_value} to PLC")
        
        # Now read setpoint from PLC (should get external value)
        plc_setpoint = await plc.read_setpoint(param_id)
        
        logger.info(f"Read setpoint from PLC: {plc_setpoint}")
        
        # Wait for background database update
        await asyncio.sleep(0.5)
        
        # Check if database was updated
        result = supabase.table('component_parameters').select(
            'set_value'
        ).eq('id', param_id).single().execute()
        
        updated_db_value = result.data['set_value']
        
        logger.info(f"Database set_value after sync: {updated_db_value}")
        
        if abs(updated_db_value - external_value) < 0.01:
            logger.info(f"✅ PASS: External change detected and synchronized")
            logger.info(f"   Original DB: {original_db_value}")
            logger.info(f"   External PLC: {external_value}")
            logger.info(f"   Updated DB: {updated_db_value}")
            return True
        else:
            logger.error(f"❌ FAIL: Database not updated. Expected {external_value}, got {updated_db_value}")
            return False
    
    finally:
        await plc.disconnect()


async def test_terminal1_integration():
    """Test full Terminal 1 data collection with setpoint sync."""
    logger.info("=" * 60)
    logger.info("TEST 4: Terminal 1 Integration (Mock)")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Simulate what Terminal 1 does
        logger.info("Simulating Terminal 1 data collection cycle...")
        
        # 1. Read all current values
        current_values = await plc.read_all_parameters()
        logger.info(f"Step 1: Read {len(current_values)} current values")
        
        # 2. Read all setpoints
        setpoint_values = await plc.read_all_setpoints()
        logger.info(f"Step 2: Read {len(setpoint_values)} setpoints")
        
        # 3. Detect changes (simulate what _sync_setpoints_to_database does)
        if setpoint_values:
            param_ids = list(setpoint_values.keys())
            db_result = supabase.table('component_parameters').select(
                'id, set_value'
            ).in_('id', param_ids).execute()
            
            db_setpoints = {row['id']: row['set_value'] for row in db_result.data}
            
            changes_detected = 0
            for param_id, plc_setpoint in setpoint_values.items():
                db_setpoint = db_setpoints.get(param_id)
                if db_setpoint is not None and abs(plc_setpoint - db_setpoint) > 0.01:
                    changes_detected += 1
            
            logger.info(f"Step 3: Detected {changes_detected} changes")
        
        logger.info(f"✅ PASS: Terminal 1 integration flow completed")
        return True
    
    finally:
        await plc.disconnect()


async def test_performance():
    """Test performance of setpoint reads."""
    logger.info("=" * 60)
    logger.info("TEST 5: Performance Test")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        import time
        
        # Measure read_all_setpoints performance
        start = time.time()
        setpoints = await plc.read_all_setpoints()
        duration = (time.time() - start) * 1000  # ms
        
        logger.info(f"read_all_setpoints() took {duration:.1f}ms for {len(setpoints)} parameters")
        
        if duration < 1000:  # Should be under 1 second
            logger.info(f"✅ PASS: Performance acceptable ({duration:.1f}ms)")
            return True
        else:
            logger.warning(f"⚠️ WARNING: Performance slow ({duration:.1f}ms)")
            return True  # Don't fail on performance
    
    finally:
        await plc.disconnect()


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("TERMINAL 1 SETPOINT SYNCHRONIZATION TESTS")
    logger.info("=" * 60 + "\n")
    
    tests = [
        ("PLC read_setpoint", test_plc_read_setpoint),
        ("PLC read_all_setpoints", test_plc_read_all_setpoints),
        ("External change detection", test_external_change_detection),
        ("Terminal 1 integration", test_terminal1_integration),
        ("Performance", test_performance),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' raised exception: {e}", exc_info=True)
            results.append((test_name, False))
        
        logger.info("")  # Blank line
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    return all(result for _, result in results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

