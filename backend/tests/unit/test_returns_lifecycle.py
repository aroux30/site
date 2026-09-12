"""Unit tests for Phase 13 / Phase 23 Returns (RMA) Domain Lifecycle and 7-day statutory eligibility."""  # noqa: E501

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions.handlers import ValidationError
from app.modules.orders.application.returns_service import ReturnsService
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.orders.domain.returns import (
    InspectionOutcome,
    ReturnItemSpec,
    ReturnReason,
    ReturnStatus,
)


@pytest.fixture
def sample_delivered_order():
    order_id = uuid.uuid4()
    user_id = uuid.uuid4()
    item_id = uuid.uuid4()
    variant_id = uuid.uuid4()

    item = OrderItem(
        id=item_id,
        order_id=order_id,
        variant_id=variant_id,
        sku="TEST-SKU-01",
        product_name="کالای آزمایشی",
        unit_price=10_000_000,
        quantity=2,
        total_price=20_000_000,
    )

    order = Order(
        id=order_id,
        user_id=user_id,
        order_number="ORD-20260911-0001",
        status=OrderStatus.DELIVERED,
        subtotal=20_000_000,
        total=20_000_000,
        items=[item],
    )
    return order, item


def test_return_eligibility_within_7_days_succeeds(sample_delivered_order):
    order, item = sample_delivered_order
    service = ReturnsService(return_window_days=7)
    delivered_at = datetime.now(UTC) - timedelta(days=3)

    return_item = ReturnItemSpec(
        order_item_id=item.id,
        variant_id=item.variant_id,
        quantity=1,
        reason=ReturnReason.CUSTOMER_REMORSE,
        customer_notes="انصراف از خرید ماده ۳۷",
    )

    rma = service.create_return_request(
        order=order,
        user_id=order.user_id,
        delivered_at=delivered_at,
        items=[return_item],
    )

    assert rma.status == ReturnStatus.REQUESTED
    assert len(rma.items) == 1
    assert rma.items[0].quantity == 1


def test_return_eligibility_exceeding_7_days_rejected(sample_delivered_order):
    order, item = sample_delivered_order
    service = ReturnsService(return_window_days=7)
    delivered_at = datetime.now(UTC) - timedelta(days=8)  # 8 days ago

    return_item = ReturnItemSpec(
        order_item_id=item.id,
        variant_id=item.variant_id,
        quantity=1,
        reason=ReturnReason.CUSTOMER_REMORSE,
    )

    with pytest.raises(ValidationError) as exc_info:
        service.create_return_request(
            order=order,
            user_id=order.user_id,
            delivered_at=delivered_at,
            items=[return_item],
        )

    assert "Return window of 7 days has expired" in exc_info.value.detail
    assert exc_info.value.error_code == "RETURN_WINDOW_EXPIRED"


def test_return_on_undelivered_order_rejected(sample_delivered_order):
    order, item = sample_delivered_order
    order.status = OrderStatus.SHIPPED  # In transit, not yet delivered
    service = ReturnsService(return_window_days=7)
    delivered_at = datetime.now(UTC)

    return_item = ReturnItemSpec(
        order_item_id=item.id,
        variant_id=item.variant_id,
        quantity=1,
        reason=ReturnReason.CUSTOMER_REMORSE,
    )

    with pytest.raises(ValidationError) as exc_info:
        service.create_return_request(
            order=order,
            user_id=order.user_id,
            delivered_at=delivered_at,
            items=[return_item],
        )

    assert exc_info.value.error_code == "ORDER_NOT_DELIVERED"


def test_return_excessive_quantity_rejected(sample_delivered_order):
    order, item = sample_delivered_order
    service = ReturnsService(return_window_days=7)
    delivered_at = datetime.now(UTC) - timedelta(days=1)

    return_item = ReturnItemSpec(
        order_item_id=item.id,
        variant_id=item.variant_id,
        quantity=5,  # Ordered was only 2
        reason=ReturnReason.DEFECTIVE,
    )

    with pytest.raises(ValidationError) as exc_info:
        service.create_return_request(
            order=order,
            user_id=order.user_id,
            delivered_at=delivered_at,
            items=[return_item],
        )

    assert exc_info.value.error_code == "INVALID_RETURN_QUANTITY"


