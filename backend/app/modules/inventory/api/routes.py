"""Inventory management API routes."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ValidationError
from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.inventory.api.digital_routes import router as digital_router
from app.modules.inventory.api.warehouse_routes import router as warehouse_router
from app.modules.inventory.application import inventory_service
from app.modules.inventory.domain.models import (
    ReceiptStatus,
    StockCountStatus,
    TransactionType,
    TransferStatus,
)
from app.modules.inventory.application import physical_ops_service, scan_service
from app.modules.inventory.schemas.inventory import (
    InventoryAdjustRequest,
    InventoryListResponse,
    InventoryResponse,
    InventoryTransactionResponse,
    LowStockAlert,
    ReorderRuleListResponse,
    ReorderRuleResponse,
    ReorderRuleUpsertRequest,
    TransactionListResponse,
)
from app.modules.inventory.schemas.physical_ops import (
    ReceiptCreateRequest,
    ReceiptListResponse,
    ReceiptResponse,
    StockCountCreateRequest,
    StockCountLinesEntryRequest,
    StockCountListResponse,
    StockCountResponse,
    TransferCreateRequest,
    TransferListResponse,
    TransferResponse,
)

router = APIRouter()

# The module's public router stays at /inventory. Physical operations follow
# the established module-level admin-router convention, mounting at
# /api/v1/admin/inventory/* through main.py.
admin_router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])

# Warehouse catalogue and stock-by-warehouse views (multi-warehouse v1). These
# use the generic inventory:read / inventory:write pair, unlike the
# inventory:counts-gated physical operations below.
admin_router.include_router(warehouse_router)

# Physical operations are deliberately narrower than generic inventory writes:
# warehouse staff can count, receive, and transfer without receiving broad
# manual-adjustment authority.
_require_counts = Depends(RequirePermissions("inventory:counts"))


# ── Physical operations (admin) ────────────────────────────────────────────


@admin_router.post(
    "/counts",
    response_model=StockCountResponse,
    status_code=201,
    summary="Create a frozen stock-count session (admin)",
    dependencies=[_require_counts],
)
async def create_stock_count(
    body: StockCountCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    count = await physical_ops_service.create_stock_count(
        db,
        warehouse_id=body.warehouse_id,
        scope=body.scope,
        scope_filter=body.scope_filter,
        created_by=user_id,
    )
    return StockCountResponse.from_count(count)


@admin_router.get(
    "/counts",
    response_model=StockCountListResponse,
    summary="List stock-count sessions (admin)",
    dependencies=[_require_counts],
)
async def list_stock_counts(
    status: StockCountStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> StockCountListResponse:
    rows, total = await physical_ops_service.list_stock_counts(
        db, status=status, page=page, page_size=page_size
    )
    return StockCountListResponse(
        items=[StockCountResponse.from_count(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/counts/{count_id}",
    response_model=StockCountResponse,
    summary="Get a stock-count session and lines (admin)",
    dependencies=[_require_counts],
)
async def get_stock_count(
    count_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    return StockCountResponse.from_count(await physical_ops_service.get_stock_count(db, count_id))


@admin_router.post(
    "/counts/{count_id}/start",
    response_model=StockCountResponse,
    summary="Start entering a stock count (admin)",
    dependencies=[_require_counts],
)
async def start_stock_count(
    count_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    return StockCountResponse.from_count(await physical_ops_service.start_stock_count(db, count_id))


@admin_router.put(
    "/counts/{count_id}/lines",
    response_model=StockCountResponse,
    summary="Enter physical quantities for stock-count lines (admin)",
    dependencies=[_require_counts],
)
async def enter_stock_count_lines(
    count_id: uuid.UUID,
    body: StockCountLinesEntryRequest,
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    count = await physical_ops_service.enter_stock_count_lines(
        db,
        count_id=count_id,
        lines=[(line.product_variant_id, line.counted_qty, line.note) for line in body.lines],
    )
    return StockCountResponse.from_count(count)


@admin_router.post(
    "/counts/{count_id}/review",
    response_model=StockCountResponse,
    summary="Move a fully entered stock count to review (admin)",
    dependencies=[_require_counts],
)
async def review_stock_count(
    count_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    return StockCountResponse.from_count(await physical_ops_service.review_stock_count(db, count_id))


@admin_router.post(
    "/counts/{count_id}/post",
    response_model=StockCountResponse,
    summary="Post stock-count variances through the inventory ledger (admin)",
    dependencies=[_require_counts],
)
async def post_stock_count(
    count_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    return StockCountResponse.from_count(await physical_ops_service.post_stock_count(db, count_id))


@admin_router.post(
    "/counts/{count_id}/cancel",
    response_model=StockCountResponse,
    summary="Cancel a non-posted stock-count session (admin)",
    dependencies=[_require_counts],
)
async def cancel_stock_count(
    count_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StockCountResponse:
    return StockCountResponse.from_count(await physical_ops_service.cancel_stock_count(db, count_id))


@admin_router.post(
    "/transfers",
    response_model=TransferResponse,
    status_code=201,
    summary="Create an idempotent two-step warehouse transfer (admin)",
    dependencies=[_require_counts],
)
async def create_transfer(
    body: TransferCreateRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=255),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    transfer = await physical_ops_service.create_transfer(
        db,
        from_warehouse_id=body.from_warehouse_id,
        to_warehouse_id=body.to_warehouse_id,
        lines=[(line.product_variant_id, line.quantity) for line in body.lines],
        idempotency_key=idempotency_key,
        notes=body.notes,
        created_by=user_id,
    )
    return TransferResponse.from_transfer(transfer)


@admin_router.get(
    "/transfers",
    response_model=TransferListResponse,
    summary="List warehouse transfers (admin)",
    dependencies=[_require_counts],
)
async def list_transfers(
    status: TransferStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> TransferListResponse:
    rows, total = await physical_ops_service.list_transfers(
        db, status=status, page=page, page_size=page_size
    )
    return TransferListResponse(
        items=[TransferResponse.from_transfer(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/transfers/{transfer_id}",
    response_model=TransferResponse,
    summary="Get a warehouse transfer (admin)",
    dependencies=[_require_counts],
)
async def get_transfer(
    transfer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    return TransferResponse.from_transfer(await physical_ops_service.get_transfer(db, transfer_id))


@admin_router.post(
    "/transfers/{transfer_id}/ship",
    response_model=TransferResponse,
    summary="Ship a transfer and debit its source warehouse (admin)",
    dependencies=[_require_counts],
)
async def ship_transfer(
    transfer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    return TransferResponse.from_transfer(await physical_ops_service.ship_transfer(db, transfer_id))


@admin_router.post(
    "/transfers/{transfer_id}/receive",
    response_model=TransferResponse,
    summary="Receive an in-transit transfer at its destination (admin)",
    dependencies=[_require_counts],
)
async def receive_transfer(
    transfer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    return TransferResponse.from_transfer(await physical_ops_service.receive_transfer(db, transfer_id))


@admin_router.post(
    "/transfers/{transfer_id}/cancel",
    response_model=TransferResponse,
    summary="Cancel a draft warehouse transfer (admin)",
    dependencies=[_require_counts],
)
async def cancel_transfer(
    transfer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    return TransferResponse.from_transfer(await physical_ops_service.cancel_transfer(db, transfer_id))


@admin_router.post(
    "/receipts",
    response_model=ReceiptResponse,
    status_code=201,
    summary="Create a blind-receiving receipt (admin)",
    dependencies=[_require_counts],
)
async def create_receipt(
    body: ReceiptCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReceiptResponse:
    receipt = await physical_ops_service.create_receipt(
        db,
        warehouse_id=body.warehouse_id,
        lines=[(line.product_variant_id, line.quantity) for line in body.lines],
        notes=body.notes,
        created_by=user_id,
    )
    return ReceiptResponse.from_receipt(receipt)


@admin_router.get(
    "/receipts",
    response_model=ReceiptListResponse,
    summary="List blind-receiving receipts (admin)",
    dependencies=[_require_counts],
)
async def list_receipts(
    status: ReceiptStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ReceiptListResponse:
    rows, total = await physical_ops_service.list_receipts(
        db, status=status, page=page, page_size=page_size
    )
    return ReceiptListResponse(
        items=[ReceiptResponse.from_receipt(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/receipts/{receipt_id}",
    response_model=ReceiptResponse,
    summary="Get a blind-receiving receipt (admin)",
    dependencies=[_require_counts],
)
async def get_receipt(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReceiptResponse:
    return ReceiptResponse.from_receipt(await physical_ops_service.get_receipt(db, receipt_id))


@admin_router.post(
    "/receipts/{receipt_id}/receive",
    response_model=ReceiptResponse,
    summary="Post a blind receipt through the inventory ledger (admin)",
    dependencies=[_require_counts],
)
async def receive_receipt(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReceiptResponse:
    return ReceiptResponse.from_receipt(await physical_ops_service.receive_receipt(db, receipt_id))


@admin_router.post(
    "/receipts/{receipt_id}/cancel",
    response_model=ReceiptResponse,
    summary="Cancel a draft blind-receiving receipt (admin)",
    dependencies=[_require_counts],
)
async def cancel_receipt(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReceiptResponse:
    return ReceiptResponse.from_receipt(await physical_ops_service.cancel_receipt(db, receipt_id))


# ── Admin list ─────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=InventoryListResponse,
    summary="List all inventory items (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    low_stock_only: bool = Query(False),
    track_inventory: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> InventoryListResponse:
    items, total = await inventory_service.get_inventory_list(
        db,
        page=page,
        page_size=page_size,
        low_stock_only=low_stock_only,
        track_inventory=track_inventory,
    )
    return InventoryListResponse(
        items=[InventoryResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Low-stock (must be before /{variant_id} to avoid path collision) ──────


@router.get(
    "/low-stock",
    response_model=list[LowStockAlert],
    summary="List low-stock items (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def get_low_stock(
    threshold: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[LowStockAlert]:
    items, _ = await inventory_service.get_low_stock_items(
        db,
        threshold=threshold,
        page=page,
        page_size=page_size,
    )
    return [LowStockAlert.model_validate(i) for i in items]


# ── Single variant ─────────────────────────────────────────────────────────


@router.get(
    "/{variant_id}",
    response_model=InventoryResponse,
    summary="Get inventory for a variant",
)
async def get_variant_inventory(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InventoryResponse:
    item = await inventory_service.get_inventory(db, variant_id)
    return InventoryResponse.model_validate(item)


# ── Stock adjustment (admin) ──────────────────────────────────────────────


@router.post(
    "/{variant_id}/adjust",
    response_model=InventoryResponse,
    summary="Adjust stock for a variant (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def adjust_stock(
    variant_id: uuid.UUID,
    body: InventoryAdjustRequest,
    db: AsyncSession = Depends(get_db),
) -> InventoryResponse:
    item = await inventory_service.adjust_stock(
        db,
        variant_id=variant_id,
        quantity=body.quantity,
        tx_type=body.type,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        notes=body.notes,
    )
    return InventoryResponse.model_validate(item)


# ── Transaction history (admin) ───────────────────────────────────────────


@router.get(
    "/{variant_id}/transactions",
    response_model=TransactionListResponse,
    summary="Get transaction history for a variant (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def get_transactions(
    variant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: TransactionType | None = Query(None),  # noqa: A002  # API parameter name is the public contract
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    txns, total = await inventory_service.get_transactions(
        db,
        variant_id=variant_id,
        page=page,
        page_size=page_size,
        tx_type=type,
    )
    return TransactionListResponse(
        items=[InventoryTransactionResponse.model_validate(t) for t in txns],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Reorder rules (Odoo stock.warehouse.orderpoint concept, clean-room) ─────


@router.get(
    "/reorder-rules",
    response_model=ReorderRuleListResponse,
    summary="List reorder rules (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def list_reorder_rules(
    db: AsyncSession = Depends(get_db),
) -> ReorderRuleListResponse:
    """Every replenishment rule, newest first."""
    from app.modules.inventory.application import reorder_service

    rules = await reorder_service.list_rules(db)
    return ReorderRuleListResponse(
        items=[ReorderRuleResponse.model_validate(r) for r in rules],
        total=len(rules),
    )


@router.put(
    "/reorder-rules",
    response_model=ReorderRuleResponse,
    summary="Create or update a reorder rule (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def upsert_reorder_rule(
    body: ReorderRuleUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> ReorderRuleResponse:
    """One rule per (variant, warehouse); re-applying the same values is a no-op."""
    from app.modules.inventory.application import reorder_service

    rule = await reorder_service.upsert_rule(
        db,
        variant_id=body.variant_id,
        warehouse_id=body.warehouse_id,
        min_quantity=body.min_quantity,
        reorder_to=body.reorder_to,
        is_active=body.is_active,
    )
    return ReorderRuleResponse.model_validate(rule)


# ── Digital inventory sub-router (Karta Phase 1/2) ─────────────────────────
router.include_router(digital_router)


# ── Barcode scanning (ERP feature #26) ─────────────────────────────────────
#
# Resolve-only: a scan session produces the line list a receiving/picking
# screen submits. The stock write stays with the physical-ops service.


class ScanRequest(BaseModel):
    """One scan batch: the raw codes a scanner emitted."""

    codes: list[str] = Field(..., min_length=1, max_length=200)
    warehouse_id: uuid.UUID | None = None


@admin_router.post(
    "/scan/resolve",
    summary="Resolve scanned barcodes to variants (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def resolve_scans(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Resolve a batch of scanned codes.

    Repeats collapse into quantities, unknown codes are reported individually
    rather than failing the batch, and the live stock position is per the
    warehouse the scanner is standing in. Requires ``inventory:read``.
    """
    return await scan_service.resolve_scan_batch(
        db, body.codes, warehouse_id=body.warehouse_id
    )


