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


async def get_trust_profile(
    db: AsyncSession, user_id: uuid.UUID
) -> UserTrustProfile | None:
    """Load a user's trust profile by user_id.

    ``UserTrustProfile.id`` is a surrogate PK generated per row, so ``db.get``
    by that key never finds the profile a user actually owns — every trust
    read must key off the unique ``user_id`` column instead.
    """
    from sqlalchemy import select

    return (
        await db.execute(
            select(UserTrustProfile).where(
                UserTrustProfile.user_id == uuid.UUID(str(user_id))
            )
        )
    ).scalar_one_or_none()


async def verify_user_shahkar(
    db: AsyncSession,
    user_id: uuid.UUID,
    national_code: str,
    birth_date: date | None = None,
    mobile: str | None = None,
) -> dict[str, Any]:
    """Verify the account mobile against a national code via Shahkar.

    Karta Zohal semantics with strict no-fake-success rules (P0.1):

    - ``status="verified"``  → provider matched; trust flags are granted.
    - ``status="failed"``    → provider answered "no match"; a KYC failed
      attempt is recorded (Karta failed_attempts, 3 per 6h lockout basis).
    - ``status="unavailable"`` → provider not configured or unreachable;
      NOTHING is granted — the request stays effectively PENDING until the
      service is configured and answers.

    Identity data is persisted only from a verified match, never from raw
    user input.
    """
    from app.core.logging.security_audit import log_security_event
    from app.modules.users.application.identity_providers import get_identity_provider

    safe_user_id = uuid.UUID(str(user_id))
    user = await db.get(User, safe_user_id)
    if user is None:
        raise NotFoundError(resource="User", detail=f"User {safe_user_id} not found")

    clean_code = re.sub(r"\D", "", national_code or "")
    if not validate_national_code(clean_code):
        raise ValidationError("کد ملی وارد شده نامعتبر است")

    trust = await get_trust_profile(db, safe_user_id)
    current_trust = (
        trust
        if trust is not None
        else UserTrustProfile(
            user_id=safe_user_id, is_trusted=False, risk_score=50, verified_at=None
        )
    )

    async def _unverified_payload(status: str, message: str) -> dict[str, Any]:
        await logger.awarning(
            "shahkar_verification_not_granted",
            user_id=str(safe_user_id),
            status=status,
        )
        return {
            "status": status,
            "message": message,
            "user_id": safe_user_id,
            "is_verified": bool(user.is_verified),
            "is_trusted": bool(current_trust.is_trusted),
            "risk_score": current_trust.risk_score,
            "verified_at": current_trust.verified_at,
        }

    provider = get_identity_provider()
    if not provider.is_configured:
        return await _unverified_payload(
            "unavailable",
            "سرویس استعلام هویتی هنوز متصل نشده است؛ درخواست شما ثبت شد و پس از "
            "اتصال درگاه رسمی بررسی خواهد شد.",
        )

    # Shahkar must match the *account's own* mobile against the national
    # code. A caller-supplied mobile is never trusted: honouring it would
    # let an attacker verify with someone else's phone/national-code pair
    # and have their own account marked verified/trusted (identity binding
    # bypass). Only the account phone is used; a supplied override that
    # disagrees is rejected outright.
    account_mobile = re.sub(r"\D", "", str(getattr(user, "phone", "") or ""))
    if not account_mobile:
        raise ValidationError("شماره موبایلی برای تطبیق شاهکار یافت نشد")

    supplied_mobile = re.sub(r"\D", "", str(mobile or ""))
    if supplied_mobile and supplied_mobile != account_mobile:
        raise ValidationError(
            "شماره موبایل وارد‌شده با شماره حساب کاربری مطابقت ندارد",
            error_code="MOBILE_MISMATCH",
        )

    result = await provider.shahkar_match(account_mobile, clean_code)

    if result == "unavailable":
        return await _unverified_payload(
            "unavailable",
            "سرویس استعلام هویتی در دسترس نیست؛ لطفاً بعداً دوباره تلاش کنید.",
        )

    if result == "mismatch":
        await record_failed_attempt(
            db,
            identifier=account_mobile,
            attempt_type=AttemptType.KYC,
        )
        log_security_event(
            "kyc_shahkar_mismatch",
            identifier=str(safe_user_id),
            success=False,
            reason="shahkar national code / mobile mismatch",
        )
        return await _unverified_payload(
            "failed",
            "تطبیق کد ملی با شماره موبایل تأیید نشد. اطلاعات خود را بررسی کنید.",
        )

    # ── Verified: persist registry-backed data and grant trust ──
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

    log_security_event(
        "kyc_shahkar_verified",
        identifier=str(safe_user_id),
        success=True,
    )
    await logger.ainfo("shahkar_verified", user_id=str(safe_user_id))

    return {
        "status": "verified",
        "message": "هویت شما با موفقیت تأیید شد",
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
    trust = await get_trust_profile(db, user_id)

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
