#!/bin/bash

# Production deployment script for Test Results Management API
# Usage: ./scripts/deploy.sh [environment] [version]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-production}"
VERSION="${2:-latest}"
IMAGE_NAME="test-results-api"
REGISTRY="your-registry.com"  # Replace with your registry

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

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
validate_environment() {
    if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT. Must be development, staging, or production"
        exit 1
    fi

    log_info "Deploying to environment: $ENVIRONMENT"
}

# Check prerequisites
check_prerequisites() {
    local missing_deps=()

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi

    # Check kubectl for Kubernetes deployment
    if ! command -v kubectl &> /dev/null; then
        missing_deps+=("kubectl")
    fi

    # Check environment-specific dependencies
    if [[ "$ENVIRONMENT" == "production" ]]; then
        if ! command -v helm &> /dev/null; then
            missing_deps+=("helm")
        fi
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_error "Please install missing dependencies and try again"
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."

    cd "$PROJECT_DIR"

    # Build production image
    docker build \
        --target production \
        --tag "$IMAGE_NAME:$VERSION" \
        --tag "$IMAGE_NAME:latest" \
        --build-arg APP_VERSION="$VERSION" \
        --build-arg APP_ENVIRONMENT="$ENVIRONMENT" \
        .

    log_success "Docker image built successfully"
}

# Run tests in container
run_tests() {
    log_info "Running tests in container..."

    # Build test image
    docker build --target development --tag "$IMAGE_NAME:test" .

    # Run unit tests
    docker run --rm \
        -v "$PROJECT_DIR:/app" \
        "$IMAGE_NAME:test" \
        pytest tests/unit/ -v

    # Run contract tests
    docker run --rm \
        -v "$PROJECT_DIR:/app" \
        "$IMAGE_NAME:test" \
        pytest tests/contract/ -v

    log_success "All tests passed"
}

# Push image to registry
push_image() {
    if [[ "$ENVIRONMENT" == "development" ]]; then
        log_info "Skipping image push for development environment"
        return
    fi

    log_info "Pushing image to registry..."

    # Tag for registry
    docker tag "$IMAGE_NAME:$VERSION" "$REGISTRY/$IMAGE_NAME:$VERSION"
    docker tag "$IMAGE_NAME:latest" "$REGISTRY/$IMAGE_NAME:latest"

    # Push to registry
    docker push "$REGISTRY/$IMAGE_NAME:$VERSION"
    docker push "$REGISTRY/$IMAGE_NAME:latest"

    log_success "Image pushed to registry"
}

# Deploy to Docker Compose (development/staging)
deploy_docker_compose() {
    log_info "Deploying with Docker Compose..."

    cd "$PROJECT_DIR"

    # Use environment-specific compose file
    COMPOSE_FILE="docker-compose.$ENVIRONMENT.yml"

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    # Set environment variables
    export IMAGE_TAG="$VERSION"
    export APP_ENVIRONMENT="$ENVIRONMENT"

    # Deploy
    docker-compose -f "$COMPOSE_FILE" down || true
    docker-compose -f "$COMPOSE_FILE" up -d

    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" exec -T api uv run alembic upgrade head

    log_success "Docker Compose deployment completed"
}

# Deploy to Kubernetes (production)
deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."

    local namespace="test-results-$ENVIRONMENT"
    local helm_release="test-results-api"

    # Ensure namespace exists
    kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -

    # Deploy with Helm
    if helm list -n "$namespace" | grep -q "$helm_release"; then
        log_info "Upgrading existing Helm release..."
        helm upgrade "$helm_release" "$PROJECT_DIR/helm/test-results-api" \
            --namespace "$namespace" \
            --set image.tag="$VERSION" \
            --set environment="$ENVIRONMENT" \
            --wait
    else
        log_info "Installing new Helm release..."
        helm install "$helm_release" "$PROJECT_DIR/helm/test-results-api" \
            --namespace "$namespace" \
            --set image.tag="$VERSION" \
            --set environment="$ENVIRONMENT" \
            --wait
    fi

    # Verify deployment
    kubectl rollout status deployment/test-results-api -n "$namespace"

    log_success "Kubernetes deployment completed"
}

# Health check
health_check() {
    log_info "Performing health check..."

    local health_url
    case "$ENVIRONMENT" in
        development)
            health_url="http://localhost:8000/health"
            ;;
        staging)
            health_url="https://staging-api.testresults.dev/health"
            ;;
        production)
            health_url="https://api.testresults.dev/health"
            ;;
    esac

    # Wait for service to be ready
    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f "$health_url" &> /dev/null; then
            log_success "Health check passed"
            return 0
        fi

        log_info "Health check attempt $attempt/$max_attempts failed, retrying..."
        sleep 10
        ((attempt++))
    done

    log_error "Health check failed after $max_attempts attempts"
    return 1
}

# Rollback function
rollback() {
    log_warn "Rolling back deployment..."

    if [[ "$ENVIRONMENT" == "production" ]]; then
        helm rollback test-results-api -n "test-results-$ENVIRONMENT"
        kubectl rollout status deployment/test-results-api -n "test-results-$ENVIRONMENT"
    else
        # For Docker Compose, restore previous version
        log_warn "Manual rollback required for Docker Compose deployment"
    fi

    log_success "Rollback completed"
}

# Cleanup old images and containers
cleanup() {
    log_info "Cleaning up old images and containers..."

    # Remove old test containers
    docker container prune -f

    # Remove old images (keep last 5 versions)
    docker images "$IMAGE_NAME" --format "table {{.Tag}}" | tail -n +2 | sort -V | head -n -5 | xargs -r docker rmi "$IMAGE_NAME:" || true

    log_success "Cleanup completed"
}

# Main deployment function
deploy() {
    log_info "Starting deployment of $IMAGE_NAME:$VERSION to $ENVIRONMENT"

    validate_environment
    check_prerequisites

    # Build and test
    build_image
    run_tests

    # Push to registry (if not development)
    push_image

    # Deploy based on environment
    case "$ENVIRONMENT" in
        development|staging)
            deploy_docker_compose
            ;;
        production)
            deploy_kubernetes
            ;;
    esac

    # Verify deployment
    if health_check; then
        cleanup
        log_success "Deployment completed successfully!"
    else
        log_error "Deployment failed health check"
        if [[ "$ENVIRONMENT" == "production" ]]; then
            rollback
        fi
        exit 1
    fi
}

# Handle script arguments
case "${3:-deploy}" in
    deploy)
        deploy
        ;;
    rollback)
        rollback
        ;;
    health-check)
        health_check
        ;;
    cleanup)
        cleanup
        ;;
    *)
        echo "Usage: $0 [environment] [version] [action]"
        echo "  environment: development, staging, production (default: production)"
        echo "  version: image version tag (default: latest)"
        echo "  action: deploy, rollback, health-check, cleanup (default: deploy)"
        exit 1
        ;;
esac