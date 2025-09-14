# AI Agent Guidelines

This document defines guidelines for AI agents working on the Test Results Management API project.

## Project Context

**Primary Focus**: Test Results Management API for centralizing E2E test results from Playwright, Cypress, and other testing frameworks.

**Tech Stack**:
- **Backend**: Python 3.13+ with FastAPI
- **Database**: PostgreSQL 17 with async SQLAlchemy
- **Storage**: S3-compatible (MinIO dev, AWS S3 prod)
- **Authentication**: JWT with GitHub OAuth
- **Notifications**: Mattermost webhooks
- **Testing**: pytest with real dependencies (no mocks)

## Development Principles

### 1. Test-Driven Development (TDD)
- Write tests first, ensure they fail before implementation
- Use real dependencies (PostgreSQL, MinIO) in tests
- No mocking of core services - integration tests are preferred
- Test pyramid: unit → integration → contract tests

### 2. Library-First Architecture
- Every feature must be implemented as a standalone library in `src/lib/`
- Services in `src/services/` orchestrate libraries
- API endpoints are thin wrappers around services
- CLI tools consume the same libraries as the API

### 3. Code Quality Standards
- **No comments** unless explicitly requested
- Follow existing code patterns and conventions
- Use structured logging with contextual information
- Implement proper error handling with specific exception types
- Performance target: <200ms p95, 1000 req/s capacity

## File Organization

```
src/
├── api/             # FastAPI route handlers (thin)
├── cli/             # Command-line interfaces
├── lib/             # Core libraries (business logic)
├── models/          # SQLAlchemy data models
└── services/        # Service orchestration layer

tests/
├── contract/        # API contract tests
├── integration/     # Cross-component tests
└── unit/           # Library unit tests
```

## Key Implementation Guidelines

### Database Operations
- Use async SQLAlchemy with proper session management
- Implement database migrations with Alembic
- Handle connection pooling and timeouts
- Use UUIDs for primary keys

### Storage Operations
- Abstract S3 operations behind consistent interface
- Support both MinIO (dev) and AWS S3 (prod)
- Implement proper error handling for network failures
- Handle large file uploads efficiently

### Authentication & Authorization
- JWT tokens for API access
- GitHub OAuth for user authentication
- Automation tokens for CI/CD systems
- Scoped permissions (read, write, delete)

### Notifications
- Mattermost webhook integration for key events
- Configurable notification types and thresholds
- Graceful degradation when notifications fail
- Rich message formatting with context

## Testing Requirements

### Test Data
- Use realistic test data from `resource/` directory
- Playwright results: 23 tests across 4 projects
- Cypress results: 8 accessibility tests
- Follow real-world test result patterns

### Test Environment
- Docker Compose for local development
- Real PostgreSQL database (not SQLite)
- Real MinIO instance for storage tests
- GitHub Actions for CI/CD integration

### Test Coverage
- Focus on critical paths and edge cases
- Test error conditions and recovery
- Validate data integrity and constraints
- Performance testing for key endpoints

## Common Patterns

### Error Handling
```python
try:
    result = await service.operation()
    logger.info("Operation completed", result_id=result.id)
    return result
except ServiceValidationError as e:
    logger.warning("Validation failed", error=str(e))
    raise HTTPException(status_code=422, detail=str(e))
except ServiceNotFoundError as e:
    logger.warning("Resource not found", error=str(e))
    raise HTTPException(status_code=404, detail=str(e))
except Exception as e:
    logger.error("Operation failed", error=str(e))
    raise HTTPException(status_code=500, detail="Internal server error")
```

### Configuration Management
- Use Pydantic Settings with environment variables
- Prefix environment variables by component (e.g., `MATTERMOST_`)
- Provide sensible defaults for development
- Document all configuration options in `.env.example`

### Logging Standards
- Use structured logging with contextual fields
- Log at appropriate levels (debug, info, warning, error)
- Include relevant IDs and context in log messages
- Never log sensitive information (tokens, passwords)

## Integration Points

### CI/CD Integration
- GitHub Actions workflows for automated testing
- Bearer token authentication for automation
- Matrix builds for multiple environments
- Artifact upload integration

### Framework Support
- Playwright 1.55.0+ with screenshots, videos, traces
- Cypress 7.2.0+ with videos, screenshots, dashboard
- Generic JSON format for custom frameworks
- JUnit XML for legacy systems

## Performance Considerations

- Database connection pooling
- Async operations throughout
- Efficient bulk operations
- S3 signed URLs for direct artifact access
- Response caching where appropriate

## Security Requirements

