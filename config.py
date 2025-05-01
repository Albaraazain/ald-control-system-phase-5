"""
Configuration settings for the machine control application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
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

# Validate required configuration
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
    
if not MACHINE_ID:
    raise ValueError("MACHINE_ID must be set in .env file")


# PLC Configuration
PLC_TYPE = "simulation"  # 'simulation' or 'real'
PLC_CONFIG = {
    'ip_address': '192.168.1.100',  # Used only for real PLC
    'port': 502                    # Used only for real PLC
}