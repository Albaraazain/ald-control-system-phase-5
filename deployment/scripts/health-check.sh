#!/bin/bash
# Health check script for ALD Control System
# Used by monitoring systems and deployment automation

set -euo pipefail

# Configuration
SERVICE_URL="${SERVICE_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-5}"
MAX_RETRIES="${MAX_RETRIES:-6}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_success() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}[ERROR]${NC} $1"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Health check script for ALD Control System

OPTIONS:
    -u, --url URL                      Service URL [default: http://localhost:8000]
    -t, --timeout SECONDS             Request timeout [default: 30]
    -i, --interval SECONDS             Retry interval [default: 5]
    -r, --retries COUNT               Max retries [default: 6]
    -b, --basic                       Use basic health check endpoint
    -q, --quiet                       Quiet mode (no output except errors)
    -j, --json                        Output JSON format
    -h, --help                        Show this help message

EXAMPLES:
    $0                                # Basic health check
    $0 --url http://production:8000   # Check production service
    $0 --basic --json                 # Basic check with JSON output
    $0 --retries 10 --interval 3      # Extended retry configuration

EOF
}

# Parse command line arguments
BASIC_CHECK=false
QUIET_MODE=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            SERVICE_URL="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -i|--interval)
            RETRY_INTERVAL="$2"
            shift 2
            ;;
        -r|--retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        -b|--basic)
            BASIC_CHECK=true
            shift
            ;;
        -q|--quiet)
            QUIET_MODE=true
            shift
            ;;
        -j|--json)
            JSON_OUTPUT=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Determine health endpoint
if [[ "$BASIC_CHECK" == "true" ]]; then
    HEALTH_ENDPOINT="$SERVICE_URL/health/basic"
else
    HEALTH_ENDPOINT="$SERVICE_URL/health"
fi

# Quiet logging
quiet_log() {
    if [[ "$QUIET_MODE" == "false" ]]; then
        echo "$@"
    fi
}

# Perform health check
perform_health_check() {
    local retry_count=0
    local start_time=$(date +%s)

    while [[ $retry_count -lt $MAX_RETRIES ]]; do
        quiet_log "$(log_info "Attempting health check... (attempt $((retry_count + 1))/$MAX_RETRIES)")"

        # Perform the health check
        local response
        local http_code

        if response=$(curl -s -w "%{http_code}" --max-time "$TIMEOUT" "$HEALTH_ENDPOINT" 2>/dev/null); then
            http_code="${response: -3}"
            response_body="${response%???}"

            case "$http_code" in
                200)
                    local end_time=$(date +%s)
                    local duration=$((end_time - start_time))

                    if [[ "$JSON_OUTPUT" == "true" ]]; then
                        echo "$response_body"
                    else
                        quiet_log "$(log_success "Health check passed (HTTP $http_code, ${duration}s)")"
                        if [[ "$QUIET_MODE" == "false" ]]; then
                            echo "$response_body" | python3 -m json.tool 2>/dev/null || echo "$response_body"
                        fi
                    fi
                    return 0
                    ;;
                503)
                    quiet_log "$(log_warning "Service unavailable (HTTP $http_code)")"
                    if [[ "$QUIET_MODE" == "false" ]]; then
                        echo "$response_body" | python3 -m json.tool 2>/dev/null || echo "$response_body"
                    fi
                    ;;
                *)
                    quiet_log "$(log_warning "Unexpected HTTP response: $http_code")"
                    ;;
            esac
        else
            quiet_log "$(log_warning "Connection failed to $HEALTH_ENDPOINT")"
        fi

        retry_count=$((retry_count + 1))

        if [[ $retry_count -lt $MAX_RETRIES ]]; then
            quiet_log "$(log_info "Retrying in ${RETRY_INTERVAL}s...")"
            sleep "$RETRY_INTERVAL"
        fi
    done

    # All retries failed
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [[ "$JSON_OUTPUT" == "true" ]]; then
        echo '{"status": "error", "message": "Health check failed after all retries", "retries": '$MAX_RETRIES', "duration": '$duration'}'
    else
        log_error "Health check failed after $MAX_RETRIES attempts (${duration}s total)"
    fi

    return 1
}

# Validate configuration
validate_config() {
    if [[ ! "$TIMEOUT" =~ ^[0-9]+$ ]] || [[ "$TIMEOUT" -le 0 ]]; then
        log_error "Invalid timeout value: $TIMEOUT"
        exit 1
    fi

    if [[ ! "$RETRY_INTERVAL" =~ ^[0-9]+$ ]] || [[ "$RETRY_INTERVAL" -le 0 ]]; then
        log_error "Invalid retry interval: $RETRY_INTERVAL"
        exit 1
    fi

    if [[ ! "$MAX_RETRIES" =~ ^[0-9]+$ ]] || [[ "$MAX_RETRIES" -le 0 ]]; then
        log_error "Invalid max retries: $MAX_RETRIES"
        exit 1
    fi

    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
}

# Main function
main() {
    validate_config

    if [[ "$QUIET_MODE" == "false" && "$JSON_OUTPUT" == "false" ]]; then
        echo "ALD Control System Health Check"
        echo "=============================="
        echo "Service URL: $SERVICE_URL"
        echo "Endpoint: $HEALTH_ENDPOINT"
        echo "Timeout: ${TIMEOUT}s"
        echo "Max Retries: $MAX_RETRIES"
        echo "Retry Interval: ${RETRY_INTERVAL}s"
        echo ""
    fi

    perform_health_check
    exit $?
}

# Run main function
main