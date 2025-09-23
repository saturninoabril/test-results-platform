# Playwright Custom Reporter Quickstart Guide

This guide walks through setting up the Playwright custom reporter to send test results to the Test Results Platform in real-time.

## Prerequisites

- Node.js 18+ and npm
- Playwright 1.55+ installed in your project
- Test Results Platform API access token
- Existing Playwright test suite

## Installation

### 1. Install the TypeScript Client Library

```bash
npm install @test-results-platform/playwright-client
# or
yarn add @test-results-platform/playwright-client
```

### 2. Environment Configuration

Create a `.env` file in your project root:

```env
TEST_RESULTS_API_URL=https://api.test-results-platform.com
TEST_RESULTS_API_TOKEN=your_jwt_token_here
TEST_RESULTS_UPLOAD_ARTIFACTS=true
TEST_RESULTS_DEBUG=false
```

### 3. Update Playwright Configuration

Modify your `playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,

  // Reporter configuration
  reporter: [
    // Keep existing reporters for local development
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],

    // Add Test Results Platform reporter
    ['@test-results-platform/playwright-reporter', {
      baseUrl: process.env.TEST_RESULTS_API_URL,
      authToken: process.env.TEST_RESULTS_API_TOKEN,
      uploadArtifacts: process.env.TEST_RESULTS_UPLOAD_ARTIFACTS === 'true',
      debug: process.env.TEST_RESULTS_DEBUG === 'true',
      timeout: 30000,
      retries: 3
    }]
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',

    // Enable artifacts for upload to platform
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    }
  ]
});
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests with real-time reporting
npx playwright test

# Run specific browser project
npx playwright test --project=chromium

# Run with debug logging
TEST_RESULTS_DEBUG=true npx playwright test
```

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: Playwright Tests
on: [push, pull_request]

jobs:
  test:
    timeout-minutes: 60
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright Browsers
        run: npx playwright install --with-deps

      - name: Run Playwright tests
        run: npx playwright test
        env:
          TEST_RESULTS_API_URL: ${{ secrets.TEST_RESULTS_API_URL }}
          TEST_RESULTS_API_TOKEN: ${{ secrets.TEST_RESULTS_API_TOKEN }}
          TEST_RESULTS_UPLOAD_ARTIFACTS: true

      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```

## Verifying Integration

### 1. Check Reporter Initialization

Look for these log messages when tests start:

```
✓ Test Results Platform reporter initialized
✓ Test suite started: abc123-def456-789
✓ Environment registered: Desktop Chrome (chromium)
```

### 2. Monitor Real-time Updates

During test execution, you should see:

```
→ Test started: should login successfully
→ Test completed: should login successfully (passed, 2.3s)
→ Artifact uploaded: screenshot.png (45KB)
```

### 3. API Health Check

Test your API connectivity:

```bash
# Using the TypeScript client
node -e "
const { createPlaywrightClient } = require('@test-results-platform/playwright-client');
const client = createPlaywrightClient({
  baseUrl: process.env.TEST_RESULTS_API_URL,
  authToken: process.env.TEST_RESULTS_API_TOKEN
});

client.healthCheck()
  .then(result => console.log('✓ API healthy:', result))
  .catch(err => console.error('✗ API error:', err.message));
