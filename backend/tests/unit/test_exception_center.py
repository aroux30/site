"""Unit tests for Phase 32 / Rule 32 / ADMIN-003 Operational Exception Center."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.audit.application.exception_center_service import (
    OperationalExceptionCenter,
)
from app.modules.audit.domain.operational_exceptions import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
)


@pytest.fixture
def center():
    return OperationalExceptionCenter()


@pytest.mark.asyncio
async def test_record_critical_price_mismatch(center):
    """Verify recording of critical PRICE_MISMATCH anomaly."""
    exc = await center.record_exception(
        db=None,
        exception_type=ExceptionType.PRICE_MISMATCH,
        severity=ExceptionSeverity.CRITICAL,
        entity_type="order",
        entity_id=str(uuid.uuid4()),
        details={
            "expected_total": 50_000_000,
            "calculated_total": 45_000_000,
            "reason": "Tampered client subtotal",
        },
    )

    assert exc.exception_type == ExceptionType.PRICE_MISMATCH
    assert exc.severity == ExceptionSeverity.CRITICAL
    assert exc.status == ExceptionStatus.OPEN
    assert exc.details["expected_total"] == 50_000_000

    fetched = center.get_exception(exc.id)
    assert fetched is exc


@pytest.mark.asyncio
async def test_record_with_db_audit_log(center):
    """Verify recording an anomaly with DB session creates an AuditLog row."""
    mock_db = AsyncMock()

    with patch(
        "app.modules.audit.application.audit_service.log_action", new_callable=AsyncMock
    ) as mock_log:
        exc = await center.record_exception(
            db=mock_db,
            exception_type=ExceptionType.INVENTORY_CONFLICT,
            severity=ExceptionSeverity.HIGH,
            entity_type="variant",
            entity_id=str(uuid.uuid4()),
            details={"requested": 2, "available": 0},
        )
        mock_log.assert_called_once()
        assert exc.exception_type == ExceptionType.INVENTORY_CONFLICT


@pytest.mark.asyncio
async def test_exception_lifecycle_workflow(center):
    """Verify assignment, investigation, and resolution workflow."""
    exc = await center.record_exception(
        db=None,
        exception_type=ExceptionType.PAYMENT_TIMEOUT,
        severity=ExceptionSeverity.HIGH,
        entity_type="payment",
        entity_id=str(uuid.uuid4()),
        details={"gateway": "zarinpal", "authority": "A0001"},
    )
    assert exc.status == ExceptionStatus.OPEN
    assert exc.owner_id is None

    # Assign to admin investigator
    admin_id = uuid.uuid4()
    center.assign_owner(exc.id, admin_id)
    assert exc.owner_id == admin_id
    assert exc.status == ExceptionStatus.INVESTIGATING

    # Resolve exception
    center.resolve_exception(exc.id, notes="Verified callback with PSP; payment was refunded")
    assert exc.status == ExceptionStatus.RESOLVED
    assert exc.resolved_at is not None
    assert "Verified callback" in (exc.resolution_notes or "")


@pytest.mark.asyncio
async def test_list_and_filter_exceptions(center):
    """Verify filtering exceptions by severity and status."""
    e1 = await center.record_exception(
        db=None,
        exception_type=ExceptionType.DUPLICATE_ORDER,
        severity=ExceptionSeverity.CRITICAL,
        entity_type="order",
        entity_id="1",
        details={},
    )
    e2 = await center.record_exception(
        db=None,
        exception_type=ExceptionType.WEBHOOK_REPLAY,
        severity=ExceptionSeverity.MEDIUM,
        entity_type="webhook",
        entity_id="2",
        details={},
    )

    critical_list = center.list_exceptions(severity=ExceptionSeverity.CRITICAL)
    assert len(critical_list) == 1
    assert critical_list[0].id == e1.id

    center.resolve_exception(e1.id, "Handled")
    open_list = center.list_exceptions(status=ExceptionStatus.OPEN)
    assert len(open_list) == 1
    assert open_list[0].id == e2.id


@pytest.mark.asyncio
async def test_api_admin_exception_center_endpoints():
    """Verify Admin Exception Center REST APIs."""
    from httpx import ASGITransport, AsyncClient

    from app.core.security.jwt import create_access_token
    from app.main import create_app
    from app.modules.audit.application.exception_center_service import exception_center

    app = create_app()
    admin_id = uuid.uuid4()
    admin_token = create_access_token(
        subject=str(admin_id),
        extra_claims={"roles": ["super_admin"], "permissions": ["*"]},
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Record anomaly in global registry
    exc = await exception_center.record_exception(
        db=None,
        exception_type=ExceptionType.PRICE_MISMATCH,
        severity=ExceptionSeverity.CRITICAL,
        entity_type="order",
        entity_id="ord-9988",
        details={"diff": 100000},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. List
        resp = await ac.get("/api/v1/audit/admin/exceptions", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert any(i["id"] == str(exc.id) for i in items)

        # 2. Assign
        resp_assign = await ac.patch(
            f"/api/v1/audit/admin/exceptions/{exc.id}/assign",
            headers=headers,
            json={"owner_id": str(admin_id)},
        )
        assert resp_assign.status_code == 200
        assert resp_assign.json()["owner_id"] == str(admin_id)
        assert resp_assign.json()["status"] == "INVESTIGATING"

        # 3. Resolve
        resp_resolve = await ac.patch(
            f"/api/v1/audit/admin/exceptions/{exc.id}/resolve",
            headers=headers,
            json={"resolution_notes": "Recalculated order with server tax rule"},
        )
        assert resp_resolve.status_code == 200
        assert resp_resolve.json()["status"] == "RESOLVED"
