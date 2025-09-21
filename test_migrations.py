#!/usr/bin/env python3
"""
Simple script to test if the migrations can be applied manually.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from db import get_supabase
from log_setup import logger


def test_column_existence():
    """Test if the new columns exist in parameter_control_commands table"""
    try:
        supabase = get_supabase()

        # Try to query the table with the new columns
        result = supabase.table('parameter_control_commands').select(
            'id, parameter_name, component_parameter_id, write_modbus_address, modbus_address'
        ).limit(1).execute()

        logger.info("✅ All required columns exist in parameter_control_commands table")
        return True

    except Exception as e:
        logger.error(f"❌ Required columns missing: {e}")
        return False


def apply_migrations_manually():
    """Apply migrations manually using ALTER TABLE through the supabase-py client"""
    try:
        supabase = get_supabase()

        logger.info("Attempting to add missing columns manually...")

        # Test if columns exist first
        if test_column_existence():
            logger.info("✅ All columns already exist, no migration needed")
            return True

        # Try adding columns one by one through direct SQL execution
        # This may not work with supabase-py, but let's try
        logger.error("❌ Columns missing. Please run migrations manually through Supabase dashboard.")
        logger.info("Required migrations:")
        logger.info("1. src/migrations/add_parameter_command_address_override.sql")
        logger.info("2. src/migrations/add_component_parameter_id_column.sql")

        return False

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    load_dotenv()
    success = apply_migrations_manually()
    sys.exit(0 if success else 1)