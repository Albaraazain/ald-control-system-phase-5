"""
Log analysis utilities for multi-terminal ALD control system testing.

Provides tools for parsing, analyzing, and correlating log files across
multiple terminals to detect errors, timing violations, and anomalies.

Usage:
    from tests.utils.log_analyzers import TerminalLogAnalyzer

    analyzer = TerminalLogAnalyzer("logs/plc.log", terminal_id=1)
    errors = analyzer.find_errors()
    timing_violations = analyzer.find_timing_violations()
    plc_errors = analyzer.find_plc_errors()
"""

import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path


class LogEntry:
    """Represents a single log entry with parsed components."""

    def __init__(self, line: str, line_number: int):
        self.line = line.strip()
        self.line_number = line_number
        self.timestamp = None
        self.level = None
        self.message = None
        self.logger_name = None

        self._parse()

    def _parse(self):
        """Parse log line into components."""
        # Expected format: "2025-10-10 19:00:00,123 - logger_name - LEVEL - message"
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\S+) - (\w+) - (.+)'
        match = re.match(pattern, self.line)

        if match:
            timestamp_str, self.logger_name, self.level, self.message = match.groups()
            try:
                self.timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            except ValueError:
                pass

    def __repr__(self):
        return f"LogEntry(line={self.line_number}, level={self.level}, timestamp={self.timestamp})"


