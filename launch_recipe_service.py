#!/usr/bin/env python3
"""
Launch script for Terminal 2: Recipe Service
Provides convenient startup with environment configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Launch the Recipe Service with proper environment setup"""

    # Get project root directory
    project_root = Path(__file__).parent.absolute()

    # Ensure we're in the right directory
    os.chdir(project_root)

    # Set environment variables if not already set
    env = os.environ.copy()

    # Default configuration for Recipe Service (Terminal 2)
    env.setdefault("LOG_LEVEL", "INFO")
    env.setdefault("TERMINAL_ID", "terminal_2_recipe")
    env.setdefault("TERMINAL_TYPE", "recipe_service")

    # Recipe service specific settings
    env.setdefault("RECIPE_COMMAND_POLL_INTERVAL", "5")  # seconds
    env.setdefault("HARDWARE_OPERATION_TIMEOUT", "60")  # seconds
    env.setdefault("EMERGENCY_OPERATION_TIMEOUT", "10")  # seconds

    print("=" * 60)
    print("🍳 ALD Control System - Terminal 2: Recipe Service")
    print("=" * 60)
    print(f"Project Root: {project_root}")
    print(f"Log Level: {env.get('LOG_LEVEL')}")
    print(f"Terminal ID: {env.get('TERMINAL_ID')}")
    print(f"Machine ID: {env.get('MACHINE_ID', 'default')}")
    print("=" * 60)
    print()

    # Check for Python virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment detected")
    else:
        print("⚠️  No virtual environment detected - consider using 'python -m venv myenv && source myenv/bin/activate'")

    print()
    print("Starting Recipe Service...")
    print("Press Ctrl+C to stop")
    print()

    try:
        # Launch the recipe service
        cmd = [sys.executable, "recipe_service.py"] + sys.argv[1:]
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)

    except KeyboardInterrupt:
        print("\n🛑 Recipe Service stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error launching Recipe Service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()