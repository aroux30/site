"""Procurement domain models: suppliers and purchase orders (v1).

ERP benchmark gap analysis (docs/erp-benchmark/gap-analysis.md, feature #21
Purchase orders, P1). Reference: ERPNext PO cycle
(draft -> sent -> received -> closed).

Design decision — dedicated ``Supplier`` instead of reusing ``Vendor``:
the ``vendors`` table models *marketplace sellers* (mandatory ``user_id``
FK, storefront ``slug``, commission rate, settlement rows). Coupling
purchasing to it would force every supplier to hold a user account and a
storefront, and would mix two populations with different lifecycles. A
separate ``suppliers`` table keeps the marketplace flow untouched
(additive-only rule) and lets procurement evolve its own fields
(payment terms, contact info JSONB, preferred-supplier links).

Money convention: integer **Rial** (BigInteger), never float. Quantities
are integers. Tax is carried per line as basis points (900 = 9%) and the
tax amount is computed with floor-division at total-recalculation time.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class PurchaseOrderStatus(str, enum.Enum):
    """Purchase-order lifecycle (ERPNext-style, rebuilt clean-room)."""

    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


# Terminal statuses: no further transitions or mutations.
TERMINAL_PO_STATUSES: frozenset[PurchaseOrderStatus] = frozenset(
    {PurchaseOrderStatus.CLOSED, PurchaseOrderStatus.CANCELLED}
)

# Receiving is allowed from these statuses.
RECEIVABLE_PO_STATUSES: frozenset[PurchaseOrderStatus] = frozenset(
    {
        PurchaseOrderStatus.SENT,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
    }
)


class Supplier(BaseModel):
    """A purchasing counterparty (distinct from marketplace ``vendors``)."""

    __tablename__ = "suppliers"
    __table_args__ = (
        Index("ix_suppliers_is_active", "is_active"),
        Index("ix_suppliers_name", "name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    contact_info: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder", back_populates="supplier", lazy="select"
    )
    product_links: Mapped[list["SupplierProduct"]] = relationship(
        "SupplierProduct",
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("contact_info", {})
        kw.setdefault("payment_terms_days", 0)
        kw.setdefault("is_active", True)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, code={self.code}, name={self.name})>"


class SupplierProduct(BaseModel):
    """Preferred-supplier link for one product variant.

    At most one preferred supplier per variant (``is_preferred`` unique
    partial rule is enforced in the service for v1; the pair itself is
    unique). Carries the supplier's own SKU and the last negotiated unit
    price in integer Rial so a suggested PO can be priced without a
    manual lookup.
    """

    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "variant_id", name="uq_supplier_products_pair"),
        Index("ix_supplier_products_variant_id", "variant_id"),
        CheckConstraint("last_unit_price_rial >= 0", name="ck_supplier_products_price_nonneg"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_unit_price_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="product_links")

    def __repr__(self) -> str:
        return (
            f"<SupplierProduct(supplier_id={self.supplier_id}, "
            f"variant_id={self.variant_id}, preferred={self.is_preferred})>"
        )


class PurchaseOrder(BaseModel):
    """Purchase-order header with integer-Rial totals."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("number", name="uq_purchase_orders_number"),
        Index("ix_purchase_orders_supplier_id", "supplier_id"),
        Index("ix_purchase_orders_status", "status"),
        Index("ix_purchase_orders_created_at", "created_at"),
        Index("ix_purchase_orders_idempotency_key", "idempotency_key"),
        CheckConstraint("subtotal_rial >= 0", name="ck_po_subtotal_nonneg"),
        CheckConstraint("tax_rial >= 0", name="ck_po_tax_nonneg"),
        CheckConstraint("total_rial >= 0", name="ck_po_total_nonneg"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Sequential per supplier per Jalali year (PO-1404-0001). Allocated at
    # creation time via ``purchase_order_sequences`` (row lock, gapless).
    number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, name="purchase_order_status_enum", native_enum=False),
        default=PurchaseOrderStatus.DRAFT,
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    expected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Integer Rial totals, recomputed from the lines on every mutation.
    subtotal_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tax_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    supplier: Mapped["Supplier"] = relationship(
        "Supplier", back_populates="purchase_orders", lazy="joined"
    )
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine",
        back_populates="purchase_order",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.position",
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("status", PurchaseOrderStatus.DRAFT)
        kw.setdefault("subtotal_rial", 0)
        kw.setdefault("tax_rial", 0)
        kw.setdefault("total_rial", 0)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<PurchaseOrder(id={self.id}, number={self.number}, status={self.status})>"


class PurchaseOrderLine(BaseModel):
    """One ordered SKU: quantity, progressive receipt count, integer pricing."""

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        Index("ix_purchase_order_lines_po_id", "purchase_order_id"),
        Index("ix_purchase_order_lines_variant_id", "product_variant_id"),
        CheckConstraint("qty_ordered > 0", name="ck_po_lines_qty_ordered_positive"),
        CheckConstraint("qty_received >= 0", name="ck_po_lines_qty_received_nonneg"),
        CheckConstraint(
            "qty_received <= qty_ordered", name="ck_po_lines_received_within_ordered"
        ),
        CheckConstraint("unit_price_rial >= 0", name="ck_po_lines_unit_price_nonneg"),
        CheckConstraint(
            "tax_basis_points >= 0 AND tax_basis_points <= 10000",
            name="ck_po_lines_tax_bps_range",
        ),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    qty_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_basis_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Optional note (e.g. supplier SKU reference for the warehouse).
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="lines"
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("qty_received", 0)
        kw.setdefault("tax_basis_points", 0)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderLine(id={self.id}, variant_id={self.product_variant_id}, "
            f"qty={self.qty_received}/{self.qty_ordered})>"
        )


class PurchaseOrderSequence(BaseModel):
    """Per (supplier, Jalali year) counter row for gapless PO numbering.

    Same allocation protocol as invoicing: the row is locked
    ``SELECT ... FOR UPDATE`` at creation time, ``last_value`` is
    incremented inside the caller's transaction, and the committed value
    feeds ``PO-<year>-<seq>`` (per supplier the sequence is unique, so the
    full uniqueness key is (supplier, number) — here ``number`` itself is
    unique globally because the year/seq pair is only ever allocated under
    one supplier's locked row, but the displayed number intentionally
    omits the supplier for readability; global uniqueness is enforced by
    the ``uq_purchase_orders_number`` constraint).
    """

    __tablename__ = "purchase_order_sequences"
    __table_args__ = (
        UniqueConstraint("supplier_id", "year", name="uq_po_sequences_supplier_year"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[str] = mapped_column(String(8), nullable=False)
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<PurchaseOrderSequence(supplier={self.supplier_id}:{self.year} last={self.last_value})>"


class PurchaseOrderReceipt(BaseModel):
    """Additive link between a purchase order and an inventory ``Receipt``.

    One link per received inventory receipt; the receipt itself stays a
    blind-receiving document owned by the inventory module. Receiving PO
    lines creates one ``inventory_receipts`` row per receiving call and
    records the link here (reference trail + idempotency support).
    """

    __tablename__ = "purchase_order_receipts"
    __table_args__ = (
        UniqueConstraint("receipt_id", name="uq_po_receipts_receipt"),
        Index("ix_po_receipts_po_id", "purchase_order_id"),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_receipts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderReceipt(po={self.purchase_order_id}, receipt={self.receipt_id})>"
        )
