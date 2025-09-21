#!/bin/bash
# Rollback script for ALD Control System
# Provides emergency rollback capabilities for production deployments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_ROOT/deployment"

# Default values
ENVIRONMENT="production"
ROLLBACK_METHOD="auto"
PREVIOUS_VERSION=""
CONFIRM=false
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Emergency rollback script for ALD Control System

OPTIONS:
    -e, --environment ENVIRONMENT       Target environment (staging|production) [default: production]
    -m, --method METHOD                Rollback method (auto|manual|version) [default: auto]
    -v, --version VERSION              Specific version to rollback to (required with --method version)
    -y, --yes                          Skip confirmation prompt
    -d, --dry-run                      Show what would be done without executing
    -h, --help                         Show this help message

ROLLBACK METHODS:
    auto        Automatically rollback to the last known good version
    manual      Manual rollback with interactive prompts
    version     Rollback to a specific version (requires --version)

EXAMPLES:
    $0 --environment production --yes                    # Emergency auto rollback
    $0 --method version --version v1.2.3 --dry-run      # Test rollback to specific version
    $0 --method manual                                   # Interactive rollback

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -m|--method)
                ROLLBACK_METHOD="$2"
                shift 2
                ;;
            -v|--version)
                PREVIOUS_VERSION="$2"
                shift 2
                ;;
            -y|--yes)
                CONFIRM=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
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
}

