# Deployment Guide

## Overview

This guide covers deploying the Test Results Management API to production environments. The API is designed to run in containerized environments with PostgreSQL and S3-compatible storage.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Load Balancer │───▶│   FastAPI App    │───▶│   PostgreSQL    │
│   (nginx/ALB)   │    │   (containers)   │    │   (RDS/managed) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   S3 Storage    │
                       │   (AWS S3/MinIO)│
                       └─────────────────┘
```

## Prerequisites

- Docker and Docker Compose (for local deployment)
- Kubernetes cluster (for production deployment)
- PostgreSQL 17+ database
- S3-compatible storage (AWS S3, MinIO, etc.)
- Domain name with SSL certificate
- GitHub OAuth application (for authentication)

## Environment Configuration

### Required Environment Variables

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Storage Configuration
STORAGE_TYPE=s3  # or 'minio' for development
STORAGE_ENDPOINT=https://s3.amazonaws.com
STORAGE_ACCESS_KEY=your-access-key
STORAGE_SECRET_KEY=your-secret-key
STORAGE_BUCKET=test-results-artifacts
STORAGE_REGION=us-west-2

# Authentication Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# GitHub OAuth Configuration
GITHUB_CLIENT_ID=your-github-app-client-id
GITHUB_CLIENT_SECRET=your-github-app-client-secret
GITHUB_REDIRECT_URI=https://your-domain.com/auth/github/callback

# API Configuration
API_TITLE="Test Results Management API"
API_VERSION=1.0.0
API_ENVIRONMENT=production
CORS_ORIGINS=["https://your-frontend.com"]

# Performance Configuration
WORKERS=4  # Number of Uvicorn workers
MAX_REQUESTS_PER_SECOND=1000
MAX_UPLOAD_SIZE_MB=100

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
STRUCTURED_LOGGING=true

# Health Check Configuration
HEALTH_CHECK_TIMEOUT=30
DATABASE_HEALTH_CHECK_QUERY="SELECT 1"
```

## Docker Deployment

### Using Docker Compose

1. **Create docker-compose.prod.yml**:

```yaml
version: '3.8'

services:
  api:
    image: test-results-api:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://testresults:${DB_PASSWORD}@postgres:5432/testresults
      - STORAGE_TYPE=s3
      - STORAGE_ENDPOINT=${STORAGE_ENDPOINT}
      - STORAGE_ACCESS_KEY=${STORAGE_ACCESS_KEY}
      - STORAGE_SECRET_KEY=${STORAGE_SECRET_KEY}
      - STORAGE_BUCKET=${STORAGE_BUCKET}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
      - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
    depends_on:
      - postgres
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  postgres:
    image: postgres:17
    environment:
      - POSTGRES_DB=testresults
      - POSTGRES_USER=testresults
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/db/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U testresults"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
```

2. **Create environment file (.env.prod)**:

```bash
DB_PASSWORD=your-secure-db-password
STORAGE_ENDPOINT=https://s3.us-west-2.amazonaws.com
STORAGE_ACCESS_KEY=your-aws-access-key
STORAGE_SECRET_KEY=your-aws-secret-key
STORAGE_BUCKET=your-s3-bucket-name
JWT_SECRET_KEY=your-super-secret-jwt-key-at-least-32-characters-long
GITHUB_CLIENT_ID=your-github-oauth-app-client-id
GITHUB_CLIENT_SECRET=your-github-oauth-app-client-secret
```

3. **Create Nginx configuration (nginx.conf)**:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=upload:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000";

        # File upload size limit
        client_max_body_size 100M;

        # API endpoints
        location /v1/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeout settings
            proxy_read_timeout 300;
            proxy_connect_timeout 30;
            proxy_send_timeout 300;
        }

        # Upload endpoints with special rate limiting
        location /v1/artifacts {
            limit_req zone=upload burst=5 nodelay;
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Extended timeout for uploads
            proxy_read_timeout 600;
            proxy_connect_timeout 30;
            proxy_send_timeout 600;
        }

        # Health check
        location /health {
            proxy_pass http://api;
            access_log off;
        }
    }
}
```

4. **Deploy**:

```bash
# Build the Docker image
docker build -t test-results-api:latest .

# Deploy with docker-compose
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Run database migrations
docker-compose -f docker-compose.prod.yml exec api uv run alembic upgrade head

# Check deployment status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs api
```

## Kubernetes Deployment

### Prerequisites

```bash
# Create namespace
kubectl create namespace test-results

# Create secrets
kubectl create secret generic api-secrets \
  --from-literal=database-url="postgresql+asyncpg://user:pass@host:port/db" \
  --from-literal=jwt-secret-key="your-secret-key" \
  --from-literal=storage-access-key="your-access-key" \
  --from-literal=storage-secret-key="your-secret-key" \
  --from-literal=github-client-secret="your-github-secret" \
  --namespace=test-results
