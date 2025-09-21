"""
Delete non-essential parameters for a specific MACHINE_ID and cascade-delete
any dependent process datapoints. Creates CSV backups first, prints dry-run
counts, performs deletes (datapoints first), and verifies results.

Usage:
  python tools/db_cleanup/delete_nonessential_params.py

Environment:
  - Uses SUPABASE_URL / SUPABASE_KEY from .env via src.config
  - Does NOT require MACHINE_ID env; uses TARGET_MACHINE_ID constant below

Backups:
  - Writes CSVs to .agent-workspace/backups/<timestamp>/

Verification:
  - Re-queries component_parameters_full for the MACHINE_ID and criteria
  - Runs RealPLC metadata loader to ensure no logs for deleted names
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Ensure repository root is on path when invoked from project root
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import get_supabase  # noqa: E402
from src.log_setup import logger, set_log_level  # noqa: E402

# Constants
TARGET_MACHINE_ID = "e3e6e280-0794-459f-84d5-5e468f60746e"
BACKUP_ROOT = ROOT / ".agent-workspace" / "backups"

DELETE_PREFIXES = [
    "scale_min",
    "scale_max",
    "scale_min_voltage",
    "scale_max_voltage",
]
DELETE_EXACT = {"zero_cal", "span_cal", "purity", "ultrathink"}


def now_ts() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def chunked(seq: Sequence[str], size: int = 100) -> Iterable[List[str]]:
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


def _param_name(row: Dict[str, Any]) -> str:
    return (row.get("parameter_name") or row.get("name") or "").strip()


def _matches_delete_criteria(row: Dict[str, Any]) -> bool:
    name = _param_name(row).lower()
    comp = (row.get("component_name") or "").lower()
    if not name:
        return False

    if any(name.startswith(p) for p in DELETE_PREFIXES):
        return True
    if name in DELETE_EXACT:
        return True
    if name == "valve_state" and not comp.startswith("valve "):
        return True
    return False


def _select_columns() -> str:
    # Keep this minimal but informative for backups
    return (
        "id,machine_id,component_name,parameter_name,data_type,"
        "read_modbus_address,write_modbus_address,is_writable,show_in_ui,show_in_graph,"
        "min_value,max_value,current_value,set_value,created_at,updated_at"
    )


def fetch_all_params_for_machine(supabase, machine_id: str) -> List[Dict[str, Any]]:
    # Retrieve denormalized view rows for the machine
    res = (
        supabase.table("component_parameters_full")
        .select(_select_columns())
        .eq("machine_id", machine_id)
        .execute()
    )
    return list(res.data or [])


def resolve_datapoints_table(supabase) -> Optional[str]:
    candidates = ["process_data_points", "process_data", "process_datapoints"]
    for t in candidates:
        try:
            _ = supabase.table(t).select("id").limit(1).execute()
            return t
        except Exception:
            continue
    return None


def count_datapoints_for_params(supabase, table: str, param_ids: Sequence[str]) -> int:
    total = 0
    for ch in chunked(param_ids, 100):
        # Use count='exact' when available; fallback to len(data)
        try:
            res = (
                supabase.table(table)
                .select("id", count="exact")
                .in_("parameter_id", ch)
                .limit(1)
                .execute()
            )
            c = getattr(res, "count", None)
            if c is None:
                c = len(res.data or [])
            total += int(c)
        except Exception as e:
            logger.warning(f"Count fallback for {table} chunk due to: {e}")
            res = (
                supabase.table(table)
                .select("id")
                .in_("parameter_id", ch)
                .execute()
            )
            total += len(res.data or [])
    return total


def backup_rows_to_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    if not rows:
        # Write an empty file with header-only for consistency
        with out_path.open("w", newline="") as f:
            f.write("id\n")
        return
    # Determine header as union of keys
    header_keys = set()
    for r in rows:
        header_keys.update(r.keys())
    header = sorted(header_keys)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def fetch_datapoints_rows(
    supabase, table: str, param_ids: Sequence[str]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ch in chunked(list(param_ids), 100):
        res = (
            supabase.table(table)
            .select("*")
            .in_("parameter_id", ch)
            .execute()
        )
        out.extend(list(res.data or []))
    return out


def delete_datapoints(supabase, table: str, param_ids: Sequence[str]) -> int:
    before = count_datapoints_for_params(supabase, table, param_ids)
    deleted = 0
    for ch in chunked(list(param_ids), 100):
        _ = (
            supabase.table(table)
            .delete()
            .in_("parameter_id", ch)
            .execute()
        )
    # Verify
    after = count_datapoints_for_params(supabase, table, param_ids)
    deleted = max(0, before - after)
    return deleted


def delete_parameters(supabase, param_ids: Sequence[str]) -> int:
    before = len(param_ids)
    for ch in chunked(list(param_ids), 100):
        _ = (
            supabase.table("component_parameters")
            .delete()
            .in_("id", ch)
            .execute()
        )
    # Re-verify from the view
    remaining = (
        supabase.table("component_parameters_full")
        .select("id")
        .in_("id", list(param_ids))
        .execute()
    )
    remaining_ids = {r["id"] for r in (remaining.data or [])}
    deleted = before - len(remaining_ids)
    return max(0, deleted)


def verify_no_candidates_remain(
    supabase, machine_id: str
) -> Tuple[int, List[Dict[str, Any]]]:
    rows = fetch_all_params_for_machine(supabase, machine_id)
    remaining = [r for r in rows if _matches_delete_criteria(r)]
    return len(remaining), remaining


def run_metadata_load_and_capture(log_path: Path) -> Dict[str, Any]:
    """Run RealPLC metadata loader and capture logs into log_path.

    Returns a dict containing counts of offending log lines for deleted names.
    """
    import logging
    import importlib

    # Attach a temporary file handler to the shared logger
    fh = logging.FileHandler(str(log_path))
    fh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    try:
        # Disable essentials filter for this process to log all params
        import src.config as cfg
        cfg.ESSENTIALS_FILTER_MACHINE_IDS = {"disabled"}  # excludes our MACHINE_ID

        from src.plc.real_plc import RealPLC  # import after patching cfg

        plc = RealPLC(ip_address="127.0.0.1", port=502)

        # Run the private loader coroutine without connecting to PLC
        import asyncio

        async def _run():
            await plc._load_parameter_metadata()  # pylint: disable=protected-access

        asyncio.run(_run())
    finally:
        # Always flush and detach handler
        for h in list(logger.handlers):
            if h is fh:
                h.flush()
                logger.removeHandler(h)
                h.close()

    # Analyze logs
    offending = {
        "scale_prefix": 0,
        "exact_set": 0,
        "valve_state_non_valve_component": 0,
        "examples": [],
    }
    txt = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    lines = [ln.strip().lower() for ln in txt.splitlines()]

    def has_any(text: str, needles: Iterable[str]) -> bool:
        text = text.lower()
        return any(n in text for n in needles)

    # Only count lines belonging to the TARGET_MACHINE_ID by cross-checking the parameter ID.
    import re as _re
    from supabase import Client as _Client  # type: ignore
    sb = get_supabase()

    def belongs_to_target_machine(param_id: str) -> bool:
        try:
            res = (
                sb.table("component_parameters_full")
                .select("id,machine_id,parameter_name,component_name")
                .eq("id", param_id)
                .execute()
            )
            row = (res.data or [None])[0]
            return bool(row and row.get("machine_id") == TARGET_MACHINE_ID)
        except Exception:
            return False

    for ln in lines:
        if "parameter '" not in ln:
            continue
        m = _re.search(r"\(id:\s*([0-9a-f\-]{36})\)", ln)
        if not m:
            continue
        pid = m.group(1)
        if not belongs_to_target_machine(pid):
            continue

        if has_any(ln, DELETE_PREFIXES):
            offending["scale_prefix"] += 1
            if len(offending["examples"]) < 5:
                offending["examples"].append(ln)
        if has_any(ln, DELETE_EXACT):
            offending["exact_set"] += 1
            if len(offending["examples"]) < 5:
                offending["examples"].append(ln)
        if "'valve_state'" in ln and ("(valve " not in ln):
            offending["valve_state_non_valve_component"] += 1
            if len(offending["examples"]) < 5:
                offending["examples"].append(ln)

    return offending


def main() -> int:
    set_log_level("INFO")
    supabase = get_supabase()

    ts = now_ts()
    backup_dir = BACKUP_ROOT / ts
    ensure_dir(backup_dir)

    logger.info("Starting non-essential parameter cleanup")
    logger.info(f"Target MACHINE_ID: {TARGET_MACHINE_ID}")
    logger.info(f"Backup directory: {backup_dir}")

    # 1) Discover candidates from view
    all_rows = fetch_all_params_for_machine(supabase, TARGET_MACHINE_ID)
    candidates = [r for r in all_rows if _matches_delete_criteria(r)]
    candidate_ids = [r["id"] for r in candidates]

    # 2) Resolve datapoints table and count
    dp_table = resolve_datapoints_table(supabase)
    dp_count = 0
    if dp_table and candidate_ids:
        dp_count = count_datapoints_for_params(supabase, dp_table, candidate_ids)

    # 3) Backups
    params_csv = backup_dir / f"parameters_candidates_{TARGET_MACHINE_ID}.csv"
    backup_rows_to_csv(candidates, params_csv)
    dp_csv = None
    if dp_table and candidate_ids:
        dp_rows = fetch_datapoints_rows(supabase, dp_table, candidate_ids)
        dp_csv = backup_dir / f"datapoints_for_candidates_{TARGET_MACHINE_ID}.csv"
        backup_rows_to_csv(dp_rows, dp_csv)

    # 4) Dry-run counts
    print("=== DRY-RUN COUNTS ===")
    print(f"Candidate parameters: {len(candidate_ids)}")
    print(f"Referencing datapoints in '{dp_table or 'N/A'}': {dp_count}")
    print(f"Backups: params -> {params_csv}")
    if dp_csv:
        print(f"Backups: datapoints -> {dp_csv}")

    # 5) Execute deletes: datapoints first, then parameters
    deleted_dp = 0
    if dp_table and candidate_ids:
        deleted_dp = delete_datapoints(supabase, dp_table, candidate_ids)
    deleted_params = 0
    if candidate_ids:
        deleted_params = delete_parameters(supabase, candidate_ids)

    # 6) Verify via DB re-query
    remain_count, remain_rows = verify_no_candidates_remain(supabase, TARGET_MACHINE_ID)

    # 7) Verify via metadata loader logs (ensure deleted names no longer logged)
    metadata_log = backup_dir / f"metadata_load_{TARGET_MACHINE_ID}.log"
    offending = run_metadata_load_and_capture(metadata_log)

    # 8) Final summary
    print("\n=== DELETE SUMMARY ===")
    print(f"Deleted datapoints from '{dp_table or 'N/A'}': {deleted_dp}")
    print(f"Deleted parameters: {deleted_params}")
    print(f"Remaining matching parameters (should be 0): {remain_count}")
    print(f"Verification log: {metadata_log}")
    print("Offending log counts (should be 0): " + json.dumps(offending))

    # Caveats if any
    if remain_count > 0 or any(v for k, v in offending.items() if k != "examples"):
        print("\nCAVEATS:")
        if remain_count > 0:
            sample = [
                {
                    "id": r.get("id"),
                    "name": _param_name(r),
                    "component_name": r.get("component_name"),
                }
                for r in remain_rows[:5]
            ]
            print("- Some parameters still match criteria:")
            print(json.dumps(sample, indent=2))
        non_zero = {
            k: v for k, v in offending.items() if k != "examples" and v
        }
        if non_zero:
            print("- Metadata loader still logs deleted names:")
            print(json.dumps(non_zero, indent=2))
            if offending.get("examples"):
                print("Examples:")
                for ex in offending["examples"]:
                    print(f"  {ex}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
