# Frequently Asked Questions (FAQ)

## General Questions

### What is the Test Results Management API?

The Test Results Management API is a comprehensive REST API designed for managing test execution results from end-to-end testing frameworks like Playwright and Cypress. It provides centralized storage, management, and reporting capabilities for test data with built-in CI/CD integration support.

**Key features:**
- Store test results from multiple frameworks (Playwright, Cypress, custom)
- Upload and manage test artifacts (screenshots, videos, traces, reports)
- GitHub Actions integration with reusable workflows
- JWT-based authentication with automation tokens
- S3-compatible storage for scalable artifact management
- Comprehensive CLI tools for data management
- Real-time reporting and analytics

### Why use this API instead of framework-built-in reporting?

**Centralization**: Instead of having test results scattered across different CI runs, pull requests, and local machines, the API provides a single source of truth for all test execution data.

**Cross-framework compatibility**: Compare results between Playwright, Cypress, and other testing frameworks in a unified interface.

**Historical tracking**: Keep long-term history of test performance, flakiness trends, and failure patterns that individual CI runs don't preserve.

**Team collaboration**: Share test results and artifacts easily across team members with proper access control.

**Advanced analytics**: Get insights into test suite performance, identify bottlenecks, and track improvements over time.

### What testing frameworks are supported?

**Currently supported:**
- **Playwright** (v1.0+): Full integration with test results, screenshots, videos, and traces
- **Cypress** (v6.0+): Complete support including Dashboard integration
- **pytest** (v6.0+): Basic test result integration
- **Jest** (v24.0+): Test results and coverage reports
- **Generic JSON**: Any testing framework that can output structured JSON

**Upcoming support:**
- Selenium WebDriver
- TestNG
- JUnit
- Custom framework adapters

The API is designed to be framework-agnostic, so adding new frameworks requires minimal configuration.

### How much does it cost?

The Test Results Management API is open-source and free to use. You can:

- **Self-host**: Deploy on your own infrastructure (AWS, Google Cloud, Azure, on-premises)
- **Use managed services**: Deploy using standard cloud services (RDS for database, S3 for storage)
- **Scale as needed**: Pay only for the cloud resources you use

**Typical monthly costs for a team of 10 developers:**
- Database (RDS PostgreSQL): $20-50/month
- Storage (S3): $5-20/month depending on artifact volume
- Compute (EC2/containers): $30-100/month depending on usage
- **Total: $55-170/month** for unlimited test results

## Technical Questions

### What are the system requirements?

**Minimum requirements:**
- Python 3.13+
- PostgreSQL 17+
- 2GB RAM
- 10GB storage for basic usage
- S3-compatible storage (AWS S3, MinIO, etc.)

**Recommended for production:**
- 4+ CPU cores
- 8GB+ RAM
- PostgreSQL with 100GB+ storage
- Dedicated S3 bucket with lifecycle policies
- Redis for caching (optional but recommended)
- Load balancer for high availability

**Development requirements:**
- Docker and Docker Compose
- 4GB RAM
- 20GB local storage

### How does authentication work?

The API uses **JWT (JSON Web Tokens)** with two authentication methods:

**1. User Authentication (GitHub OAuth):**
```bash
# Interactive login flow
test-results-cli auth login
# Opens browser for GitHub OAuth, creates short-lived token (24 hours)
```

**2. Automation Tokens (for CI/CD):**
```bash
# Long-lived tokens for automated systems
test-results-cli auth generate-token \
  --name "GitHub Actions - MyRepo" \
  --scope write \
  --expires-days 365
```

**Token scopes:**
- `read`: View test results and artifacts
- `write`: Create/update test results, upload artifacts
- `admin`: Manage tokens, delete data, system administration

**Security features:**
- Tokens can be revoked individually
- Configurable expiration (1 day to 2 years)
- Audit logging for token usage
- Rate limiting per token

### How do I integrate with GitHub Actions?

**Quick setup using our reusable workflows:**

1. **Add secrets to your repository:**
```
Settings > Secrets and variables > Actions
- TEST_RESULTS_TOKEN: your-automation-token
- TEST_RESULTS_API_ENDPOINT: https://your-api-domain.com/v1
```

