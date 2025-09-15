# Security Policy

## Supported Versions

We actively maintain security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Email security concerns to: [maintainer-email]
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Measures

### CI/CD Security

Our GitHub Actions workflows implement several security measures:

#### Fork Safety
- **Fork-Safe CI**: Basic checks run on all PRs, including forks, without secrets
- **Trusted Workflows**: Workflows with secrets only run on trusted repositories
- **Pull Request Target**: Used for workflows that need write permissions on forks

#### Token Security
- Workflows use minimal required permissions
- `GITHUB_TOKEN` permissions are explicitly scoped
- No secrets are passed to forked repositories
- Repository owner checks prevent unauthorized workflow runs

#### Workflow Patterns
```yaml
# ✅ Safe for forks - no secrets
on: pull_request

# ⚠️ Only for trusted repositories
on: pull_request_target
if: github.event.pull_request.head.repo.full_name == github.repository

# ✅ Scheduled/push workflows with repository owner check
if: github.repository_owner == 'saturninoabril'
```

### Code Security

#### Dependencies
- Automated dependency updates via Dependabot
- Security vulnerability scanning with Trivy
- Safety checks for known Python vulnerabilities
- Regular security audits via CodeQL

#### Secrets Management
- Environment variables for configuration
- No hardcoded secrets in code
- Database credentials via environment variables
- S3/MinIO credentials via environment variables

#### Authentication
- JWT-based authentication with GitHub SSO
- Token expiration and rotation
- Scoped permissions for API access
- Rate limiting on API endpoints

## Security Best Practices for Contributors

### Code Contributions

1. **Never commit secrets**:
   ```bash
   # ❌ Bad
   DATABASE_URL = "postgresql://user:password@localhost/db"

   # ✅ Good
   DATABASE_URL = os.getenv("DATABASE_URL")
   ```

2. **Use environment variables**:
   ```python
   # ✅ Proper configuration
   import os
   from pydantic import BaseSettings

   class Settings(BaseSettings):
       database_url: str
       secret_key: str

       class Config:
           env_file = ".env"
   ```

3. **Validate inputs**:
   ```python
   # ✅ Input validation
   from pydantic import BaseModel, validator

   class TestResult(BaseModel):
       name: str

       @validator('name')
       def validate_name(cls, v):
           if not v or len(v) > 255:
               raise ValueError('Invalid name')
           return v
   ```

### Workflow Contributions

1. **Never add secrets to workflows**:
   ```yaml
   # ❌ Never do this
   - name: Bad example
     env:
       SECRET: "hardcoded-secret"

   # ✅ Use repository secrets
   - name: Good example
     env:
       SECRET: ${{ secrets.SECRET_NAME }}
   ```

2. **Use minimal permissions**:
   ```yaml
   # ✅ Explicit minimal permissions
   permissions:
     contents: read
     pull-requests: write
   ```

3. **Check for fork safety**:
   ```yaml
   # ✅ Fork-safe condition
   if: github.event.pull_request.head.repo.full_name == github.repository
   ```

### Database Security

1. **Use parameterized queries**:
   ```python
   # ✅ Safe from SQL injection
   result = await session.execute(
       select(TestResult).where(TestResult.id == test_id)
   )
   ```

2. **Connection security**:
   ```python
   # ✅ SSL and proper connection handling
   DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"
   ```

### API Security

1. **Authentication required**:
   ```python
   # ✅ Protect endpoints
   @router.get("/results/{id}")
   async def get_result(
       id: int,
       current_user: User = Depends(get_current_user)
   ):
   ```

2. **Rate limiting**:
   ```python
   # ✅ Implement rate limiting
   from slowapi import Limiter

   @limiter.limit("100/minute")
   async def api_endpoint():
   ```

## Incident Response

In case of a security incident:

1. **Immediate Response**:
   - Assess the scope and impact
   - Contain the incident
   - Document everything

2. **Communication**:
   - Notify security team
   - Prepare public disclosure (if needed)
   - Update affected users

3. **Recovery**:
   - Apply security patches
   - Validate fixes
   - Monitor for additional issues

4. **Post-Incident**:
   - Conduct retrospective
   - Update security measures
   - Document lessons learned

## Security Tools and Scanning

The repository uses multiple security scanning tools:

- **Trivy**: Container and dependency vulnerability scanning
- **Bandit**: Python security linting
- **Safety**: Python dependency vulnerability checking
- **CodeQL**: Semantic code analysis
- **Ruff**: Code quality and security patterns

## Security Contact

For security-related questions or concerns:
- Create a GitHub issue (for non-sensitive topics)
- Email: [maintainer-email] (for sensitive security issues)

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers who help improve our security posture.