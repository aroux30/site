"""Wholesale-inquiry pipeline: capture, progression, conversion.

The pipeline rules are deliberately strict about two things:

* **Stage moves are validated.** ``qualified`` is a claim that someone
  actually checked the prospect can buy; letting any stage jump to any other
  makes the field decoration rather than a funnel.
* **Conversion provisions a real partner account.** The value of a CRM is
  that the last step is not retyping — it creates the ``ResellerApiKey`` the
  partner needs and links it back to the inquiry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.crm.domain.models import (
    CLOSED_STAGES,
    InquirySource,
    InquiryStage,
    LeadInquiry,
    is_transition_allowed,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Sane upper bound on the structured estimate. A typo'd extra zero in a
#: rial amount is a 10x error that would skew every pipeline total; refusing
#: implausible figures beats reporting on them.
MAX_ESTIMATED_VALUE_RIAL = 100_000_000_000  # 10 billion Toman


async def create_inquiry(
    db: AsyncSession,
    *,
    contact_name: str,
    phone: str,
    company_name: str | None = None,
    email: str | None = None,
    source: InquirySource = InquirySource.WEB_FORM,
    message: str | None = None,
    estimated_monthly_value_rial: int | None = None,
    estimated_monthly_volume: int | None = None,
) -> LeadInquiry:
    """Record a new inquiry at the NEW stage."""
    clean_contact = (contact_name or "").strip()
    clean_phone = (phone or "").strip()
    if not clean_contact:
        raise ValidationError(
            "نام تماس الزامی است", error_code="CONTACT_NAME_REQUIRED"
        )
    if not clean_phone:
        raise ValidationError("شماره تماس الزامی است", error_code="PHONE_REQUIRED")
    if estimated_monthly_value_rial is not None:
        if estimated_monthly_value_rial < 0:
            raise ValidationError(
                "مبلغ برآوردی نمی‌تواند منفی باشد", error_code="NEGATIVE_VALUE"
            )
        if estimated_monthly_value_rial > MAX_ESTIMATED_VALUE_RIAL:
            raise ValidationError(
                "مبلغ برآوردی غیرواقعی است", error_code="IMPLAUSIBLE_VALUE"
            )

    inquiry = LeadInquiry(
        contact_name=clean_contact,
        company_name=(company_name or "").strip() or None,
        phone=clean_phone,
        email=(email or "").strip() or None,
        stage=InquiryStage.NEW,
        source=source,
        message=message,
        estimated_monthly_value_rial=estimated_monthly_value_rial,
        estimated_monthly_volume=estimated_monthly_volume,
    )
    db.add(inquiry)
    await db.flush()
    await logger.ainfo(
        "lead_inquiry_created",
        inquiry_id=str(inquiry.id),
        source=source.value,
        has_company=bool(inquiry.company_name),
    )
    return inquiry


async def get_inquiry(db: AsyncSession, *, inquiry_id: uuid.UUID) -> LeadInquiry:
    inquiry = await db.get(LeadInquiry, inquiry_id)
    if inquiry is None:
        raise NotFoundError("LeadInquiry")
    return inquiry


async def move_stage(
    db: AsyncSession,
    *,
    inquiry_id: uuid.UUID,
    target: InquiryStage,
    actor_id: uuid.UUID | None = None,
    lost_reason: str | None = None,
    note: str | None = None,
) -> LeadInquiry:
    """Advance an inquiry along the pipeline.

    Refuses illegal transitions, refuses to move a closed inquiry, and
    demands a reason when marking one LOST — "why did we lose them" is the
    only question a pipeline exists to answer later.
    """
    inquiry = await get_inquiry(db, inquiry_id=inquiry_id)

    if inquiry.stage in CLOSED_STAGES:
        raise ConflictError(
            f"این درخواست در وضعیت «{inquiry.stage.value}» بسته شده است",
            error_code="INQUIRY_CLOSED",
        )
    if not is_transition_allowed(inquiry.stage, target):
        raise ValidationError(
            f"گذار از «{inquiry.stage.value}» به «{target.value}» مجاز نیست",
            error_code="INVALID_STAGE_TRANSITION",
        )
    if target == InquiryStage.LOST and not (lost_reason or "").strip():
        raise ValidationError(
            "دلیل از دست رفتن درخواست الزامی است",
            error_code="LOST_REASON_REQUIRED",
        )
    if target == InquiryStage.CONVERTED:
        # Conversion goes through ``convert_to_partner`` — it provisions
        # accounts. Allowing a bare stage flip here would let a lead read as
        # converted while no partner account exists.
        raise ValidationError(
            "برای تبدیل به همکار از عملیات «تبدیل به همکار» استفاده کنید",
            error_code="USE_CONVERT_ENDPOINT",
        )

    previous = inquiry.stage
    inquiry.stage = target
    if target == InquiryStage.LOST:
        inquiry.lost_reason = lost_reason.strip()

    if note:
        inquiry.notes = [
            *(inquiry.notes or []),
            {
                "at": datetime.now(UTC).isoformat(),
                "actor_id": str(actor_id) if actor_id else None,
                "text": note.strip(),
                "event": f"stage:{previous.value}->{target.value}",
            },
        ]

    await db.flush()
    await logger.ainfo(
        "lead_inquiry_stage_changed",
        inquiry_id=str(inquiry_id),
        from_stage=previous.value,
        to_stage=target.value,
        actor_id=str(actor_id) if actor_id else None,
    )
    return inquiry


async def assign_owner(
    db: AsyncSession,
    *,
    inquiry_id: uuid.UUID,
    owner_id: uuid.UUID | None,
) -> LeadInquiry:
    """Assign (or unassign) the staff member responsible for the inquiry."""
    inquiry = await get_inquiry(db, inquiry_id=inquiry_id)
    inquiry.owner_id = owner_id
    await db.flush()
    await logger.ainfo(
        "lead_inquiry_owner_changed",
        inquiry_id=str(inquiry_id),
        owner_id=str(owner_id) if owner_id else None,
    )
    return inquiry


async def add_note(
    db: AsyncSession,
    *,
    inquiry_id: uuid.UUID,
    text: str,
    actor_id: uuid.UUID | None = None,
) -> LeadInquiry:
    """Append a timestamped note to the inquiry timeline."""
    clean = (text or "").strip()
    if not clean:
        raise ValidationError("متن یادداشت الزامی است", error_code="NOTE_REQUIRED")

    inquiry = await get_inquiry(db, inquiry_id=inquiry_id)
    inquiry.notes = [
        *(inquiry.notes or []),
        {
            "at": datetime.now(UTC).isoformat(),
            "actor_id": str(actor_id) if actor_id else None,
            "text": clean,
            "event": "note",
        },
    ]
    await db.flush()
    return inquiry


async def convert_to_partner(
    db: AsyncSession,
    *,
    inquiry_id: uuid.UUID,
    user_id: uuid.UUID,
    api_key_name: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[LeadInquiry, Any, str]:
    """Convert an inquiry into a B2B partner with an API key.

    Returns ``(inquiry, api_key_record, plaintext_key)``. The key is revealed
    once, exactly like the direct creation path — this endpoint is a
    convenience over that path, not a second implementation of it.

    The inquiry must be QUALIFIED or NEGOTIATING: converting a lead nobody
    has spoken to would silently bless an account we know nothing about.
    """
    inquiry = await get_inquiry(db, inquiry_id=inquiry_id)

    if inquiry.stage in CLOSED_STAGES:
        raise ConflictError(
            f"این درخواست قبلاً بسته شده است ({inquiry.stage.value})",
            error_code="INQUIRY_CLOSED",
        )
    if inquiry.stage not in (InquiryStage.QUALIFIED, InquiryStage.NEGOTIATING):
        raise ValidationError(
            "برای تبدیل، درخواست باید در مرحله «تایید صلاحیت» یا «مذاکره» باشد",
            error_code="INQUIRY_NOT_QUALIFIED",
        )

    from app.modules.orders.application import reseller_service

    key_name = (api_key_name or inquiry.company_name or inquiry.contact_name).strip()
    record, plaintext = await reseller_service.create_reseller_api_key(
        db,
        user_id=user_id,
        name=key_name,
    )

    inquiry.stage = InquiryStage.CONVERTED
    inquiry.converted_user_id = user_id
    inquiry.converted_at = datetime.now(UTC)
    inquiry.notes = [
        *(inquiry.notes or []),
        {
            "at": datetime.now(UTC).isoformat(),
            "actor_id": str(actor_id) if actor_id else None,
            "text": f"تبدیل به همکار — کلید «{key_name}» صادر شد",
            "event": "converted",
        },
    ]
    await db.flush()
    await logger.ainfo(
        "lead_inquiry_converted",
        inquiry_id=str(inquiry_id),
        user_id=str(user_id),
        api_key_id=str(record.id),
    )
    return inquiry, record, plaintext


async def list_inquiries(
    db: AsyncSession,
    *,
    stage: InquiryStage | None = None,
    owner_id: uuid.UUID | None = None,
    include_closed: bool = True,
    limit: int = 200,
) -> list[LeadInquiry]:
    """Pipeline list. Open inquiries first, then the most valuable.

    Ordering is by *follow-up urgency*, not recency: an unclaimed NEW inquiry
    from three weeks ago is more urgent than one from this morning, and a
    list sorted by created_at would hide exactly that.
    """
    stmt = select(LeadInquiry).limit(limit)
    if stage is not None:
        stmt = stmt.where(LeadInquiry.stage == stage)
    elif not include_closed:
        stmt = stmt.where(LeadInquiry.stage.notin_(tuple(CLOSED_STAGES)))
    if owner_id is not None:
        stmt = stmt.where(LeadInquiry.owner_id == owner_id)

    stmt = stmt.order_by(
        LeadInquiry.next_follow_up_at.asc().nullslast(),
        LeadInquiry.created_at.asc(),
    )
    return list((await db.execute(stmt)).scalars().all())


def pipeline_summary(inquiries: list[LeadInquiry]) -> dict[str, Any]:
    """Counts and value per stage, for the pipeline header. Pure."""
    by_stage: dict[str, int] = {}
    value_by_stage: dict[str, int] = {}
    for inquiry in inquiries:
        key = inquiry.stage.value if hasattr(inquiry.stage, "value") else str(inquiry.stage)
        by_stage[key] = by_stage.get(key, 0) + 1
        value = inquiry.estimated_monthly_value_rial or 0
        value_by_stage[key] = value_by_stage.get(key, 0) + value
    open_count = sum(
        count
        for stage_name, count in by_stage.items()
        if stage_name not in {s.value for s in CLOSED_STAGES}
    )
    return {
        "total": len(inquiries),
        "open": open_count,
        "by_stage": by_stage,
        "value_by_stage_rial": value_by_stage,
        "open_pipeline_value_rial": sum(
            value
            for stage_name, value in value_by_stage.items()
            if stage_name not in {s.value for s in CLOSED_STAGES}
        ),
    }