@admin_router.get(
    "/scan/{code}",
    summary="Resolve a single barcode (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def resolve_single_scan(
    code: str,
    db: AsyncSession = Depends(get_db),
    warehouse_id: uuid.UUID | None = Query(None),
) -> dict[str, Any]:
    """Resolve one code — the lookup a scan-to-pick screen makes per beep."""
    scan = await scan_service.resolve_barcode(
        db, code, warehouse_id=warehouse_id
    )
    return scan.to_dict()


@admin_router.post(
    "/scan/receive",
    summary="Create a receipt from scanned codes (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def receive_scanned(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Turn a scan session into a draft receipt.

    Refuses when *no* code resolved — an empty receipt is not a useful
    outcome, and silently creating one would hide that every scan failed.
    Individual unknowns are surfaced to the caller for a second attempt.
    """
    batch = await scan_service.resolve_scan_batch(
        db, body.codes, warehouse_id=body.warehouse_id
    )
    if batch["resolved_count"] == 0:
        raise ValidationError(
            "هیچ بارکدی شناسایی نشد؛ رسیدی ایجاد نشد",
            error_code="NO_RESOLVED_SCANS",
        )

    resolved = [
        scan_service.ResolvedScan(
            code=row["code"],
            quantity=row["quantity"],
            variant_id=uuid.UUID(row["variant_id"]),
            sku=row["sku"],
            product_name=row["product_name"],
            price_rial=row["price_rial"],
        )
        for row in batch["resolved"]
    ]
    receipt = await physical_ops_service.create_receipt(
        db,
        warehouse_id=body.warehouse_id,
        lines=scan_service.build_receipt_lines(resolved),
        notes="دریافت با اسکن بارکد",
        created_by=actor_id,
    )
    await db.commit()
    return {
        "receipt_id": str(receipt.id),
        "line_count": len(resolved),
        "unresolved": batch["unresolved"],
    }
