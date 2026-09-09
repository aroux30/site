"""Pydantic v2 schemas for the SEO module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SEOMetadataCreate(BaseModel):
    """Schema for creating or updating SEO metadata."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(None, max_length=200, description="Page title tag")
    description: Optional[str] = Field(None, max_length=500, description="Meta description")
    canonical_url: Optional[str] = Field(None, max_length=500, description="Canonical link")
    og_title: Optional[str] = Field(None, max_length=200, description="Open Graph title")
    og_description: Optional[str] = Field(None, max_length=500, description="Open Graph description")
    og_image: Optional[str] = Field(None, max_length=500, description="Open Graph image URL")
    schema_markup: Optional[dict[str, Any]] = Field(
        None, description="Custom JSON-LD schema markup dictionary"
    )


class SEOMetadataUpdate(BaseModel):
    """Schema for updating SEO metadata (partial fields)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    canonical_url: Optional[str] = Field(None, max_length=500)
    og_title: Optional[str] = Field(None, max_length=200)
    og_description: Optional[str] = Field(None, max_length=500)
    og_image: Optional[str] = Field(None, max_length=500)
    schema_markup: Optional[dict[str, Any]] = None


class SEOMetadataResponse(BaseModel):
    """Response schema for SEO metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    schema_markup: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
