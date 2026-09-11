"""Pydantic schemas for the settings module."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SettingResponse(BaseModel):
    """Setting output schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: dict[str, Any] | None = None
    group: str | None = None
    description: str | None = None
    is_public: bool = False


class SettingCreateRequest(BaseModel):
    """Create setting payload."""

    key: str = Field(..., max_length=200)
    value: dict[str, Any] | None = None
    group: str | None = Field(None, max_length=100)
    description: str | None = None
    is_public: bool = False


class SettingUpdateRequest(BaseModel):
    """Update setting payload."""

    value: dict[str, Any] | None = None
    group: str | None = Field(None, max_length=100)
    description: str | None = None
    is_public: bool | None = None


class PublicSettingResponse(BaseModel):
    """Publicly visible setting."""

    key: str
    value: dict[str, Any] | None = None
