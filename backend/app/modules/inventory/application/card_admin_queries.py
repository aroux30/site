"""Admin read-model queries for digital cards.

Read-only listing helper for the admin inventory screen. The PIN and
encrypted payload columns are deliberately NOT selected — the route layer
serializes rows through DigitalCardResponse. The statement is fully
parameterized: both filter values travel as bound parameters, so no user
input is ever concatenated into the SQL text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, String, bindparam, text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Fully parameterized admin listing (status filter optional, newest first).
# CASTs give asyncpg explicit parameter types.
_LIST_CARDS_SQL = text(
    """
    SELECT id, product_id, delivery_type, serial_ciphertext, card_hash, status,
           max_uses, used_count, assigned_order_id, expire_at, used_at,
           reading_at, created_at
    FROM digital_cards
    WHERE (CAST(:status AS VARCHAR) IS NULL OR status = CAST(:status AS VARCHAR))
    ORDER BY created_at DESC
    LIMIT CAST(:limit AS INTEGER)
    """
).bindparams(
    bindparam("status", type_=String),
    bindparam("limit", type_=Integer),
)


async def list_cards_for_admin(
    db: AsyncSession,
    status: Any | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return the newest cards, newest first, optionally filtered by status.

    *status* accepts a DigitalCardStatus (or its string value) or None to
    list every status. Values are passed as bound parameters only.
    """
    result = await db.execute(
        _LIST_CARDS_SQL,
        {"status": getattr(status, "value", status), "limit": limit},
    )
    rows = [dict(row) for row in result.mappings()]

    # Raw SQL returns the persisted enum *names* (e.g. 'AVAILABLE'); the API
    # contract speaks enum *values* ('available'). Normalize both columns.
    from app.modules.inventory.domain.digital_models import (
        DigitalCardStatus as _Status,
    )
    from app.modules.inventory.domain.digital_models import (
        DigitalDeliveryType as _Delivery,
    )

    name_to_delivery = {m.name: m.value for m in _Delivery}
    name_to_status = {m.name: m.value for m in _Status}
    for row in rows:
        raw_delivery = row.get("delivery_type")
        if isinstance(raw_delivery, str):
            row["delivery_type"] = name_to_delivery.get(
                raw_delivery.upper(), raw_delivery.lower()
            )
        raw_status = row.get("status")
        if isinstance(raw_status, str):
            row["status"] = name_to_status.get(raw_status.upper(), raw_status.lower())

    # Serials are encrypted at rest (Sprint 1.1); the admin list may display
    # them, so decrypt here — the PIN ciphertext is still never selected.
    from app.modules.inventory.application.crypto_service import decrypt_serial

    for row in rows:
        ciphertext = row.pop("serial_ciphertext", None)
        if ciphertext:
            try:
                row["serial_number"] = decrypt_serial(ciphertext)
            except ValueError:
                row["serial_number"] = None
        else:
            row["serial_number"] = None
    return rows
