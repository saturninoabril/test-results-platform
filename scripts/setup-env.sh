#!/bin/bash

# Environment setup script for Test Results Management API
# Usage: ./scripts/setup-env.sh [environment]

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-development}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

# Generate secure random string
generate_secret() {
    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install system dependencies
install_system_dependencies() {
    log_info "Installing system dependencies..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Ubuntu/Debian
        if command_exists apt-get; then
            sudo apt-get update
            sudo apt-get install -y \
                python3.13 \
                python3-pip \
                postgresql-client \
                curl \
                jq \
                git
        # RedHat/CentOS
        elif command_exists yum; then
            sudo yum update -y
            sudo yum install -y \
                python313 \
                python3-pip \
                postgresql \
                curl \
                jq \
                git
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command_exists brew; then
            brew update
            brew install python@3.13 postgresql curl jq git
        else
            log_error "Homebrew not found. Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    fi

    log_success "System dependencies installed"
}

# Install Python dependencies
install_python_dependencies() {
    log_info "Installing Python dependencies..."

    cd "$PROJECT_DIR"

    # Install uv if not present
    if ! command_exists uv; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null || true
    fi

    # Install project dependencies
    uv sync

    if [[ "$ENVIRONMENT" == "development" ]]; then
        uv sync --dev
        log_info "Development dependencies installed"
    fi

    log_success "Python dependencies installed"
}

# Install Docker and Docker Compose
install_docker() {
    if command_exists docker && command_exists docker-compose; then
        log_info "Docker already installed"
        return
    fi

    log_info "Installing Docker..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Install Docker on Linux
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        rm get-docker.sh

        # Add user to docker group
        sudo usermod -aG docker "$USER"

        # Install Docker Compose
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose

    elif [[ "$OSTYPE" == "darwin"* ]]; then
        log_warn "Please install Docker Desktop for Mac from: https://docs.docker.com/docker-for-mac/install/"
        log_warn "Docker Compose is included with Docker Desktop"
        return
    fi

    log_success "Docker installed. Please log out and log back in to use Docker without sudo"
}

# Setup development database
setup_development_database() {
    if [[ "$ENVIRONMENT" != "development" ]]; then
        return
    fi

    log_info "Setting up development database..."

    cd "$PROJECT_DIR"

    # Start PostgreSQL with Docker Compose
    docker-compose up -d postgres

    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10

    # Run database migrations
    log_info "Running database migrations..."
    uv run alembic upgrade head

    log_success "Development database setup completed"
}

# Setup development storage
setup_development_storage() {
    if [[ "$ENVIRONMENT" != "development" ]]; then
        return
    fi

    log_info "Setting up development storage (MinIO)..."

    cd "$PROJECT_DIR"

    # Start MinIO with Docker Compose
    docker-compose up -d minio

    # Wait for MinIO to be ready
    log_info "Waiting for MinIO to be ready..."
    sleep 10

    # Create bucket if it doesn't exist
    if command_exists mc; then
        mc config host add local http://localhost:9000 minioadmin minioadmin123
        mc mb local/test-results-artifacts || true
        log_success "MinIO bucket created"
    else
        log_warn "MinIO client (mc) not found. Please create bucket manually at http://localhost:9001"
    fi

    log_success "Development storage setup completed"
}

# Generate environment configuration
generate_env_config() {
    local env_file="$PROJECT_DIR/.env.$ENVIRONMENT"

    log_info "Generating environment configuration: $env_file"

    # Generate secrets
    local jwt_secret
    jwt_secret=$(generate_secret)

    case "$ENVIRONMENT" in
        development)
            cat > "$env_file" << EOF
# Development Environment Configuration
APP_ENVIRONMENT=development
DEBUG=true
APP_VERSION=0.4.0

# Database Configuration
DATABASE_URL=postgresql+asyncpg://testresults:testresults123@localhost:5432/testresults
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Storage Configuration
STORAGE_TYPE=minio
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin123
STORAGE_BUCKET=test-results-artifacts
STORAGE_SECURE=false

# Authentication Configuration
JWT_SECRET_KEY=$jwt_secret
JWT_EXPIRATION_HOURS=24

# GitHub OAuth (optional for development)
# GITHUB_CLIENT_ID=your-github-client-id
# GITHUB_CLIENT_SECRET=your-github-client-secret
# GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback

# Logging Configuration
LOG_LEVEL=DEBUG
LOG_FORMAT=standard
STRUCTURED_LOGGING=false

# Security Configuration
CORS_ORIGINS=*
RATE_LIMIT_ENABLED=false
ENABLE_SECURITY_HEADERS=false

# Performance Configuration
WORKERS=1
CACHE_ENABLED=false
EOF
            ;;

        staging)
            cat > "$env_file" << EOF