def test_full_rma_lifecycle_transitions(sample_delivered_order):
    order, item = sample_delivered_order
    service = ReturnsService(return_window_days=7)
    delivered_at = datetime.now(UTC) - timedelta(days=2)

    return_item = ReturnItemSpec(
        order_item_id=item.id,
        variant_id=item.variant_id,
        quantity=1,
        reason=ReturnReason.DEFECTIVE,
    )

    rma = service.create_return_request(
        order=order,
        user_id=order.user_id,
        delivered_at=delivered_at,
        items=[return_item],
    )
    assert rma.status == ReturnStatus.REQUESTED

    # 1. Admin Approval
    service.approve_return(rma, admin_notes="تایید جهت ارسال به انبار مرجوعی")
    assert rma.status == ReturnStatus.APPROVED
    assert rma.approved_at is not None

    # 2. Receipt at warehouse
    service.mark_received(rma)
    assert rma.status == ReturnStatus.RECEIVED

    # 3. Quality Inspection
    service.complete_inspection(
        rma,
        outcomes={item.id: InspectionOutcome.DEFECTIVE_CONFIRMED},
        inspection_notes="ایراد فنی تایید شد",
    )
    assert rma.status == ReturnStatus.INSPECTED
    assert rma.items[0].inspection_outcome == InspectionOutcome.DEFECTIVE_CONFIRMED

    # 4. Refund processing
    service.process_refund(rma, refund_amount=10_000_000)
    assert rma.status == ReturnStatus.REFUNDED
    assert rma.refund_amount == 10_000_000

    # 5. Close RMA
    rma.transition_to(ReturnStatus.CLOSED)
    assert rma.status == ReturnStatus.CLOSED


def test_rma_illegal_transition_fails_closed(sample_delivered_order):
    order, item = sample_delivered_order
    service = ReturnsService(return_window_days=7)
    delivered_at = datetime.now(UTC) - timedelta(days=1)

    return_item = ReturnItemSpec(
        order_item_id=item.id,
        variant_id=item.variant_id,
        quantity=1,
        reason=ReturnReason.CUSTOMER_REMORSE,
    )

    rma = service.create_return_request(
        order=order,
        user_id=order.user_id,
        delivered_at=delivered_at,
        items=[return_item],
    )

    # Illegal jump: REQUESTED directly to REFUNDED without approval/inspection
    with pytest.raises(ValueError) as exc_info:
        rma.transition_to(ReturnStatus.REFUNDED)

    assert "Cannot transition return from 'requested' to 'refunded'" in str(exc_info.value)


from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.core.database.session import get_db
from app.core.security.jwt import create_access_token
from app.main import create_app


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
async def test_api_request_order_return_unauthorized(test_app):
    """Test POST /api/v1/orders/{order_id}/returns requires authentication."""
    order_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/orders/{order_id}/returns",
            json={"items": []},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_request_order_return_success(test_app, mock_db, sample_delivered_order):
    """Test POST /api/v1/orders/{order_id}/returns with authenticated user."""
    order, item = sample_delivered_order
    token = create_access_token(
        subject=str(order.user_id),
        extra_claims={"roles": ["customer"], "permissions": ["orders:read"]},
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = order
    mock_db.execute.return_value = mock_res

    payload = {
        "items": [
            {
                "order_item_id": str(item.id),
                "variant_id": str(item.variant_id),
                "quantity": 1,
                "reason": "customer_remorse",
                "customer_notes": "انصراف از خرید",
            }
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/orders/{order.id}/returns",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["order_id"] == str(order.id)
        assert data["status"] == "requested"
        assert len(data["items"]) == 1
        assert data["items"][0]["quantity"] == 1
