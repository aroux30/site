"""CMS page service: draft/publish workflow, slug uniqueness, and revisions.

Pages are the source of truth for storefront copy (about, terms, returns, …)
so editors can change text without a deploy. Every mutating write snapshots a
``CmsPageRevision`` so a bad edit can be inspected and rolled back.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.blog.application.slug_history_service import (
    SLUG_RESOURCE_CMS_PAGE,
    record_slug_change,
)
from app.modules.content.domain.models import (
    CmsPage,
    CmsPageRevision,
    PageStatus,
)
from app.modules.content.schemas.content import (
    BulkActionResult,
    CmsPageCreateRequest,
    CmsPageListResponse,
    CmsPageResponse,
    CmsPageRevisionResponse,
    CmsPageUpdateRequest,
)
from app.shared.content.html_sanitizer import sanitize_html
from app.shared.domain.slug import generate_slug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Storefront routes that a CMS page must never shadow.
RESERVED_SLUGS: frozenset[str] = frozenset(
    {
        "admin",
        "api",
        "blog",
        "cart",
        "checkout",
        "compare",
        "favorites",
        "login",
        "products",
        "register",
        "returns",
        "rewards",
        "search",
        "payment",
        "mock-gateway",
    }
)


def _status_value(status: Any) -> str:
    """Render a page status for storage and audit trails.

    ``PageStatus`` is a ``str`` enum, so ``str(PageStatus.DRAFT)`` yields
    ``"PageStatus.DRAFT"``, not ``"draft"`` — the value the API contract and the
    frontend both compare against. ``.value`` is the only correct rendering.
    """
    return status.value if isinstance(status, PageStatus) else str(status)


def _snapshot(page: CmsPage, *, created_by: uuid.UUID | None) -> CmsPageRevision:
    """Build an immutable revision row from the page's current state."""
    return CmsPageRevision(
        page_id=page.id,
        revision_number=page.revision_number,
        title=page.title,
        slug=page.slug,
        body_html=page.body_html,
        excerpt=page.excerpt,
        status=_status_value(page.status),
        seo_title=page.seo_title,
        seo_description=page.seo_description,
        created_by=created_by,
    )


def _to_response(page: CmsPage) -> CmsPageResponse:
    return CmsPageResponse.model_validate(page)


async def _audit(
    db: AsyncSession,
    action: str,
    page: CmsPage,
    *,
    actor_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Write CMS edits into the platform audit log; never breaks the write."""
    try:
        from app.modules.audit.application.audit_service import log_action

        await log_action(
            db,
            actor_id=actor_id,
            action=action,
            resource="cms_page",
            resource_id=page.id,
            before=before,
            after=after or {"title": page.title, "slug": page.slug,
                            "status": _status_value(page.status)},
        )
    except Exception:  # noqa: BLE001
        logger.warning("cms_audit_log_failed", action=action, page_id=str(page.id))


async def _slug_exists(
    db: AsyncSession, slug: str, *, exclude_id: uuid.UUID | None = None
) -> bool:
    stmt = select(func.count(CmsPage.id)).where(CmsPage.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(CmsPage.id != exclude_id)
    return (await db.execute(stmt)).scalar_one() > 0


async def _validate_parent(
    db: AsyncSession, parent_id: uuid.UUID | None, *, page_id: uuid.UUID | None = None
) -> None:
    """Reject a parent that would make the page tree loop.

    Two failure modes, both of which make every ancestor walk recurse forever
    and hang a request rather than raise: a page made its own parent, and a
    page moved under one of its own descendants. The walk is iterative and
    bounded, because a cycle in the data must not be able to hang the check
    that is meant to catch one.
    """
    if parent_id is None:
        return

    if page_id is not None and parent_id == page_id:
        raise ValidationError("یک صفحه نمی‌تواند والد خودش باشد.")

    # Collect the ancestors of the proposed parent. If the page being edited
    # is among them, the proposed parent is one of its own descendants.
    seen: set[uuid.UUID] = set()
    cursor = parent_id
    for _ in range(_MAX_PARENT_WALK):
        if cursor is None or cursor in seen:
            return
        if page_id is not None and cursor == page_id:
            raise ValidationError("یک صفحه نمی‌تواند والد یکی از نوادگان خودش باشد.")
        seen.add(cursor)
        cursor = (
            await db.execute(select(CmsPage.parent_id).where(CmsPage.id == cursor))
        ).scalar_one_or_none()
    # A chain longer than the bound is itself a loop we cannot unwind; refuse
    # rather than accept a structure the breadcrumb would hang on.
    raise ValidationError("سلسله‌مراتب والدها بیش از حد عمیق است؛ احتمالاً یک چرخه وجود دارد.")


#: Bound on the ancestor walk. A hand-built page tree is a handful deep; a
#: hundred is already pathological, and an unbounded walk would be a hang.
_MAX_PARENT_WALK = 100


async def _ensure_unique_slug(
    db: AsyncSession, slug: str, *, exclude_id: uuid.UUID | None = None
) -> str:
    """Return ``slug``, suffixed with a counter until it is unique."""
    candidate = slug
    counter = 1
    while await _slug_exists(db, candidate, exclude_id=exclude_id):
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _resolve_slug(raw: str | None, fallback_text: str) -> str:
    base = (raw or "").strip() or generate_slug(fallback_text)
    if base in RESERVED_SLUGS:
        raise ValidationError(f"نامک «{base}» برای صفحه فروشگاه رزرو شده است")
    return base


# Strapi-style sortable columns: allowlisted so ?sort= never reaches SQL raw.
_PAGE_SORT_COLUMNS = {
    "title": CmsPage.title,
    "slug": CmsPage.slug,
    "status": CmsPage.status,
    "published_at": CmsPage.published_at,
    "created_at": CmsPage.created_at,
    "updated_at": CmsPage.updated_at,
}


async def list_pages(
    db: AsyncSession,
    *,
    status: PageStatus | None = None,
    search: str | None = None,
    sort: str | None = None,
    include_trashed: bool = False,
    locale: str | None = None,
) -> CmsPageListResponse:
    """List CMS pages for the admin table, newest edit first by default.

    ``sort`` follows the Strapi convention: ``<field>[:asc|desc]`` —
    e.g. ``title:asc``. Unknown fields fall back to newest-edit-first.
    Trashed (soft-deleted) pages are hidden unless ``include_trashed``.
    ``locale`` filters to one content language (Strapi i18n parity).
    """
    stmt = select(CmsPage)
    if not include_trashed:
        stmt = stmt.where(CmsPage.deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(CmsPage.status == status)
    if locale:
        stmt = stmt.where(CmsPage.locale == locale.strip())
    if search:
        like_q = f"%{search.strip()}%"
        stmt = stmt.where(CmsPage.title.ilike(like_q) | CmsPage.slug.ilike(like_q))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    order_clause: list[Any] = [CmsPage.updated_at.desc(), CmsPage.title.asc()]
    if sort:
        field, _, direction = sort.partition(":")
        column = _PAGE_SORT_COLUMNS.get(field.strip())
        if column is not None:
            order_clause = [column.asc() if direction.strip().lower() == "asc" else column.desc()]

    pages = (await db.execute(stmt.order_by(*order_clause))).scalars().all()
    return CmsPageListResponse(items=[_to_response(p) for p in pages], total=total)


async def get_page_by_id(db: AsyncSession, page_id: uuid.UUID) -> CmsPageResponse:
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")
    return _to_response(page)


async def get_page_by_slug(
    db: AsyncSession,
    slug: str,
    *,
    only_published: bool = True,
) -> CmsPageResponse:
    """Fetch a page for the storefront, or any state for the admin preview."""
    stmt = select(CmsPage).where(CmsPage.slug == slug, CmsPage.deleted_at.is_(None))
    if only_published:
        stmt = stmt.where(CmsPage.status == PageStatus.PUBLISHED)
    page = (await db.execute(stmt)).scalar_one_or_none()
    if not page:
        raise NotFoundError("CmsPage", f"Page '{slug}' not found")
    return _to_response(page)


async def get_page_by_slug_path(
    db: AsyncSession,
    path: str,
    *,
    only_published: bool = True,
) -> CmsPageResponse:
    """Fetch a page by its ``/parent/child/`` path.

    ``slug`` stays globally unique, so a nested path is resolved by walking
    down from the root rather than by matching a joined string — which also
    means a page moved to a different parent stops answering at its old URL,
    the same way WordPress behaves when a page is re-parented. The walk is
    bounded, so a cycle in stored data returns 404 rather than hanging.
    """
    segments = [s for s in path.split("/") if s]
    if not segments:
        raise NotFoundError("CmsPage", f"Page path '{path}' not found")

    parent: uuid.UUID | None = None
    page: CmsPage | None = None
    for segment in segments[:_MAX_PARENT_WALK]:
        stmt = select(CmsPage).where(
            CmsPage.slug == segment,
            CmsPage.deleted_at.is_(None),
        )
        # `parent_id IS NULL` vs `= :parent` — SQLAlchemy needs both shapes
        # spelled out, and `.is_(None)` is the correct one for the root.
        stmt = stmt.where(
            CmsPage.parent_id.is_(None) if parent is None else CmsPage.parent_id == parent
        )
        if only_published:
            stmt = stmt.where(CmsPage.status == PageStatus.PUBLISHED)
        page = (await db.execute(stmt)).scalar_one_or_none()
        if page is None:
            raise NotFoundError("CmsPage", f"Page '{path}' not found")
        parent = page.id

    if page is None or len(segments) > _MAX_PARENT_WALK:
        raise NotFoundError("CmsPage", f"Page '{path}' not found")
    return _to_response(page)


async def create_page(
    db: AsyncSession,
    data: CmsPageCreateRequest,
    *,
    author_id: uuid.UUID | None = None,
) -> CmsPageResponse:
    """Create a page and record its first revision."""
    slug = await _ensure_unique_slug(db, _resolve_slug(data.slug, data.title))
    await _validate_parent(db, data.parent_id)

    published_at: datetime | None = None
    if data.status == PageStatus.PUBLISHED:
        published_at = datetime.now(UTC)

    page = CmsPage(
        title=data.title.strip(),
        slug=slug,
        body_html=sanitize_html(data.body_html),
        excerpt=data.excerpt,
        status=data.status,
        seo_title=data.seo_title,
        seo_description=data.seo_description,
        author_id=author_id,
        published_at=published_at,
        revision_number=1,
        scheduled_publish_at=data.scheduled_publish_at,
        scheduled_unpublish_at=data.scheduled_unpublish_at,
        locale=data.locale,
        parent_id=data.parent_id,
    )
    db.add(page)
    await db.flush()
    db.add(_snapshot(page, created_by=author_id))
    await db.flush()

    logger.info("cms_page_created", page_id=str(page.id), slug=slug)
    await _audit(db, "cms_page.created", page, actor_id=author_id)
    await _emit(db, "page.created", page)
    return _to_response(page)


async def update_page(
    db: AsyncSession,
    page_id: uuid.UUID,
    data: CmsPageUpdateRequest,
    *,
    editor_id: uuid.UUID | None = None,
) -> CmsPageResponse:
    """Apply an edit and snapshot a new revision.

    Revisions are only recorded when the content actually changed, so toggling
    a status twice does not flood the history with identical snapshots.
    """
    page = await db.get(CmsPage, page_id)
    if not page or page.deleted_at is not None:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")

    # Re-parenting is the one edit that can break the tree, so it is checked
    # against the page's own descendants rather than trusted.
    if "parent_id" in data.model_fields_set:
        await _validate_parent(db, data.parent_id, page_id=page_id)

    old_status = page.status

    update_dict = data.model_dump(exclude_unset=True)

    # Plugin filter: plugins may transform the incoming payload before it lands.
    from app.shared.plugins.registry import HOOK_PAGE_BEFORE_SAVE, registry

    update_dict = await registry.apply_filters(
        HOOK_PAGE_BEFORE_SAVE, update_dict, page_id=str(page_id)
    )
    if not isinstance(update_dict, dict):
        update_dict = data.model_dump(exclude_unset=True)

    if update_dict.get("slug"):
        update_dict["slug"] = await _ensure_unique_slug(
            db, _resolve_slug(update_dict["slug"], page.title), exclude_id=page_id
        )
    else:
        update_dict.pop("slug", None)

    # Capture the slug *before* it is reassigned below. A slug is a public URL,
    # so renaming a page 404s every link to the old one; the history row is what
    # lets the storefront 301 to the new URL and lets the menu health check say
    # "renamed" instead of "deleted".
    previous_slug = page.slug

    if "status" in update_dict:
        new_status = update_dict["status"]
        if new_status == PageStatus.PUBLISHED and page.published_at is None:
            update_dict.setdefault("published_at", datetime.now(UTC))
        # A manual status change supersedes the pending schedule for that direction.
        if new_status == PageStatus.PUBLISHED:
            update_dict.setdefault("scheduled_publish_at", None)
        elif new_status == PageStatus.DRAFT:
            update_dict.setdefault("scheduled_unpublish_at", None)

    content_fields = {"title", "body_html", "excerpt", "seo_title", "seo_description", "slug"}
    is_content_edit = any(
        field in update_dict and update_dict[field] != getattr(page, field)
        for field in content_fields
    )

    # Sanitise before anything is written, and before the revision snapshot is
    # taken, so neither the live row nor the revision history can hold a
    # payload. The browser's DOMPurify pass is not this boundary: the API
    # accepts the same field directly.
    if "body_html" in update_dict and update_dict["body_html"]:
        update_dict["body_html"] = sanitize_html(update_dict["body_html"])

    for key, value in update_dict.items():
        setattr(page, key, value)

    if is_content_edit:
        page.revision_number = (page.revision_number or 1) + 1
        await db.flush()
        db.add(_snapshot(page, created_by=editor_id))

    if page.slug != previous_slug:
        await record_slug_change(
            db,
            resource_type=SLUG_RESOURCE_CMS_PAGE,
            resource_id=page.id,
            old_slug=previous_slug,
            new_slug=page.slug,
        )

    await db.flush()

    logger.info("cms_page_updated", page_id=str(page.id), revision=page.revision_number)
    await _audit(db, "cms_page.updated", page, actor_id=editor_id,
                 before={"status": _status_value(old_status)},
                 after={"title": page.title, "status": _status_value(page.status),
                        "revision_number": page.revision_number})
    await _emit(db, "page.updated", page)
    if page.status != old_status:
        if page.status == PageStatus.PUBLISHED:
            await _emit(db, "page.published", page)
            from app.shared.plugins.registry import HOOK_PAGE_AFTER_PUBLISH, registry

            await registry.do_action(HOOK_PAGE_AFTER_PUBLISH, page)
        elif old_status == PageStatus.PUBLISHED:
            await _emit(db, "page.unpublished", page)
    return _to_response(page)


async def delete_page(db: AsyncSession, page_id: uuid.UUID) -> None:
    """Soft delete: move to trash (restorable). Use ``hard_delete_page`` to purge."""
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")
    if page.deleted_at is None:
        page.deleted_at = datetime.now(UTC)
        await db.flush()
        await _emit(db, "page.deleted", page)
        await _audit(db, "cms_page.trashed", page, actor_id=None)
    logger.info("cms_page_trashed", page_id=str(page_id))


async def restore_page(db: AsyncSession, page_id: uuid.UUID) -> CmsPageResponse:
    """Restore a trashed page to its previous status (as a draft-safe restore)."""
    page = await db.get(CmsPage, page_id)
    if not page or page.deleted_at is None:
        raise NotFoundError("CmsPage", f"Trashed page {page_id} not found")
    page.deleted_at = None
    await db.flush()
    logger.info("cms_page_restored_from_trash", page_id=str(page_id))
    return _to_response(page)


async def hard_delete_page(db: AsyncSession, page_id: uuid.UUID) -> None:
    """Permanently delete a page and its revisions (only allowed from trash)."""
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")
    if page.deleted_at is None:
        raise ValidationError("صفحه ابتدا باید به سطل زباله منتقل شود")
    await _audit(db, "cms_page.hard_deleted", page, actor_id=None)
    await db.delete(page)
    await db.flush()
    logger.info("cms_page_hard_deleted", page_id=str(page_id))


async def duplicate_page(
    db: AsyncSession, page_id: uuid.UUID, *, author_id: uuid.UUID | None = None
) -> CmsPageResponse:
    """Copy a page as a new draft with a unique slug (WordPress "Duplicate")."""
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")
    copy_slug = await _ensure_unique_slug(db, f"{page.slug}-copy")
    now = datetime.now(UTC)
    copy = CmsPage(
        title=f"{page.title} (کپی)",
        slug=copy_slug,
        body_html=page.body_html,
        excerpt=page.excerpt,
        status=PageStatus.DRAFT,
        seo_title=page.seo_title,
        seo_description=page.seo_description,
        author_id=author_id,
        published_at=None,
        revision_number=1,
        locale=page.locale or "fa",
    )
    db.add(copy)
    await db.flush()
    db.add(_snapshot(copy, created_by=author_id))
    await db.flush()
    logger.info("cms_page_duplicated", source_id=str(page_id), copy_id=str(copy.id))
    await _emit(db, "page.created", copy)
    return _to_response(copy)


async def bulk_pages(
    db: AsyncSession,
    ids: list[uuid.UUID],
    action: str,
    *,
    actor_id: uuid.UUID | None = None,
    actor_payload: dict[str, Any] | None = None,
) -> BulkActionResult:
    """Run publish/unpublish/trash/restore over a set of page ids.

    Per-item failures are collected instead of aborting the batch, matching
    WordPress/Strapi bulk-action semantics.

    The ownership check is **per item**, not once for the batch. A single check
    over the id list would only prove the caller owns one of them, and the loop
    would then happily trash the rest — including a page the caller has never
    seen. A rejected item is counted as a failure and reported by id, which is
    the same shape as any other per-item error, so the admin screen already
    renders it without change.

    With ``actor_payload`` omitted the loop is unguarded, which is what the
    Celery entry points rely on; the route must pass it.
    """
    result = BulkActionResult(succeeded=0, failed=0)
    for page_id in ids:
        try:
            if action not in {"publish", "unpublish", "trash", "restore"}:
                raise ValidationError(f"عملیات ناشناخته: {action}")

            if actor_payload is not None:
                # Before the action, not after: `delete_page` and `restore_page`
                # commit, so a check that ran afterwards would refuse the caller
                # *after* the page had already moved. A rejection has to leave
                # the row exactly as it was.
                from app.core.security.object_capabilities import (
                    OBJECT_RULES,
                    require_object_capability,
                )
                from app.modules.content.domain.models import CmsPage

                page = await db.get(CmsPage, page_id)
                if page is None:
                    raise NotFoundError("CmsPage", f"Page {page_id} not found")
                await require_object_capability(actor_payload, page, OBJECT_RULES["pages"])

            if action == "publish":
                await update_page(db, page_id, CmsPageUpdateRequest(status=PageStatus.PUBLISHED), editor_id=actor_id)
            elif action == "unpublish":
                await update_page(db, page_id, CmsPageUpdateRequest(status=PageStatus.DRAFT), editor_id=actor_id)
            elif action == "trash":
                await delete_page(db, page_id)
            else:
                await restore_page(db, page_id)
            result.succeeded += 1
        except (NotFoundError, ValidationError, HTTPException) as exc:
            # HTTPException is caught deliberately. The guard raises 403, and an
            # uncaught one would abort the whole batch *after* the earlier items
            # had already committed — the caller would see "forbidden" and
            # reasonably assume nothing happened, while a third of their batch
            # had been trashed. Catching it keeps the promise this function's
            # docstring makes: every id is attempted, every failure is reported
            # by id, and the counts tell the operator what actually changed.
            result.failed += 1
            result.errors[str(page_id)] = str(exc.detail if isinstance(exc, HTTPException) else exc)
    logger.info("cms_page_bulk", action=action, succeeded=result.succeeded, failed=result.failed)
    return result


async def process_scheduled_pages(db: AsyncSession) -> dict[str, int]:
    """Publish/unpublish pages whose schedule is due (Celery beat entry body).

    Idempotent: firing clears the corresponding schedule column, so a rerun
    finds nothing to do.
    """
    now = datetime.now(UTC)
    due_publish = (
        (await db.execute(
            select(CmsPage).where(
                CmsPage.deleted_at.is_(None),
                CmsPage.scheduled_publish_at.is_not(None),
                CmsPage.scheduled_publish_at <= now,
                CmsPage.status != PageStatus.PUBLISHED,
            )
        ))
        .scalars()
        .all()
    )
    for page in due_publish:
        page.status = PageStatus.PUBLISHED
        page.published_at = page.scheduled_publish_at
        page.scheduled_publish_at = None
        await db.flush()
        await _emit(db, "page.published", page)

    due_unpublish = (
        (await db.execute(
            select(CmsPage).where(
                CmsPage.deleted_at.is_(None),
                CmsPage.scheduled_unpublish_at.is_not(None),
                CmsPage.scheduled_unpublish_at <= now,
                CmsPage.status == PageStatus.PUBLISHED,
            )
        ))
        .scalars()
        .all()
    )
    for page in due_unpublish:
        page.status = PageStatus.DRAFT
        page.scheduled_unpublish_at = None
        await db.flush()
        await _emit(db, "page.unpublished", page)

    counts = {"published": len(due_publish), "unpublished": len(due_unpublish)}
    if counts["published"] or counts["unpublished"]:
        logger.info("cms_scheduled_pages_processed", **counts)
    return counts


async def _emit(db: AsyncSession, event: str, page: CmsPage) -> None:
    """Publish the content event to the transactional outbox (webhook fan-out).

    The outbox row commits atomically with the content change; the beat-drained
    outbox worker later turns it into webhook deliveries. Failures never break
    the content write.
    """
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type=f"webhook.{event}",
            aggregate_type="cms_page",
            aggregate_id=str(page.id),
            payload={"id": str(page.id), "slug": page.slug, "title": page.title},
        )
    except Exception:  # noqa: BLE001 — webhooks must not block content writes
        logger.warning("cms_webhook_emit_failed", event_name=event, page_id=str(page.id))


async def list_revisions(
    db: AsyncSession, page_id: uuid.UUID, *, limit: int = 50
) -> list[CmsPageRevisionResponse]:
    """Revision history for a page, newest first."""
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")

    stmt = (
        select(CmsPageRevision)
        .where(CmsPageRevision.page_id == page_id)
        .order_by(CmsPageRevision.revision_number.desc())
        .limit(limit)
    )
    revisions = (await db.execute(stmt)).scalars().all()
    return [CmsPageRevisionResponse.model_validate(r) for r in revisions]


async def restore_revision(
    db: AsyncSession,
    page_id: uuid.UUID,
    revision_number: int,
    *,
    editor_id: uuid.UUID | None = None,
) -> CmsPageResponse:
    """Roll a page back to an earlier revision, recording the rollback as a new one."""
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")

    stmt = (
        select(CmsPageRevision)
        .where(
            CmsPageRevision.page_id == page_id,
            CmsPageRevision.revision_number == revision_number,
        )
        .options(selectinload(CmsPageRevision.page))
    )
    revision = (await db.execute(stmt)).scalar_one_or_none()
    if not revision:
        raise NotFoundError(
            "CmsPageRevision", f"Revision {revision_number} of page {page_id} not found"
        )

    page.title = revision.title
    page.body_html = revision.body_html
    page.excerpt = revision.excerpt
    page.seo_title = revision.seo_title
    page.seo_description = revision.seo_description
    page.revision_number = (page.revision_number or 1) + 1
    await db.flush()
    db.add(_snapshot(page, created_by=editor_id))
    await db.flush()

    logger.info(
        "cms_page_restored",
        page_id=str(page.id),
        restored_from=revision_number,
        new_revision=page.revision_number,
    )
    return _to_response(page)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _lastmod(row: Any) -> str:
    """``updated_at`` (falling back to ``created_at``/today) as YYYY-MM-DD."""
    stamp = getattr(row, "updated_at", None) or getattr(row, "created_at", None)
    return (stamp or datetime.now(UTC)).strftime("%Y-%m-%d")


def _sitemap_url(loc: str, row: Any, *, changefreq: str, priority: str) -> str:
    lastmod = _lastmod(row)
    return (
        "  <url>"
        f"<loc>{_escape_xml(loc)}</loc>"
        f"<lastmod>{lastmod}</lastmod>"
        f"<changefreq>{changefreq}</changefreq>"
        f"<priority>{priority}</priority>"
        "</url>"
    )


def render_sitemap_entries(
    pages: list[CmsPage],
    *,
    base_url: str,
    blog_categories: list[Any] | None = None,
    blog_tags: list[Any] | None = None,
    products: list[Any] | None = None,
) -> str:
    """Render ``<url>`` entries for published CMS pages.

    Returned as a fragment so the frontend ``sitemap.ts`` can merge these with
    product and blog URLs into one ``urlset``.

    Sitemap completeness: optional cross-section rows (blog categories/tags,
    catalog products — any object exposing ``slug`` + ``updated_at``) extend
    the fragment with their crawlable archive addresses. Passing ``None``
    (the default) keeps the historical page-only output byte-for-byte.
    """
    root = base_url.rstrip("/")
    lines: list[str] = []
    for page in pages:
        loc = f"{root}/{page.slug}" if page.slug else root
        lines.append(
            _sitemap_url(loc, page, changefreq="monthly", priority="0.5")
        )
    for category in blog_categories or []:
        lines.append(
            _sitemap_url(
                f"{root}/blog/category/{category.slug}",
                category,
                changefreq="weekly",
                priority="0.6",
            )
        )
    for tag in blog_tags or []:
        lines.append(
            _sitemap_url(
                f"{root}/blog/tag/{tag.slug}",
                tag,
                changefreq="weekly",
                priority="0.5",
            )
        )
    for product in products or []:
        lines.append(
            _sitemap_url(
                f"{root}/products/{product.slug}",
                product,
                changefreq="daily",
                priority="0.7",
            )
        )
    return "\n".join(lines)


def paginate(pages: list[CmsPage], *, page: int, page_size: int) -> tuple[list[CmsPage], int]:
    """Slice an in-memory page list, returning the window and total page count."""
    total = len(pages)
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    start = (page - 1) * page_size
    return pages[start : start + page_size], total_pages


async def list_published_page_summaries(
    db: AsyncSession,
    *,
    locale: str | None = None,
) -> list[CmsPage]:
    """Published, non-trashed pages for a public discovery surface.

    Returns ORM rows (the route maps them to a minimal schema) and applies no
    pagination: a sitemap generator wants every address in one call. The
    result is ordered by slug so the emitted sitemap is stable between builds.
    """
    stmt = select(CmsPage).where(
        CmsPage.status == PageStatus.PUBLISHED,
        CmsPage.deleted_at.is_(None),
    )
    if locale:
        stmt = stmt.where(CmsPage.locale == locale.strip())
    stmt = stmt.order_by(CmsPage.slug)
    return list((await db.execute(stmt)).scalars().all())
