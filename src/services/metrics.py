"""
Metrics collection and monitoring for production observability.
"""

import asyncio
import logging
import os
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Deque, Optional

import psutil  # type: ignore[import-untyped]
from fastapi import Request
from prometheus_client import (  # type: ignore[import-not-found]
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    Summary,
    generate_latest,
)

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Metric data point."""

    timestamp: datetime
    value: float
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Comprehensive metrics collection system."""

    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or CollectorRegistry()
        self.custom_metrics: dict[str, Deque[Any]] = defaultdict(lambda: deque(maxlen=1000))
        self._lock = threading.Lock()

        # Initialize Prometheus metrics
        self._init_prometheus_metrics()

        # Initialize system metrics collection
        self._init_system_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics."""

        # API Request metrics
        self.request_count = Counter(
            "api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        self.request_duration = Histogram(
            "api_request_duration_seconds",
            "API request duration in seconds",
            ["method", "endpoint"],
            buckets=[
                0.001,
                0.005,
                0.01,
                0.025,
                0.05,
                0.075,
                0.1,
                0.25,
                0.5,
                0.75,
                1.0,
                2.5,
                5.0,
                7.5,
                10.0,
            ],
            registry=self.registry,
        )

        self.request_size = Summary(
            "api_request_size_bytes",
            "API request size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )

        self.response_size = Summary(
            "api_response_size_bytes",
            "API response size in bytes",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        # Database metrics
        self.db_connections_active = Gauge(
            "db_connections_active", "Active database connections", registry=self.registry
        )

        self.db_connections_max = Gauge(
            "db_connections_max", "Maximum database connections", registry=self.registry
        )

        self.db_query_duration = Histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation", "table"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry,
        )

        self.db_operations_total = Counter(
            "db_operations_total",
            "Total database operations",
            ["operation", "table", "status"],
            registry=self.registry,
        )

        # Storage metrics
        self.storage_operations_total = Counter(
            "storage_operations_total",
            "Total storage operations",
            ["operation", "status"],
            registry=self.registry,
        )

        self.storage_operation_duration = Histogram(
            "storage_operation_duration_seconds",
            "Storage operation duration in seconds",
            ["operation"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )

        self.storage_bytes_transferred = Counter(
            "storage_bytes_transferred_total",
            "Total bytes transferred to/from storage",
            ["operation"],
            registry=self.registry,
        )

        # Authentication metrics
        self.auth_operations_total = Counter(
            "auth_operations_total",
            "Total authentication operations",
            ["operation", "token_type", "status"],
            registry=self.registry,
        )

        self.auth_tokens_active = Gauge(
            "auth_tokens_active",
            "Active authentication tokens",
            ["token_type"],
            registry=self.registry,
        )

        # Application metrics
        self.app_info = Info("app_info", "Application information", registry=self.registry)

        self.app_uptime = Gauge(
            "app_uptime_seconds", "Application uptime in seconds", registry=self.registry
        )

        self.app_memory_usage = Gauge(
            "app_memory_usage_bytes", "Application memory usage in bytes", registry=self.registry
        )

        self.app_cpu_usage = Gauge(
            "app_cpu_usage_percent", "Application CPU usage percentage", registry=self.registry
        )

        # Business metrics
        self.test_results_total = Counter(
            "test_results_total",
            "Total test results processed",
            ["framework", "status"],
            registry=self.registry,
        )

        self.test_artifacts_total = Counter(
            "test_artifacts_total",
            "Total test artifacts uploaded",
            ["type"],
            registry=self.registry,
        )

        self.test_suites_active = Gauge(
            "test_suites_active", "Currently active test suites", registry=self.registry
        )

    def _init_system_metrics(self) -> None:
        """Initialize system-level metrics."""

        # Set application info
        self.app_info.info(
            {
                "version": os.getenv("APP_VERSION", "0.4.0"),
                "environment": os.getenv("APP_ENVIRONMENT", "development"),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            }
        )

        # Start system metrics collection
        self._start_system_metrics_collection()

    def _start_system_metrics_collection(self) -> None:
        """Start background system metrics collection."""

        async def collect_system_metrics() -> None:
            """Collect system-level metrics periodically."""
            while True:
                try:
                    # Memory usage
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    self.app_memory_usage.set(memory_info.rss)

                    # CPU usage
                    cpu_percent = process.cpu_percent()
                    self.app_cpu_usage.set(cpu_percent)

                    # Uptime (mock - would be calculated from start time)
                    # self.app_uptime.set(time.time() - start_time)

                except Exception as e:
                    logger.warning(f"Failed to collect system metrics: {e}")

                await asyncio.sleep(30)  # Collect every 30 seconds

        # Start background task
        asyncio.create_task(collect_system_metrics())

    # API Metrics Methods
    def record_api_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
    ) -> None:
        """Record API request metrics."""

        self.request_count.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).inc()

        self.request_duration.labels(method=method, endpoint=endpoint).observe(duration)

        if request_size is not None:
            self.request_size.labels(method=method, endpoint=endpoint).observe(request_size)

        if response_size is not None:
            self.response_size.labels(
                method=method, endpoint=endpoint, status_code=str(status_code)
            ).observe(response_size)

    # Database Metrics Methods
    def record_db_connection_stats(self, active: int, max_connections: int) -> None:
        """Record database connection statistics."""
        self.db_connections_active.set(active)
        self.db_connections_max.set(max_connections)

    def record_db_operation(
        self, operation: str, table: str, duration: float, success: bool = True
    ) -> None:
        """Record database operation metrics."""

        status = "success" if success else "error"

        self.db_operations_total.labels(operation=operation, table=table, status=status).inc()

        self.db_query_duration.labels(operation=operation, table=table).observe(duration)

    # Storage Metrics Methods
    def record_storage_operation(
        self, operation: str, duration: float, bytes_transferred: Optional[int] = None, success: bool = True
    ) -> None:
        """Record storage operation metrics."""

        status = "success" if success else "error"

        self.storage_operations_total.labels(operation=operation, status=status).inc()

        self.storage_operation_duration.labels(operation=operation).observe(duration)

        if bytes_transferred is not None:
            self.storage_bytes_transferred.labels(operation=operation).inc(bytes_transferred)

    # Authentication Metrics Methods
    def record_auth_operation(self, operation: str, token_type: str, success: bool = True) -> None:
        """Record authentication operation metrics."""

        status = "success" if success else "failure"

        self.auth_operations_total.labels(
            operation=operation, token_type=token_type, status=status
        ).inc()

    def update_active_tokens(self, token_type: str, count: int) -> None:
        """Update active tokens count."""
        self.auth_tokens_active.labels(token_type=token_type).set(count)

    # Business Metrics Methods
    def record_test_result(self, framework: str, status: str) -> None:
        """Record test result processed."""
        self.test_results_total.labels(framework=framework, status=status).inc()

    def record_test_artifact(self, artifact_type: str) -> None:
        """Record test artifact uploaded."""
        self.test_artifacts_total.labels(type=artifact_type).inc()

    def update_active_test_suites(self, count: int) -> None:
        """Update active test suites count."""
        self.test_suites_active.set(count)

    # Custom Metrics Methods
    def record_custom_metric(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Record custom metric value."""

        with self._lock:
            self.custom_metrics[name].append(
                MetricData(timestamp=datetime.now(UTC), value=value, labels=labels or {})
            )

    def get_custom_metrics(self, name: str) -> list[MetricData]:
        """Get custom metric values."""
        with self._lock:
            return list(self.custom_metrics.get(name, []))

    # Export Methods
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        return str(generate_latest(self.registry).decode("utf-8"))

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get metrics summary for health checks."""

        # Get sample values from Prometheus metrics
        try:
            summary = {
                "api_requests_total": self.request_count._value._value,
                "active_connections": self.db_connections_active._value._value,
                "memory_usage_mb": self.app_memory_usage._value._value / 1024 / 1024,
                "cpu_usage_percent": self.app_cpu_usage._value._value,
                "custom_metrics_count": len(self.custom_metrics),
            }
        except:
            # Fallback if metrics not available
            summary = {
                "status": "metrics_collection_active",
                "custom_metrics_count": len(self.custom_metrics),
            }

        return summary


class MetricsMiddleware:
    """FastAPI middleware for automatic metrics collection."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    async def __call__(self, request: Request, call_next: Any) -> Any:
        """Collect metrics for each request."""

        start_time = time.time()
        request_size = 0

        # Get request size if available
        if hasattr(request, "body"):
            try:
                body = await request.body()
                request_size = len(body) if body else 0
            except:
                pass

        try:
            # Process request
            response = await call_next(request)

            # Calculate metrics
            duration = time.time() - start_time
            response_size = 0

            # Get response size if available
            if hasattr(response, "body"):
                try:
                    response_size = len(response.body)
                except:
                    pass

            # Record metrics
            self.collector.record_api_request(
                method=request.method,
                endpoint=self._normalize_endpoint(request.url.path),
                status_code=response.status_code,
                duration=duration,
                request_size=request_size if request_size > 0 else None,
                response_size=response_size if response_size > 0 else None,
            )

            return response

        except Exception:
            # Record error metrics
            duration = time.time() - start_time

            self.collector.record_api_request(
                method=request.method,
                endpoint=self._normalize_endpoint(request.url.path),
                status_code=500,  # Internal server error
                duration=duration,
                request_size=request_size if request_size > 0 else None,
            )

            raise

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics."""

        # Remove IDs and other dynamic parts
        import re

        # Replace UUIDs and IDs with placeholders
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{id}", path
        )
        path = re.sub(r"/\d+", "/{id}", path)

        return path


@contextmanager
def measure_operation(collector: MetricsCollector, operation_type: str, **labels: Any) -> Any:
    """Context manager to measure operation duration."""

    start_time = time.time()
    success = True

    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration = time.time() - start_time

        # Record custom metric
        metric_name = f"{operation_type}_duration"
        collector.record_custom_metric(
            name=metric_name, value=duration, labels={**labels, "success": str(success)}
        )


# Global metrics collector
metrics_collector: MetricsCollector | None = None


def init_metrics() -> MetricsCollector:
    """Initialize global metrics collector."""
    global metrics_collector
    metrics_collector = MetricsCollector()

    logger.info("Metrics collection initialized")
    return metrics_collector


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    if not metrics_collector:
        raise RuntimeError("Metrics not initialized. Call init_metrics() first.")
    return metrics_collector
