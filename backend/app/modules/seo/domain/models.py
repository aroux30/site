"""SEO metadata domain models."""

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class SEOMetadata(BaseModel):
    """Per-resource SEO metadata and Open Graph tags."""

    __tablename__ = "seo_metadata"
    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "resource_id",
            name="uq_seo_metadata_resource",
        ),
        Index("ix_seo_metadata_resource_type", "resource_type"),
        Index(
            "ix_seo_metadata_resource_type_id",
            "resource_type",
            "resource_id",
        ),
    )

    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    og_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schema_markup: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # The keyphrase the content is written for — Rank Math's "focus keyword".
    # TEXT, not VARCHAR: Rank Math stores it as free text and a post can carry
    # several comma-separated keyphrases. The analyzer scores against it; the
    # value lived only in request payloads until migration `seokw1` (the
    # operator could analyze a keyword but had nowhere to keep the choice).
    focus_keyword: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rank Math's Advanced tab: per-resource robots directives. NULL means
    # "no explicit directive" (the site default applies); True/False are
    # explicit operator choices, so a page can be force-indexed even when a
    # broader rule would exclude it. Stored as booleans rather than a robots
    # string so the UI cannot write an invalid directive.
    robots_noindex: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    robots_nofollow: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Open Graph object type (article/website/product/...) — Rank Math's
    # Facebook tab. NULL = derive from the resource type.
    og_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Twitter/X card override. NULL = fall back to the OG values.
    twitter_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    twitter_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    twitter_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Additional keyphrases beyond the focus keyword (Rank Math Pro's
    # "additional keywords"), comma-separated.
    secondary_focus_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The last computed analyzer score (0-100). Rank Math stores this so the
    # admin list can show a score column without re-running the analyzer for
    # every row; NULL = never analyzed since the column existed.
    seo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<SEOMetadata(id={self.id}, resource_type={self.resource_type}, resource_id={self.resource_id})>"  # noqa: E501


class RedirectRule(BaseModel):
    """Admin-managed redirect, evaluated by storefront middleware.

    Status codes follow Rank Math's set: 301 (moved permanently), 302 (found),
    307 (temporary, method-preserving), 308 (permanent, method-preserving),
    410 (gone — no target), 451 (unavailable for legal reasons — no target).
    410/451 carry no destination by design: their whole meaning is "this is
    not coming back", and a 410 to a live page is a contradiction.
    """

    __tablename__ = "seo_redirects"
    __table_args__ = (
        UniqueConstraint("from_path", name="uq_seo_redirects_from_path"),
        Index("ix_seo_redirects_is_active", "is_active"),
    )

    from_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # Nullable: 410/451 have no target. The service enforces which codes may
    # omit it and which must carry one.
    to_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=301)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Regex matching (Rank Math's "Regex" comparison). When True, from_path is
    # a regular expression evaluated against the request path; a capture group
    # referenced as $1 in to_path is substituted (Rank Math's syntax).
    is_regex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Operator-facing note ("old campaign URL"), Rank Math's "note" field.
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<RedirectRule({self.from_path} → {self.to_path}, {self.status_code})>"


class Seo404Log(BaseModel):
    """One row per distinct not-found path (Rank Math's 404 Monitor).

    A counter, not an event log: the operator's question is "what is broken
    on my site", and a log of every hit to the same dead URL buries that
    answer. The first and last hit times are kept so a fixed path can be
    recognised (a row that stops growing), and the referrer and user agent
    from the most recent hit so a broken internal link can be told from a
    crawler following a stale sitemap entry.

    ``path`` is unique — the writer upserts and increments ``hit_count``.
    """

    __tablename__ = "seo_404_logs"
    __table_args__ = (
        UniqueConstraint("path", name="uq_seo_404_logs_path"),
        Index("ix_seo_404_logs_last_seen", "last_seen_at"),
    )

    path: Mapped[str] = mapped_column(String(500), nullable=False)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Seo404Log({self.path}, hits={self.hit_count})>"
