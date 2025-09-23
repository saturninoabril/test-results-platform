# API Reference

## Overview

The Test Results Management API provides comprehensive endpoints for managing test execution data from end-to-end testing frameworks like Playwright and Cypress. This API is designed for CI/CD integration with GitHub Actions and supports real-time test result submission, artifact management, and reporting.

## Base URL

```
Production: https://api.testresults.dev/v1
Development: http://localhost:8000/v1
```

## Authentication

The API uses Bearer token authentication with JWT tokens. Two types of tokens are supported:

### User Tokens
- Issued via GitHub OAuth for interactive use
- Short-lived (24 hours)
- Full access to user's data

### Automation Tokens
- Long-lived tokens for CI/CD systems
- Scoped permissions (read, write, admin)
- Can be revoked independently

## Core Entities

### TestSuite
Groups related test results from a single execution.

```json
{
  "id": "suite-123",
  "external_id": "github-run-456789",
  "name": "Login Flow Tests",
  "status": "completed",
  "total_tests": 15,
  "passed": 13,
  "failed": 2,
  "skipped": 0,
  "duration_ms": 45000,
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:00:45Z",
  "metadata": {
    "commit_sha": "abc123def456",
    "branch": "feature/login-improvements",
    "pr_number": 123
  }
}
```

### TestResult
Individual test execution result.

```json
{
  "id": "result-456",
  "suite_id": "suite-123",
  "external_id": "test-login-valid-credentials",
  "full_title": "Login Flow › Valid Credentials › should login successfully",
  "status": "passed",
  "duration_ms": 1500,
  "error_message": null,
  "stack_trace": null,
  "tags": ["auth", "smoke", "critical"],
  "retry_count": 0,
  "started_at": "2024-01-15T10:01:00Z",
  "completed_at": "2024-01-15T10:01:01.5Z",
  "metadata": {
    "test_file": "tests/auth/login.spec.ts",
    "test_location": "login.spec.ts:25:5"
  }
}
```

### TestArtifact
Files generated during test execution.

```json
{
  "id": "artifact-789",
  "result_id": "result-456",
  "name": "login-failure-screenshot.png",
  "type": "screenshot",
  "content_type": "image/png",
  "size": 156789,
  "storage_path": "artifacts/2024/01/15/login-failure-screenshot.png",
  "metadata": {
    "width": 1280,
    "height": 720,
    "capture_time": "2024-01-15T10:01:01Z"
  },
  "created_at": "2024-01-15T10:01:02Z"
}
```

## Endpoints

### Test Suites

#### List Test Suites
```http
GET /v1/suites
```

Query Parameters:
- `status`: Filter by status (pending, running, completed, failed)
- `started_after`: ISO datetime filter
- `started_before`: ISO datetime filter

#### Create Test Suite
```http
POST /v1/suites
Content-Type: application/json

{
  "external_id": "github-run-456789",
  "name": "E2E Test Suite",
  "metadata": {
    "commit_sha": "abc123def456",
    "branch": "main",
    "repository": "org/repo"
  }
}
```

#### Update Test Suite
```http
PATCH /v1/suites/{suite_id}
Content-Type: application/json

{
  "status": "completed",
  "total_tests": 25,
  "passed": 23,
  "failed": 2,
  "duration_ms": 120000,
  "completed_at": "2024-01-15T10:05:00Z"
}
```

### Test Results

#### List Test Results
```http
GET /v1/results
```

Query Parameters:
- `suite_id`: Filter by test suite
- `status`: Filter by status (passed, failed, skipped)
- `tags`: Filter by tags (comma-separated)
- `limit`: Number of items (default: 50, max: 100)

#### Create Test Result
```http
POST /v1/results
Content-Type: application/json

{
  "suite_id": "suite-123",
  "external_id": "test-checkout-flow",
  "full_title": "E-commerce › Checkout › should complete purchase",
  "status": "passed",
  "duration_ms": 3500,
  "tags": ["checkout", "payment", "integration"],
  "metadata": {
    "test_file": "tests/checkout/purchase.spec.ts"
  }
}
```

