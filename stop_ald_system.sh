#!/bin/bash

# ALD Control System - Stop Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Stopping ALD Control System...${NC}"

# Stop main service if running
if [ -f "main_service.pid" ]; then
    PID=$(cat main_service.pid)
    if kill -0 $PID 2>/dev/null; then
        echo -e "${YELLOW}Stopping main service (PID: $PID)...${NC}"
        kill $PID
        rm main_service.pid
        echo -e "${GREEN}✅ Main service stopped${NC}"
    else
        echo -e "${YELLOW}Main service not running${NC}"
        rm -f main_service.pid
    fi
else
    echo -e "${YELLOW}No main service PID file found${NC}"
fi

# Stop any remaining ALD processes
echo -e "${YELLOW}Checking for remaining ALD processes...${NC}"
PIDS=$(pgrep -f "main.py" 2>/dev/null || true)
if [ ! -z "$PIDS" ]; then
    echo -e "${YELLOW}Stopping remaining processes: $PIDS${NC}"
    echo $PIDS | xargs kill 2>/dev/null || true
    sleep 2
    # Force kill if still running
    PIDS=$(pgrep -f "main.py" 2>/dev/null || true)
    if [ ! -z "$PIDS" ]; then
        echo -e "${RED}Force killing remaining processes...${NC}"
        echo $PIDS | xargs kill -9 2>/dev/null || true
    fi
fi

echo -e "${GREEN}✅ ALD Control System stopped${NC}"
