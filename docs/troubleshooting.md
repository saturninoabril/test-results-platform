# Troubleshooting Guide

## Overview

This guide covers common issues, debugging techniques, and solutions for the Test Results Management API. It's organized by problem category to help you quickly find and resolve issues.

## Quick Diagnostic Commands

### Health Check
```bash
# Check overall API health
curl http://localhost:8000/health

# Detailed health check with component status
curl http://localhost:8000/health/detailed

# Readiness check (for load balancers)
curl http://localhost:8000/health/ready
```

### CLI Diagnostics
```bash
# Test database connection
test-results-cli db status

# Test storage connection
test-results-cli storage health

# Validate authentication setup
test-results-cli auth validate-token --token YOUR_TOKEN

# Check system configuration
test-results-cli config check
```

## Database Issues

### Connection Problems

**Symptoms:**
- `ConnectionError: connection to server at "localhost" failed`
- `FATAL: password authentication failed for user "testresults"`
- API returns 500 errors on all requests

**Diagnostics:**
```bash
# Test database connection directly
psql -h localhost -U testresults -d testresults -c "SELECT version();"

# Check connection pool status
curl http://localhost:8000/health/detailed | jq '.database.connection_pool'

# Review database logs
docker logs postgres-container | tail -50

# Check if database is accepting connections
nc -zv localhost 5432
```

**Common Solutions:**

1. **Wrong credentials:**
```bash
# Check environment variables
echo $DATABASE_URL
# Should be: postgresql+asyncpg://user:password@host:port/database

# Update credentials
export DATABASE_URL="postgresql+asyncpg://testresults:newpassword@localhost:5432/testresults"
```

2. **Database not running:**
```bash
# Start PostgreSQL (Docker)
docker-compose up -d postgres

# Start PostgreSQL (system service)
sudo systemctl start postgresql
```

3. **Connection pool exhaustion:**
```bash
# Check active connections
psql -h localhost -U testresults -d testresults -c "
SELECT state, count(*)
FROM pg_stat_activity
WHERE datname = 'testresults'
GROUP BY state;"

# Kill idle connections
psql -h localhost -U testresults -d testresults -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'testresults'
AND state = 'idle'
AND state_change < current_timestamp - interval '5 minutes';"
```

### Migration Issues

**Symptoms:**
- `alembic.script.revision.ResolutionError: Can't locate revision`
- `sqlalchemy.exc.ProgrammingError: relation does not exist`
- Tables missing after deployment

**Diagnostics:**
```bash
# Check migration status
uv run alembic current

# Show migration history
uv run alembic history

# Check if alembic_version table exists
psql -h localhost -U testresults -d testresults -c "SELECT * FROM alembic_version;"
```

**Solutions:**

1. **Initialize alembic (first time setup):**
```bash
# Stamp current state
uv run alembic stamp head

# Run migrations
uv run alembic upgrade head
```

2. **Reset migrations (development only):**
```bash
# Drop all tables
psql -h localhost -U testresults -d testresults -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migrations
uv run alembic upgrade head
```

3. **Fix revision conflicts:**
```bash
# Show divergent revisions
uv run alembic branches

# Create merge revision
uv run alembic merge -m "Merge migrations" revision1 revision2

# Apply merge
uv run alembic upgrade head
```

### Performance Issues

**Symptoms:**
- Slow query response times
- High CPU usage on database server
- Connection timeouts

**Diagnostics:**
```bash
# Find slow queries
psql -h localhost -U testresults -d testresults -c "
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# Check database size and activity
psql -h localhost -U testresults -d testresults -c "
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY tablename, attname;"

# Monitor active queries
psql -h localhost -U testresults -d testresults -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
```

**Solutions:**

1. **Add missing indexes:**
```sql
-- Common indexes for performance
CREATE INDEX CONCURRENTLY idx_test_results_suite_status
ON test_results(suite_id, status);

CREATE INDEX CONCURRENTLY idx_test_results_tags
ON test_results USING GIN(tags);

CREATE INDEX CONCURRENTLY idx_test_suites_started_at
ON test_suites(started_at DESC);

CREATE INDEX CONCURRENTLY idx_test_artifacts_result_type
ON test_artifacts(result_id, type);
```

