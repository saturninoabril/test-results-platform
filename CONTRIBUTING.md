# Contributing to Test Results Management Platform

Thank you for contributing to the Test Results Management Platform! This document provides guidelines for contributing to the project.

## 🔒 Security First

**Important**: Before contributing, please review our [Security Policy](.github/SECURITY.md) to understand:
- How to report security vulnerabilities responsibly
- Security best practices for code contributions
- CI/CD security measures and fork safety

### Fork Contributions
External contributors should note:
- **Fork-Safe CI**: Basic checks run automatically on your PR
- **Full CI**: Requires maintainer approval for security (normal process)
- **No Secrets**: Your fork cannot access repository secrets (this is intentional)

## 🚀 Quick Start

1. **Fork and clone** the repository
2. **Set up development environment**: `make install`
3. **Run tests locally**: `make test-all`
4. **Create a feature branch**: `git checkout -b feature/your-feature`
5. **Make your changes** following our guidelines below
6. **Test your changes**: Run quality checks and tests
7. **Submit a pull request**

## 🔍 Quality Standards

### Code Quality Checks
Before submitting a PR, ensure all local checks pass:

```bash
# Code formatting and linting
make format        # Auto-format code
make lint          # Check code style
make type-check    # Static type analysis

# Testing
make test-unit           # Fast unit tests
make test-integration    # Full integration tests (requires services)
make test-contract       # API contract tests
make test-all           # Complete test suite

# Build validation
make build-dev     # Development build
make build-check   # Validate build artifacts
```

### Required Standards
- ✅ **Test Coverage**: Maintain >80% coverage
- ✅ **Type Safety**: All code must pass `mypy` type checking
- ✅ **Code Style**: Follow `ruff` formatting and linting rules
- ✅ **Security**: Pass security scans (Bandit, Safety)
- ✅ **Documentation**: Update docs for new features

## 📋 Pull Request Guidelines

### PR Title Format
Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
feat(api): add bulk test result submission endpoint
fix(database): resolve migration conflict with enum types
docs(readme): update installation instructions
chore(deps): update pytest to latest version
```

**Types:**
- `feat` - New features
- `fix` - Bug fixes
- `docs` - Documentation updates
- `style` - Code formatting (not affecting functionality)
- `refactor` - Code refactoring
- `test` - Adding or updating tests
- `chore` - Maintenance tasks
- `ci` - CI/CD changes
- `perf` - Performance improvements

### PR Description Template
```markdown
## 🎯 Purpose
Brief description of what this PR accomplishes.

## 🔄 Changes
- List key changes made
- Include any breaking changes
- Note new dependencies or configuration

## 🧪 Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing performed
- [ ] Documentation updated

## 📋 Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] Breaking changes documented
```

### PR Size Guidelines
- **Small PR** (< 200 lines): ✅ Preferred - easy to review
- **Medium PR** (200-500 lines): ⚠️ Acceptable with good description
- **Large PR** (> 500 lines): ⚠️ Consider breaking into smaller PRs

## 🤖 Automated Checks

When you submit a PR, the following automated checks run:

### CI Pipeline (`ci.yml`)
1. **Lint and Format**: Code style validation
2. **Type Check**: Static type analysis
3. **Unit Tests**: Fast tests with coverage
4. **Integration Tests**: Full database/storage tests
5. **Contract Tests**: API validation
6. **Build Check**: Package building verification

### Code Quality (`code-quality.yml`)
- Complexity analysis and maintainability metrics
- Security scanning for vulnerabilities
- Dead code detection
- Test coverage reporting with quality gates

### Status Checks (`status-check.yml`)
- PR status summary with metrics
- Conventional commit validation
- PR size analysis and recommendations

## 🏗️ Development Setup

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker and Docker Compose (for integration tests)

### Local Environment
```bash
# Install dependencies
make install

# Start local services (PostgreSQL, MinIO)
docker-compose up -d postgres minio

# Run database migrations
make db-upgrade

# Seed test data
make db-seed

# Start development server
make dev  # HTTP on :8000
# or
make dev-https  # HTTPS on :8443
```

### Running Tests
```bash
# Quick unit tests
make test-unit

# Full test suite (requires services)
make test-all

# Specific test categories
make test-integration
make test-contract

# With coverage reporting
uv run pytest tests/unit/ --cov=src --cov-report=html
```

## 🔧 Project Structure

```
src/
├── models/          # SQLAlchemy database models
├── services/        # Business logic libraries
├── cli/            # Command-line interfaces
└── lib/            # Shared utilities (auth, database, storage)

tests/
├── unit/           # Fast isolated tests
├── integration/    # Database/storage integration tests
└── contract/       # API contract validation tests

.github/
└── workflows/      # CI/CD automation
```

## 🎯 Development Workflow

### Feature Development
1. Create feature branch from `main`
2. Implement feature with tests
3. Run local quality checks
4. Submit PR against `main`
5. Address review feedback
6. Merge after approval and CI passes

### Bug Fixes
1. Create bugfix branch from `main`
2. Write failing test that reproduces bug
3. Implement fix
4. Verify test passes
5. Submit PR with clear description

### Breaking Changes
- Clearly document in PR description
- Update migration guides if needed
- Consider deprecation warnings for APIs
- Coordinate with team on release timing

## 🚦 Branch Strategy

### Protected Branches
- **`main`**: Primary development branch
  - Requires PR review and status checks
  - Automatically deploys to staging
  - All changes via pull request

- **`release/*`**: Release preparation branches
  - Feature freeze and bug fixes only
  - Production deployments from tags

### Workflow
1. **Feature branches** → **`main`** (via PR)
2. **`main`** → **Staging deployment** (automatic)
3. **Release tags** → **Production deployment** (automatic)

## 🔒 Security Guidelines

### Code Security
- Never commit secrets or credentials
- Use environment variables for configuration
- Follow secure coding practices
- Address security scan findings promptly

### Dependencies
- Keep dependencies updated (automated weekly)
- Review security advisories
- Use `uv run safety check` for vulnerability scanning
- Pin versions in production builds

## 📊 Quality Metrics

### Coverage Targets
- **Minimum**: 80% overall coverage
- **Goal**: 90%+ for critical paths
- **New code**: Should maintain or improve coverage

### Performance Standards
- API response times: <200ms p95
- Database queries: Optimize for <10ms typical
- Memory usage: Monitor for leaks in long-running processes

## 🛠️ Troubleshooting

### Common Issues

**Tests failing locally:**
```bash
# Reset database
make db-reset

# Restart services
docker-compose restart

# Clear Python cache
make clean
```

**Type check errors:**
```bash
# Install missing type stubs
uv add types-requests types-pyyaml

# Check specific file
uv run mypy src/specific_file.py
```

**Import errors:**
```bash
# Ensure proper installation
uv sync --extra dev

# Check Python path
uv run python -c "import sys; print(sys.path)"
```

## 💬 Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **PR Reviews**: Code feedback and guidance
- **Documentation**: Check `.github/README.md` for CI/CD details

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

Thank you for contributing! 🚀

*This document is updated regularly. Please check for the latest version when contributing.*