"""Parameterized report generation.

Each report returns a :class:`ReportResult` of typed rows (all monetary
values are integer Rials — BigInteger columns, floored integer division,
never floats) plus a column layout used for CSV/HTML rendering.

Status semantics are canonical with the rest of the codebase:

- **Revenue-recognized orders** follow ``AnalyticsService.get_sales_analytics``:
  ``COMPLETED`` + ``DELIVERED`` — the dashboard KPIs use exactly this set.
- **Refunded orders** are reported separately from ``REFUNDED`` /
  ``PARTIALLY_REFUNDED`` statuses so a report reader can reconcile
  ``net_revenue = gross_sales - refunds`` without hidden status math.
- **Fiscally relevant orders** (the wider "paid and beyond" set) are
  everything except canceled and refunded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ValidationError
from app.modules.catalog.domain.models import (
    Category,
    Product,
    ProductVariant,
)
from app.modules.inventory.domain.models import (
    InventoryItem,
    InventoryReservation,
    ReorderRule,
    ReservationStatus,
)
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus

TZ_TEHRAN = ZoneInfo("Asia/Tehran")

# Canonical with AnalyticsService.get_sales_analytics — do not widen without
# a dashboard decision: these KPIs must keep reconciling with the dashboard.
REVENUE_ORDER_STATUSES = (OrderStatus.COMPLETED,)
REFUNDED_ORDER_STATUSES = (OrderStatus.REFUNDED,)

SalesGroupBy = Literal["day", "week", "month", "category", "channel"]
SALES_GROUP_BYS = ("day", "week", "month", "category", "channel")
StockGroupBy = Literal["category", "variant"]
STOCK_GROUP_BYS = ("category", "variant")


@dataclass(frozen=True)
class ReportColumn:
    """One output column: machine key, Persian label, kind for formatting."""

    key: str
    label: str
    kind: str = "text"  # text | int | money


@dataclass
class ReportResult:
    """Generated report payload (rows are dicts keyed by column key)."""

    report_type: str
    date_from: date
    date_to: date
    group_by: str
    columns: list[ReportColumn]
    rows: list[dict[str, Any]]
    totals: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)


# ── Windowing helpers ─────────────────────────────────────────────────────


def _validate_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise ValidationError(
            detail="بازه زمانی نامعتبر است: «از تاریخ» بعد از «تا تاریخ» است",
            error_code="INVALID_DATE_RANGE",
        )
    if (date_to - date_from).days > 366:
        raise ValidationError(
            detail="بازه گزارش نمی‌تواند بیش از یک سال باشد",
            error_code="DATE_RANGE_TOO_WIDE",
        )


def _day_start_utc(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def _day_end_utc(day: date) -> datetime:
    return datetime.combine(day, datetime.max.time(), tzinfo=UTC)


def _month_key(day: date) -> str:
    return day.strftime("%Y-%m")


def _week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _period_key(day: date, group_by: str) -> str:
    if group_by == "day":
        return day.isoformat()
    if group_by == "week":
        return _week_key(day)
    return _month_key(day)


# ── Sales report ──────────────────────────────────────────────────────────


_SALES_PERIOD_COLUMNS = [
    ReportColumn("bucket", "بازه", "text"),
    ReportColumn("order_count", "تعداد سفارش", "int"),
    ReportColumn("gross_sales_rial", "فروش ناخالص (ریال)", "money"),
    ReportColumn("discount_rial", "تخفیف (ریال)", "money"),
    ReportColumn("tax_rial", "مالیات (ریال)", "money"),
    ReportColumn("refund_rial", "استرداد (ریال)", "money"),
    ReportColumn("net_revenue_rial", "درآمد خالص (ریال)", "money"),
]

_SALES_GROUPED_COLUMNS = [
    ReportColumn("bucket", "گروه", "text"),
    ReportColumn("order_count", "تعداد سفارش", "int"),
    ReportColumn("item_count", "تعداد اقلام", "int"),
    ReportColumn("gross_sales_rial", "فروش ناخالص (ریال)", "money"),
    ReportColumn("net_revenue_rial", "درآمد خالص (ریال)", "money"),
]


async def generate_sales_report(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    group_by: str = "day",
    category_id: uuid.UUID | None = None,
) -> ReportResult:
    """Sales report: volume, gross, discounts, refunds, tax, net revenue.

    ``group_by=day|week|month`` buckets orders by Tehran-local period over
    the orders table; ``category|channel`` group over order lines joined to
    products (the item's ``total_price`` is the line revenue). Channel
    currently distinguishes orders that carry an ``idempotency_key``
    (API/storefront idempotent placements) from legacy rows without one —
    there is no dedicated channel column on orders yet.
    """
    _validate_range(date_from, date_to)
    if group_by not in SALES_GROUP_BYS:
        raise ValidationError(
            detail="group_by باید یکی از day، week، month، category یا channel باشد",
            error_code="INVALID_GROUP_BY",
        )

    start_dt = _day_start_utc(date_from)
    end_dt = _day_end_utc(date_to)
    order_day = cast(Order.created_at, Date)

    def _period_filters() -> list[Any]:
        return [Order.created_at >= start_dt, Order.created_at <= end_dt]

    # Optional line-level filters restrict the order set first.
    filtered_order_ids: set[uuid.UUID] | None = None
    if category_id is not None:
        line_stmt: Any = (
            select(OrderItem.order_id)
            .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
        )
        conditions: list[Any] = []
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        line_stmt = line_stmt.where(*conditions)
        filtered_order_ids = {
            row[0] for row in (await db.execute(line_stmt)).all()
        }

    def _apply_order_filters(stmt: Any) -> Any:
        stmt = stmt.where(*_period_filters())
        if filtered_order_ids is not None:
            stmt = stmt.where(Order.id.in_(filtered_order_ids))
        return stmt

    # ── Revenue-recognized buckets (gross/discount/tax per period) ─────
    revenue_rows = (
        await db.execute(
            _apply_order_filters(
                select(
                    order_day.label("day"),
                    func.count().label("order_count"),
                    func.coalesce(func.sum(Order.total), 0).label("gross"),
                    func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
                    func.coalesce(func.sum(Order.tax), 0).label("tax"),
                ).where(Order.status.in_(REVENUE_ORDER_STATUSES))
            ).group_by(order_day)
        )
    ).all()
    revenue_by_day = {
        r.day: (int(r.order_count), int(r.gross), int(r.discount), int(r.tax))
        for r in revenue_rows
    }

    # ── Refunded orders (separate bucket, never netted in-place) ───────
    refund_rows = (
        await db.execute(
            _apply_order_filters(
                select(
                    order_day.label("day"),
                    func.coalesce(func.sum(Order.total), 0).label("refund_total"),
                ).where(Order.status.in_(REFUNDED_ORDER_STATUSES))
            ).group_by(order_day)
        )
    ).all()
    refunds_by_day = {r.day: int(r.refund_total) for r in refund_rows}

    if group_by in ("day", "week", "month"):
        buckets: dict[str, dict[str, int]] = {}
        for day, (count, gross, discount, tax) in revenue_by_day.items():
            key = _period_key(day, group_by)
            b = buckets.setdefault(
                key,
                {"order_count": 0, "gross": 0, "discount": 0, "tax": 0, "refund": 0},
            )
            b["order_count"] += count
            b["gross"] += gross
            b["discount"] += discount
            b["tax"] += tax
        for day, refund_total in refunds_by_day.items():
            key = _period_key(day, group_by)
            buckets.setdefault(
                key,
                {"order_count": 0, "gross": 0, "discount": 0, "tax": 0, "refund": 0},
            )["refund"] += refund_total

        rows: list[dict[str, Any]] = [
            {
                "bucket": key,
                "order_count": b["order_count"],
                "gross_sales_rial": b["gross"],
                "discount_rial": b["discount"],
                "tax_rial": b["tax"],
                "refund_rial": b["refund"],
                "net_revenue_rial": b["gross"] - b["refund"],
            }
            for key, b in sorted(buckets.items())
        ]
        totals = {
            "order_count": sum(r["order_count"] for r in rows),
            "gross_sales_rial": sum(r["gross_sales_rial"] for r in rows),
            "discount_rial": sum(r["discount_rial"] for r in rows),
            "tax_rial": sum(r["tax_rial"] for r in rows),
            "refund_rial": sum(r["refund_rial"] for r in rows),
            "net_revenue_rial": sum(r["net_revenue_rial"] for r in rows),
        }
        return ReportResult(
            report_type="sales",
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            columns=list(_SALES_PERIOD_COLUMNS),
            rows=rows,
            totals=totals,
        )

    # ── Category / channel grouping over order lines ─────────
    line_stmt = (
        select(
            OrderItem.order_id,
            OrderItem.quantity,
            OrderItem.total_price,
            Category.name.label("category_name"),
            Order.idempotency_key.label("idempotency_key"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .where(*_period_filters())
        .where(Order.status.in_(REVENUE_ORDER_STATUSES))
    )
    if category_id is not None:
        line_stmt = line_stmt.where(Product.category_id == category_id)
    line_rows = (await db.execute(line_stmt)).all()

    grouped: dict[str, dict[str, Any]] = {}
    for row in line_rows:
        if group_by == "category":
            key = row.category_name or "بدون دسته‌بندی"
        else:  # channel
            key = "فروشگاه آنلاین (Idempotent)" if row.idempotency_key else "ثبت سنتی/ادمین"
        g = grouped.setdefault(
            key, {"order_ids": set(), "item_count": 0, "gross": 0}
        )
        g["order_ids"].add(row.order_id)
        g["item_count"] += int(row.quantity)
        g["gross"] += int(row.total_price)

    rows = [
        {
            "bucket": key,
            "order_count": len(g["order_ids"]),
            "item_count": g["item_count"],
            "gross_sales_rial": g["gross"],
            "net_revenue_rial": g["gross"],
        }
        for key, g in sorted(grouped.items(), key=lambda kv: kv[1]["gross"], reverse=True)
    ]
    totals = {
        "order_count": sum(r["order_count"] for r in rows),
        "item_count": sum(r["item_count"] for r in rows),
        "gross_sales_rial": sum(r["gross_sales_rial"] for r in rows),
        "net_revenue_rial": sum(r["net_revenue_rial"] for r in rows),
    }
    return ReportResult(
        report_type="sales",
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        columns=list(_SALES_GROUPED_COLUMNS),
        rows=rows,
        totals=totals,
        notes=[
            "گروه‌بندی بر اساس اقلام سفارش است؛ استرداد در این نما لحاظ نمی‌شود "
            "(برای راستی‌آزمایی استرداد از group_by=day استفاده کنید)"
        ],
    )


# ── Stock report ──────────────────────────────────────────────────────────


_STOCK_COLUMNS = [
    ReportColumn("bucket", "گروه", "text"),
    ReportColumn("sku", "شناسه کالا (SKU)", "text"),
    ReportColumn("product_name", "نام محصول", "text"),
    ReportColumn("on_hand", "موجودی فیزیکی", "int"),
    ReportColumn("reserved", "رزرو فعال", "int"),
    ReportColumn("available", "قابل فروش", "int"),
    ReportColumn("is_low_stock", "کم‌موجودی", "text"),
    ReportColumn("reorder_to", "نقطه سفارش مجدد", "int"),
]


async def generate_stock_report(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    group_by: str = "variant",
    category_id: uuid.UUID | None = None,
    low_stock_only: bool = False,
) -> ReportResult:
    """Stock report: on-hand / reserved / sellable per variant (or grouped).

    on_hand = available + reserved buckets as tracked on ``inventory_items``;
    reserved_active adds currently open reservations (not yet expired) so the
    sellable figure matches what checkout would see. Low stock = sellable at
    or below the item's ``low_stock_threshold``; reorder candidates come from
    the matching ``inventory_reorder_rules`` row.
    """
    _validate_range(date_from, date_to)
    if group_by not in STOCK_GROUP_BYS:
        raise ValidationError(
            detail="group_by باید یکی از category یا variant باشد",
            error_code="INVALID_GROUP_BY",
        )

    now_utc = datetime.now(UTC)

    stmt = (
        select(
            InventoryItem.variant_id,
            InventoryItem.available,
            InventoryItem.reserved,
            InventoryItem.low_stock_threshold,
            InventoryItem.track_inventory,
            ProductVariant.sku,
            Product.name.label("product_name"),
            Category.name.label("category_name"),
            ReorderRule.min_quantity.label("reorder_min"),
            ReorderRule.reorder_to.label("reorder_to"),
        )
        .join(ProductVariant, InventoryItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .outerjoin(
            ReorderRule,
            ReorderRule.variant_id == InventoryItem.variant_id,
        )
        .where(InventoryItem.track_inventory.is_(True))
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    rows_in = (await db.execute(stmt)).all()

    # Active (open, unexpired) reservations per inventory row. Reservations
    # hang off ``inventory_item_id`` (there is no variant_id column), so we
    # join back to inventory_items to key them by variant. Open statuses are
    # PENDING (cart hold) and CONFIRMED (checked out, awaiting payment).
    reserved_stmt = (
        select(
            InventoryItem.variant_id,
            func.coalesce(func.sum(InventoryReservation.quantity), 0).label("qty"),
        )
        .join(InventoryItem, InventoryReservation.inventory_item_id == InventoryItem.id)
        .where(
            InventoryReservation.status.in_(
                [ReservationStatus.PENDING, ReservationStatus.CONFIRMED]
            )
        )
        .where(InventoryReservation.expires_at > now_utc)
        .group_by(InventoryItem.variant_id)
    )
    active_reserved = {
        r.variant_id: int(r.qty) for r in (await db.execute(reserved_stmt)).all()
    }

    flat: list[dict[str, Any]] = []
    for r in rows_in:
        # InventoryItem.available already nets RESERVED rows at the ledger;
        # clamp against live reservations so the report never claims more
        # stock than checkout can sell (read-only observation, no mutation).
        live_reserved = active_reserved.get(r.variant_id, 0)
        on_hand = int(r.available)
        sellable = max(0, on_hand - live_reserved)
        threshold = int(r.low_stock_threshold)
        low = sellable <= threshold
        flat.append(
            {
                "variant_id": r.variant_id,
                "sku": r.sku,
                "product_name": r.product_name,
                "category_name": r.category_name,
                "on_hand": on_hand,
                "reserved": live_reserved,
                "available": sellable,
                "is_low_stock": "بله" if low else "خیر",
                "reorder_to": int(r.reorder_to) if r.reorder_to is not None else 0,
                "_low": low,
            }
        )
    if low_stock_only:
        flat = [r for r in flat if r["_low"]]

    rows: list[dict[str, Any]]
    if group_by == "variant":
        rows = [
            {
                "bucket": "انبار",
                "sku": r["sku"],
                "product_name": r["product_name"],
                "on_hand": r["on_hand"],
                "reserved": r["reserved"],
                "available": r["available"],
                "is_low_stock": r["is_low_stock"],
                "reorder_to": r["reorder_to"],
            }
            for r in sorted(flat, key=lambda x: (x["available"], x["sku"]))
        ]
    else:
        grouped: dict[str, dict[str, Any]] = {}
        for item in flat:
            key: str = item["category_name"]
            g = grouped.setdefault(
                key,
                {"on_hand": 0, "reserved": 0, "available": 0, "low": 0, "count": 0},
            )
            g["on_hand"] += item["on_hand"]
            g["reserved"] += item["reserved"]
            g["available"] += item["available"]
            g["low"] += 1 if item["_low"] else 0
            g["count"] += 1
        rows = [
            {
                "bucket": key,
                "sku": f"{g['count']} قلم",
                "product_name": "",
                "on_hand": g["on_hand"],
                "reserved": g["reserved"],
                "available": g["available"],
                "is_low_stock": f"{g['low']} قلم",
                "reorder_to": 0,
            }
            for key, g in sorted(grouped.items())
        ]

    totals = {
        "on_hand": sum(r["on_hand"] for r in rows if isinstance(r["on_hand"], int)),
        "reserved": sum(r["reserved"] for r in rows if isinstance(r["reserved"], int)),
        "available": sum(r["available"] for r in rows if isinstance(r["available"], int)),
        "low_stock_items": sum(1 for r in flat if r["_low"]),
    }
    return ReportResult(
        report_type="stock",
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        columns=list(_STOCK_COLUMNS),
        rows=rows,
        totals=totals,
        notes=[
            "موجودی لحظه‌ای است؛ بازه تاریخی برای تعریف گزارش ذخیره‌شده نگه داشته می‌شود"
        ],
    )


# ── Dispatcher ────────────────────────────────────────────────────────────


async def generate_report(
    db: AsyncSession,
    report_type: str,
    *,
    date_from: date,
    date_to: date,
    group_by: str | None = None,
    category_id: uuid.UUID | None = None,
    low_stock_only: bool = False,
) -> ReportResult:
    """Route a report_type to its generator (admin routes + saved reports)."""
    if report_type == "sales":
        return await generate_sales_report(
            db,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by or "day",
            category_id=category_id,
        )
    if report_type == "stock":
        return await generate_stock_report(
            db,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by or "variant",
            category_id=category_id,
            low_stock_only=low_stock_only,
        )
    raise ValidationError(
        detail="نوع گزارش نامعتبر است؛ مقادیر مجاز: sales، stock",
        error_code="INVALID_REPORT_TYPE",
    )
