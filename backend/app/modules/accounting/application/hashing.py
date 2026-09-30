"""SHA-256 tamper-evident hash chain for posted journal entries.

Each posted entry stores ``hash = sha256(number | posted_at | lines |
previous_hash)`` where ``previous_hash`` is the hash of the previous posted
entry *in the same Jalali fiscal period* — the same Odoo-style
``inalterable_hash`` pattern the fiscal invoices use.

The canonical line serialization is deterministic: sorted account code, the
integer Rial debit/credit pair, and the line description, all JSON with
sorted keys and no whitespace. Editing any posted figure breaks that entry's
own hash; deleting or re-ordering an entry breaks the next link's
``previous_hash`` reference.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_lines(lines: list[Any]) -> str:
    """Deterministically serialize a line list for hashing.

    Integer Rial amounts only; account identity is the *code* (stable across
    a re-seed) with the row id as a fallback when the relationship is not
    loaded. Sorted keys + no whitespace so dict ordering can never change the
    digest.
    """
    payload = []
    for idx, line in enumerate(lines):
        account = getattr(line, "account", None)
        account_code = getattr(account, "code", None)
        payload.append(
            {
                "position": int(getattr(line, "position", idx + 1) or 0),
                "account_code": str(account_code) if account_code else None,
                "account_id": str(getattr(line, "account_id", "") or ""),
                "debit_rial": int(getattr(line, "debit_rial", 0) or 0),
                "credit_rial": int(getattr(line, "credit_rial", 0) or 0),
                "description": getattr(line, "description", None) or "",
            }
        )
    payload.sort(
        key=lambda item: (
            item["position"],
            item["account_code"] or "",
            item["account_id"],
            item["debit_rial"],
            item["credit_rial"],
        )
    )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(
    *,
    number: str,
    posted_at: datetime,
    lines: list[Any],
    previous_hash: str,
) -> str:
    """Compute the tamper-evident hash for one posted journal entry."""
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    posted_iso = posted_at.astimezone(UTC).isoformat()
    payload = "|".join([number, posted_iso, canonical_lines(lines), previous_hash])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_entry(
    *,
    number: str,
    posted_at: datetime,
    lines: list[Any],
    previous_hash: str,
    expected_hash: str,
) -> bool:
    """Recompute an entry's hash and compare it against the stored value."""
    return (
        compute_entry_hash(
            number=number,
            posted_at=posted_at,
            lines=lines,
            previous_hash=previous_hash,
        )
        == expected_hash
    )