2. **Create workflow file (.github/workflows/tests.yml):**
```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  playwright-tests:
    uses: your-org/test-results-workflows/.github/workflows/playwright-tests.yml@v1
    with:
      browsers: '["chromium", "firefox", "webkit"]'
      test-command: 'npm run test:e2e'
    secrets:
      api-token: ${{ secrets.TEST_RESULTS_TOKEN }}
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
```

3. **For custom workflows:**
```yaml
- name: Submit Test Results
  if: always()
  uses: your-org/submit-test-results@v1
  with:
    api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
    automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
    results-path: test-results.json
    artifacts-path: test-results/
```

**Benefits:**
- Automatic test result submission
- Artifact upload (screenshots, videos, traces)
- Matrix build support (multiple browsers/environments)
- Retry logic for flaky uploads
- Integration with existing workflows

### What file formats are supported for test results?

**Input formats:**
- **Playwright JSON**: Native playwright test results format
- **Cypress JSON**: Native cypress test results and mochawesome reports
- **JUnit XML**: Standard JUnit test report format
- **Generic JSON**: Custom structured format
- **pytest JSON**: pytest-json-report output
- **Jest JSON**: Jest test results format

**Example import:**
```bash
# Auto-detect format
test-results-cli import test-results.json

# Specify format explicitly
test-results-cli import --format playwright results.json
test-results-cli import --format cypress cypress-results.json
test-results-cli import --format junit junit-results.xml
```

**Output formats:**
- **JSON**: Full structured data
- **CSV**: Tabular data for spreadsheet analysis
- **JUnit XML**: For CI integration
- **HTML**: Human-readable reports

### How large can test artifacts be?

**File size limits:**
- Single artifact: 100MB (configurable up to 1GB)
- Total artifacts per test result: 500MB
- API request timeout: 10 minutes for uploads

**Supported artifact types:**
- **Images**: PNG, JPEG, WebP, GIF (screenshots, diagrams)
- **Videos**: MP4, WebM, AVI (test recordings)
- **Documents**: PDF, HTML, TXT (reports, logs)
- **Archives**: ZIP, TAR.GZ (trace files, test bundles)
- **Custom**: Any binary or text file type

**Storage optimization:**
```bash
# Automatic compression for large files
test-results-cli storage optimize --compress-videos --resize-images

# Cleanup old artifacts
test-results-cli storage cleanup --older-than 90d --dry-run
test-results-cli storage cleanup --older-than 90d
```

**Best practices:**
- Compress videos before upload (use H.264 with CRF 28)
- Optimize images (use WebP format when possible)
- Archive multiple small files into ZIP
- Set up S3 lifecycle policies for automatic cleanup

### Can I run this on-premises?

Yes! The API is designed for flexible deployment:

**Docker Compose (simplest):**
```bash
# Clone repository
git clone https://github.com/your-org/test-results-api
cd test-results-api

# Configure environment
cp .env.example .env.prod
# Edit .env.prod with your settings

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

**Kubernetes:**
```bash
# Deploy to existing cluster
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

**Requirements for on-premises:**
- PostgreSQL database server
- S3-compatible storage (MinIO works great on-premises)
- SSL certificate for HTTPS
- Backup strategy for data persistence

**Benefits:**
- Full control over data and infrastructure
- Compliance with data residency requirements
- No external dependencies or API limits
- Customizable for specific enterprise needs

## Usage Questions

### How do I get started quickly?

**1. Development setup (5 minutes):**
```bash
# Clone and start services
git clone https://github.com/your-org/test-results-api
cd test-results-api
docker-compose up -d

# Initialize database
uv run alembic upgrade head

# Create your first token
uv run python -m src.cli.auth generate-token \
  --name "Development Token" \
  --scope write
```

**2. Import existing test results:**
```bash
# Import Playwright results
test-results-cli import playwright-results.json --format playwright

# Import Cypress results
test-results-cli import cypress-results.json --format cypress

# View imported data
test-results-cli results list --recent 10
```

**3. Integrate with your tests:**
```javascript
// JavaScript/Node.js example
const { TestResultsClient } = require('@testresults/js-sdk');

const client = new TestResultsClient({
  endpoint: 'http://localhost:8000/v1',
  token: process.env.TEST_RESULTS_TOKEN
});

// Create test suite
const suite = await client.suites.create({
  name: 'Login Tests',
  framework_id: 'playwright-1.55.0',
  environment_id: 'chrome-local'
});

// Submit test result
await client.results.create({
  suite_id: suite.id,
  external_id: 'test-login-success',
  status: 'passed',
  duration_ms: 1500
});
```