#### Get Test Result
```http
GET /v1/results/{result_id}
```

### Artifacts

#### Upload Artifact
```http
POST /v1/artifacts
Content-Type: multipart/form-data

result_id=result-456
name=failure-screenshot.png
type=screenshot
file=@screenshot.png
```

#### Get Artifact
```http
GET /v1/artifacts/{artifact_id}
```

Returns artifact metadata.

#### Download Artifact
```http
GET /v1/artifacts/{artifact_id}/download
```

Returns the actual file content with appropriate Content-Type header.

#### List Artifacts
```http
GET /v1/artifacts
```

Query Parameters:
- `result_id`: Filter by test result
- `type`: Filter by artifact type
- `content_type`: Filter by MIME type

## Error Responses

The API returns consistent error responses:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field": "framework_id",
      "reason": "Framework not found"
    }
  }
}
```

### Error Codes

- `VALIDATION_ERROR`: Invalid input data
- `NOT_FOUND`: Resource not found
- `UNAUTHORIZED`: Invalid or missing authentication
- `FORBIDDEN`: Insufficient permissions
- `RATE_LIMITED`: Too many requests
- `INTERNAL_ERROR`: Server error

## Rate Limits

- **User tokens**: 1000 requests per hour
- **Automation tokens**: 10000 requests per hour
- **Upload endpoints**: 100 requests per hour per token

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

## Pagination

List endpoints support cursor-based pagination:

```json
{
  "data": [...],
  "pagination": {
    "has_more": true,
    "next_cursor": "eyJ0aW1lc3RhbXAiOiIyMDI0LTAxLTE1VDEwOjAwOjAwWiJ9"
  }
}
```

Use the `cursor` query parameter for subsequent requests:
```http
GET /v1/suites?cursor=eyJ0aW1lc3RhbXAiOiIyMDI0LTAxLTE1VDEwOjAwOjAwWiJ9
```

## GitHub Actions Integration

### Workflow Example

```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Run Playwright Tests
        run: npx playwright test

      - name: Submit Results
        if: always()
        uses: your-org/submit-test-results@v1
        with:
          api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
          automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
          results-path: test-results.json
          artifacts-path: test-results/
```

### Token Setup

1. Generate automation token:
```bash
test-results-cli auth generate-token \
  --name "GitHub Actions - My Repo" \
  --scope write \
  --expires-days 365
```

2. Add token to GitHub Secrets as `TEST_RESULTS_TOKEN`

3. Configure API endpoint in GitHub Variables as `TEST_RESULTS_API_ENDPOINT`

## SDKs and Libraries

### JavaScript/TypeScript
```javascript
import { TestResultsAPI } from '@testresults/js-sdk';

const client = new TestResultsAPI({
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
await client.results.create({
  suite_id: suite.id,
  external_id: 'test-login',
  status: 'passed',
  duration_ms: 1500
});
```

### Python
```python
from testresults import TestResultsClient

client = TestResultsClient(
    endpoint='https://api.testresults.dev/v1',
    token=os.getenv('TEST_RESULTS_TOKEN')
)

# Create test suite
suite = client.suites.create({
    'name': 'API Tests',
    'framework_id': 'pytest-7.0.0',
    'environment_id': 'python-ci'
})

# Upload artifact
with open('screenshot.png', 'rb') as f:
    client.artifacts.upload(
        result_id=result.id,
        name='failure-screenshot.png',
        type='screenshot',
        file=f
    )
```

## Webhooks

Subscribe to test result events:

### Event Types
- `suite.created`
- `suite.completed`
- `result.created`
- `result.failed`
- `artifact.uploaded`

### Payload Example
```json
{
  "event": "suite.completed",
  "timestamp": "2024-01-15T10:05:00Z",
  "data": {
    "suite": {
      "id": "suite-123",
      "name": "E2E Tests",
      "status": "completed",
      "passed": 23,
      "failed": 2,
      "total_tests": 25
    }
  }
}
```

### Setup
```bash
test-results-cli webhooks create \
  --url https://your-app.com/webhooks/test-results \
  --events suite.completed,result.failed \
  --secret your-webhook-secret
```