#!/usr/bin/env python3
"""Monitor data_collection.log for wide inserts and adjacent timing violations."""

from __future__ import annotations

import argparse
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, Iterable, Optional

LOG_PATH_DEFAULT = (
    Path("/Users/albaraa/Developer/Projects/ald-control-system-phase-5-1/logs")
    / "data_collection.log"
)
TIMING_WINDOW = timedelta(seconds=2)
TIMESTAMP_SLICE = slice(0, 23)
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S,%f"


@dataclass
class TimedLine:
    """Store parsed log line details for correlation."""

    timestamp: datetime
    text: str
    printed: bool = False
    correlations: set[int] = field(default_factory=set)


def parse_timestamp(line: str) -> Optional[datetime]:
    """Extract timestamp prefix from a log line."""
    prefix = line[TIMESTAMP_SLICE]
    try:
        return datetime.strptime(prefix, TIMESTAMP_FORMAT)
    except ValueError:
        return None


def follow_file(
    path: Path, start_from_beginning: bool, exit_after_replay: bool
) -> Iterable[str]:
    """Yield new lines as they are written to the file."""
    with path.open(encoding="utf-8") as file_obj:
        if not start_from_beginning:
            file_obj.seek(0, os.SEEK_END)
        while True:
            line = file_obj.readline()
            if not line:
                if exit_after_replay:
                    break
                time.sleep(0.1)
                continue
            yield line.rstrip("\n")
            exit_after_replay = False


def cleanup_buffer(buffer: Deque[TimedLine], reference_time: datetime) -> None:
    """Drop entries older than the timing window."""
    while buffer and reference_time - buffer[0].timestamp > TIMING_WINDOW:
        buffer.popleft()


def monitor(
    log_path: Path,
    start_from_beginning: bool = False,
    exit_after_replay: bool = False,
) -> None:
    """Stream wide insert events and nearby timing violations."""
    recent_wide: Deque[TimedLine] = deque()
    recent_timing: Deque[TimedLine] = deque()
    event_counter = 0

    for raw_line in follow_file(
        log_path, start_from_beginning=start_from_beginning, exit_after_replay=exit_after_replay
    ):
        timestamp = parse_timestamp(raw_line)
        if timestamp is None:
            continue

        is_wide = "Wide insert:" in raw_line
        is_timing = "Timing violation" in raw_line

        if not any((is_wide, is_timing)):
            continue

        if is_wide:
            event_counter += 1
            wide_entry = TimedLine(timestamp=timestamp, text=raw_line)
            recent_wide.append(wide_entry)
            print(raw_line, flush=True)

            for timing_entry in list(recent_timing):
                if (
                    abs((timing_entry.timestamp - timestamp).total_seconds())
                    <= TIMING_WINDOW.total_seconds()
                    and event_counter not in timing_entry.correlations
                ):
                    print(timing_entry.text, flush=True)
                    timing_entry.printed = True
                    timing_entry.correlations.add(event_counter)

        if is_timing:
            timing_entry = TimedLine(timestamp=timestamp, text=raw_line)
            recent_timing.append(timing_entry)

            for idx, wide_entry in enumerate(list(recent_wide), start=1):
                if (
                    abs((timestamp - wide_entry.timestamp).total_seconds())
                    <= TIMING_WINDOW.total_seconds()
                ):
                    if idx not in timing_entry.correlations:
                        print(raw_line, flush=True)
                        timing_entry.printed = True
                        timing_entry.correlations.add(idx)

        reference = timestamp
        cleanup_buffer(recent_wide, reference)
        cleanup_buffer(recent_timing, reference)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor data_collection.log for 'Wide insert:' entries and "
            "associated 'Timing violation' lines within ±2 seconds."
        )
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=LOG_PATH_DEFAULT,
        help="Path to data_collection.log (default: %(default)s)",
    )
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Process the log from the beginning instead of tailing new entries.",
    )
    parser.add_argument(
        "--exit-after-replay",
        action="store_true",
        help="When used with --from-start, exit after replaying current file contents.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    monitor(
        args.log_path,
        start_from_beginning=args.from_start,
        exit_after_replay=args.exit_after_replay,
    )


if __name__ == "__main__":
    main()
