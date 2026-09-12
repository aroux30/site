"""Unit tests for the Multi-Vendor / Marketplace module.

Tests domain models, Pydantic schemas, application service business logic,
and REST API endpoints with async mock DB sessions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError as PydanticValidationError

from app.core.database.session import get_db
from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.security.jwt import create_access_token
from app.main import create_app
from app.modules.catalog.domain.models import (
    Product,
    ProductVariant,
    SettlementStatus,
    Vendor,
    VendorSettlement,
)
from app.modules.vendors.application.vendor_service import (
    VendorService,
    admin_verify_vendor,
    calculate_vendor_earnings,
    create_settlement,
    generate_vendor_slug,
    get_vendor,
    get_vendor_by_slug,
    register_vendor,
)
from app.modules.vendors.schemas.vendor import (
    VendorEarningsResponse,
    VendorRegisterRequest,
    VendorResponse,
    VendorSettlementCreate,
)

# ============================================================================
# 1. Domain Models Tests
# ============================================================================


def test_vendor_model_attributes():
    """Verify Vendor model columns and defaults."""
    uid = uuid.uuid4()
    vendor = Vendor(
        id=uuid.uuid4(),
        user_id=uid,
        store_name="دیجی استور",
        slug="digi-store",
        description="توضیحات فروشگاه",
        national_id="0012345678",
        iban_number="IR120120000000001234567890",
        contact_phone="09121112233",
    )

    assert vendor.store_name == "دیجی استور"
    assert vendor.slug == "digi-store"
    assert vendor.commission_rate == 1000  # 10% default
    assert vendor.is_verified is False
    assert vendor.is_active is True
    assert vendor.rating == 5.0
    assert vendor.total_sales_count == 0
    assert "دیجی استور" in repr(vendor)


def test_vendor_settlement_model_attributes():
    """Verify VendorSettlement model columns and defaults."""
    vid = uuid.uuid4()
    now = datetime.now(UTC)
    settlement = VendorSettlement(
        id=uuid.uuid4(),
        vendor_id=vid,
        amount=50_000_000,
        period_start=now,
        period_end=now,
        status=SettlementStatus.PENDING,
        payment_reference="PAYA-123456",
    )

    assert settlement.vendor_id == vid
    assert settlement.amount == 50_000_000
    assert settlement.status == SettlementStatus.PENDING
    assert settlement.payment_reference == "PAYA-123456"
    assert "50000000" in repr(settlement)


def test_settlement_status_enum_values():
    """Verify SettlementStatus enum variants."""
    assert SettlementStatus.PENDING == "pending"
    assert SettlementStatus.APPROVED == "approved"
    assert SettlementStatus.PAID == "paid"
    assert SettlementStatus.REJECTED == "rejected"


def test_catalog_product_vendor_id_attribute():
    """Verify Product and ProductVariant have vendor_id FK column."""
    product = Product(
        id=uuid.uuid4(),
        name="کالای تست",
        slug="test-product",
        category_id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
    )
    assert product.vendor_id is not None

    variant = ProductVariant(
        id=uuid.uuid4(),
        product_id=product.id,
        sku="SKU-VENDOR-1",
        price=100000,
        vendor_id=product.vendor_id,
    )
    assert variant.vendor_id == product.vendor_id


# ============================================================================
# 2. Schemas Tests (Pydantic v2)
# ============================================================================


def test_vendor_register_request_valid():
    """Verify valid VendorRegisterRequest parsing and IBAN normalization."""
    req = VendorRegisterRequest(
        store_name="فروشگاه آفتاب",
        slug="aftab-shop",
        national_id="0012345678",
        iban_number="120120000000001234567890",  # Without IR prefix
        contact_phone="09123456789",
    )
    assert req.store_name == "فروشگاه آفتاب"
    assert req.slug == "aftab-shop"
    assert req.iban_number == "IR120120000000001234567890"


def test_vendor_register_request_invalid_iban():
    """Verify IBAN validation error on wrong length."""
    with pytest.raises(PydanticValidationError):
        VendorRegisterRequest(
            store_name="فروشگاه خطا",
            iban_number="IR12345",  # Too short
        )


def test_vendor_register_request_invalid_national_id():
    """Verify national ID validation error on wrong length."""
    with pytest.raises(PydanticValidationError):
        VendorRegisterRequest(
            store_name="فروشگاه خطا",
            national_id="123",  # Too short
        )


def test_vendor_settlement_create_schema():
    """Verify VendorSettlementCreate validation."""
    valid = VendorSettlementCreate(amount=10_000_000, payment_reference="REF-001")
    assert valid.amount == 10_000_000

    with pytest.raises(PydanticValidationError):
        VendorSettlementCreate(amount=0)

    with pytest.raises(PydanticValidationError):
        VendorSettlementCreate(amount=-500)


def test_vendor_response_serialization():
    """Verify VendorResponse model serialization."""
    now = datetime.now(UTC)
    vendor_id = uuid.uuid4()
    user_id = uuid.uuid4()

    resp = VendorResponse(
        id=vendor_id,
        user_id=user_id,
        store_name="فروشگاه نمونه",
        slug="sample-store",
        commission_rate=1200,
        is_verified=True,
        is_active=True,
        rating=4.9,
        total_sales_count=42,
        created_at=now,
        updated_at=now,
    )
    data = resp.model_dump()
    assert data["id"] == vendor_id
    assert data["commission_rate"] == 1200
    assert data["rating"] == 4.9


def test_vendor_earnings_response():
    """Verify VendorEarningsResponse structure."""
    vid = uuid.uuid4()
    earnings = VendorEarningsResponse(
        vendor_id=vid,
        store_name="فروشگاه ارس",
        total_sales=100_000_000,
        total_orders=15,
        total_items=30,
        commission_rate=1000,
        commission_amount=10_000_000,
        net_earnings=90_000_000,
        settled_amount=50_000_000,
        pending_settlement=40_000_000,
    )
    assert earnings.net_earnings == 90_000_000
    assert earnings.pending_settlement == 40_000_000


# ============================================================================
# 3. Slug Generation Tests
# ============================================================================


def test_generate_vendor_slug():
    """Test Persian and English slug generation."""
    assert generate_vendor_slug("فروشگاه پارس") == "frvshgah-pars"
    assert generate_vendor_slug("Apple Store Tehran") == "apple-store-tehran"
    assert generate_vendor_slug("فروشگاه ۱۲۳!") == "frvshgah-123"
    assert generate_vendor_slug("").startswith("vendor-")


# ============================================================================
# 4. Application Service Tests (with AsyncMock DB)
# ============================================================================


@pytest.mark.asyncio
async def test_register_vendor_success():
    """Test successful vendor registration."""
    db = AsyncMock()
    db.add = MagicMock()
    # Mock no existing user or slug
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result_empty

    user_id = uuid.uuid4()
    req = VendorRegisterRequest(
        store_name="فروشگاه نوین",
        slug="novin-store",
        description="توضیحات",
    )

    vendor = await register_vendor(db, user_id, req)

    assert vendor.store_name == "فروشگاه نوین"
    assert vendor.slug == "novin-store"
    assert vendor.commission_rate == 1000
    assert vendor.is_verified is False
    assert vendor.is_active is True
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_vendor_duplicate_user_conflict():
    """Test registering when user already has a vendor raises ConflictError."""
    db = AsyncMock()
    existing_vendor = MagicMock(spec=Vendor)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_vendor
    db.execute.return_value = mock_result

    user_id = uuid.uuid4()
    req = VendorRegisterRequest(store_name="فروشگاه تکراری")

    with pytest.raises(ConflictError, match="already registered as a vendor"):
        await register_vendor(db, user_id, req)


@pytest.mark.asyncio
async def test_get_vendor_success_and_not_found():
    """Test get_vendor retrieval and 404 handling."""
    db = AsyncMock()
    vendor_id = uuid.uuid4()
    mock_vendor = Vendor(
        id=vendor_id,
        user_id=uuid.uuid4(),
        store_name="فروشگاه تست",
        slug="test-vendor",
    )

    # Success case
    mock_res_found = MagicMock()
    mock_res_found.scalar_one_or_none.return_value = mock_vendor
    db.execute.return_value = mock_res_found

    res = await get_vendor(db, vendor_id)
    assert res.id == vendor_id

    # Not found case
    mock_res_empty = MagicMock()
    mock_res_empty.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_res_empty

    with pytest.raises(NotFoundError):
        await get_vendor(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_vendor_by_slug():
    """Test get_vendor_by_slug."""
    db = AsyncMock()
    mock_vendor = Vendor(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        store_name="فروشگاه تست",
        slug="my-cool-store",
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_vendor
    db.execute.return_value = mock_res

    res = await get_vendor_by_slug(db, "my-cool-store")
    assert res.slug == "my-cool-store"

    # Not found
    mock_res.scalar_one_or_none.return_value = None
    with pytest.raises(NotFoundError):
        await get_vendor_by_slug(db, "unknown-slug")


@pytest.mark.asyncio
async def test_admin_verify_vendor():
    """Test admin verification approval."""
    db = AsyncMock()
    vendor_id = uuid.uuid4()
    vendor = Vendor(
        id=vendor_id,
        user_id=uuid.uuid4(),
        store_name="فروشگاه در انتظار",
        slug="pending-store",
        is_verified=False,
        is_active=False,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = vendor
    db.execute.return_value = mock_res

    updated = await admin_verify_vendor(db, vendor_id, verified=True)
    assert updated.is_verified is True
    assert updated.is_active is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_calculate_vendor_earnings():
    """Test calculation of sales, commission, and pending settlements."""
    db = AsyncMock()
    vendor_id = uuid.uuid4()
    vendor = Vendor(
        id=vendor_id,
        user_id=uuid.uuid4(),
        store_name="فروشگاه محاسبات",
        slug="calc-store",
        commission_rate=1500,  # 15%
    )

    # First call: get_vendor
    mock_vendor_res = MagicMock()
    mock_vendor_res.scalar_one_or_none.return_value = vendor

    # Second call: order items query
    item1 = MagicMock(total_price=20_000_000, quantity=2, order_id=uuid.uuid4())
    item2 = MagicMock(total_price=30_000_000, quantity=3, order_id=uuid.uuid4())
    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [item1, item2]

    # Third call: settled amount query
    mock_settlement_res = MagicMock()
    mock_settlement_res.scalar_one.return_value = 10_000_000

    db.execute.side_effect = [mock_vendor_res, mock_items_res, mock_settlement_res]

    earnings = await calculate_vendor_earnings(db, vendor_id)

    assert earnings["total_sales"] == 50_000_000
    assert earnings["total_items"] == 5
    assert earnings["total_orders"] == 2
    assert earnings["commission_rate"] == 1500
    # 50,000,000 * 15% = 7,500,000
    assert earnings["commission_amount"] == 7_500_000
    # 50,000,000 - 7,500,000 = 42,500,000
    assert earnings["net_earnings"] == 42_500_000
    assert earnings["settled_amount"] == 10_000_000
    # 42,500,000 - 10,000,000 = 32,500,000
    assert earnings["pending_settlement"] == 32_500_000


@pytest.mark.asyncio
async def test_create_settlement_success_and_validation():
    """Test creating a vendor settlement record."""
    db = AsyncMock()
    db.add = MagicMock()
    vendor_id = uuid.uuid4()
    vendor = Vendor(
        id=vendor_id,
        user_id=uuid.uuid4(),
        store_name="فروشگاه تسویه",
        slug="settlement-store",
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = vendor
    db.execute.return_value = mock_res

    # Valid amount
    settlement = await create_settlement(
        db, vendor_id, amount=25_000_000, payment_reference="REF-888"
    )
    assert settlement.amount == 25_000_000
    assert settlement.status == SettlementStatus.PENDING
    assert settlement.payment_reference == "REF-888"
    db.add.assert_called_once()

    # Invalid amount <= 0
    with pytest.raises(ValidationError, match="greater than zero"):
        await create_settlement(db, vendor_id, amount=0)


@pytest.mark.asyncio
async def test_vendor_service_oo_wrapper():
    """Test VendorService class delegation."""
    db = AsyncMock()
    svc = VendorService(db)
    vendor_id = uuid.uuid4()
    vendor = Vendor(id=vendor_id, user_id=uuid.uuid4(), store_name="تست شی گرایی", slug="oo-test")

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = vendor
    db.execute.return_value = mock_res

    res = await svc.get_vendor(vendor_id)
    assert res.id == vendor_id


# ============================================================================
# 5. REST API Endpoints Tests (with TestClient & Overrides)
# ============================================================================


@pytest.fixture
def mock_db():
    """Mock AsyncSession for dependency override."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def test_app(mock_db):
    """Create FastAPI application with get_db overridden."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_public_list_vendors(test_app, mock_db):
    """Test GET /api/v1/vendors and GET /vendors."""
    vendor1 = Vendor(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        store_name="فروشگاه ۱",
        slug="store-1",
        is_verified=True,
        is_active=True,
    )
    mock_count = MagicMock()
    mock_count.scalar_one.return_value = 1
    mock_items = MagicMock()
    mock_items.scalars.return_value.all.return_value = [vendor1]

    mock_db.execute.side_effect = [mock_count, mock_items]

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/vendors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["slug"] == "store-1"

        # Also test /vendors root prefix
        mock_db.execute.side_effect = [mock_count, mock_items]
        resp_root = await ac.get("/vendors")
        assert resp_root.status_code == 200


@pytest.mark.asyncio
async def test_api_get_vendor_by_slug(test_app, mock_db):
    """Test GET /api/v1/vendors/{slug}."""
    vendor = Vendor(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        store_name="فروشگاه انحصاری",
        slug="exclusive-store",
        is_verified=True,
        is_active=True,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = vendor
    mock_db.execute.return_value = mock_res

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/vendors/exclusive-store")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "exclusive-store"
        assert data["store_name"] == "فروشگاه انحصاری"


@pytest.mark.asyncio
async def test_api_register_vendor_requires_auth(test_app):
    """Test POST /api/v1/vendors/register without auth header returns 401."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/vendors/register",
            json={"store_name": "فروشگاه بدون احراز"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_register_vendor_success(test_app, mock_db):
    """Test POST /api/v1/vendors/register with authenticated user."""
    user_id = uuid.uuid4()
    token = create_access_token(
        subject=str(user_id),
        extra_claims={"roles": ["customer"], "permissions": ["orders:read"]},
    )

    # Mock no existing user and no existing slug
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/vendors/register",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "store_name": "فروشگاه جدید",
                "slug": "new-store",
                "contact_phone": "09120001122",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["store_name"] == "فروشگاه جدید"
        assert data["slug"] == "new-store"


@pytest.mark.asyncio
async def test_api_vendor_me_earnings(test_app, mock_db):
    """Test GET /api/v1/vendors/me vendor sales & earnings endpoint."""
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    token = create_access_token(
        subject=str(user_id),
        extra_claims={"roles": ["vendor"], "permissions": ["orders:read"]},
    )

    vendor = Vendor(
        id=vendor_id,
        user_id=user_id,
        store_name="فروشگاه خودم",
        slug="my-own-store",
        commission_rate=1000,
    )

    # First execute: get_vendor_by_user_id
    mock_v_res = MagicMock()
    mock_v_res.scalar_one_or_none.return_value = vendor

    # Second execute: get_vendor in calculate_vendor_earnings
    mock_v2_res = MagicMock()
    mock_v2_res.scalar_one_or_none.return_value = vendor

    # Third execute: order items
    item = MagicMock(total_price=10_000_000, quantity=1, order_id=uuid.uuid4())
    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [item]

    # Fourth execute: settlements sum
    mock_settle_res = MagicMock()
    mock_settle_res.scalar_one.return_value = 0

    mock_db.execute.side_effect = [mock_v_res, mock_v2_res, mock_items_res, mock_settle_res]

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/vendors/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vendor_id"] == str(vendor_id)
        assert data["total_sales"] == 10_000_000
        assert data["commission_amount"] == 1_000_000
        assert data["net_earnings"] == 9_000_000
        assert data["pending_settlement"] == 9_000_000


@pytest.mark.asyncio
async def test_api_admin_verify_vendor(test_app, mock_db):
    """Test PATCH /api/v1/admin/vendors/{id}/verify."""
    admin_id = uuid.uuid4()
    token = create_access_token(
        subject=str(admin_id),
        extra_claims={"roles": ["super_admin"], "permissions": ["*"]},
    )
    vendor_id = uuid.uuid4()
    vendor = Vendor(
        id=vendor_id,
        user_id=uuid.uuid4(),
        store_name="فروشگاه تایید",
        slug="verify-store",
        is_verified=False,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = vendor
    mock_db.execute.return_value = mock_res

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/admin/vendors/{vendor_id}/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"verified": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_verified"] is True


@pytest.mark.asyncio
async def test_api_admin_vendor_settlements(test_app, mock_db):
    """Test GET and POST /api/v1/admin/vendors/{id}/settlements."""
    admin_id = uuid.uuid4()
    token = create_access_token(
        subject=str(admin_id),
        extra_claims={"roles": ["super_admin"], "permissions": ["*"]},
    )
    vendor_id = uuid.uuid4()
    vendor = Vendor(
        id=vendor_id,
        user_id=uuid.uuid4(),
        store_name="فروشگاه تسویه‌حساب",
        slug="settle-store",
    )

    # 1. GET settlements
    mock_vendor_res = MagicMock()
    mock_vendor_res.scalar_one_or_none.return_value = vendor
    mock_count = MagicMock()
    mock_count.scalar_one.return_value = 0
    mock_items = MagicMock()
    mock_items.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_vendor_res, mock_count, mock_items]

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/admin/vendors/{vendor_id}/settlements",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

        # 2. POST create settlement
        mock_db.execute.side_effect = None
        mock_db.execute.return_value = mock_vendor_res

        resp_create = await ac.post(
            f"/api/v1/admin/vendors/{vendor_id}/settlements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": 15_000_000,
                "payment_reference": "PAYA-998877",
            },
        )
        assert resp_create.status_code == 201
        create_data = resp_create.json()
        assert create_data["amount"] == 15_000_000
        assert create_data["payment_reference"] == "PAYA-998877"
        assert create_data["status"] == "pending"
