#!/usr/bin/env python3
"""
Script to run database migrations for parameter control enhancements.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from db import get_supabase
from log_setup import logger


def run_migration(migration_file):
    """Run a SQL migration file"""
    try:
        supabase = get_supabase()

        # Read the migration file
        migration_path = os.path.join('src', 'migrations', migration_file)
        with open(migration_path, 'r') as f:
            sql_content = f.read()

        # Execute the migration using rpc to run raw SQL
        logger.info(f"Running migration: {migration_file}")

        # Split by semicolon to handle multiple statements
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        for stmt in statements:
            if stmt.upper().startswith(('ALTER', 'CREATE', 'COMMENT')):
                try:
                    # Use rpc to execute raw SQL
                    result = supabase.rpc('exec_sql', {'sql': stmt}).execute()
                    logger.info(f"✅ Executed: {stmt[:50]}...")
                except Exception as e:
                    if "already exists" in str(e) or "duplicate" in str(e):
                        logger.info(f"⚠️ Already exists: {stmt[:50]}...")
                    else:
                        logger.error(f"❌ Failed: {stmt[:50]}... - {e}")
                        return False

        logger.info(f"✅ Migration {migration_file} completed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Migration {migration_file} failed: {e}")
        return False


def main():
    load_dotenv()

    logger.info("Running parameter control migrations...")

    # Run migrations in order
    migrations = [
        'add_parameter_command_address_override.sql',
        'add_component_parameter_id_column.sql'
    ]

    for migration in migrations:
        if not run_migration(migration):
            logger.error(f"❌ Migration failed: {migration}")
            return False

    logger.info("✅ All migrations completed successfully")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)