```

### Deployment Manifests

**deployment.yaml**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-results-api
  namespace: test-results
  labels:
    app: test-results-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: test-results-api
  template:
    metadata:
      labels:
        app: test-results-api
    spec:
      containers:
      - name: api
        image: test-results-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: database-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: jwt-secret-key
        - name: STORAGE_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: storage-access-key
        - name: STORAGE_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: storage-secret-key
        - name: GITHUB_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: github-client-secret
        - name: STORAGE_TYPE
          value: "s3"
        - name: STORAGE_ENDPOINT
          value: "https://s3.us-west-2.amazonaws.com"
        - name: STORAGE_BUCKET
          value: "test-results-artifacts"
        - name: GITHUB_CLIENT_ID
          value: "your-github-client-id"
        - name: API_ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: test-results-api-service
  namespace: test-results
spec:
  selector:
    app: test-results-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-results-api-ingress
  namespace: test-results
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  tls:
  - hosts:
    - api.testresults.dev
    secretName: test-results-tls
  rules:
  - host: api.testresults.dev
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: test-results-api-service
            port:
              number: 80
```

**Deploy to Kubernetes**:

```bash
# Apply manifests
kubectl apply -f deployment.yaml

# Run database migrations
kubectl exec -it deployment/test-results-api -n test-results -- uv run alembic upgrade head

# Check deployment status
kubectl get pods -n test-results
kubectl logs -f deployment/test-results-api -n test-results
```

## Database Setup

### PostgreSQL Configuration

**Recommended PostgreSQL settings for production**:

```postgresql
# postgresql.conf
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

# Enable logging for monitoring
log_statement = 'mod'
log_duration = on
log_min_duration_statement = 1000
```

### Database Migrations

```bash
# Initialize database (first time only)
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "Add new feature"

# Apply migrations
uv run alembic upgrade head

# Check migration status
uv run alembic current
uv run alembic history
```

## Storage Configuration

### AWS S3

1. **Create S3 bucket**:

```bash
aws s3api create-bucket \
  --bucket test-results-artifacts-prod \
  --region us-west-2 \
  --create-bucket-configuration LocationConstraint=us-west-2
```

2. **Configure bucket policy**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAPIAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT:user/test-results-api"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::test-results-artifacts-prod",
        "arn:aws:s3:::test-results-artifacts-prod/*"
      ]
    }
  ]
}
```

3. **Configure CORS**:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedOrigins": ["https://your-frontend.com"],
    "ExposeHeaders": ["ETag"]
  }
]
```

### MinIO (Self-hosted)

```bash
# Start MinIO server
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin123 \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"

# Create bucket
mc config host add minio http://localhost:9000 minioadmin minioadmin123
mc mb minio/test-results-artifacts
```

## Monitoring and Observability

### Health Checks

The API provides comprehensive health check endpoints:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# Readiness check
curl http://localhost:8000/health/ready
```

### Logging

Configure structured logging with proper log levels:

```python
# logging.py
import structlog
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### Metrics Collection

**Prometheus metrics example**:

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'api_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

# Database metrics
DB_CONNECTIONS = Gauge(
    'db_connections_active',
    'Active database connections'
)

# Storage metrics
STORAGE_OPERATIONS = Counter(
    'storage_operations_total',
    'Storage operations',
    ['operation', 'status']
)
```

## Security Best Practices

### JWT Token Security

```python
# Strong JWT configuration
JWT_SECRET_KEY = os.urandom(32)  # 256-bit key
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
JWT_REFRESH_EXPIRATION_DAYS = 30

# Token rotation
AUTOMATION_TOKEN_MAX_AGE_DAYS = 90
AUTOMATION_TOKEN_ROTATION_WARNING_DAYS = 7
```

### API Security

```python
# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/results")
@limiter.limit("100/minute")
async def get_results(request: Request):
    pass

# Input validation
from pydantic import BaseModel, validator

class TestResultCreate(BaseModel):
    suite_id: str
    external_id: str
    status: Literal["passed", "failed", "skipped"]

    @validator('external_id')
    def validate_external_id(cls, v):
        if not v or len(v) > 255:
            raise ValueError('Invalid external_id')
        return v
```

### Database Security

```sql
-- Create dedicated user with limited permissions
CREATE USER test_results_api WITH PASSWORD 'secure_password';

-- Grant only necessary permissions
GRANT CONNECT ON DATABASE testresults TO test_results_api;
GRANT USAGE ON SCHEMA public TO test_results_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO test_results_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO test_results_api;

