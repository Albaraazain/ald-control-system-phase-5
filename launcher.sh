#!/bin/bash
# ALD Control System Launcher
# Interactive launcher for all system components

clear
echo "🚀 ALD Control System Launcher"
echo "==============================="
echo ""

# Check if environment is set up
if [ ! -d "myenv" ]; then
    echo "⚠️  Virtual environment not found. Setting up environment first..."
    ./scripts/setup_environment.sh
    echo ""
    echo "Environment setup complete. Please restart the launcher."
    exit 0
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Please create it with your Supabase credentials:"
    echo "SUPABASE_URL=your_supabase_url"
    echo "SUPABASE_KEY=your_supabase_key"
    echo ""
    echo "Press Enter to continue anyway (some features may not work)..."
    read
fi

while true; do
    echo ""
    echo "Available Components:"
    echo "===================="
    echo "1. 🖥️  Main ALD Control Service (Backend)"
    echo "2. 🎛️  Parameter Control UI (Port 8501)"
    echo "3. 🔧 PLC Tester UI (Port 8502)"
    echo "4. 🐛 Simple PLC Debug UI (Port 8503)"
    echo "5. 📊 Start All UIs (Ports 8501, 8502, 8503)"
    echo "6. 🌐 Show Running Services"
    echo "7. 🛑 Stop All Services"
    echo "8. ⚙️  Setup Environment"
    echo "9. 📋 View Logs Directory"
    echo "0. ❌ Exit"
    echo ""
    
    read -p "Select option (0-9): " choice
    echo ""
    
    case $choice in
        1)
            echo "Starting Main ALD Control Service..."
            ./scripts/start_main_service.sh
            ;;
        2)
            echo "Starting Parameter Control UI on port 8501..."
            echo "Access at: http://localhost:8501"
            ./scripts/start_parameter_control_ui.sh &
            echo "Service started in background."
            ;;
        3)
            echo "Starting PLC Tester UI on port 8502..."
            echo "Access at: http://localhost:8502"
            ./scripts/start_plc_tester.sh &
            echo "Service started in background."
            ;;
        4)
            echo "Starting Simple PLC Debug UI on port 8503..."
            echo "Access at: http://localhost:8503"
            ./scripts/start_plc_debug.sh &
            echo "Service started in background."
            ;;
        5)
            echo "Starting all UIs..."
            echo "Parameter Control UI: http://localhost:8501"
            ./scripts/start_parameter_control_ui.sh &
            sleep 2
            echo "PLC Tester UI: http://localhost:8502"
            ./scripts/start_plc_tester.sh &
            sleep 2
            echo "Simple PLC Debug UI: http://localhost:8503"
            ./scripts/start_plc_debug.sh &
            echo "All UIs started in background."
            ;;
        6)
            echo "Checking running services..."
            echo ""
            echo "Python services:"
            ps aux | grep "python.*main.py\|python.*test_parameter" | grep -v grep
            echo ""
            echo "Streamlit services:"
            ps aux | grep streamlit | grep -v grep
            echo ""
            echo "Listening ports:"
            ss -tulpn | grep -E ":850[1-3]"
            ;;
        7)
            echo "Stopping all services..."
            pkill -f "python.*main.py"
            pkill -f "python.*test_parameter"
            pkill -f streamlit
            echo "All services stopped."
            ;;
        8)
            ./scripts/setup_environment.sh
            ;;
        9)
            echo "Log files location:"
            echo "- Main logs: Check console output"
            echo "- Streamlit logs: ~/.streamlit/logs/"
            echo "- System logs: Check your application logs"
            ;;
        0)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid option. Please select 0-9."
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
    clear
    echo "🚀 ALD Control System Launcher"
    echo "==============================="
done