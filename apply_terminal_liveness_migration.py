#!/usr/bin/env python3
"""Apply terminal liveness migration"""

import os
import sys
from supabase import create_client

# Load environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read migration file
with open('supabase/migrations/20251029160500_create_terminal_liveness.sql', 'r') as f:
    migration_sql = f.read()

print("Applying terminal liveness migration...")
print(f"Migration size: {len(migration_sql)} characters")

# Split into smaller chunks if needed (Postgres can handle large statements)
# But we'll send it all at once via execute_sql
try:
    # Use PostgREST's raw SQL execution (if available)
    # Note: This might not work depending on Supabase setup
    # We may need to use psql or similar
    print("Note: This requires direct database access.")
    print("Please run: cat supabase/migrations/20251029160500_create_terminal_liveness.sql | psql <connection_string>")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
