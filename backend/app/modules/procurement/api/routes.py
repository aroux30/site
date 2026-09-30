"""Procurement API — admin supplier + purchase-order endpoints.

Admin endpoints are guarded by ``procurement:read`` / ``procurement:write``
permissions (RequirePermissions pattern, mirroring invoicing). There is no
customer-facing surface in v1, so only ``admin_router`` is exposed;
main.py mounts it under ``/api/v1/admin/procurement/*``.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.procurement.application import procurement_service
from app.modules.procurement.application.procurement_service import POLineInput
from app.modules.procurement.domain.models import PurchaseOrderStatus, Supplier
from app.modules.procurement.schemas.procurement import (
    CreateSuggestedPORequest,
    PurchaseOrderCreateRequest,
    PurchaseOrderListResponse,
    PurchaseOrderReceiveRequest,
    PurchaseOrderResponse,
    PurchaseOrderUpdateRequest,
    SuggestedPOGroup,
    SuggestedPOLine,
    SuggestPOResponse,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierPreferredSetRequest,
    SupplierResponse,
    SupplierUpdateRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Module-level admin router; main.py mounts it under the /api/v1 prefix.
admin_router = APIRouter(prefix="/admin/procurement", tags=["admin-procurement"])

_require_read = Depends(RequirePermissions("procurement:read"))
_require_write = Depends(RequirePermissions("procurement:write"))


def _line_inputs(body_lines: list) -> list[POLineInput]:
    return [
        POLineInput(
            product_variant_id=line.product_variant_id,
            qty_ordered=line.qty_ordered,
            unit_price_rial=line.unit_price_rial,
            tax_basis_points=line.tax_basis_points,
            note=line.note,
        )
        for line in body_lines
    ]


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


@admin_router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=201,
    summary="Create a supplier (admin)",
    dependencies=[_require_write],
)
async def create_supplier(
    body: SupplierCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    supplier = await procurement_service.create_supplier(
        db,
        name=body.name,
        code=body.code,
        contact_info=body.contact_info,
        payment_terms_days=body.payment_terms_days,
        is_active=body.is_active,
    )
    await db.commit()
    return SupplierResponse.model_validate(supplier)


@admin_router.get(
    "/suppliers",
    response_model=SupplierListResponse,
    summary="List suppliers (admin)",
    dependencies=[_require_read],
)
async def list_suppliers(
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> SupplierListResponse:
    rows, total = await procurement_service.list_suppliers(
        db, is_active=is_active, search=search, page=page, page_size=page_size
    )
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Supplier detail (admin)",
    dependencies=[_require_read],
)
async def get_supplier(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    supplier = await procurement_service.get_supplier(db, supplier_id)
    return SupplierResponse.model_validate(supplier)


@admin_router.patch(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Update a supplier (admin)",
    dependencies=[_require_write],
)
async def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    supplier = await procurement_service.update_supplier(
        db,
        supplier_id,
        name=body.name,
        code=body.code,
        contact_info=body.contact_info,
        payment_terms_days=body.payment_terms_days,
        is_active=body.is_active,
    )
    await db.commit()
    return SupplierResponse.model_validate(supplier)


@admin_router.post(
    "/suppliers/{supplier_id}/preferred-variant",
    status_code=204,
    summary="Mark this supplier as the preferred source for a variant (admin)",
    dependencies=[_require_write],
)
async def set_preferred_variant(
    supplier_id: uuid.UUID,
    body: SupplierPreferredSetRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    await procurement_service.set_preferred_supplier(
        db,
        variant_id=body.variant_id,
        supplier_id=supplier_id,
        supplier_sku=body.supplier_sku,
        last_unit_price_rial=body.last_unit_price_rial,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


@admin_router.post(
    "/pos",
    response_model=PurchaseOrderResponse,
    status_code=201,
    summary="Create a draft purchase order (admin)",
    dependencies=[_require_write],
)
async def create_purchase_order(
    body: PurchaseOrderCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.create_purchase_order(
        db,
        supplier_id=body.supplier_id,
        lines=_line_inputs(body.lines),
        expected_at=body.expected_at,
        notes=body.notes,
        warehouse_id=body.warehouse_id,
        idempotency_key=None,
        created_by=user_id,
    )
    await db.commit()
    return PurchaseOrderResponse.from_po(po)


@admin_router.get(
    "/pos",
    response_model=PurchaseOrderListResponse,
    summary="List purchase orders (admin)",
    dependencies=[_require_read],
)
async def list_purchase_orders(
    status: PurchaseOrderStatus | None = Query(None),
    supplier_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderListResponse:
    rows, total = await procurement_service.list_purchase_orders(
        db, status=status, supplier_id=supplier_id, page=page, page_size=page_size
    )
    return PurchaseOrderListResponse(
        items=[PurchaseOrderResponse.from_po(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/pos/suggest",
    response_model=SuggestPOResponse,
    summary="Preview low-stock reorder suggestions grouped by supplier (admin)",
    dependencies=[_require_read],
)
async def suggest_purchase_orders(
    db: AsyncSession = Depends(get_db),
) -> SuggestPOResponse:
    groups = await procurement_service.build_po_suggestions(db)
    supplier_ids = [g.supplier_id for g in groups if g.supplier_id is not None]
    names: dict[uuid.UUID, str] = {}
    if supplier_ids:
        rows = await db.execute(select(Supplier).where(Supplier.id.in_(supplier_ids)))
        names = {s.id: s.name for s in rows.scalars().all()}
    return SuggestPOResponse(
        groups=[
            SuggestedPOGroup(
                supplier_id=group.supplier_id,
                supplier_name=names.get(group.supplier_id) if group.supplier_id else None,
                lines=[
                    SuggestedPOLine(
                        variant_id=line.variant_id,
                        warehouse_id=line.warehouse_id,
                        available=line.available,
                        min_quantity=line.min_quantity,
                        suggested_qty=line.suggested_qty,
                        unit_price_rial=line.unit_price_rial,
                    )
                    for line in group.lines
                ],
            )
            for group in groups
        ]
    )


@admin_router.post(
    "/pos/suggest",
    response_model=PurchaseOrderResponse,
    status_code=201,
    summary="Create a draft PO from low-stock suggestions (admin)",
    dependencies=[_require_write],
)
async def create_purchase_order_from_suggestions(
    body: CreateSuggestedPORequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.create_po_from_suggestions(
        db,
        supplier_id=body.supplier_id,
        variant_ids=body.variant_ids,
        notes=body.notes,
        created_by=user_id,
        idempotency_key=body.idempotency_key,
    )
    await db.commit()
    return PurchaseOrderResponse.from_po(po)


@admin_router.get(
    "/pos/{po_id}",
    response_model=PurchaseOrderResponse,
    summary="Purchase-order detail with lines and linked receipts (admin)",
    dependencies=[_require_read],
)
async def get_purchase_order(
    po_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.get_purchase_order(db, po_id)
    links = await procurement_service.list_po_receipts(db, po.id)
    return PurchaseOrderResponse.from_po(po, receipt_ids=[link.receipt_id for link in links])


@admin_router.patch(
    "/pos/{po_id}",
    response_model=PurchaseOrderResponse,
    summary="Edit a draft purchase order (admin)",
    dependencies=[_require_write],
)
async def update_purchase_order(
    po_id: uuid.UUID,
    body: PurchaseOrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.update_purchase_order(
        db,
        po_id,
        expected_at=body.expected_at,
        notes=body.notes,
        warehouse_id=body.warehouse_id,
        lines=_line_inputs(body.lines) if body.lines is not None else None,
    )
    await db.commit()
    return PurchaseOrderResponse.from_po(po)


@admin_router.post(
    "/pos/{po_id}/send",
    response_model=PurchaseOrderResponse,
    summary="Mark a draft PO as sent to the supplier (admin)",
    dependencies=[_require_write],
)
async def send_purchase_order(
    po_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.send_purchase_order(db, po_id)
    await db.commit()
    return PurchaseOrderResponse.from_po(po)


@admin_router.post(
    "/pos/{po_id}/receive",
    response_model=PurchaseOrderResponse,
    summary="Receive quantities against PO lines; posts a linked inventory receipt (admin)",
    dependencies=[_require_write],
)
async def receive_purchase_order(
    po_id: uuid.UUID,
    body: PurchaseOrderReceiveRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po, _receipt_id = await procurement_service.receive_lines(
        db,
        po_id,
        lines=[(line.line_id, line.quantity) for line in body.lines],
        notes=body.notes,
        created_by=user_id,
    )
    await db.commit()
    links = await procurement_service.list_po_receipts(db, po.id)
    return PurchaseOrderResponse.from_po(po, receipt_ids=[link.receipt_id for link in links])


@admin_router.post(
    "/pos/{po_id}/close",
    response_model=PurchaseOrderResponse,
    summary="Close a purchase order (admin)",
    dependencies=[_require_write],
)
async def close_purchase_order(
    po_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.close_purchase_order(db, po_id)
    await db.commit()
    return PurchaseOrderResponse.from_po(po)


@admin_router.post(
    "/pos/{po_id}/cancel",
    response_model=PurchaseOrderResponse,
    summary="Cancel a purchase order with no received quantities (admin)",
    dependencies=[_require_write],
)
async def cancel_purchase_order(
    po_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    po = await procurement_service.cancel_purchase_order(db, po_id)
    await db.commit()
    return PurchaseOrderResponse.from_po(po)
