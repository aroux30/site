"""Content import/export (WordPress WXR / Strapi export parity, JSON flavour).

Exports CMS pages (+ their revision counts) and FAQs into one versioned JSON
document; imports upsert pages by slug so re-importing is idempotent — the
same file applied twice changes nothing the second time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.content.application import cms_page_service
from app.modules.content.domain.models import CmsPage, FAQItem, PageStatus
from app.modules.content.schemas.content import CmsPageCreateRequest, CmsPageUpdateRequest

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

EXPORT_FORMAT = "site-cms-export"
EXPORT_VERSION = 1

# Import safety rails: a hostile/accidental giant payload must not OOM the API.
MAX_IMPORT_PAGES = 500
MAX_BODY_CHARS = 500_000


async def export_content(db: Any) -> dict[str, Any]:
    """Full CMS content dump (pages + FAQs) as a JSON-serializable document."""
    pages = (
        (await db.execute(select(CmsPage).where(CmsPage.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    faqs = (await db.execute(select(FAQItem))).scalars().all()
    # Resolve parent ids to slugs in one pass rather than per row.
    parent_slugs: dict[uuid.UUID, str] = {}
    parent_ids = {p.parent_id for p in pages if p.parent_id is not None}
    if parent_ids:
        parent_slugs = {
            row.id: row.slug
            for row in (
                await db.execute(select(CmsPage).where(CmsPage.id.in_(parent_ids)))
            ).scalars()
        }
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "pages": [
            {
                "slug": p.slug,
                "title": p.title,
                "body_html": p.body_html,
                "excerpt": p.excerpt,
                "status": p.status.value if isinstance(p.status, PageStatus) else str(p.status),
                "seo_title": p.seo_title,
                "seo_description": p.seo_description,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "revision_number": p.revision_number,
                # The parent's slug, not its id: a UUID has no meaning in the
                # install being imported into, so the hierarchy only survives a
                # transfer if it travels as a name.
                "parent_slug": parent_slugs.get(p.parent_id),
            }
            for p in pages
        ],
        "faqs": [
            {
                "question": f.question,
                "answer_html": f.answer_html,
                "category": f.category,
                "position": f.position,
                "is_active": f.is_active,
            }
            for f in faqs
        ],
    }


def _validate_document(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("format") != EXPORT_FORMAT:
        raise ValidationError("سند import معتبر نیست (format ناشناخته است)")
    if doc.get("version", 0) > EXPORT_VERSION:
        raise ValidationError(f"نسخه سند ({doc.get('version')}) جدیدتر از پشتیبانی‌شده است")
    pages = doc.get("pages")
    if not isinstance(pages, list) or len(pages) > MAX_IMPORT_PAGES:
        raise ValidationError(f"تعداد صفحات باید بین ۰ و {MAX_IMPORT_PAGES} باشد")
    for page in pages:
        if not isinstance(page, dict) or not page.get("title"):
            raise ValidationError("هر صفحه باید title داشته باشد")
        if len(page.get("body_html") or "") > MAX_BODY_CHARS:
            raise ValidationError(f"بدنه صفحه «{page.get('title')}» بیش از حد بزرگ است")
    return doc


async def import_content(
    db: Any, doc: dict[str, Any], *, author_id: uuid.UUID | None = None
) -> dict[str, int]:
    """Upsert pages by slug; append missing FAQs by (question, category).

    Idempotent: matching pages are updated with identical content (no revision
    bump happens on identical edits, per cms_page_service), matching FAQs are
    skipped.
    """
    doc = _validate_document(doc)
    counts = {"pages_created": 0, "pages_updated": 0, "faqs_created": 0, "faqs_skipped": 0}
    # (child slug, parent slug) resolved after every page exists.
    pending_parents: list[tuple[str, str]] = []

    for item in doc.get("pages", []):
        parent_slug = item.get("parent_slug")
        if parent_slug:
            # Remember it for the second pass rather than resolving now: a
            # child may well be listed before its parent, and the parent row
            # does not exist until this loop has created it.
            pending_parents.append((item["slug"], parent_slug))
        existing = (
            await db.execute(
                select(CmsPage).where(
                    CmsPage.slug == item["slug"], CmsPage.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none() if item.get("slug") else None

        status_value = item.get("status", "draft")
        try:
            page_status = PageStatus(status_value)
        except ValueError:
            page_status = PageStatus.DRAFT

        if existing is None:
            await cms_page_service.create_page(
                db,
                CmsPageCreateRequest(
                    title=item["title"],
                    slug=item.get("slug"),
                    body_html=item.get("body_html") or "",
                    excerpt=item.get("excerpt"),
                    status=page_status,
                    seo_title=item.get("seo_title"),
                    seo_description=item.get("seo_description"),
                ),
                author_id=author_id,
            )
            counts["pages_created"] += 1
        else:
            await cms_page_service.update_page(
                db,
                existing.id,
                CmsPageUpdateRequest(
                    title=item["title"],
                    body_html=item.get("body_html"),
                    excerpt=item.get("excerpt"),
                    status=page_status,
                    seo_title=item.get("seo_title"),
                    seo_description=item.get("seo_description"),
                ),
                editor_id=author_id,
            )
            counts["pages_updated"] += 1

    # Second pass: wire up the hierarchy now that every page exists. Parents are
    # resolved by slug because a UUID from one install means nothing in another,
    # and a missing parent is a warning rather than a failure — the page still
    # imports, just as a root instead of a child.
    counts["pages_reparented"] = 0
    for child_slug, parent_slug in pending_parents:
        child = (
            await db.execute(
                select(CmsPage).where(
                    CmsPage.slug == child_slug, CmsPage.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        parent = (
            await db.execute(
                select(CmsPage).where(
                    CmsPage.slug == parent_slug, CmsPage.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if child is None or parent is None or child.id == parent.id:
            logger.warning("transfer_parent_unresolved", child=child_slug, parent=parent_slug)
            continue
        await cms_page_service.update_page(
            db,
            child.id,
            CmsPageUpdateRequest(parent_id=parent.id),
            editor_id=author_id,
        )
        counts["pages_reparented"] += 1

    for item in doc.get("faqs", []):
        question = (item.get("question") or "").strip()
        category = (item.get("category") or "عمومی").strip()
        if not question:
            continue
        existing = (
            await db.execute(
                select(FAQItem).where(
                    FAQItem.question == question, FAQItem.category == category
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            counts["faqs_skipped"] += 1
            continue
        db.add(
            FAQItem(
                question=question,
                answer_html=item.get("answer_html") or "",
                category=category,
                position=item.get("position", 0),
                is_active=bool(item.get("is_active", True)),
            )
        )
        counts["faqs_created"] += 1

    await db.flush()
    logger.info("cms_content_imported", **counts)
    return counts
