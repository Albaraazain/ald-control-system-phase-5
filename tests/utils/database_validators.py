"""
Database validation utilities for ALD control system testing.

Provides efficient database state validators with optimized queries.

Usage:
    from tests.utils.database_validators import (
        validate_parameter_history,
        validate_recipe_execution_state,
        validate_machine_state,
        validate_no_orphaned_records
    )
"""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta


async def validate_parameter_history(
    db,
    parameter_id: int,
    start_time: datetime,
    end_time: datetime,
    expected_min_count: Optional[int] = None,
    expected_frequency_hz: float = 1.0
) -> Dict:
    """
    Validate parameter_value_history completeness.

    Returns validation result with gaps detected.
    """
    query = """
        SELECT COUNT(*) as count, MIN(timestamp) as first, MAX(timestamp) as last
        FROM parameter_value_history
        WHERE parameter_id = $1 AND timestamp BETWEEN $2 AND $3
    """

    result = await db.execute_query(query, parameter_id, start_time, end_time)
    actual_count = result[0]['count'] if result else 0

    duration_seconds = (end_time - start_time).total_seconds()
    expected_count = int(duration_seconds * expected_frequency_hz)

    return {
        "valid": actual_count >= (expected_min_count or expected_count * 0.95),
        "actual_count": actual_count,
        "expected_count": expected_count,
        "data_loss_percent": ((expected_count - actual_count) / expected_count * 100) if expected_count > 0 else 0,
        "first_timestamp": result[0]['first'] if result and result[0]['first'] else None,
        "last_timestamp": result[0]['last'] if result and result[0]['last'] else None
    }


async def validate_recipe_execution_state(
    db,
    recipe_id: int,
    expected_status: str = "completed"
) -> Dict:
    """
    Validate process_executions consistency.

    Checks recipe execution state and related tables.
    """
    query = """
        SELECT
            pe.status,
            pe.error_message,
            pe.completed_at,
            pe.created_at,
            COUNT(pes.id) as step_count
        FROM process_executions pe
        LEFT JOIN process_execution_state pes ON pe.id = pes.process_execution_id
        WHERE pe.recipe_id = $1
        GROUP BY pe.id, pe.status, pe.error_message, pe.completed_at, pe.created_at
        ORDER BY pe.created_at DESC
        LIMIT 1
    """

    result = await db.execute_query(query, recipe_id)

    if not result:
        return {"valid": False, "reason": "No execution record found"}

    execution = result[0]

    return {
        "valid": execution['status'] == expected_status,
        "status": execution['status'],
        "error_message": execution.get('error_message'),
        "step_count": execution['step_count'],
        "completed_at": execution.get('completed_at'),
        "duration_seconds": (execution['completed_at'] - execution['created_at']).total_seconds() if execution.get('completed_at') else None
    }


async def validate_machine_state(
    db,
    machine_id: str,
    expected_state: Optional[str] = None
) -> Dict:
    """
    Validate machine_state accuracy.

    Checks machine state consistency across tables.
    """
    query = """
        SELECT
            m.name,
            m.enabled,
            ms.current_state,
            ms.process_id,
            ms.updated_at
        FROM machines m
        LEFT JOIN machine_state ms ON m.id = ms.machine_id
        WHERE m.id = $1
    """

    result = await db.execute_query(query, machine_id)

    if not result:
        return {"valid": False, "reason": "Machine not found"}

    machine = result[0]

    validation = {
        "valid": True,
        "machine_name": machine['name'],
        "enabled": machine['enabled'],
        "current_state": machine['current_state'],
        "process_id": machine['process_id'],
        "updated_at": machine['updated_at']
    }

    if expected_state:
        validation["valid"] = machine['current_state'] == expected_state
        if not validation["valid"]:
            validation["reason"] = f"Expected state '{expected_state}', got '{machine['current_state']}'"

    return validation


async def validate_no_orphaned_records(db) -> Dict:
    """
    Check for dangling foreign keys across critical tables.

    Returns dictionary with orphan counts per table.
    """
    orphan_checks = [
        ("parameter_value_history", "parameter_id", "component_parameters", "id"),
        ("process_execution_state", "process_execution_id", "process_executions", "id"),
        ("recipe_steps", "recipe_id", "recipes", "id")
    ]

    orphans = {}

    for table, fk_col, ref_table, ref_col in orphan_checks:
        query = f"""
            SELECT COUNT(*) as count
            FROM {table} t
            LEFT JOIN {ref_table} r ON t.{fk_col} = r.{ref_col}
            WHERE r.{ref_col} IS NULL AND t.{fk_col} IS NOT NULL
        """

        result = await db.execute_query(query)
        orphan_count = result[0]['count'] if result else 0

        if orphan_count > 0:
            orphans[f"{table}.{fk_col}"] = orphan_count

    return {
        "valid": len(orphans) == 0,
        "orphan_counts": orphans,
        "total_orphans": sum(orphans.values())
    }


async def count_database_records(
    db,
    table: str,
    condition: Optional[str] = None
) -> int:
    """
    Efficient count query with optional WHERE clause.
    """
    where_clause = f"WHERE {condition}" if condition else ""
    query = f"SELECT COUNT(*) as count FROM {table} {where_clause}"

    result = await db.execute_query(query)
    return result[0]['count'] if result else 0


async def verify_database_consistency(db) -> Dict:
    """
    Cross-table integrity checks for common consistency issues.

    Returns dictionary with all validation results.
    """
    results = {
        "orphaned_records": await validate_no_orphaned_records(db),
        "timestamp": datetime.now().isoformat(),
        "checks_performed": [
            "orphaned_foreign_keys"
        ]
    }

    results["valid"] = all(
        v.get("valid", True) for v in results.values()
        if isinstance(v, dict) and "valid" in v
    )

    return results


async def verify_no_lost_updates(
    db,
    table: str,
    start_time: datetime,
    end_time: datetime,
    expected_count: int,
    tolerance_percent: float = 5.0
) -> Dict:
    """
    Verify no database updates were lost during concurrent operations.

    Validates that the actual count of records falls within tolerance
    of expected count, accounting for timing precision and race conditions.

    Args:
        db: Database connection
        table: Table name to validate
        start_time: Start of time window
        end_time: End of time window
        expected_count: Expected number of records
        tolerance_percent: Acceptable deviation percentage (default 5%)

    Returns:
        Dict with validation result and statistics

    Example:
        >>> result = await verify_no_lost_updates(
        ...     db, 'parameter_value_history',
        ...     start_time, end_time,
        ...     expected_count=100,
        ...     tolerance_percent=5.0
        ... )
        >>> assert result['valid'], f"Lost updates detected: {result}"
    """
    query = f"""
        SELECT COUNT(*) as count
        FROM {table}
        WHERE created_at BETWEEN $1 AND $2
    """

    result = await db.execute_query(query, start_time, end_time)
    actual_count = result[0]['count'] if result else 0

    tolerance = expected_count * (tolerance_percent / 100.0)
    min_acceptable = expected_count - tolerance
    max_acceptable = expected_count + tolerance

    is_valid = min_acceptable <= actual_count <= max_acceptable
    lost_count = max(0, expected_count - actual_count)
    lost_percent = (lost_count / expected_count * 100) if expected_count > 0 else 0

    return {
        "valid": is_valid,
        "actual_count": actual_count,
        "expected_count": expected_count,
        "lost_updates": lost_count,
        "lost_percent": lost_percent,
        "tolerance_percent": tolerance_percent,
        "acceptable_range": [int(min_acceptable), int(max_acceptable)],
        "time_window_seconds": (end_time - start_time).total_seconds()
    }