### What's the best way to organize test results?

**Recommended hierarchy:**
```
Repository/Project
├── Test Suites (by feature or CI run)
│   ├── Test Results (individual tests)
│   │   ├── Test Artifacts (screenshots, videos)
│   │   └── Metadata (tags, timing, environment)
│   └── Summary (pass/fail counts, duration)
└── Environments (browser, OS, CI vs local)
```

**Naming conventions:**
- **Suites**: `{Feature} - {Environment} - {Date}` (e.g., "Login Flow - Chrome CI - 2024-01-15")
- **Results**: Use full test titles including describe blocks (e.g., "Login › Valid Credentials › should login with correct username")
- **Artifacts**: `{test-id}-{artifact-type}.{ext}` (e.g., "login-001-screenshot.png")

**Tagging strategy:**
```python
# Use tags for categorization and filtering
tags = [
    "feature:auth",      # Feature area
    "type:smoke",        # Test type (smoke, regression, integration)
    "priority:critical", # Business priority
    "browser:chrome",    # Test environment
    "flaky:false"        # Known test stability
]
```

**Environment management:**
```bash
# Create environments for different contexts
test-results-cli environments create \
  --id chrome-ci \
  --name "Chrome (GitHub Actions)" \
  --browser chromium \
  --os ubuntu-latest

test-results-cli environments create \
  --id firefox-local \
  --name "Firefox (Local Development)" \
  --browser firefox \
  --os macOS
```

### How do I handle flaky tests?

The API provides several tools for identifying and managing flaky tests:

**1. Flaky test detection:**
```bash
# Find tests that have failed multiple times recently
test-results-cli results analyze-flaky --days 7 --min-failures 3

# Get detailed flakiness report
test-results-cli results flakiness-report --format html --output flaky-tests.html
```

**2. Mark tests as known flaky:**
```python
# Tag flaky tests for special handling
await client.results.create({
    'suite_id': suite.id,
    'external_id': 'test-intermittent-feature',
    'status': 'failed',
    'tags': ['flaky:true', 'tracking:issue-123'],
    'metadata': {
        'flaky_reason': 'Network timing dependent',
        'github_issue': 'https://github.com/org/repo/issues/123'
    }
})
```

**3. Retry and stability tracking:**
```python
# Track retry attempts
result = TestResult(
    external_id='test-flaky-login',
    status='passed',  # Final status after retries
    retry_count=2,    # Number of retries needed
    metadata={
        'retry_history': [
            {'attempt': 1, 'status': 'failed', 'duration_ms': 1200},
            {'attempt': 2, 'status': 'failed', 'duration_ms': 1100},
            {'attempt': 3, 'status': 'passed', 'duration_ms': 1050}
        ]
    }
)
```

**4. Automated flaky test management:**
```yaml
# GitHub Actions workflow for flaky test handling
- name: Handle Flaky Tests
  if: failure()
  run: |
    # Mark failed tests as potentially flaky
    test-results-cli results mark-flaky \
      --suite-id ${{ steps.run-tests.outputs.suite_id }} \
      --threshold 3 \
      --days 7

    # Create GitHub issue for new flaky tests
    test-results-cli results create-flaky-issues \
      --github-token ${{ secrets.GITHUB_TOKEN }} \
      --repository ${{ github.repository }}
```

### How do I backup and restore data?

**Database backup:**
```bash
# Create backup
test-results-cli db backup --output backup-2024-01-15.sql

# Automated daily backups
crontab -e
0 2 * * * test-results-cli db backup --output /backups/testresults-$(date +%Y%m%d).sql

# Upload backup to S3
test-results-cli db backup --output - | aws s3 cp - s3://backups/db/testresults-$(date +%Y%m%d).sql
```

**Storage backup:**
```bash
# Backup all artifacts
test-results-cli storage backup --output artifacts-backup-2024-01-15.tar.gz

# Backup specific time range
test-results-cli storage backup \
  --since 2024-01-01 \
  --until 2024-01-31 \
  --output january-2024-artifacts.tar.gz

# Verify backup integrity
test-results-cli storage verify-backup artifacts-backup-2024-01-15.tar.gz
```

