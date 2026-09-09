"""Pydantic v2 schemas for the Blog module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.blog.domain.models import BlogPostStatus


# ============================================================================
# Category Schemas
# ============================================================================


class BlogCategoryCreate(BaseModel):
    """Schema for creating a blog category."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200, description="Category name")
    slug: Optional[str] = Field(
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    post_count: Optional[int] = Field(0, description="Number of published posts in this category")


# ============================================================================
# Post Schemas
# ============================================================================


class BlogPostCreate(BaseModel):
    """Schema for creating a new blog post."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=500, description="Article title")
    slug: Optional[str] = Field(
        None,
        max_length=550,
        description="URL-friendly slug (auto-generated from title if omitted)",
    )
    content: str = Field(..., min_length=1, description="Article body in Markdown or HTML")
    excerpt: Optional[str] = Field(None, max_length=1000, description="Brief summary or excerpt")
    cover_image_url: Optional[str] = Field(None, max_length=500, description="Cover/header image URL")
    status: BlogPostStatus = Field(
        default=BlogPostStatus.DRAFT,
        description="Publication status: draft, published, or archived",
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Publication timestamp; automatically set to now if status is published",
    )
    category_id: Optional[uuid.UUID] = Field(None, description="Associated category UUID")
    author_id: Optional[uuid.UUID] = Field(
        None,
        description="Author user UUID (automatically set from current user if omitted)",
    )


class BlogPostUpdate(BaseModel):
    """Schema for updating an existing blog post (all fields optional)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    slug: Optional[str] = Field(None, max_length=550)
    content: Optional[str] = Field(None, min_length=1)
    excerpt: Optional[str] = Field(None, max_length=1000)
    cover_image_url: Optional[str] = Field(None, max_length=500)
    status: Optional[BlogPostStatus] = None
    published_at: Optional[datetime] = None
    category_id: Optional[uuid.UUID] = None


class BlogPostResponse(BaseModel):
    """List / summary view of a blog post."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    slug: str
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    status: BlogPostStatus
    published_at: Optional[datetime] = None
    category_id: Optional[uuid.UUID] = None
    category: Optional[BlogCategoryResponse] = None
    reading_time: Optional[int] = Field(
        default=None,
        description="Estimated reading time in minutes (based on 200 wpm)",
    )
    view_count: int = Field(default=0, description="Total views")
    author_name: Optional[str] = Field(default=None, description="Author full name")
    created_at: datetime
    updated_at: datetime


class BlogPostDetailResponse(BlogPostResponse):
    """Full detail view of a single blog post."""

    content: str
    related_posts: list[BlogPostResponse] = Field(
        default_factory=list,
        description="List of related published posts",
    )
    seo: Optional[dict[str, Any]] = Field(
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
