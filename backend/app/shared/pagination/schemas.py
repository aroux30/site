"""Pagination schemas: offset-based and cursor-based.

Every paginated API endpoint should return a :class:`PaginatedResponse` (for
offset pagination) or :class:`CursorPaginatedResponse` (for cursor pagination).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Offset-based pagination ──────────────────────────────────────────────


class PaginationParams(BaseModel):
    """Query parameters for offset-based pagination."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginationMeta(BaseModel):
    """Metadata about the current page of results."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, *, page: int, page_size: int, total_items: int) -> PaginationMeta:
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for offset-paginated API responses."""

    success: bool = True
    data: list[T]
    meta: PaginationMeta


# ── Cursor-based pagination ──────────────────────────────────────────────


class CursorParams(BaseModel):
    """Query parameters for cursor-based (keyset) pagination."""

    cursor: str | None = Field(default=None, description="Opaque cursor from previous response")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items to return")


class CursorMeta(BaseModel):
    """Metadata for cursor-paginated results."""

    next_cursor: str | None = Field(
        default=None, description="Cursor to fetch the next page (null if no more)"
    )
    has_more: bool
    count: int = Field(description="Number of items in this page")


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for cursor-paginated API responses."""

    success: bool = True
    data: list[T]
    meta: CursorMeta


# ── Sorting ───────────────────────────────────────────────────────────────


class SortParams(BaseModel):
    """Query parameters for result ordering."""

    sort_by: str = Field(default="created_at", description="Column to sort by")
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort direction: 'asc' or 'desc'",
    )
