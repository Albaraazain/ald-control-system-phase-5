#!/usr/bin/env python3
"""
Recipe Execution Audit Query Utility

Provides comprehensive querying and analysis of recipe execution audit trail.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_KEY')
)


def get_process_audit_trail(process_id: str):
    """Get complete audit trail for a process execution, ordered by sequence."""
    result = supabase.table('recipe_audit_summary').select('*').eq(
        'process_id', process_id
    ).order('step_sequence').execute()

    print(f"\n📋 Audit Trail for Process: {process_id}\n")
    print("=" * 120)

    if not result.data:
        print("No audit records found.")
        return

    total_duration = 0
    for i, record in enumerate(result.data, 1):
        print(f"\n{i}. Step {record['step_sequence']}: {record['step_name']}")
        print(f"   Operation: {record['operation_type']} - {record['parameter_name']}")
        print(f"   Target: {record['target_value']}")
        if record['duration_ms']:
            print(f"   Duration: {record['duration_ms']}ms")
        if record['plc_write_duration_ms']:
            print(f"   PLC Write: {record['plc_write_duration_ms']}ms")
            total_duration += record['plc_write_duration_ms']
        print(f"   Status: {record['final_status']}")
        if record['error_message']:
            print(f"   Error: {record['error_message']}")
        print(f"   Timestamp: {record['created_at']}")

    print(f"\n{'=' * 120}")
    print(f"Total PLC Write Time: {total_duration}ms")
    print(f"Process Status: {result.data[0]['process_status']}")
    print(f"Recipe: {result.data[0]['recipe_name']}")


def get_recipe_performance_stats(recipe_id: str, limit: int = 10):
    """Analyze performance statistics for a recipe across multiple executions."""
    result = supabase.table('recipe_execution_audit').select(
        'process_id, step_sequence, operation_type, parameter_name, plc_write_duration_ms, final_status'
    ).eq('recipe_id', recipe_id).execute()

    if not result.data:
        print(f"\nNo audit records found for recipe: {recipe_id}")
        return

    print(f"\n📊 Performance Statistics for Recipe: {recipe_id}\n")
    print("=" * 100)

    # Group by process_id
    processes = {}
    for record in result.data:
        pid = record['process_id']
        if pid not in processes:
            processes[pid] = {
                'operations': [],
                'total_plc_time': 0,
                'failed_operations': 0
            }
        processes[pid]['operations'].append(record)
        if record['plc_write_duration_ms']:
            processes[pid]['total_plc_time'] += record['plc_write_duration_ms']
        if record['final_status'] == 'failed':
            processes[pid]['failed_operations'] += 1

    # Calculate statistics
    plc_times = [p['total_plc_time'] for p in processes.values()]
    avg_plc_time = sum(plc_times) / len(plc_times) if plc_times else 0
    min_plc_time = min(plc_times) if plc_times else 0
    max_plc_time = max(plc_times) if plc_times else 0

    print(f"Total Executions: {len(processes)}")
    print(f"Average PLC Time: {avg_plc_time:.1f}ms")
    print(f"Min PLC Time: {min_plc_time}ms")
    print(f"Max PLC Time: {max_plc_time}ms")

    # Show operation breakdown
    op_stats = {}
    for record in result.data:
        op = record['parameter_name']
        if op not in op_stats:
            op_stats[op] = {'count': 0, 'total_time': 0, 'failures': 0}
        op_stats[op]['count'] += 1
        if record['plc_write_duration_ms']:
            op_stats[op]['total_time'] += record['plc_write_duration_ms']
        if record['final_status'] == 'failed':
            op_stats[op]['failures'] += 1

    print(f"\n📊 Operation Breakdown:")
    for op, stats in sorted(op_stats.items()):
        avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
        print(f"   {op}: {stats['count']} operations, avg {avg_time:.1f}ms, {stats['failures']} failures")


def get_recent_operations(machine_id: str, operation_type: str = None, limit: int = 10):
    """Get recent operations for a machine, optionally filtered by type."""
    query = supabase.table('recipe_audit_summary').select('*').eq('machine_id', machine_id)

    if operation_type:
        query = query.eq('operation_type', operation_type)

    result = query.order('created_at', desc=True).limit(limit).execute()

    print(f"\n🕒 Recent Operations for Machine: {machine_id}")
    if operation_type:
        print(f"   Filtered by: {operation_type}")
    print("=" * 100)

    if not result.data:
        print("No operations found.")
        return

    for record in result.data:
        print(f"\n{record['created_at']}")
        print(f"   {record['operation_type']}: {record['parameter_name']} = {record['target_value']}")
        print(f"   Recipe: {record['recipe_name']}, Step: {record['step_name']}")
        print(f"   Status: {record['final_status']}")
        if record['plc_write_duration_ms']:
            print(f"   PLC Write: {record['plc_write_duration_ms']}ms")


def get_failed_operations(hours: int = 24):
    """Get all failed operations within the specified time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = supabase.table('recipe_audit_summary').select('*').eq(
        'final_status', 'failed'
    ).gte('created_at', cutoff.isoformat()).execute()

    print(f"\n❌ Failed Operations (last {hours} hours)\n")
    print("=" * 100)

    if not result.data:
        print("No failed operations found.")
        return

    for record in result.data:
        print(f"\n{record['created_at']}")
        print(f"   Recipe: {record['recipe_name']}")
        print(f"   Step: {record['step_name']}")
        print(f"   Operation: {record['operation_type']} - {record['parameter_name']}")
        print(f"   Target: {record['target_value']}")
        if record['error_message']:
            print(f"   Error: {record['error_message']}")
        print(f"   Process ID: {record['process_id']}")


