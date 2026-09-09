"""Pydantic schemas for the settings module."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SettingResponse(BaseModel):
    """Setting output schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: Optional[dict[str, Any]] = None
    group: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = False


class SettingCreateRequest(BaseModel):
    """Create setting payload."""

    key: str = Field(..., max_length=200)
    value: Optional[dict[str, Any]] = None
    group: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_public: bool = False


class SettingUpdateRequest(BaseModel):
    """Update setting payload."""

    value: Optional[dict[str, Any]] = None
    group: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class PublicSettingResponse(BaseModel):
    """Publicly visible setting."""

    key: str
    value: Optional[dict[str, Any]] = None
