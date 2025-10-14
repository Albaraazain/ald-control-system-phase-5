#!/usr/bin/env python3
"""
One-shot scanner for machine_control.log to report missing parameter errors.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict


DEFAULT_LOG_PATH = "/Users/albaraa/Developer/Projects/ald-control-system-phase-5-1/machine_control.log"
DEFAULT_STATE_PATH = "logwatch_state.json"

# Match "Parameter <uuid> (<name>) missing"
PARAMETER_MISSING_PATTERN = re.compile(
    r"Parameter ([0-9a-fA-F-]{36}) \(([^)]+)\) missing"
)

# Capture timestamp at the start of the line (with optional milliseconds)
TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d{3})?)"
)


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"position": 0}
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        # Reset state if file is unreadable
        return {"position": 0}


def save_state(path: str, state: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(state, file)


def main() -> int:
    log_path = os.environ.get("LOG_PATH", None)
    state_path = os.environ.get("STATE_PATH", None)

    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    if len(sys.argv) > 2:
        state_path = sys.argv[2]

    if not log_path:
        log_path = DEFAULT_LOG_PATH
    if not state_path:
        state_path = DEFAULT_STATE_PATH

    state = load_state(state_path)
    position = int(state.get("position", 0))

    try:
        with open(log_path, "r", encoding="utf-8") as log_file:
            log_file.seek(0, os.SEEK_END)
            file_size = log_file.tell()

            # Handle log rotation or truncation
            if position > file_size:
                position = 0

            log_file.seek(position)

            for line in log_file:
                parameter_match = PARAMETER_MISSING_PATTERN.search(line)
                if not parameter_match:
                    continue

                uuid = parameter_match.group(1)
                name = parameter_match.group(2)

                timestamp_match = TIMESTAMP_PATTERN.match(line)
                timestamp = timestamp_match.group(1) if timestamp_match else "UNKNOWN_TIMESTAMP"

                print(f"{timestamp} Parameter {uuid} ({name}) missing")

            state["position"] = log_file.tell()
    except FileNotFoundError:
        print(f"Log file not found: {log_path}", file=sys.stderr)
        return 1

    save_state(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
