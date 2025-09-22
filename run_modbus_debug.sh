#!/bin/bash
# Modbus Debug CLI Launcher
# This script activates the virtual environment and runs the Modbus debug tool

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source myenv/bin/activate

# Check if activation was successful
if [ $? -eq 0 ]; then
    echo "✅ Virtual environment activated"
    echo "🚀 Starting Modbus Debug CLI..."
    echo ""
    
    # Run the Modbus debug CLI
    python modbus_debug_cli.py
else
    echo "❌ Failed to activate virtual environment"
    echo "Please ensure the virtual environment is set up correctly:"
    echo "  python -m venv myenv"
    echo "  source myenv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi




