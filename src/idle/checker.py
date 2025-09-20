"""
Idle readiness checker for per-machine conditions.

Evaluates machine-specific idle conditions stored in the database before
starting a recipe. Conditions are flexible and user-editable from the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.config import MACHINE_ID
from src.db import get_supabase
from src.log_setup import logger


@dataclass
class IdleConditionItem:
    id: str
    parameter_id: Optional[str]
    component_id: Optional[str]
    check_type: str  # 'range' | 'equals' | 'binary_on' | 'binary_off'
    min_value: Optional[float]
    max_value: Optional[float]
    equals_value: Optional[float]
    required_on: Optional[bool]
    recommended_min: Optional[float]
    recommended_max: Optional[float]
    priority: int
    note: Optional[str]


@dataclass
class FailedCheck:
    item_id: str
    parameter_id: Optional[str]
    component_id: Optional[str]
    check_type: str
    expected: str
    observed: Optional[float]
    recommendation: Optional[str]


def _fmt_recommendation(item: IdleConditionItem) -> Optional[str]:
    if item.recommended_min is not None or item.recommended_max is not None:
        mn = "-inf" if item.recommended_min is None else f"{item.recommended_min}"
        mx = "+inf" if item.recommended_max is None else f"{item.recommended_max}"
        return f"Recommended range: [{mn}, {mx}]"
    return None


def evaluate_idle_conditions() -> Tuple[bool, List[FailedCheck]]:
    """
    Evaluate active idle conditions for the current machine.

    Returns:
        (ok, failed_list) where ok is True if all conditions pass or no
        active condition profile exists; failed_list describes failing checks.
    """
    supabase = get_supabase()

    # Find active condition profile for this machine
    cond = (
        supabase.table("machine_idle_conditions")
        .select("id")
        .eq("machine_id", MACHINE_ID)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not cond.data:
        logger.info("No active idle conditions defined; allowing start by default")
        return True, []

    cond_id = cond.data[0]["id"]

    # Load condition items
    res = (
        supabase.table("machine_idle_condition_items")
        .select("*")
        .eq("idle_condition_id", cond_id)
        .order("priority")
        .execute()
    )
    items_raw = res.data or []
    if not items_raw:
        logger.info("Active idle profile has no items; allowing start")
        return True, []

    # Collect parameter_ids to fetch current values
    param_ids = [r["parameter_id"] for r in items_raw if r.get("parameter_id")]
    current_values = {}
    if param_ids:
        pr = (
            supabase.table("component_parameters")
            .select("id,current_value")
            .in_("id", param_ids)
            .execute()
        )
        for row in pr.data or []:
            current_values[row["id"]] = row["current_value"]

    failed: List[FailedCheck] = []
    for r in items_raw:
        item = IdleConditionItem(
            id=r["id"],
            parameter_id=r.get("parameter_id"),
            component_id=r.get("component_id"),
            check_type=r.get("check_type", "range"),
            min_value=r.get("min_value"),
            max_value=r.get("max_value"),
            equals_value=r.get("equals_value"),
            required_on=r.get("required_on"),
            recommended_min=r.get("recommended_min"),
            recommended_max=r.get("recommended_max"),
            priority=r.get("priority", 10),
            note=r.get("note"),
        )

        observed = None
        if item.parameter_id:
            observed = current_values.get(item.parameter_id)

        # Evaluate
        expected_desc = ""
        ok = True
        ct = item.check_type.lower()

        if ct == "range":
            expected_desc = f"{item.min_value} <= value <= {item.max_value}"
            if observed is None:
                ok = False
            else:
                if item.min_value is not None and observed < float(item.min_value):
                    ok = False
                if item.max_value is not None and observed > float(item.max_value):
                    ok = False

        elif ct == "equals":
            expected_desc = f"value == {item.equals_value}"
            ok = observed is not None and float(observed) == float(item.equals_value)

        elif ct == "binary_on":
            expected_desc = "value ON (>0.5)"
            ok = observed is not None and float(observed) > 0.5

        elif ct == "binary_off":
            expected_desc = "value OFF (<=0.5)"
            ok = observed is not None and float(observed) <= 0.5

        else:
            # Unknown type – mark as failed to be safe
            expected_desc = f"unsupported check_type: {ct}"
            ok = False

        if not ok:
            failed.append(
                FailedCheck(
                    item_id=item.id,
                    parameter_id=item.parameter_id,
                    component_id=item.component_id,
                    check_type=ct,
                    expected=expected_desc,
                    observed=observed,
                    recommendation=_fmt_recommendation(item),
                )
            )

    return len(failed) == 0, failed


def ensure_idle_ready() -> None:
    """Raise ValueError with details if idle conditions are not satisfied."""
    ok, failed = evaluate_idle_conditions()
    if ok:
        return
    details = []
    for f in failed[:10]:  # limit verbosity
        rec = f"; {f.recommendation}" if f.recommendation else ""
        pid = f.parameter_id or "?"
        details.append(
            f"param={pid} type={f.check_type} expected={f.expected} observed={f.observed}{rec}"
        )
    msg = "Idle conditions not met: " + "; ".join(details)
    logger.warning(msg)
    raise ValueError(msg)

