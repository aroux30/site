"""CRM API: the wholesale-inquiry pipeline.

The public capture endpoint is unauthenticated by design — a prospect on the
site has no account yet; that is the entire point of a lead. It is rate
limited at the deployment level and validated hard (contact name, phone,
plausible values) so the table cannot be filled by a script.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.crm.application import crm_service as svc
from app.modules.crm.domain.models import (
    CLOSED_STAGES,
    InquirySource,
    InquiryStage,
)

router = APIRouter()
_ADMIN = "/admin"


# ── Schemas ─────────────────────────────────────────────────────────────────


class InquiryCaptureRequest(BaseModel):
    """Public capture payload — what the storefront form posts."""

    contact_name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=20)
    company_name: str | None = Field(None, max_length=300)
    email: str | None = Field(None, max_length=255)
    message: str | None = Field(None, max_length=5000)
    estimated_monthly_volume: int | None = Field(None, ge=0)


class InquiryStageRequest(BaseModel):
    stage: InquiryStage
    lost_reason: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=2000)


class InquiryAssignRequest(BaseModel):
    owner_id: uuid.UUID | None = None


class InquiryNoteRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class InquiryConvertRequest(BaseModel):
    user_id: uuid.UUID = Field(
        ..., description="کاربری که حساب همکار روی آن ساخته می‌شود"
    )
    api_key_name: str | None = Field(None, max_length=100)


class InquiryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_name: str
    company_name: str | None = None
    phone: str
    email: str | None = None
    stage: str
    source: str
    message: str | None = None
    estimated_monthly_value_rial: int | None = None
    estimated_monthly_volume: int | None = None
    owner_id: uuid.UUID | None = None
    converted_user_id: uuid.UUID | None = None
    converted_at: datetime | None = None
    lost_reason: str | None = None
    notes: list[dict[str, Any]] | None = None
    next_follow_up_at: datetime | None = None
    created_at: datetime


class ConvertResponse(BaseModel):
    """Conversion result — the key is shown exactly once."""

    inquiry: InquiryResponse
    api_key_id: uuid.UUID
    key_prefix: str
    api_key: str = Field(..., description="نمایش یک‌باره — ذخیره کنید")


# ── Public capture ──────────────────────────────────────────────────────────


@router.post(
    "/inquiries",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a wholesale inquiry (public)",
)
async def capture_inquiry(
    body: InquiryCaptureRequest,
    db: AsyncSession = Depends(get_db),
) -> InquiryResponse:
    """Capture a wholesale inquiry from the storefront form.

    No authentication: a prospect has no account yet. Deliberately accepts no
    estimate fields — a self-declared budget is worthless and a spammer's
    favourite knob; staff fill the estimate after a real conversation.
    """
    inquiry = await svc.create_inquiry(
        db,
        contact_name=body.contact_name,
        phone=body.phone,
        company_name=body.company_name,
        email=body.email,
        source=InquirySource.WEB_FORM,
        message=body.message,
        estimated_monthly_volume=body.estimated_monthly_volume,
    )
    await db.commit()
    return InquiryResponse.model_validate(inquiry)


# ── Admin pipeline ──────────────────────────────────────────────────────────


@router.get(
    f"{_ADMIN}/inquiries",
    response_model=list[InquiryResponse],
    dependencies=[Depends(RequirePermissions("crm:read"))],
    summary="List wholesale inquiries (admin)",
)
async def list_inquiries(
    db: AsyncSession = Depends(get_db),
    stage: InquiryStage | None = Query(None),
    owner_id: uuid.UUID | None = Query(None),
    include_closed: bool = Query(True, description="نمایش مراحل بسته"),
    limit: int = Query(200, ge=1, le=500),
) -> list[InquiryResponse]:
    """Pipeline list, ordered by follow-up urgency. Requires ``crm:read``."""
    rows = await svc.list_inquiries(
        db, stage=stage, owner_id=owner_id, include_closed=include_closed, limit=limit
    )
    return [InquiryResponse.model_validate(r) for r in rows]


@router.get(
    f"{_ADMIN}/pipeline",
    dependencies=[Depends(RequirePermissions("crm:read"))],
    summary="Pipeline counts and value per stage (admin)",
)
async def pipeline_overview(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Header numbers for the pipeline board."""
    rows = await svc.list_inquiries(db, limit=500)
    return svc.pipeline_summary(rows)


@router.get(
    f"{_ADMIN}/stages",
    summary="Pipeline stage vocabulary (admin)",
    dependencies=[Depends(RequirePermissions("crm:read"))],
)
async def list_stages(
    _user: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    """The stage list plus which are terminal — the UI renders from this."""
    return {
        "stages": [s.value for s in InquiryStage],
        "closed": sorted(s.value for s in CLOSED_STAGES),
    }


@router.get(
    f"{_ADMIN}/inquiries/{{inquiry_id}}",
    response_model=InquiryResponse,
    dependencies=[Depends(RequirePermissions("crm:read"))],
    summary="One inquiry with its timeline (admin)",
)
async def get_inquiry(
    inquiry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InquiryResponse:
    """One inquiry, notes timeline included."""
    inquiry = await svc.get_inquiry(db, inquiry_id=inquiry_id)
    return InquiryResponse.model_validate(inquiry)


@router.patch(
    f"{_ADMIN}/inquiries/{{inquiry_id}}/stage",
    response_model=InquiryResponse,
    dependencies=[Depends(RequirePermissions("crm:write"))],
    summary="Move an inquiry through the pipeline (admin)",
)
async def move_stage(
    inquiry_id: uuid.UUID,
    body: InquiryStageRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> InquiryResponse:
    """Advance the stage. Illegal jumps and a missing LOST reason are refused."""
    inquiry = await svc.move_stage(
        db,
        inquiry_id=inquiry_id,
        target=body.stage,
        actor_id=actor_id,
        lost_reason=body.lost_reason,
        note=body.note,
    )
    await db.commit()
    return InquiryResponse.model_validate(inquiry)


@router.patch(
    f"{_ADMIN}/inquiries/{{inquiry_id}}/owner",
    response_model=InquiryResponse,
    dependencies=[Depends(RequirePermissions("crm:write"))],
    summary="Assign an inquiry to a staff member (admin)",
)
async def assign_owner(
    inquiry_id: uuid.UUID,
    body: InquiryAssignRequest,
    db: AsyncSession = Depends(get_db),
) -> InquiryResponse:
    """Claim or release an inquiry."""
    inquiry = await svc.assign_owner(db, inquiry_id=inquiry_id, owner_id=body.owner_id)
    await db.commit()
    return InquiryResponse.model_validate(inquiry)


@router.post(
    f"{_ADMIN}/inquiries/{{inquiry_id}}/notes",
    response_model=InquiryResponse,
    dependencies=[Depends(RequirePermissions("crm:write"))],
    summary="Append a timeline note (admin)",
)
async def add_note(
    inquiry_id: uuid.UUID,
    body: InquiryNoteRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> InquiryResponse:
    """Append a note to the inquiry timeline."""
    inquiry = await svc.add_note(
        db, inquiry_id=inquiry_id, text=body.text, actor_id=actor_id
    )
    await db.commit()
    return InquiryResponse.model_validate(inquiry)


@router.post(
    f"{_ADMIN}/inquiries/{{inquiry_id}}/convert",
    response_model=ConvertResponse,
    dependencies=[Depends(RequirePermissions("crm:write"))],
    summary="Convert an inquiry into a B2B partner (admin)",
)
async def convert_inquiry(
    inquiry_id: uuid.UUID,
    body: InquiryConvertRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ConvertResponse:
    """Provision the partner API key and mark the inquiry converted.

    The key is returned exactly once, like every other key-issuing path.
    Requires ``crm:write``.
    """
    inquiry, record, plaintext = await svc.convert_to_partner(
        db,
        inquiry_id=inquiry_id,
        user_id=body.user_id,
        api_key_name=body.api_key_name,
        actor_id=actor_id,
    )
    await db.commit()
    return ConvertResponse(
        inquiry=InquiryResponse.model_validate(inquiry),
        api_key_id=record.id,
        key_prefix=record.key_prefix,
        api_key=plaintext,
    )


__all__ = ["router"]
