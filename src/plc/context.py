"""
PLC Context Module

Provides a simple way for terminals to set their PLC instance
that step executors can access. This replaces the singleton pattern
with a cleaner per-terminal approach.

Each terminal creates its own PLC instance and sets it here.
Step executors access it via get_plc().
"""
from typing import Optional
from src.plc.interface import PLCInterface

# Module-level PLC instance (set by each terminal)
_current_plc: Optional[PLCInterface] = None


def set_plc(plc: PLCInterface):
    """Set the current PLC instance for this terminal."""
    global _current_plc
    _current_plc = plc


def get_plc() -> Optional[PLCInterface]:
    """Get the current PLC instance."""
    return _current_plc


def clear_plc():
    """Clear the current PLC instance."""
    global _current_plc
    _current_plc = None