**Restore procedures:**
```bash
# Restore database (creates new database)
test-results-cli db restore --input backup-2024-01-15.sql --target-db testresults_restored

# Restore artifacts
test-results-cli storage restore --input artifacts-backup-2024-01-15.tar.gz --target-prefix restored/

# Point-in-time recovery
test-results-cli db restore \
  --backup backup-2024-01-15.sql \
  --replay-logs /var/log/postgres/pg_wal/ \
  --target-time "2024-01-15 14:30:00"
```

**Disaster recovery strategy:**
1. **Daily database backups** to S3 with 30-day retention
2. **Weekly full artifact backups** with 90-day retention
3. **Continuous WAL archiving** for point-in-time recovery
4. **Cross-region replication** for critical production data
5. **Regular restore testing** to verify backup integrity

## Performance Questions

### How fast is the API?

**Performance targets:**
- **Response time**: <200ms p95 for read operations
- **Throughput**: 1000+ requests/second with proper hardware
- **Upload speed**: 10MB/s for artifacts (depends on network/storage)
- **Concurrent users**: 100+ simultaneous users

**Real-world benchmarks:**
```bash
# API endpoint performance
ab -n 10000 -c 100 http://localhost:8000/v1/frameworks
# Result: ~2000 req/sec on 4-core machine

# Database query performance
test-results-cli db benchmark --queries 1000 --concurrent 10
# Result: 50-100ms average for complex queries

# Storage operations
test-results-cli storage benchmark --files 100 --size 1MB
# Result: 5-15MB/s upload speed (depends on storage backend)
```

**Performance optimization:**
- Enable PostgreSQL query caching and connection pooling
- Use Redis for frequently accessed data
- Implement CDN for artifact downloads
- Configure appropriate database indexes
- Use async/await patterns throughout the codebase

### How much storage space do I need?

**Storage estimates per test result:**
- **Test metadata**: ~1KB per test result
- **Screenshots**: 50-500KB each (depends on resolution)
- **Videos**: 1-10MB per test (depends on duration/quality)
- **Trace files**: 500KB-5MB each (Playwright traces)
- **Log files**: 10-100KB each

**Example calculations:**
```
Small team (1000 tests/day):
- Test data: 1000 × 1KB = 1MB/day
- Screenshots (50% of tests): 500 × 200KB = 100MB/day
- Videos (10% of tests): 100 × 2MB = 200MB/day
- Total: ~300MB/day → 9GB/month → 100GB/year

Large team (10,000 tests/day):
- Test data: 10,000 × 1KB = 10MB/day
- Screenshots (50% of tests): 5,000 × 200KB = 1GB/day
- Videos (10% of tests): 1,000 × 2MB = 2GB/day
- Total: ~3GB/day → 90GB/month → 1TB/year
```

**Storage optimization strategies:**
```bash
# Automatic cleanup of old artifacts
test-results-cli storage cleanup --older-than 90d

# Compress large files
test-results-cli storage optimize --compress-videos --quality medium

# Set up S3 lifecycle policies
{
  "Rules": [{
    "Status": "Enabled",
    "Transitions": [
      {
        "Days": 30,
        "StorageClass": "STANDARD_IA"
      },
      {
        "Days": 90,
        "StorageClass": "GLACIER"
      }
    ],
    "Expiration": {
      "Days": 365
    }
  }]
}
```

### Can it handle high volume test suites?

**Scalability features:**
- **Horizontal scaling**: Deploy multiple API instances behind load balancer
- **Database optimization**: Connection pooling, read replicas, partitioning
- **Storage scalability**: S3 handles unlimited artifacts automatically
- **Async processing**: Background jobs for heavy operations
- **Caching**: Redis for frequently accessed data

**High-volume configurations:**
```python
# Database connection pooling
DATABASE_POOL_SIZE = 50
DATABASE_MAX_OVERFLOW = 100
DATABASE_POOL_TIMEOUT = 30

# API worker scaling
UVICORN_WORKERS = 8
MAX_REQUESTS_PER_SECOND = 5000

# Caching configuration
REDIS_URL = "redis://localhost:6379"
CACHE_TTL_SECONDS = 300
```

