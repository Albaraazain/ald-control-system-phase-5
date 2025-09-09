#!/bin/bash

# ALD Control System - Universal Environment Launcher
# This script sets up one comprehensive virtual environment for the entire project
# Supports: PLC communication, Streamlit UI, testing, debugging, and all development tools

echo "🚀 ALD Control System - Universal Environment"
echo "=============================================="

# Check if universal virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating universal virtual environment for entire project..."
    python -m venv venv
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        echo "Please make sure Python venv module is available"
        exit 1
    fi
    echo "✅ Universal virtual environment created"
fi

# Activate universal virtual environment
echo "⚡ Activating universal virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies for entire project
echo "📥 Installing all project dependencies..."
pip install --upgrade pip

# Install all project dependencies (existing + Streamlit + development tools)
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    echo "Please check requirements.txt and your internet connection"
    exit 1
fi

# Install additional development tools (optional)
echo "🛠️ Installing development tools..."
pip install pytest pytest-asyncio black flake8 mypy 2>/dev/null || echo "⚠️ Some dev tools may not be available"

echo "✅ Universal environment ready!"
echo ""
echo "🎯 Available Scripts:"
echo "   • Streamlit UI:     streamlit run streamlit_plc_tester.py"  
echo "   • Main PLC App:     python main.py"
echo "   • Run Tests:        pytest tests/"
echo "   • Debug Scripts:    python debug/test_*.py"
echo ""

# Ask user what they want to run
echo "What would you like to run?"
echo "1) Streamlit PLC Testing UI (default)"
echo "2) Main PLC Application" 
echo "3) Exit (keep environment active)"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    2)
        echo "🚀 Starting Main PLC Application..."
        python main.py
        ;;
    3)
        echo "✅ Universal environment is active. You can now run any project script."
        echo "💡 To run Streamlit UI: streamlit run streamlit_plc_tester.py"
        echo "💡 To run main app: python main.py"
        echo "💡 To deactivate: deactivate"
        exec bash --rcfile <(echo "PS1='(ALD-venv) \$PS1'")
        ;;
    *)
        # Default: Run Streamlit UI
        echo "🌟 Starting Streamlit PLC Testing UI..."
        echo ""
        echo "🔗 Application will be available at:"
        echo "   Local:    http://localhost:8501"
        echo "   Network:  http://0.0.0.0:8501"
        echo ""
        echo "Press Ctrl+C to stop the application"
        echo "================================"
        streamlit run streamlit_plc_tester.py --server.port 8501 --server.address 0.0.0.0
        ;;
esac

# Deactivate virtual environment on exit
deactivate