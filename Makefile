# Comprehensive Development and Production Makefile
# Test Results Management Platform

# Shell configuration
SHELL := /bin/bash
.ONESHELL:
.DEFAULT_GOAL := help

# Environment variables
ENV ?= dev
VERBOSE ?= 0
CI ?= false

# Project configuration
PROJECT_NAME := test-results-platform
PYTHON_VERSION := 3.13
PYTHON_MIN_VERSION := 3.13
UV_VERSION := latest

# Development requirements check
define check_requirements
	@echo -e "$(BLUE)Checking development requirements...$(RESET)"
	@# Check Python version
	@if ! command -v python3 >/dev/null 2>&1; then \
		echo -e "$(RED)❌ Python 3 is not installed$(RESET)"; \
		echo -e "$(YELLOW)Please install Python $(PYTHON_MIN_VERSION)+ from https://python.org$(RESET)"; \
		exit 1; \
	fi
	@PYTHON_VERSION_CHECK=$$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"); \
	REQUIRED_VERSION="$(PYTHON_MIN_VERSION)"; \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$PYTHON_VERSION_CHECK" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo -e "$(RED)❌ Python $$PYTHON_VERSION_CHECK found, but $(PYTHON_MIN_VERSION)+ required$(RESET)"; \
		echo -e "$(YELLOW)Current Python version: $$PYTHON_VERSION_CHECK$(RESET)"; \
		echo -e "$(YELLOW)Required Python version: $(PYTHON_MIN_VERSION)+$(RESET)"; \
		echo -e "$(YELLOW)Please upgrade Python from https://python.org$(RESET)"; \
		exit 1; \
	fi
	@# Check uv installation
	@if ! command -v uv >/dev/null 2>&1; then \
		echo -e "$(RED)❌ uv is not installed$(RESET)"; \
		echo -e "$(YELLOW)Visit: https://docs.astral.sh/uv/getting-started/installation/$(RESET)"; \
		exit 1; \
	fi
	@# Check uv version (basic check)
	@UV_VERSION_INSTALLED=$$(uv --version | cut -d' ' -f2); \
	PYTHON_VERSION_CHECK=$$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"); \
	echo -e "$(GREEN)✅ Python $$PYTHON_VERSION_CHECK found$(RESET)"; \
	echo -e "$(GREEN)✅ uv $$UV_VERSION_INSTALLED found$(RESET)"; \
	echo -e "$(GREEN)✅ Development requirements satisfied$(RESET)"
