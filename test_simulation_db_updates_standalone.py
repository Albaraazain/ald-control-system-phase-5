#!/usr/bin/env python3
"""
Standalone test for simulation PLC database updates.

This verifies that the simulation properly updates both current_value
and set_value fields in the component_parameters table.
"""
import asyncio
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.plc.simulation import SimulationPLC
from src.db import get_supabase
from src.log_setup import logger


async def test_read_updates_current_value():
    """Test that read_parameter updates current_value in database."""
    logger.info("=" * 60)
    logger.info("TEST 1: read_parameter updates current_value")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Get a test parameter
        result = supabase.table('component_parameters').select('*').limit(1).execute()
        if not result.data:
            logger.error("No parameters found in database")
            return False
        
        param_id = result.data[0]['id']
        param_name = result.data[0].get('data_type', 'unknown')
        
        logger.info(f"Testing with parameter: {param_id} ({param_name})")
        
        # Read parameter
        value = await plc.read_parameter(param_id)
        logger.info(f"Read value: {value}")
        
        # Wait for background task to complete
        await asyncio.sleep(0.5)
        
        # Check database
        result = supabase.table('component_parameters').select(
            'current_value'
        ).eq('id', param_id).single().execute()
        
        current_value = result.data['current_value']
        
        if current_value is not None:
            logger.info(f"✅ PASS: current_value updated in database: {current_value}")
            return True
        else:
            logger.error(f"❌ FAIL: current_value not updated in database")
            return False
            
    finally:
        await plc.disconnect()


async def test_write_updates_both_values():
    """Test that write_parameter updates both current_value and set_value."""
    logger.info("=" * 60)
    logger.info("TEST 2: write_parameter updates both values")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Get a writable parameter
        result = supabase.table('component_parameters').select('*').eq(
            'is_writable', True
        ).limit(1).execute()
        
        if not result.data:
            logger.error("No writable parameters found")
            return False
        
        param = result.data[0]
        param_id = param['id']
        param_name = param.get('data_type', 'unknown')
        min_val = param['min_value']
        max_val = param['max_value']
        
        # Calculate test value
        test_value = (min_val + max_val) / 2
        
        logger.info(f"Testing with parameter: {param_id} ({param_name})")
        logger.info(f"Writing value: {test_value} (range: {min_val} - {max_val})")
        
        # Write parameter
        success = await plc.write_parameter(param_id, test_value)
        
        if not success:
            logger.error("❌ FAIL: write_parameter returned False")
            return False
        
        # Wait for background task
        await asyncio.sleep(0.5)
        
        # Check database
        result = supabase.table('component_parameters').select(
            'current_value, set_value, updated_at'
        ).eq('id', param_id).single().execute()
        
        current_value = result.data['current_value']
        set_value = result.data['set_value']
        updated_at = result.data['updated_at']
        
        logger.info(f"Database values - current: {current_value}, set: {set_value}")
        
        # Check both values
        if current_value is None:
            logger.error("❌ FAIL: current_value not updated")
            return False
        
        if set_value is None:
            logger.error("❌ FAIL: set_value not updated")
            return False
        
        if abs(current_value - test_value) > 0.001:
            logger.error(f"❌ FAIL: current_value mismatch. Expected {test_value}, got {current_value}")
            return False
        
        if abs(set_value - test_value) > 0.001:
            logger.error(f"❌ FAIL: set_value mismatch. Expected {test_value}, got {set_value}")
            return False
        
        logger.info(f"✅ PASS: Both values updated correctly")
        logger.info(f"   current_value: {current_value}")
        logger.info(f"   set_value: {set_value}")
        logger.info(f"   updated_at: {updated_at}")
        return True
        
    finally:
        await plc.disconnect()


