"""
Enhanced database service with performance optimization and monitoring.
"""

import logging
import os
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
from typing import Any

from sqlalchemy import text
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics for monitoring."""

    size: int
    checked_in: int
    checked_out: int
    overflow: int
    invalidated: int


@dataclass
class QueryStats:
    """Query performance statistics."""

    count: int
    total_time: float
    avg_time: float
    max_time: float
    min_time: float


class PerformantDatabaseManager:
    """Enhanced database manager with performance optimization."""

    def __init__(
        self,
        database_url: str,
        pool_size: int = 20,
        max_overflow: int = 30,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo: bool = False,
        query_timeout: int = 30,
        enable_query_logging: bool = True,
    ):
        self.database_url = database_url
        self.query_stats: dict[str, QueryStats] = defaultdict(
            lambda: QueryStats(0, 0.0, 0.0, 0.0, float("inf"))
        )
        self.slow_query_threshold = 1.0  # Log queries slower than 1 second
        self.enable_query_logging = enable_query_logging

        # Configure engine with optimized settings
        connect_args = {
            "command_timeout": query_timeout,
            "server_settings": {
                # Optimize PostgreSQL session settings
                "jit": "off",  # Disable JIT for predictable performance
                "application_name": "test-results-api",
                "statement_timeout": f"{query_timeout * 1000}ms",
            },
        }

        self.engine = create_async_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            echo=echo,
            echo_pool=echo,
            connect_args=connect_args,
            # Async-specific optimizations
            pool_reset_on_return="commit",
            future=True,
        )

        # Session factory with optimized settings
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Better for async operations
            autoflush=False,  # Manual control over flushing
        )

        # Set up event listeners for monitoring
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners for performance monitoring."""

        @event.listens_for(self.engine.sync_engine, "before_cursor_execute")
        def before_cursor_execute(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool) -> None:
            context._query_start_time = time.time()

        @event.listens_for(self.engine.sync_engine, "after_cursor_execute")
        def after_cursor_execute(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool) -> None:
            total = time.time() - context._query_start_time

            if self.enable_query_logging:
                # Update query statistics
                query_key = self._normalize_query(statement)
                stats = self.query_stats[query_key]
                stats.count += 1
                stats.total_time += total
                stats.avg_time = stats.total_time / stats.count
                stats.max_time = max(stats.max_time, total)
                stats.min_time = min(stats.min_time, total)

                # Log slow queries
                if total > self.slow_query_threshold:
                    logger.warning(
                        "Slow query detected",
                        extra={
                            "query": statement,
                            "duration_ms": total * 1000,
                            "parameters": parameters,
                        },
                    )

    def _normalize_query(self, statement: str) -> str:
        """Normalize SQL statement for statistics grouping."""
        # Remove parameter placeholders and normalize whitespace
        import re

        normalized = re.sub(r"\$\d+", "?", str(statement))
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()[:200]  # Limit length for memory

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Get database session with automatic cleanup and error handling."""
        async with self.session_factory() as session:
            try:
                # Configure session for optimal performance
                await session.execute(text("SET LOCAL work_mem = '16MB'"))
                await session.execute(text("SET LOCAL random_page_cost = 1.1"))

                yield session
                await session.commit()

            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_optimized_session(
        self, read_only: bool = False, isolation_level: str | None = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """Get session with specific optimizations."""
        async with self.session_factory() as session:
            try:
                if read_only:
                    await session.execute(text("SET TRANSACTION READ ONLY"))

                if isolation_level:
                    await session.execute(
                        text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
                    )

                # Additional optimizations for read-heavy workloads
                if read_only:
                    await session.execute(text("SET LOCAL enable_hashjoin = on"))
                    await session.execute(text("SET LOCAL enable_mergejoin = on"))

                yield session

                if not read_only:
                    await session.commit()

            except Exception:
                if not read_only:
                    await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive database health check."""
        start_time = time.time()

        try:
            async with self.get_session() as session:
                # Basic connectivity test
                result = await session.execute(text("SELECT 1 as healthy"))
                healthy = result.scalar() == 1

                # Check database version
                version_result = await session.execute(text("SELECT version()"))
                version = version_result.scalar()

                # Check current connections
                connections_result = await session.execute(
                    text("""
                    SELECT count(*) as active_connections
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    AND state = 'active'
                """)
                )
                active_connections = connections_result.scalar()

                # Check for long-running queries
                long_queries_result = await session.execute(
                    text("""
                    SELECT count(*) as long_queries
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    AND state = 'active'
                    AND now() - query_start > interval '30 seconds'
                """)
                )
                long_queries = long_queries_result.scalar()

                response_time = (time.time() - start_time) * 1000

                return {
                    "healthy": healthy,
                    "response_time_ms": response_time,
                    "database_version": version,
                    "active_connections": active_connections,
                    "long_running_queries": long_queries,
                    "connection_pool": asdict(self.get_connection_pool_stats()),
                    "query_stats": self.get_query_performance_stats(),
                }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "response_time_ms": (time.time() - start_time) * 1000,
            }

    def get_connection_pool_stats(self) -> ConnectionPoolStats:
        """Get current connection pool statistics."""
        pool = self.engine.pool
        return ConnectionPoolStats(
            size=pool.size(),  # type: ignore[attr-defined]
            checked_in=pool.checkedin(),  # type: ignore[attr-defined]
            checked_out=pool.checkedout(),  # type: ignore[attr-defined]
            overflow=pool.overflow(),  # type: ignore[attr-defined]
            invalidated=pool.invalidated(),  # type: ignore[attr-defined]
        )

    def get_query_performance_stats(self) -> dict[str, dict[str, Any]]:
        """Get query performance statistics."""
        return {
            query: {
                "count": stats.count,
                "total_time_ms": stats.total_time * 1000,
                "avg_time_ms": stats.avg_time * 1000,
                "max_time_ms": stats.max_time * 1000,
                "min_time_ms": stats.min_time * 1000,
            }
            for query, stats in self.query_stats.items()
        }

    async def optimize_database(self) -> None:
        """Run database optimization commands."""
        async with self.get_session() as session:
            # Update table statistics
            await session.execute(text("ANALYZE"))

            # Log optimization completion
            logger.info("Database optimization completed")

    async def prepare_for_load(self) -> None:
        """Prepare database for high-load scenarios."""
        async with self.get_session() as session:
            # Increase work_mem for complex queries
            await session.execute(text("SET work_mem = '32MB'"))

            # Optimize for read-heavy workloads
            await session.execute(text("SET default_statistics_target = 1000"))

            # Enable parallel query execution
            await session.execute(text("SET max_parallel_workers_per_gather = 4"))

            logger.info("Database prepared for high-load operations")

    async def reset_query_stats(self) -> None:
        """Reset query performance statistics."""
        self.query_stats.clear()
        logger.info("Query statistics reset")

    async def close(self) -> None:
        """Close database connections and cleanup."""
        await self.engine.dispose()
        logger.info("Database connections closed")