- Never commit secrets to repository
- Use environment variables for sensitive config
- Validate all input data
- Implement rate limiting
- Secure artifact access with signed URLs
- Audit logging for sensitive operations

## Documentation Standards

- Update API documentation when adding endpoints
- Include realistic examples in OpenAPI schemas
- Document configuration options
- Provide integration examples for common frameworks
- Keep README.md updated with quick start instructions

## Contributing Guidelines

### Open Source Contribution Process

This is an open source project welcoming contributions from the community. Follow these guidelines to ensure smooth collaboration:

#### Getting Started
1. **Fork the repository** to your GitHub account
2. **Clone your fork** locally: `git clone https://github.com/YOUR_USERNAME/testresults-platform.git`
3. **Set up development environment** using Docker Compose: `docker-compose up -d`
4. **Install dependencies**: `uv sync --dev`
5. **Run tests** to ensure everything works: `pytest`

#### Development Workflow
1. **Create a feature branch** from `main`: `git checkout -b feature/your-feature-name`
2. **Follow TDD approach**: Write tests first, then implementation
3. **Make small, focused commits** with clear messages
4. **Run full test suite** before pushing: `pytest && ruff check && mypy src/`
5. **Push to your fork** and create a pull request

#### Code Standards
- **Follow existing patterns** - Study the codebase before adding new patterns
- **Write tests first** - All new features must have comprehensive tests
- **No mocking** - Use real dependencies (PostgreSQL, MinIO) in tests
- **Document public APIs** - Include docstrings and type hints
- **Performance matters** - Consider impact on <200ms p95 target

#### Pull Request Requirements
- **Descriptive title** - Clearly explain what the PR does
- **Link to issue** - Reference related GitHub issues
- **Test coverage** - Include unit, integration, and contract tests
- **Documentation updates** - Update relevant docs and examples
- **Changelog entry** - Add entry to CHANGELOG.md for user-facing changes

#### Commit Message Format
```
type(scope): brief description

Longer explanation if needed

- Bullet points for multiple changes
- Reference issues: Fixes #123, Closes #456
```

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

#### Code Review Process
1. **Automated checks** must pass (tests, linting, type checking)
2. **Manual review** by maintainers focusing on:
   - Code quality and maintainability
   - Test coverage and quality
   - Documentation completeness
   - Performance implications
3. **Address feedback** promptly and professionally
4. **Squash commits** if requested before merge

#### Issue Guidelines
- **Search existing issues** before creating new ones
- **Use issue templates** when available
- **Provide context** - include environment details, error messages, steps to reproduce
- **Label appropriately** - bug, enhancement, documentation, etc.
- **Be respectful** - maintain professional communication

#### Community Standards
- **Be inclusive** - Welcome contributors of all backgrounds and skill levels
- **Be patient** - Help newcomers learn the project patterns
- **Be constructive** - Provide actionable feedback in reviews
- **Follow CoC** - Adhere to our Code of Conduct (see CODE_OF_CONDUCT.md)

#### Testing Philosophy
This project emphasizes **real-world testing** with actual dependencies:
- Use PostgreSQL database, not SQLite or mocks
- Test against real MinIO/S3 storage
- Include realistic test data from Playwright/Cypress runs
- Focus on integration scenarios over isolated unit tests
- Performance test critical paths

#### Documentation Standards
- **README.md** - Keep quick start guide current
- **API docs** - Auto-generated from OpenAPI schemas
- **Examples** - Include working code samples
- **Architecture docs** - Explain design decisions
- **Changelog** - Document all user-facing changes

#### Release Process
1. **Semantic versioning** - MAJOR.MINOR.PATCH
2. **Release notes** - Highlight features, fixes, breaking changes
3. **Migration guides** - Help users upgrade between versions
4. **Docker images** - Publish to container registries
5. **Package releases** - Publish SDKs to package managers

#### Getting Help
- **Discussions** - Use GitHub Discussions for questions
- **Issues** - Report bugs and request features
- **Documentation** - Comprehensive guides in `/docs`

#### Maintainer Responsibilities
- **Timely reviews** - Respond to PRs within 48 hours
- **Clear feedback** - Provide actionable suggestions
- **Consistent standards** - Apply guidelines fairly
- **Community building** - Foster welcoming environment
- **Release management** - Regular, stable releases

This project emphasizes real-world usage patterns, robust error handling, and comprehensive testing. Focus on building production-ready features that integrate seamlessly with existing CI/CD pipelines.

**Welcome to the community! Your contributions help make E2E testing better for everyone.** 🚀