# Automation Token Management

This guide covers the automation token management system for the Test Results Management API, including token generation, scoping, permissions, rotation policies, and CI/CD integration.

## Overview

Automation tokens provide secure, programmatic access to the Test Results Management API. They are designed specifically for CI/CD systems, automated testing pipelines, and other machine-to-machine integrations.

### Key Features

- 🔐 **Secure JWT-based tokens** with configurable expiration
- 🎯 **Scoped permissions** for principle of least privilege
- 🔄 **Token rotation** and lifecycle management
- 🤖 **CI/CD optimized** with GitHub Actions integration
- 📊 **Usage tracking** and audit capabilities
- 🛡️ **Automatic expiry** with configurable warnings

## Token Scopes

### Automation Scope (Recommended for CI/CD)

```bash
test-results-cli auth token generate \
  --name "GitHub Actions CI" \
  --scope automation \
  --expires-days 365
```

**Permissions:**
- `frameworks:read`, `frameworks:write`
- `environments:read`, `environments:write`
- `suites:read`, `suites:write`
- `results:read`, `results:write`
- `artifacts:read`, `artifacts:write`

**Use cases:**
- GitHub Actions workflows
- CI/CD pipelines
- Automated test result submission
- Build system integration

### Read-Only Scope

```bash
test-results-cli auth token generate \
  --name "Dashboard Reader" \
  --scope read-only \
  --expires-days 90
```

**Permissions:**
- `frameworks:read`
- `environments:read`
- `suites:read`
- `results:read`
- `artifacts:read`

**Use cases:**
- Monitoring dashboards
- Reporting tools
- Data analysis scripts
- Read-only integrations

### User Scope

```bash
test-results-cli auth token generate \
  --name "Admin Token" \
  --scope user \
  --expires-days 30
```

**Permissions:**
- Full CRUD access to all resources
- User management capabilities
- Administrative operations

**Use cases:**
- Administrative scripts
- Data migration tools
- Emergency access tokens

## CLI Installation and Setup

### Installation

```bash
# Install the CLI tool
pip install -e /path/to/test-results-api

# Or run directly from source
cd /path/to/test-results-api
python src/cli/main.py --help
```

### Configuration

```bash
# Create a profile for your environment
test-results-cli config profile create production \
  --api-endpoint https://test-results.your-company.com \
  --activate

# Check configuration status
test-results-cli auth status

# Run diagnostics
test-results-cli auth troubleshoot
```

## Token Generation

### Basic Token Generation

```bash
# Generate an automation token
test-results-cli auth token generate \
  --name "My CI Pipeline" \
  --scope automation

# Generate with custom expiration
test-results-cli auth token generate \
  --name "Short-term Token" \
  --scope automation \
  --expires-days 30

# Generate with specific permissions
test-results-cli auth token generate \
  --name "Results Only" \
  --scope automation \
  --permissions "results:write" \
  --permissions "artifacts:write"
```

### Output Formats

```bash
# Table format (default)
test-results-cli auth token generate --name "My Token"

# JSON output
test-results-cli auth token generate --name "My Token" --output json

# Token only (for scripting)
test-results-cli auth token generate --name "My Token" --output token
```

### Example Output

```
✅ Token generated successfully!

┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field       ┃ Value                                               ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Name        │ GitHub Actions CI                                   │
│ ID          │ auto_f4a7b2c8e9d3f1a6                               │
│ Scope       │ automation                                          │
│ Created     │ 2025-09-14 14:30:25                                │
│ Expires     │ 2026-09-14 14:30:25                                │
│ Permissions │ frameworks:read, frameworks:write, environments:... │
└─────────────┴─────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━ 🔑 Bearer Token ━━━━━━━━━━━━━━━━━━━━┓
┃ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdXRvX2Y0... ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━ Security Notice ━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚠️  Store this token securely - it won't be shown again!     ┃
┃ 💡 Add it to GitHub Secrets as TEST_RESULTS_TOKEN           ┃
┃ 🔒 This token grants access to your Test Results API        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Token Management

### List Tokens

```bash
# List all stored tokens
test-results-cli auth token list

