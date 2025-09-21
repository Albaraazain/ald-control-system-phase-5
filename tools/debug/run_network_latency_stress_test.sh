#!/bin/bash

# Network Latency Stress Test Runner
# Provides comprehensive network latency and timeout stress testing for the continuous parameter logging system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default configuration
DURATION=${1:-180}  # Test duration in seconds (default: 3 minutes)
LOG_LEVEL=${2:-INFO}
OUTPUT_DIR="$PROJECT_ROOT/test_results/network_latency_stress"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo -e "${CYAN}🚀 Network Latency Stress Test Runner${NC}"
echo -e "${CYAN}=====================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${PURPLE}🔧 $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if running as root for network simulation
    if [ "$EUID" -eq 0 ]; then
        print_success "Running with root privileges - full network simulation available"
        NETWORK_SIM_AVAILABLE=true
    else
        print_warning "Not running as root - network simulation limited"
        print_info "For full tc/netem support, run with: sudo $0 $@"
        NETWORK_SIM_AVAILABLE=false
    fi

    # Check for tc (traffic control)
    if command -v tc &> /dev/null; then
        print_success "tc (traffic control) available"
    else
        print_warning "tc (traffic control) not available - install iproute2 package"
    fi

    # Check for Python dependencies
    if python3 -c "import asyncio, subprocess, socket" &> /dev/null; then
        print_success "Python dependencies available"
    else
        print_error "Python dependencies missing"
        exit 1
    fi

    # Check project structure
    if [ -f "$PROJECT_ROOT/src/main.py" ]; then
        print_success "Project structure validated"
    else
        print_error "Invalid project structure - run from project root"
        exit 1
    fi

    echo ""
}

# Setup test environment
setup_environment() {
    print_header "Setting Up Test Environment"

    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    print_success "Created output directory: $OUTPUT_DIR"

    # Setup virtual environment if needed
    if [ ! -d "$PROJECT_ROOT/myenv" ]; then
        print_info "Creating virtual environment..."
        cd "$PROJECT_ROOT"
        python3 -m venv myenv
        source myenv/bin/activate
        pip install -r requirements.txt
        print_success "Virtual environment created"
    else
        print_success "Virtual environment exists"
    fi

    # Load environment variables
    if [ -f "$PROJECT_ROOT/.env" ]; then
        source "$PROJECT_ROOT/.env"
        print_success "Environment variables loaded"
    else
        print_warning ".env file not found - using defaults"
    fi

    echo ""
}

# System information collection
collect_system_info() {
    print_header "Collecting System Information"

    INFO_FILE="$OUTPUT_DIR/system_info_$TIMESTAMP.txt"

    {
        echo "=== System Information ==="
        echo "Date: $(date)"
        echo "Hostname: $(hostname)"
        echo "OS: $(uname -a)"
        echo "Python: $(python3 --version)"
        echo "User: $(whoami)"
        echo "UID: $(id -u)"
        echo ""

        echo "=== Network Interfaces ==="
        ip addr show || ifconfig
        echo ""

        echo "=== Network Routes ==="
        ip route show || route -n
        echo ""

        echo "=== Active Network Connections ==="
        ss -tuln || netstat -tuln
        echo ""

        echo "=== TC Queueing Disciplines ==="
        tc qdisc show 2>/dev/null || echo "TC not available or no rules"
        echo ""

        echo "=== Memory Usage ==="
        free -h
        echo ""

        echo "=== CPU Information ==="
        lscpu 2>/dev/null || cat /proc/cpuinfo | grep "model name" | head -1
        echo ""

        echo "=== Disk Usage ==="
        df -h
        echo ""

    } > "$INFO_FILE"

    print_success "System information saved to: $INFO_FILE"
    echo ""
}

