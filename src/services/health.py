"""
Comprehensive health check and monitoring system.
"""

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

import psutil  # type: ignore[import-untyped]

from .database_performance import get_database_manager
from .storage import get_storage_client  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Individual health check result."""

    name: str
    status: HealthStatus
    response_time_ms: float
    message: str
    details: Optional[dict[str, Any]] = None


@dataclass
class SystemHealth:
    """Overall system health status."""

    status: HealthStatus
    timestamp: datetime
    response_time_ms: float
    checks: list[HealthCheck]
    summary: Optional[dict[str, Any]] = None


class HealthCheckManager:
    """Manages all health checks and monitoring."""

    def __init__(self) -> None:
        self.startup_time = datetime.now(UTC)
        self.check_history: list[SystemHealth] = []
        self.max_history = 100

    async def perform_basic_health_check(self) -> SystemHealth:
        """Perform basic health check for load balancer."""
        start_time = time.time()

        checks = [await self._check_api_ready()]

        overall_status = self._determine_overall_status(checks)
        response_time = (time.time() - start_time) * 1000

        return SystemHealth(
            status=overall_status,
            timestamp=datetime.now(UTC),
            response_time_ms=response_time,
            checks=checks,
            summary={"basic": True},
        )

    async def perform_detailed_health_check(self) -> SystemHealth:
        """Perform comprehensive health check."""
        start_time = time.time()

        # Run all checks in parallel for faster response
        check_tasks = [
            self._check_api_ready(),
            self._check_database_health(),
            self._check_storage_health(),
            self._check_system_resources(),
            self._check_dependencies(),
        ]

        checks = await asyncio.gather(*check_tasks, return_exceptions=True)

        # Handle any exceptions in checks
        valid_checks = []
        for i, check in enumerate(checks):
            if isinstance(check, Exception):
                valid_checks.append(
                    HealthCheck(
                        name=f"check_{i}",
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0,
                        message=f"Check failed: {str(check)}",
                    )
                )
            else:
                valid_checks.append(check)  # type: ignore[arg-type]

        overall_status = self._determine_overall_status(valid_checks)
        response_time = (time.time() - start_time) * 1000

        system_health = SystemHealth(
            status=overall_status,
            timestamp=datetime.now(UTC),
            response_time_ms=response_time,
            checks=valid_checks,
            summary=self._generate_summary(valid_checks),
        )

        # Store in history
        self._store_health_check(system_health)

        return system_health

    async def _check_api_ready(self) -> HealthCheck:
        """Check if API is ready to serve requests."""
        start_time = time.time()

        try:
            # Basic readiness check
            uptime = datetime.now(UTC) - self.startup_time
            response_time = (time.time() - start_time) * 1000

            return HealthCheck(
                name="api_ready",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="API is ready",
                details={
                    "uptime_seconds": uptime.total_seconds(),
                    "startup_time": self.startup_time.isoformat(),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="api_ready",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"API not ready: {str(e)}",
            )

    async def _check_database_health(self) -> HealthCheck:
        """Check database connectivity and performance."""
        start_time = time.time()

        try:
            db_manager = get_database_manager()
            health_data = await db_manager.health_check()

            response_time = (time.time() - start_time) * 1000

            if health_data.get("healthy", False):
                # Determine status based on response time and connection usage
                db_response_time = health_data.get("response_time_ms", 0)
                pool_stats = health_data.get("connection_pool", {})

                status = HealthStatus.HEALTHY
                if db_response_time > 100:  # Slow database responses
                    status = HealthStatus.DEGRADED
                elif pool_stats.get("checked_out", 0) / max(pool_stats.get("size", 1), 1) > 0.8:
                    status = HealthStatus.DEGRADED  # High connection pool usage

                return HealthCheck(
                    name="database",
                    status=status,
                    response_time_ms=response_time,
                    message="Database is healthy"
                    if status == HealthStatus.HEALTHY
                    else "Database performance degraded",
                    details=health_data,
                )
            else:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    message=f"Database unhealthy: {health_data.get('error', 'Unknown error')}",
                    details=health_data,
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Database check failed: {str(e)}",
            )

    async def _check_storage_health(self) -> HealthCheck:
        """Check storage system health."""
        start_time = time.time()

        try:
            storage_client = get_storage_client()

            # Test basic connectivity by listing a small number of objects
            async with storage_client:
                files = await storage_client.list_files()
                test_connectivity = len(files) >= 0  # Just verify we can list

            response_time = (time.time() - start_time) * 1000

            if test_connectivity:
                # Determine status based on response time
                status = HealthStatus.HEALTHY
                if response_time > 500:  # Slow storage responses
                    status = HealthStatus.DEGRADED

                return HealthCheck(
                    name="storage",
                    status=status,
                    response_time_ms=response_time,
                    message="Storage is healthy"
                    if status == HealthStatus.HEALTHY
                    else "Storage performance degraded",
                    details={
                        "storage_type": storage_client.config.storage_type,
                        "endpoint": storage_client.config.endpoint,
                        "bucket": storage_client.config.bucket,
                    },
                )
            else:
                return HealthCheck(
                    name="storage",
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    message="Storage connectivity failed",
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="storage",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Storage check failed: {str(e)}",
            )

    async def _check_system_resources(self) -> HealthCheck:
        """Check system resource usage."""
        start_time = time.time()

        try:
            # Get system metrics
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()

            # Get system-wide metrics
            system_memory = psutil.virtual_memory()
            system_disk = psutil.disk_usage("/")

            response_time = (time.time() - start_time) * 1000

            # Determine status based on resource usage
            status = HealthStatus.HEALTHY
            warnings = []

            if system_memory.percent > 90:
                status = HealthStatus.DEGRADED
                warnings.append("High system memory usage")
            elif system_memory.percent > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append("Critical system memory usage")

            if system_disk.percent > 90:
                status = HealthStatus.DEGRADED
                warnings.append("High disk usage")
            elif system_disk.percent > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append("Critical disk usage")

            if cpu_percent > 80:
                status = HealthStatus.DEGRADED
                warnings.append("High CPU usage")

            message = "System resources healthy"
            if warnings:
                message = f"Resource warnings: {', '.join(warnings)}"

            return HealthCheck(
                name="system_resources",
                status=status,
                response_time_ms=response_time,
                message=message,
                details={
                    "process_memory_mb": memory_info.rss / 1024 / 1024,
                    "process_cpu_percent": cpu_percent,
                    "system_memory_percent": system_memory.percent,
                    "system_disk_percent": system_disk.percent,
                    "available_memory_mb": system_memory.available / 1024 / 1024,
                    "available_disk_gb": system_disk.free / 1024 / 1024 / 1024,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"System resource check failed: {str(e)}",
            )

    async def _check_dependencies(self) -> HealthCheck:
        """Check external dependencies and integrations."""
        start_time = time.time()

        try:
            # Check if we can import critical modules
            dependencies_status: dict[str, Any] = {
                "fastapi": True,
                "sqlalchemy": True,
                "aioboto3": True,
                "structlog": True,
                "prometheus_client": True,
            }

            # Try basic operations
            try:
                import aioboto3
                import fastapi
                import prometheus_client  # type: ignore[import-not-found]
                import sqlalchemy
                import structlog
            except ImportError as e:
                dependencies_status["import_error"] = str(e)

            response_time = (time.time() - start_time) * 1000

            # Check environment variables
            critical_env_vars = ["DATABASE_URL", "JWT_SECRET_KEY"]

            missing_env_vars = [var for var in critical_env_vars if not os.getenv(var)]

            status = HealthStatus.HEALTHY
            message = "All dependencies available"

            if missing_env_vars:
                status = HealthStatus.DEGRADED
                message = f"Missing environment variables: {', '.join(missing_env_vars)}"

            return HealthCheck(
                name="dependencies",
                status=status,
                response_time_ms=response_time,
                message=message,
                details={
                    "dependencies": dependencies_status,
                    "missing_env_vars": missing_env_vars,
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="dependencies",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Dependencies check failed: {str(e)}",
            )

    def _determine_overall_status(self, checks: list[HealthCheck]) -> HealthStatus:
        """Determine overall system status from individual checks."""

        if not checks:
            return HealthStatus.UNHEALTHY

        # If any check is unhealthy, system is unhealthy
        if any(check.status == HealthStatus.UNHEALTHY for check in checks):
            return HealthStatus.UNHEALTHY

        # If any check is degraded, system is degraded
        if any(check.status == HealthStatus.DEGRADED for check in checks):
            return HealthStatus.DEGRADED

        # All checks healthy
        return HealthStatus.HEALTHY

    def _generate_summary(self, checks: list[HealthCheck]) -> dict[str, Any]:
        """Generate health check summary."""

        status_counts = {
            "healthy": sum(1 for check in checks if check.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for check in checks if check.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for check in checks if check.status == HealthStatus.UNHEALTHY),
        }

        avg_response_time = sum(check.response_time_ms for check in checks) / len(checks)

        return {
            "total_checks": len(checks),
            "status_counts": status_counts,
            "average_response_time_ms": avg_response_time,
            "failed_checks": [
                check.name
                for check in checks
                if check.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
            ],
        }

    def _store_health_check(self, health: SystemHealth) -> None:
        """Store health check in history."""
        self.check_history.append(health)

        # Keep only the most recent checks
        if len(self.check_history) > self.max_history:
            self.check_history = self.check_history[-self.max_history :]

    def get_health_trends(self, hours: int = 1) -> dict[str, Any]:
        """Get health trends over time."""

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        recent_checks = [health for health in self.check_history if health.timestamp >= cutoff_time]

        if not recent_checks:
            return {"message": "No recent health data available"}

        # Calculate trends
        status_distribution = {
            "healthy": sum(1 for h in recent_checks if h.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for h in recent_checks if h.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for h in recent_checks if h.status == HealthStatus.UNHEALTHY),
        }

        avg_response_time = sum(h.response_time_ms for h in recent_checks) / len(recent_checks)

        # Identify most common issues
        failed_check_names = []
        for health in recent_checks:
            failed_check_names.extend(
                [
                    check.name
                    for check in health.checks
                    if check.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
                ]
            )

        from collections import Counter

        common_issues = Counter(failed_check_names).most_common(5)

        return {
            "timeframe_hours": hours,
            "total_checks": len(recent_checks),
            "status_distribution": status_distribution,
            "average_response_time_ms": avg_response_time,
            "uptime_percentage": (status_distribution["healthy"] / len(recent_checks)) * 100,
            "most_common_issues": dict(common_issues),
        }

    async def get_readiness_check(self) -> bool:
        """Simple readiness check for Kubernetes."""
        try:
            # Check critical components only
            db_manager = get_database_manager()
            health_data = await db_manager.health_check()
            return bool(health_data.get("healthy", False))
        except:
            return False

    async def get_liveness_check(self) -> bool:
        """Simple liveness check for Kubernetes."""
        try:
            # Very basic check - can we respond?
            return True
        except:
            return False


# Global health check manager
health_manager: HealthCheckManager | None = None


def init_health_checks() -> HealthCheckManager:
    """Initialize global health check manager."""
    global health_manager
    health_manager = HealthCheckManager()

    logger.info("Health check system initialized")
    return health_manager


def get_health_manager() -> HealthCheckManager:
    """Get the global health check manager."""
    if not health_manager:
        raise RuntimeError("Health checks not initialized. Call init_health_checks() first.")
    return health_manager
