#!/usr/bin/env python3
"""
Entry point launcher for the ALD control system.
This script ensures proper module resolution by running the main module.
"""
import sys
import os
import asyncio

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import and run main
if __name__ == "__main__":
    from src.main import main
    asyncio.run(main())