# Pre-test validation
pre_test_validation() {
    print_header "Pre-Test Validation"

    cd "$PROJECT_ROOT"
    source myenv/bin/activate

    # Test basic connectivity
    print_info "Testing basic connectivity..."

    # Test database connectivity
    if python3 -c "
import sys
sys.path.append('.')
from src.db import get_supabase
try:
    supabase = get_supabase()
    result = supabase.table('machines').select('id').limit(1).execute()
    print('Database connectivity: OK')
except Exception as e:
    print(f'Database connectivity: FAILED - {e}')
    sys.exit(1)
" > "$OUTPUT_DIR/connectivity_test_$TIMESTAMP.log" 2>&1; then
        print_success "Database connectivity validated"
    else
        print_error "Database connectivity failed"
        cat "$OUTPUT_DIR/connectivity_test_$TIMESTAMP.log"
        exit 1
    fi

    # Test PLC connectivity (if configured)
    if python3 -c "
import sys
sys.path.append('.')
import asyncio
from src.plc.manager import plc_manager

async def test_plc():
    try:
        success = await plc_manager.initialize()
        if success:
            print('PLC connectivity: OK')
            await plc_manager.disconnect()
        else:
            print('PLC connectivity: FAILED - Could not initialize')
    except Exception as e:
        print(f'PLC connectivity: WARNING - {e}')

asyncio.run(test_plc())
" >> "$OUTPUT_DIR/connectivity_test_$TIMESTAMP.log" 2>&1; then
        print_success "PLC connectivity validated"
    else
        print_warning "PLC connectivity issues (check logs)"
    fi

    echo ""
}

# Run the actual stress test
run_stress_test() {
    print_header "Running Network Latency Stress Test"

    cd "$PROJECT_ROOT"
    source myenv/bin/activate

    # Set test parameters
    export PYTHONPATH="$PROJECT_ROOT"
    export LOG_LEVEL="$LOG_LEVEL"

    TEST_LOG="$OUTPUT_DIR/network_latency_stress_test_$TIMESTAMP.log"

    print_info "Test duration: ${DURATION} seconds"
    print_info "Log level: $LOG_LEVEL"
    print_info "Network simulation: $NETWORK_SIM_AVAILABLE"
    print_info "Output directory: $OUTPUT_DIR"
    print_info ""

    print_info "Starting test... (this may take a while)"

    # Run the stress test with timeout
    if timeout $((DURATION + 120)) python3 tools/debug/test_network_latency_stress.py 2>&1 | tee "$TEST_LOG"; then
        print_success "Network latency stress test completed successfully"
        TEST_RESULT="PASSED"
    else
        TEST_EXIT_CODE=$?
        if [ $TEST_EXIT_CODE -eq 124 ]; then
            print_error "Test timed out after $((DURATION + 120)) seconds"
        else
            print_error "Network latency stress test failed (exit code: $TEST_EXIT_CODE)"
        fi
        TEST_RESULT="FAILED"
    fi

    echo ""
}

# Analyze results
analyze_results() {
    print_header "Analyzing Test Results"

    ANALYSIS_FILE="$OUTPUT_DIR/analysis_$TIMESTAMP.txt"

    {
        echo "=== Network Latency Stress Test Analysis ==="
        echo "Date: $(date)"
        echo "Test Result: $TEST_RESULT"
        echo "Duration: $DURATION seconds"
        echo ""

        echo "=== Key Metrics ==="
        if [ -f "$TEST_LOG" ]; then
            grep -E "(OVERALL STATISTICS|LATENCY STATISTICS|CONTINUOUS LOGGING|CRITICAL FINDINGS)" "$TEST_LOG" | head -20
        fi
        echo ""

        echo "=== Critical Issues Found ==="
        if [ -f "$TEST_LOG" ]; then
            grep -E "(CRITICAL|ERROR|❌)" "$TEST_LOG" | head -10
        fi
        echo ""

        echo "=== Warnings ==="
        if [ -f "$TEST_LOG" ]; then
            grep -E "(WARNING|⚠️)" "$TEST_LOG" | head -10
        fi
        echo ""

        echo "=== Recommendations ==="
        if [ -f "$TEST_LOG" ]; then
            grep -A 20 "RECOMMENDATIONS" "$TEST_LOG" | head -20
        fi

    } > "$ANALYSIS_FILE"

    print_success "Analysis saved to: $ANALYSIS_FILE"

    # Display summary
    if [ "$TEST_RESULT" = "PASSED" ]; then
        print_success "✨ Test Summary: PASSED"
    else
        print_error "💥 Test Summary: FAILED"
    fi

    echo ""
}

