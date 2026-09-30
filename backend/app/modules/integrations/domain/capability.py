"""The capability record and its availability rule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.integrations.domain.status import (
    CapabilityCategory,
    CapabilityReason,
    CapabilityStatus,
)


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    """One integration capability, as reported to clients.

    Every field is safe to return to a client: the record carries no
    credential, merchant id, endpoint URL, token, environment value, or
    stack trace. Whether a client is *allowed* to receive it is decided by
    ``customer_visible`` at the route layer, not here.
    """

    id: str
    category: CapabilityCategory
    display_name: str
    status: CapabilityStatus
    configured: bool
    customer_visible: bool
    available_to_customers: bool
    reason_code: CapabilityReason
    updated_at: datetime


# Only a capability that is verified-operational, or offered as an
# intentionally provisional capability, is usable by a customer right now.
# A mock, a disabled capability, a degraded capability, and a capability in
# maintenance are all reported but not counted as available.
_CUSTOMER_AVAILABLE_STATUSES = frozenset(
    {CapabilityStatus.LIVE, CapabilityStatus.BETA}
)


def is_available_to_customers(
    *,
    status: CapabilityStatus,
    configured: bool,
    customer_visible: bool,
) -> bool:
    """Derive the single availability flag from the other three indicators.

    Derived rather than assigned so the rule lives in exactly one place: an
    unconfigured, hidden, or non-available-status capability can never be
    reported as available to customers.
    """
    return (
        customer_visible
        and configured
        and status in _CUSTOMER_AVAILABLE_STATUSES
    )