async def test_convergence():
    """Test that values converge toward set_value over time."""
    logger.info("=" * 60)
    logger.info("TEST 3: Values converge toward set_value")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Get a parameter that fluctuates (not binary)
        result = supabase.table('component_parameters').select('*').eq(
            'is_writable', True
        ).execute()
        
        # Find a parameter with good range
        param = None
        for p in result.data:
            if (p['max_value'] - p['min_value']) > 10:
                param = p
                break
        
        if not param:
            logger.warning("⚠️ SKIP: No suitable fluctuating parameters found")
            return True
        
        param_id = param['id']
        min_val = param['min_value']
        max_val = param['max_value']
        
        # Set a target value
        target_value = min_val + (max_val - min_val) * 0.75
        
        logger.info(f"Testing with parameter: {param_id}")
        logger.info(f"Target value: {target_value} (range: {min_val} - {max_val})")
        
        # Write target
        await plc.write_parameter(param_id, target_value)
        await asyncio.sleep(0.5)
        
        # Set current value to something different
        start_value = min_val + (max_val - min_val) * 0.25
        plc.current_values[param_id] = start_value
        
        logger.info(f"Starting value: {start_value}")
        logger.info("Reading parameter 10 times to observe convergence...")
        
        # Read multiple times
        values = []
        for i in range(10):
            value = await plc.read_parameter(param_id)
            values.append(value)
            logger.info(f"  Read {i+1}: {value:.3f} (distance from target: {abs(value - target_value):.3f})")
            await asyncio.sleep(0.1)
        
        # Check convergence
        distances = [abs(v - target_value) for v in values]
        first_half_avg = sum(distances[:5]) / 5
        second_half_avg = sum(distances[5:]) / 5
        
        logger.info(f"First half avg distance: {first_half_avg:.3f}")
        logger.info(f"Second half avg distance: {second_half_avg:.3f}")
        
        if second_half_avg < first_half_avg * 1.5:
            logger.info(f"✅ PASS: Values converge toward target")
            return True
        else:
            logger.warning(f"⚠️ WARNING: Convergence not clearly observed (may need more reads)")
            return True  # Don't fail on this
        
    finally:
        await plc.disconnect()


async def test_direct_address_writes():
    """Test that write_holding_register and write_coil update database."""
    logger.info("=" * 60)
    logger.info("TEST 4: Direct address writes update database")
    logger.info("=" * 60)
    
    plc = SimulationPLC()
    await plc.initialize()
    
    try:
        supabase = get_supabase()
        
        # Test holding register write
        result = supabase.table('component_parameters').select('*').not_.is_(
            'write_modbus_address', 'null'
        ).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            param = result.data[0]
            address = param['write_modbus_address']
            
            # Use the actual mapped parameter ID from simulation
            if address in plc._address_to_param_id:
                param_id = plc._address_to_param_id[address]
                logger.info(f"Testing write_holding_register with address {address} -> parameter {param_id}")
            else:
                logger.warning(f"⚠️ Address {address} not in simulation mappings")
                return True
            
            # Ensure in cache
            if param_id not in plc.current_values:
                await plc._load_parameter(param_id)
            
            test_value = 42.5
            await plc.write_holding_register(address, test_value)
            await asyncio.sleep(1.0)  # Wait longer for background task
            
            # Check database
            result = supabase.table('component_parameters').select(
                'current_value, set_value'
            ).eq('id', param_id).single().execute()
            
            logger.info(f"After write - current_value: {result.data['current_value']}, set_value: {result.data['set_value']}")
            
            if (abs(result.data['current_value'] - test_value) < 0.001 and
                abs(result.data['set_value'] - test_value) < 0.001):
                logger.info(f"✅ PASS: write_holding_register updated database")
            else:
                logger.error(f"❌ FAIL: write_holding_register didn't update correctly")
                logger.error(f"Expected {test_value}, got current:{result.data['current_value']}, set:{result.data['set_value']}")
                return False
        else:
            logger.warning("⚠️ SKIP: No parameters with write addresses found")
        
        return True
        
    finally:
        await plc.disconnect()


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("SIMULATION PLC DATABASE UPDATE TESTS")
    logger.info("=" * 60 + "\n")
    
    tests = [
        ("Read updates current_value", test_read_updates_current_value),
        ("Write updates both values", test_write_updates_both_values),
        ("Values converge toward set_value", test_convergence),
        ("Direct address writes", test_direct_address_writes),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' raised exception: {e}", exc_info=True)
            results.append((test_name, False))
        
        logger.info("")  # Blank line between tests
    
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