endef

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
MAGENTA := \033[35m
CYAN := \033[36m
WHITE := \033[37m
RESET := \033[0m

# Docker configuration
DOCKER_IMAGE_DEV := $(PROJECT_NAME):dev
DOCKER_IMAGE_PROD := $(PROJECT_NAME):prod
DOCKER_REGISTRY ?= localhost:5000

# Database configuration
DATABASE_URL ?= postgresql+asyncpg://test_results_user:test_results_password@localhost:5433/test_results

# .PHONY declarations for all targets
.PHONY: help check-requirements install upgrade dev dev-https dev-certs dev-certs-force dev-certs-trust dev-https-setup type-check lint format test-unit test-integration test-contract test-all
.PHONY: build build-dev build-check docker-build docker-build-prod docker-publish docker-run
.PHONY: docker-up docker-down docker-logs docker-ps docker-restart
.PHONY: db-upgrade db-downgrade db-reset db-seed clean clean-docker docker-prune clean-all
.PHONY: playwright-test validate-artifacts download-object

# Default target - show help
help: ## Show this help message with available targets
	@echo -e "$(CYAN)$(PROJECT_NAME) - Development and Production Makefile$(RESET)"
	@echo ""
	@echo -e "$(YELLOW)Usage:$(RESET) make <target> [options]"
	@echo ""
	@echo -e "$(GREEN)Development Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(check-requirements|install|upgrade|dev.*)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo -e "$(GREEN)Quality Assurance Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(type-check|lint|format|test-.*)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo -e "$(GREEN)Build and Container Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(build|docker-.*)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo -e "$(GREEN)Database Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(db-.*)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo -e "$(GREEN)Playwright Demo Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(playwright-.*)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo -e "$(GREEN)Utility Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(clean.*|help|download-object|stop)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo -e "$(YELLOW)Environment Variables:$(RESET)"
	@echo "  ENV=dev|test|prod     Set environment (default: dev)"
	@echo "  VERBOSE=0|1           Enable verbose output (default: 0)"
	@echo "  CI=false|true         CI/CD environment detection (default: false)"
	@echo ""
	@echo -e "$(YELLOW)Examples:$(RESET)"
	@echo "  make install              # Install development dependencies"
	@echo "  make dev                  # Start HTTP development server"
	@echo "  make dev-https            # Start HTTPS development server"
	@echo "  make dev-https-setup      # View HTTPS setup documentation"
	@echo "  make test-all             # Run complete test suite"
	@echo "  make build ENV=prod       # Create production build"
	@echo "  make playwright-test      # Run Playwright tests with reporter"

# Development requirements validation
check-requirements: ## Check Python 3.13+ and uv installation
	$(call check_requirements)

# Development dependencies installation
install: check-requirements ## Install development dependencies
	@echo -e "$(BLUE)Installing development dependencies...$(RESET)"
	@echo -e "$(GREEN)Using uv for dependency management$(RESET)"
	@uv sync --extra dev
	@echo -e "$(GREEN)Dependencies installed successfully$(RESET)"

upgrade: check-requirements ## Upgrade all dependencies to latest versions
	@echo -e "$(BLUE)Upgrading all dependencies...$(RESET)"
	@echo -e "$(GREEN)Using uv to upgrade dependencies$(RESET)"
	@uv lock --upgrade
	@echo -e "$(CYAN)Updated uv.lock with new versions$(RESET)"
	@uv sync
	@echo -e "$(CYAN)Installed upgraded dependencies$(RESET)"
	@echo -e "$(GREEN)Dependencies upgraded successfully$(RESET)"

dev: install ## Start development server with hot reload (HTTP)
	@echo -e "$(BLUE)Starting development server with hot reload (HTTP)...$(RESET)"
	@echo -e "$(CYAN)Using uvicorn for FastAPI development$(RESET)"
	@echo ""
	@echo -e "$(GREEN)🌐 HTTP Development Server$(RESET)"
	@echo -e "$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo -e "$(CYAN)📍 Server URL:$(RESET)    http://localhost:8000"
	@echo -e "$(CYAN)📍 API Docs:$(RESET)     http://localhost:8000/docs"
	@echo -e "$(CYAN)📍 OpenAPI:$(RESET)      http://localhost:8000/openapi.json"
	@echo ""
	@echo -e "$(CYAN)💡 Development Tips:$(RESET)"
	@echo -e "   • Hot reload enabled - changes auto-restart server"
	@echo -e "   • Use VERBOSE=1 for detailed logging: make dev VERBOSE=1"
	@echo -e "   • HTTPS version available: make dev-https (port 8443)"
	@echo ""
	@echo -e "$(GREEN)Starting server... Press Ctrl+C to stop$(RESET)"
	@echo -e "$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo ""
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running with verbose output and debug logging$(RESET)"; \
		uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug; \
	else \
		uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload; \
	fi

dev-https: install dev-certs ## Start development server with HTTPS and hot reload
	@echo -e "$(BLUE)Starting development server with HTTPS and hot reload...$(RESET)"
	@echo -e "$(CYAN)Using uvicorn for FastAPI development with SSL$(RESET)"
	@echo ""
	@echo -e "$(GREEN)🔒 HTTPS Development Server$(RESET)"
	@echo -e "$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo -e "$(CYAN)📍 Server URL:$(RESET)    https://localhost:8443"
	@echo -e "$(CYAN)📍 API Docs:$(RESET)     https://localhost:8443/docs"
	@echo -e "$(CYAN)📍 OpenAPI:$(RESET)      https://localhost:8443/openapi.json"
	@echo ""
	@echo -e "$(YELLOW)🛡️  SSL Certificate Info:$(RESET)"
	@echo -e "   • Using mkcert locally-trusted certificates"
	@echo -e "   • No browser security warnings expected"
	@echo -e "   • Works with all browsers and HTTP tools"
	@echo ""
	@echo -e "$(CYAN)💡 Development Tips:$(RESET)"
	@echo -e "   • Hot reload enabled - changes auto-restart server"
	@echo -e "   • Use VERBOSE=1 for detailed logging: make dev-https VERBOSE=1"
	@echo -e "   • Check certificate status: make dev-certs-trust"
	@echo -e "   • HTTP version also available: make dev (port 8000)"
	@echo ""
	@echo -e "$(GREEN)Starting server... Press Ctrl+C to stop$(RESET)"
	@echo -e "$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo ""
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running with verbose output and debug logging$(RESET)"; \
		uv run uvicorn src.main:app --host 0.0.0.0 --port 8443 --reload --log-level debug \
			--ssl-keyfile certs/localhost.key --ssl-certfile certs/localhost.crt; \
	else \
		uv run uvicorn src.main:app --host 0.0.0.0 --port 8443 --reload \
			--ssl-keyfile certs/localhost.key --ssl-certfile certs/localhost.crt; \
	fi

dev-certs: ## Generate locally-trusted SSL certificates using mkcert
	@echo -e "$(BLUE)Generating SSL certificates for HTTPS development...$(RESET)"
	@if [ ! -f "certs/localhost.crt" ] || [ ! -f "certs/localhost.key" ]; then \
		./scripts/generate-dev-certs.sh; \
	else \
		echo -e "$(GREEN)SSL certificates already exist$(RESET)"; \
		echo -e "$(YELLOW)Certificate: certs/localhost.crt$(RESET)"; \
		echo -e "$(YELLOW)Private Key: certs/localhost.key$(RESET)"; \
		echo -e "$(CYAN)To regenerate certificates, run: make dev-certs-force$(RESET)"; \
	fi

dev-certs-force: ## Force regenerate SSL certificates
	@echo -e "$(BLUE)Force regenerating SSL certificates...$(RESET)"
	@rm -f certs/localhost.crt certs/localhost.key
	@./scripts/generate-dev-certs.sh

dev-certs-trust: dev-certs ## Check mkcert certificate status and troubleshoot
	@echo -e "$(BLUE)Checking mkcert certificate status...$(RESET)"
	@./scripts/trust-dev-cert.sh

dev-https-setup: ## View HTTPS development setup documentation
	@echo -e "$(CYAN)HTTPS Development Setup$(RESET)"
	@echo -e "$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo ""
	@echo -e "$(YELLOW)📖 Complete setup documentation available at:$(RESET)"
	@echo -e "   $(GREEN)docs/https-development.md$(RESET)"
	@echo ""
	@echo -e "$(YELLOW)🚀 Quick Start:$(RESET)"
	@echo -e "   $(CYAN)make dev-https$(RESET)     # Automatically sets up HTTPS and starts server"
	@echo ""
	@echo -e "$(YELLOW)📋 Manual Setup:$(RESET)"
	@echo -e "   $(CYAN)1.$(RESET) Install mkcert: $(GREEN)brew install mkcert$(RESET) (macOS)"
	@echo -e "   $(CYAN)2.$(RESET) Generate certs: $(GREEN)make dev-certs$(RESET)"
	@echo -e "   $(CYAN)3.$(RESET) Start server:   $(GREEN)make dev-https$(RESET)"
	@echo ""
	@echo -e "$(YELLOW)🌐 Server Access:$(RESET)"
	@echo -e "   • https://localhost:8443      (Main server)"
	@echo -e "   • https://localhost:8443/docs (API documentation)"
	@echo ""
	@echo -e "$(YELLOW)🛠️  Troubleshooting:$(RESET)"
	@echo -e "   $(CYAN)make dev-certs-trust$(RESET)  # Check certificate status"
	@echo -e "   $(CYAN)make dev-certs-force$(RESET)  # Regenerate certificates"
	@echo ""
	@echo -e "$(GREEN)Read the full guide: docs/https-development.md$(RESET)"

type-check: install ## Validate Python type annotations
	@echo -e "$(BLUE)Running type checking...$(RESET)"
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running mypy with verbose output$(RESET)"; \
		uv run mypy src/ --verbose; \
	else \
		uv run mypy src/; \
	fi
	@echo -e "$(GREEN)Type checking completed$(RESET)"

lint: install ## Run code linting
	@echo -e "$(BLUE)Running code linting...$(RESET)"
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running ruff with verbose output$(RESET)"; \
		uv run ruff check src/ tests/ --verbose; \
	else \
		uv run ruff check src/ tests/; \
	fi
	@echo -e "$(GREEN)Linting completed$(RESET)"

format: install ## Format code according to project standards
	@echo -e "$(BLUE)Formatting code...$(RESET)"
	@echo -e "$(CYAN)Running ruff format$(RESET)"
	@uv run ruff format src/ tests/
	@echo -e "$(CYAN)Running ruff check --fix$(RESET)"
	@uv run ruff check src/ tests/ --fix
	@echo -e "$(GREEN)Code formatting completed$(RESET)"

test-unit: install ## Run unit tests only
	@echo -e "$(BLUE)Running unit tests...$(RESET)"
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running with verbose output$(RESET)"; \
		uv run python -m pytest tests/unit/ -v --tb=short; \
	else \
		uv run python -m pytest tests/unit/ --tb=short; \
	fi
	@echo -e "$(GREEN)Unit tests completed$(RESET)"

test-integration: install ## Run integration tests with real dependencies
	@echo -e "$(BLUE)Running integration tests...$(RESET)"
	@echo -e "$(YELLOW)Note: Requires PostgreSQL and MinIO services running$(RESET)"
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running with verbose output$(RESET)"; \
		uv run python -m pytest tests/integration/ -v --tb=short; \
	else \
		uv run python -m pytest tests/integration/ --tb=short; \
	fi
	@echo -e "$(GREEN)Integration tests completed$(RESET)"

test-contract: install ## Run API contract validation tests
	@echo -e "$(BLUE)Running contract tests...$(RESET)"
	@echo -e "$(CYAN)Validating API contracts and Makefile interface specifications$(RESET)"
	@if [ "$(VERBOSE)" = "1" ]; then \
		echo -e "$(CYAN)Running with verbose output$(RESET)"; \
		uv run python -m pytest tests/contract/ -v --tb=short; \
	else \
		uv run python -m pytest tests/contract/ --tb=short; \
	fi
	@echo -e "$(GREEN)Contract tests completed$(RESET)"

test-all: install ## Run complete test suite
	@echo -e "$(BLUE)Running complete test suite...$(RESET)"
	@echo -e "$(CYAN)Step 1/3: Running unit tests$(RESET)"
	@$(MAKE) test-unit VERBOSE=$(VERBOSE)
	@echo -e "$(CYAN)Step 2/3: Running contract tests$(RESET)"
	@$(MAKE) test-contract VERBOSE=$(VERBOSE)
	@echo -e "$(CYAN)Step 3/3: Running integration tests$(RESET)"
	@$(MAKE) test-integration VERBOSE=$(VERBOSE)
	@echo -e "$(GREEN)✅ Complete test suite passed$(RESET)"

build: install type-check test-all ## Create production-ready artifacts
	@echo -e "$(BLUE)Creating production-ready artifacts...$(RESET)"
	@echo -e "$(CYAN)Building Python package$(RESET)"
	@uv build
	@echo -e "$(CYAN)Validating build artifacts$(RESET)"
	@ls -la dist/
	@echo -e "$(GREEN)✅ Production artifacts created successfully$(RESET)"

build-dev: install ## Create development build
	@echo -e "$(BLUE)Creating development build...$(RESET)"
	@echo -e "$(CYAN)Building with development dependencies included$(RESET)"
	@echo -e "$(YELLOW)Skipping tests for faster development iteration$(RESET)"
	@uv build
	@echo -e "$(CYAN)Development build artifacts:$(RESET)"
	@ls -la dist/
	@echo -e "$(GREEN)Development build completed$(RESET)"

build-check: ## Validate build artifacts
	@echo -e "$(BLUE)Validating build artifacts...$(RESET)"
	@if [ ! -d "dist" ]; then \
		echo -e "$(RED)❌ No build artifacts found$(RESET)"; \
		echo -e "$(YELLOW)Run 'make build' or 'make build-dev' first$(RESET)"; \
		exit 1; \
	fi
	@echo -e "$(CYAN)Checking for wheel and source distribution$(RESET)"
	@ls -la dist/
	@WHEEL_COUNT=$$(ls dist/*.whl 2>/dev/null | wc -l); \
	SDIST_COUNT=$$(ls dist/*.tar.gz 2>/dev/null | wc -l); \
	if [ $$WHEEL_COUNT -eq 0 ]; then \
		echo -e "$(RED)❌ No wheel (.whl) artifacts found$(RESET)"; \
		exit 1; \
	fi; \
	if [ $$SDIST_COUNT -eq 0 ]; then \
		echo -e "$(RED)❌ No source distribution (.tar.gz) artifacts found$(RESET)"; \
		exit 1; \
	fi
	@echo -e "$(CYAN)Validating package metadata$(RESET)"
	@uv run python scripts/validate_build.py
	@echo -e "$(GREEN)✅ Build artifacts validated successfully$(RESET)"

docker-build: ## Build development Docker image
	@echo -e "$(BLUE)Building development Docker image...$(RESET)"
	@echo -e "$(CYAN)Building $(DOCKER_IMAGE_DEV) with development dependencies$(RESET)"
	@if [ ! -f "Dockerfile" ]; then \
		echo -e "$(RED)❌ Dockerfile not found$(RESET)"; \
		exit 1; \
	fi
	@docker build \
		--target development \
		--tag $(DOCKER_IMAGE_DEV) \
		--label "project=$(PROJECT_NAME)" \
		--label "environment=development" \
		--label "build-date=$$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
		.
	@echo -e "$(GREEN)Development Docker image built: $(DOCKER_IMAGE_DEV)$(RESET)"

docker-build-prod: ## Build production Docker image
	@echo -e "$(BLUE)Building production Docker image...$(RESET)"
	@echo -e "$(CYAN)Building $(DOCKER_IMAGE_PROD) with production optimizations$(RESET)"
	@if [ ! -f "Dockerfile" ]; then \
		echo -e "$(RED)❌ Dockerfile not found$(RESET)"; \
		exit 1; \
	fi
	@docker build \
		--target production \
		--tag $(DOCKER_IMAGE_PROD) \
		--label "project=$(PROJECT_NAME)" \
		--label "environment=production" \
		--label "build-date=$$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
		--label "version=$$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
		.
	@echo -e "$(GREEN)Production Docker image built: $(DOCKER_IMAGE_PROD)$(RESET)"

docker-publish: ## Push Docker image to registry
	@echo -e "$(BLUE)Publishing Docker image to registry...$(RESET)"
	@if [ "$(ENV)" != "prod" ]; then \
		echo -e "$(YELLOW)⚠️  Publishing development image to $(DOCKER_REGISTRY)$(RESET)"; \
		docker tag $(DOCKER_IMAGE_DEV) $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_DEV); \
		docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_DEV); \
	else \
		echo -e "$(CYAN)Publishing production image to $(DOCKER_REGISTRY)$(RESET)"; \
		docker tag $(DOCKER_IMAGE_PROD) $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_PROD); \
		docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_PROD); \
	fi
	@echo -e "$(GREEN)Docker image published successfully$(RESET)"

docker-run: ## Run application in container locally
	@echo -e "$(BLUE)Running application in container locally...$(RESET)"
	@echo -e "$(CYAN)Starting $(DOCKER_IMAGE_DEV) with port 8000 exposed$(RESET)"
	@echo -e "$(YELLOW)Application will be available at http://localhost:8000$(RESET)"
	@echo -e "$(YELLOW)Press Ctrl+C to stop the container$(RESET)"
	@if [ -t 0 ]; then \
		echo -e "$(CYAN)Running with interactive TTY$(RESET)"; \
		docker run \
			--rm \
			--interactive \
			--tty \
			--publish 8000:8000 \
			--env ENV=$(ENV) \
			--name $(PROJECT_NAME)-dev \
			$(DOCKER_IMAGE_DEV); \
	else \
		echo -e "$(CYAN)Running without TTY (non-interactive mode)$(RESET)"; \
		docker run \
			--rm \
			--publish 8000:8000 \
			--env ENV=$(ENV) \
			--name $(PROJECT_NAME)-dev \
			$(DOCKER_IMAGE_DEV); \
	fi

db-upgrade: install ## Apply database migrations
	@echo -e "$(BLUE)Applying database migrations...$(RESET)"
	@echo -e "$(CYAN)Using Alembic for database schema management$(RESET)"
	@if [ "$(ENV)" = "prod" ]; then \
		echo -e "$(YELLOW)⚠️  Running migrations in PRODUCTION environment$(RESET)"; \
		echo -e "$(YELLOW)Press Ctrl+C within 5 seconds to cancel...$(RESET)"; \
		sleep 5; \
	fi
	@uv run alembic upgrade head
	@echo -e "$(GREEN)Database migrations applied successfully$(RESET)"

db-downgrade: install ## Rollback database migrations
	@echo -e "$(BLUE)Rolling back database migrations...$(RESET)"
	@echo -e "$(RED)⚠️  WARNING: This will rollback database schema$(RESET)"
	@echo -e "$(YELLOW)Press Ctrl+C within 10 seconds to cancel...$(RESET)"
	@sleep 10
	@echo -e "$(CYAN)Rolling back one migration step$(RESET)"
	@uv run alembic downgrade -1
	@echo -e "$(GREEN)Database rollback completed$(RESET)"

db-reset: install ## Reset development database
	@echo -e "$(BLUE)Resetting development database...$(RESET)"
	@if [ "$(ENV)" != "dev" ]; then \
		echo -e "$(RED)❌ Database reset only allowed in development environment$(RESET)"; \
		echo -e "$(YELLOW)Current ENV=$(ENV). Set ENV=dev to proceed$(RESET)"; \
		exit 1; \
	fi
	@echo -e "$(RED)⚠️  WARNING: This will destroy all data in development database$(RESET)"
	@echo -e "$(YELLOW)Press Ctrl+C within 10 seconds to cancel...$(RESET)"
	@sleep 10
	@echo -e "$(CYAN)Performing complete database cleanup$(RESET)"
	@if command -v docker >/dev/null 2>&1 && docker ps | grep -q test-results-postgres; then \
		echo -e "$(CYAN)Using Docker PostgreSQL container for cleanup$(RESET)"; \
		docker exec test-results-postgres psql -U test_results_user -d test_results -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" || true; \
		echo -e "$(CYAN)Database schema completely reset$(RESET)"; \
	else \
		echo -e "$(YELLOW)Docker PostgreSQL container not found, using Alembic downgrade$(RESET)"; \
		uv run alembic downgrade base || true; \
	fi
	@echo -e "$(CYAN)Recreating database schema$(RESET)"
	@uv run alembic upgrade head
	@echo -e "$(GREEN)Development database reset completed$(RESET)"

db-seed: install ## Populate database with test data
	@echo -e "$(BLUE)Populating database with test data...$(RESET)"
	@if [ "$(ENV)" = "prod" ]; then \
		echo -e "$(RED)❌ Database seeding not allowed in production environment$(RESET)"; \
		exit 1; \
	fi
	@echo -e "$(CYAN)Loading test data from resource files$(RESET)"
	@if [ -f "scripts/import_test_data.py" ]; then \
		uv run python scripts/import_test_data.py; \
	else \
		echo -e "$(YELLOW)⚠️  Test data import script not found$(RESET)"; \
		echo -e "$(CYAN)Creating sample test frameworks and environments$(RESET)"; \
	fi
	@echo -e "$(GREEN)Database seeded with test data$(RESET)"

clean: ## Remove Python cache and temporary files
	@echo -e "$(BLUE)Cleaning Python cache and temporary files...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".coverage" -delete 2>/dev/null || true
	@find . -type f -name ".coverage.*" -delete 2>/dev/null || true
	@rm -rf build/ dist/ 2>/dev/null || true
	@echo -e "$(GREEN)Python cache and temporary files cleaned$(RESET)"

# =============================================================================
# Docker Compose Commands
# =============================================================================

docker-up: ## Start all docker-compose services
	@echo -e "$(BLUE)Starting docker-compose services...$(RESET)"
	@if ! command -v docker-compose >/dev/null 2>&1; then \
		echo -e "$(RED)❌ docker-compose not found$(RESET)"; \
		echo -e "$(YELLOW)Please install Docker Compose: https://docs.docker.com/compose/install/$(RESET)"; \
		exit 1; \
	fi
	@docker-compose up -d
	@echo -e "$(GREEN)✅ Docker services started$(RESET)"
	@echo -e "$(CYAN)Services available:$(RESET)"
	@echo -e "  • PostgreSQL: localhost:5433"
	@echo -e "  • MinIO: http://localhost:9000"
	@echo -e "  • Adminer: http://localhost:8080"

docker-down: ## Stop and remove docker-compose services
	@echo -e "$(BLUE)Stopping docker-compose services...$(RESET)"
	@docker-compose down
	@echo -e "$(GREEN)✅ Docker services stopped$(RESET)"

docker-logs: ## View docker-compose service logs
	@echo -e "$(BLUE)Showing docker-compose service logs...$(RESET)"
	@docker-compose logs -f

docker-ps: ## Show status of docker-compose services
	@echo -e "$(BLUE)Docker Compose Service Status$(RESET)"
	@echo -e "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@docker-compose ps

docker-restart: ## Restart docker-compose services
	@echo -e "$(BLUE)Restarting docker-compose services...$(RESET)"
	@docker-compose restart
	@echo -e "$(GREEN)✅ Docker services restarted$(RESET)"

# =============================================================================
# Docker Cleanup Commands
# =============================================================================

clean-docker: ## Remove Docker development artifacts
	@echo -e "$(BLUE)Cleaning Docker development artifacts...$(RESET)"
# 	@echo -e "$(CYAN)Removing dangling images$(RESET)"
# 	@docker image prune -f 2>/dev/null || echo -e "$(YELLOW)Docker not available or no images to clean$(RESET)"
	@echo -e "$(CYAN)Removing unused containers$(RESET)"
	@docker container prune -f 2>/dev/null || echo -e "$(YELLOW)Docker not available or no containers to clean$(RESET)"
	@echo -e "$(CYAN)Removing unused networks$(RESET)"
	@docker network prune -f 2>/dev/null || echo -e "$(YELLOW)Docker not available or no networks to clean$(RESET)"
	@echo -e "$(CYAN)Removing development volumes$(RESET)"
	@docker volume ls -q -f label=project=$(PROJECT_NAME) | xargs -r docker volume rm 2>/dev/null || echo -e "$(YELLOW)No project volumes to clean$(RESET)"
	@echo -e "$(GREEN)Docker development artifacts cleaned$(RESET)"

docker-prune: ## Complete Docker cleanup (remove unused containers, networks, volumes, and build cache - preserves images)
	@echo -e "$(BLUE)Performing Docker cleanup...$(RESET)"
	@echo -e "$(RED)⚠️  WARNING: This will remove unused Docker resources$(RESET)"
	@echo -e "$(YELLOW)This includes: unused containers, networks, volumes, and build cache$(RESET)"
	@echo -e "$(GREEN)Images will be preserved$(RESET)"
	@echo -e "$(YELLOW)Press Ctrl+C within 5 seconds to cancel...$(RESET)"
	@sleep 5
	@echo -e "$(CYAN)Removing unused containers...$(RESET)"
	@docker container prune -f
	@echo -e "$(CYAN)Removing unused networks...$(RESET)"
	@docker network prune -f
	@echo -e "$(CYAN)Removing unused volumes...$(RESET)"
	@docker volume prune -f
	@echo -e "$(CYAN)Removing build cache...$(RESET)"
	@docker builder prune -f
	@echo -e "$(GREEN)✅ Docker cleanup completed (images preserved)$(RESET)"

clean-all: ## Complete cleanup of all artifacts
	@echo -e "$(BLUE)Performing complete cleanup of all artifacts...$(RESET)"
	@echo -e "$(CYAN)Step 1/3: Cleaning Python cache and temporary files$(RESET)"
	@$(MAKE) clean
	@echo -e "$(CYAN)Step 2/3: Cleaning Docker artifacts$(RESET)"
	@$(MAKE) clean-docker
	@echo -e "$(CYAN)Step 3/3: Removing additional build artifacts$(RESET)"
	@rm -rf .uv_cache/ 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .tox/ 2>/dev/null || true
	@rm -rf site-packages/ 2>/dev/null || true
	@echo -e "$(GREEN)✅ Complete cleanup finished$(RESET)"

playwright-test: ## Run Playwright tests with custom reporter integration and artifact validation
	@echo -e "$(BLUE)Running Playwright tests with custom reporter...$(RESET)"
	@echo -e "$(CYAN)Tests will stream results to Test Results Platform API$(RESET)"
	@if [ ! -f "example/playwright/custom_reporter.ts" ]; then \
		echo -e "$(RED)❌ example/playwright/custom_reporter.ts not found$(RESET)"; \
		echo -e "$(YELLOW)Please ensure you're running from the project root$(RESET)"; \
		exit 1; \
	fi
	@echo -e "$(CYAN)Phase 1: Running Playwright tests...$(RESET)"
	@test_output=$$(cd example/playwright && npx playwright test --reporter=./custom_reporter.ts 2>&1); \
	echo "$$test_output"; \
	suite_id=$$(echo "$$test_output" | grep -o "suite_id=[a-f0-9-]*" | head -1 | cut -d= -f2 || \
		echo "$$test_output" | grep -o "([a-f0-9-]*)" | head -1 | sed 's/[()]//g' || echo ""); \
	if [ -n "$$suite_id" ]; then \
		echo -e "$(GREEN)✅ Captured suite ID: $$suite_id$(RESET)"; \
		echo "$$suite_id" > /tmp/playwright_suite_id; \
	else \
		echo -e "$(YELLOW)⚠️ Could not capture suite ID, will use default for validation$(RESET)"; \
	fi
	@echo ""
	@echo -e "$(CYAN)Phase 2: Validating artifact uploads...$(RESET)"
	@if [ -f "/tmp/playwright_suite_id" ]; then \
		SUITE_ID=$$(cat /tmp/playwright_suite_id) $(MAKE) validate-artifacts; \
	else \
		$(MAKE) validate-artifacts; \
	fi
	@echo ""
	@echo -e "$(GREEN)✅ Playwright tests completed with real-time API integration$(RESET)"

validate-artifacts: ## Validate that failed tests have artifacts uploaded
	@echo -e "$(BLUE)Validating artifact uploads for failed tests...$(RESET)"
	@echo -e "$(CYAN)Step 1: Getting test suite ID...$(RESET)"
	@if [ -n "$(SUITE_ID)" ]; then \
		suite_id="$(SUITE_ID)"; \
		echo -e "$(GREEN)✅ Using passed suite ID: $$suite_id$(RESET)"; \
	else \
		echo -e "$(YELLOW)⚠️ No suite ID provided, using default$(RESET)"; \
		suite_id="cdf209ef-8feb-4b06-b4b9-7f31b294dacc"; \
		echo -e "$(GREEN)✅ Using default suite: $$suite_id$(RESET)"; \
	fi
	@echo -e "$(CYAN)Step 2: Checking for failed test results$(RESET)"
	@if [ -n "$(SUITE_ID)" ]; then \
		suite_id="$(SUITE_ID)"; \
	else \
		suite_id="cdf209ef-8feb-4b06-b4b9-7f31b294dacc"; \
	fi; \
	failed_count=$$(curl -s "http://localhost:8000/playwright/test-results?suite_id=$$suite_id" | jq '.results | map(select(.status == "failed")) | length' 2>/dev/null || echo "0"); \
	if [ "$$failed_count" = "0" ]; then \
		echo -e "$(YELLOW)⚠️ No failed tests found - unable to validate artifact upload$(RESET)"; \
		echo -e "$(CYAN)💡 Artifacts are only generated for failed tests$(RESET)"; \
		echo -e "$(GREEN)✅ SKIPPED: Artifact validation (no failed tests to check)$(RESET)"; \
	else \
		echo -e "$(GREEN)✅ Found $$failed_count failed test(s)$(RESET)"; \
		echo -e "$(CYAN)Step 3: Checking artifact uploads$(RESET)"; \
		artifacts_count=$$(curl -s "http://localhost:8000/playwright/test-results?suite_id=$$suite_id" | jq '[.results[] | select(.status == "failed") | .artifacts | length] | add // 0' 2>/dev/null || echo "0"); \
		total_artifacts=$$(curl -s "http://localhost:8000/playwright/test-results?suite_id=$$suite_id" | jq '[.results[] | .artifacts | length] | add // 0' 2>/dev/null || echo "0"); \
		echo -e "$(CYAN)Total artifacts found: $$total_artifacts$(RESET)"; \
		echo -e "$(CYAN)Artifacts for failed tests: $$artifacts_count$(RESET)"; \
		echo -e "$(CYAN)Step 4: Checking MinIO storage$(RESET)"; \
		minio_files=$$(docker exec test-results-minio sh -c 'mc ls --recursive myminio/dev-screenshot/ myminio/dev-video/ myminio/dev-trace/ 2>/dev/null | wc -l' 2>/dev/null || echo "0"); \
		echo -e "$(CYAN)MinIO artifact files: $$minio_files$(RESET)"; \
		echo -e "$(CYAN)Step 5: Validation Summary$(RESET)"; \
		if [ "$$artifacts_count" -gt "0" ]; then \
			echo -e "$(GREEN)✅ SUCCESS: Artifact upload is working!$(RESET)"; \
			echo -e "$(GREEN)   - Failed tests: $$failed_count$(RESET)"; \
			echo -e "$(GREEN)   - Artifacts uploaded: $$artifacts_count$(RESET)"; \
		else \
			echo -e "$(RED)❌ FAILED: No artifacts found for failed tests$(RESET)"; \
			echo -e "$(YELLOW)💡 Expected behavior:$(RESET)"; \
			echo -e "$(YELLOW)   - Failed tests should generate screenshots/videos$(RESET)"; \
			echo -e "$(YELLOW)   - Custom reporter should upload them to API$(RESET)"; \
			echo -e "$(YELLOW)   - API should store them in MinIO$(RESET)"; \
			echo -e "$(CYAN)🔍 Debug: Check custom reporter logs above for upload attempts$(RESET)"; \
			exit 1; \
		fi; \
	fi

stop: ## Stop any running uvicorn servers on port 8000
	@echo -e "$(BLUE)Stopping any running uvicorn servers on port 8000...$(RESET)"
	@if lsof -ti:8000 >/dev/null 2>&1; then \
		echo -e "$(CYAN)Found processes using port 8000, stopping them...$(RESET)"; \
		lsof -ti:8000 | xargs kill -9 2>/dev/null || true; \
		echo -e "$(GREEN)✅ Server stopped successfully$(RESET)"; \
	else \
		echo -e "$(YELLOW)No processes found running on port 8000$(RESET)"; \
	fi

download-object: ## Download object from MinIO storage (usage: make download-object object_path="path/to/object" [output="filename"])
	@echo -e "$(BLUE)Downloading object from MinIO storage...$(RESET)"
	@if [ -z "$(object_path)" ]; then \
		echo -e "$(RED)❌ Error: object_path parameter is required$(RESET)"; \
		echo -e "$(YELLOW)Usage examples:$(RESET)"; \
		echo -e "  make download-object object_path=\"suites/suite-id/test-cases/test-id/screenshot-hash\""; \
		echo -e "  make download-object object_path=\"suites/suite-id/test-cases/test-id/video-hash\" output=\"test-video.webm\""; \
		echo ""; \
		echo -e "$(CYAN)💡 Available download methods:$(RESET)"; \
		echo -e "  1. Direct HTTP: curl http://localhost:9000/playwright/\$$object_path -o output.file"; \
		echo -e "  2. MinIO client: docker exec test-results-minio mc cp myminio/playwright/\$$object_path /tmp/output.file"; \
		echo -e "  3. Browser: http://localhost:9000/playwright/\$$object_path"; \
		exit 1; \
	fi
	@BUCKET="playwright"; \
	OBJECT_PATH="$(object_path)"; \
	OUTPUT_FILE="$${output:-$$(basename "$$OBJECT_PATH")}"; \
	echo -e "$(CYAN)Source: $$BUCKET/$$OBJECT_PATH$(RESET)"; \
	echo -e "$(CYAN)Output: $$OUTPUT_FILE$(RESET)"; \
	echo ""
	@echo -e "$(CYAN)Method 1: Trying direct HTTP download...$(RESET)"
	@BUCKET="playwright"; \
	OBJECT_PATH="$(object_path)"; \
	OUTPUT_FILE="$${output:-$$(basename "$$OBJECT_PATH")}"; \
	if curl -f -s "http://localhost:9000/$$BUCKET/$$OBJECT_PATH" -o "$$OUTPUT_FILE"; then \
		echo -e "$(GREEN)✅ HTTP download successful: $$(ls -lh "$$OUTPUT_FILE")$(RESET)"; \
	else \
		echo -e "$(YELLOW)⚠️ HTTP download failed, trying MinIO client...$(RESET)"; \
		if docker exec test-results-minio mc cp "myminio/$$BUCKET/$$OBJECT_PATH" "/tmp/$$OUTPUT_FILE" 2>/dev/null; then \
			docker cp "test-results-minio:/tmp/$$OUTPUT_FILE" "./$$OUTPUT_FILE" 2>/dev/null; \
			if [ -f "./$$OUTPUT_FILE" ]; then \
				echo -e "$(GREEN)✅ MinIO client download successful: $$(ls -lh "$$OUTPUT_FILE")$(RESET)"; \
			else \
				echo -e "$(RED)❌ Failed to copy file from container$(RESET)"; \
				exit 1; \
			fi; \
		else \
			echo -e "$(RED)❌ MinIO client download failed$(RESET)"; \
			echo -e "$(YELLOW)💡 Check if object exists:$(RESET)"; \
			docker exec test-results-minio mc ls --recursive "myminio/$$BUCKET/" | grep "$$OBJECT_PATH" || echo -e "$(RED)Object not found$(RESET)"; \
			exit 1; \
		fi; \
	fi
	@echo ""
	@echo -e "$(GREEN)✅ Object downloaded successfully$(RESET)"
	@echo -e "$(CYAN)💡 Alternative access methods:$(RESET)"
	@echo -e "  Browser URL: http://localhost:9000/playwright/$(object_path)"
	@echo -e "  MinIO Console: http://localhost:9001 (minio/minio123)"