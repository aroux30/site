"""Integration tests for core API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verify liveness probe returns 200 OK."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_public_settings(client: AsyncClient):
    """Verify public settings endpoint returns a list."""
    response = await client.get("/api/v1/settings/public")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_payment_methods(client: AsyncClient):
    """Verify payment methods endpoint returns enabled providers."""
    response = await client.get("/api/v1/payments/methods")
    assert response.status_code == 200
    data = response.json()
    assert "methods" in data
    assert len(data["methods"]) > 0


@pytest.mark.asyncio
async def test_shipping_methods(client: AsyncClient):
    """Verify shipping methods returns list."""
    response = await client.get("/api/v1/shipping/methods")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_catalog_categories(client: AsyncClient):
    """Verify catalog categories endpoint returns paginated/items list."""
    response = await client.get("/api/v1/catalog/categories")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_catalog_products(client: AsyncClient):
    """Verify catalog products list returns items and meta."""
    response = await client.get("/api/v1/catalog/products")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_gamification_rewards(client: AsyncClient):
    """Verify public gamification rewards endpoint."""
    response = await client.get("/api/v1/gamification/rewards")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_recommendations_trending(client: AsyncClient):
    """Verify trending recommendations returns items."""
    response = await client.get("/api/v1/recommendations/trending")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_blog_posts(client: AsyncClient):
    """Verify blog posts list returns items and total."""
    response = await client.get("/api/v1/blog/posts")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_unauthorized_profile_access(client: AsyncClient):
    """Verify protected /auth/me returns 401 Unauthorized without token."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_invoice_access(client: AsyncClient):
    """Verify protected /orders/{id}/invoice returns 401 Unauthorized without token."""
    response = await client.get("/api/v1/orders/11111111-1111-1111-1111-111111111111/invoice")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_vendor_endpoints(client: AsyncClient):
    """Verify vendor endpoints require authentication."""
    resp_reg = await client.post("/api/v1/vendors/register", json={"store_name": "تست"})
    assert resp_reg.status_code == 401

    resp_me = await client.get("/api/v1/vendors/me")
    assert resp_me.status_code == 401

    resp_admin = await client.get("/api/v1/admin/vendors")
    assert resp_admin.status_code == 401


