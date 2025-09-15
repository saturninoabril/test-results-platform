# Test Results Management GitHub Actions

This directory contains reusable GitHub Actions and workflows for integrating test results with the Test Results Management API. These components provide seamless CI/CD integration for popular testing frameworks.

## 📋 Components Overview

### Actions

- **[submit-test-results](./submit-test-results/)**: Core action for submitting test results and artifacts to the API
  - Supports Playwright, Cypress, and custom JSON formats
  - Handles authentication, parsing, and artifact uploads
  - Provides detailed outputs and error handling

### Workflows

- **[playwright-tests.yml](..//workflows/playwright-tests.yml)**: Reusable workflow for Playwright testing
  - Multi-browser support with matrix strategy
  - Configurable test commands and reporting
  - Automatic artifact collection and submission

- **[cypress-tests.yml](../workflows/cypress-tests.yml)**: Reusable workflow for Cypress testing
  - Browser matrix testing with mochawesome reporter
  - Cypress Dashboard integration (optional)
  - Parallel execution support

### Examples

- **[example-playwright-usage.yml](../workflows/example-playwright-usage.yml)**: Complete example workflows
- **[example-cypress-usage.yml](../workflows/example-cypress-usage.yml)**: Ready-to-use templates

## 🚀 Quick Start

### 1. Setup Authentication

First, generate an automation token:

```bash
# Using the Test Results Management CLI
test-results-cli auth generate-token --scope automation --name "GitHub Actions"
```

Add the token to your repository secrets:
1. Go to **Settings** > **Secrets and variables** > **Actions**
2. Add `TEST_RESULTS_TOKEN` with your generated token
3. Optionally add `TEST_RESULTS_API_ENDPOINT` as a variable

### 2. Copy Actions to Your Repository

```bash
# Copy the actions directory to your repository
cp -r .github/actions/submit-test-results /path/to/your/repo/.github/actions/

# Copy reusable workflows
cp .github/workflows/playwright-tests.yml /path/to/your/repo/.github/workflows/
cp .github/workflows/cypress-tests.yml /path/to/your/repo/.github/workflows/
```

### 3. Create Your Workflow

For **Playwright**:
```yaml
name: Playwright Tests
on: [push, pull_request]

jobs:
  test:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chromium", "firefox", "webkit"]'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

For **Cypress**:
```yaml
name: Cypress Tests
on: [push, pull_request]

jobs:
  test:
    uses: ./.github/workflows/cypress-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
      browsers: '["chrome", "firefox"]'
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

## 🔧 Configuration Options

### Common Inputs

All workflows support these common configuration options:

| Input | Description | Default | Required |
|-------|-------------|---------|----------|
| `api-endpoint` | Test Results API URL | - | ✅ |
| `node-version` | Node.js version | `'20'` | ❌ |
| `working-directory` | Command execution directory | `'.'` | ❌ |
| `upload-artifacts` | Upload test artifacts | `true` | ❌ |
| `additional-tags` | Extra tags (comma-separated) | `''` | ❌ |

### Framework-Specific Options

#### Playwright

| Input | Description | Default |
|-------|-------------|---------|
| `playwright-version` | Playwright version | `'latest'` |
| `test-command` | Test execution command | `'npx playwright test'` |
| `browsers` | Browser matrix (JSON array) | `'["chromium"]'` |
| `results-path` | Results storage path | `'test-results'` |

#### Cypress

| Input | Description | Default |
|-------|-------------|---------|
| `cypress-version` | Cypress version | `'latest'` |
| `test-command` | Test execution command | `'npx cypress run'` |
| `browsers` | Browser matrix (JSON array) | `'["chrome"]'` |
| `record` | Enable Cypress Dashboard | `false` |
| `parallel` | Parallel execution | `false` |

## 📊 Outputs and Monitoring

### Workflow Outputs

All workflows provide these outputs:

- `results-submitted`: Whether results were successfully submitted
- `total-tests`: Total number of tests executed
- `failed-tests`: Number of failed tests

### GitHub Actions Integration

The workflows automatically:
- Upload artifacts to GitHub Actions
- Generate test summaries in job outputs
- Provide detailed logging and error reporting
- Handle failures gracefully without breaking CI

### Test Results API Integration

Submitted data includes:
- **Framework information**: Name, version, metadata
- **Environment details**: Browser, OS, CI context
- **Test suites**: Aggregated statistics and metadata
- **Individual results**: Status, duration, tags, error details
- **Artifacts**: Screenshots, videos, reports, logs

## 🏗️ Advanced Usage Patterns

### Multi-Environment Testing

```yaml
jobs:
  # Test against different Node.js versions
  test-matrix:
    strategy:
      matrix:
        node-version: ['18', '20', '22']
    uses: ./.github/workflows/playwright-tests.yml
    with:
      node-version: ${{ matrix.node-version }}
      environment-prefix: 'node-${{ matrix.node-version }}'
```

### Conditional Testing

```yaml
jobs:
  # Run full tests on main, smoke tests on PRs
  full-tests:
    if: github.ref == 'refs/heads/main'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      browsers: '["chromium", "firefox", "webkit"]'

  smoke-tests:
    if: github.event_name == 'pull_request'
    uses: ./.github/workflows/playwright-tests.yml
    with:
      test-command: 'npx playwright test --grep @smoke'
      browsers: '["chromium"]'
```

### Custom Test Commands

```yaml
jobs:
  # Different test suites
  unit-tests:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      test-command: 'npm run test:unit'
      suite-name-prefix: 'Unit Tests'

  integration-tests:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      test-command: 'npm run test:integration'
      suite-name-prefix: 'Integration Tests'
```

## 🔍 Troubleshooting

### Common Issues

1. **Authentication failures**
   - Verify `TEST_RESULTS_TOKEN` secret is set
   - Check token permissions and expiration
   - Validate API endpoint URL

2. **No results submitted**
   - Ensure test command generates JSON output
   - Check results file path configuration
   - Verify test framework version compatibility

3. **Artifact upload failures**
   - Check artifacts directory exists
   - Verify supported file extensions
   - Review artifact path configuration

### Debug Mode

Enable detailed logging:

```yaml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

### Manual Testing

Test the action locally:

```bash
# Install dependencies
cd .github/actions/submit-test-results
npm install

# Set environment variables
export INPUT_API_ENDPOINT="https://your-api.example.com"
export INPUT_AUTOMATION_TOKEN="your-token"
export INPUT_FRAMEWORK="playwright@1.55.0"
export INPUT_ENVIRONMENT_NAME="local-test"
export INPUT_RESULTS_FILE="test-results.json"

# Run the action
node src/index.js
```

## 📚 Additional Resources

- [Submit Test Results Action Documentation](./submit-test-results/README.md)
- [Example Workflows](../workflows/)
- [Test Results Management API Documentation](../../docs/)
- [Troubleshooting Guide](../../docs/troubleshooting.md)

## 🤝 Contributing

To contribute improvements:

1. **Action Updates**: Modify files in `./submit-test-results/`
2. **Workflow Updates**: Edit the reusable workflow files
3. **Testing**: Use the example workflows to validate changes
4. **Documentation**: Update relevant README files

### Development Workflow

```bash
# Make changes to the action
cd .github/actions/submit-test-results

# Install dependencies
npm install

# Build the action (if using @vercel/ncc)
npm run build

# Test with example data
npm test

# Commit the dist/ directory
git add dist/
git commit -m "Update action build"
```

## 📄 License

These GitHub Actions are licensed under the MIT License. See the project's main LICENSE file for details.