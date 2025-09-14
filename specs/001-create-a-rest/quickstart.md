# Quickstart: Test Results Management API

## Overview
This quickstart demonstrates the complete workflow for storing and retrieving test results from Playwright and Cypress test executions using the Test Results Management API. Primary integration is via GitHub Actions CI/CD pipelines using bearer token authentication.

## Prerequisites
- API running on `http://localhost:8000` (local) or production endpoint
- Valid JWT bearer token (GitHub OAuth authentication or automation token)
- Sample test results data
- For GitHub Actions: Repository secrets configured

## Authentication Setup

### For GitHub Actions (Recommended)
```bash
# 1. Generate automation token (one-time setup)
curl -X POST http://localhost:8000/auth/token \
  -H "Authorization: Bearer $USER_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub Actions - my-org/my-repo",
    "scope": "write",
    "expires_days": 90,
    "metadata": {
      "repository": "my-org/my-repo",
      "workflow": "test.yml"
    }
  }'

# 2. Add token to GitHub repository secrets as TEST_RESULTS_API_TOKEN
# Settings > Secrets and variables > Actions > New repository secret
```

### For Local Development
```bash
# Use personal access token from GitHub OAuth flow
export JWT_TOKEN="your-personal-jwt-token"
```

## Quick Start Scenarios

### Scenario 1: Store Playwright Test Results
**Goal**: Submit test results from a Playwright test suite execution

```bash
# 1. Create test framework
curl -X POST http://localhost:8000/frameworks \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "playwright",
    "version": "1.40.0",
    "metadata": {
      "browser_support": ["chromium", "firefox", "webkit"],
      "parallel_workers": 4
    }
  }'

# 2. Create test environment
curl -X POST http://localhost:8000/environments \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ci-staging",
    "browser": "chromium",
    "os": "ubuntu-22.04",
    "metadata": {
      "node_version": "18.17.0",
      "ci_run_id": "run-12345"
    }
  }'

# 3. Create test suite
curl -X POST http://localhost:8000/suites \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "E2E Login Flow Tests",
    "framework_id": "<framework-uuid>",
    "environment_id": "<environment-uuid>",
    "total_tests": 5,
    "passed_tests": 4,
    "failed_tests": 1,
    "skipped_tests": 0,
    "duration_ms": 25000,
    "started_at": "2025-09-14T10:00:00Z",
    "completed_at": "2025-09-14T10:00:25Z",
    "metadata": {
      "commit_sha": "abc123def456",
      "branch": "feature/login-improvements"
    }
  }'

# 4. Submit test results in bulk
curl -X POST http://localhost:8000/results/bulk \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "suite_id": "<suite-uuid>",
      "test_name": "manages focus when opening and closing settings modal with keyboard",
      "full_title": "accessibility/channels/settings_dialog/settings.spec.ts > manages focus when opening and closing settings modal with keyboard",
      "status": "passed",
      "duration_ms": 3971,
      "retry_count": 0,
      "tags": ["accessibility", "settings"],
      "external_id": "c27dc2d4fd7579bfae82-84088ebe5b793a8b0db8",
      "metadata": {
        "projectId": "ipad",
        "projectName": "ipad",
        "workerIndex": 1,
        "parallelIndex": 0,
        "file": "accessibility/channels/settings_dialog/settings.spec.ts",
        "line": 9,
        "column": 5
      }
    },
    {
      "suite_id": "<suite-uuid>",
      "test_name": "passes accessibility scan on notifications settings panel",
      "full_title": "accessibility/channels/settings_dialog/settings.spec.ts > passes accessibility scan on notifications settings panel",
      "status": "passed",
      "duration_ms": 3064,
      "retry_count": 0,
      "tags": ["accessibility", "settings"],
      "external_id": "c27dc2d4fd7579bfae82-b56dd53696317a97121f",
      "metadata": {
        "projectId": "ipad",
        "projectName": "ipad",
        "workerIndex": 1,
        "parallelIndex": 0,
        "file": "accessibility/channels/settings_dialog/settings.spec.ts",
        "line": 115,
        "column": 5
      }
    }
  ]'
```