2. **Optimize queries:**
```python
# Use select_related to avoid N+1 queries
from sqlalchemy.orm import selectinload

# Instead of:
results = await db.execute(select(TestResult))

# Use:
results = await db.execute(
    select(TestResult)
    .options(selectinload(TestResult.artifacts))
)
```

3. **Configure connection pooling:**
```python
# In database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Increase pool size
    max_overflow=30,       # Allow overflow
    pool_timeout=30,       # Timeout for getting connection
    pool_recycle=3600,     # Recycle connections hourly
    pool_pre_ping=True     # Validate connections
)
```

## Storage Issues

### S3/MinIO Connection Problems

**Symptoms:**
- `NoCredentialsError: Unable to locate credentials`
- `EndpointConnectionError: Could not connect to the endpoint URL`
- File uploads fail with 403 Forbidden

**Diagnostics:**
```bash
# Test S3 connection
aws s3 ls s3://your-bucket-name/ --endpoint-url=https://your-endpoint

# Test MinIO connection
mc ls minio/your-bucket-name/

# Check storage health via CLI
test-results-cli storage health

# Test file operations
test-results-cli storage list --prefix artifacts/
```

**Solutions:**

1. **AWS S3 credentials:**
```bash
# Check AWS credentials
aws configure list

# Set credentials via environment
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-west-2

# Or use AWS credentials file
aws configure
```

2. **MinIO setup:**
```bash
# Configure MinIO client
mc config host add minio http://localhost:9000 minioadmin minioadmin123

# Create bucket
mc mb minio/test-results-artifacts

# Set bucket policy for public read (if needed)
mc policy set public minio/test-results-artifacts
```

3. **Bucket permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT:user/test-results-api"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT:user/test-results-api"
      },
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::your-bucket-name"
    }
  ]
}
```

### Upload/Download Failures

**Symptoms:**
- Large file uploads timeout
- Downloads return corrupted files
- Out of disk space errors

**Diagnostics:**
```bash
# Check disk space
df -h

# Monitor storage operations
test-results-cli storage monitor --duration 60

# Check upload progress
curl -X POST http://localhost:8000/v1/artifacts \
  -F "result_id=test-123" \
  -F "name=large-file.mp4" \
  -F "type=video" \
  -F "file=@large-file.mp4" \
  --progress-bar

# Validate file integrity
test-results-cli storage validate --path artifacts/2024/01/15/
```

**Solutions:**

1. **Increase timeouts:**
```python
# In storage.py
import httpx

# Increase timeout for large uploads
timeout = httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)
```

2. **Implement chunked uploads:**
```python
# For large files, use multipart upload
async def upload_large_file(file_path: str, storage_path: str):
    client = get_storage_client()
    async with client:
        if os.path.getsize(file_path) > 100 * 1024 * 1024:  # 100MB
            # Use multipart upload
            return await client.upload_multipart(file_path, storage_path)
        else:
            return await client.upload_file(file_path, storage_path)
```

3. **Add retry logic:**
```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def upload_with_retry(file_path: str, storage_path: str):
    client = get_storage_client()
    async with client:
        return await client.upload_file(file_path, storage_path)
```

## Authentication Issues

### JWT Token Problems

**Symptoms:**
- `401 Unauthorized` responses
- `Invalid token` errors
- Tokens expire unexpectedly

**Diagnostics:**
```bash
# Decode JWT token (without validation)
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | jq

# Validate token via CLI
test-results-cli auth validate-token --token YOUR_TOKEN

# Check token expiration
test-results-cli auth token-info --token YOUR_TOKEN

# Test API with token
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/v1/frameworks
```

**Solutions:**

1. **Token expired:**
```bash
# Generate new user token
test-results-cli auth login

# Generate new automation token
test-results-cli auth generate-token \
  --name "CI Pipeline" \
  --scope write \
  --expires-days 365
```

2. **Wrong JWT secret:**
```bash
# Verify JWT_SECRET_KEY is consistent
echo $JWT_SECRET_KEY

# Regenerate all tokens after changing secret
test-results-cli auth revoke-all-tokens
```

3. **Token format issues:**
```python
# Ensure proper Bearer format
headers = {
    "Authorization": f"Bearer {token}"  # Note the space after "Bearer"
}

# Not:
headers = {
    "Authorization": f"Bearer{token}"   # Missing space - will fail
}
```

### GitHub OAuth Issues

**Symptoms:**
- OAuth redirect fails
- GitHub login returns errors
- User information not retrieved

**Diagnostics:**
```bash
# Check GitHub OAuth configuration
curl -X GET "https://api.github.com/user" \
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN"

