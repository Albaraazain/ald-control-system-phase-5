#!/bin/bash

# ALD Control System - Unified Startup Script
# This script starts the complete ALD system in an organized way

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 ALD Control System - Unified Startup${NC}"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Please run: python -m venv .venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}📦 Activating virtual environment...${NC}"
source .venv/bin/activate

# Check if requirements are installed
echo -e "${YELLOW}🔧 Checking dependencies...${NC}"
if ! python -c "import supabase" &> /dev/null; then
    echo -e "${YELLOW}📥 Installing requirements...${NC}"
    pip install -r requirements.txt
fi

# Show current configuration
echo -e "${BLUE}⚙️  Current Configuration:${NC}"
echo "  PLC Type: $(grep PLC_TYPE .env | cut -d'=' -f2)"
echo "  PLC IP: $(grep PLC_IP .env | cut -d'=' -f2)"
echo "  Machine ID: $(grep MACHINE_ID .env | cut -d'=' -f2)"
echo ""

# Menu for startup options
echo -e "${BLUE}🎯 Choose startup option:${NC}"
echo "  1) Main Service"
echo "  2) Test PLC Connection"
echo "  3) Run Diagnostics"
echo ""

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo -e "${GREEN}⚙️  Starting Main Service...${NC}"
        python main.py
        ;;
    2)
        echo -e "${GREEN}🔧 Testing PLC Connection...${NC}"
        python tools/plc_cli/plc_cli.py connect-test
        ;;
    3)
        echo -e "${GREEN}🩺 Running Diagnostics...${NC}"
        bash scripts/doctor.sh
        ;;
    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac
