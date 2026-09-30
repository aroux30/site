"""Inventory management domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


class TransactionType(str, enum.Enum):
    RECEIVED = "received"
    SOLD = "sold"
    RETURNED = "returned"
    ADJUSTED = "adjusted"
    DAMAGED = "damaged"
    RESERVED = "reserved"
    RELEASED = "released"


class StockCountStatus(str, enum.Enum):
    """Lifecycle of a physical cycle-count session."""

    DRAFT = "draft"
    COUNTING = "counting"
    REVIEW = "review"
    POSTED = "posted"
    CANCELLED = "cancelled"


class StockCountScope(str, enum.Enum):
    """The inventory population captured when a count begins."""

    FULL = "full"
    CATEGORY = "category"
    PRODUCT_LIST = "product-list"


class TransferStatus(str, enum.Enum):
    """Two-step warehouse transfer lifecycle."""

    DRAFT = "draft"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class ReceiptStatus(str, enum.Enum):
    """Blind-receiving lifecycle. Purchase-order matching is deliberately v2."""

    DRAFT = "draft"
    RECEIVED = "received"
    CANCELLED = "cancelled"


# Default warehouse for all pre-multi-warehouse rows. Every existing
# inventory item belongs to this warehouse; new warehouses get their own ids.
#
# The id is a fixed sentinel *on purpose*: it is baked into the Python column
# defaults, the pre-multi-warehouse migration's ``server_default`` and the
# reporting "انبار پیش‌فرض" label. Warehouse CRUD never changes what
# ``DEFAULT_WAREHOUSE_ID`` means — it only selects which *row* is flagged
# ``is_default`` for the UI. Changing the flag never moves stock.
DEFAULT_WAREHOUSE_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")


# ---- Models ----


class Warehouse(BaseModel):
    """A physical stocking location.

    Additive to the multi-warehouse data model: every inventory row already
    carries ``warehouse_id``, so this table only *catalogues* locations that
    were previously free-form UUIDs. Nothing here participates in quantity
    math — that remains the inventory ledger's job.
    """

    __tablename__ = "warehouses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_warehouses_code"),
        # At most one default warehouse, enforced by the database rather than
        # by convention. A partial unique index keeps the rule true even for
        # concurrent writers that both try to promote themselves.
        Index(
            "uq_warehouses_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        Index("ix_warehouses_is_active", "is_active"),
        # The metadata naming convention prefixes ``ck_<table>_``, so these
        # short names resolve to the same constraint names the migration
        # creates (``ck_warehouses_name_not_blank``).
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Stable human key used on lists, transfers, and count sheets.
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Warehouse(id={self.id}, code={self.code}, is_default={self.is_default})>"


class InventoryItem(BaseModel):
    """Tracks stock levels for each product variant per warehouse."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index("ix_inventory_items_variant_id", "variant_id"),
        Index("ix_inventory_items_warehouse_id", "warehouse_id"),
        Index(
            "ix_inventory_items_variant_warehouse",
            "variant_id",
            "warehouse_id",
            unique=True,
        ),
        CheckConstraint("available >= 0", name="ck_inventory_available_non_negative"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_non_negative"),
        CheckConstraint("committed >= 0", name="ck_inventory_committed_non_negative"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=DEFAULT_WAREHOUSE_ID,
        nullable=False,
    )
    available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    damaged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incoming: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    backorder_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    reservations: Mapped[list["InventoryReservation"]] = relationship(
        "InventoryReservation", back_populates="inventory_item", lazy="select"
    )
    transactions: Mapped[list["InventoryTransaction"]] = relationship(
        "InventoryTransaction", back_populates="inventory_item", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<InventoryItem(id={self.id}, variant_id={self.variant_id}, available={self.available})>"  # noqa: E501


class ReorderRule(BaseModel):
    """Min/max replenishment rule for one variant in one warehouse (Odoo
    ``stock.warehouse.orderpoint`` concept, rebuilt clean-room).

    When a variant's available stock at a warehouse falls to or below
    ``min_quantity``, the replenishment task drafts a purchase suggestion for
    ``reorder_to`` units. One rule per (variant, warehouse).
    """

    __tablename__ = "inventory_reorder_rules"
    __table_args__ = (
        UniqueConstraint("variant_id", "warehouse_id", name="uq_reorder_variant_warehouse"),
        Index("ix_reorder_rules_variant_id", "variant_id"),
        Index("ix_reorder_rules_warehouse_id", "warehouse_id"),
        CheckConstraint("min_quantity >= 0", name="ck_reorder_min_non_negative"),
        CheckConstraint("reorder_to >= 0", name="ck_reorder_to_non_negative"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=DEFAULT_WAREHOUSE_ID,
        nullable=False,
    )
    # Replenish when available stock reaches this floor.
    min_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Target stock to bring the warehouse back up to.
    reorder_to: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ReorderRule(id={self.id}, variant_id={self.variant_id}, "
            f"min={self.min_quantity}, to={self.reorder_to})>"
        )


class InventoryReservation(BaseModel):
    """Temporary stock reservations for carts and orders."""

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        Index("ix_inventory_reservations_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_reservations_order_id", "order_id"),
        Index("ix_inventory_reservations_cart_id", "cart_id"),
        Index("ix_inventory_reservations_status", "status"),
        Index("ix_inventory_reservations_expires_at", "expires_at"),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    cart_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="SET NULL"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=DEFAULT_WAREHOUSE_ID,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status_enum", native_enum=False),
        default=ReservationStatus.PENDING,
        nullable=False,
    )

    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="reservations"
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryReservation(id={self.id}, quantity={self.quantity}, status={self.status})>"
        )


class StockCount(BaseModel):
    """A frozen warehouse stock snapshot that is reconciled through the ledger.

    The session never changes :class:`InventoryItem` rows itself. On post, the
    application service creates one ``ADJUSTED`` transaction per variance.
    """

    __tablename__ = "stock_counts"
    __table_args__ = (
        Index("ix_stock_counts_warehouse_id", "warehouse_id"),
        Index("ix_stock_counts_status", "status"),
        Index("ix_stock_counts_created_by", "created_by"),
        Index("ix_stock_counts_created_at", "created_at"),
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[StockCountStatus] = mapped_column(
        Enum(StockCountStatus, name="stock_count_status_enum", native_enum=False),
        default=StockCountStatus.DRAFT,
        nullable=False,
    )
    scope: Mapped[StockCountScope] = mapped_column(
        Enum(StockCountScope, name="stock_count_scope_enum", native_enum=False),
        default=StockCountScope.FULL,
        nullable=False,
    )
    # Scope-specific identifiers, e.g. {"category_id": "..."} or
    # {"product_variant_ids": ["..."]}. The server validates its shape.
    scope_filter: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    counted_line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    variance_line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    variance_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    lines: Mapped[list["StockCountLine"]] = relationship(
        "StockCountLine",
        back_populates="count",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<StockCount(id={self.id}, warehouse_id={self.warehouse_id}, status={self.status})>"


class StockCountLine(BaseModel):
    """A count-line snapshot. ``system_qty`` remains immutable after creation."""

    __tablename__ = "stock_count_lines"
    __table_args__ = (
        UniqueConstraint("count_id", "product_variant_id", name="uq_stock_count_lines_count_variant"),
        Index("ix_stock_count_lines_count_id", "count_id"),
        Index("ix_stock_count_lines_product_variant_id", "product_variant_id"),
        CheckConstraint("system_qty >= 0", name="ck_stock_count_system_qty_non_negative"),
        CheckConstraint("counted_qty IS NULL OR counted_qty >= 0", name="ck_stock_count_counted_qty_non_negative"),
    )

    count_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_counts.id", ondelete="CASCADE"), nullable=False
    )
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    system_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    count: Mapped["StockCount"] = relationship("StockCount", back_populates="lines")

    @property
    def variance(self) -> int | None:
        """Physical minus frozen-system quantity; absent until staff count it."""
        return None if self.counted_qty is None else self.counted_qty - self.system_qty

    def __repr__(self) -> str:
        return f"<StockCountLine(count_id={self.count_id}, variant_id={self.product_variant_id})>"


class WarehouseTransfer(BaseModel):
    """A two-step physical inter-warehouse movement header."""

    __tablename__ = "warehouse_transfers"
    __table_args__ = (
        Index("ix_warehouse_transfers_from_warehouse_id", "from_warehouse_id"),
        Index("ix_warehouse_transfers_to_warehouse_id", "to_warehouse_id"),
        Index("ix_warehouse_transfers_status", "status"),
        Index("ix_warehouse_transfers_idempotency_key", "idempotency_key"),
        UniqueConstraint("idempotency_key", name="uq_warehouse_transfers_idempotency_key"),
        CheckConstraint(
            "from_warehouse_id <> to_warehouse_id", name="ck_warehouse_transfer_distinct_warehouses"
        ),
    )

    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus, name="warehouse_transfer_status_enum", native_enum=False),
        default=TransferStatus.DRAFT,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["WarehouseTransferLine"]] = relationship(
        "WarehouseTransferLine",
        back_populates="transfer",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WarehouseTransfer(id={self.id}, status={self.status})>"


class WarehouseTransferLine(BaseModel):
    """An immutable product-quantity instruction for one transfer."""

    __tablename__ = "warehouse_transfer_lines"
    __table_args__ = (
        UniqueConstraint("transfer_id", "product_variant_id", name="uq_transfer_lines_transfer_variant"),
        Index("ix_warehouse_transfer_lines_transfer_id", "transfer_id"),
        CheckConstraint("quantity > 0", name="ck_warehouse_transfer_line_quantity_positive"),
    )

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_transfers.id", ondelete="CASCADE"), nullable=False
    )
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    transfer: Mapped["WarehouseTransfer"] = relationship(
        "WarehouseTransfer", back_populates="lines"
    )