# Test OAuth flow manually
curl -X POST "https://github.com/login/oauth/access_token" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "code=AUTHORIZATION_CODE" \
  -H "Accept: application/json"
```

**Solutions:**

1. **Update GitHub OAuth app settings:**
```
Application name: Test Results API
Homepage URL: https://your-domain.com
Authorization callback URL: https://your-domain.com/auth/github/callback
```

2. **Verify environment variables:**
```bash
export GITHUB_CLIENT_ID=your_client_id
export GITHUB_CLIENT_SECRET=your_client_secret
export GITHUB_REDIRECT_URI=https://your-domain.com/auth/github/callback
```

3. **Handle OAuth errors:**
```python
# In auth.py
async def handle_github_callback(code: str, state: str, error: str = None):
    if error:
        # Handle OAuth errors
        if error == "access_denied":
            return {"error": "User denied access"}
        else:
            return {"error": f"OAuth error: {error}"}

    # Continue with normal flow
    token_data = await github.exchange_code(code, state)
    # ...
```

## API Performance Issues

### High Response Times

**Symptoms:**
- Requests take longer than 1 second
- Timeout errors in client applications
- High server CPU usage

**Diagnostics:**
```bash
# Measure response times
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:8000/v1/suites

# Load test specific endpoints
ab -n 1000 -c 10 http://localhost:8000/v1/frameworks

# Monitor system resources
top -p $(pgrep -f "uvicorn")
iostat -x 1

# Check FastAPI metrics (if enabled)
curl http://localhost:8000/metrics
```

**Solutions:**

1. **Enable query optimization:**
```python
# Add database indexes
# Use query batching
# Implement result pagination

@app.get("/v1/results")
async def get_results(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    suite_id: str = None,
    db: AsyncSession = Depends(get_db_session)
):
    query = select(TestResult)
    if suite_id:
        query = query.where(TestResult.suite_id == suite_id)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
```

2. **Add caching:**
```python
from functools import lru_cache
import redis.asyncio as redis

# In-memory caching for static data
@lru_cache(maxsize=128)
async def get_frameworks():
    # Cache framework list
    pass

# Redis caching for dynamic data
redis_client = redis.from_url("redis://localhost:6379")

async def get_suite_with_cache(suite_id: str):
    cached = await redis_client.get(f"suite:{suite_id}")
    if cached:
        return json.loads(cached)

    # Fetch from database
    suite = await get_suite_from_db(suite_id)
    await redis_client.setex(f"suite:{suite_id}", 300, json.dumps(suite))
    return suite
```

3. **Optimize worker configuration:**
```bash
# In Docker or systemd service
uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --max-requests 1000 \
  --max-requests-jitter 50
```

### Memory Issues

**Symptoms:**
- Out of memory errors
- High memory usage
- Process killed by system

**Diagnostics:**
```bash
# Monitor memory usage
ps aux | grep uvicorn
cat /proc/$(pgrep uvicorn)/status | grep -i mem

# Check for memory leaks
valgrind --tool=memcheck --leak-check=full python -m uvicorn src.main:app

# Monitor garbage collection
import gc
print(f"Objects before: {len(gc.get_objects())}")
gc.collect()
print(f"Objects after: {len(gc.get_objects())}")
```

**Solutions:**

1. **Optimize database sessions:**
```python
# Close sessions properly
async def get_results():
    async with get_db_session() as db:
        # Use session
        result = await db.execute(query)
        return result.scalars().all()
    # Session automatically closed
```

2. **Process large files in chunks:**
```python
async def process_large_file(file_path: str):
    chunk_size = 8192
    async with aiofiles.open(file_path, 'rb') as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            # Process chunk
            await process_chunk(chunk)
```

3. **Set memory limits:**
```python
# In Docker
FROM python:3.13-slim
ENV PYTHONMALLOC=malloc
ENV MALLOC_MMAP_THRESHOLD_=128
ENV MALLOC_TRIM_THRESHOLD_=128

# Limit worker memory
uvicorn src.main:app --limit-memory 512MB
```

## GitHub Actions Integration Issues

### Token Authentication

**Symptoms:**
- GitHub Actions workflows fail with 401 errors
- Token not recognized by API
- Permission denied errors

**Diagnostics:**
```yaml
# Add debugging to workflow
- name: Debug Token
  run: |
    echo "Token length: ${#TEST_RESULTS_TOKEN}"
    curl -v -H "Authorization: Bearer $TEST_RESULTS_TOKEN" \
      ${{ vars.TEST_RESULTS_API_ENDPOINT }}/health

# Check token permissions
- name: Validate Token
  run: |
    test-results-cli auth validate-token --token $TEST_RESULTS_TOKEN
```

**Solutions:**

1. **Verify token is in secrets:**
```bash
# GitHub repository settings
Settings > Secrets and variables > Actions
# Add TEST_RESULTS_TOKEN as repository secret
```

2. **Check token scope:**
```bash
# Generate token with correct scope
test-results-cli auth generate-token \
  --name "GitHub Actions - MyRepo" \
  --scope write \
  --expires-days 365
```

3. **Update workflow syntax:**
```yaml
# Correct way to use secrets
env:
  TEST_RESULTS_TOKEN: ${{ secrets.TEST_RESULTS_TOKEN }}

# Not:
env:
  TEST_RESULTS_TOKEN: "${{ secrets.TEST_RESULTS_TOKEN }}"  # Extra quotes
```

### Artifact Upload Issues

**Symptoms:**
- Artifacts not uploaded to API
- Large artifacts timeout
- File path not found errors

**Diagnostics:**
```yaml
- name: Debug Artifacts
  run: |
    find . -name "test-results*" -type f
    ls -la test-results/
    du -sh test-results/

- name: Test API Connection
  run: |
    curl -f ${{ vars.TEST_RESULTS_API_ENDPOINT }}/health
```

**Solutions:**

1. **Fix artifact paths:**
```yaml
- name: Run Tests
  run: npx playwright test --reporter=json --output-dir=test-results

- name: Submit Results
  if: always()
  uses: ./.github/actions/submit-test-results
  with:
    api-endpoint: ${{ vars.TEST_RESULTS_API_ENDPOINT }}
    automation-token: ${{ secrets.TEST_RESULTS_TOKEN }}
    results-path: test-results/results.json  # Correct path
    artifacts-path: test-results/             # Directory with artifacts
```

2. **Handle large artifacts:**
```yaml
- name: Compress Large Artifacts
  if: always()
  run: |
    cd test-results
    for video in *.webm; do
      if [[ $(stat -f%z "$video" 2>/dev/null || stat -c%s "$video") -gt 52428800 ]]; then
        echo "Compressing $video"
        ffmpeg -i "$video" -c:v libx264 -crf 28 "compressed_${video%.webm}.mp4"
        rm "$video"
      fi
    done
```

3. **Add retry logic:**
```yaml
- name: Submit Results with Retry
  if: always()
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 10
    max_attempts: 3
    command: |
      ./.github/actions/submit-test-results/submit.sh \
        "${{ vars.TEST_RESULTS_API_ENDPOINT }}" \
        "${{ secrets.TEST_RESULTS_TOKEN }}" \
        "test-results/results.json"
```

## CLI Tool Issues

### Installation Problems

**Symptoms:**
- `command not found: test-results-cli`
- ImportError when running CLI
- Permission denied errors

**Diagnostics:**
```bash
# Check if CLI is installed
which test-results-cli
echo $PATH

# Test import
python -c "import src.cli.main; print('OK')"

# Check permissions
ls -la $(which test-results-cli)
```

**Solutions:**

1. **Install in development mode:**
```bash
# From project root
uv sync
uv pip install -e .

# Verify installation
test-results-cli --version
```

2. **Use direct Python execution:**
```bash
# If CLI not in PATH
python -m src.cli.main --help

# Or with uv
uv run python -m src.cli.main --help
```

3. **Fix PATH issues:**
```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Reload shell
source ~/.bashrc
```

### Configuration Issues

**Symptoms:**
- CLI can't find configuration
- Database connection errors
- Storage access denied

**Diagnostics:**
```bash
# Check configuration
test-results-cli config show

# Test connections
test-results-cli db status
test-results-cli storage health

# Debug with verbose output
test-results-cli --verbose config check
```

**Solutions:**

1. **Create configuration file:**
```bash
# ~/.test-results-cli/config.yaml
database:
  url: "postgresql+asyncpg://user:pass@localhost/testresults"

storage:
  type: "s3"
  endpoint: "https://s3.amazonaws.com"
  access_key: "your-access-key"
  secret_key: "your-secret-key"
  bucket: "test-results-artifacts"

api:
  endpoint: "https://api.testresults.dev/v1"
  token: "your-api-token"
```

2. **Use environment variables:**
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/testresults"
export STORAGE_ACCESS_KEY="your-access-key"
export STORAGE_SECRET_KEY="your-secret-key"
export API_TOKEN="your-api-token"
```

3. **Initialize CLI:**
```bash
# First-time setup
test-results-cli init --interactive

# Or non-interactive
test-results-cli init \
  --database-url "postgresql+asyncpg://user:pass@localhost/testresults" \
  --storage-type s3 \
  --storage-endpoint "https://s3.amazonaws.com"
```

## Monitoring and Alerting

### Log Analysis

**Common Error Patterns:**
```bash
# Database connection errors
grep -i "connection.*refused\|timeout" /var/log/test-results-api/app.log

# Authentication failures
grep -i "401\|unauthorized\|invalid.*token" /var/log/test-results-api/app.log

# Storage errors
grep -i "s3\|storage\|upload.*failed" /var/log/test-results-api/app.log

# Performance issues
grep -i "slow.*query\|timeout\|503" /var/log/test-results-api/app.log
```

### Metrics and Monitoring

**Key Metrics to Monitor:**
```python
# Response time percentiles
api_request_duration_p95 > 1.0  # Alert if p95 > 1 second

# Error rates
rate(api_requests_total{status_code=~"5.."}[5m]) > 0.1  # >10% error rate

# Database connections
db_connections_active / db_connections_max > 0.8  # >80% pool usage

# Storage operations
increase(storage_operations_total{status="error"}[5m]) > 10  # Storage issues

# Memory usage
process_resident_memory_bytes > 512 * 1024 * 1024  # >512MB memory
```

### Health Check Automation

```bash
#!/bin/bash
# health-check.sh - Run comprehensive health checks

echo "=== API Health Check ==="
curl -f http://localhost:8000/health/detailed || exit 1

echo "=== Database Health Check ==="
test-results-cli db status || exit 1

echo "=== Storage Health Check ==="
test-results-cli storage health || exit 1

echo "=== Authentication Check ==="
test-results-cli auth validate-token --token $API_TOKEN || exit 1

echo "All checks passed!"
```

## Getting Help

### Debug Information Collection

When reporting issues, include this diagnostic information:

```bash
#!/bin/bash
# collect-debug-info.sh

echo "=== System Information ==="
uname -a
python --version
docker --version

echo "=== API Status ==="
curl -s http://localhost:8000/health/detailed | jq

echo "=== Environment Variables ==="
env | grep -E "(DATABASE|STORAGE|JWT|GITHUB)_" | sed 's/=.*/=***/'

echo "=== Database Status ==="
test-results-cli db status

echo "=== Storage Status ==="
test-results-cli storage health

echo "=== Recent Logs ==="
tail -50 /var/log/test-results-api/app.log

echo "=== Docker Container Status ==="
docker ps | grep test-results

echo "=== Resource Usage ==="
df -h
free -h
ps aux | grep -E "(uvicorn|postgres|minio)" | head -10
```

### Support Channels

1. **GitHub Issues**: Report bugs and feature requests
   - Include debug information from script above
   - Provide minimal reproduction case
   - Specify environment (Docker, Kubernetes, etc.)

2. **Documentation**: Check comprehensive guides
   - API Reference: `/docs/api-reference.md`
   - Deployment Guide: `/docs/deployment-guide.md`
   - Library Documentation: `/docs/library-documentation.md`

### Common Debugging Workflow

1. **Check health endpoints** - Start with basic connectivity
2. **Review logs** - Look for error patterns and stack traces
3. **Test individual components** - Database, storage, authentication
4. **Verify configuration** - Environment variables, config files
5. **Check network connectivity** - Firewalls, DNS resolution
6. **Monitor resources** - CPU, memory, disk space
7. **Test with minimal setup** - Isolate the problem
8. **Collect debug information** - Prepare detailed issue report

This troubleshooting guide provides systematic approaches to diagnosing and resolving common issues with the Test Results Management API. Always start with the health checks and work through the diagnostic commands before attempting solutions.