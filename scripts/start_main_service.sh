#!/bin/bash
# Start the main ALD control system service

echo "Starting ALD Control System Main Service..."
echo "This service includes command flow, recipe execution, and connection monitoring"
echo "Make sure the .env file is configured with your Supabase credentials"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with your Supabase credentials:"
    echo "SUPABASE_URL=your_supabase_url"
    echo "SUPABASE_KEY=your_supabase_key"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "myenv" ]; then
    echo "❌ Error: Virtual environment 'myenv' not found!"
    echo "Please create it with: python -m venv myenv && ./myenv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "Starting main service..."
./myenv/bin/python main.py
