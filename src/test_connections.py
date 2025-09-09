"""
Connection testing module for ALD Control System.
Tests PLC, Supabase, and realtime channel connections.
"""
import asyncio
from datetime import datetime
from src.log_setup import logger
from src.db import get_supabase, create_async_supabase
from src.plc.manager import plc_manager
from src.config import MACHINE_ID, PLC_TYPE, PLC_IP, PLC_PORT

async def test_supabase_connection():
    """Test Supabase database connection."""
    print("\n📊 Testing Supabase Connection...")
    try:
        supabase = get_supabase()
        
        # Test basic query
        result = supabase.table('machines').select('id,serial_number,status').eq('id', MACHINE_ID).execute()
        
        if result.data:
            print(f"  ✅ Database connection successful")
            print(f"  📍 Machine ID: {MACHINE_ID}")
            print(f"  📍 Machine Serial: {result.data[0].get('serial_number', 'N/A')}")
            print(f"  📍 Machine Status: {result.data[0].get('status', 'N/A')}")
            return True
        else:
            print(f"  ⚠️ Machine {MACHINE_ID} not found in database")
            return False
            
    except Exception as e:
        print(f"  ❌ Database connection failed: {str(e)}")
        return False

async def test_realtime_channels():
    """Test Supabase realtime channel subscription."""
    print("\n📡 Testing Realtime Channels...")
    try:
        async_supabase = await create_async_supabase()
        
        # Create a test channel
        test_channel = async_supabase.channel("test-channel")
        
        # Track if we received an event
        event_received = asyncio.Event()
        
        def on_event(payload):
            print(f"  📨 Received realtime event: {payload}")
            event_received.set()
        
        # Subscribe to a test channel
        test_channel = test_channel.on_postgres_changes(
            event="*",
            schema="public",
            table="parameter_control_commands",
            callback=on_event
        )
        
        await test_channel.subscribe()
        print(f"  ✅ Realtime channel subscribed successfully")
        
        # Wait briefly to see if we get any events
        try:
            await asyncio.wait_for(event_received.wait(), timeout=2.0)
            print(f"  ✅ Realtime events working")
        except asyncio.TimeoutError:
            print(f"  ℹ️ No realtime events received (this is normal if no commands are being sent)")
        
        # Unsubscribe
        await test_channel.unsubscribe()
        return True
        
    except Exception as e:
        print(f"  ⚠️ Realtime channel test failed: {str(e)}")
        print(f"  ℹ️ System will fall back to polling mode")
        return False

async def test_plc_connection():
    """Test PLC connection."""
    print(f"\n🔌 Testing PLC Connection (Mode: {PLC_TYPE})...")
    
    if PLC_TYPE == "simulation":
        print(f"  ℹ️ Running in simulation mode - no real PLC required")
        
    try:
        # Try to initialize PLC with timeout
        success = await asyncio.wait_for(
            plc_manager.initialize(),
            timeout=10.0
        )
        
        if success:
            print(f"  ✅ PLC connection successful")
            
            if PLC_TYPE == "real":
                print(f"  📍 PLC IP: {PLC_IP}")
                print(f"  📍 PLC Port: {PLC_PORT}")
            
            # Try to read all parameters
            try:
                params = await plc_manager.read_all_parameters()
                print(f"  ✅ Successfully read {len(params)} parameters from PLC")
                
                # Show first few parameters
                for i, (name, value) in enumerate(list(params.items())[:3]):
                    print(f"    - {name}: {value}")
                if len(params) > 3:
                    print(f"    ... and {len(params) - 3} more")
                    
            except Exception as e:
                print(f"  ⚠️ Could not read parameters: {str(e)}")
            
            # Disconnect after test
            await plc_manager.disconnect()
            return True
        else:
            print(f"  ❌ PLC initialization failed")
            return False
            
    except asyncio.TimeoutError:
        print(f"  ⚠️ PLC connection timed out")
        if PLC_TYPE == "real":
            print(f"  📍 Check PLC IP: {PLC_IP}")
            print(f"  📍 Check PLC Port: {PLC_PORT}")
            print(f"  📍 Ensure PLC is powered on and network accessible")
        return False
    except Exception as e:
        print(f"  ❌ PLC connection error: {str(e)}")
        return False

async def test_machine_health_table():
    """Test if machine_health table exists and is accessible."""
    print("\n🏥 Testing Machine Health Table...")
    try:
        supabase = get_supabase()
        
        # Try to query machine_health table
        result = supabase.table('machine_health').select('*').eq('machine_id', MACHINE_ID).execute()
        
        print(f"  ✅ Machine health table accessible")
        if result.data:
            print(f"  📍 Existing health record found")
        else:
            print(f"  ℹ️ No health record yet (will be created on first run)")
        return True
        
    except Exception as e:
        if "machine_health" in str(e):
            print(f"  ❌ Machine health table not found - please run migration")
            print(f"  💡 Run the SQL migration in src/migrations/create_machine_health_table.sql")
        else:
            print(f"  ❌ Error accessing machine health table: {str(e)}")
        return False

async def run_connection_test():
    """Run all connection tests."""
    print("\n" + "="*60)
    print("ALD Control System - Connection Test Suite")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Machine ID: {MACHINE_ID}")
    print(f"PLC Type: {PLC_TYPE}")
    
    results = {}
    
    # Test Supabase
    results['supabase'] = await test_supabase_connection()
    
    # Test Machine Health Table
    results['health_table'] = await test_machine_health_table()
    
    # Test Realtime Channels
    results['realtime'] = await test_realtime_channels()
    
    # Test PLC
    results['plc'] = await test_plc_connection()
    
    # Summary
    print("\n" + "="*60)
    print("Test Results Summary:")
    print("="*60)
    
    all_passed = True
    critical_passed = True
    
    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {component.title()}: {status}")
        
        if not passed:
            all_passed = False
            # Supabase is critical, others can fail gracefully
            if component == 'supabase':
                critical_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n🎉 All tests passed! System is ready to run.")
    elif critical_passed:
        print("\n⚠️ Some tests failed, but system can still run with reduced functionality.")
        print("  - PLC connection will retry automatically if failed")
        print("  - Realtime will fall back to polling if failed")
    else:
        print("\n❌ Critical tests failed. Please check configuration.")
        print("  - Ensure .env file has correct SUPABASE_URL and SUPABASE_KEY")
        print("  - Verify MACHINE_ID exists in database")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(run_connection_test())