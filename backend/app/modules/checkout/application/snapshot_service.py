"""Price snapshot application service.

Creates, verifies, and retrieves immutable price snapshots that seal
the exact monetary breakdown of an order at checkout time.

All money is INTEGER Rials — no floats, no Decimal.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.core.exceptions.handlers import NotFoundError
from app.modules.checkout.domain.price_snapshot import OrderPriceSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _canonical_json(data: dict[str, Any]) -> str:
    """Deterministic JSON serialisation for hash stability.

    Keys are sorted, no whitespace, ASCII-safe — the same input always
    produces the same byte string so the SHA-256 is reproducible.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_hash(snapshot_dict: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of the snapshot payload."""
    canonical = _canonical_json(snapshot_dict)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_snapshot_payload(
    *,
    lines: list[dict[str, Any]],
    subtotal_rial: int,
    total_discount_rial: int,
    total_tax_rial: int,
    shipping_rial: int,
    grand_total_rial: int,
    currency: str,
) -> dict[str, Any]:
    """Assemble the hashable payload dict (no DB ids, no timestamps)."""
    return {
        "currency": currency,
        "lines": lines,
        "subtotal_rial": subtotal_rial,
        "total_discount_rial": total_discount_rial,
        "total_tax_rial": total_tax_rial,
        "shipping_rial": shipping_rial,
        "grand_total_rial": grand_total_rial,
    }


# ── Public API ─────────────────────────────────────────────────────────────


async def create_snapshot(
    db: "AsyncSession",
    *,
    order_id: uuid.UUID,
    line_items: list[dict[str, Any]],
    subtotal_rial: int,
    total_discount_rial: int,
    total_tax_rial: int,
    shipping_rial: int,
    grand_total_rial: int,
    currency: str = "IRR",
) -> OrderPriceSnapshot:
    """Build an immutable price snapshot and insert it atomically.

    This must be called inside the same DB transaction as order creation
    so the snapshot is committed or rolled back together with the order.

    Parameters
    ----------
    line_items : list[dict]
        Each dict must contain: variant_id, product_name, quantity,
        unit_price_rial, line_total_rial, discount_amount_rial,
        discount_code (nullable), tax_amount_rial, tax_rate_percent.
    """
    # Normalise line dicts to a stable shape (strip unexpected keys)
    clean_lines: list[dict[str, Any]] = []
    for item in line_items:
        clean_lines.append({
            "variant_id": str(item["variant_id"]),
            "product_name": str(item["product_name"]),
            "quantity": int(item["quantity"]),
            "unit_price_rial": int(item["unit_price_rial"]),
            "line_total_rial": int(item["line_total_rial"]),
            "discount_amount_rial": int(item.get("discount_amount_rial", 0)),
            "discount_code": item.get("discount_code"),
            "tax_amount_rial": int(item.get("tax_amount_rial", 0)),
            "tax_rate_percent": int(item.get("tax_rate_percent", 0)),
        })

    payload = _build_snapshot_payload(
        lines=clean_lines,
        subtotal_rial=int(subtotal_rial),
        total_discount_rial=int(total_discount_rial),
        total_tax_rial=int(total_tax_rial),
        shipping_rial=int(shipping_rial),
        grand_total_rial=int(grand_total_rial),
        currency=currency,
    )
    snapshot_hash = _compute_hash(payload)

    snapshot = OrderPriceSnapshot(
        order_id=order_id,
        currency=currency,
        lines=clean_lines,
        subtotal_rial=int(subtotal_rial),
        total_discount_rial=int(total_discount_rial),
        total_tax_rial=int(total_tax_rial),
        shipping_rial=int(shipping_rial),
        grand_total_rial=int(grand_total_rial),
        snapshot_hash=snapshot_hash,
    )
    db.add(snapshot)
    await db.flush()

    await logger.ainfo(
        "price_snapshot_created",
        order_id=str(order_id),
        grand_total_rial=grand_total_rial,
        hash=snapshot_hash[:12],
    )
    return snapshot


async def verify_snapshot(db: "AsyncSession", order_id: uuid.UUID) -> bool:
    """Load the snapshot for *order_id*, recompute the hash, and return
    ``True`` only if it matches the stored hash (no tampering).
    """
    from sqlalchemy import select

    stmt = select(OrderPriceSnapshot).where(OrderPriceSnapshot.order_id == order_id)
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise NotFoundError(resource="OrderPriceSnapshot", detail="No price snapshot for order")

    payload = _build_snapshot_payload(
        lines=snapshot.lines,
        subtotal_rial=snapshot.subtotal_rial,
        total_discount_rial=snapshot.total_discount_rial,
        total_tax_rial=snapshot.total_tax_rial,
        shipping_rial=snapshot.shipping_rial,
        grand_total_rial=snapshot.grand_total_rial,
        currency=snapshot.currency,
    )
    expected_hash = _compute_hash(payload)
    is_valid = expected_hash == snapshot.snapshot_hash

    if not is_valid:
        await logger.awarning(
            "price_snapshot_tampered",
            order_id=str(order_id),
            expected=expected_hash[:12],
            stored=snapshot.snapshot_hash[:12],
        )
    return is_valid


async def get_snapshot(db: "AsyncSession", order_id: uuid.UUID) -> OrderPriceSnapshot:
    """Return the snapshot for *order_id* or raise NotFoundError."""
    from sqlalchemy import select

    stmt = select(OrderPriceSnapshot).where(OrderPriceSnapshot.order_id == order_id)
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise NotFoundError(resource="OrderPriceSnapshot", detail="No price snapshot for order")
    return snapshot
