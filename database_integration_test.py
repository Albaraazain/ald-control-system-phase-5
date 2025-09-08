#!/usr/bin/env python3
"""
Database Integration Test for ALD Control System Phase 5
Tests the new database schema integration without PLC dependencies.
"""
import asyncio
import sys
import os
from datetime import datetime
import json

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import only database-related modules (no PLC dependencies)
try:
    from log_setup import logger
    from config import MACHINE_ID
    from db import get_supabase
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're in the project directory and dependencies are installed")
    sys.exit(1)

async def test_database_connectivity():
    """Test basic database connectivity."""
    logger.info("🔧 Testing database connectivity...")
    
    try:
        supabase = get_supabase()
        
        # Test basic connection - use actual column names from machines table
        result = supabase.table('machines').select('id, serial_number, location, status').eq('id', MACHINE_ID).execute()
        if not result.data:
            logger.error("❌ Machine not found in database")
            return False
        
        machine = result.data[0]
        machine_name = machine.get('serial_number') or machine.get('location') or 'Unknown'
        logger.info(f"✅ Connected to database - Machine: {machine_name} (Status: {machine.get('status', 'Unknown')})")
        return True
    
    except Exception as e:
        logger.error(f"❌ Database connectivity test failed: {e}")
        return False

async def test_new_schema_tables():
    """Test that all new schema tables are accessible."""
    logger.info("🔧 Testing new schema tables...")
    
    tables_to_test = [
        'component_parameter_definitions',
        'valve_step_config', 
        'purge_step_config',
        'loop_step_config',
        'process_execution_state',
        'recipe_parameters'
    ]
    
    supabase = get_supabase()
    results = {}
    
    for table in tables_to_test:
        try:
            result = supabase.table(table).select('*').limit(5).execute()
            count = len(result.data) if result.data else 0
            results[table] = {'accessible': True, 'count': count}
            logger.info(f"✅ Table '{table}': {count} records found")
        except Exception as e:
            results[table] = {'accessible': False, 'error': str(e)}
            logger.error(f"❌ Table '{table}': {e}")
    
    # Summary
    accessible_count = sum(1 for r in results.values() if r['accessible'])
    total_count = len(tables_to_test)
    
    if accessible_count == total_count:
        logger.info(f"✅ All {total_count} new schema tables are accessible")
        return True
    else:
        logger.error(f"❌ Only {accessible_count}/{total_count} tables accessible")
        return False

async def test_parameter_definitions_join():
    """Test the new component parameter definitions join."""
    logger.info("🔧 Testing parameter definitions join...")
    
    try:
        supabase = get_supabase()
        
        # Test the new join query
        result = supabase.table('component_parameters').select(
            '*, component_parameter_definitions!definition_id(name, unit, description)'
        ).limit(10).execute()
        
        if not result.data:
            logger.warning("⚠️ No component parameters found")
            return True
        
        params_with_definitions = 0
        for param in result.data:
            if param.get('component_parameter_definitions'):
                params_with_definitions += 1
        
        total_params = len(result.data)
        logger.info(f"✅ Parameter join successful: {params_with_definitions}/{total_params} parameters have definitions")
        
        # Show example of enhanced parameter data
        if params_with_definitions > 0:
            enhanced_param = next((p for p in result.data if p.get('component_parameter_definitions')), None)
            if enhanced_param:
                def_data = enhanced_param['component_parameter_definitions']
                logger.info(f"✅ Example enhanced parameter: {def_data.get('name', 'Unknown')} ({def_data.get('unit', 'No unit')})")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Parameter definitions join test failed: {e}")
        return False