def compare_recipe_runs(process_ids: list[str]):
    """Compare multiple recipe execution runs side-by-side."""
    print(f"\n🔍 Comparing {len(process_ids)} Recipe Runs\n")
    print("=" * 120)

    for pid in process_ids:
        result = supabase.table('recipe_audit_summary').select('*').eq(
            'process_id', pid
        ).order('step_sequence').execute()

        if not result.data:
            print(f"No data for process {pid}")
            continue

        total_plc_time = sum(r['plc_write_duration_ms'] or 0 for r in result.data)
        failed = sum(1 for r in result.data if r['final_status'] == 'failed')

        print(f"\nProcess: {pid}")
        print(f"   Recipe: {result.data[0]['recipe_name']}")
        print(f"   Operations: {len(result.data)}")
        print(f"   Total PLC Time: {total_plc_time}ms")
        print(f"   Failed Operations: {failed}")
        print(f"   Status: {result.data[0]['process_status']}")


def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        print("\nRecipe Execution Audit Query Utility\n")
        print("Usage:")
        print("  python audit_query_util.py process <process_id>")
        print("  python audit_query_util.py recipe <recipe_id>")
        print("  python audit_query_util.py recent <machine_id> [operation_type] [limit]")
        print("  python audit_query_util.py failures [hours]")
        print("  python audit_query_util.py compare <process_id1> <process_id2> ...")
        return

    command = sys.argv[1]

    if command == 'process' and len(sys.argv) >= 3:
        get_process_audit_trail(sys.argv[2])

    elif command == 'recipe' and len(sys.argv) >= 3:
        get_recipe_performance_stats(sys.argv[2])

    elif command == 'recent' and len(sys.argv) >= 3:
        machine_id = sys.argv[2]
        operation_type = sys.argv[3] if len(sys.argv) > 3 else None
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        get_recent_operations(machine_id, operation_type, limit)

    elif command == 'failures':
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        get_failed_operations(hours)

    elif command == 'compare' and len(sys.argv) >= 3:
        process_ids = sys.argv[2:]
        compare_recipe_runs(process_ids)

    else:
        print("Invalid command. Use --help for usage information.")


if __name__ == '__main__':
    main()
