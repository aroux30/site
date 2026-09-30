"""Pydantic schemas for the backend i18n string catalogue."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class I18nStringCreate(BaseModel):
    """Upsert one catalogue row (key, locale) pair."""

    model_config = ConfigDict(str_strip_whitespace=True)

    key: str = Field(..., min_length=1, max_length=200, examples=["common.save"])
    locale: str = Field(..., min_length=2, max_length=10, examples=["fa"])
    value: str = Field(..., min_length=1)
    group: str | None = Field(None, max_length=100, examples=["common"])
    is_active: bool = True


class I18nStringBulkRequest(BaseModel):
    """Bulk upsert payload."""

    items: list[I18nStringCreate] = Field(..., min_length=1)


class I18nStringBulkResponse(BaseModel):
    """Bulk upsert result counts."""

    created: int
    updated: int
    total: int


class I18nStringResponse(BaseModel):
    """One catalogue row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    locale: str
    value: str
    group: str | None = None
    is_active: bool
    created_at: datetime


class I18nStringListResponse(BaseModel):
    """Paginated catalogue rows."""

    items: list[I18nStringResponse]
    total: int


class I18nCatalogResponse(BaseModel):
    """Public per-locale catalogue with the fallback chain applied."""

    locale: str
    default_locale: str
    strings: dict[str, Any]


class I18nSeedResponse(BaseModel):
    """Seed-defaults result counts."""

    created: int
    skipped: int
