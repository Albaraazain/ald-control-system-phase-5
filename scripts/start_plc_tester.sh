#!/bin/bash
# Start PLC Tester UI on port 8502

echo "Starting PLC Tester UI on port 8502..."
./myenv/bin/streamlit run streamlit_plc_tester.py --server.port 8502 --server.headless true