# Validate arguments
validate_args() {
    if [[ ! "$ENVIRONMENT" =~ ^(staging|production)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT"
        exit 1
    fi

    if [[ ! "$ROLLBACK_METHOD" =~ ^(auto|manual|version)$ ]]; then
        log_error "Invalid rollback method: $ROLLBACK_METHOD"
        exit 1
    fi

    if [[ "$ROLLBACK_METHOD" == "version" && -z "$PREVIOUS_VERSION" ]]; then
        log_error "Version rollback requires --version parameter"
        exit 1
    fi
}

# Get current deployment status
get_current_status() {
    log_info "Getting current deployment status..."

    local compose_file="$DEPLOYMENT_DIR/docker-compose.prod.yml"

    if [[ -f "$compose_file" ]]; then
        # Get currently running containers
        CURRENT_CONTAINERS=$(docker-compose -f "$compose_file" ps --services --filter "status=running" 2>/dev/null || echo "")

        # Get current image tags
        if docker-compose -f "$compose_file" ps ald-control | grep -q "Up"; then
            CURRENT_IMAGE=$(docker-compose -f "$compose_file" images ald-control | tail -n 1 | awk '{print $4}' || echo "unknown")
        else
            CURRENT_IMAGE="none"
        fi

        log_info "Current image: $CURRENT_IMAGE"
        log_info "Running services: $CURRENT_CONTAINERS"
    else
        log_error "Docker compose file not found: $compose_file"
        exit 1
    fi
}

# Get available rollback versions
get_available_versions() {
    log_info "Scanning for available rollback versions..."

    # Check Docker images
    AVAILABLE_IMAGES=$(docker images ald-control-system --format "table {{.Tag}}" | grep -v "TAG" | grep -v "latest" | sort -V -r | head -10 || echo "")

    # Check backup configurations
    BACKUP_DIR="$DEPLOYMENT_DIR/backups"
    if [[ -d "$BACKUP_DIR" ]]; then
        AVAILABLE_CONFIGS=$(ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | xargs -I {} basename {} .tar.gz | sort -V -r || echo "")
    else
        AVAILABLE_CONFIGS=""
    fi

    log_info "Available Docker images: $AVAILABLE_IMAGES"
    log_info "Available backup configs: $AVAILABLE_CONFIGS"
}

# Create backup of current state
create_backup() {
    log_info "Creating backup of current deployment state..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create backup of current state"
        return 0
    fi

    local backup_dir="$DEPLOYMENT_DIR/backups"
    local backup_timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/rollback_backup_${backup_timestamp}.tar.gz"

    mkdir -p "$backup_dir"

    # Backup configuration files
    tar -czf "$backup_file" \
        -C "$DEPLOYMENT_DIR" \
        docker-compose.prod.yml \
        haproxy/haproxy.cfg \
        monitoring/ \
        config/ \
        2>/dev/null || log_warning "Some files could not be backed up"

    if [[ -f "$backup_file" ]]; then
        log_success "Backup created: $backup_file"
    else
        log_warning "Backup creation failed"
    fi
}

# Auto rollback to last known good version
auto_rollback() {
    log_info "Performing automatic rollback..."

    # Try to determine last known good version
    local last_good_version=""

    # Check deployment history
    if [[ -f "$DEPLOYMENT_DIR/deployment.log" ]]; then
        last_good_version=$(grep "DEPLOYMENT_SUCCESS" "$DEPLOYMENT_DIR/deployment.log" | tail -2 | head -1 | awk '{print $3}' || echo "")
    fi

    # Fallback to previous image tag
    if [[ -z "$last_good_version" ]]; then
        last_good_version=$(docker images ald-control-system --format "{{.Tag}}" | grep -v "latest" | sort -V -r | head -2 | tail -1 || echo "")
    fi

    if [[ -z "$last_good_version" ]]; then
        log_error "Cannot determine last known good version for auto rollback"
        return 1
    fi

    log_info "Auto rollback target: $last_good_version"
    PREVIOUS_VERSION="$last_good_version"
    rollback_to_version
}

# Manual interactive rollback
manual_rollback() {
    log_info "Starting manual rollback process..."

    get_available_versions

    echo ""
    echo "Available versions for rollback:"
    echo "================================"

    local versions=()
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            versions+=("$line")
            echo "${#versions[@]}. $line"
        fi
    done <<< "$AVAILABLE_IMAGES"

    echo ""
    read -p "Select version number to rollback to (1-${#versions[@]}): " selection

    if [[ "$selection" =~ ^[0-9]+$ ]] && [[ "$selection" -ge 1 ]] && [[ "$selection" -le "${#versions[@]}" ]]; then
        PREVIOUS_VERSION="${versions[$((selection-1))]}"
        log_info "Selected version: $PREVIOUS_VERSION"
        rollback_to_version
    else
        log_error "Invalid selection: $selection"
        exit 1
    fi
}

# Rollback to specific version
rollback_to_version() {
    log_info "Rolling back to version: $PREVIOUS_VERSION"

    local compose_file="$DEPLOYMENT_DIR/docker-compose.prod.yml"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would rollback to version: $PREVIOUS_VERSION"
        log_info "[DRY RUN] Would update docker-compose configuration"
        log_info "[DRY RUN] Would restart services with previous version"
        log_info "[DRY RUN] Would perform health checks"
        return 0
    fi

    # Verify target image exists
    if ! docker pull "ald-control-system:$PREVIOUS_VERSION" > /dev/null 2>&1; then
        log_error "Target image not found: ald-control-system:$PREVIOUS_VERSION"
        exit 1
    fi

    # Update environment to use previous version
    export IMAGE_TAG="$PREVIOUS_VERSION"
    log_info "Using image tag: $IMAGE_TAG"

    # Stop current services
    log_info "Stopping current services..."
    docker-compose -f "$compose_file" down --timeout 30

    # Start services with previous version
    log_info "Starting services with version $PREVIOUS_VERSION..."
    docker-compose -f "$compose_file" up -d ald-control

    # Health check with retry
    local max_retries=12
    local retry_count=0
    local health_ok=false

    log_info "Performing health checks..."
    while [[ $retry_count -lt $max_retries ]]; do
        if curl -sf "http://localhost:8000/health/basic" > /dev/null 2>&1; then
            health_ok=true
            break
        fi

        retry_count=$((retry_count + 1))
        log_info "Health check failed, retrying in 10s... ($retry_count/$max_retries)"
        sleep 10
    done

    if [[ "$health_ok" == "true" ]]; then
        log_success "Rollback completed successfully!"
        log_success "System is healthy on version: $PREVIOUS_VERSION"

        # Log successful rollback
        echo "$(date '+%Y-%m-%d %H:%M:%S') ROLLBACK_SUCCESS $PREVIOUS_VERSION" >> "$DEPLOYMENT_DIR/deployment.log"
    else
        log_error "Rollback health check failed"
        log_error "Manual intervention required"
        exit 1
    fi
}

# Emergency stop all services
emergency_stop() {
    log_warning "Performing emergency stop of all services..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would stop all ALD Control services immediately"
        return 0
    fi

    local compose_file="$DEPLOYMENT_DIR/docker-compose.prod.yml"

    # Force stop all services
    docker-compose -f "$compose_file" down --timeout 10

    log_warning "All services stopped"
    log_info "System is in maintenance mode - manual restart required"
}

# Confirmation prompt
confirm_rollback() {
    if [[ "$CONFIRM" == "true" ]]; then
        return 0
    fi

    echo ""
    echo "ROLLBACK CONFIRMATION"
    echo "===================="
    echo "Environment: $ENVIRONMENT"
    echo "Method: $ROLLBACK_METHOD"
    echo "Current Image: $CURRENT_IMAGE"

    if [[ -n "$PREVIOUS_VERSION" ]]; then
        echo "Target Version: $PREVIOUS_VERSION"
    fi

    echo ""
    echo "WARNING: This will interrupt the current ALD process!"
    echo ""

    read -p "Are you sure you want to proceed with rollback? (yes/no): " confirm

    if [[ "$confirm" != "yes" ]]; then
        log_info "Rollback cancelled by user"
        exit 0
    fi
}

# Main rollback function
main() {
    log_warning "ALD Control System Rollback Initiated"
    log_info "Environment: $ENVIRONMENT"
    log_info "Method: $ROLLBACK_METHOD"
    log_info "Dry Run: $DRY_RUN"

    # Get current status
    get_current_status

    # Create backup before rollback
    create_backup

    # Confirmation
    confirm_rollback

    # Execute rollback based on method
    case "$ROLLBACK_METHOD" in
        "auto")
            auto_rollback
            ;;
        "manual")
            manual_rollback
            ;;
        "version")
            rollback_to_version
            ;;
    esac

    log_success "Rollback process completed!"
}

# Parse arguments and run main function
parse_args "$@"
validate_args
main