class Receipt(BaseModel):
    """Blind-receiving header, intentionally not yet linked to purchase orders."""

    __tablename__ = "inventory_receipts"
    __table_args__ = (
        Index("ix_inventory_receipts_warehouse_id", "warehouse_id"),
        Index("ix_inventory_receipts_status", "status"),
        Index("ix_inventory_receipts_created_at", "created_at"),
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[ReceiptStatus] = mapped_column(
        Enum(ReceiptStatus, name="inventory_receipt_status_enum", native_enum=False),
        default=ReceiptStatus.DRAFT,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["ReceiptLine"]] = relationship(
        "ReceiptLine", back_populates="receipt", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Receipt(id={self.id}, warehouse_id={self.warehouse_id}, status={self.status})>"


class ReceiptLine(BaseModel):
    """A positive integer quantity received for a product variant."""

    __tablename__ = "inventory_receipt_lines"
    __table_args__ = (
        UniqueConstraint("receipt_id", "product_variant_id", name="uq_receipt_lines_receipt_variant"),
        Index("ix_inventory_receipt_lines_receipt_id", "receipt_id"),
        CheckConstraint("quantity > 0", name="ck_inventory_receipt_line_quantity_positive"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_receipts.id", ondelete="CASCADE"), nullable=False
    )
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="lines")


class InventoryTransaction(BaseModel):
    """Audit trail for all inventory movements."""

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_inventory_transactions_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_transactions_type", "type"),
        Index("ix_inventory_transactions_created_at", "created_at"),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=DEFAULT_WAREHOUSE_ID,
        nullable=False,
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="inventory_transaction_type_enum", native_enum=False),
        nullable=False,
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="transactions"
    )

    def __repr__(self) -> str:
        return f"<InventoryTransaction(id={self.id}, type={self.type}, quantity={self.quantity})>"