# Staging Environment Configuration
APP_ENVIRONMENT=staging
DEBUG=false
APP_VERSION=0.4.0

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@staging-db-host:5432/testresults
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Storage Configuration
STORAGE_TYPE=s3
STORAGE_ENDPOINT=https://s3.us-west-2.amazonaws.com
STORAGE_ACCESS_KEY=your-s3-access-key
STORAGE_SECRET_KEY=your-s3-secret-key
STORAGE_BUCKET=test-results-staging-artifacts
STORAGE_REGION=us-west-2

# Authentication Configuration
JWT_SECRET_KEY=$jwt_secret
JWT_EXPIRATION_HOURS=24

# GitHub OAuth
GITHUB_CLIENT_ID=your-staging-github-client-id
GITHUB_CLIENT_SECRET=your-staging-github-client-secret
GITHUB_REDIRECT_URI=https://staging-api.testresults.dev/auth/github/callback

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
STRUCTURED_LOGGING=true
LOG_FILE=/app/logs/app.log

# Security Configuration
CORS_ORIGINS=https://staging.testresults.dev,https://staging-dashboard.testresults.dev
RATE_LIMIT_ENABLED=true
ENABLE_SECURITY_HEADERS=true

# Performance Configuration
WORKERS=2
CACHE_ENABLED=true
CACHE_REDIS_URL=redis://staging-redis:6379/0
EOF
            ;;

        production)
            cat > "$env_file" << EOF
# Production Environment Configuration
APP_ENVIRONMENT=production
DEBUG=false
APP_VERSION=0.4.0

# Database Configuration (UPDATE WITH ACTUAL VALUES)
DATABASE_URL=postgresql+asyncpg://user:password@prod-db-host:5432/testresults
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=100
DATABASE_POOL_TIMEOUT=30

# Storage Configuration (UPDATE WITH ACTUAL VALUES)
STORAGE_TYPE=s3
STORAGE_ENDPOINT=https://s3.us-west-2.amazonaws.com
STORAGE_ACCESS_KEY=your-production-s3-access-key
STORAGE_SECRET_KEY=your-production-s3-secret-key
STORAGE_BUCKET=test-results-production-artifacts
STORAGE_REGION=us-west-2

# Authentication Configuration
JWT_SECRET_KEY=$jwt_secret
JWT_EXPIRATION_HOURS=24
AUTOMATION_TOKEN_MAX_AGE_DAYS=90

# GitHub OAuth (UPDATE WITH ACTUAL VALUES)
GITHUB_CLIENT_ID=your-production-github-client-id
GITHUB_CLIENT_SECRET=your-production-github-client-secret
GITHUB_REDIRECT_URI=https://api.testresults.dev/auth/github/callback

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
STRUCTURED_LOGGING=true
LOG_FILE=/app/logs/app.log

# Security Configuration (UPDATE CORS ORIGINS)
CORS_ORIGINS=https://testresults.dev,https://dashboard.testresults.dev
CORS_ALLOW_CREDENTIALS=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=100
ENABLE_SECURITY_HEADERS=true
MAX_UPLOAD_SIZE_MB=100

# Performance Configuration
WORKERS=4
MAX_REQUESTS=1000
CACHE_ENABLED=true
CACHE_REDIS_URL=redis://prod-redis:6379/0
CACHE_TTL_SECONDS=300
EOF
            ;;
    esac

    log_success "Environment configuration generated: $env_file"

    if [[ "$ENVIRONMENT" == "production" ]]; then
        log_warn "IMPORTANT: Update production environment file with actual values:"
        log_warn "  - Database connection string"
        log_warn "  - S3 credentials and bucket"
        log_warn "  - GitHub OAuth credentials"
        log_warn "  - CORS origins"
        log_warn "  - Redis URL"
    fi
}

# Setup pre-commit hooks
setup_pre_commit() {
    if [[ "$ENVIRONMENT" != "development" ]]; then
        return
    fi

    log_info "Setting up pre-commit hooks..."

    cd "$PROJECT_DIR"

    # Install pre-commit
    uv run pip install pre-commit

    # Install hooks
    uv run pre-commit install

    log_success "Pre-commit hooks installed"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/tmp"
    mkdir -p "$PROJECT_DIR/backups"

    if [[ "$ENVIRONMENT" == "development" ]]; then
        mkdir -p "$PROJECT_DIR/test-data"
        mkdir -p "$PROJECT_DIR/coverage"
    fi

    log_success "Directories created"
}

