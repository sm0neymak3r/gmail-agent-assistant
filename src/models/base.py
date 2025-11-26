"""SQLAlchemy base configuration and engine management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import get_config


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


_async_engine = None
_sync_engine = None


def get_async_engine():
    """Get or create async database engine."""
    global _async_engine
    if _async_engine is None:
        config = get_config()
        _async_engine = create_async_engine(
            config.database.connection_string,
            echo=config.environment == "dev",
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _async_engine


def get_sync_engine():
    """Get or create sync database engine (for CLI/migrations)."""
    global _sync_engine
    if _sync_engine is None:
        config = get_config()
        _sync_engine = create_engine(
            config.database.sync_connection_string,
            echo=config.environment == "dev",
            pool_pre_ping=True,
        )
    return _sync_engine


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Get async session factory."""
    engine = get_async_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def get_sync_session():
    """Get sync session factory (for CLI)."""
    engine = get_sync_engine()
    return sessionmaker(engine, expire_on_commit=False)
