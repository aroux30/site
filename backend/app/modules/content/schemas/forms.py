"""Pydantic schemas for Visual Page Builder Form Builder submissions (Phase P4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FormSubmitRequest(BaseModel):
    """Payload sent by storefront when visitor submits a form_container widget."""

    model_config = ConfigDict(populate_by_name=True)

    form_id: str = Field(..., min_length=1, max_length=100, description="Form identifier or element ID")
    page_id: uuid.UUID | None = Field(default=None, description="Optional page UUID")
    page_slug: str | None = Field(default=None, max_length=220, description="Optional page slug")
    data: dict[str, Any] = Field(default_factory=dict, description="Submitted field values (name -> value)")
    # Anti-spam Honeypot field (must be empty from legitimate humans)
    hp_website: str | None = Field(
        default=None,
        alias="_hp_website",
        description="Honeypot trap field; bots filling this are dropped silently.",
    )


class FormSubmitResponse(BaseModel):
    """Response returned upon successful form submission."""

    success: bool = True
    message: str = "پیام یا فرم شما با موفقیت ثبت شد."
    submission_id: uuid.UUID | None = None


class FormSubmissionItemResponse(BaseModel):
    """Admin representation of a single visitor form submission."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    form_id: str
    page_id: uuid.UUID | None = None
    page_slug: str | None = None
    data: dict[str, Any]
    ip_address: str | None = None
    user_agent: str | None = None
    is_read: bool = False


class FormSubmissionListResponse(BaseModel):
    """Paginated list of form submissions for admin viewing."""

    items: list[FormSubmissionItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