**Performance under load:**
- **10,000 tests/hour**: Single instance with database tuning
- **50,000 tests/hour**: 3-4 API instances with load balancer
- **100,000+ tests/hour**: Auto-scaling cluster with read replicas

**Enterprise features:**
- Database partitioning by date for massive historical data
- Async artifact processing with queue systems
- Multi-region deployment for global teams
- Advanced monitoring and alerting

## Troubleshooting Questions

### The API is returning 500 errors, what do I check?

**Step 1: Check health endpoints**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed
```

**Step 2: Review logs**
```bash
# Docker logs
docker logs test-results-api --tail 50

# System logs
journalctl -u test-results-api --since "1 hour ago"

# Application logs
tail -f /var/log/test-results-api/app.log
```

**Step 3: Test individual components**
```bash
# Database connectivity
test-results-cli db status

# Storage connectivity
test-results-cli storage health

# Authentication
test-results-cli auth validate-token --token YOUR_TOKEN
```

**Common causes and solutions:**

**Database connection issues:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection manually
psql -h localhost -U testresults -d testresults -c "SELECT version();"

# Fix connection string
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/testresults"
```

**Storage permission issues:**
```bash
# Test S3 access
aws s3 ls s3://your-bucket-name/

# Check MinIO connectivity
mc ls minio/your-bucket-name/

# Verify environment variables
echo $STORAGE_ACCESS_KEY | head -c 10  # Should show first 10 chars
```

### My GitHub Actions workflow is failing, what's wrong?

**Check the workflow logs:**
```yaml
- name: Debug Environment
  run: |
    echo "API Endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}"
    echo "Token configured: ${{ secrets.TEST_RESULTS_TOKEN != '' }}"
    curl -I ${{ vars.TEST_RESULTS_API_ENDPOINT }}/health
```

**Common issues:**

**1. Token not configured:**
```
Error: Invalid or missing token
Solution: Add TEST_RESULTS_TOKEN to GitHub repository secrets
```

**2. API endpoint unreachable:**
```
Error: Could not resolve host
Solution: Check TEST_RESULTS_API_ENDPOINT variable is correct
```

**3. Artifact paths wrong:**
```
Error: File not found: test-results.json
Solution: Verify test output directory and file names

# Debug file paths
- name: Debug Files
  run: |
    find . -name "*.json" -type f
    ls -la test-results/
```

**4. Upload timeout:**
```
Error: Upload timeout after 300 seconds
Solution: Compress large files or increase timeout

- name: Compress Videos
  run: |
    find test-results -name "*.webm" -exec ffmpeg -i {} -c:v libx264 -crf 28 {}.mp4 \; -delete
```

### How do I migrate from another test reporting system?

**Common migration scenarios:**

**From Allure:**
```bash
# Convert Allure results to API format
test-results-cli import --format allure \
  --input-dir allure-results/ \
  --framework-id custom-allure \
  --environment-id ci-environment
```

**From TestRail:**
```bash
# Export TestRail data and import
test-results-cli import --format testrail \
  --input testrail-export.xml \
  --framework-id testrail \
  --map-users testrail-users.json
```

**From Jenkins Test Results:**
```bash
# Import JUnit XML files
test-results-cli import --format junit \
  --input-dir jenkins-test-results/ \
  --framework-id jenkins-junit \
  --environment-id jenkins-ci
```

**Migration strategy:**
1. **Parallel running**: Keep existing system while testing new API
2. **Historical import**: Import 3-6 months of historical data
3. **User training**: Provide team training on new workflows
4. **Gradual rollout**: Migrate projects one by one
5. **Data validation**: Compare results between systems during transition

**Data mapping:**
```python
# Custom mapping for complex migrations
migration_config = {
    'field_mappings': {
        'test_name': 'full_title',
        'result': 'status',
        'execution_time': 'duration_ms'
    },
    'value_mappings': {
        'status': {
            'PASS': 'passed',
            'FAIL': 'failed',
            'SKIP': 'skipped'
        }
    },
    'default_values': {
        'framework_id': 'migrated-system',
        'environment_id': 'legacy-environment'
    }
}
```

Need more help? Check our comprehensive documentation or open a GitHub issue with your specific question!