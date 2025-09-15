# Submit Test Results Action

A GitHub Action for submitting test results and artifacts to the Test Results Management API. Supports Playwright, Cypress, and other testing frameworks.

## Features

- 🚀 **Multi-framework support**: Works with Playwright, Cypress, and custom JSON formats
- 📊 **Automatic result parsing**: Detects format and extracts test data automatically
- 📎 **Artifact management**: Uploads screenshots, videos, and other test artifacts
- 🔐 **Secure authentication**: Uses bearer token authentication
- 📋 **Flexible configuration**: Comprehensive input options for different CI scenarios
- 🏷️ **Tagging support**: Apply custom tags to organize test results

## Usage

### Basic Example

```yaml
- name: Submit Test Results
  uses: ./path/to/submit-test-results
  with:
    api-endpoint: 'https://test-results.example.com'
    automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
    framework: 'playwright@1.55.0'
    environment-name: 'ci-chrome-ubuntu'
    results-file: 'test-results.json'
    artifacts-path: 'test-results/'
```

### Complete Playwright Example

```yaml
name: Playwright Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps

      - name: Run Playwright tests
        run: npx playwright test --reporter=json --output-file=test-results.json

      - name: Submit Test Results
        if: always()
        uses: ./path/to/submit-test-results
        with:
          api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
          automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
          framework: 'playwright@1.55.0'
          environment-name: 'ci-playwright-chrome'
          browser: 'chrome'
          os: 'ubuntu'
          results-file: 'test-results.json'
          suite-name: 'Playwright E2E Tests - ${{ github.ref_name }}'
          artifacts-path: 'test-results/'
          tags: 'e2e,playwright,chrome,${{ github.ref_name }}'
```

### Complete Cypress Example

```yaml
name: Cypress Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Run Cypress tests
        run: |
          npx cypress run \
            --reporter mochawesome \
            --reporter-options reportDir=cypress/results,overwrite=false,html=false,json=true

      - name: Submit Test Results
        if: always()
        uses: ./path/to/submit-test-results
        with:
          api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
          automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
          framework: 'cypress@13.6.0'
          environment-name: 'ci-cypress-chrome'
          browser: 'chrome'
          os: 'ubuntu'
          results-file: 'cypress/results/mochawesome.json'
          suite-name: 'Cypress Integration Tests - ${{ github.ref_name }}'
          artifacts-path: 'cypress/screenshots/'
          tags: 'integration,cypress,chrome,${{ github.ref_name }}'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `api-endpoint` | API endpoint URL | ✅ | - |
| `automation-token` | Bearer token for API authentication | ✅ | - |
| `framework` | Test framework name and version (format: `name@version`) | ✅ | - |
| `environment-name` | Environment name for test execution | ✅ | - |
| `browser` | Browser used for testing | ❌ | `chrome` |
| `os` | Operating system | ❌ | `ubuntu` |
| `results-file` | Path to test results JSON file | ✅ | - |
| `suite-name` | Test suite name | ❌ | `CI Test Suite` |
| `artifacts-path` | Path to artifacts directory | ❌ | - |
| `upload-artifacts` | Whether to upload artifacts | ❌ | `true` |
| `tags` | Comma-separated list of tags | ❌ | `ci,automated` |

## Outputs

| Output | Description |
|--------|-------------|
| `framework-id` | ID of the created/found framework |
| `environment-id` | ID of the created/found environment |
| `suite-id` | ID of the created test suite |
| `results-count` | Number of test results submitted |
| `artifacts-count` | Number of artifacts uploaded |

## Supported Test Result Formats

### Playwright JSON Reporter

```json
{
  "config": { ... },
  "suites": [
    {
      "title": "Test Suite",
      "specs": [
        {
          "title": "test-file.spec.js",
          "tests": [
            {
              "title": "should work correctly",
              "results": [
                {
                  "status": "passed",
                  "duration": 1500
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### Cypress Mochawesome Reporter

```json
{
  "stats": {
    "suites": 1,
    "tests": 5,
    "passes": 4,
    "pending": 0,
    "failures": 1
  },
  "results": [
    {
      "suites": [
        {
          "title": "Test Suite",
          "tests": [
            {
              "title": "should work correctly",
              "state": "passed",
              "duration": 1500
            }
          ]
        }
      ]
    }
  ]
}
```

### Generic Array Format

```json
[
  {
    "name": "Test case name",
    "status": "passed",
    "duration_ms": 1500,
    "tags": ["smoke", "critical"]
  }
]
```

## Artifact Types

The action automatically detects and categorizes artifacts:

- **Screenshots**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
- **Videos**: `.mp4`, `.webm`
- **Reports**: `.json`, `.html`
- **Logs**: `.txt`, `.log`
- **Other**: Any other file type

## Authentication

The action requires a bearer token for API authentication. Create the token using the Test Results Management API CLI:

```bash
# Generate an automation token
test-results-cli auth generate-token --scope automation --name "GitHub Actions"
```

Store the token as a GitHub secret:
1. Go to your repository settings
2. Navigate to **Secrets and variables** > **Actions**
3. Add a new secret named `TEST_RESULTS_TOKEN`
4. Paste the generated token

## Environment Variables

The action automatically includes GitHub context in the metadata:

- `GITHUB_REPOSITORY`
- `GITHUB_RUN_ID`
- `GITHUB_RUN_NUMBER`
- `GITHUB_SHA`
- `GITHUB_REF`
- `GITHUB_ACTOR`
- `GITHUB_WORKFLOW`
- `RUNNER_OS`
- `RUNNER_ARCH`

## Error Handling

The action is designed to be resilient:

- **Non-blocking**: Failed artifact uploads won't fail the entire action
- **Partial success**: Successfully submitted results are reported even if some fail
- **Detailed logging**: Comprehensive logs help with troubleshooting
- **Graceful degradation**: Missing optional inputs are handled gracefully

## Troubleshooting

### Common Issues

1. **Authentication Error (401)**
   - Verify the `automation-token` is correct
   - Check token hasn't expired
   - Ensure token has required permissions

2. **Results File Not Found**
   - Verify the `results-file` path is correct
   - Ensure the test command generates the results file
   - Check file permissions

3. **Unsupported Format**
   - Currently supports Playwright JSON, Cypress Mochawesome, and generic arrays
   - Check the results file structure matches expected format

4. **Artifacts Not Uploaded**
   - Verify the `artifacts-path` exists and contains files
   - Check file extensions are supported
   - Ensure `upload-artifacts` is set to `true`

### Debug Mode

Enable debug logging by setting the `ACTIONS_STEP_DEBUG` secret to `true` in your repository.

## License

This action is licensed under the MIT License. See [LICENSE](LICENSE) for details.