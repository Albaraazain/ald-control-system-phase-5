#!/usr/bin/env python3
"""Cleanup stale terminal entries in database"""
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

# Call detect_dead_terminals RPC
result = client.rpc('detect_dead_terminals', {'heartbeat_timeout_seconds': 30}).execute()

print(f'Found {len(result.data)} dead terminals')
for term in result.data:
    tid = term.get('terminal_id')
    ttype = term.get('terminal_type')
    pid = term.get('process_id')

    print(f'  Marking {ttype} (PID {pid}) as crashed...')

    # Mark as crashed
    client.rpc('mark_terminal_crashed', {
        'terminal_instance_id': tid,
        'crash_reason': 'Stale entry - process not found'
    }).execute()

print('✅ Cleanup complete')
