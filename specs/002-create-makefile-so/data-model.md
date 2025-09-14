# Data Model: Makefile Structure and Target Organization

## Overview
Since this feature involves creating a Makefile rather than traditional data entities, this document describes the structural organization of Makefile targets, their dependencies, and the command execution model.

## Target Categories (Conceptual Entities)

### 1. Development Commands
**Purpose**: Support local development workflows
**Attributes**:
- Target name (e.g., `dev`, `test-unit`, `type-check`)
- Dependencies (other targets or files)
- Environment requirements
- Output/side effects

**Key Targets**:
- `dev` - Start development server
- `dev-debug` - Development with debugging
- `install` - Install development dependencies
- `upgrade` - Upgrade dependencies

### 2. Quality Assurance Commands
**Purpose**: Code quality validation and testing
**Attributes**:
- Validation type (type-check, lint, test)
- Scope (unit, integration, all)
- Configuration files
- Exit behavior

**Key Targets**:
- `type-check` - Run type validation
- `lint` - Code linting
- `format` - Code formatting
- `test-unit` - Unit tests only
- `test-integration` - Integration tests
- `test-contract` - Contract validation
- `test-all` - Complete test suite

### 3. Build Commands
**Purpose**: Create deployable artifacts
**Attributes**:
- Build type (development, production)
- Output location
- Dependencies (source files, tests)
- Validation requirements

**Key Targets**:
- `build` - Production build
- `build-dev` - Development build
- `build-check` - Validate build artifacts

### 4. Container Commands
**Purpose**: Docker container management
**Attributes**:
- Image type (dev, prod, test)
- Registry information
- Tag strategy
- Push/pull behavior

**Key Targets**:
- `docker-build` - Build development image
- `docker-build-prod` - Build production image
- `docker-publish` - Push to registry
- `docker-run` - Run container locally

### 5. Database Commands
**Purpose**: Database operations and migrations
**Attributes**:
- Migration direction (up/down)
- Environment target
- Data seeding requirements
- Connection parameters

**Key Targets**:
- `db-upgrade` - Run migrations
- `db-downgrade` - Rollback migrations
- `db-reset` - Reset development database
- `db-seed` - Populate test data

### 6. Utility Commands
**Purpose**: Maintenance and cleanup operations
**Attributes**:
- Cleanup scope (cache, containers, all)
- Safety checks
- Confirmation requirements
- Restoration capability

**Key Targets**:
- `clean` - Remove cache files
- `clean-docker` - Clean container artifacts
- `clean-all` - Complete cleanup
- `help` - Show available commands

## Target Dependencies and Relationships

### Dependency Graph
```
test-all
├── test-contract (depends on: build)
├── test-integration (depends on: db-upgrade, docker-build)
└── test-unit (depends on: install)

build
├── type-check (depends on: install)
├── lint (depends on: install)
└── format-check (depends on: install)

docker-publish
└── docker-build-prod (depends on: build, test-all)

dev
├── install
└── db-upgrade
```

### Validation Rules
1. **Prerequisites**: All quality checks must pass before build
2. **Testing Order**: Contract → Integration → Unit → End-to-End
3. **Build Gates**: Type check + lint must pass before build
4. **Publishing Gates**: All tests + build must pass before container publishing
5. **Database Safety**: Backup/confirmation for destructive operations

## State Management

### File-Based State
**Cache Files**: `.pytest_cache/`, `__pycache__/`, `.mypy_cache/`
**Lock Files**: `uv.lock`, `docker-compose.override.yml`
**Build Artifacts**: `dist/`, `build/`, container images

### Environment State
**Development**: Local database, hot-reload servers, debug flags
**Testing**: Isolated test database, test containers, mock services
**Production**: Optimized builds, production database, release artifacts

### Dependency State
**Installed Packages**: Virtual environment, system dependencies
**Container Images**: Development images, production images, base images
**Database Schema**: Migration versions, seed data status

## Command Interface Model

### Input Parameters
- **Environment Variables**: `ENV`, `DEBUG`, `DATABASE_URL`
- **Command Arguments**: Target names, options (`make test-unit VERBOSE=1`)
- **Configuration Files**: `Makefile`, `.env`, `pyproject.toml`

### Output Formats
- **Success**: Exit code 0, structured output for automation
- **Failure**: Exit code 1+, error messages to stderr
- **Progress**: Human-readable status messages
- **Logs**: Structured logging for CI/CD parsing

### Error Handling Model
**Fail Fast**: Commands stop on first error by default
**Cleanup**: Temporary resources cleaned on failure
**Recovery**: Clear error messages with suggested fixes
**Idempotency**: Safe to re-run commands after failures

## Integration Points

### External Tools
- **uv**: Package management and virtual environments
- **Docker**: Container building and running
- **pytest**: Test execution and reporting
- **PostgreSQL**: Database operations and migrations
- **Git**: Version control integration for CI/CD

### CI/CD Integration
- **Environment Detection**: Automatic CI/CD behavior adjustments
- **Artifact Generation**: Build outputs for deployment pipelines
- **Status Reporting**: Machine-readable success/failure indicators
- **Caching**: Integration with CI/CD caching systems

---

**Note**: This data model describes the structural organization of Makefile targets and their relationships, serving as the foundation for contract definition and implementation planning.