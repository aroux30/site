"""Immutable price snapshot domain model.

Records the exact pricing breakdown at the moment an order is created.
Once inserted, no field may be updated — the row is a tamper-evident
ledger entry sealed by a SHA-256 hash of its canonical JSON.

All monetary values are INTEGER Rials (IRR).  No floats, no Decimal.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import event

from app.core.database.base import BaseModel


class OrderPriceSnapshot(BaseModel):
    """Immutable, hash-sealed pricing breakdown for a single order.

    Invariant:
        grand_total_rial == subtotal_rial - total_discount_rial + total_tax_rial + shipping_rial

    This model is append-only: once a row is inserted it must never be
    modified.  The ``_block_update`` listener below enforces this at the
    ORM layer so even a programming mistake cannot silently mutate a
    sealed snapshot.
    """

    __tablename__ = "order_price_snapshots"
    __table_args__ = (
        Index("ix_order_price_snapshots_order_id", "order_id", unique=True),
        Index("ix_order_price_snapshots_created_at", "created_at"),
    )

    # ── Foreign key ────────────────────────────────────────────────────
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )

    # ── Currency ───────────────────────────────────────────────────────
    currency: Mapped[str] = mapped_column(
        String(10),
        default="IRR",
        server_default="IRR",
        nullable=False,
    )

    # ── Per-line breakdown (JSON array) ────────────────────────────────
    # Each element:
    #   variant_id        : str (UUID)
    #   product_name      : str
    #   quantity          : int
    #   unit_price_rial   : int
    #   line_total_rial   : int
    #   discount_amount_rial : int
    #   discount_code     : str | null
    #   tax_amount_rial   : int
    #   tax_rate_percent  : int   (basis-point friendly: 10 means 10%)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    # ── Aggregate totals (all integer Rials) ───────────────────────────
    subtotal_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_discount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_tax_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    grand_total_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # ── Tamper-detection hash ──────────────────────────────────────────
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<OrderPriceSnapshot(order_id={self.order_id}, "
            f"grand_total_rial={self.grand_total_rial})>"
        )


# ── Immutability guard ────────────────────────────────────────────────────
# Once a snapshot row is inserted it must never be modified.  This ORM-level
# listener fires before any UPDATE flush and raises unconditionally — even a
# programming mistake cannot silently mutate a sealed snapshot.


@event.listens_for(OrderPriceSnapshot, "before_update")
def _block_update(
    mapper: Any, connection: Any, target: OrderPriceSnapshot
) -> None:  # noqa: ARG001
    from app.core.exceptions.handlers import ValidationError

    raise ValidationError(
        "OrderPriceSnapshot is immutable — updates are forbidden. "
        f"Attempted to modify snapshot for order_id={target.order_id}"
    )
