"""Pytest configuration and shared fixtures for API tests."""

import asyncio
import os

# ── Isolate tests from the production database ────────────────────────────────
# MUST be set before any app module is imported.  app.core.database creates the
# SQLAlchemy engine at import time by reading DATABASE_URL from app.config, so
# if we don't override it here first the tests will write to the real DB.
_TEST_DB_PATH = "./data/test_ulss9.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
# ─────────────────────────────────────────────────────────────────────────────

import pytest
from fastapi.testclient import TestClient

from app.api.auth import require_admin
from app.core.database import async_session_factory, close_db, init_db
from app.main import app
from app.services.admin_seed import seed_admin_user
from app.services.store_registry import seed_initial_stores


def _fake_require_admin() -> str:
    """Bypass auth for tests. Returns email for consistency."""
    return "test@test.com"


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    """Create a fresh isolated test DB, seed it once per session, then delete it."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    loop.run_until_complete(seed_initial_stores())
    loop.run_until_complete(seed_admin_user())
    yield
    loop.run_until_complete(close_db())
    loop.close()
    # Remove the test DB file so it does not persist between runs and can never
    # be confused with the production database.
    try:
        os.remove(_TEST_DB_PATH)
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def _clean_corrections_after_test():
    """Truncate the corrections table after every test.

    Prevents corrections written during a test from appearing in subsequent
    tests or (if the wrong DB URL were used) in the admin UI.
    """
    yield
    from app.core.models import CorrectionRecord
    from sqlalchemy import delete

    async def _truncate():
        async with async_session_factory() as session:
            await session.execute(delete(CorrectionRecord))
            await session.commit()

    asyncio.run(_truncate())


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client (no live server). Overrides auth for admin tests."""
    app.dependency_overrides[require_admin] = _fake_require_admin
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