### Scenario 2: Store Cypress Test Results
**Goal**: Submit test results from a Cypress test suite execution

```bash
# 1. Create Cypress framework
curl -X POST http://localhost:8000/frameworks \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cypress",
    "version": "13.6.0",
    "metadata": {
      "browser_support": ["chrome", "firefox", "edge"],
      "video_recording": true
    }
  }'

# 2. Create local test environment
curl -X POST http://localhost:8000/environments \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "local-dev",
    "browser": "chrome",
    "os": "macos-13",
    "metadata": {
      "resolution": "1920x1080",
      "cypress_config": "cypress.config.js"
    }
  }'

# 3. Submit Cypress suite and results
curl -X POST http://localhost:8000/suites \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Verify Accessibility Support in Channel Sidebar Navigation",
    "framework_id": "<cypress-framework-uuid>",
    "environment_id": "<local-env-uuid>",
    "total_tests": 8,
    "passed_tests": 8,
    "failed_tests": 0,
    "skipped_tests": 0,
    "duration_ms": 22041,
    "started_at": "2025-09-01T06:21:14Z",
    "completed_at": "2025-09-01T06:21:36Z"
  }'

# 4. Submit real Cypress test results
curl -X POST http://localhost:8000/results/bulk \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "suite_id": "<cypress-suite-uuid>",
      "test_name": "MM-T1470 Verify Tab Support in Channels section",
      "full_title": "Verify Accessibility Support in Channel Sidebar Navigation MM-T1470 Verify Tab Support in Channels section",
      "status": "passed",
      "duration_ms": 7225,
      "retry_count": 0,
      "external_id": "c8554ed9-b1f8-4b8b-8b40-e8e9486095e3",
      "metadata": {
        "speed": "medium",
        "parentUUID": "8da87bb9-d6ee-497d-bc9a-4b3714cd9b6e",
        "file": "tests/integration/channels/accessibility/accessibility_sidebar_spec.ts"
      }
    },
    {
      "suite_id": "<cypress-suite-uuid>",
      "test_name": "Focus should be on RHS when opening Recent Mentions",
      "full_title": "Accessibility tests for RHS getting focus after buttons actions Focus should be on RHS when opening Recent Mentions",
      "status": "passed",
      "duration_ms": 3374,
      "retry_count": 0,
      "external_id": "fe4ddf12-5b7f-4c47-a6a5-27179356b65b",
      "metadata": {
        "speed": "fast",
        "parentUUID": "cfa95ed8-6b87-4105-a0c0-305d1771cbb7"
      }
    }
  ]'
```

### Scenario 3: Query and Filter Test Results
**Goal**: Retrieve test results with various filters for analysis

```bash
# 1. Get all test results for a specific suite
curl -X GET "http://localhost:8000/results?suite_id=<suite-uuid>" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 2. Get failed tests from last 24 hours
curl -X GET "http://localhost:8000/results?status=failed&created_after=2025-09-13T14:00:00Z" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 3. Search for login-related tests
curl -X GET "http://localhost:8000/results?test_name=login&page=1&size=10" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 4. Get suite summary with pagination
curl -X GET "http://localhost:8000/suites?framework_id=<framework-uuid>&page=1&size=20" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Scenario 4: Upload and Manage Test Artifacts
**Goal**: Upload screenshots, videos, and reports associated with test results

```bash
# 1. Upload a screenshot for a specific test result
curl -X POST http://localhost:8000/artifacts \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@login-failure-screenshot.png" \
  -F "result_id=<result-uuid>" \
  -F "artifact_type=screenshot" \
  -F 'metadata={"step":"login_attempt","retry":2}'

# 2. Upload a video for an entire test suite
curl -X POST http://localhost:8000/artifacts \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@test-suite-recording.mp4" \
  -F "suite_id=<suite-uuid>" \
  -F "artifact_type=video" \
  -F 'metadata={"recording_quality":"1080p","duration_seconds":120}'

# 3. Upload a test report
curl -X POST http://localhost:8000/artifacts \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@playwright-report.html" \
  -F "suite_id=<suite-uuid>" \
  -F "artifact_type=report" \
  -F 'metadata={"format":"html","generator":"playwright"}'

