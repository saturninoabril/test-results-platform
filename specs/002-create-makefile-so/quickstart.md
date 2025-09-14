# Quickstart Guide: Comprehensive Development Makefile

## Overview
This guide walks through the complete development workflow using the new Makefile commands, from initial setup to production deployment.

## Prerequisites
- GNU Make installed
- Python 3.13+ available
- Docker and Docker Compose installed
- PostgreSQL accessible (local or containerized)
- Git repository access

## Quick Start Workflow

### 1. Initial Setup
```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd test-results-platform

# Install development dependencies
make install

# Verify installation
make help
```

**Expected Output**:
- Dependencies installed successfully
- Help menu showing all available commands
- No errors reported

### 2. Development Environment Setup
```bash
# Set up database with latest migrations
make db-upgrade

# Seed database with test data (optional)
make db-seed

# Start development server
make dev
```

**Expected Output**:
- Database migrations applied successfully
- FastAPI server running on http://localhost:8000
- Auto-reload enabled for code changes

### 3. Code Quality Workflow
```bash
# Run type checking
make type-check

# Run linting
make lint

# Format code (if needed)
make format

# Run unit tests
make test-unit
```

**Expected Output**:
- Type checking passes with no errors
- Linting passes or shows specific issues to fix
- Code formatted according to project standards
- Unit tests pass with coverage report

### 4. Integration Testing
```bash
# Run integration tests with real dependencies
make test-integration

# Run contract tests
make test-contract

# Run complete test suite
make test-all
```

**Expected Output**:
- Integration tests pass with real PostgreSQL/MinIO
- API contracts validated successfully
- All test suites pass with comprehensive report

### 5. Build and Container Workflow
```bash
# Create production build
make build

# Build development Docker image
make docker-build

# Run application in container
make docker-run
```

**Expected Output**:
- Production artifacts created in `dist/` directory
- Docker image built successfully
- Application running in container on mapped port

### 6. Production Deployment Preparation
```bash
# Build production Docker image
make docker-build-prod

# Validate build artifacts
make build-check

# Publish to registry (CI/CD environment)
make docker-publish
```

**Expected Output**:
- Optimized production image created
- Build artifacts validated
- Image pushed to configured registry

## Daily Development Commands

### Most Common Commands
```bash
# Start developing (complete setup)
make dev                    # Start development server

# Code quality check
make type-check lint        # Quick quality verification

# Test changes
make test-unit              # Fast unit test feedback

# Clean workspace
make clean                  # Remove cache files
```

### Debugging Commands
```bash
# Development with debugging
make dev-debug              # Start with debugger support

# Verbose output
make test-unit VERBOSE=1    # Detailed test output

# Database inspection
make db-upgrade             # Apply latest migrations
make db-reset               # Fresh database (development only)
```

## Dependency Management

### Adding New Dependencies
```bash
# Add a new package
uv add <package-name>

# Upgrade all dependencies
make upgrade

# Install updated dependencies
make install
```

### Upgrading Existing Dependencies
```bash
# Upgrade all to latest versions
make upgrade

# Upgrade specific package
uv lock --upgrade-package <package-name>
make install
```

## Troubleshooting Common Issues

### Development Server Won't Start
```bash
# Check database status
make db-upgrade

# Verify dependencies
make install

# Clean and retry
make clean
make dev
```

### Tests Failing
```bash
# Run tests in verbose mode
make test-unit VERBOSE=1

# Check database state
make db-reset
make db-seed

# Verify integration test dependencies
make docker-build
```

### Docker Issues
```bash
# Clean Docker artifacts
make clean-docker

# Rebuild images
make docker-build

# Check container logs
docker logs <container-name>
```

### Type Checking Errors
```bash
# Run type checking with details
make type-check VERBOSE=1

# Check for import issues
make install
```

## CI/CD Integration Examples

### GitHub Actions Workflow
```yaml
# Example workflow using Makefile commands
- name: Install dependencies
  run: make install

- name: Run quality checks
  run: make type-check lint

- name: Run tests
  run: make test-all

- name: Build application
  run: make build

- name: Build and publish container
  run: |
    make docker-build-prod
    make docker-publish
```

### Local CI Simulation
```bash
# Simulate complete CI/CD pipeline
make clean-all
make install
make type-check
make lint
make test-all
make build
make docker-build-prod
```

## Environment-Specific Usage

### Development Environment
```bash
export ENV=dev
make dev                    # Development server
make test-unit              # Fast feedback tests
make db-reset               # Safe database operations
```

### Testing Environment
```bash
export ENV=test
make test-all               # Complete test suite
make db-upgrade             # Production-like migrations
```

### Production Environment
```bash
export ENV=prod
make build                  # Production artifacts
make docker-build-prod      # Optimized containers
make db-upgrade             # Safe migration deployment
```

## Performance Tips

### Parallel Execution
```bash
# Run tests in parallel (if supported)
make test-unit PARALLEL=1

# Parallel Docker builds
make -j4 docker-build       # Use multiple cores
```

### Caching Optimization
```bash
# Leverage Docker layer caching
make docker-build           # Subsequent builds faster

# Use dependency caching
make install                # uv handles caching automatically
```

## Success Validation

### Complete Workflow Test
Run this sequence to verify everything works:

```bash
# Clean slate
make clean-all

# Development setup
make install
make db-upgrade
make dev &                  # Background process
sleep 5                     # Wait for startup
curl http://localhost:8000/health  # Verify running
kill %1                     # Stop dev server

# Quality and testing
make type-check
make lint
make test-all

# Build and deploy
make build
make docker-build-prod
make build-check

echo "✅ Complete workflow successful!"
```

**Expected Result**: All commands complete successfully with exit code 0.

---

**Guide Version**: 1.0
**Last Updated**: 2025-09-14
**Prerequisites**: Makefile implementation complete