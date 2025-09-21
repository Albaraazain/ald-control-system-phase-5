#!/bin/bash
# Production deployment script for ALD Control System
# Supports blue-green, canary, and rolling deployments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_ROOT/deployment"

# Default values
ENVIRONMENT="staging"
DEPLOYMENT_STRATEGY="blue-green"
IMAGE_TAG="latest"
HEALTH_CHECK_TIMEOUT=300
ROLLBACK_ON_FAILURE=true
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

Deploy ALD Control System to production environment

OPTIONS:
    -e, --environment ENVIRONMENT       Target environment (staging|production) [default: staging]
    -s, --strategy STRATEGY            Deployment strategy (blue-green|canary|rolling) [default: blue-green]
    -t, --tag TAG                      Docker image tag [default: latest]
    -T, --timeout SECONDS             Health check timeout [default: 300]
    -r, --no-rollback                 Disable automatic rollback on failure
    -d, --dry-run                      Show what would be done without executing
    -h, --help                         Show this help message

EXAMPLES:
    $0 --environment production --strategy blue-green --tag v1.2.3
    $0 --environment staging --strategy canary --dry-run
    $0 --environment production --strategy rolling --no-rollback

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
            -s|--strategy)
                DEPLOYMENT_STRATEGY="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -T|--timeout)
                HEALTH_CHECK_TIMEOUT="$2"
                shift 2
                ;;
            -r|--no-rollback)
                ROLLBACK_ON_FAILURE=false
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

    if [[ ! "$DEPLOYMENT_STRATEGY" =~ ^(blue-green|canary|rolling)$ ]]; then
        log_error "Invalid deployment strategy: $DEPLOYMENT_STRATEGY"
        exit 1
    fi

    if [[ ! "$HEALTH_CHECK_TIMEOUT" =~ ^[0-9]+$ ]]; then
        log_error "Invalid timeout: $HEALTH_CHECK_TIMEOUT"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    # Check curl for health checks
    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed"
        exit 1
    fi

    # Check required files
    required_files=(
        "$DEPLOYMENT_DIR/docker-compose.prod.yml"
        "$DEPLOYMENT_DIR/Dockerfile"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file not found: $file"
            exit 1
        fi
    done

    log_success "Prerequisites check passed"
}

# Load environment configuration
load_environment() {
    local env_file="$DEPLOYMENT_DIR/config/$ENVIRONMENT.env"

    if [[ -f "$env_file" ]]; then
        log_info "Loading environment configuration: $env_file"
        set -a
        source "$env_file"
        set +a
    else
        log_warning "Environment file not found: $env_file"
        log_info "Using default configuration"
    fi
}

# Health check function
health_check() {
    local service_url="$1"
    local timeout="$2"
    local start_time=$(date +%s)

    log_info "Performing health check on $service_url (timeout: ${timeout}s)"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [[ $elapsed -ge $timeout ]]; then
            log_error "Health check timed out after ${timeout}s"
            return 1
        fi

        if curl -sf "$service_url/health" > /dev/null 2>&1; then
            log_success "Health check passed"
            return 0
        fi

        log_info "Health check failed, retrying in 5s... (${elapsed}s elapsed)"
        sleep 5
    done
}

# Blue-Green deployment
deploy_blue_green() {
    log_info "Executing blue-green deployment..."

    local compose_file="$DEPLOYMENT_DIR/docker-compose.prod.yml"
    local green_service="ald-control-green"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would start green service with image: $IMAGE_TAG"
        log_info "[DRY RUN] Would perform health check on green service"
        log_info "[DRY RUN] Would switch traffic to green service"
        log_info "[DRY RUN] Would stop blue service"
        return 0
    fi

    # Start green service
    log_info "Starting green service..."
    export IMAGE_TAG="$IMAGE_TAG"
    docker-compose -f "$compose_file" --profile blue-green up -d "$green_service"

    # Health check green service
    if ! health_check "http://localhost:8001" "$HEALTH_CHECK_TIMEOUT"; then
        log_error "Green service health check failed"
        if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
            log_info "Rolling back green service..."
            docker-compose -f "$compose_file" --profile blue-green stop "$green_service"
        fi
        return 1
    fi

    # Switch traffic (update load balancer configuration)
    log_info "Switching traffic to green service..."
    # TODO: Implement load balancer configuration update

    # Stop blue service
    log_info "Stopping blue service..."
    docker-compose -f "$compose_file" stop ald-control

    # Promote green to blue
    log_info "Promoting green service to blue..."
    docker-compose -f "$compose_file" up -d ald-control

    log_success "Blue-green deployment completed successfully"
}

