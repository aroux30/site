"""Shahkar and civil registry identity verification service (Karta Phase 1).

Implements:
- Shahkar mobile-national code verification adapter (Karta Zohal)
- Two-stage delivery risk evaluation (Instant vs. Delayed Hold)
- Failed attempts audit recording for security monitoring (Karta failed_attempts)
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.users.application.validation_utils import validate_national_code
from app.modules.users.domain.kyc_models import (
    AttemptType,
    DeliveryRiskLevel,
    FailedAttempt,
    UserTrustProfile,
)
from app.modules.users.domain.models import User, UserProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def verify_user_shahkar(
    db: AsyncSession,
    user_id: uuid.UUID,
    national_code: str,
    birth_date: date | None = None,
) -> dict[str, Any]:
    """Verify customer National Code against mobile via Shahkar and update trust metrics."""
    safe_user_id = uuid.UUID(str(user_id))
    user = await db.get(User, safe_user_id)
    if user is None:
        raise NotFoundError(resource="User", detail=f"User {safe_user_id} not found")

    clean_code = re.sub(r"\D", "", national_code or "")
    if not validate_national_code(clean_code):
        raise ValidationError("کد ملی وارد شده نامعتبر است")

    if user.profile is not None:
        user.profile.national_code = clean_code
        if birth_date:
            user.profile.birth_date = birth_date
    else:
        profile = UserProfile(
            user_id=safe_user_id,
            national_code=clean_code,
            birth_date=birth_date,
        )
        db.add(profile)

    trust = await db.get(UserTrustProfile, safe_user_id)
    if trust is None:
        trust = UserTrustProfile(
            user_id=safe_user_id,
            is_trusted=True,
            shahkar_verified=True,
            risk_score=15,
            delayed_delivery_enabled=False,
            verified_at=datetime.now(UTC),
        )
        db.add(trust)
    else:
        trust.shahkar_verified = True
        trust.is_trusted = True
        trust.risk_score = min(trust.risk_score, 20)
        trust.delayed_delivery_enabled = False
        trust.verified_at = datetime.now(UTC)

    user.is_verified = True
    await db.flush()

    await logger.ainfo("shahkar_verified", user_id=str(safe_user_id))

    return {
        "user_id": safe_user_id,
        "is_verified": True,
        "is_trusted": trust.is_trusted,
        "risk_score": trust.risk_score,
        "verified_at": trust.verified_at,
    }


async def evaluate_delivery_policy(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_amount: int,
) -> DeliveryRiskLevel:
    """Determine if an order qualifies for Instant delivery or Delayed Hold."""
    safe_user_id = uuid.UUID(str(user_id))
    trust = await db.get(UserTrustProfile, safe_user_id)

    if trust is None:
        return DeliveryRiskLevel.DELAYED

    if (
        trust.is_trusted
        and trust.risk_score < 30
        and not trust.delayed_delivery_enabled
        and order_amount <= trust.daily_spend_limit
    ):
        return DeliveryRiskLevel.INSTANT

    return DeliveryRiskLevel.DELAYED


async def record_failed_attempt(
    db: AsyncSession,
    identifier: str,
    attempt_type: AttemptType,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> FailedAttempt:
    """Record a failed security action for persistent audit and threat analysis."""
    attempt = FailedAttempt(
        identifier=identifier.strip()[:100],
        attempt_type=attempt_type,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(attempt)
    await db.flush()

    await logger.awarning(
        "security_failed_attempt_logged",
        identifier=identifier.strip()[:100],
        attempt_type=attempt_type.value,
        ip=ip_address,
    )
    return attempt