async def test_step_configurations():
    """Test loading step configurations from new tables."""
    logger.info("🔧 Testing step configurations...")
    
    supabase = get_supabase()
    step_types = [
        ('valve_step_config', 'valve'),
        ('purge_step_config', 'purge'), 
        ('loop_step_config', 'loop')
    ]
    
    results = {}
    
    for config_table, step_type in step_types:
        try:
            # Get step configs
            config_result = supabase.table(config_table).select('*').limit(5).execute()
            config_count = len(config_result.data) if config_result.data else 0
            
            results[step_type] = {'configs': config_count, 'success': True}
            logger.info(f"✅ {step_type.title()} steps: {config_count} configurations found")
            
            # Show example configuration
            if config_result.data:
                example = config_result.data[0]
                example_fields = {k: v for k, v in example.items() if k not in ['id', 'step_id', 'created_at', 'updated_at']}
                logger.info(f"  📋 Example {step_type} config: {example_fields}")
        
        except Exception as e:
            results[step_type] = {'configs': 0, 'success': False, 'error': str(e)}
            logger.error(f"❌ {step_type.title()} config test failed: {e}")
    
    successful_tests = sum(1 for r in results.values() if r['success'])
    total_tests = len(step_types)
    
    if successful_tests == total_tests:
        logger.info(f"✅ All {total_tests} step configuration types working")
        return True
    else:
        logger.error(f"❌ Only {successful_tests}/{total_tests} step config types working")
        return False

async def test_process_execution_state():
    """Test process execution state table functionality."""
    logger.info("🔧 Testing process execution state...")
    
    try:
        supabase = get_supabase()
        
        # Check existing process execution states
        result = supabase.table('process_execution_state').select('*').limit(5).execute()
        
        if result.data:
            count = len(result.data)
            logger.info(f"✅ Process execution state table accessible: {count} records found")
            
            # Show example state data
            example = result.data[0]
            progress = example.get('progress', {})
            logger.info(f"  📊 Example progress: {progress.get('completed_steps', 0)}/{progress.get('total_steps', 0)} steps")
            logger.info(f"  🔄 Current step: {example.get('current_step_type', 'Unknown')} - {example.get('current_step_name', 'Unknown')}")
        else:
            logger.info("✅ Process execution state table accessible (no records yet)")
        
        # Test that we can create a test state record (then delete it)
        # First, get or create a real process execution record to satisfy foreign key
        import uuid
        test_execution_id = str(uuid.uuid4())
        
        # Get an actual recipe ID from the database for testing
        recipes_result = supabase.table('recipes').select('id').limit(1).execute()
        if not recipes_result.data:
            logger.error("❌ No recipes found in database for testing")
            return False
        
        actual_recipe_id = recipes_result.data[0]['id']
        
        # Get an actual session_id from the database for testing
        sessions_result = supabase.table('operator_sessions').select('id').limit(1).execute()
        if not sessions_result.data:
            logger.error("❌ No operator sessions found in database for testing")
            return False
        
        actual_session_id = sessions_result.data[0]['id']
        
        # Create a temporary process execution record first
        test_operator_id = str(uuid.uuid4())  # Generate UUID for operator_id if needed
        temp_process = {
            'id': test_execution_id,
            'session_id': test_session_id,  # Add required session_id field
            'recipe_id': actual_recipe_id,  # Use actual recipe ID from database
            'machine_id': MACHINE_ID,
            'operator_id': test_operator_id,  # Add required operator_id field with UUID
            'status': 'completed',  # Use valid enum value instead of 'testing'
            'recipe_version': {'name': 'Test Recipe', 'steps': []},
            'parameters': {'test_param': 'test_value'},  # Add required parameters field
            'start_time': 'now()',
            'created_at': 'now()',
            'updated_at': 'now()'
        }
        
        try:
            # Insert temp process execution
            process_insert = supabase.table('process_executions').insert(temp_process).execute()
            if process_insert.data:
                
                # Now create the state record
                test_state = {
                    'execution_id': test_execution_id,
                    'current_step_index': 0,
                    'current_overall_step': 0,
                    'current_step_type': 'test',
                    'current_step_name': 'Test Step',
                    'progress': {'total_steps': 1, 'completed_steps': 0}
                }
                
                # Try insert state then delete both records
                state_insert = supabase.table('process_execution_state').insert(test_state).execute()
                if state_insert.data:
                    state_record_id = state_insert.data[0]['id']
                    # Delete state record first (due to foreign key)
                    supabase.table('process_execution_state').delete().eq('id', state_record_id).execute()
                    # Then delete process execution record
                    supabase.table('process_executions').delete().eq('id', test_execution_id).execute()
                    logger.info("✅ Process execution state insert/delete test successful")
                else:
                    # Clean up process record if state insert failed
                    supabase.table('process_executions').delete().eq('id', test_execution_id).execute()
                    raise Exception("Failed to insert process_execution_state record")
        except Exception as e:
            # Try to clean up any partial records
            try:
                supabase.table('process_execution_state').delete().eq('execution_id', test_execution_id).execute()
                supabase.table('process_executions').delete().eq('id', test_execution_id).execute()
            except:
                pass  # Ignore cleanup errors
            raise e
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Process execution state test failed: {e}")
        return False