# JSON format
test-results-cli auth token list --format json
```

### Validate Tokens

```bash
# Validate a token
test-results-cli auth token validate eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# JSON output
test-results-cli auth token validate <token> --format json
```

### Revoke Tokens

```bash
# Revoke a token by ID
test-results-cli auth token revoke auto_f4a7b2c8e9d3f1a6

# Skip confirmation
test-results-cli auth token revoke auto_f4a7b2c8e9d3f1a6 --yes
```

## GitHub Actions Integration

### Step 1: Generate Token

```bash
test-results-cli auth token generate \
  --name "GitHub Actions - $(git remote get-url origin)" \
  --scope automation \
  --expires-days 365 \
  --output token
```

### Step 2: Add to GitHub Secrets

1. Go to your repository settings
2. Navigate to **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `TEST_RESULTS_TOKEN`
5. Value: Paste the token from Step 1

### Step 3: Use in Workflows

```yaml
name: Test Results Integration
on: [push, pull_request]

jobs:
  playwright-tests:
    uses: ./.github/workflows/playwright-tests.yml
    with:
      api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
    secrets:
      automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
```

## Token Rotation Strategy

### Regular Rotation

```bash
#!/bin/bash
# Token rotation script

OLD_TOKEN_ID="auto_f4a7b2c8e9d3f1a6"
TOKEN_NAME="GitHub Actions CI"

# Generate new token
NEW_TOKEN=$(test-results-cli auth token generate \
  --name "$TOKEN_NAME" \
  --scope automation \
  --expires-days 365 \
  --output token)

echo "New token generated: $NEW_TOKEN"

# Update GitHub secret (requires GitHub CLI)
gh secret set TEST_RESULTS_TOKEN --body "$NEW_TOKEN"

# Revoke old token
test-results-cli auth token revoke "$OLD_TOKEN_ID" --yes

echo "Token rotation completed"
```

### Automated Rotation

```yaml
# .github/workflows/rotate-token.yml
name: Rotate API Token
on:
  schedule:
    - cron: '0 2 1 */3 *'  # Every 3 months

jobs:
  rotate-token:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install CLI
        run: pip install -e .

      - name: Generate new token
        id: new-token
        run: |
          TOKEN=$(python src/cli/main.py auth token generate \
            --name "GitHub Actions (Auto-rotated)" \
            --scope automation \
            --expires-days 90 \
            --output token)
          echo "token=$TOKEN" >> $GITHUB_OUTPUT

      - name: Update repository secret
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.actions.createOrUpdateRepoSecret({
              owner: context.repo.owner,
              repo: context.repo.repo,
              secret_name: 'TEST_RESULTS_TOKEN',
              encrypted_value: '${{ steps.new-token.outputs.token }}'
            });
```

## Security Best Practices

### Token Storage

- ✅ **Store in GitHub Secrets**: Never commit tokens to code
- ✅ **Use environment-specific tokens**: Different tokens for dev/staging/prod
- ✅ **Limit scope**: Use minimal required permissions
- ✅ **Set expiration**: Regularly rotate tokens

### Token Permissions

```bash
# Good: Minimal permissions for CI
test-results-cli auth token generate \
  --name "CI Results Only" \
  --permissions "results:write" \
  --permissions "artifacts:write" \
  --expires-days 90

# Avoid: Overly broad permissions
test-results-cli auth token generate \
  --name "CI Token" \
  --scope user \
  --expires-days 365
```

### Monitoring and Auditing

```bash
# Check token status regularly
test-results-cli auth token list

# Validate tokens are working
test-results-cli auth token validate $TEST_RESULTS_TOKEN

# Check system status
test-results-cli auth status
```

## Integration Examples

### Custom CI System

```bash
#!/bin/bash
# CI script example

