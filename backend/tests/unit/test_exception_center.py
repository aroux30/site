"""Unit tests for Phase 32 / Rule 32 / ADMIN-003 Operational Exception Center."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.modules.audit.domain.operational_exceptions import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    OperationalExceptionDomain,
)
from app.modules.audit.application.exception_center_service import (
    OperationalExceptionCenter,
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

    with patch("app.modules.audit.application.audit_service.log_action", new_callable=AsyncMock) as mock_log:
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