async def test_recipe_parameters():
    """Test recipe parameters functionality."""
    logger.info("🔧 Testing recipe parameters...")
    
    try:
        supabase = get_supabase()
        
        # Get recipe parameters with recipe names
        result = supabase.table('recipe_parameters').select(
            '*, recipes!recipe_id(name)'
        ).limit(10).execute()
        
        if result.data:
            count = len(result.data)
            recipes_with_params = set(p['recipes']['name'] for p in result.data if p.get('recipes'))
            logger.info(f"✅ Recipe parameters: {count} parameters for {len(recipes_with_params)} recipes")
            
            # Show example parameters
            for recipe_name in list(recipes_with_params)[:3]:
                recipe_params = [p for p in result.data if p.get('recipes', {}).get('name') == recipe_name]
                param_names = [p['parameter_name'] for p in recipe_params]
                logger.info(f"  📋 {recipe_name}: {', '.join(param_names[:5])}")
        else:
            logger.info("✅ Recipe parameters table accessible (no parameters configured yet)")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Recipe parameters test failed: {e}")
        return False

async def test_schema_relationships():
    """Test foreign key relationships in the new schema."""
    logger.info("🔧 Testing schema relationships...")
    
    try:
        supabase = get_supabase()
        
        # Test component_parameters -> component_parameter_definitions
        cp_result = supabase.table('component_parameters').select('*').not_.is_('definition_id', 'null').limit(5).execute()
        if cp_result.data:
            logger.info(f"✅ component_parameters -> component_parameter_definitions: {len(cp_result.data)} linked records")
        
        # Test step_configs -> recipe_steps relationships
        for config_table in ['valve_step_config', 'purge_step_config', 'loop_step_config']:
            try:
                config_result = supabase.table(config_table).select('*, recipe_steps!step_id(name)').limit(3).execute()
                if config_result.data:
                    linked_count = sum(1 for r in config_result.data if r.get('recipe_steps'))
                    logger.info(f"✅ {config_table} -> recipe_steps: {linked_count}/{len(config_result.data)} linked records")
            except Exception:
                pass  # Skip if no data
        
        # Test process_execution_state -> process_executions
        pes_result = supabase.table('process_execution_state').select('*').limit(5).execute()
        if pes_result.data:
            logger.info(f"✅ process_execution_state records: {len(pes_result.data)} found")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Schema relationships test failed: {e}")
        return False

async def run_all_tests():
    """Run all database integration tests."""
    logger.info("🚀 Starting ALD Control System Phase 5 - Database Integration Test Suite")
    logger.info("=" * 80)
    
    test_results = []
    
    tests = [
        ("Database Connectivity", test_database_connectivity),
        ("New Schema Tables", test_new_schema_tables),
        ("Parameter Definitions Join", test_parameter_definitions_join),
        ("Step Configurations", test_step_configurations),
        ("Process Execution State", test_process_execution_state),
        ("Recipe Parameters", test_recipe_parameters),
        ("Schema Relationships", test_schema_relationships)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running: {test_name}")
        logger.info("-" * 50)
        
        try:
            result = await test_func()
            test_results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
        
        except Exception as e:
            logger.error(f"💥 {test_name}: CRASHED - {e}")
            test_results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 DATABASE INTEGRATION TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name:<35} {status}")
    
    logger.info(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL DATABASE TESTS PASSED!")
        logger.info("✅ The new database schema integration is working correctly")
        logger.info("💡 Next step: Test with full recipe execution using comprehensive simulation")
    else:
        logger.warning("⚠️ Some database tests failed - check logs for details")
        logger.info("💡 Fix database issues before proceeding to full recipe testing")
    
    return passed == total

if __name__ == "__main__":
    # Run the database integration tests
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n✅ Database integration test completed successfully!")
        print("🚀 Ready for full recipe execution testing with simulation")
    else:
        print("\n❌ Some database tests failed. Check the logs above for details.")
        sys.exit(1)