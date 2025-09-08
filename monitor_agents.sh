#!/bin/bash

WORKSPACE=".agent-workspace/db_migration_20250908_152108"

while true; do
    clear
    echo "=== DATABASE MIGRATION AGENT ORCHESTRATION STATUS ==="
    echo "Time: $(date)"
    echo "Workspace: $WORKSPACE"
    echo ""
    
    echo "ACTIVE CLAUDE AGENTS:"
    ps aux | grep "claude -p" | grep -v grep | wc -l | xargs echo "  Total:"
    echo ""
    
    echo "HANDOFFS COMPLETED:"
    if [ -d "$WORKSPACE/handoffs" ]; then
        ls -la "$WORKSPACE/handoffs/" 2>/dev/null | grep -v "^total" | grep -v "^d" | wc -l | xargs echo "  Count:"
        ls "$WORKSPACE/handoffs/" 2>/dev/null | while read f; do
            [ -n "$f" ] && echo "  - $f"
        done
    else
        echo "  None yet"
    fi
    echo ""
    
    echo "ARTIFACTS CREATED:"
    if [ -d "$WORKSPACE/artifacts" ]; then
        find "$WORKSPACE/artifacts" -type f 2>/dev/null | wc -l | xargs echo "  Count:"
        find "$WORKSPACE/artifacts" -type f 2>/dev/null | while read f; do
            echo "  - $(basename $f)"
        done | head -10
    else
        echo "  None yet"
    fi
    echo ""
    
    echo "RECENT ACTIVITY:"
    if [ -d "$WORKSPACE/progress" ]; then
        find "$WORKSPACE/progress" -type f -name "*.log" 2>/dev/null | while read f; do
            tail -2 "$f" 2>/dev/null | sed "s/^/  /"
        done
    fi
    
    echo ""
    echo "Press Ctrl+C to stop monitoring"
    sleep 10
done