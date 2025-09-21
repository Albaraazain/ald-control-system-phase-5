#!/usr/bin/env python3
"""
Test script for parameter control command modbus address override functionality.
This script tests the new override mechanism that allows commands to specify their own modbus address.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from db import get_supabase
from log_setup import logger


def test_override_mechanism():
    """Test the modbus address override mechanism"""

    logger.info("Testing parameter control command modbus address override mechanism")

    try:
        supabase = get_supabase()

        # Check if the new columns exist
        logger.info("Checking if override columns exist in parameter_control_commands table...")

        # Try to query with the new columns to verify they exist
        result = supabase.table('parameter_control_commands').select(
            'id, parameter_name, target_value, write_modbus_address, modbus_address, component_parameter_id'
        ).limit(1).execute()

        logger.info("✅ Override columns exist in parameter_control_commands table")

        # Test 1: Command with override address
        logger.info("Testing command creation with override address...")

        test_command_1 = {
            'machine_id': os.getenv('MACHINE_ID'),
            'parameter_name': 'test_power_on',
            'target_value': 1.0,
            'write_modbus_address': 9999,  # Override address
            'timeout_ms': 30000
        }

        insert_result_1 = supabase.table('parameter_control_commands').insert(test_command_1).execute()

        if insert_result_1.data:
            command_id_1 = insert_result_1.data[0]['id']
            logger.info(f"✅ Successfully created test command {command_id_1} with override address 9999")

            # Clean up test command
            supabase.table('parameter_control_commands').delete().eq('id', command_id_1).execute()
            logger.info(f"✅ Cleaned up test command {command_id_1}")
        else:
            logger.error("❌ Failed to create test command with override address")

        # Test 2: Command with component_parameter_id (need to find a real parameter first)
        logger.info("Testing command creation with component_parameter_id...")

        # Find a real parameter to test with
        param_result = supabase.table('component_parameters').select('id, name').limit(1).execute()

        if param_result.data:
            test_param_id = param_result.data[0]['id']
            test_param_name = param_result.data[0]['name']

            test_command_2 = {
                'machine_id': os.getenv('MACHINE_ID'),
                'parameter_name': test_param_name,
                'component_parameter_id': test_param_id,  # Direct parameter ID
                'target_value': 1.0,
                'timeout_ms': 30000
            }

            insert_result_2 = supabase.table('parameter_control_commands').insert(test_command_2).execute()

            if insert_result_2.data:
                command_id_2 = insert_result_2.data[0]['id']
                logger.info(f"✅ Successfully created test command {command_id_2} with component_parameter_id {test_param_id}")

                # Clean up test command
                supabase.table('parameter_control_commands').delete().eq('id', command_id_2).execute()
                logger.info(f"✅ Cleaned up test command {command_id_2}")
            else:
                logger.error("❌ Failed to create test command with component_parameter_id")
        else:
            logger.warning("⚠️ No parameters found in component_parameters table for component_parameter_id test")

    except Exception as e:
        error_str = str(e).lower()
        if "column" in error_str and any(col in error_str for col in ["write_modbus_address", "modbus_address", "component_parameter_id"]):
            logger.error("❌ Required columns do not exist. Please run the migrations first:")
            logger.error("   1. Run: src/migrations/add_parameter_command_address_override.sql")
            logger.error("   2. Run: src/migrations/add_component_parameter_id_column.sql")
        else:
            logger.error(f"❌ Test failed: {e}")


def show_usage():
    """Show how to use the enhanced parameter control command system"""

    logger.info("=== Parameter Control Command Enhanced Usage ===")
    logger.info("")
    logger.info("Method 1: Use component_parameter_id for precise parameter targeting (RECOMMENDED):")
    logger.info("   INSERT INTO parameter_control_commands (")
    logger.info("       machine_id, parameter_name, component_parameter_id, target_value")
    logger.info("   ) VALUES (")
    logger.info("       'your-machine-id', 'power_on', 'uuid-of-parameter', 1.0")
    logger.info("   );")
    logger.info("")
    logger.info("Method 2: Use modbus address override for direct hardware control:")
    logger.info("   INSERT INTO parameter_control_commands (")
    logger.info("       machine_id, parameter_name, target_value, write_modbus_address")
    logger.info("   ) VALUES (")
    logger.info("       'your-machine-id', 'power_on', 1.0, 1234")
    logger.info("   );")
    logger.info("")
    logger.info("Method 3: Legacy parameter_name lookup (fallback, may cause conflicts):")
    logger.info("   INSERT INTO parameter_control_commands (")
    logger.info("       machine_id, parameter_name, target_value")
    logger.info("   ) VALUES (")
    logger.info("       'your-machine-id', 'power_on', 1.0")
    logger.info("   );")
    logger.info("")
    logger.info("Optional: Add data_type for binary/coil operations (defaults to 'float'):")
    logger.info("   ... data_type: 'binary' for coils, 'float' for holding registers")
    logger.info("")
    logger.info("System Processing Priority:")
    logger.info("1. Check for write_modbus_address/modbus_address - direct hardware write")
    logger.info("2. Check for component_parameter_id - precise parameter lookup")
    logger.info("3. Fall back to parameter_name lookup (backward compatibility)")
    logger.info("")
    logger.info("Benefits of component_parameter_id:")
    logger.info("- Eliminates conflicts when multiple parameters have same name")
    logger.info("- Ensures commands target the correct parameter on the right machine")
    logger.info("- More reliable and predictable parameter control")
    logger.info("")


if __name__ == "__main__":
    load_dotenv()

    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        show_usage()
    else:
        test_override_mechanism()
        print()
        show_usage()