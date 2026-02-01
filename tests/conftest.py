"""Pytest configuration and shared fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client (no live server)."""
    return TestClient(app)
