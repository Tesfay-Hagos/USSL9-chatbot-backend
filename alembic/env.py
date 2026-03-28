"""
Alembic Environment — ULSS 9 Chatbot Migrations

Supports both sync (alembic upgrade) and async execution.
Reads DATABASE_URL from app config.
"""

import asyncio
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import our models so Alembic sees them
from app.core.models import Base  # noqa: F401
from app.config import DATABASE_URL

# Alembic Config object
config = context.config

# Set the sqlalchemy.url from our app config
_PG_PREFIX = "postgresql://"
_db_url = DATABASE_URL
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
elif _db_url.startswith(_PG_PREFIX):
    _db_url = _db_url.replace(_PG_PREFIX, "postgresql+asyncpg://", 1)
    # asyncpg does not accept sslmode/channel_binding as URL params — strip them
    _db_url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", _db_url)
    _db_url = _db_url.rstrip("?&")
config.set_main_option("sqlalchemy.url", _db_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a live connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode (PostgreSQL + asyncpg)."""
    connect_args = {"ssl": True} if DATABASE_URL.startswith(_PG_PREFIX) else {}
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
