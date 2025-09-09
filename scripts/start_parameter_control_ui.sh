#!/bin/bash
# Start Parameter Control UI on port 8501

echo "Starting Parameter Control UI on port 8501..."
./myenv/bin/streamlit run parameter_control_ui.py --server.port 8501 --server.headless true