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
DATABASE_URL ?= postgresql://postgres:postgres@localhost:5432/test_results_$(ENV)

# .PHONY declarations for all targets
.PHONY: help check-requirements install upgrade dev dev-https dev-certs dev-certs-force dev-certs-trust dev-https-setup type-check lint format test-unit test-integration test-contract test-all
.PHONY: build build-dev build-check docker-build docker-build-prod docker-publish docker-run
.PHONY: db-upgrade db-downgrade db-reset db-seed clean clean-docker clean-all

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
	@echo -e "$(GREEN)Utility Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(clean.*|help)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
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
		uv run python -c "from src.models.test_framework import TestFramework; from src.models.test_environment import TestEnvironment; print('Sample data creation would go here')"; \
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

clean-docker: ## Remove Docker development artifacts
	@echo -e "$(BLUE)Cleaning Docker development artifacts...$(RESET)"
	@echo -e "$(CYAN)Removing dangling images$(RESET)"
	@docker image prune -f 2>/dev/null || echo -e "$(YELLOW)Docker not available or no images to clean$(RESET)"
	@echo -e "$(CYAN)Removing unused containers$(RESET)"
	@docker container prune -f 2>/dev/null || echo -e "$(YELLOW)Docker not available or no containers to clean$(RESET)"
	@echo -e "$(CYAN)Removing unused networks$(RESET)"
	@docker network prune -f 2>/dev/null || echo -e "$(YELLOW)Docker not available or no networks to clean$(RESET)"
	@echo -e "$(CYAN)Removing development volumes$(RESET)"
	@docker volume ls -q -f label=project=$(PROJECT_NAME) | xargs -r docker volume rm 2>/dev/null || echo -e "$(YELLOW)No project volumes to clean$(RESET)"
	@echo -e "$(GREEN)Docker development artifacts cleaned$(RESET)"

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