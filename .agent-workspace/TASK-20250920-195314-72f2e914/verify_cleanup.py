import json
from pathlib import Path
from typing import Dict, List, Set

from src.db import get_supabase
from src.config import MACHINE_ID


def fetch_candidates() -> Dict[str, List[dict]]:
    supabase = get_supabase()

    # Group 1: Prefix matches
    prefixes = [
        "scale_min%",
        "scale_max%",
        "scale_min_voltage%",
        "scale_max_voltage%",
    ]
    prefix_rows: List[dict] = []
    for p in prefixes:
        res = (
            supabase
            .table("component_parameters_full")
            .select("id, parameter_name, component_name")
            .eq("machine_id", MACHINE_ID)
            .ilike("parameter_name", p)
            .execute()
        )
        prefix_rows.extend(res.data or [])

    # Group 2: Exact names
    exact_names = ["zero_cal", "span_cal", "purity", "ultrathink"]
    exact_rows: List[dict] = []
    if exact_names:
        res = (
            supabase
            .table("component_parameters_full")
            .select("id, parameter_name, component_name")
            .eq("machine_id", MACHINE_ID)
            .in_("parameter_name", exact_names)
            .execute()
        )
        exact_rows = res.data or []

    # Group 3: valve_state where component_name NOT starting with 'Valve '
    valve_rows: List[dict] = []
    res = (
        supabase
        .table("component_parameters_full")
        .select("id, parameter_name, component_name")
        .eq("machine_id", MACHINE_ID)
        .eq("parameter_name", "valve_state")
        .filter("component_name", "not.ilike", "Valve %")
        .execute()
    )
    valve_rows = res.data or []

    return {
        "prefix": prefix_rows,
        "exact": exact_rows,
        "valve_state_non_valve": valve_rows,
    }


def unique_ids(groups: Dict[str, List[dict]]) -> Set[str]:
    ids: Set[str] = set()
    for rows in groups.values():
        for r in rows:
            rid = r.get("id")
            if rid:
                ids.add(rid)
    return ids


def fetch_datapoints(parameter_ids: Set[str]) -> List[dict]:
    if not parameter_ids:
        return []
    supabase = get_supabase()
    # Supabase has a limit per request; fetch in chunks of 100
    ids_list = list(parameter_ids)
    batch_size = 100
    result: List[dict] = []
    for i in range(0, len(ids_list), batch_size):
        chunk = ids_list[i : i + batch_size]
        res = (
            supabase
            .table("process_data_points")
            .select("id, parameter_id, value, set_point, timestamp")
            .in_("parameter_id", chunk)
            .limit(1000)
            .execute()
        )
        result.extend(res.data or [])
    return result


def main() -> None:
    out_dir = Path(".agent-workspace/TASK-20250920-195314-72f2e914")
    out_dir.mkdir(parents=True, exist_ok=True)

    groups = fetch_candidates()
    ids = unique_ids(groups)
    datapoints = fetch_datapoints(ids)

    report = {
        "machine_id": MACHINE_ID,
        "counts": {
            "prefix": len(groups["prefix"]),
            "exact": len(groups["exact"]),
            "valve_state_non_valve": len(groups["valve_state_non_valve"]),
            "total_candidate_parameters": len(ids),
            "datapoints_referencing_candidates": len(datapoints),
        },
        "samples": {
            "parameters_prefix": groups["prefix"][:10],
            "parameters_exact": groups["exact"][:10],
            "parameters_valve_state_non_valve": groups["valve_state_non_valve"][:10],
            "datapoints": datapoints[:10],
        },
    }

    # Write full JSON report
    (out_dir / "cleanup_verification.json").write_text(
        json.dumps(report, indent=2, default=str)
    )

    # Print concise summary to stdout
    concise = {
        "machine_id": MACHINE_ID,
        "prefix": report["counts"]["prefix"],
        "exact": report["counts"]["exact"],
        "valve_state_non_valve": report["counts"]["valve_state_non_valve"],
        "total_candidates": report["counts"]["total_candidate_parameters"],
        "datapoints": report["counts"]["datapoints_referencing_candidates"],
    }
    print(json.dumps(concise))

    # If anything remains, also print up to 10 samples (compact)
    if concise["total_candidates"] > 0:
        samples = {
            "parameters_sample": (
                groups["prefix"][:5]
                + groups["exact"][:3]
                + groups["valve_state_non_valve"][:2]
            )[:10],
            "datapoints_sample": report["samples"]["datapoints"],
        }
        print("\nSAMPLES\n" + json.dumps(samples))


if __name__ == "__main__":
    main()

