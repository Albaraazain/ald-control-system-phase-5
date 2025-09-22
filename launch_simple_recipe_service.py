#!/usr/bin/env python3
"""
Simple launcher for Terminal 2: Recipe Service
"""

import subprocess
import sys

def main():
    """Launch the simple recipe service"""
    print("🚀 Launching Simple Recipe Service (Terminal 2)")
    print("   - Direct PLC access enabled")
    print("   - No complex coordination")
    print("   - Simplified recipe execution")
    print()

    try:
        subprocess.run([sys.executable, "simple_recipe_service.py"] + sys.argv[1:])
    except KeyboardInterrupt:
        print("\n👋 Recipe service stopped")

if __name__ == "__main__":
    main()