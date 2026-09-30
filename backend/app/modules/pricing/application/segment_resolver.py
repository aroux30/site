"""Map a user to the customer segment their price list applies.

Today the segment derives from the loyalty tier — the single existing
per-user tier signal. This keeps the pricelist wiring honest: no new source of
truth is invented, and upgrading the mapping later (e.g. an explicit B2B flag
on the user) is a one-line change here.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.modules.loyalty.domain.models import LoyaltyAccount, LoyaltyTier
from app.modules.pricing.domain.models import CustomerSegment

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Loyalty tier -> pricing segment. Guests / unmapped tiers resolve to RETAIL.
_TIER_TO_SEGMENT: dict[LoyaltyTier, CustomerSegment] = {
    LoyaltyTier.BRONZE: CustomerSegment.RETAIL,
    LoyaltyTier.SILVER: CustomerSegment.RETAIL,
    LoyaltyTier.GOLD: CustomerSegment.GOLD,
    LoyaltyTier.PLATINUM: CustomerSegment.WHOLESALE,
}


async def resolve_user_segment(
    db: AsyncSession,
    user_id: uuid.UUID | None,
) -> CustomerSegment:
    """The price-list segment for a user; RETAIL for guests and unknown users."""
    if user_id is None:
        return CustomerSegment.RETAIL

    stmt = select(LoyaltyAccount.tier).where(LoyaltyAccount.user_id == user_id)
    tier = (await db.execute(stmt)).scalar_one_or_none()
    segment = _TIER_TO_SEGMENT.get(tier, CustomerSegment.RETAIL)
    return segment
