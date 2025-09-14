# GitHub Actions Integration Guide

This comprehensive guide covers integrating the Test Results Management API with GitHub Actions using our reusable workflows and custom actions.

## Overview

The Test Results Management API provides first-class GitHub Actions integration through:

- 🎭 **Reusable Workflows**: Pre-built workflows for Playwright and Cypress
- 🔧 **Custom Actions**: `submit-test-results` action for any testing framework
- 🔐 **Automation Tokens**: Secure API access for CI/CD systems
- 📊 **Rich Reporting**: Automatic test result aggregation and artifact management
- ⚡ **Performance Optimized**: Matrix builds, parallel execution, and caching

## Quick Start

### 1. Generate an Automation Token

```bash
# Install the CLI (if not already installed)
pip install -e /path/to/test-results-api

# Generate a token for GitHub Actions
test-results-cli auth token generate \
  --name "GitHub Actions - $(basename $(pwd))" \
  --scope automation \
  --expires-days 365
```

### 2. Add Token to GitHub Secrets

1. Copy the generated token
2. Go to repository **Settings** → **Secrets and variables** → **Actions**
3. Add a new secret named `TEST_RESULTS_TOKEN`
4. Paste the token value

### 3. Add API Endpoint to Variables

1. Go to **Settings** → **Secrets and variables** → **Actions** → **Variables** tab
2. Add `TEST_RESULTS_API_ENDPOINT` with your API URL (e.g., `https://test-results.your-company.com`)

### 4. Copy Actions to Your Repository

```bash
# Copy the submit-test-results action
cp -r .github/actions/submit-test-results /path/to/your/repo/.github/actions/

# Copy reusable workflows
cp .github/workflows/playwright-tests.yml /path/to/your/repo/.github/workflows/
cp .github/workflows/cypress-tests.yml /path/to/your/repo/.github/workflows/
```

## Using Reusable Workflows

### Playwright Integration

Create `.github/workflows/playwright.yml`:

```yaml
name: Playwright Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  playwright-tests:
    name: Run Playwright Tests
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chromium", "firefox", "webkit"]'
      playwright-version: '1.55.0'
      suite-name-prefix: 'E2E Tests'
      additional-tags: 'regression,nightly'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

### Cypress Integration

Create `.github/workflows/cypress.yml`:

```yaml
name: Cypress Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  cypress-tests:
    name: Run Cypress Tests
    uses: ./.github/workflows/cypress-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chrome", "firefox"]'
      cypress-version: '13.6.0'
      suite-name-prefix: 'Integration Tests'
      record: false  # Set to true if using Cypress Dashboard
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

## Configuration Options

### Playwright Workflow Inputs

| Input | Description | Default | Required |
|-------|-------------|---------|----------|
| `api-endpoint` | Test Results API URL | - | ✅ |
| `node-version` | Node.js version | `'20'` | ❌ |
| `playwright-version` | Playwright version | `'latest'` | ❌ |
| `browsers` | Browser matrix (JSON) | `'["chromium"]'` | ❌ |
| `test-command` | Test command | `'npx playwright test'` | ❌ |
| `environment-prefix` | Environment name prefix | `'ci-playwright'` | ❌ |
| `suite-name-prefix` | Suite name prefix | `'Playwright Tests'` | ❌ |
| `working-directory` | Working directory | `'.'` | ❌ |
| `results-path` | Results storage path | `'test-results'` | ❌ |
| `upload-artifacts` | Upload artifacts | `true` | ❌ |
| `additional-tags` | Extra tags | `''` | ❌ |

### Cypress Workflow Inputs

| Input | Description | Default | Required |
|-------|-------------|---------|----------|
| `api-endpoint` | Test Results API URL | - | ✅ |
| `node-version` | Node.js version | `'20'` | ❌ |
| `cypress-version` | Cypress version | `'latest'` | ❌ |
| `browsers` | Browser matrix (JSON) | `'["chrome"]'` | ❌ |
| `test-command` | Test command | `'npx cypress run'` | ❌ |
| `environment-prefix` | Environment name prefix | `'ci-cypress'` | ❌ |
| `suite-name-prefix` | Suite name prefix | `'Cypress Tests'` | ❌ |
| `working-directory` | Working directory | `'.'` | ❌ |
| `results-path` | Results storage path | `'cypress/results'` | ❌ |
| `upload-artifacts` | Upload artifacts | `true` | ❌ |
| `additional-tags` | Extra tags | `''` | ❌ |
| `record` | Cypress Dashboard recording | `false` | ❌ |
| `parallel` | Parallel execution | `false` | ❌ |

