"""SHA-256 tamper-evident hash chain for posted fiscal documents.

Each posted document stores ``hash = sha256(number | issued_at | totals |
previous_hash)`` where ``previous_hash`` is the hash of the previous posted
document in the same (fiscal_period, doc_type) chain — the Odoo
``inalterable_hash`` pattern. Editing any posted field (number, issue time,
totals) breaks that document's own hash; deleting or re-ordering a document
breaks the *next* link's ``previous_hash`` reference. ``verify_chain``
recomputes the whole chain and reports the first broken link.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

# Chain anchor for the first posted document of a period/type.
GENESIS_HASH = "0" * 64


def canonical_totals(totals: dict[str, Any]) -> str:
    """Serialize the totals snapshot deterministically.

    Integer Rial amounts only — the canonical form is JSON with sorted keys
    and no whitespace so the digest never depends on dict ordering.
    """
    return json.dumps(totals, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_document_hash(
    *,
    number: str,
    issued_at: datetime,
    totals: dict[str, Any],
    previous_hash: str,
) -> str:
    """Compute the tamper-evident hash for one posted document."""
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=UTC)
    issued_iso = issued_at.astimezone(UTC).isoformat()
    payload = "|".join([number, issued_iso, canonical_totals(totals), previous_hash])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_document(
    *,
    number: str,
    issued_at: datetime,
    totals: dict[str, Any],
    previous_hash: str,
    expected_hash: str,
) -> bool:
    """Recompute a document's hash and compare against the stored value."""
    return (
        compute_document_hash(
            number=number, issued_at=issued_at, totals=totals, previous_hash=previous_hash
        )
        == expected_hash
    )
