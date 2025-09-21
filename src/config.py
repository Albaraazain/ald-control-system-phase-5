"""
Configuration settings for the machine control application.

Notes on validation:
- This module intentionally avoids raising on import to support tools like
  `python main.py --doctor` that should run even when Supabase env vars are
  missing. Runtime code should call the helper validators below when strict
  enforcement is required (e.g., service startup).
"""
import os
from dotenv import load_dotenv
from typing import Set

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Machine configuration
MACHINE_ID = os.getenv("MACHINE_ID")

# Command status constants
class CommandStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

# Machine state constants
class MachineState:
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    OFFLINE = "offline"

def missing_required_keys() -> list:
    """Return a list of missing critical configuration env keys."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY):
        missing.append("SUPABASE_KEY")
    if not MACHINE_ID:
        missing.append("MACHINE_ID")
    return missing


def is_supabase_config_present() -> bool:
    """Check if Supabase URL and KEY exist."""
    return bool(SUPABASE_URL and SUPABASE_KEY)


def is_core_config_ready() -> bool:
    """Check if all critical config (Supabase + Machine ID) is present."""
    return bool(is_supabase_config_present() and MACHINE_ID)


# PLC Configuration
PLC_TYPE = os.getenv("PLC_TYPE", "simulation")  # 'simulation' or 'real'

# Get PLC connection parameters from environment or use defaults
PLC_IP = os.getenv("PLC_IP", "192.168.1.100")
PLC_PORT = int(os.getenv("PLC_PORT", "502"))
PLC_HOSTNAME = os.getenv("PLC_HOSTNAME")  # Optional: e.g. 'plc.local'
PLC_AUTO_DISCOVER = os.getenv("PLC_AUTO_DISCOVER", "false").lower() in {"1", "true", "yes", "on"}

# PLC byte order: 'abcd' (big-endian), 'badc' (big-byte/little-word),
# 'cdab' (little-byte/big-word), 'dcba' (little-endian)
PLC_BYTE_ORDER = os.getenv("PLC_BYTE_ORDER", "badc")

PLC_CONFIG = {
    'ip_address': PLC_IP,
    'port': PLC_PORT,
    'byte_order': PLC_BYTE_ORDER,
    'hostname': PLC_HOSTNAME,
    'auto_discover': PLC_AUTO_DISCOVER,
}

# --- Feature Flags / Machine-Specific Toggles ---
# A lightweight, opt-in filter that limits which parameter names are loaded/logged
# from Supabase for specific machines. This is used to reduce noise for machines
# that currently have non-essential parameters populated in the DB.
#
# Enable for specific machines by listing their IDs in the env var
# `ESSENTIALS_FILTER_MACHINE_IDS` (comma-separated). If not provided, we default
# to enabling it only for the machine below. Other machines remain unaffected.
_DEFAULT_FILTER_IDS = {
    # TODO: Move this default to environment/config once DB cleanup is complete.
    "e3e6e280-0794-459f-84d5-5e468f60746e",
}

def _parse_csv_ids(value: str) -> Set[str]:
    items = [x.strip() for x in value.split(",") if x and x.strip()]
    return set(items)

ESSENTIALS_FILTER_MACHINE_IDS: Set[str] = (
    _parse_csv_ids(os.getenv("ESSENTIALS_FILTER_MACHINE_IDS", "")) or _DEFAULT_FILTER_IDS
)

def is_essentials_filter_enabled() -> bool:
    """Return True if the essentials filter is enabled for this MACHINE_ID."""
    return bool(MACHINE_ID and MACHINE_ID in ESSENTIALS_FILTER_MACHINE_IDS)
