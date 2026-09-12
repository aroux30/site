"""Direct Pay invoices and dynamic gateway configuration service (Karta Phase 3/5).

Implements:
- Quick standalone invoice creation without shopping cart cycle (Karta Directpay)
- Dynamic gateway registry, priority ordering, and active failover (Karta Gateways)
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.payments.domain.fintech_models import (
    DirectInvoice,
    DirectInvoiceStatus,
    GatewaySetting,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def create_direct_invoice(
    db: AsyncSession,
    amount: int,
    title: str,
    description: str | None = None,
    user_id: uuid.UUID | None = None,
    payer_name: str | None = None,
    payer_mobile: str | None = None,
    ttl_hours: int = 72,
) -> DirectInvoice:
    """Create a standalone quick invoice with a human-friendly invoice number."""
    if amount <= 0:
        raise ValidationError("مبلغ فاکتور باید بزرگتر از صفر باشد")

    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("عنوان فاکتور مستقیم الزامی است")

    inv_num = f"DIR-{datetime.now(UTC).strftime('%Y%m')}-{secrets.token_hex(3).upper()}"
    safe_user_id = uuid.UUID(str(user_id)) if user_id else None
    now = datetime.now(UTC)

    invoice = DirectInvoice(
        invoice_number=inv_num,
        user_id=safe_user_id,
        amount=amount,
        title=clean_title,
        description=description,
        payer_name=payer_name,
        payer_mobile=payer_mobile,
        status=DirectInvoiceStatus.UNPAID,
        expire_at=now + timedelta(hours=ttl_hours),
    )
    db.add(invoice)
    await db.flush()

    await logger.ainfo(
        "direct_invoice_created",
        invoice_id=str(invoice.id),
        invoice_number=inv_num,
        amount=amount,
    )
    return invoice


async def get_direct_invoice_by_id(
    db: AsyncSession,
    invoice_id: uuid.UUID,
) -> DirectInvoice:
    """Retrieve direct invoice by its unique UUID."""
    safe_id = uuid.UUID(str(invoice_id))
    inv = await db.get(DirectInvoice, safe_id)
    if inv is None:
        raise NotFoundError(resource="DirectInvoice", detail="فاکتور مستقیم مورد نظر یافت نشد")
    return inv


async def mark_direct_invoice_paid(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> DirectInvoice:
    """Mark a direct invoice as paid upon gateway verification."""
    safe_inv_id = uuid.UUID(str(invoice_id))
    inv = await db.get(DirectInvoice, safe_inv_id)
    if inv is None:
        raise NotFoundError(resource="DirectInvoice", detail=f"Invoice {safe_inv_id} not found")

    inv.status = DirectInvoiceStatus.PAID
    inv.payment_id = uuid.UUID(str(payment_id))
    inv.paid_at = datetime.now(UTC)
    await db.flush()

    return inv


async def list_active_gateways(
    db: AsyncSession,
) -> list[GatewaySetting]:
    """List all active payment gateways ordered by priority."""
    stmt = (
        select(GatewaySetting)
        .where(GatewaySetting.is_active.is_(True))
        .order_by(GatewaySetting.priority.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def configure_gateway_setting(
    db: AsyncSession,
    provider_key: str,
    title_fa: str,
    is_active: bool = True,
    is_default: bool = False,
    priority: int = 0,
    min_amount: int = 10_000,
    max_amount: int = 500_000_000,
    credentials: dict[str, Any] | None = None,
) -> GatewaySetting:
    """Configure or update gateway runtime settings and priority."""
    clean_key = provider_key.strip().lower()

    # Load all settings and find by key in memory to prevent raw string SQL queries
    stmt = select(GatewaySetting)
    all_gw = list((await db.execute(stmt)).scalars().all())
    gw = next((g for g in all_gw if g.provider_key == clean_key), None)

    if gw is None:
        gw = GatewaySetting(
            provider_key=clean_key,
            title_fa=title_fa,
            is_active=is_active,
            is_default=is_default,
            priority=priority,
            min_amount=min_amount,
            max_amount=max_amount,
            credentials=credentials,
        )
        db.add(gw)
    else:
        gw.title_fa = title_fa
        gw.is_active = is_active
        gw.is_default = is_default
        gw.priority = priority
        gw.min_amount = min_amount
        gw.max_amount = max_amount
        if credentials:
            gw.credentials = credentials

    await db.flush()
    return gw
