#!/bin/bash
# Start Simple PLC Debug UI on port 8503

echo "Starting Simple PLC Debug UI on port 8503..."
./myenv/bin/streamlit run simple_plc_debug.py --server.port 8503 --server.headless true