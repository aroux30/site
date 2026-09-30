"""Invoicing API — admin fiscal document endpoints + customer document view.

Admin endpoints are guarded by ``invoicing:read`` / ``invoicing:write``
permissions (RequirePermissions pattern). The customer endpoint
``GET /orders/{id}/invoice-document`` returns the posted fiscal document's
archived snapshot when one exists and otherwise falls back to the legacy
rendered receipt HTML — backward compatible with ``GET /orders/{id}/invoice``.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.exceptions.handlers import ForbiddenError, NotFoundError
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_active_user,
    get_current_user_id,
)
from app.modules.invoicing.application import invoice_service
from app.modules.invoicing.domain.models import InvoiceStatus, InvoiceType
from app.modules.invoicing.schemas.invoice import (
    CancelInvoiceRequest,
    ChainVerificationResponse,
    InvoiceListResponse,
    InvoiceResponse,
)
from app.modules.orders.domain.models import Order

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Public router carries the customer-facing document endpoint.
router = APIRouter(tags=["invoicing"])

admin_router = APIRouter(prefix="/admin", tags=["admin-invoicing"])

_require_read = Depends(RequirePermissions("invoicing:read"))
_require_write = Depends(RequirePermissions("invoicing:write"))


# ---------------------------------------------------------------------------
# Admin: list / detail
# ---------------------------------------------------------------------------


@admin_router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List fiscal documents (admin)",
    dependencies=[_require_read],
)
async def list_invoices(
    status: str | None = Query(None),
    fiscal_period: str | None = Query(None),
    type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    status_filter = InvoiceStatus(status) if status else None
    type_filter = InvoiceType(type) if type else None
    rows, total = await invoice_service.list_invoices(
        db,
        status=status_filter,
        fiscal_period=fiscal_period,
        doc_type=type_filter,
        page=page,
        page_size=page_size,
    )
    return InvoiceListResponse(
        items=[InvoiceResponse.from_invoice(inv) for inv in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/invoices/verify-chain",
    response_model=ChainVerificationResponse,
    summary="Verify the fiscal hash chain (admin)",
    dependencies=[_require_read],
)
async def verify_chain(
    type: str | None = Query(None),
    fiscal_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ChainVerificationResponse:
    type_filter = InvoiceType(type) if type else None
    report = await invoice_service.verify_chain(
        db, doc_type=type_filter, fiscal_period=fiscal_period
    )
    return ChainVerificationResponse(**report)


@admin_router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Fiscal document detail (admin)",
    dependencies=[_require_read],
)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.get_invoice(db, invoice_id)
    return InvoiceResponse.from_invoice(invoice)


# ---------------------------------------------------------------------------
# Admin: lifecycle transitions
# ---------------------------------------------------------------------------


@admin_router.post(
    "/invoices/{invoice_id}/post",
    response_model=InvoiceResponse,
    summary="Post a draft invoice (allocate number + hash, admin)",
    dependencies=[_require_write],
)
async def post_invoice(
    invoice_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.post_invoice(db, invoice_id=invoice_id, actor_id=user_id)
    await db.commit()
    return InvoiceResponse.from_invoice(invoice)


@admin_router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel a draft or posted-before-payment invoice (admin)",
    dependencies=[_require_write],
)
async def cancel_invoice(
    invoice_id: uuid.UUID,
    body: CancelInvoiceRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.cancel_invoice(
        db, invoice_id=invoice_id, reason=body.reason, actor_id=user_id
    )
    await db.commit()
    return InvoiceResponse.from_invoice(invoice)


@admin_router.post(
    "/invoices/{invoice_id}/mark-paid",
    response_model=InvoiceResponse,
    summary="Mark a posted invoice as paid (admin)",
    dependencies=[_require_write],
)
async def mark_invoice_paid(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.mark_paid(db, invoice_id=invoice_id)
    await db.commit()
    return InvoiceResponse.from_invoice(invoice)


@admin_router.post(
    "/invoices/orders/{order_id}/create-draft",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Create (or return) the draft invoice for an order (admin)",
    dependencies=[_require_write],
)
async def create_draft_for_order(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    invoice, _created = await invoice_service.create_draft_for_order(
        db, order_id=order_id, created_by=user_id
    )
    await db.commit()
    return InvoiceResponse.from_invoice(invoice)


# ---------------------------------------------------------------------------
# Admin: archived document download
# ---------------------------------------------------------------------------


@admin_router.get(
    "/invoices/{invoice_id}/archive",
    summary="Download the archived fiscal document (admin)",
    dependencies=[_require_read],
)
async def download_archive(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    invoice = await invoice_service.get_invoice(db, invoice_id)
    if not invoice.archive_path:
        raise NotFoundError("InvoiceArchive", "این سند هنوز بایگانی نشده است")

    settings = get_settings()
    base_dir = Path(getattr(settings, "UPLOAD_DIR", "media")).resolve()
    file_path = (base_dir / invoice.archive_path).resolve()
    # Path traversal guard: the stored path must stay under the upload root.
    if not str(file_path).startswith(str(base_dir)) or not file_path.exists():
        raise NotFoundError("InvoiceArchive", "فایل بایگانی یافت نشد")

    media_type = (invoice.archive_content_type or "application/octet-stream").split(";")[0]
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"{invoice.number or invoice.id}{file_path.suffix}",
    )


# ---------------------------------------------------------------------------
# Customer-facing: fiscal document with legacy fallback
# ---------------------------------------------------------------------------


@router.get(
    "/orders/{order_id}/invoice-document",
    response_class=HTMLResponse,
    summary="Get the posted fiscal document for an order (falls back to the rendered receipt)",
)
async def get_order_invoice_document(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    claims: dict[str, Any] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Return the posted fiscal document HTML when available, else the legacy receipt.

    Ownership rule mirrors the legacy invoice endpoint: the order owner or an
    admin permission holder. The returned HTML is the archived snapshot for a
    posted document (frozen at post time) or the live-rendered receipt for
    orders with no posted invoice yet.
    """
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order")

    permissions = set(claims.get("permissions", []))
    roles = set(claims.get("roles", []))
    is_admin = bool({"orders:read", "orders:write", "admin:access", "invoicing:read"} & permissions) or bool(
        {"admin", "superadmin"} & roles
    )
    if not is_admin and order.user_id != user_id:
        raise ForbiddenError("You do not have permission to view this invoice")

    invoice = await invoice_service.get_invoice_for_order(db, order_id)
    if invoice is not None and invoice.status in (
        InvoiceStatus.POSTED,
        InvoiceStatus.PAID,
    ) and invoice.archive_path:
        settings = get_settings()
        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media")).resolve()
        file_path = (base_dir / invoice.archive_path).resolve()
        if str(file_path).startswith(str(base_dir)) and file_path.exists():
            return HTMLResponse(
                content=file_path.read_text(encoding="utf-8"),
                headers={"X-Invoice-Number": invoice.number or ""},
            )

    # Fallback: the legacy rendered receipt (unchanged presentation layer).
    from app.modules.orders.application.invoice_service import (
        generate_invoice_html_for_order,
    )

    html = await generate_invoice_html_for_order(
        db=db,
        order_id_or_number=order_id,
        requesting_user_id=user_id,
        user_permissions=permissions,
        user_roles=roles,
    )
    return HTMLResponse(content=html)
