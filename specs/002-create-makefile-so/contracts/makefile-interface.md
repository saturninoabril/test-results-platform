# Makefile Interface Contract

## Target Interface Specifications

### Development Commands

#### `make install`
**Purpose**: Install development dependencies
**Dependencies**: None
**Environment**: Development
**Success Criteria**:
- Exit code 0
- All dependencies from `pyproject.toml` installed
- Virtual environment activated
- Output: "Dependencies installed successfully"

#### `make upgrade`
**Purpose**: Upgrade all dependencies to latest versions
**Dependencies**: None
**Environment**: Development
**Success Criteria**:
- Exit code 0
- `uv.lock` updated with new versions
- Virtual environment updated
- Output: Summary of upgraded packages

#### `make dev`
**Purpose**: Start development server with hot reload
**Dependencies**: `install`, `db-upgrade`
**Environment**: Development
**Success Criteria**:
- Exit code 0 (long-running process)
- FastAPI server running on configured port
- Auto-reload enabled
- Output: Server startup messages

### Quality Assurance Commands

#### `make type-check`
**Purpose**: Validate Python type annotations
**Dependencies**: `install`
**Environment**: Any
**Success Criteria**:
- Exit code 0 if no type errors
- Exit code 1 if type errors found
- Output: Type checking results with file/line references

#### `make lint`
**Purpose**: Run code linting
**Dependencies**: `install`
**Environment**: Any
**Success Criteria**:
- Exit code 0 if no lint errors
- Exit code 1 if lint errors found
- Output: Linting results with specific violations

#### `make format`
**Purpose**: Format code according to project standards
**Dependencies**: `install`
**Environment**: Development
**Success Criteria**:
- Exit code 0
- Source files formatted in-place
- Output: List of modified files

#### `make test-unit`
**Purpose**: Run unit tests only
**Dependencies**: `install`
**Environment**: Testing
**Success Criteria**:
- Exit code 0 if all tests pass
- Exit code 1 if any tests fail
- Output: Test results with coverage report

#### `make test-integration`
**Purpose**: Run integration tests with real dependencies
**Dependencies**: `install`, `db-upgrade`, `docker-build`
**Environment**: Testing
**Success Criteria**:
- Exit code 0 if all tests pass
- Exit code 1 if any tests fail
- Output: Test results with timing information

#### `make test-contract`
**Purpose**: Run API contract validation tests
**Dependencies**: `build`
**Environment**: Testing
**Success Criteria**:
- Exit code 0 if contracts valid
- Exit code 1 if contract violations
- Output: Contract validation results

#### `make test-all`
**Purpose**: Run complete test suite
**Dependencies**: `test-unit`, `test-integration`, `test-contract`
**Environment**: Testing
**Success Criteria**:
- Exit code 0 if all test suites pass
- Exit code 1 if any test suite fails
- Output: Comprehensive test report

### Build Commands

#### `make build`
**Purpose**: Create production-ready artifacts
**Dependencies**: `type-check`, `lint`, `test-all`
**Environment**: Build
**Success Criteria**:
- Exit code 0
- Production artifacts in `dist/` directory
- Build validation passed
- Output: Build summary with artifact locations

#### `make build-dev`
**Purpose**: Create development build
**Dependencies**: `install`, `type-check`
**Environment**: Development
**Success Criteria**:
- Exit code 0
- Development artifacts created
- Debug symbols included
- Output: Development build summary

#### `make build-check`
**Purpose**: Validate build artifacts
**Dependencies**: `build`
**Environment**: Build
**Success Criteria**:
- Exit code 0 if artifacts valid
- Exit code 1 if validation fails
- Output: Validation results with checks performed

### Container Commands

#### `make docker-build`
**Purpose**: Build development Docker image
**Dependencies**: `install`
**Environment**: Development
**Success Criteria**:
- Exit code 0
- Docker image created with development tag
- Image size within reasonable limits
- Output: Image build summary with tag

#### `make docker-build-prod`
**Purpose**: Build production Docker image
**Dependencies**: `build`
**Environment**: Production
**Success Criteria**:
- Exit code 0
- Optimized production image created
- Multi-stage build completed
- Output: Production image details

#### `make docker-publish`
**Purpose**: Push Docker image to registry
**Dependencies**: `docker-build-prod`, `test-all`
**Environment**: CI/CD
**Success Criteria**:
- Exit code 0
- Image pushed to configured registry
- Proper tagging applied
- Output: Registry push confirmation

#### `make docker-run`
**Purpose**: Run application in container locally
**Dependencies**: `docker-build`
**Environment**: Development
**Success Criteria**:
- Exit code 0 (long-running process)
- Container running with port mapping
- Application accessible
- Output: Container startup information

### Database Commands

#### `make db-upgrade`
**Purpose**: Apply database migrations
**Dependencies**: `install`
**Environment**: Development/Production
**Success Criteria**:
- Exit code 0
- All pending migrations applied
- Database schema up to date
- Output: Migration execution summary

#### `make db-downgrade`
**Purpose**: Rollback database migrations
**Dependencies**: `install`
**Environment**: Development
**Success Criteria**:
- Exit code 0
- Specified migrations rolled back
- Database schema reverted
- Output: Rollback confirmation

#### `make db-reset`
**Purpose**: Reset development database
**Dependencies**: `install`
**Environment**: Development only
**Success Criteria**:
- Exit code 0
- Database dropped and recreated
- Fresh schema applied
- Output: Reset confirmation

#### `make db-seed`
**Purpose**: Populate database with test data
**Dependencies**: `db-upgrade`
**Environment**: Development
**Success Criteria**:
- Exit code 0
- Test data loaded successfully
- Referential integrity maintained
- Output: Data loading summary

### Utility Commands

#### `make clean`
**Purpose**: Remove Python cache and temporary files
**Dependencies**: None
**Environment**: Any
**Success Criteria**:
- Exit code 0
- Cache directories removed
- Temporary files cleaned
- Output: Cleanup summary

#### `make clean-docker`
**Purpose**: Remove Docker development artifacts
**Dependencies**: None
**Environment**: Development
**Success Criteria**:
- Exit code 0
- Development containers stopped/removed
- Unused images pruned
- Output: Docker cleanup summary

#### `make clean-all`
**Purpose**: Complete cleanup of all artifacts
**Dependencies**: None
**Environment**: Development
**Success Criteria**:
- Exit code 0
- All cache, build, and container artifacts removed
- Virtual environment preserved
- Output: Complete cleanup summary

#### `make help`
**Purpose**: Display available commands with descriptions
**Dependencies**: None
**Environment**: Any
**Success Criteria**:
- Exit code 0
- Categorized list of all targets
- Brief description for each target
- Usage examples provided

## Global Interface Requirements

### Environment Variable Support
- `ENV`: Environment type (dev/test/prod)
- `VERBOSE`: Enable verbose output (0/1)
- `CI`: CI/CD environment detection (true/false)

### Error Handling Contract
- All commands MUST return appropriate exit codes
- Error messages MUST go to stderr
- Success messages MUST go to stdout
- Long-running processes MUST handle SIGINT gracefully

### Parallel Execution Support
- Commands MUST be safe for parallel execution where applicable
- File locking MUST be used for shared resources
- Dependencies MUST be properly declared

### Cross-Platform Compatibility
- Commands MUST work on Linux, macOS, and Windows (WSL)
- Shell commands MUST be POSIX-compatible
- File paths MUST use forward slashes or variables

---

**Contract Version**: 1.0
**Last Updated**: 2025-09-14
**Status**: Draft - Ready for implementation