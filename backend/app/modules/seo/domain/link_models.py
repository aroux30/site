"""Link Genius domain models (Rank Math Pro parity, self-hosted).

Four tables back the internal-linking toolkit:

* ``SeoInternalLink`` — one row per anchor found in a post body. Rank Math
  extracts links on every save and keeps them in a table so the admin can ask
  "which posts link to this one?" without re-parsing every body. ``url_hash``
  (md5 of the normalized URL) makes dedup and lookups cheap; ``target_post_id``
  is filled when the URL resolves to a post on this site, which is what turns
  a raw anchor into an internal-link edge.

* ``SeoLinkMap`` — a keyword→URL auto-linking rule ("every mention of
  «پابجی موبایل» links to /products/pubg-mobile"). Rank Math calls these
  "Keyword Maps"; they run on publish so a writer never has to hand-link the
  same product in every article.

* ``SeoLinkMapVariation`` — the individual keyword phrases for a map. A single
  map carries several phrasings (Persian word-order variants, synonyms), each
  its own row so the auto-linker scans one alternation pattern.

* ``SeoLinkAudit`` — the broken-link crawler's result per distinct URL. One row
  per ``url_hash`` (the same URL reached from many posts is checked once), with
  the HTTP status, a category, and a ``last_checked_at`` used to skip URLs
  checked in the last 24h.

None of these tables hold the *suggested* links — those are computed on demand
by :mod:`link_suggestion_service` from the posts themselves and never stored,
so a suggestion can never go stale against an edited body.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class SeoInternalLink(BaseModel):
    """One anchor extracted from a post body.

    ``link_type`` is ``internal`` (same site) or ``external``; ``anchor`` and
    ``other`` kinds are deliberately NOT stored — the table answers "what does
    this post link to", and an in-page ``#section`` anchor or a ``mailto:``
    is not a link an operator manages.

    ``url_hash`` is md5 of the normalized URL (scheme/host lowercased, trailing
    slash trimmed, fragment stripped). It is the dedup key: the same URL
    written three ways in one body collapses to one row.
    """

    __tablename__ = "seo_internal_links"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "url_hash",
            "anchor_text",
            name="uq_seo_internal_links_post_url_anchor",
        ),
        Index("ix_seo_internal_links_post_id", "post_id"),
        Index("ix_seo_internal_links_target_post_id", "target_post_id"),
        Index("ix_seo_internal_links_url_hash", "url_hash"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL when the URL is external or points at a slug that no longer resolves.
    target_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # internal | external
    link_type: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    is_nofollow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_blank: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<SeoInternalLink(post={self.post_id}, {self.link_type} {self.url})>"


class SeoLinkMap(BaseModel):
    """A keyword→URL auto-linking rule (Rank Math's "Keyword Map").

    ``max_links_per_post`` caps how many times one map may inject a link into a
    single post — an article that says a product name ten times should not get
    ten identical anchors. ``auto_link_on_publish`` gates whether the map runs
    automatically; a map with it off is still usable from the manual "apply"
    action, which is how an operator tests a new map before trusting it.
    """

    __tablename__ = "seo_link_maps"
    __table_args__ = (
        Index("ix_seo_link_maps_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Resolved at apply time; NULL when the target is a page this site does not
    # model as a post (a CMS page, a product).
    target_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="SET NULL"),
        nullable=True,
    )
    max_links_per_post: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    auto_link_on_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    variations: Mapped[list["SeoLinkMapVariation"]] = relationship(
        "SeoLinkMapVariation",
        back_populates="link_map",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SeoLinkMap({self.name} → {self.target_url})>"


class SeoLinkMapVariation(BaseModel):
    """One keyword phrase belonging to a link map.

    ``kind`` is ``manual`` (operator typed it) or ``ai`` (generated) — the two
    are shown differently in the panel, and keeping the origin lets the UI
    offer "remove AI variants" without touching the operator's own phrases.
    """

    __tablename__ = "seo_link_map_variations"
    __table_args__ = (
        UniqueConstraint(
            "map_id",
            "keyword",
            name="uq_seo_link_map_variations_map_keyword",
        ),
        Index("ix_seo_link_map_variations_map_id", "map_id"),
    )

    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seo_link_maps.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    # manual | ai
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    link_map: Mapped["SeoLinkMap"] = relationship(
        "SeoLinkMap", back_populates="variations"
    )

    def __repr__(self) -> str:
        return f"<SeoLinkMapVariation({self.keyword}, {self.kind})>"


class SeoLinkAudit(BaseModel):
    """The broken-link crawler's verdict for one distinct URL.

    One row per ``url_hash`` — the same dead URL linked from ten posts is
    checked once and reported once. ``category`` buckets the outcome so the
    admin can filter without parsing status codes:

    * ``ok``       — 2xx, or a 3xx that is mere normalization (the crawler
                     follows redirects and records the FINAL status).
    * ``redirect`` — a 3xx the crawler did not follow (cross-host, or a loop).
    * ``broken``   — 4xx/5xx.
    * ``timeout``  — no response in the budget.
    * ``error``    — DNS failure, TLS error, connection refused.
    * ``blocked``  — refused by our own SSRF guard (an internal address), so it
                     was never fetched.

    ``last_checked_at`` gates the 24h re-check skip. ``is_marked_safe`` is the
    operator's override: a URL that returns 403 to a bot but works in a
    browser (Cloudflare, a paywall) can be silenced without deleting the row.
    """

    __tablename__ = "seo_link_audit"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_seo_link_audit_url_hash"),
        Index("ix_seo_link_audit_category", "category"),
        Index("ix_seo_link_audit_last_checked", "last_checked_at"),
    )

    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    # Human-readable reason for the category (the exception text, the redirect
    # target, ...). Bounded: an exception message can be arbitrarily long.
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_marked_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_checked_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SeoLinkAudit({self.category} {self.http_status} {self.url})>"
