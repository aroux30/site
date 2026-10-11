"""CMS page/FAQ import (the WXR migration path's landing point).

`import_content` upserts pages by slug (idempotent — the same document applied
twice changes nothing the second time) and appends missing FAQs by
``(question, category)``. The WordPress WXR import
(``blog.application.wxr_import``) is the caller: WXR pages are CMS pages here,
not posts, so they land through this function.

The JSON *export* half (``export_content``, the ``/admin/content/export``
route and the `manage.py cms export` command) was removed on 2026-10-07 with
the «انتقال محتوا» admin page. «ورود و خروج داده» (data-exchange) is the one
import/export surface, and it covers CMS pages and FAQs as first-class
entities. Archive: `_archived/content-transfer-removal-2026-10-07/`.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.content.application import cms_page_service
from app.modules.content.domain.models import CmsPage, FAQItem, PageStatus
from app.modules.content.schemas.content import CmsPageCreateRequest, CmsPageUpdateRequest

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: The document shape the WXR orchestrator builds. Kept in sync with
#: `blog.application.wxr_import._CONTENT_FORMAT` / ``_CONTENT_VERSION``.
EXPORT_FORMAT = "site-cms-export"
EXPORT_VERSION = 1

# Import safety rails: a hostile/accidental giant payload must not OOM the API.
MAX_IMPORT_PAGES = 500
MAX_BODY_CHARS = 500_000


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

    Per-page savepoints: one rejected page (a slug reserved by the storefront,
    e.g. WooCommerce's `cart`; a cycle; a duplicate) is counted as
    ``pages_skipped`` with a log line — it must not take the other 17 pages of
    a WordPress export down with it. A migration that imports nothing because
    one page collided is the failure this guards against.
    """
    doc = _validate_document(doc)
    counts = {
        "pages_created": 0,
        "pages_updated": 0,
        "pages_skipped": 0,
        "faqs_created": 0,
        "faqs_skipped": 0,
    }
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

        try:
            async with db.begin_nested():
                if existing is None:
                    await cms_page_service.create_page(
                        db,
                        CmsPageCreateRequest(
                            title=item["title"],
                            slug=item.get("slug"),
                            body_html=item.get("body_html") or "",
                            excerpt=item.get("excerpt"),
                            status=page_status,
                            # A page's featured image travels in the same
                            # document: the field existed on the create
                            # request and was never passed, so a migrated
                            # page lost its cover.
                            cover_image_url=item.get("cover_image_url"),
                            seo_title=item.get("seo_title"),
                            seo_description=item.get("seo_description"),
                        ),
                        author_id=author_id,
                    )
                    counts["pages_created"] += 1
                else:
                    # Only fields the file actually carried are sent: the
                    # update request treats an explicitly-passed `None` as
                    # "clear this column", so a file without a cover must
                    # leave the existing one alone rather than wipe it.
                    update_fields: dict[str, Any] = {
                        "title": item["title"],
                        "body_html": item.get("body_html"),
                        "excerpt": item.get("excerpt"),
                        "status": page_status,
                        "seo_title": item.get("seo_title"),
                        "seo_description": item.get("seo_description"),
                    }
                    if item.get("cover_image_url"):
                        update_fields["cover_image_url"] = item["cover_image_url"]
                    await cms_page_service.update_page(
                        db,
                        existing.id,
                        CmsPageUpdateRequest(**update_fields),
                        editor_id=author_id,
                    )
                    counts["pages_updated"] += 1
        except Exception as exc:
            # The savepoint rolled the page back; the rest of the document
            # continues. A reserved slug is the expected case (a WordPress
            # install carries its own cart/checkout pages, which this store
            # already owns), so it is a skip with a reason, not a failure.
            counts["pages_skipped"] += 1
            logger.warning(
                "cms_content_import_page_skipped",
                slug=item.get("slug"),
                error=str(exc),
            )
            continue

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