class TerminalLogAnalyzer:
    """Analyze logs from a single terminal."""

    def __init__(self, log_file_path: str, terminal_id: Optional[int] = None):
        """
        Initialize log analyzer.

        Args:
            log_file_path: Path to log file
            terminal_id: Terminal ID for context (optional)
        """
        self.log_file_path = Path(log_file_path)
        self.terminal_id = terminal_id
        self.entries: List[LogEntry] = []
        self._load_log()

    def _load_log(self):
        """Load and parse log file."""
        if not self.log_file_path.exists():
            return

        with open(self.log_file_path, 'r') as f:
            for line_num, line in enumerate(f, start=1):
                if line.strip():
                    self.entries.append(LogEntry(line, line_num))

    def find_errors(
        self,
        min_level: str = "ERROR",
        time_window: Optional[timedelta] = None
    ) -> List[LogEntry]:
        """
        Find ERROR and CRITICAL level log entries.

        Args:
            min_level: Minimum log level ("ERROR" or "CRITICAL")
            time_window: Only include recent entries (optional)

        Returns:
            List of error log entries
        """
        error_levels = {"ERROR", "CRITICAL"}
        if min_level == "WARNING":
            error_levels.add("WARNING")

        cutoff_time = None
        if time_window:
            cutoff_time = datetime.now() - time_window

        errors = []
        for entry in self.entries:
            if entry.level in error_levels:
                if cutoff_time is None or (entry.timestamp and entry.timestamp >= cutoff_time):
                    errors.append(entry)

        return errors

    def find_timing_violations(self) -> List[LogEntry]:
        """
        Find timing violation messages.

        Returns:
            List of timing violation log entries
        """
        violations = []
        timing_patterns = [
            r'timing violation',
            r'timing precision',
            r'cycle time exceeded',
            r'jitter',
            r'timing drift'
        ]

        for entry in self.entries:
            for pattern in timing_patterns:
                if re.search(pattern, entry.line, re.IGNORECASE):
                    violations.append(entry)
                    break

        return violations

    def find_database_errors(self) -> List[LogEntry]:
        """
        Find database-related errors.

        Returns:
            List of database error log entries
        """
        db_errors = []
        db_patterns = [
            r'database',
            r'supabase',
            r'query failed',
            r'connection.*failed',
            r'transaction.*failed',
            r'insert.*failed',
            r'update.*failed'
        ]

        for entry in self.entries:
            if entry.level in {"ERROR", "CRITICAL"}:
                for pattern in db_patterns:
                    if re.search(pattern, entry.line, re.IGNORECASE):
                        db_errors.append(entry)
                        break

        return db_errors

    def find_plc_errors(self) -> List[LogEntry]:
        """
        Find PLC-related errors.

        Returns:
            List of PLC error log entries
        """
        plc_errors = []
        plc_patterns = [
            r'plc',
            r'modbus',
            r'read.*failed',
            r'write.*failed',
            r'connection.*failed',
            r'disconnected'
        ]

        for entry in self.entries:
            if entry.level in {"ERROR", "CRITICAL"}:
                for pattern in plc_patterns:
                    if re.search(pattern, entry.line, re.IGNORECASE):
                        plc_errors.append(entry)
                        break

        return plc_errors

    def count_log_pattern(self, pattern: str, ignore_case: bool = True) -> int:
        """
        Count occurrences of a regex pattern in logs.

        Args:
            pattern: Regex pattern to search
            ignore_case: Whether to ignore case

        Returns:
            Number of matches
        """
        flags = re.IGNORECASE if ignore_case else 0
        count = 0

        for entry in self.entries:
            if re.search(pattern, entry.line, flags):
                count += 1

        return count

    def get_error_summary(self) -> Dict[str, int]:
        """
        Get summary of error counts by type.

        Returns:
            Dictionary with error type counts
        """
        return {
            "total_errors": len(self.find_errors("ERROR")),
            "critical_errors": len([e for e in self.entries if e.level == "CRITICAL"]),
            "timing_violations": len(self.find_timing_violations()),
            "database_errors": len(self.find_database_errors()),
            "plc_errors": len(self.find_plc_errors())
        }

    def get_entries_between(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[LogEntry]:
        """
        Get log entries within time window.

        Args:
            start_time: Start of window
            end_time: End of window

        Returns:
            List of log entries in window
        """
        return [
            entry for entry in self.entries
            if entry.timestamp and start_time <= entry.timestamp <= end_time
        ]


class MultiTerminalLogAnalyzer:
    """Analyze and correlate logs across multiple terminals."""

    def __init__(self, log_files: Dict[int, str]):
        """
        Initialize multi-terminal analyzer.

        Args:
            log_files: Dictionary mapping terminal_id to log file path
                      Example: {1: "logs/plc.log", 2: "logs/recipe_flow.log"}
        """
        self.analyzers: Dict[int, TerminalLogAnalyzer] = {}

        for terminal_id, log_file in log_files.items():
            self.analyzers[terminal_id] = TerminalLogAnalyzer(log_file, terminal_id)

    def correlate_events(
        self,
        pattern: str,
        time_window_seconds: float = 5.0
    ) -> List[Tuple[int, LogEntry]]:
        """
        Find events matching pattern across all terminals within time window.

        Args:
            pattern: Regex pattern to search
            time_window_seconds: Time window for correlation

        Returns:
            List of (terminal_id, log_entry) tuples, sorted by timestamp
        """
        all_matches = []

        for terminal_id, analyzer in self.analyzers.items():
            for entry in analyzer.entries:
                if re.search(pattern, entry.line, re.IGNORECASE) and entry.timestamp:
                    all_matches.append((terminal_id, entry))

        # Sort by timestamp
        all_matches.sort(key=lambda x: x[1].timestamp or datetime.min)

        return all_matches

    def find_concurrent_errors(
        self,
        time_window_seconds: float = 10.0
    ) -> List[Dict]:
        """
        Find errors that occurred across multiple terminals concurrently.

        Args:
            time_window_seconds: Time window for concurrency

        Returns:
            List of error groups with timestamps and terminals
        """
        all_errors = []

        for terminal_id, analyzer in self.analyzers.items():
            errors = analyzer.find_errors()
            for error in errors:
                if error.timestamp:
                    all_errors.append({
                        "terminal_id": terminal_id,
                        "timestamp": error.timestamp,
                        "entry": error
                    })

        # Sort by timestamp
        all_errors.sort(key=lambda x: x["timestamp"])

        # Group errors within time window
        error_groups = []
        i = 0
        while i < len(all_errors):
            group = [all_errors[i]]
            current_time = all_errors[i]["timestamp"]

            j = i + 1
            while j < len(all_errors):
                if (all_errors[j]["timestamp"] - current_time).total_seconds() <= time_window_seconds:
                    group.append(all_errors[j])
                    j += 1
                else:
                    break

            if len(group) > 1:  # Only include groups with multiple terminals
                error_groups.append({
                    "start_time": group[0]["timestamp"],
                    "end_time": group[-1]["timestamp"],
                    "terminals": list(set([e["terminal_id"] for e in group])),
                    "errors": group
                })

            i = j if j > i + 1 else i + 1

        return error_groups

    def get_combined_summary(self) -> Dict:
        """
        Get combined error summary across all terminals.

        Returns:
            Dictionary with combined error counts
        """
        combined = {
            "by_terminal": {},
            "total": {
                "errors": 0,
                "critical": 0,
                "timing_violations": 0,
                "database_errors": 0,
                "plc_errors": 0
            }
        }

        for terminal_id, analyzer in self.analyzers.items():
            summary = analyzer.get_error_summary()
            combined["by_terminal"][terminal_id] = summary

            combined["total"]["errors"] += summary["total_errors"]
            combined["total"]["critical"] += summary["critical_errors"]
            combined["total"]["timing_violations"] += summary["timing_violations"]
            combined["total"]["database_errors"] += summary["database_errors"]
            combined["total"]["plc_errors"] += summary["plc_errors"]

        return combined