# Canary deployment
deploy_canary() {
    log_info "Executing canary deployment..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would deploy canary instance with 10% traffic"
        log_info "[DRY RUN] Would monitor canary metrics"
        log_info "[DRY RUN] Would gradually increase traffic to 100%"
        return 0
    fi

    # TODO: Implement canary deployment logic
    log_warning "Canary deployment not fully implemented yet"
    log_info "Falling back to rolling deployment"
    deploy_rolling
}

# Rolling deployment
deploy_rolling() {
    log_info "Executing rolling deployment..."

    local compose_file="$DEPLOYMENT_DIR/docker-compose.prod.yml"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would update service with new image: $IMAGE_TAG"
        log_info "[DRY RUN] Would perform rolling update"
        return 0
    fi

    # Update service
    log_info "Updating service with image: $IMAGE_TAG"
    export IMAGE_TAG="$IMAGE_TAG"
    docker-compose -f "$compose_file" up -d ald-control

    # Health check
    if ! health_check "http://localhost:8000" "$HEALTH_CHECK_TIMEOUT"; then
        log_error "Rolling deployment health check failed"
        if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
            log_info "Rolling back deployment..."
            # TODO: Implement rollback logic
        fi
        return 1
    fi

    log_success "Rolling deployment completed successfully"
}

# Rollback function
rollback() {
    log_info "Performing rollback..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would rollback to previous version"
        return 0
    fi

    # TODO: Implement rollback logic
    log_warning "Rollback functionality not fully implemented yet"
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."

    # Check if services are running
    if docker-compose -f "$DEPLOYMENT_DIR/docker-compose.prod.yml" ps | grep -q "Up"; then
        log_info "Existing services detected"
    else
        log_info "No existing services running"
    fi

    # Validate Docker image exists
    if docker pull "ald-control-system:$IMAGE_TAG" > /dev/null 2>&1; then
        log_success "Docker image validated: ald-control-system:$IMAGE_TAG"
    else
        log_error "Docker image not found: ald-control-system:$IMAGE_TAG"
        exit 1
    fi
}

# Post-deployment checks
post_deployment_checks() {
    log_info "Running post-deployment checks..."

    # Verify services are running
    local compose_file="$DEPLOYMENT_DIR/docker-compose.prod.yml"
    if docker-compose -f "$compose_file" ps ald-control | grep -q "Up"; then
        log_success "Main service is running"
    else
        log_error "Main service is not running"
        return 1
    fi

    # Final health check
    if health_check "http://localhost:8000" 60; then
        log_success "Post-deployment health check passed"
    else
        log_error "Post-deployment health check failed"
        return 1
    fi

    log_success "Post-deployment checks completed"
}

# Main deployment function
main() {
    log_info "Starting ALD Control System deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Strategy: $DEPLOYMENT_STRATEGY"
    log_info "Image Tag: $IMAGE_TAG"
    log_info "Dry Run: $DRY_RUN"

    # Run all checks and deployment steps
    check_prerequisites
    load_environment
    pre_deployment_checks

    # Execute deployment strategy
    case "$DEPLOYMENT_STRATEGY" in
        "blue-green")
            deploy_blue_green
            ;;
        "canary")
            deploy_canary
            ;;
        "rolling")
            deploy_rolling
            ;;
    esac

    # Post-deployment validation
    if [[ "$DRY_RUN" == "false" ]]; then
        post_deployment_checks
    fi

    log_success "Deployment completed successfully!"
}

# Parse arguments and run main function
parse_args "$@"
validate_args
main