# 4. List artifacts for a test result
curl -X GET "http://localhost:8000/artifacts?result_id=<result-uuid>" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 5. Get download URL for an artifact
curl -X GET "http://localhost:8000/artifacts/<artifact-id>/download?expires_in=3600" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 6. Delete an artifact
curl -X DELETE http://localhost:8000/artifacts/<artifact-id> \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Scenario 5: Update Test Results
**Goal**: Modify existing test result metadata or rerun status

```bash
# 1. Update test result with additional metadata
curl -X PUT http://localhost:8000/results/<result-uuid> \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": "<suite-uuid>",
    "test_name": "tests/login.spec.ts > should login with valid credentials",
    "status": "passed",
    "duration_ms": 3500,
    "retry_count": 1,
    "metadata": {
      "test_id": "login-001",
      "page_url": "https://staging.app.com/login",
      "rerun_reason": "flaky test retry",
      "performance_metrics": {
        "dom_content_loaded": 1200,
        "first_paint": 800
      }
    }
  }'
```

### Scenario 6: Clean Up Old Results
**Goal**: Remove test results and artifacts that are no longer needed

```bash
# 1. Clean up expired artifacts (admin only)
curl -X POST http://localhost:8000/artifacts/cleanup \
  -H "Authorization: Bearer $JWT_TOKEN"

# 2. Delete a specific test result
curl -X DELETE http://localhost:8000/results/<result-uuid> \
  -H "Authorization: Bearer $JWT_TOKEN"

# 3. Delete an entire test suite (cascades to results and artifacts)
curl -X DELETE http://localhost:8000/suites/<suite-uuid> \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## GitHub Actions Integration

### Complete Playwright Workflow
```yaml
name: E2E Tests with Result Submission
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        browser: [chromium, firefox, webkit]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps ${{ matrix.browser }}

      - name: Run Playwright tests
        run: npx playwright test --project=${{ matrix.browser }} --reporter=json
        env:
          PLAYWRIGHT_JSON_OUTPUT_FILE: test-results.json

      - name: Submit test results
        if: always()
        run: |
          # Create framework and environment
          FRAMEWORK_ID=$(curl -s -X POST ${{ vars.TEST_API_URL }}/frameworks \
            -H "Authorization: Bearer ${{ secrets.TEST_RESULTS_API_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{"name": "playwright", "version": "1.55.0"}' | jq -r '.id')

          ENV_ID=$(curl -s -X POST ${{ vars.TEST_API_URL }}/environments \
            -H "Authorization: Bearer ${{ secrets.TEST_RESULTS_API_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "name": "github-actions",
              "browser": "${{ matrix.browser }}",
              "os": "ubuntu-22.04",
              "metadata": {
                "github_run_id": "${{ github.run_id }}",
                "github_workflow": "${{ github.workflow }}",
                "github_ref": "${{ github.ref }}"
              }
            }' | jq -r '.id')

          # Create test suite
          SUITE_ID=$(curl -s -X POST ${{ vars.TEST_API_URL }}/suites \
            -H "Authorization: Bearer ${{ secrets.TEST_RESULTS_API_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d "{
              \"name\": \"E2E Tests - ${{ matrix.browser }}\",
              \"framework_id\": \"$FRAMEWORK_ID\",
              \"environment_id\": \"$ENV_ID\",
              \"total_tests\": $(jq '.stats.expected' test-results.json),
              \"passed_tests\": $(jq '.stats.expected - .stats.unexpected' test-results.json),
              \"failed_tests\": $(jq '.stats.unexpected' test-results.json),
              \"skipped_tests\": $(jq '.stats.skipped' test-results.json),
              \"duration_ms\": $(jq '.stats.duration' test-results.json),
              \"started_at\": \"$(jq -r '.stats.startTime' test-results.json)\",
              \"completed_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
              \"metadata\": {
                \"github_run_id\": \"${{ github.run_id }}\",
                \"commit_sha\": \"${{ github.sha }}\",
                \"branch\": \"${{ github.ref_name }}\"
              }
            }" | jq -r '.id')

          # Submit individual test results
          node -e "
            const results = require('./test-results.json');
            const testResults = results.suites.flatMap(suite =>
              suite.specs.flatMap(spec =>
                spec.tests.map(test => ({
                  suite_id: '$SUITE_ID',
                  test_name: spec.title,
                  full_title: spec.title + ' > ' + test.results[0]?.status || 'unknown',
                  status: test.results[0]?.status || 'skipped',
                  duration_ms: test.results[0]?.duration || 0,
                  retry_count: test.results[0]?.retry || 0,
                  external_id: test.id,
                  tags: test.tags || [],
                  metadata: {
                    projectId: test.projectId,
                    projectName: test.projectName,
                    file: spec.file,
                    line: test.line,
                    column: test.column
                  }
                }))
              )
            );

            fetch('${{ vars.TEST_API_URL }}/results/bulk', {
              method: 'POST',
              headers: {
                'Authorization': 'Bearer ${{ secrets.TEST_RESULTS_API_TOKEN }}',
                'Content-Type': 'application/json'
              },
              body: JSON.stringify(testResults)
            }).then(r => r.json()).then(console.log);
          "

      - name: Upload test artifacts
        if: always()
        run: |
          # Upload screenshots and videos
          find playwright-report -name "*.png" -o -name "*.webm" | while read file; do
            curl -X POST ${{ vars.TEST_API_URL }}/artifacts \
              -H "Authorization: Bearer ${{ secrets.TEST_RESULTS_API_TOKEN }}" \
              -F "file=@$file" \
              -F "suite_id=$SUITE_ID" \
              -F "artifact_type=screenshot" \
              -F "metadata={\"browser\": \"${{ matrix.browser }}\"}"
          done
```

### Cypress GitHub Actions Workflow
```yaml
name: Cypress Tests
on: [push, pull_request]

jobs:
  cypress:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Cypress run
        uses: cypress-io/github-action@v6
        with:
          start: npm start
          wait-on: 'http://localhost:3000'
          reporter: mochawesome
          reporter-options: 'reportDir=cypress/reports,overwrite=false,html=false,json=true'

      - name: Submit Cypress results
        if: always()
        uses: ./.github/actions/submit-test-results
        with:
          api_url: ${{ vars.TEST_API_URL }}
          api_token: ${{ secrets.TEST_RESULTS_API_TOKEN }}
          framework: cypress
          framework_version: "13.6.0"
          results_file: cypress/reports/mochawesome.json
          environment_name: github-actions-cypress
```

### Reusable Action for Test Submission
Create `.github/actions/submit-test-results/action.yml`:
```yaml
name: 'Submit Test Results'
description: 'Submit test results to Test Results Management API'
inputs:
  api_url:
    description: 'API base URL'
    required: true
  api_token:
    description: 'Bearer token for API authentication'
    required: true
  framework:
    description: 'Testing framework name'
    required: true
  framework_version:
    description: 'Framework version'
    required: true
  results_file:
    description: 'Path to test results JSON file'
    required: true
  environment_name:
    description: 'Test environment name'
    required: true

runs:
  using: 'composite'
  steps:
    - name: Submit results
      shell: bash
      run: |
        # Process results file and submit to API
        node -e "
          const fs = require('fs');
          const results = JSON.parse(fs.readFileSync('${{ inputs.results_file }}'));

          // Create framework, environment, suite, and submit results
          // (implementation similar to above Playwright example)
        "
```

## Integration Examples

### Playwright Integration Script
```javascript
// playwright-reporter.js
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

class TestResultsReporter {
  constructor(options) {
    this.apiUrl = options.apiUrl;
    this.token = options.token;
    this.frameworkId = options.frameworkId;
    this.environmentId = options.environmentId;
  }

  async onTestRunComplete(result) {
    // Create suite
    const suite = await this.createSuite(result);

    // Submit results in bulk
    const testResults = await Promise.all(result.tests.map(async test => {
      const testResult = await this.submitTestResult({
        suite_id: suite.id,
        test_name: test.title,
        status: test.outcome === 'passed' ? 'passed' : 'failed',
        duration_ms: test.duration,
        error_message: test.error?.message,
        metadata: {
          file_path: test.location.file,
          line_number: test.location.line
        }
      });

      // Upload artifacts (screenshots, videos, traces)
      await this.uploadArtifacts(testResult.id, test.attachments);

      return testResult;
    }));

    // Upload suite-level report if available
    if (result.htmlReportPath) {
      await this.uploadSuiteArtifact(suite.id, result.htmlReportPath, 'report');
    }
  }

  async uploadArtifacts(resultId, attachments) {
    for (const attachment of attachments) {
      if (fs.existsSync(attachment.path)) {
        await this.uploadFile(attachment.path, {
          result_id: resultId,
          artifact_type: this.detectArtifactType(attachment.name),
          metadata: {
            original_name: attachment.name,
            content_type: attachment.contentType
          }
        });
      }
    }
  }

  async uploadFile(filePath, metadata) {
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    formData.append('result_id', metadata.result_id);
    formData.append('artifact_type', metadata.artifact_type);
    formData.append('metadata', JSON.stringify(metadata.metadata));

    await axios.post(`${this.apiUrl}/artifacts`, formData, {
      headers: {
        ...formData.getHeaders(),
        'Authorization': `Bearer ${this.token}`
      }
    });
  }

  detectArtifactType(fileName) {
    const ext = path.extname(fileName).toLowerCase();
    if (['.png', '.jpg', '.jpeg'].includes(ext)) return 'screenshot';
    if (['.mp4', '.webm'].includes(ext)) return 'video';
    if (['.zip', '.har'].includes(ext)) return 'trace';
    if (['.html', '.json'].includes(ext)) return 'report';
    return 'other';
  }
}
```

### Cypress Integration Plugin
```javascript
// cypress/plugins/test-results.js
const axios = require('axios');

module.exports = (on, config) => {
  on('after:run', async (results) => {
    const suiteData = {
      name: 'Cypress Test Run',
      framework_id: config.env.FRAMEWORK_ID,
      environment_id: config.env.ENVIRONMENT_ID,
      total_tests: results.totalTests,
      passed_tests: results.totalPassed,
      failed_tests: results.totalFailed,
      skipped_tests: results.totalSkipped,
      duration_ms: results.totalDuration,
      started_at: results.startedTestsAt,
      completed_at: results.endedTestsAt
    };

    // Submit to API
    await submitTestResults(suiteData, results.runs);
  });
};
```

## Expected Responses

### Successful Suite Creation
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "E2E Login Flow Tests",
  "framework_id": "123e4567-e89b-12d3-a456-426614174000",
  "environment_id": "987fcdeb-51a2-43d1-9f12-345678901234",
  "total_tests": 5,
  "passed_tests": 4,
  "failed_tests": 1,
  "skipped_tests": 0,
  "duration_ms": 25000,
  "started_at": "2025-09-14T10:00:00Z",
  "completed_at": "2025-09-14T10:00:25Z",
  "created_at": "2025-09-14T10:01:00Z",
  "updated_at": "2025-09-14T10:01:00Z"
}
```

### Paginated Results Response
```json
{
  "items": [
    {
      "id": "result-uuid-1",
      "test_name": "tests/login.spec.ts > should login",
      "status": "passed",
      "duration_ms": 3500
    }
  ],
  "total": 150,
  "page": 1,
  "size": 20,
  "pages": 8
}
```

### Error Response
```json
{
  "detail": "Suite not found",
  "code": "SUITE_NOT_FOUND",
  "field": "suite_id"
}
```

## Performance Expectations
- **Suite creation**: < 100ms
- **Bulk result submission** (100 results): < 500ms
- **Result queries** (filtered): < 200ms
- **Pagination**: < 150ms per page

## Troubleshooting
- **401 Unauthorized**: Check JWT token validity
- **404 Not Found**: Verify resource UUIDs exist
- **400 Bad Request**: Check request payload format
- **409 Conflict**: Resource already exists or has dependencies