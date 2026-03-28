"""
Async Database Engine & Session for ULSS 9 Chatbot

Supports PostgreSQL (production) and SQLite (development/testing).
Uses SQLAlchemy 2.0 async engine with asyncpg or aiosqlite.
"""

import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import DATABASE_URL
from app.core.models import Base

logger = logging.getLogger(__name__)

# Convert sync URL to async driver
_db_url = DATABASE_URL
_connect_args: dict = {}

if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg does not accept sslmode/channel_binding as URL params — strip them
    # and pass ssl=True via connect_args instead
    if "sslmode=" in _db_url or "channel_binding=" in _db_url:
        _db_url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", _db_url)
        _db_url = _db_url.rstrip("?&")
        _connect_args = {"ssl": True}
elif _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Verify database connectivity. Schema is managed by Alembic migrations."""
    async with engine.connect() as conn:
        await conn.execute(sa.text("SELECT 1"))
    logger.info("Database connected", extra={"url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL})


async def close_db() -> None:
    """Dispose engine connections on shutdown."""
    await engine.dispose()
    logger.info("Database connections closed")


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for request-scoped DB sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Alias for code that imports get_db_session
get_db_session = get_db