-- Enable row-level security where needed
ALTER TABLE test_results ENABLE ROW LEVEL SECURITY;
```

## Performance Optimization

### Database Performance

```python
# Connection pooling
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
    echo=False
)
```

### Caching

```python
# Redis caching
import redis.asyncio as redis
from functools import wraps

redis_client = redis.from_url("redis://localhost:6379")

def cache_result(expire_seconds: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            await redis_client.setex(
                cache_key,
                expire_seconds,
                json.dumps(result, default=str)
            )
            return result
        return wrapper
    return decorator
```

### CDN Configuration

```bash
# CloudFront distribution for artifacts
aws cloudfront create-distribution --distribution-config '{
  "CallerReference": "test-results-cdn-2024",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-test-results-artifacts",
        "DomainName": "test-results-artifacts-prod.s3.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": ""
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-test-results-artifacts",
    "ViewerProtocolPolicy": "redirect-to-https",
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {
        "Forward": "none"
      }
    },
    "MinTTL": 86400
  },
  "Comment": "CDN for test artifacts",
  "Enabled": true
}'
```

## Backup and Disaster Recovery

### Database Backups

```bash
# Automated PostgreSQL backup script
#!/bin/bash
BACKUP_DIR="/backups/postgresql"
DB_NAME="testresults"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create backup
pg_dump -h localhost -U testresults -d $DB_NAME \
  --no-password --format=custom \
  --file="$BACKUP_DIR/testresults_$TIMESTAMP.dump"

# Upload to S3
aws s3 cp "$BACKUP_DIR/testresults_$TIMESTAMP.dump" \
  s3://test-results-backups/database/

# Cleanup old local backups (keep last 7 days)
find $BACKUP_DIR -name "testresults_*.dump" -mtime +7 -delete
```

### Storage Backups

```bash
# S3 cross-region replication
aws s3api put-bucket-replication --bucket test-results-artifacts-prod \
--replication-configuration '{
  "Role": "arn:aws:iam::ACCOUNT:role/replication-role",
  "Rules": [
    {
      "Status": "Enabled",
      "Priority": 1,
      "Filter": {"Prefix": "artifacts/"},
      "Destination": {
        "Bucket": "arn:aws:s3:::test-results-artifacts-backup",
        "StorageClass": "GLACIER"
      }
    }
  ]
}'
```

### Restore Procedures

```bash
# Database restore
pg_restore -h localhost -U testresults -d testresults_new \
  --clean --if-exists testresults_20240115_100000.dump

# Storage restore
aws s3 sync s3://test-results-artifacts-backup/ \
  s3://test-results-artifacts-prod/ --delete
```

## Troubleshooting

### Common Issues

**Database Connection Issues**:
```bash
# Check connection
psql -h localhost -U testresults -d testresults -c "SELECT version();"

# Check pool status
SELECT state, count(*) FROM pg_stat_activity
WHERE datname = 'testresults' GROUP BY state;
```

**Storage Issues**:
```bash
# Test S3 connectivity
aws s3 ls s3://test-results-artifacts-prod/

# MinIO connectivity
mc ls minio/test-results-artifacts/
```

**Performance Issues**:
```bash
# Check slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;

# Check API response times
curl -w "@curl-format.txt" -s -o /dev/null http://api.testresults.dev/v1/health
```

### Log Analysis

```bash
# Find errors in logs
docker logs test-results-api | grep ERROR

# Monitor API requests
kubectl logs -f deployment/test-results-api -n test-results | \
  grep -E "(POST|GET|PUT|DELETE)"

# Check database connections
grep "database" /var/log/test-results-api/app.log | tail -20
```

## Maintenance

### Regular Tasks

```bash
# Weekly database maintenance
VACUUM ANALYZE;
REINDEX DATABASE testresults;

# Monthly storage cleanup
test-results-cli storage cleanup --older-than 90d --dry-run
test-results-cli storage cleanup --older-than 90d

# Quarterly security updates
docker pull test-results-api:latest
kubectl set image deployment/test-results-api api=test-results-api:latest -n test-results

# Token rotation
test-results-cli auth list-tokens --expires-soon
test-results-cli auth rotate-token --token-id auto_abc123
```

### Monitoring Alerts

```yaml
# Prometheus alerts
groups:
- name: test-results-api
  rules:
  - alert: HighErrorRate
    expr: rate(api_requests_total{status_code=~"5.."}[5m]) > 0.1
    for: 5m
    annotations:
      summary: High error rate detected

  - alert: DatabaseConnectionIssues
    expr: db_connections_active / db_connections_max > 0.8
    for: 2m
    annotations:
      summary: High database connection usage

  - alert: StorageIssues
    expr: increase(storage_operations_total{status="error"}[5m]) > 10
    for: 1m
    annotations:
      summary: Storage operation failures detected
```