## Advanced Patterns

### Multi-Environment Testing

```yaml
name: Multi-Environment Tests

on: [push, pull_request]

jobs:
  # Test against different environments
  staging-tests:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.STAGING_API_ENDPOINT }}
      environment-prefix: 'staging'
      additional-tags: 'staging,pre-prod'
    secrets:
      automation-token: ${{ secrets.STAGING_TEST_TOKEN }}

  production-tests:
    if: github.ref == 'refs/heads/main'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.PRODUCTION_API_ENDPOINT }}
      environment-prefix: 'production'
      test-command: 'npx playwright test --grep @smoke'
      additional-tags: 'production,smoke'
    secrets:
      automation-token: ${{ secrets.PRODUCTION_TEST_TOKEN }}
```

### Matrix Testing Across Node Versions

```yaml
name: Node Version Matrix

on: [push, pull_request]

jobs:
  playwright-matrix:
    strategy:
      matrix:
        node-version: ['18', '20', '22']
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      node-version: ${{ matrix.node-version }}
      environment-prefix: 'node-${{ matrix.node-version }}'
      browsers: '["chromium"]'
      additional-tags: 'node-${{ matrix.node-version }}'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

### Conditional Execution

```yaml
name: Smart Test Execution

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  # Full test suite on main branch
  full-tests:
    if: github.ref == 'refs/heads/main'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chromium", "firefox", "webkit"]'
      suite-name-prefix: 'Full Regression'
      additional-tags: 'full-suite,main-branch'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}

  # Smoke tests on pull requests
  smoke-tests:
    if: github.event_name == 'pull_request'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      test-command: 'npx playwright test --grep @smoke'
      browsers: '["chromium"]'
      suite-name-prefix: 'PR Smoke Tests'
      additional-tags: 'smoke,pull-request'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

### Custom Test Suites

```yaml
name: Specialized Test Suites

on: [push, pull_request]

jobs:
  # API tests only
  api-tests:
    uses: ./.github/workflows/cypress-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      test-command: 'npx cypress run --spec "cypress/e2e/api/**/*"'
      browsers: '["chrome"]'
      environment-prefix: 'api'
      suite-name-prefix: 'API Tests'
      additional-tags: 'api,backend'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}

  # Visual regression tests
  visual-tests:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      test-command: 'npx playwright test --grep @visual'
      browsers: '["chromium"]'
      environment-prefix: 'visual'
      suite-name-prefix: 'Visual Regression'
      additional-tags: 'visual,regression'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}

  # Performance tests
  performance-tests:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      test-command: 'npx playwright test --grep @performance --project performance'
      browsers: '["chromium"]'
      environment-prefix: 'performance'
      suite-name-prefix: 'Performance Tests'
      additional-tags: 'performance,load'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

## Direct Action Usage

For custom testing setups, use the action directly:

```yaml
name: Custom Integration

on: [push, pull_request]

jobs:
  custom-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Run custom tests
        run: |
          npm run test:custom -- --reporter=json --output-file=results.json

      - name: Submit test results
        if: always()
        uses: ./.github/actions/submit-test-results
        with:
          api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
          automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
          framework: 'custom-framework@1.0.0'
          environment-name: 'custom-env'
          results-file: 'results.json'
          suite-name: 'Custom Test Suite'
          tags: 'custom,integration'
```

## Scheduled Testing

Run tests on a schedule for continuous monitoring:

```yaml
name: Scheduled Tests

on:
  schedule:
    # Run every day at 2 AM UTC
    - cron: '0 2 * * *'
    # Run every hour during business hours (9 AM - 5 PM UTC, Mon-Fri)
    - cron: '0 9-17 * * 1-5'

jobs:
  nightly-full-suite:
    if: github.event.schedule == '0 2 * * *'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chromium", "firefox", "webkit"]'
      suite-name-prefix: 'Nightly Regression'
      additional-tags: 'nightly,scheduled,full-suite'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}

  hourly-smoke-tests:
    if: github.event.schedule == '0 9-17 * * 1-5'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      test-command: 'npx playwright test --grep @smoke'
      browsers: '["chromium"]'
      suite-name-prefix: 'Hourly Smoke'
      additional-tags: 'smoke,scheduled,monitoring'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

## Workflow Outputs and Reporting

Access workflow outputs for custom reporting:

```yaml
name: Test Results with Reporting

on: [push, pull_request]

jobs:
  run-tests:
    id: tests
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chromium", "firefox"]'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}

  report-results:
    needs: run-tests
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Create summary report
        run: |
          echo "# 🎭 Test Results Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Results Submitted**: ${{ needs.run-tests.outputs.results-submitted }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Total Tests**: ${{ needs.run-tests.outputs.total-tests }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Failed Tests**: ${{ needs.run-tests.outputs.failed-tests }}" >> $GITHUB_STEP_SUMMARY

      - name: Notify on failure
        if: needs.run-tests.outputs.failed-tests != '0'
        run: |
          echo "::warning::${{ needs.run-tests.outputs.failed-tests }} tests failed"

      - name: Post to Mattermost (example)
        if: failure()
        # Add your Mattermost notification action here
        run: |
          echo "Would post to Mattermost: Tests failed in ${{ github.repository }}"
```

## Security Best Practices

### Token Management

- ✅ **Use repository secrets** for tokens, never commit them
- ✅ **Generate environment-specific tokens** for different environments
- ✅ **Set reasonable expiration dates** (90-365 days)
- ✅ **Rotate tokens regularly** using the CLI
- ✅ **Use minimal scope** (automation scope for CI/CD)

### Environment Isolation

```yaml
# Use different tokens for different environments
jobs:
  staging-tests:
    environment: staging  # GitHub environment with protection rules
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.STAGING_API_ENDPOINT }}
    secrets:
      automation-token: ${{ secrets.STAGING_TEST_TOKEN }}

  production-tests:
    environment: production  # Requires manual approval
    if: github.ref == 'refs/heads/main'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.PRODUCTION_API_ENDPOINT }}
    secrets:
      automation-token: ${{ secrets.PRODUCTION_TEST_TOKEN }}
```

## Troubleshooting

### Common Issues

1. **Authentication failures**
   ```yaml
   - name: Validate token
     run: |
       # Add token validation step for debugging
       curl -H "Authorization: Bearer ${{ secrets.TEST_RESULTS_TOKEN }}" \
            -H "Content-Type: application/json" \
            ${{ vars.TEST_RESULTS_API_ENDPOINT }}/api/v1/frameworks
   ```

2. **Results file not found**
   ```yaml
   - name: Debug results files
     if: always()
     run: |
       echo "Looking for results files:"
       find . -name "*.json" -type f
       ls -la test-results/ || echo "test-results directory not found"
   ```

3. **Network connectivity issues**
   ```yaml
   - name: Test API connectivity
     run: |
       curl -v ${{ vars.TEST_RESULTS_API_ENDPOINT }}/health
   ```

### Debug Mode

Enable debug logging in workflows:

```yaml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

### Artifact Inspection

Download and inspect artifacts:

```yaml
- name: Upload raw results for debugging
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: debug-results
    path: |
      test-results/
      *.json
      *.log
```

## Performance Optimization

### Caching Strategies

```yaml
jobs:
  playwright-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js with caching
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Cache Playwright browsers
        uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: playwright-browsers-${{ hashFiles('package-lock.json') }}

      # ... rest of the steps
```

### Parallel Execution

```yaml
jobs:
  playwright-matrix:
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      test-command: 'npx playwright test --shard=${{ matrix.shard }}/4'
      environment-prefix: 'shard-${{ matrix.shard }}'
      additional-tags: 'parallel,shard-${{ matrix.shard }}'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

## Migration from Other Systems

### From existing GitHub Actions

```yaml
# Before: Basic test run
- name: Run tests
  run: npx playwright test

# After: With test results integration
- name: Run tests with results submission
  uses: ./.github/workflows/playwright-tests.yml
  with:
    api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
  secrets:
    automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

### From other CI systems

When migrating from Jenkins, CircleCI, etc., the workflows provide equivalent functionality:

- **Matrix builds** → `browsers` input with JSON array
- **Parallel execution** → Use sharding or matrix strategy
- **Artifact management** → Automatic with `upload-artifacts: true`
- **Environment variables** → Workflow inputs and GitHub variables
- **Notifications** → Workflow outputs and custom reporting steps

## Resources

- [Submit Test Results Action](../.github/actions/submit-test-results/README.md)
- [Automation Token Management](./automation-tokens.md)
- [Example Workflows](../.github/workflows/)
- [CLI Documentation](./cli-usage.md)
- [API Reference](./api-reference.md)