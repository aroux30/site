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
- **Fiscally relevant orders** (the wider "paid and beyond" set, used by the
  sales-by-period breakdown and vendor earnings) follow
  ``tax_service_v2.REPORTABLE_ORDER_STATUSES`` and
  ``vendor_service.calculate_vendor_earnings`` (everything except canceled
  and refunded).

The VAT report does not re-implement tax math: it delegates to
``tax_service_v2.aggregate_vat_report`` (the checkout tax engine's canonical
aggregation over persisted ``order_tax_observations``).
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
    SettlementStatus,
    Vendor,
    VendorSettlement,
)
from app.modules.checkout.application import tax_service_v2
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
REVENUE_ORDER_STATUSES = (OrderStatus.COMPLETED, OrderStatus.DELIVERED)
REFUNDED_ORDER_STATUSES = (OrderStatus.REFUNDED, OrderStatus.PARTIALLY_REFUNDED)

SalesGroupBy = Literal["day", "week", "month", "category", "vendor", "channel"]
SALES_GROUP_BYS = ("day", "week", "month", "category", "vendor", "channel")
StockGroupBy = Literal["warehouse", "category", "variant"]
STOCK_GROUP_BYS = ("warehouse", "category", "variant")
SettlementGroupBy = Literal["vendor", "status"]
SETTLEMENT_GROUP_BYS = ("vendor", "status")
TaxGroupBy = Literal["period", "rule", "category"]
TAX_GROUP_BYS = ("period", "rule", "category")


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
    vendor_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> ReportResult:
    """Sales report: volume, gross, discounts, refunds, tax, net revenue.

    ``group_by=day|week|month`` buckets orders by Tehran-local period over
    the orders table; ``category|vendor|channel`` group over order lines
    joined to products (the item's ``total_price`` is the line revenue).
    Channel currently distinguishes orders that carry an ``idempotency_key``
    (API/storefront idempotent placements) from legacy rows without one —
    there is no dedicated channel column on orders yet.
    """
    _validate_range(date_from, date_to)
    if group_by not in SALES_GROUP_BYS:
        raise ValidationError(
            detail="group_by باید یکی از day، week، month، category، vendor یا channel باشد",
            error_code="INVALID_GROUP_BY",
        )

    start_dt = _day_start_utc(date_from)
    end_dt = _day_end_utc(date_to)
    order_day = cast(Order.created_at, Date)

    def _period_filters() -> list[Any]:
        return [Order.created_at >= start_dt, Order.created_at <= end_dt]

    # Optional line-level filters restrict the order set first.
    filtered_order_ids: set[uuid.UUID] | None = None
    if vendor_id is not None or category_id is not None:
        line_stmt: Any = (
            select(OrderItem.order_id)
            .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
        )
        conditions: list[Any] = []
        if vendor_id is not None:
            conditions.append(
                (ProductVariant.vendor_id == vendor_id) | (Product.vendor_id == vendor_id)
            )
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

    # ── Category / vendor / channel grouping over order lines ─────────
    line_stmt = (
        select(
            OrderItem.order_id,
            OrderItem.quantity,
            OrderItem.total_price,
            Category.name.label("category_name"),
            Vendor.store_name.label("vendor_name"),
            Order.idempotency_key.label("idempotency_key"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .outerjoin(Vendor, ProductVariant.vendor_id == Vendor.id)
        .where(*_period_filters())
        .where(Order.status.in_(REVENUE_ORDER_STATUSES))
    )
    if vendor_id is not None:
        line_stmt = line_stmt.where(
            (ProductVariant.vendor_id == vendor_id) | (Product.vendor_id == vendor_id)
        )
    if category_id is not None:
        line_stmt = line_stmt.where(Product.category_id == category_id)
    line_rows = (await db.execute(line_stmt)).all()

    grouped: dict[str, dict[str, Any]] = {}
    for row in line_rows:
        if group_by == "category":
            key = row.category_name or "بدون دسته‌بندی"
        elif group_by == "vendor":
            key = row.vendor_name or "فروشگاه اصلی"
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
    warehouse_id: uuid.UUID | None = None,
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
            detail="group_by باید یکی از warehouse، category یا variant باشد",
            error_code="INVALID_GROUP_BY",
        )

    now_utc = datetime.now(UTC)

    stmt = (
        select(
            InventoryItem.variant_id,
            InventoryItem.warehouse_id,
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
            (ReorderRule.variant_id == InventoryItem.variant_id)
            & (ReorderRule.warehouse_id == InventoryItem.warehouse_id),
        )
        .where(InventoryItem.track_inventory.is_(True))
    )
    if warehouse_id is not None:
        stmt = stmt.where(InventoryItem.warehouse_id == warehouse_id)
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
            InventoryReservation.warehouse_id,
            func.coalesce(func.sum(InventoryReservation.quantity), 0).label("qty"),
        )
        .join(InventoryItem, InventoryReservation.inventory_item_id == InventoryItem.id)
        .where(
            InventoryReservation.status.in_(
                [ReservationStatus.PENDING, ReservationStatus.CONFIRMED]
            )
        )
        .where(InventoryReservation.expires_at > now_utc)
        .group_by(InventoryItem.variant_id, InventoryReservation.warehouse_id)
    )
    if warehouse_id is not None:
        reserved_stmt = reserved_stmt.where(
            InventoryReservation.warehouse_id == warehouse_id
        )
    active_reserved = {
        (r.variant_id, r.warehouse_id): int(r.qty)
        for r in (await db.execute(reserved_stmt)).all()
    }

    def _warehouse_label(warehouse: uuid.UUID) -> str:
        from app.modules.inventory.domain.models import DEFAULT_WAREHOUSE_ID

        if warehouse == DEFAULT_WAREHOUSE_ID:
            return "انبار پیش‌فرض"
        return str(warehouse)

    flat: list[dict[str, Any]] = []
    for r in rows_in:
        # InventoryItem.available already nets RESERVED rows at the ledger;
        # clamp against live reservations so the report never claims more
        # stock than checkout can sell (read-only observation, no mutation).
        live_reserved = active_reserved.get((r.variant_id, r.warehouse_id), 0)
        on_hand = int(r.available)
        sellable = max(0, on_hand - live_reserved)
        threshold = int(r.low_stock_threshold)
        low = sellable <= threshold
        flat.append(
            {
                "variant_id": r.variant_id,
                "warehouse_id": r.warehouse_id,
                "sku": r.sku,
                "product_name": r.product_name,
                "category_name": r.category_name,
                "on_hand": on_hand,
                "reserved": live_reserved,
                "available": sellable,
                "is_low_stock": "بله" if low else "خیر",
                "reorder_to": int(r.reorder_to) if r.reorder_to is not None else 0,
                "_low": low,
                "_warehouse_label": _warehouse_label(r.warehouse_id),
            }
        )
    if low_stock_only:
        flat = [r for r in flat if r["_low"]]

    rows: list[dict[str, Any]]
    if group_by == "variant":
        rows = [
            {
                "bucket": r["_warehouse_label"],
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
            key: str = (
                item["_warehouse_label"]
                if group_by == "warehouse"
                else item["category_name"]
            )
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


# ── Vendor settlement report ──────────────────────────────────────────────


_SETTLEMENT_COLUMNS = [
    ReportColumn("bucket", "فروشنده", "text"),
    ReportColumn("gross_sales_rial", "فروش ناخالص (ریال)", "money"),
    ReportColumn("commission_rate_bp", "نرخ کمیسیون (bp)", "int"),
    ReportColumn("commission_rial", "کمیسیون پلتفرم (ریال)", "money"),
    ReportColumn("net_payable_rial", "خالص قابل پرداخت (ریال)", "money"),
    ReportColumn("pending_settlement_rial", "تسویه در انتظار (ریال)", "money"),
    ReportColumn("paid_settlement_rial", "تسویه پرداخت‌شده (ریال)", "money"),
]


async def generate_vendor_settlement_report(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    group_by: str = "vendor",
    vendor_id: uuid.UUID | None = None,
) -> ReportResult:
    """Vendor settlement report: commission + pending/payable/paid per vendor.

    Gross sales and commission follow ``vendor_service.calculate_vendor_earnings``
    exactly (lines whose order is not canceled/refunded, rate in basis
    points, integer floor division). Settlement buckets come from
    ``vendor_settlements``: paid = PAID, pending = PENDING + APPROVED (issued
    but not yet paid out), payable = net earnings minus settled amounts.
    """
    _validate_range(date_from, date_to)
    if group_by not in SETTLEMENT_GROUP_BYS:
        raise ValidationError(
            detail="group_by باید vendor یا status باشد",
            error_code="INVALID_GROUP_BY",
        )

    start_dt = _day_start_utc(date_from)
    end_dt = _day_end_utc(date_to)

    vendor_stmt = select(Vendor).where(Vendor.is_active.is_(True))
    if vendor_id is not None:
        vendor_stmt = vendor_stmt.where(Vendor.id == vendor_id)
    vendors = list((await db.execute(vendor_stmt)).scalars().all())

    # Canonical earnings semantics: exclude canceled and refunded orders.
    excluded = [OrderStatus.CANCELED, OrderStatus.REFUNDED]
    line_stmt = (
        select(
            Vendor.id.label("vendor_id"),
            func.coalesce(func.sum(OrderItem.total_price), 0).label("gross"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(
            Vendor,
            (ProductVariant.vendor_id == Vendor.id) | (Product.vendor_id == Vendor.id),
        )
        .where(Vendor.id.is_not(None))
        .where(Order.status.notin_(excluded))
        .where(Order.created_at >= start_dt, Order.created_at <= end_dt)
        .group_by(Vendor.id)
    )
    if vendor_id is not None:
        line_stmt = line_stmt.where(Vendor.id == vendor_id)
    gross_by_vendor = {
        r.vendor_id: int(r.gross) for r in (await db.execute(line_stmt)).all()
    }

    settlement_stmt = select(VendorSettlement).where(
        VendorSettlement.created_at >= start_dt,
        VendorSettlement.created_at <= end_dt,
    )
    if vendor_id is not None:
        settlement_stmt = settlement_stmt.where(VendorSettlement.vendor_id == vendor_id)
    settlements = list((await db.execute(settlement_stmt)).scalars().all())

    paid_by_vendor: dict[uuid.UUID, int] = {}
    pending_by_vendor: dict[uuid.UUID, int] = {}
    for s in settlements:
        if s.status == SettlementStatus.PAID:
            paid_by_vendor[s.vendor_id] = paid_by_vendor.get(s.vendor_id, 0) + int(s.amount)
        elif s.status in (SettlementStatus.PENDING, SettlementStatus.APPROVED):
            pending_by_vendor[s.vendor_id] = (
                pending_by_vendor.get(s.vendor_id, 0) + int(s.amount)
            )

    rows: list[dict[str, Any]] = []
    for vendor in vendors:
        gross = gross_by_vendor.get(vendor.id, 0)
        commission = (gross * int(vendor.commission_rate)) // 10000
        net = gross - commission
        paid = paid_by_vendor.get(vendor.id, 0)
        pending = pending_by_vendor.get(vendor.id, 0)
        payable = max(0, net - paid)
        rows.append(
            {
                "bucket": vendor.store_name,
                "gross_sales_rial": gross,
                "commission_rate_bp": int(vendor.commission_rate),
                "commission_rial": commission,
                "net_payable_rial": payable if group_by == "vendor" else net,
                "pending_settlement_rial": pending,
                "paid_settlement_rial": paid,
            }
        )

    if group_by == "status":
        status_rows: dict[str, dict[str, int]] = {}
        for s in settlements:
            label = {
                SettlementStatus.PENDING: "در انتظار",
                SettlementStatus.APPROVED: "تأییدشده",
                SettlementStatus.PAID: "پرداخت‌شده",
                SettlementStatus.REJECTED: "ردشده",
            }[s.status]
            b = status_rows.setdefault(label, {"count": 0, "amount": 0})
            b["count"] += 1
            b["amount"] += int(s.amount)
        rows = [
            {
                "bucket": key,
                "gross_sales_rial": b["amount"],
                "commission_rate_bp": b["count"],
                "commission_rial": 0,
                "net_payable_rial": 0,
                "pending_settlement_rial": b["amount"] if key in ("در انتظار", "تأییدشده") else 0,
                "paid_settlement_rial": b["amount"] if key == "پرداخت‌شده" else 0,
            }
            for key, b in status_rows.items()
        ]
        notes = [
            "gross_sales_rial در این نما مجموع مبالغ اسناد تسویه است؛ "
            "ستون commission_rate_bp تعداد اسناد را نشان می‌دهد"
        ]
    else:
        rows.sort(key=lambda r: r["gross_sales_rial"], reverse=True)
        notes = []

    totals = {
        "gross_sales_rial": sum(r["gross_sales_rial"] for r in rows),
        "commission_rial": sum(r["commission_rial"] for r in rows),
        "net_payable_rial": sum(r["net_payable_rial"] for r in rows),
        "pending_settlement_rial": sum(r["pending_settlement_rial"] for r in rows),
        "paid_settlement_rial": sum(r["paid_settlement_rial"] for r in rows),
    }
    return ReportResult(
        report_type="vendor_settlement",
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        columns=list(_SETTLEMENT_COLUMNS),
        rows=rows,
        totals=totals,
        notes=notes,
    )


# ── Tax / VAT report (composes the checkout tax engine) ───────────────────


_TAX_COLUMNS = [
    ReportColumn("bucket", "گروه", "text"),
    ReportColumn("order_count", "تعداد سفارش", "int"),
    ReportColumn("taxable_total_rial", "مشمول مالیات (ریال)", "money"),
    ReportColumn("vat_total_rial", "مالیات بر ارزش افزوده (ریال)", "money"),
    ReportColumn("withholding_total_rial", "مالیات تکلیفی (ریال)", "money"),
    ReportColumn("tax_total_rial", "جمع مالیات (ریال)", "money"),
]


async def generate_tax_vat_report(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    group_by: str = "period",
) -> ReportResult:
    """VAT report — composes ``tax_service_v2.aggregate_vat_report``.

    Tax math lives in the checkout tax engine over persisted
    ``order_tax_observations``; this report only re-windows the call and
    shapes rows for the reporting layer (no duplicate tax logic here).
    """
    _validate_range(date_from, date_to)
    if group_by not in TAX_GROUP_BYS:
        raise ValidationError(
            detail="group_by باید یکی از period، rule یا category باشد",
            error_code="INVALID_GROUP_BY",
        )

    raw_rows = await tax_service_v2.aggregate_vat_report(
        db,
        date_from=_day_start_utc(date_from),
        date_to=_day_end_utc(date_to),
        group_by=group_by,
    )
    rows: list[dict[str, Any]] = [
        {
            "bucket": str(r["bucket"]),
            "order_count": int(r["order_count"]),
            "taxable_total_rial": int(r["taxable_total_rial"]),
            "vat_total_rial": int(r["vat_total_rial"]),
            "withholding_total_rial": int(r["withholding_total_rial"]),
            "tax_total_rial": int(r["tax_total_rial"]),
        }
        for r in raw_rows
    ]
    totals = {
        "order_count": sum(r["order_count"] for r in rows),
        "taxable_total_rial": sum(r["taxable_total_rial"] for r in rows),
        "vat_total_rial": sum(r["vat_total_rial"] for r in rows),
        "withholding_total_rial": sum(r["withholding_total_rial"] for r in rows),
        "tax_total_rial": sum(r["tax_total_rial"] for r in rows),
    }
    return ReportResult(
        report_type="tax_vat",
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        columns=list(_TAX_COLUMNS),
        rows=rows,
        totals=totals,
        notes=[
            "محاسبه مالیات توسط موتور مالیاتی checkout از مشاهدات ثبت‌شده سفارش انجام می‌شود"
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
    warehouse_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
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
            vendor_id=vendor_id,
            category_id=category_id,
        )
    if report_type == "stock":
        return await generate_stock_report(
            db,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by or "variant",
            warehouse_id=warehouse_id,
            category_id=category_id,
            low_stock_only=low_stock_only,
        )
    if report_type == "vendor_settlement":
        return await generate_vendor_settlement_report(
            db,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by or "vendor",
            vendor_id=vendor_id,
        )
    if report_type == "tax_vat":
        return await generate_tax_vat_report(
            db,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by or "period",
        )
    raise ValidationError(
        detail="نوع گزارش نامعتبر است؛ مقادیر مجاز: sales، stock، vendor_settlement، tax_vat",
        error_code="INVALID_REPORT_TYPE",
    )
