"""Pydantic v2 schemas for the Blog module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.blog.domain.models import BlogPostStatus

# ============================================================================
# Category Schemas
# ============================================================================


class BlogCategoryCreate(BaseModel):
    """Schema for creating a blog category."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200, description="Category name")
    slug: str | None = Field(
        None,
        max_length=220,
        description="URL-friendly slug (auto-generated from name if omitted)",
    )


class BlogCategoryResponse(BaseModel):
    """Response schema for a blog category."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    post_count: int | None = Field(0, description="Number of published posts in this category")


# ============================================================================
# Post Schemas
# ============================================================================


class BlogPostCreate(BaseModel):
    """Schema for creating a new blog post."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=500, description="Article title")
    slug: str | None = Field(
        None,
        max_length=550,
        description="URL-friendly slug (auto-generated from title if omitted)",
    )
    content: str = Field(..., min_length=1, description="Article body in Markdown or HTML")
    excerpt: str | None = Field(None, max_length=1000, description="Brief summary or excerpt")
    cover_image_url: str | None = Field(None, max_length=500, description="Cover/header image URL")
    status: BlogPostStatus = Field(
        default=BlogPostStatus.DRAFT,
        description="Publication status: draft, published, or archived",
    )
    published_at: datetime | None = Field(
        None,
        description="Publication timestamp; automatically set to now if status is published",
    )
    category_id: uuid.UUID | None = Field(None, description="Associated category UUID")
    author_id: uuid.UUID | None = Field(
        None,
        description="Author user UUID (automatically set from current user if omitted)",
    )


class BlogPostUpdate(BaseModel):
    """Schema for updating an existing blog post (all fields optional)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=500)
    slug: str | None = Field(None, max_length=550)
    content: str | None = Field(None, min_length=1)
    excerpt: str | None = Field(None, max_length=1000)
    cover_image_url: str | None = Field(None, max_length=500)
    status: BlogPostStatus | None = None
    published_at: datetime | None = None
    category_id: uuid.UUID | None = None


class BlogPostResponse(BaseModel):
    """List / summary view of a blog post."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    slug: str
    excerpt: str | None = None
    cover_image_url: str | None = None
    status: BlogPostStatus
    published_at: datetime | None = None
    category_id: uuid.UUID | None = None
    category: BlogCategoryResponse | None = None
    reading_time: int | None = Field(
        default=None,
        description="Estimated reading time in minutes (based on 200 wpm)",
    )
    view_count: int = Field(default=0, description="Total views")
    author_name: str | None = Field(default=None, description="Author full name")
    created_at: datetime
    updated_at: datetime


class BlogPostDetailResponse(BlogPostResponse):
    """Full detail view of a single blog post."""

    content: str
    related_posts: list[BlogPostResponse] = Field(
        default_factory=list,
        description="List of related published posts",
    )
    seo: dict[str, Any] | None = Field(
        default=None,
        description="Associated SEO metadata",
    )


class BlogListResponse(BaseModel):
    """Paginated list of blog posts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BlogPostResponse]
    total: int = Field(ge=0, description="Total matching blog posts")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = False
    has_prev: bool = False