# Generate test report
generate_report() {
    print_header "Generating Test Report"

    REPORT_FILE="$OUTPUT_DIR/network_latency_stress_test_report_$TIMESTAMP.html"

    cat > "$REPORT_FILE" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Network Latency Stress Test Report - $TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 15px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border-left: 3px solid #007acc; }
        .success { color: green; }
        .warning { color: orange; }
        .error { color: red; }
        pre { background-color: #f5f5f5; padding: 10px; overflow-x: auto; }
        .metric { display: inline-block; margin: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Network Latency Stress Test Report</h1>
        <p><strong>Timestamp:</strong> $TIMESTAMP</p>
        <p><strong>Duration:</strong> $DURATION seconds</p>
        <p><strong>Result:</strong> <span class="$([ "$TEST_RESULT" = "PASSED" ] && echo "success" || echo "error")">$TEST_RESULT</span></p>
    </div>

    <div class="section">
        <h2>📊 Test Overview</h2>
        <p>This test validates the continuous parameter logging system's behavior under various network latency conditions.</p>
        <p><strong>Target:</strong> Maintain 1-second logging intervals under network stress</p>
        <p><strong>Network Simulation:</strong> $NETWORK_SIM_AVAILABLE</p>
    </div>

    <div class="section">
        <h2>🔧 System Information</h2>
        <pre>$(cat "$OUTPUT_DIR/system_info_$TIMESTAMP.txt" 2>/dev/null || echo "System info not available")</pre>
    </div>

    <div class="section">
        <h2>📈 Test Results</h2>
        <pre>$(cat "$OUTPUT_DIR/analysis_$TIMESTAMP.txt" 2>/dev/null || echo "Analysis not available")</pre>
    </div>

    <div class="section">
        <h2>📋 Full Test Log</h2>
        <pre>$(tail -100 "$TEST_LOG" 2>/dev/null || echo "Test log not available")</pre>
    </div>

    <div class="section">
        <h2>📁 Generated Files</h2>
        <ul>
EOF

    # List all generated files
    for file in "$OUTPUT_DIR"/*"$TIMESTAMP"*; do
        if [ -f "$file" ]; then
            echo "            <li>$(basename "$file")</li>" >> "$REPORT_FILE"
        fi
    done

    cat >> "$REPORT_FILE" << EOF
        </ul>
    </div>
</body>
</html>
EOF

    print_success "HTML report generated: $REPORT_FILE"
    echo ""
}

# Cleanup function
cleanup() {
    print_header "Cleanup"

    # Clear any tc rules that might have been left behind
    if [ "$EUID" -eq 0 ] && command -v tc &> /dev/null; then
        print_info "Clearing tc rules..."
        for interface in lo eth0 wlan0 enp0s3; do
            tc qdisc del dev "$interface" root 2>/dev/null || true
        done
        print_success "TC rules cleared"
    fi

    print_success "Cleanup completed"
    echo ""
}

# Main execution
main() {
    echo -e "${CYAN}Starting Network Latency Stress Test...${NC}"
    echo ""

    # Run all steps
    check_prerequisites
    setup_environment
    collect_system_info
    pre_test_validation
    run_stress_test
    analyze_results
    generate_report
    cleanup

    # Final summary
    echo -e "${CYAN}🎯 Test Execution Summary${NC}"
    echo -e "${CYAN}=========================${NC}"
    echo ""

    if [ "$TEST_RESULT" = "PASSED" ]; then
        print_success "✨ Network latency stress test completed successfully!"
        print_info "The continuous parameter logging system demonstrates acceptable performance under network stress."
    else
        print_error "💥 Network latency stress test failed!"
        print_info "The continuous parameter logging system has issues under network stress conditions."
    fi

    print_info "📁 All results saved in: $OUTPUT_DIR"
    print_info "📊 View the HTML report: $OUTPUT_DIR/network_latency_stress_test_report_$TIMESTAMP.html"
    echo ""

    # Return appropriate exit code
    [ "$TEST_RESULT" = "PASSED" ] && exit 0 || exit 1
}

# Handle interruption gracefully
trap cleanup EXIT INT TERM

# Run main function
main "$@"