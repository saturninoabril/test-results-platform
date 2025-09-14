# Test Results Management API - Documentation

## Overview

Welcome to the comprehensive documentation for the Test Results Management API. This REST API provides centralized storage, management, and reporting capabilities for test execution results from end-to-end testing frameworks like Playwright and Cypress.

## Quick Links

### 📚 Core Documentation
- **[API Reference](api-reference.md)** - Complete REST API documentation with examples
- **[Library Documentation](library-documentation.md)** - Detailed library and SDK documentation
- **[Deployment Guide](deployment-guide.md)** - Production deployment instructions

### 🚀 Getting Started
- **[Quick Start](#quick-start)** - Get running in 5 minutes
- **[GitHub Actions Integration](github-actions-integration.md)** - CI/CD workflow examples
- **[Authentication Guide](automation-tokens.md)** - Token management and OAuth setup

### 🛠️ Support & Troubleshooting
- **[Troubleshooting Guide](troubleshooting.md)** - Diagnose and fix common issues
- **[FAQ](faq.md)** - Frequently asked questions and answers

## Quick Start

### 1. Local Development Setup

**Prerequisites:**
- Docker and Docker Compose
- Python 3.13+
- Git

**Get started:**
```bash
# Clone the repository
git clone https://github.com/your-org/test-results-api
cd test-results-api

# Start services with Docker Compose
docker-compose up -d

# Initialize database
uv run alembic upgrade head

# Create your first authentication token
uv run python -m src.cli.auth generate-token \
  --name "Development Token" \
  --scope write \
  --expires-days 30

# Test the API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/v1/frameworks
```

### 2. Import Your First Test Results

```bash
# Install CLI tools
uv sync
uv pip install -e .

# Import Playwright results
test-results-cli import playwright-results.json --format playwright

# Import Cypress results
test-results-cli import cypress-results.json --format cypress

# View imported data
test-results-cli results list --recent 10
test-results-cli suites list --status completed
```

### 3. GitHub Actions Integration

**Add to your repository secrets:**
- `TEST_RESULTS_TOKEN`: Your automation token
- `TEST_RESULTS_API_ENDPOINT`: Your API endpoint URL

**Create workflow (.github/workflows/e2e-tests.yml):**
```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  playwright-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Run Playwright Tests
        run: |
          npm ci
          npx playwright install
          npx playwright test --reporter=json --output-dir=test-results

      - name: Submit Test Results
        if: always()
        uses: your-org/submit-test-results@v1
        with:
          api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
          automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
          results-path: test-results/results.json
          artifacts-path: test-results/
```

## Key Features

### 🎯 Framework Support
- **Playwright**: Screenshots, videos, traces, test results
- **Cypress**: Videos, screenshots, test results, Dashboard integration
- **Generic JSON**: Custom testing frameworks
- **JUnit XML**: Legacy test result formats
- **Extensible**: Easy to add new frameworks

### 🔐 Authentication & Security
- **JWT Tokens**: Secure API access with configurable expiration
- **GitHub OAuth**: Seamless login integration
- **Automation Tokens**: Long-lived tokens for CI/CD systems
- **Scoped Permissions**: Read, write, and admin access levels
- **Token Management**: Revocation, rotation, and audit logging

### ☁️ Scalable Storage
- **S3 Compatible**: AWS S3, MinIO, Google Cloud Storage
- **Artifact Management**: Automatic compression and cleanup
- **CDN Support**: Fast artifact delivery globally
- **Backup & Restore**: Comprehensive data protection

### 📊 Comprehensive Reporting
- **Historical Trends**: Track test performance over time
- **Flaky Test Detection**: Identify unreliable tests automatically
- **Cross-Browser Analysis**: Compare results across environments
- **Custom Tags**: Organize and filter tests your way

### 🚀 CI/CD Ready
- **GitHub Actions**: Pre-built workflows and actions
- **Matrix Builds**: Multi-browser, multi-environment support
- **Retry Logic**: Handle flaky infrastructure gracefully
- **Parallel Execution**: Scale test submission efficiently

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub Actions│───▶│   FastAPI App    │───▶│   PostgreSQL    │
│   CI/CD Pipeline│    │   (Python 3.13) │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   S3 Storage    │
                       │   (Artifacts)   │
                       └─────────────────┘

┌─────────────────┐    ┌──────────────────┐
│   CLI Tools     │───▶│   Libraries      │
│   Management    │    │   (Auth, Storage)│
└─────────────────┘    └──────────────────┘
```

**Core Components:**
- **REST API**: FastAPI-based HTTP service with OpenAPI documentation
- **Database**: PostgreSQL 17 with async SQLAlchemy for data persistence
- **Storage**: S3-compatible blob storage for test artifacts
- **Authentication**: JWT tokens with GitHub OAuth integration
- **CLI Tools**: Comprehensive command-line interface for management
- **Libraries**: Modular Python libraries for each feature area

## Data Model

### Core Entities

**TestFramework**
```json
{
  "id": "playwright-1.55.0",
  "name": "Playwright",
  "version": "1.55.0",
  "metadata": {
    "supports_parallel": true,
    "artifact_types": ["screenshot", "video", "trace"]
  }
}
```

**TestEnvironment**
```json
{
  "id": "chrome-ubuntu-ci",
  "name": "Chrome on Ubuntu (CI)",
  "browser": "chromium",
  "os": "ubuntu-latest",
  "metadata": {
    "headless": true,
    "viewport": "1280x720"
  }
}
```

**TestSuite**
```json
{
  "id": "suite-123",
  "name": "Login Flow Tests",
  "framework_id": "playwright-1.55.0",
  "environment_id": "chrome-ubuntu-ci",
  "status": "completed",
  "total_tests": 15,
  "passed": 13,
  "failed": 2,
  "duration_ms": 45000
}
```

**TestResult**
```json
{
  "id": "result-456",
  "suite_id": "suite-123",
  "full_title": "Login Flow › Valid Credentials › should login successfully",
  "status": "passed",
  "duration_ms": 1500,
  "tags": ["auth", "smoke", "critical"],
  "retry_count": 0
}
```

**TestArtifact**
```json
{
  "id": "artifact-789",
  "result_id": "result-456",
  "name": "login-screenshot.png",
  "type": "screenshot",
  "content_type": "image/png",
  "size": 156789,
  "storage_path": "artifacts/2024/01/15/login-screenshot.png"
}
```

## Common Use Cases

### 1. Centralized Test Reporting
Replace scattered test results across CI runs with a unified dashboard:

```bash
# Import results from multiple sources
test-results-cli import playwright-results.json --suite-name "E2E Tests - PR #123"
test-results-cli import cypress-results.json --suite-name "Component Tests - PR #123"

# Generate unified report
test-results-cli reports generate --format html --output pr-123-report.html
```

### 2. Flaky Test Management
Identify and track unreliable tests across your test suite:

```bash
# Find flaky tests
test-results-cli results analyze-flaky --days 30 --min-failures 5

# Mark known flaky tests
test-results-cli results tag --test-id "login-test-001" --add "flaky:networking"

# Generate flaky test report
test-results-cli reports flaky --format csv --output flaky-tests.csv
```

### 3. Cross-Environment Analysis
Compare test behavior across different browsers and environments:

```bash
# Compare results across environments
test-results-cli results compare \
  --environment chrome-ci \
  --environment firefox-ci \
  --environment safari-ci \
  --since 7d

# Generate comparison report
test-results-cli reports comparison \
  --environments chrome-ci,firefox-ci,safari-ci \
  --format html
```

### 4. Historical Performance Tracking
Monitor test suite performance and identify regressions:

```bash
# Track performance trends
test-results-cli analytics performance \
  --suite-pattern "E2E Tests*" \
  --timerange 30d \
  --group-by date

# Alert on performance regressions
test-results-cli analytics alerts \
  --threshold-increase 50% \
  --notification mattermost \
  --webhook-url $MATTERMOST_WEBHOOK
```

## CLI Command Reference

### Authentication Commands
```bash
# User login (GitHub OAuth)
test-results-cli auth login

# Generate automation token
test-results-cli auth generate-token --name "CI Token" --scope write --expires-days 365

# List tokens
test-results-cli auth list-tokens

# Revoke token
test-results-cli auth revoke-token --token-id auto_abc123

# Validate token
test-results-cli auth validate-token --token YOUR_TOKEN
```

### Data Management Commands
```bash
# Import test results
test-results-cli import results.json --format playwright
test-results-cli import results.xml --format junit

# Export test results
test-results-cli export --format csv --output results.csv --since 30d
test-results-cli export --format json --suite-id suite-123

# List and filter data
test-results-cli results list --status failed --tags "smoke,critical"
test-results-cli suites list --framework playwright --since 7d

# Validate data integrity
test-results-cli validate --check-artifacts --fix-missing
```

### Storage Management Commands
```bash
# Check storage health
test-results-cli storage health

# Monitor usage
test-results-cli storage usage --breakdown-by type
test-results-cli storage monitor --duration 60

# Cleanup operations
test-results-cli storage cleanup --older-than 90d --dry-run
test-results-cli storage optimize --compress-videos --resize-images

# Backup and restore
test-results-cli storage backup --output backup-2024-01-15.tar.gz
test-results-cli storage restore --input backup-2024-01-15.tar.gz
```

## API Client Libraries

### JavaScript/TypeScript
```bash
npm install @testresults/js-sdk
```

```javascript
import { TestResultsClient } from '@testresults/js-sdk';

const client = new TestResultsClient({
  endpoint: 'https://api.testresults.dev/v1',
  token: process.env.TEST_RESULTS_TOKEN
});

// Create test suite
const suite = await client.suites.create({
  name: 'E2E Tests',
  framework_id: 'playwright-1.55.0',
  environment_id: 'chrome-ci'
});

// Submit test results
await client.results.createBatch([
  {
    suite_id: suite.id,
    external_id: 'test-login',
    status: 'passed',
    duration_ms: 1500
  },
  {
    suite_id: suite.id,
    external_id: 'test-logout',
    status: 'failed',
    duration_ms: 2100,
    error_message: 'Logout button not found'
  }
]);
```

### Python
```bash
pip install testresults-python-sdk
```

```python
from testresults import TestResultsClient

client = TestResultsClient(
    endpoint='https://api.testresults.dev/v1',
    token=os.getenv('TEST_RESULTS_TOKEN')
)

# Upload artifact with test result
with open('screenshot.png', 'rb') as f:
    artifact = client.artifacts.upload(
        result_id=result.id,
        name='failure-screenshot.png',
        type='screenshot',
        file=f
    )

# Query historical data
results = client.results.list(
    suite_id=suite.id,
    status='failed',
    tags=['critical'],
    limit=50
)
```

## Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Fork the repository** and create a feature branch
2. **Write tests** for any new functionality (TDD approach)
3. **Follow code style** guidelines (ruff, mypy)
4. **Update documentation** for API changes
5. **Submit a pull request** with clear description

### Development Setup
```bash
# Clone and setup development environment
git clone https://github.com/your-org/test-results-api
cd test-results-api

# Install dependencies
uv sync --dev

# Setup pre-commit hooks
pre-commit install

# Run tests
pytest

# Start development server
uvicorn src.main:app --reload
```

## Support & Community

- **📖 Documentation**: Comprehensive guides and API reference
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/your-org/test-results-api/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/your-org/test-results-api/discussions)
- **📧 Email**: support@testresults.dev
- **💼 Enterprise**: enterprise@testresults.dev

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

---

**Ready to get started?** Follow our [Quick Start](#quick-start) guide or dive into the [API Reference](api-reference.md) for detailed integration instructions.