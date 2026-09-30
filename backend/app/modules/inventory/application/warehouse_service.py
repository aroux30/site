"""Warehouse catalogue service: CRUD, the single-default invariant, and
stock-by-warehouse aggregation.

This module is deliberately additive. The inventory ledger keeps writing
``warehouse_id`` values exactly as before (including ``DEFAULT_WAREHOUSE_ID``
for every pre-multi-warehouse call site); nothing in the ledger path consults
this table. What lives here is the *catalogue* those ids always implied:

- CRUD over the ``warehouses`` table
- the single-default rule (promoting a warehouse demotes the previous one)
- deactivation guards that refuse to orphan stock
- read-only aggregation of ``inventory_items`` per warehouse for the admin UI

Default-warehouse semantics (documented on ``set_default``) are flag-only:
**changing the default never moves stock.** It selects which location the UI
pre-selects and which warehouse future "no warehouse specified" flows should
resolve to — it is not a data migration and must never be implemented as one.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE_ID,
    InventoryItem,
    Receipt,
    StockCount,
    Warehouse,
    WarehouseTransfer,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Quantities the aggregation selects. Named once so the summary and the
# per-variant rows can never drift apart.
_STOCK_BUCKETS = ("available", "reserved", "committed", "damaged", "incoming")

# Distinguishes "field omitted" from an explicit ``None`` in partial updates.
UNSET: Any = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_text(value: str | None, *, field: str, required: bool = False) -> str | None:
    cleaned = value.strip() if isinstance(value, str) else None
    if required and not cleaned:
        raise ValidationError(f"{field} الزامی است")
    return cleaned


async def _stock_buckets_by_warehouse(
    db: AsyncSession, warehouse_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, dict[str, int]]:
    """Aggregate ``inventory_items`` into integer buckets per warehouse.

    One grouped query for the whole screen. An empty group-by result means "no
    stock rows", which callers render as zeros rather than as missing data.
    """
    stmt = select(
        InventoryItem.warehouse_id,
        func.coalesce(func.sum(InventoryItem.available), 0).label("available"),
        func.coalesce(func.sum(InventoryItem.reserved), 0).label("reserved"),
        func.coalesce(func.sum(InventoryItem.committed), 0).label("committed"),
        func.coalesce(func.sum(InventoryItem.damaged), 0).label("damaged"),
        func.coalesce(func.sum(InventoryItem.incoming), 0).label("incoming"),
        func.count(InventoryItem.id).label("variant_count"),
    ).group_by(InventoryItem.warehouse_id)
    if warehouse_ids is not None:
        stmt = stmt.where(InventoryItem.warehouse_id.in_(warehouse_ids))

    rows = (await db.execute(stmt)).all()
    buckets: dict[uuid.UUID, dict[str, int]] = {}
    for row in rows:
        buckets[uuid.UUID(str(row.warehouse_id))] = {
            "available": int(row.available or 0),
            "reserved": int(row.reserved or 0),
            "committed": int(row.committed or 0),
            "damaged": int(row.damaged or 0),
            "incoming": int(row.incoming or 0),
            "variant_count": int(row.variant_count or 0),
        }
    return buckets


def _zero_buckets() -> dict[str, int]:
    return dict.fromkeys((*_STOCK_BUCKETS, "variant_count"), 0)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_warehouses(
    db: AsyncSession,
    *,
    is_active: bool | None = None,
    include_stock: bool = True,
) -> list[tuple[Warehouse, dict[str, int]]]:
    """Every catalogue row, defaults first, then newest first."""
    stmt = select(Warehouse).order_by(
        Warehouse.is_default.desc(), Warehouse.created_at.desc()
    )
    if is_active is not None:
        stmt = stmt.where(Warehouse.is_active == is_active)
    warehouses = list((await db.execute(stmt)).scalars().all())

    buckets = (
        await _stock_buckets_by_warehouse(db, [w.id for w in warehouses] or [])
        if include_stock
        else {}
    )
    return [(warehouse, buckets.get(warehouse.id, _zero_buckets())) for warehouse in warehouses]


async def get_warehouse(db: AsyncSession, warehouse_id: uuid.UUID) -> Warehouse:
    warehouse = (
        await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
    ).scalar_one_or_none()
    if warehouse is None:
        raise NotFoundError(resource="Warehouse", detail=f"انبار {warehouse_id} یافت نشد")
    return warehouse


async def get_default_warehouse(db: AsyncSession) -> Warehouse | None:
    """The row flagged default, if any.

    Callers must treat ``None`` as "no catalogue row yet" and fall back to
    :data:`DEFAULT_WAREHOUSE_ID` — that sentinel is what the ledger actually
    uses and stays valid regardless of this table's contents.
    """
    return (
        await db.execute(select(Warehouse).where(Warehouse.is_default.is_(True)))
    ).scalar_one_or_none()


async def _get_by_code(db: AsyncSession, code: str) -> Warehouse | None:
    return (
        await db.execute(select(Warehouse).where(Warehouse.code == code))
    ).scalar_one_or_none()


async def _demote_current_default(
    db: AsyncSession, *, keep_id: uuid.UUID | None = None
) -> Warehouse | None:
    """Clear ``is_default`` on the current default; returns what was demoted."""
    current = await get_default_warehouse(db)
    if current is None or (keep_id is not None and current.id == keep_id):
        return None
    current.is_default = False
    return current


async def create_warehouse(
    db: AsyncSession,
    *,
    name: str,
    code: str,
    address: str | None = None,
    is_default: bool = False,
) -> Warehouse:
    name_clean = _clean_text(name, field="نام انبار", required=True)
    code_clean = _clean_text(code, field="کد انبار", required=True)
    assert name_clean is not None and code_clean is not None  # required=True above

    if await _get_by_code(db, code_clean) is not None:
        raise ConflictError(f"انباری با کد {code_clean} از قبل وجود دارد")

    if is_default:
        await _demote_current_default(db)

    warehouse = Warehouse(
        name=name_clean,
        code=code_clean,
        address=_clean_text(address, field="نشانی"),
        is_default=is_default,
        is_active=True,
    )
    db.add(warehouse)
    await db.flush()
    await logger.ainfo(
        "warehouse_created", warehouse_id=str(warehouse.id), code=code_clean, is_default=is_default
    )
    return warehouse


async def update_warehouse(
    db: AsyncSession,
    warehouse_id: uuid.UUID,
    *,
    name: str | None = None,
    code: str | None = None,
    address: Any = UNSET,
    is_default: bool | None = None,
) -> Warehouse:
    """Edit a warehouse. Promoting one demotes the previous default.

    ``address`` uses a sentinel so that "omit the field" (leave the address
    alone) is distinguishable from "send null" (clear it).

    Sending ``is_default=False`` for the current default is refused: the
    catalogue must always name exactly one default. Promote another warehouse
    instead.
    """
    warehouse = await get_warehouse(db, warehouse_id)

    if name is not None:
        name_clean = _clean_text(name, field="نام انبار", required=True)
        assert name_clean is not None
        warehouse.name = name_clean

    if code is not None:
        code_clean = _clean_text(code, field="کد انبار", required=True)
        assert code_clean is not None
        if code_clean != warehouse.code and await _get_by_code(db, code_clean) is not None:
            raise ConflictError(f"انباری با کد {code_clean} از قبل وجود دارد")
        warehouse.code = code_clean

    if address is not UNSET:
        warehouse.address = _clean_text(address, field="نشانی")

    if is_default is not None:
        if is_default:
            await _demote_current_default(db, keep_id=warehouse.id)
            warehouse.is_default = True
        elif warehouse.is_default:
            raise ConflictError(
                "انبار پیش‌فرض را نمی‌توان بدون تعیین پیش‌فرض جدید لغو کرد؛ "
                "ابتدا انبار دیگری را پیش‌فرض کنید"
            )

    await db.flush()
    await logger.ainfo("warehouse_updated", warehouse_id=str(warehouse.id))
    return warehouse


async def get_stock_summary(
    db: AsyncSession, warehouse_id: uuid.UUID
) -> dict[str, int]:
    buckets = await _stock_buckets_by_warehouse(db, [warehouse_id])
    return buckets.get(warehouse_id, _zero_buckets())


async def count_ledger_references(db: AsyncSession, warehouse_id: uuid.UUID) -> dict[str, int]:
    """Workflow rows that reference a warehouse and must not be orphaned.

    ``inventory_items`` balances are checked separately by
    :func:`get_stock_summary`, but a warehouse can also be referenced by
    physical-operation *history* after its stock has been moved out. Both must
    be clear before deactivation, so a warehouse that was ever counted,
    received into, or transferred through stays visible in the UI.
    """
    references: dict[str, int] = {}

    references["stock_counts"] = int(
        (
            await db.execute(
                select(func.count(StockCount.id)).where(StockCount.warehouse_id == warehouse_id)
            )
        ).scalar_one()
        or 0
    )
    references["receipts"] = int(
        (
            await db.execute(
                select(func.count(Receipt.id)).where(Receipt.warehouse_id == warehouse_id)
            )
        ).scalar_one()
        or 0
    )
    references["transfers"] = int(
        (
            await db.execute(
                select(func.count(WarehouseTransfer.id)).where(
                    (WarehouseTransfer.from_warehouse_id == warehouse_id)
                    | (WarehouseTransfer.to_warehouse_id == warehouse_id)
                )
            )
        ).scalar_one()
        or 0
    )
    return references


async def deactivate_warehouse(db: AsyncSession, warehouse_id: uuid.UUID) -> Warehouse:
    """Deactivate a warehouse. Stock and history are never deleted.

    Refuses in two cases, both with a Persian explanation:
    - the warehouse is the default (promote another one first)
    - the warehouse still holds stock or physical-operation records

    Warehouses are never hard-deleted: the ledger references them by id, so
    deleting one would corrupt history rather than remove stock.
    """
    warehouse = await get_warehouse(db, warehouse_id)

    if warehouse.is_default:
        raise ConflictError(
            "انبار پیش‌فرض قابل غیرفعال‌سازی نیست؛ ابتدا انبار دیگری را پیش‌فرض کنید"
        )

    if not warehouse.is_active:
        return warehouse  # idempotent

    summary = await get_stock_summary(db, warehouse_id)
    if any(summary[bucket] for bucket in _STOCK_BUCKETS):
        raise ConflictError(
            "انبار دارای موجودی است و قابل غیرفعال‌سازی نیست؛ "
            "ابتدا موجودی آن را به انبار دیگری منتقل یا تعدیل کنید"
        )

    references = await count_ledger_references(db, warehouse_id)
    if any(references.values()):
        raise ConflictError(
            "انبار دارای سابقه عملیات انبارداری (شمارش، انتقال یا رسید) است و "
            "قابل غیرفعال‌سازی نیست"
        )

    warehouse.is_active = False
    await db.flush()
    await logger.ainfo("warehouse_deactivated", warehouse_id=str(warehouse.id))
    return warehouse


async def reactivate_warehouse(db: AsyncSession, warehouse_id: uuid.UUID) -> Warehouse:
    """Return a warehouse to service (idempotent)."""
    warehouse = await get_warehouse(db, warehouse_id)
    if warehouse.is_active:
        return warehouse
    warehouse.is_active = True
    await db.flush()
    await logger.ainfo("warehouse_reactivated", warehouse_id=str(warehouse.id))
    return warehouse


# ---------------------------------------------------------------------------
# Stock views
# ---------------------------------------------------------------------------


async def list_stock_by_warehouse(db: AsyncSession) -> list[dict[str, Any]]:
    """Stock aggregated per warehouse across every SKU.

    Includes warehouses that hold stock without a catalogue row, so the screen
    total always reconciles to the ledger. See ``WarehouseStockRow``.
    """
    warehouses = list((await db.execute(select(Warehouse))).scalars().all())
    buckets = await _stock_buckets_by_warehouse(db)
    by_id = {warehouse.id: warehouse for warehouse in warehouses}

    rows: list[dict[str, Any]] = []
    for warehouse in warehouses:
        rows.append(
            {
                "warehouse_id": warehouse.id,
                "name": warehouse.name,
                "code": warehouse.code,
                "is_default": bool(warehouse.is_default),
                "is_active": bool(warehouse.is_active),
                "is_registered": True,
                "stock": buckets.get(warehouse.id, _zero_buckets()),
            }
        )

    for warehouse_id, stock in buckets.items():
        if warehouse_id in by_id:
            continue
        rows.append(
            {
                "warehouse_id": warehouse_id,
                "name": f"انبار ثبت‌نشده {str(warehouse_id)[:8]}",
                "code": str(warehouse_id),
                "is_default": warehouse_id == DEFAULT_WAREHOUSE_ID,
                "is_active": False,
                "is_registered": False,
                "stock": stock,
            }
        )

    # Default first, then registered before unregistered, then by code.
    rows.sort(key=lambda row: (not row["is_default"], not row["is_registered"], row["code"]))
    return rows


async def get_stock_by_variant(db: AsyncSession, variant_id: uuid.UUID) -> list[dict[str, Any]]:
    """One variant's stock across every warehouse (transfer-screen support).

    Warehouses that hold no row for the variant are omitted — an absent row
    means "not stocked here", which is what a transfer form needs to know. A
    variant with no rows anywhere returns an empty list, not an error.
    """
    stmt = select(InventoryItem).where(InventoryItem.variant_id == variant_id)
    items = list((await db.execute(stmt)).scalars().all())

    warehouses = {
        warehouse.id: warehouse
        for warehouse in (await db.execute(select(Warehouse))).scalars().all()
    }

    rows: list[dict[str, Any]] = []
    for item in items:
        warehouse = warehouses.get(item.warehouse_id)
        placeholder = f"انبار ثبت‌نشده {str(item.warehouse_id)[:8]}"
        rows.append(
            {
                "warehouse_id": item.warehouse_id,
                "name": warehouse.name if warehouse else placeholder,
                "code": warehouse.code if warehouse else str(item.warehouse_id),
                "is_active": bool(warehouse.is_active) if warehouse else False,
                "is_registered": warehouse is not None,
                "available": int(item.available),
                "reserved": int(item.reserved),
                "committed": int(item.committed),
                "damaged": int(item.damaged),
                "incoming": int(item.incoming),
                "low_stock_threshold": int(item.low_stock_threshold),
            }
        )
    rows.sort(key=lambda row: (not row["is_registered"], row["code"]))
    return rows


async def ensure_default_warehouse(db: AsyncSession) -> Warehouse | None:
    """Register the sentinel warehouse on first use (bootstrap helper).

    Pre-existing installs have stock under :data:`DEFAULT_WAREHOUSE_ID` but no
    catalogue row, which makes the admin list look empty while the ledger is
    not. Calling this once at seed time creates a matching row only when one
    is genuinely absent; it never rewrites existing data.
    """
    existing = await get_warehouse_or_none(db, DEFAULT_WAREHOUSE_ID)
    if existing is not None:
        return existing
    current_default = await get_default_warehouse(db)
    warehouse = Warehouse(
        id=DEFAULT_WAREHOUSE_ID,
        name="انبار مرکزی",
        code="CENTRAL",
        address=None,
        is_default=current_default is None,
        is_active=True,
    )
    db.add(warehouse)
    await db.flush()
    await logger.ainfo("warehouse_default_registered", warehouse_id=str(warehouse.id))
    return warehouse


async def get_warehouse_or_none(
    db: AsyncSession, warehouse_id: uuid.UUID
) -> Warehouse | None:
    return (
        await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
    ).scalar_one_or_none()
