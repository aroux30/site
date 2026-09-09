"""Pytest test fixtures and configuration."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# Set test environment
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"

from app.core.database.session import engine
from app.core.security.jwt import create_access_token
from app.main import create_app


@pytest.fixture(autouse=True)
async def dispose_engine():
    """Ensure asyncpg engine connection pool is disposed cleanly between tests."""
    yield
    await engine.dispose()


@pytest.fixture
def app():
    """FastAPI application instance."""
    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Stable UUID for test customer."""
    return uuid.uuid4()


@pytest.fixture
def test_admin_id() -> uuid.UUID:
    """Stable UUID for test administrator."""
    return uuid.uuid4()


@pytest.fixture
def user_token(test_user_id: uuid.UUID) -> str:
    """Valid customer JWT access token."""
    return create_access_token(
        subject=str(test_user_id),
        extra_claims={
            "roles": ["customer"],
            "permissions": ["orders:read", "cart:write", "wishlist:write"],
        },
    )


@pytest.fixture
def admin_token(test_admin_id: uuid.UUID) -> str:
    """Valid administrator JWT access token with wildcard permissions."""
    return create_access_token(
        subject=str(test_admin_id),
        extra_claims={
            "roles": ["super_admin"],
            "permissions": ["*"],
        },
    )


@pytest.fixture
def auth_headers(user_token: str) -> dict[str, str]:
    """Authorization headers for regular user requests."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Authorization headers for admin requests."""
    return {"Authorization": f"Bearer {admin_token}"}
