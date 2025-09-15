# GitHub Actions CI/CD Setup

This directory contains the GitHub Actions workflows for the Test Results Management Platform. The CI/CD pipeline provides comprehensive quality assurance, testing, and deployment automation.

## 🚀 Workflows Overview

### [`ci.yml`](workflows/ci.yml) - Continuous Integration
**Triggers**: Pull requests and pushes to `main` and `release/*` branches

**Jobs**:
- **Lint and Format**: Code style checking with `ruff`
- **Type Check**: Static type analysis with `mypy`
- **Unit Tests**: Fast tests with coverage reporting
- **Integration Tests**: Full database and storage tests
- **Contract Tests**: API contract validation
- **Build Check**: Package building and validation

**Services**: PostgreSQL 17, MinIO (S3-compatible storage)

### [`release.yml`](workflows/release.yml) - Release and Deployment
**Triggers**: Pushes to `main`, version tags (`v*`), and releases

**Jobs**:
- **Full Test Suite**: Comprehensive testing with all checks
- **Build and Publish**: Docker image building and GitHub Packages publishing
- **Deploy Staging**: Automatic deployment to staging environment (main branch)
- **Deploy Production**: Automatic deployment to production (version tags)
- **Security Scan**: Container vulnerability scanning with Trivy

**Features**:
- Automated Docker image building and publishing to GitHub Container Registry
- Build attestations for supply chain security
- Environment-based deployments with approval gates

### [`code-quality.yml`](workflows/code-quality.yml) - Code Quality Analysis
**Triggers**: PRs, pushes to main, weekly schedule (Sundays)

**Analysis**:
- **Complexity Analysis**: Cyclomatic complexity and maintainability metrics
- **Security Scanning**: Bandit security linter and Safety vulnerability checks
- **Dead Code Detection**: Unused code identification with Vulture
- **Test Coverage**: Detailed coverage reports with quality gates (80% threshold)

**Reports**: Comprehensive quality metrics with PR comments and artifacts

### [`dependency-update.yml`](workflows/dependency-update.yml) - Dependency Management
**Triggers**: Weekly schedule (Mondays), manual dispatch

**Process**:
- Automated dependency updates using `uv lock --upgrade`
- Smoke testing with updated dependencies
- Automatic PR creation with detailed change summaries
- Proper labeling and branch management

### [`status-check.yml`](workflows/status-check.yml) - PR Status Management
**Triggers**: PR events, workflow completions

**Features**:
- Automatic PR status comments with comprehensive summaries
- Conventional commit format validation
- PR size analysis and recommendations
- Real-time workflow status updates

### [`maintenance.yml`](workflows/maintenance.yml) - Repository Maintenance
**Triggers**: Daily schedule, manual dispatch

**Tasks**:
- Stale issue and PR management with configurable timelines
- Automated workflow run cleanup (30-day retention)
- Repository health maintenance

## 🔧 Configuration

### Environment Variables
```yaml
PYTHON_VERSION: "3.13"           # Python version for all workflows
REGISTRY: ghcr.io               # Container registry
IMAGE_NAME: ${{ github.repository }}  # Docker image name
```

### Required Secrets
- `GITHUB_TOKEN`: Automatically provided (repository access)
- Environment-specific secrets for deployments (configure in Settings → Environments)

### Service Configuration
All workflows use consistent service configurations:
- **PostgreSQL**: Version 17 with health checks
- **MinIO**: Latest with S3-compatible API
- **Test Database**: `test_results` with `test_results_user`

## 📊 Quality Standards

### Code Quality Gates
- **Test Coverage**: Minimum 80% required
- **Linting**: All `ruff` rules must pass
- **Type Checking**: Full `mypy` compliance
- **Security**: No high-severity vulnerabilities
- **Complexity**: Cyclomatic complexity monitoring

### PR Requirements
- All CI checks must pass
- Code coverage maintained or improved
- Conventional commit message format recommended
- Security scan clearance for dependencies

## 🏷️ Branch Strategy

### Protected Branches
- **`main`**: Primary branch with full CI/CD pipeline
- **`release/*`**: Release branches with production deployments

### Workflow Behavior
- **Pull Requests**: Full CI suite with quality reports
- **Main Branch**: Full testing + staging deployment
- **Release Tags**: Full testing + production deployment
- **Scheduled**: Maintenance and dependency updates

## 🚦 Status Checks

### Required Status Checks (Recommended)
Configure these as required status checks in branch protection:
- `Lint and Format`
- `Type Check`
- `Unit Tests`
- `Integration Tests`
- `Contract Tests`
- `Build Check`

### Quality Reports
- PR status comments with metrics and recommendations
- Coverage reports uploaded as artifacts
- Security scan results in GitHub Security tab
- Code quality metrics in workflow summaries

## 🔐 Security Features

### Supply Chain Security
- **Build Attestations**: Cryptographic proof of build provenance
- **Container Scanning**: Trivy vulnerability scanner
- **Dependency Scanning**: Safety and Bandit security checks
- **SARIF Upload**: Security results in GitHub Security tab

### Access Control
- Workflows use minimal required permissions
- Environment-based deployment approval gates
- Secure secret management for deployment credentials

## 📈 Monitoring and Observability

### Metrics Collection
- Test coverage trends over time
- Build duration and success rates
- Security vulnerability trends
- Code quality metrics

### Notifications
- PR status updates and quality reports
- Deployment status notifications
- Security alert integration
- Dependency update notifications

## 🛠️ Maintenance

### Regular Tasks
- **Weekly**: Dependency updates and quality reports
- **Daily**: Stale issue/PR management and cleanup
- **Per PR**: Full quality analysis and status updates
- **Per Release**: Complete testing and security scans

### Troubleshooting
- Check workflow logs for detailed error information
- Verify service health and database connectivity
- Review artifact uploads for detailed reports
- Monitor resource usage and workflow duration

## 🔧 Local Development

To run the same checks locally:
```bash
# Code quality
make lint          # Linting
make format        # Code formatting
make type-check    # Type checking

# Testing
make test-unit     # Unit tests
make test-integration  # Integration tests (requires services)
make test-contract     # Contract tests
make test-all          # Complete test suite

# Building
make build         # Package building
make build-check   # Build validation
```

## 📚 Best Practices

### Workflow Design
- ✅ Use specific action versions (not `@latest`)
- ✅ Include health checks for services
- ✅ Set appropriate timeouts and retries
- ✅ Use caching for dependencies when beneficial
- ✅ Implement proper error handling and cleanup

### Security
- ✅ Use minimal required permissions
- ✅ Pin action versions to specific commits
- ✅ Validate inputs and sanitize outputs
- ✅ Use GitHub's built-in security features
- ✅ Regular security dependency updates

### Performance
- ✅ Parallel job execution where possible
- ✅ Efficient artifact and report uploading
- ✅ Appropriate workflow triggers and conditions
- ✅ Resource optimization and cleanup

---

*This documentation is maintained alongside the workflow files. Please update both when making changes to the CI/CD pipeline.*