# Set up environment
export TEST_RESULTS_TOKEN="your-automation-token"
export TEST_RESULTS_API="https://test-results.example.com"

# Run tests (Playwright example)
npx playwright test --reporter=json --output-file=results.json

# Submit results using the GitHub Action logic
python -c "
import json
import requests

# Read results
with open('results.json') as f:
    results = json.load(f)

# Submit to API
headers = {'Authorization': f'Bearer {os.environ[\"TEST_RESULTS_TOKEN\"]}'}
response = requests.post(
    f'{os.environ[\"TEST_RESULTS_API\"]}/api/v1/results',
    json=results,
    headers=headers
)
print(f'Results submitted: {response.status_code}')
"
```

### Jenkins Integration

```groovy
pipeline {
    agent any
    environment {
        TEST_RESULTS_TOKEN = credentials('test-results-token')
        TEST_RESULTS_API = 'https://test-results.example.com'
    }
    stages {
        stage('Test') {
            steps {
                sh 'npx playwright test --reporter=json'
            }
            post {
                always {
                    script {
                        // Submit results using CLI
                        sh '''
                            test-results-cli auth token validate $TEST_RESULTS_TOKEN
                            # Custom submission logic here
                        '''
                    }
                }
            }
        }
    }
}
```

### Docker Integration

```dockerfile
# Dockerfile for CI image with CLI
FROM node:20-alpine

RUN apk add --no-cache python3 py3-pip

# Install test-results-cli
COPY . /app
WORKDIR /app
RUN pip install -e .

# Install testing dependencies
RUN npm install

# Entry point script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

```bash
#!/bin/bash
# entrypoint.sh

# Validate token
test-results-cli auth token validate $TEST_RESULTS_TOKEN

# Run tests
npm run test:ci

# Results are automatically submitted via GitHub Actions
```

## Troubleshooting

### Common Issues

1. **Token Expired**
   ```bash
   # Check token status
   test-results-cli auth token validate $TOKEN

   # Generate new token
   test-results-cli auth token generate --name "Replacement" --scope automation
   ```

2. **Insufficient Permissions**
   ```bash
   # Check current permissions
   test-results-cli auth token validate $TOKEN --format json

   # Generate token with specific permissions
   test-results-cli auth token generate \
     --name "Custom Permissions" \
     --permissions "results:write" \
     --permissions "artifacts:read"
   ```

3. **API Connection Issues**
   ```bash
   # Check system status
   test-results-cli auth status

   # Run diagnostics
   test-results-cli auth troubleshoot

   # Validate configuration
   test-results-cli config show
   ```

### Debug Mode

```bash
# Enable verbose logging
test-results-cli --verbose auth token generate --name "Debug Token"

# Check configuration
test-results-cli --verbose auth status

# Validate with details
test-results-cli --verbose auth token validate $TOKEN
```

## API Reference

### Token Claims Structure

```json
{
  "sub": "auto_f4a7b2c8e9d3f1a6",
  "exp": 1725456625,
  "scope": "automation",
  "token_type": "automation",
  "username": "GitHub Actions CI",
  "email": "auto_f4a7b2c8e9d3f1a6@automation.local",
  "permissions": [
    "frameworks:read",
    "frameworks:write",
    "environments:read",
    "environments:write",
    "suites:read",
    "suites:write",
    "results:read",
    "results:write",
    "artifacts:read",
    "artifacts:write"
  ],
  "metadata": {
    "created_by": "cli",
    "token_name": "GitHub Actions CI",
    "created_at": "2025-09-14T14:30:25.123456Z"
  }
}
```

### Authentication Headers

```bash
# Using the token in API requests
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     -H "Content-Type: application/json" \
     https://test-results.example.com/api/v1/results
```

For more information, see:
- [GitHub Actions Integration Guide](github-actions-integration.md)
- [API Authentication Reference](api-authentication.md)
- [Security Best Practices](security-guide.md)