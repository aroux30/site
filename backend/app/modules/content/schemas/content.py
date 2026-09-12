"""Pydantic v2 schemas for Content Management, Blocks, Menus, and FAQs (Karta Phase 7/9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.domain.models import BlockType, MenuLocation

# ── Homepage Block Schemas ────────────────────────────────────────────────


class HomepageBlockCreateRequest(BaseModel):
    """Admin payload to configure a homepage section."""

    title: str = Field(..., min_length=1, max_length=150)
    block_type: BlockType
    config: dict[str, Any] | None = None
    position: int = 0


class HomepageBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    block_type: BlockType
    config: dict[str, Any] | None = None
    position: int
    is_active: bool
    created_at: datetime


class BlockReorderRequest(BaseModel):
    """Admin payload to update display ordering of multiple blocks."""

    positions: dict[uuid.UUID, int] = Field(..., description="Mapping of block_id to new integer position")


# ── Tree Menu Schemas ─────────────────────────────────────────────────────


class MenuItemCreateRequest(BaseModel):
    """Admin payload to add a navigation link."""

    location: MenuLocation = MenuLocation.HEADER_MAIN
    title: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=500)
    parent_id: uuid.UUID | None = None
    position: int = 0
    icon: str | None = Field(None, max_length=50)


class MenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location: MenuLocation
    title: str
    url: str
    parent_id: uuid.UUID | None = None
    position: int
    icon: str | None = None
    is_active: bool


class TreeMenuItemNode(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    location: str
    position: int
    icon: str | None = None
    children: list[TreeMenuItemNode] = Field(default_factory=list)


# ── FAQ Schemas & Google Schema.org ───────────────────────────────────────


class FAQItemCreateRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)
    answer_html: str = Field(..., min_length=1)
    category: str = Field("عمومی", max_length=100)
    position: int = 0


class FAQItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer_html: str
    category: str
    position: int
    is_active: bool


class FAQListWithGoogleSchemaResponse(BaseModel):
    items: list[FAQItemResponse]
    total: int
    schema_json_ld: dict[str, Any] = Field(..., description="Valid Schema.org FAQPage JSON-LD for Google Rich Snippets")