# Global database manager instance
perf_db_manager: PerformantDatabaseManager | None = None


async def init_performant_database(database_url: str | None = None, **kwargs: Any) -> PerformantDatabaseManager:
    """Initialize high-performance database connection."""
    global perf_db_manager

    if not database_url:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL must be provided or set in environment")

    # Production-optimized defaults
    production_config = {
        "pool_size": 50,  # Larger pool for high concurrency
        "max_overflow": 100,  # Allow significant overflow
        "pool_timeout": 30,  # Reasonable timeout
        "pool_recycle": 3600,  # Recycle connections hourly
        "pool_pre_ping": True,  # Validate connections
        "query_timeout": 30,  # Prevent runaway queries
        "enable_query_logging": True,
    }

    # Override with provided kwargs
    production_config.update(kwargs)

    perf_db_manager = PerformantDatabaseManager(database_url, **production_config)  # type: ignore[arg-type]

    # Prepare for optimal performance
    await perf_db_manager.prepare_for_load()

    return perf_db_manager


async def get_perf_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency for FastAPI to get optimized database session."""
    if not perf_db_manager:
        raise RuntimeError("Performant database not initialized")

    async with perf_db_manager.get_session() as session:
        yield session


async def get_readonly_db_session() -> AsyncGenerator[AsyncSession]:
    """Get read-only optimized database session."""
    if not perf_db_manager:
        raise RuntimeError("Performant database not initialized")

    async with perf_db_manager.get_optimized_session(
        read_only=True, isolation_level="READ COMMITTED"
    ) as session:
        yield session


def get_database_manager() -> PerformantDatabaseManager:
    """Get the global performant database manager."""
    if not perf_db_manager:
        raise RuntimeError("Performant database not initialized")
    return perf_db_manager


# Query optimization helpers
async def execute_optimized_query(
    session: AsyncSession, query: str, parameters: dict[str, Any] | None = None, timeout: int = 30
) -> Any:
    """Execute query with optimizations."""

    # Set query timeout
    await session.execute(text(f"SET LOCAL statement_timeout = '{timeout}s'"))

    # Execute with parameters
    if parameters:
        result = await session.execute(text(query), parameters)
    else:
        result = await session.execute(text(query))

    return result


async def bulk_insert_optimized(
    session: AsyncSession, table_name: str, records: list[dict[str, Any]], chunk_size: int = 1000
) -> None:
    """Optimized bulk insert with chunking."""

    # Disable autoflush for bulk operations
    session.autoflush = False

    try:
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]

            # Add chunk to session
            session.add_all(chunk)

            # Flush periodically
            await session.flush()

            # Clear session cache to manage memory
            session.expunge_all()

        # Final commit
        await session.commit()

    finally:
        # Re-enable autoflush
        session.autoflush = True
