"""Currency/USD-rate domain models.

One table, ``usd_price_updates``: the per-run change log the WordPress plugin
kept as a rotating text file (``nobitex_price_updates.log``). Each row is one
completed sweep: the rate it used, how many prices changed, and the exact
before/after per variant — stored as JSONB so the admin page can render the
same detail the plugin's log viewer showed, and the history is queryable.

Why a table and not a file: the project's admin surfaces (history + filter +
CSV export) all read from the database; a file inside the app directory is
invisible to them, lost on redeploy, and unwritable on a read-only filesystem.
The rows are written by the sweep only — there is no ORM write path from a
request, so the table is append-only in practice.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class UsdPriceUpdate(BaseModel):
    """One completed USD→Toman price sweep (the plugin's log entry)."""

    __tablename__ = "usd_price_updates"
    __table_args__ = (
        Index("ix_usd_price_updates_created_at", "created_at"),
        Index("ix_usd_price_updates_status", "status"),
    )

    #: The rate used, in RIAL (site money convention, ADR-012). The plugin
    #: worked in Toman; the site stores every amount in Rial and displays
    #: Toman, and the sweep converts the API's Rial quote once.
    rate_rial: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Where the rate came from: ``api`` (Nobitex) or ``manual`` (fallback).
    rate_source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'api'")
    )
    #: Number of variant prices this run rewrote.
    updated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    #: Whether this run was triggered by the schedule (True) or the operator's
    #: manual "update now" button (False). The plugin had the same distinction
    #: in its admin_post handler.
    scheduled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    #: ``success`` or ``failed`` — a failed run still logs its error, so the
    #: history shows outages instead of silently skipping them.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'success'")
    )
    #: Error detail for a failed run (empty for success).
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Per-variant change detail: [{variant_id, sku, product_name,
    #: usd_price, usd_sale_price, old_price, old_compare, new_price,
    #: new_compare}]. Same fields the plugin's log lines carried.
    details: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<UsdPriceUpdate(id={self.id}, rate_rial={self.rate_rial}, "
            f"updated={self.updated_count})>"
        )
