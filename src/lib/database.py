"""
Database connection and session management using SQLAlchemy async.
Provides connection pooling, health checks, and session lifecycle management.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

logger = structlog.get_logger()

# Global engine instance
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Create async SQLAlchemy engine with proper configuration."""
    settings = get_settings()
    url = database_url or settings.database.url

    # Configure connection pool based on environment
    echo = settings.database.echo if settings.is_development() else False

    engine = create_async_engine(
        url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=3600,  # Recycle connections every hour to prevent stale connections
        pool_pre_ping=True,  # Test connections before use
        echo=echo,
        echo_pool=settings.is_development(),
    )

    logger.info(
        "Database engine created",
        url=url.split("@")[-1],  # Log only host part for security
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
    )

    return engine


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session maker."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def init_database(database_url: str | None = None) -> None:
    """Initialize database connection and session maker."""
    global _engine, _session_maker

    if _engine is not None:
        logger.warning("Database already initialized")
        return

    _engine = create_engine(database_url)
    _session_maker = create_session_maker(_engine)

    logger.info("Database initialized")


async def close_database() -> None:
    """Close database connections."""
    global _engine, _session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.info("Database connections closed")


def get_engine() -> AsyncEngine:
    """Get the current database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get the current session maker."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_maker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get database session with automatic cleanup and retry logic."""
    from sqlalchemy.exc import SQLAlchemyError

    session_maker = get_session_maker()

    # Retry logic for connection issues only
    max_retries = 3
    retry_count = 0

    while retry_count <= max_retries:
        try:
            async with session_maker() as session:
                # Test the connection before yielding
                await session.execute(text("SELECT 1"))
                yield session
                break
        except SQLAlchemyError as e:
            if retry_count >= max_retries:
                logger.error(
                    "Database session failed after retries", error=str(e), retry_count=retry_count
                )
                raise
            logger.warning(
                "Database session failed, retrying", error=str(e), retry_count=retry_count
            )
            retry_count += 1
            # Re-initialize engine on connection errors
            if "connection is closed" in str(e).lower():
                logger.warning("Connection closed error detected, reinitializing database")
                await close_database()
                await init_database()
                session_maker = get_session_maker()


async def health_check() -> bool:
    """Check database connectivity."""
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            logger.debug("Database health check passed")
            return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


async def create_tables() -> None:
    """Create all tables (for development/testing)."""
    # Import models to ensure they're registered with Base.metadata
    from ..models.base import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def drop_tables() -> None:
    """Drop all tables (for testing)."""
    from ..models.base import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database tables dropped")
