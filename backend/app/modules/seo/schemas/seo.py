"""Pydantic v2 schemas for the SEO module."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SEOMetadataCreate(BaseModel):
    """Schema for creating or updating SEO metadata."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, max_length=200, description="Page title tag")
    description: str | None = Field(None, max_length=500, description="Meta description")
    canonical_url: str | None = Field(None, max_length=500, description="Canonical link")
    og_title: str | None = Field(None, max_length=200, description="Open Graph title")
    og_description: str | None = Field(None, max_length=500, description="Open Graph description")
    og_image: str | None = Field(None, max_length=500, description="Open Graph image URL")
    schema_markup: dict[str, Any] | None = Field(
        None, description="Custom JSON-LD schema markup dictionary"
    )


class SEOMetadataUpdate(BaseModel):
    """Schema for updating SEO metadata (partial fields)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500)
    canonical_url: str | None = Field(None, max_length=500)
    og_title: str | None = Field(None, max_length=200)
    og_description: str | None = Field(None, max_length=500)
    og_image: str | None = Field(None, max_length=500)
    schema_markup: dict[str, Any] | None = None


class SEOMetadataResponse(BaseModel):
    """Response schema for SEO metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None
    schema_markup: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ============================================================================
# SEO Scoring Engine Schemas (Rank Math / Yoast for Iran Market)
# ============================================================================


class SeoCheckItem(BaseModel):
    """Result of an individual SEO evaluation check."""

    model_config = ConfigDict(str_strip_whitespace=True)

    passed: bool = Field(..., description="Whether check passed")
    title: str = Field(..., description="Name of the check in Persian")
    message: str = Field(..., description="Detailed result message in Persian")
    points: int = Field(..., description="Score awarded or penalty applied")
    max_points: int = Field(default=0, description="Maximum available points for this check")
    category: str | None = Field(
        default=None,
        description="Category of check (title, description, slug, content, media_links)",
    )


class SeoAnalysisRequest(BaseModel):
    """Request schema for scoring content SEO."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(default="", description="SEO title")
    content: str = Field(
        default="",
        description="Post or product content (HTML or markdown or plain text)",
    )
    focus_keyword: str = Field(default="", description="Focus keyphrase / keyword")
    slug: str = Field(default="", description="URL slug or permalink")
    meta_description: str = Field(default="", description="Meta description tag")
    images_count: int | None = Field(default=None, ge=0, description="Number of images")
    has_image_alt: bool | None = Field(
        default=None,
        description="Whether image with alt matching keyword is present",
    )
    internal_links_count: int | None = Field(
        default=None, ge=0, description="Count of internal/outbound links"
    )
    images: list[Any] | None = Field(
        default=None, description="List of images or image metadata dicts"
    )
    internal_links: list[str] | None = Field(
        default=None, description="List of internal / outbound link URLs"
    )


class SeoAnalysisResponse(BaseModel):
    """Complete response from automated SEO scoring engine."""

    model_config = ConfigDict(str_strip_whitespace=True)

    score: int = Field(..., ge=0, le=100, description="Overall score between 0 and 100")
    grade: str = Field(..., description="Grade: 'عالی', 'متوسط و نیازمند بهبود', or 'ضعیف'")
    grade_color: str = Field(..., description="Grade color: green, yellow, or red")
    word_count: int = Field(default=0, ge=0, description="Word count of content")
    keyword_density: float = Field(
        default=0.0, description="Calculated keyword density percentage"
    )
    checklist: list[SeoCheckItem] = Field(
        default_factory=list, description="Checklist items in Persian"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Actionable recommendations in Persian"
    )


