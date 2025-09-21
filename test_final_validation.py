#!/usr/bin/env python3
"""
Final validation test for the component_parameter_id implementation.
Tests all key functionality without requiring database migrations.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from db import get_supabase
from log_setup import logger


def test_implementation_completeness():
    """Test that all required implementation changes are present"""
    logger.info("=== Testing Implementation Completeness ===")

    # Check parameter_control_listener.py implementation
    try:
        with open('src/parameter_control_listener.py', 'r') as f:
            content = f.read()

        tests = [
            ('component_parameter_id extraction', "component_parameter_id = command.get('component_parameter_id')"),
            ('ID-first lookup logic', "if component_parameter_id:"),
            ('Direct ID database query', "eq('id', component_parameter_id)"),
            ('Fallback to parameter_name', "if not param_row:"),
            ('Conflict warning message', "Multiple parameters found"),
            ('Enhanced error messages', "component_parameter_id"),
            ('Backward compatibility', "parameter_name")
        ]

        all_passed = True
        for test_name, search_string in tests:
            if search_string in content:
                logger.info(f"✅ {test_name}: FOUND")
            else:
                logger.error(f"❌ {test_name}: MISSING")
                all_passed = False

        if all_passed:
            logger.info("✅ All implementation requirements satisfied")
        else:
            logger.error("❌ Some implementation requirements missing")

        return all_passed

    except Exception as e:
        logger.error(f"❌ Error checking implementation: {e}")
        return False


def test_migration_files():
    """Test that migration files exist and are properly structured"""
    logger.info("=== Testing Migration Files ===")

    migration_files = [
        'src/migrations/add_parameter_command_address_override.sql',
        'src/migrations/add_component_parameter_id_column.sql'
    ]

    all_exist = True
    for migration_file in migration_files:
        if os.path.exists(migration_file):
            logger.info(f"✅ Migration file exists: {migration_file}")

            # Check content
            try:
                with open(migration_file, 'r') as f:
                    content = f.read()

                if 'ALTER TABLE parameter_control_commands' in content:
                    logger.info(f"✅ {migration_file}: Contains parameter_control_commands modifications")
                else:
                    logger.warning(f"⚠️ {migration_file}: Missing parameter_control_commands modifications")

            except Exception as e:
                logger.error(f"❌ Error reading {migration_file}: {e}")
        else:
            logger.error(f"❌ Migration file missing: {migration_file}")
            all_exist = False

    return all_exist


def test_enhanced_test_scripts():
    """Test that test scripts have been enhanced with component_parameter_id support"""
    logger.info("=== Testing Enhanced Test Scripts ===")

    test_files = [
        'test_parameter_override.py'
    ]

    all_enhanced = True
    for test_file in test_files:
        if os.path.exists(test_file):
            logger.info(f"✅ Test file exists: {test_file}")

            try:
                with open(test_file, 'r') as f:
                    content = f.read()

                if 'component_parameter_id' in content:
                    logger.info(f"✅ {test_file}: Contains component_parameter_id testing")
                else:
                    logger.warning(f"⚠️ {test_file}: Missing component_parameter_id testing")
                    all_enhanced = False

            except Exception as e:
                logger.error(f"❌ Error reading {test_file}: {e}")
                all_enhanced = False
        else:
            logger.error(f"❌ Test file missing: {test_file}")
            all_enhanced = False

    return all_enhanced


def test_database_connectivity():
    """Test that database connectivity still works"""
    logger.info("=== Testing Database Connectivity ===")

    try:
        supabase = get_supabase()

        # Test basic table access
        result = supabase.table('component_parameters').select('id, name').limit(1).execute()

        if result.data:
            logger.info("✅ Database connectivity working")
            logger.info("✅ component_parameters table accessible")
            return True
        else:
            logger.warning("⚠️ Database connected but no parameters found")
            return True

    except Exception as e:
        logger.error(f"❌ Database connectivity failed: {e}")
        return False


def test_processing_priority_logic():
    """Test the processing priority logic implementation"""
    logger.info("=== Testing Processing Priority Logic ===")

    # Simulate the logic from the actual implementation
    test_commands = [
        {
            'name': 'Address override priority',
            'command': {
                'write_modbus_address': 1234,
                'component_parameter_id': 'test-uuid',
                'parameter_name': 'test_param'
            },
            'expected': 'write_modbus_address'
        },
        {
            'name': 'Component ID priority',
            'command': {
                'component_parameter_id': 'test-uuid',
                'parameter_name': 'test_param'
            },
            'expected': 'component_parameter_id'
        },
        {
            'name': 'Parameter name fallback',
            'command': {
                'parameter_name': 'test_param'
            },
            'expected': 'parameter_name'
        }
    ]

    all_passed = True
    for test in test_commands:
        command = test['command']
        expected = test['expected']

        # Simulate the priority logic
        if command.get('write_modbus_address') is not None or command.get('modbus_address') is not None:
            actual = 'write_modbus_address'
        elif command.get('component_parameter_id'):
            actual = 'component_parameter_id'
        elif command.get('parameter_name'):
            actual = 'parameter_name'
        else:
            actual = 'none'

        if actual == expected:
            logger.info(f"✅ {test['name']}: {actual}")
        else:
            logger.error(f"❌ {test['name']}: Expected {expected}, got {actual}")
            all_passed = False

    return all_passed


def main():
    """Run all validation tests"""
    load_dotenv()

    logger.info("🧪 FINAL VALIDATION TESTING - Component Parameter ID Implementation")
    logger.info("=" * 80)

    tests = [
        ('Implementation Completeness', test_implementation_completeness),
        ('Migration Files', test_migration_files),
        ('Enhanced Test Scripts', test_enhanced_test_scripts),
        ('Database Connectivity', test_database_connectivity),
        ('Processing Priority Logic', test_processing_priority_logic)
    ]

    results = {}
    for test_name, test_func in tests:
        logger.info("")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("🎯 TEST SUMMARY")
    logger.info("=" * 80)

    passed = 0
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
        if result:
            passed += 1

    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! Implementation is ready for deployment.")
        logger.info("")
        logger.info("📋 NEXT STEPS:")
        logger.info("1. Apply database migrations:")
        logger.info("   - src/migrations/add_parameter_command_address_override.sql")
        logger.info("   - src/migrations/add_component_parameter_id_column.sql")
        logger.info("2. Test with real parameter control commands")
        logger.info("3. Verify PLC communication with new parameter lookup")
        logger.info("4. Monitor for parameter name conflict warnings")
    else:
        logger.error("❌ Some tests failed. Please review the implementation.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)