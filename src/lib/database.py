"""
Database connection and session management using SQLAlchemy async.
Provides connection pooling, health checks, and session lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
import structlog

from .config import get_settings

logger = structlog.get_logger()

# Base class for all models
Base = declarative_base()

# Global engine instance
_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def create_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Create async SQLAlchemy engine with proper configuration."""
    settings = get_settings()
    url = database_url or settings.database.url

    # Configure connection pool based on environment
    if settings.is_development():
        # Development: echo SQL, async pool
        echo = settings.database.echo
    else:
        # Production: no echo
        echo = False

    engine = create_async_engine(
        url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
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


async def init_database(database_url: Optional[str] = None) -> None:
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
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with automatic cleanup."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


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
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def drop_tables() -> None:
    """Drop all tables (for testing)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database tables dropped")