# Setup development tools
setup_development_tools() {
    if [[ "$ENVIRONMENT" != "development" ]]; then
        return
    fi

    log_info "Setting up development tools..."

    # Install additional development tools
    if [[ "$OSTYPE" == "darwin"* ]] && command_exists brew; then
        brew install --cask postman
        brew install httpie
        log_info "Installed Postman and HTTPie for API testing"
    fi

    # Create development shortcuts
    cat > "$PROJECT_DIR/dev-shortcuts.sh" << 'EOF'
#!/bin/bash
# Development shortcuts

# Start development environment
alias dev-start="docker-compose up -d && uvicorn src.main:app --reload"

# Run tests
alias dev-test="pytest"
alias dev-test-unit="pytest tests/unit/"
alias dev-test-integration="pytest tests/integration/"
alias dev-test-contract="pytest tests/contract/"

# Database operations
alias dev-db-migrate="alembic upgrade head"
alias dev-db-rollback="alembic downgrade -1"
alias dev-db-reset="alembic downgrade base && alembic upgrade head"

# Code quality
alias dev-lint="ruff check src/ tests/"
alias dev-format="ruff format src/ tests/"
alias dev-typecheck="mypy src/"

# Benchmarking
alias dev-benchmark="python -m src.cli.benchmark api"

echo "Development shortcuts loaded!"
echo "Available commands:"
echo "  dev-start       - Start development environment"
echo "  dev-test        - Run all tests"
echo "  dev-test-*      - Run specific test types"
echo "  dev-db-*        - Database operations"
echo "  dev-lint        - Run linting"
echo "  dev-format      - Format code"
echo "  dev-typecheck   - Run type checking"
echo "  dev-benchmark   - Run API benchmarks"
EOF

    chmod +x "$PROJECT_DIR/dev-shortcuts.sh"
    log_success "Development tools and shortcuts created"
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."

    cd "$PROJECT_DIR"

    # Check Python dependencies
    if ! uv run python -c "import fastapi, sqlalchemy, pydantic"; then
        log_error "Failed to import required Python packages"
        exit 1
    fi

    # Check database connection (development only)
    if [[ "$ENVIRONMENT" == "development" ]]; then
        if ! docker-compose exec -T postgres pg_isready -U testresults; then
            log_error "Database connection failed"
            exit 1
        fi
    fi

    # Check environment configuration
    if [[ ! -f ".env.$ENVIRONMENT" ]]; then
        log_error "Environment configuration file not found"
        exit 1
    fi

    log_success "Installation verified successfully"
}

# Display next steps
display_next_steps() {
    log_success "Environment setup completed for: $ENVIRONMENT"
    echo
    echo "Next steps:"
    echo

    case "$ENVIRONMENT" in
        development)
            echo "1. Start the development environment:"
            echo "   cd $PROJECT_DIR"
            echo "   source dev-shortcuts.sh"
            echo "   dev-start"
            echo
            echo "2. Run tests to verify everything works:"
            echo "   dev-test"
            echo
            echo "3. Access the API at http://localhost:8000"
            echo "   - API docs: http://localhost:8000/docs"
            echo "   - MinIO console: http://localhost:9001"
            echo
            echo "4. Import sample data:"
            echo "   uv run python -m src.cli.test_results import resource/playwright-test-results.json"
            ;;

        staging|production)
            echo "1. Update environment configuration:"
            echo "   vi .env.$ENVIRONMENT"
            echo
            echo "2. Deploy using the deployment script:"
            echo "   ./scripts/deploy.sh $ENVIRONMENT"
            echo
            echo "3. Verify deployment:"
            echo "   ./scripts/deploy.sh $ENVIRONMENT latest health-check"
            ;;
    esac
}

# Main setup function
main() {
    log_info "Setting up Test Results Management API for environment: $ENVIRONMENT"

    # Validate environment
    if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT. Must be development, staging, or production"
        exit 1
    fi

    # Run setup steps
    install_system_dependencies
    install_python_dependencies

    if [[ "$ENVIRONMENT" == "development" ]]; then
        install_docker
        setup_development_database
        setup_development_storage
        setup_pre_commit
        setup_development_tools
    fi

    create_directories
    generate_env_config
    verify_installation
    display_next_steps
}

# Run main function
main "$@"