"
```

## Sample Test with Tags

```typescript
// tests/auth.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should login successfully @smoke @auth', async ({ page }) => {
    await page.goto('/login');

    await page.fill('[data-testid="username"]', 'testuser@example.com');
    await page.fill('[data-testid="password"]', 'testpass123');

    await page.click('[data-testid="login-button"]');

    // This screenshot will be uploaded automatically on failure
    await expect(page).toHaveURL('/dashboard');
  });

  test('should handle invalid credentials @negative @auth', async ({ page }) => {
    await page.goto('/login');

    await page.fill('[data-testid="username"]', 'invalid@example.com');
    await page.fill('[data-testid="password"]', 'wrongpass');

    await page.click('[data-testid="login-button"]');

    await expect(page.locator('[data-testid="error-message"]'))
      .toContainText('Invalid credentials');
  });
});
```

## Advanced Configuration

### Custom Reporter Options

```typescript
// In playwright.config.ts reporter configuration
['@test-results-platform/playwright-reporter', {
  baseUrl: process.env.TEST_RESULTS_API_URL,
  authToken: process.env.TEST_RESULTS_API_TOKEN,

  // Artifact configuration
  uploadArtifacts: true,
  maxArtifactSize: 52428800, // 50MB
  artifactTypes: ['screenshot', 'video', 'trace'], // Skip logs

  // Performance tuning
  timeout: 45000,
  retries: 5,
  concurrentUploads: 3,

  // Custom metadata
  suiteNamePrefix: 'E2E Tests',
  defaultTags: ['automated', 'playwright'],

  // Error handling
  failOnUploadError: false,
  storeFailedRequests: true,

  // Debug options
  debug: true,
  logLevel: 'info' // 'debug', 'info', 'warn', 'error'
}]
```

### Programmatic Usage

```typescript
// For custom reporter implementations
import { createPlaywrightClient } from '@test-results-platform/playwright-client';

const client = createPlaywrightClient({
  baseUrl: 'https://api.test-results-platform.com',
  authToken: 'your-jwt-token',
  timeout: 30000,
  retries: 3
});

// Create test suite
const suite = await client.createTestSuite({
  name: 'Custom E2E Test Suite',
  framework: 'playwright',
  version: '1.55.0',
  testCount: 25,
  status: 'running',
  startTime: new Date().toISOString()
});

// Create environment
const environment = await client.createTestEnvironment({
  name: 'Desktop Chrome',
  browserName: 'chromium',
  browserVersion: '118.0.5993.70',
  os: 'linux'
});

// Create test result
const testResult = await client.createTestResult({
  suiteId: suite.id,
  environmentId: environment.id,
  title: 'should load homepage',
  fullTitle: 'Homepage › Layout › should load homepage',
  status: 'running',
  startTime: new Date().toISOString(),
  tags: ['smoke', 'homepage']
});
```

## Troubleshooting

### Common Issues

#### Authentication Errors
```
ERROR: Authentication failed (401)
```
- Verify your JWT token is valid and not expired
- Check the token has `test-results:write` scope
- Ensure the token is set in environment variables

#### Network Timeouts
```
ERROR: Request timeout after 30000ms
```
- Increase timeout in configuration: `timeout: 60000`
- Check network connectivity to API endpoint
- Verify API endpoint URL is correct

#### Artifact Upload Failures
```
WARN: Failed to upload screenshot.png: Network error
```
- Check S3/MinIO connectivity and permissions
- Verify artifact file exists and is readable
- Enable debug logging: `debug: true`

#### Rate Limiting
```
ERROR: Rate limit exceeded (429)
```
- Reduce concurrent uploads: `concurrentUploads: 1`
- Add retry backoff: `retries: 5`
- Contact platform admin for rate limit increase

### Debug Mode

Enable detailed logging:

```bash
TEST_RESULTS_DEBUG=true npx playwright test
```

This will show:
- API request/response details
- Artifact upload progress
- Error stack traces
- Performance metrics

### Manual Recovery

If tests fail to report due to API issues:

```bash
# Export failed requests log
cat .test-results-failed-requests.json

# Retry failed requests manually using CLI tool
npx @test-results-platform/replay-failed-requests .test-results-failed-requests.json
```

## What's Reported

The integration automatically captures:

### Test Metadata
- Test title and full title (including describe blocks)
- File location (path, line, column)
- Test duration and status
- Retry attempts
- Custom tags from test annotations

### Environment Information
- Browser name and version
- Operating system
- Viewport dimensions
- Device information (for mobile tests)

### Test Artifacts
- Screenshots (on failure or explicit capture)
- Videos (on failure or when configured)
- Trace files (for debugging)
- Console logs and network activity

### Real-time Events
- Test suite started/completed
- Individual test started/completed
- Progress updates during execution
- Error events and recovery attempts

This comprehensive setup ensures your Playwright tests provide rich, real-time insights into your test execution through the Test Results Platform.