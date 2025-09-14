# Multi-stage build for Test Results API
# Stage 1: Base dependencies
FROM python:3.13-slim as base

# Set environment variables for optimal Python behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PYTHONPATH=/app

# Install system dependencies and clean up in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user with specific UID/GID for security
RUN groupadd -r -g 1001 appuser && \
    useradd -r -u 1001 -g appuser -m -d /app appuser

# Set work directory
WORKDIR /app

# Copy and install Python dependencies
COPY pyproject.toml ./
COPY uv.lock* ./
RUN pip install --upgrade pip uv && \
    uv sync --frozen --no-dev && \
    pip uninstall -y uv && \
    pip cache purge

# Stage 2: Development
FROM base as development

# Install development dependencies
RUN pip install uv && \
    uv sync --frozen && \
    pip uninstall -y uv

# Install additional development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copy all source code for development
COPY . .

# Set ownership and switch to app user
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Development command with auto-reload
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]

# Stage 3: Production builder
FROM base as builder

# Copy source code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY pyproject.toml ./

# Remove __pycache__ and .pyc files
RUN find . -type d -name __pycache__ -exec rm -rf {} + || true && \
    find . -type f -name "*.pyc" -delete

# Stage 4: Production
FROM python:3.13-slim as production

# Production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    WORKERS=4 \
    MAX_REQUESTS=1000 \
    MAX_REQUESTS_JITTER=50 \
    TIMEOUT_KEEP_ALIVE=5 \
    LOG_LEVEL=info

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user (matching base stage)
RUN groupadd -r -g 1001 appuser && \
    useradd -r -u 1001 -g appuser -m -d /app appuser

# Set work directory
WORKDIR /app

# Copy Python packages from base stage
COPY --from=base /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application code from builder
COPY --from=builder --chown=appuser:appuser /app ./

# Create necessary directories
RUN mkdir -p /app/logs /tmp/app && \
    chown -R appuser:appuser /app /tmp/app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command with optimizations
CMD uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers ${WORKERS} \
    --worker-class uvicorn.workers.UvicornWorker \
    --max-requests ${MAX_REQUESTS} \
    --max-requests-jitter ${MAX_REQUESTS_JITTER} \
    --timeout-keep-alive ${TIMEOUT_KEEP_ALIVE} \
    --log-level ${LOG_LEVEL} \
    --access-log \
    --use-colors

# Optional: Production with Gunicorn (alternative)
FROM production as production-gunicorn

# Install Gunicorn
RUN pip install --no-cache-dir gunicorn[gthread]

# Gunicorn production command
CMD gunicorn src.main:app \
    -w ${WORKERS} \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    --max-requests ${MAX_REQUESTS} \
    --max-requests-jitter ${MAX_REQUESTS_JITTER} \
    --timeout 30 \
    --keep-alive ${TIMEOUT_KEEP_ALIVE} \
    --log-level ${LOG_LEVEL} \
    --access-logfile - \
    --error-logfile -