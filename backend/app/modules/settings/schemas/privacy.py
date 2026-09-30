"""Pydantic schemas for data-subject requests (GDPR articles 15 & 17).

Deliberately absent from every customer-facing response: the export payload
and the operator's private note. The payload is fetched once through its own
endpoint and immediately discarded server-side; the note is the operator's
working text, not something the subject is entitled to read.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.settings.domain.models import PrivacyRequestStatus, PrivacyRequestType


class PrivacyRequestCreate(BaseModel):
    """A customer's request, raised against their own account.

    There is no ``user_id`` field. Adding one would be the whole bug: the
    handler would have to decide whether to trust it, and forgetting to
    ignore it is a cross-account data leak. The subject comes from the token.
    """

    type: PrivacyRequestType
    reason: str | None = Field(None, max_length=2000)
    password: str | None = Field(
        None,
        max_length=256,
        description="Re-authentication for the erase request; required for erase.",
    )


class PrivacyRequestItem(BaseModel):
    """One request as the owner sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: PrivacyRequestType
    status: PrivacyRequestStatus
    reason: str | None = None
    verified_at: datetime | None = None
    confirmed_at: datetime | None = None
    admin_note: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    #: True when a result is ready to collect. Derived, not stored, so the
    #: UI cannot show a "download" button for a payload that was purged.
    has_result: bool = False


class PrivacyRequestListResponse(BaseModel):
    """The caller's own requests, newest first."""

    items: list[PrivacyRequestItem]


class PrivacyRequestConfirmRequest(BaseModel):
    """The emailed OTP that confirms an erase request.

    Six digits, matching what the OTP sender delivers; the service compares
    against the hashed row so a wrong guess reveals nothing about the code.
    """

    code: str = Field(
        ...,
        min_length=4,
        max_length=10,
        description="کد تأیید ارسال‌شده به شمارهٔ ثبت‌شدهٔ حساب",
    )


class PrivacyRequestAdminItem(PrivacyRequestItem):
    """The operator's view: adds the subject and the resolution actor."""

    user_id: uuid.UUID
    resolved_by: uuid.UUID | None = None
    result_expires_at: datetime | None = None


class PrivacyRequestAdminListResponse(BaseModel):
    """Paged operator queue."""

    items: list[PrivacyRequestAdminItem]
    total: int
    skip: int
    limit: int


class PrivacyRequestActionResponse(BaseModel):
    """Outcome of running (or rejecting) a queued request."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: PrivacyRequestType
    status: PrivacyRequestStatus
    admin_note: str | None = None
    resolved_at: datetime | None = None
    #: Set on a completed export so the operator UI can offer "open the
    #: subject's copy". The payload itself never travels on this response.
    has_result: bool = False


class PrivacyRequestReject(BaseModel):
    """Reject with a reason."""

    note: str = Field(..., min_length=1, max_length=2000)
