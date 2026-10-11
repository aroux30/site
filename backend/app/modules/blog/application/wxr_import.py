"""WXR → posts + comments + pages, in one transaction.

The parser (`wxr_parser.py`) turns the XML into a dict; this module decides
where each part of that dict goes:

* posts / categories / tags / comments → ``BlogTransferService.import_json``
* pages → the content module's ``import_content`` (upsert by slug, parents
  resolved by slug), because a page in WXR is a CMS page here, not a post.

Why one orchestrator instead of two call sites: the blog route and the
data-exchange route both import WXR files, and a page that lands in one path
but not the other is exactly the "parsed but silently dropped" failure this
project keeps finding. One function, both routes.

Order matters for atomicity: pages are imported FIRST and only flushed, then
the blog import runs last and its internal commit commits both. If the blog
half fails, the route-level rollback takes the pages with it — a half-imported
file is worse than a failed one.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: `<img src="…">` with either quote style. Group 1 is everything up to the
#: opening quote, group 2 the URL, group 3 the closing quote — so a rewrite
#: keeps the original quoting and attributes byte for byte.
_IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*?\ssrc\s*=\s*)("([^"]+)"|\'([^\']+)\')', re.IGNORECASE
)


async def _sideload_content_images(
    db: Any, parsed: dict[str, Any], *, uploader_id: uuid.UUID
) -> dict[str, int]:
    """Download the file's remote images and rewrite URLs to local media.

    WordPress's own importer does this — it fetches each attachment and
    rewrites the body — and without it every imported article points at the
    old site: when that site is switched off, which is the whole point of a
    migration, every image 404s. The featured image and every `<img>` in a
    post or page body go through the ordinary ``sideload_image`` path, so the
    SSRF guard, the magic-byte sniff and the size ceilings all apply.

    One fetch per distinct URL even when several posts share an image. A URL
    that fails to fetch is counted and left as-is rather than failing the
    import: one dead image must not cost the whole file, and the operator
    sees the count in the result.
    """
    from app.modules.media.application.sideload_service import sideload_image

    stats = {"images_imported": 0, "images_failed": 0}
    # url → (file_url, width, height), or None for "tried and failed". Cached
    # so a shared image is fetched once and a dead one is not retried per
    # occurrence. The dimensions travel with the URL because the rewritten
    # `<img>` gets them as attributes: `withResponsiveImages` only emits a
    # srcset when a width is present (it cannot know which derivatives the
    # uploader wrote otherwise), so a rewrite without them would leave every
    # imported image unoptimised.
    cache: dict[str, tuple[str, int | None, int | None] | None] = {}

    async def resolve(url: str) -> tuple[str, int | None, int | None] | None:
        if not url.startswith(("http://", "https://")):
            # Local paths, data: URIs and protocol-relative URLs are not the
            # old site's to serve; leave them untouched.
            return None
        if url in cache:
            return cache[url]
        try:
            asset = await sideload_image(db, url, uploader_id=uploader_id)
            cache[url] = (asset.file_url, asset.width, asset.height)
            stats["images_imported"] += 1
        except Exception as exc:  # noqa: BLE001 — one image must not sink the file
            cache[url] = None
            stats["images_failed"] += 1
            logger.warning(
                "wxr_image_sideload_failed",
                url=url[:200],
                error=str(exc)[:200],
            )
        return cache[url]

    #: Matches the opening tag through the src attribute so the rewrite can
    #: add width/height right after it when the source tag lacked them.
    async def rewrite_content(content: str | None) -> str | None:
        if not content or "<img" not in content.lower():
            return content
        pieces: list[str] = []
        last = 0
        for match in _IMG_SRC_RE.finditer(content):
            raw = match.group(2)
            url = match.group(3) if match.group(3) is not None else match.group(4) or ""
            resolved = await resolve(url) if url else None
            if resolved is None:
                continue
            local, width, height = resolved
            # Rebuild with the same quoting: group(2)'s first character is the
            # quote the source used.
            quote = raw[0]
            pieces.append(content[last : match.start()])
            pieces.append(f"{match.group(1)}{quote}{local}{quote}")
            # Width/height after the src, only when the tag carries neither:
            # an author-set value is left alone, and a srcset emitted from the
            # wrong width is worse than none (see content-responsive-images).
            tag_end = content.find(">", match.end())
            if tag_end != -1:
                tag_so_far = content[match.end() : tag_end]
                if width and "width=" not in tag_so_far.lower():
                    dims = f' width="{width}"'
                    if height and "height=" not in tag_so_far.lower():
                        dims += f' height="{height}"'
                    pieces.append(dims)
            last = match.end()
        if not pieces:
            return content
        pieces.append(content[last:])
        return "".join(pieces)

    async def rewrite_cover(item: dict[str, Any]) -> None:
        cover = item.get("cover_image_url")
        if not cover:
            return
        resolved = await resolve(cover)
        if resolved:
            item["cover_image_url"] = resolved[0]
        # On failure the original URL stays: a cover on a still-live site
        # beats a blank one, and the failed count reports it.

    for post in parsed.get("posts") or []:
        post["content"] = await rewrite_content(post.get("content"))
        await rewrite_cover(post)
    for page in parsed.get("pages") or []:
        page["content"] = await rewrite_content(page.get("content"))
        await rewrite_cover(page)

    return stats

#: `import_content` validates at most 500 pages per document. A real store can
#: export more, so pages are fed to it in batches inside the same transaction —
#: the limit is a per-call guard, not a statement about what a migration may
#: contain.
_PAGE_BATCH = 400

#: The document shape `import_content` accepts. Kept in sync with
#: `content.application.transfer_service.EXPORT_FORMAT` / ``EXPORT_VERSION``.
_CONTENT_FORMAT = "site-cms-export"
_CONTENT_VERSION = 1


def _pages_document(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """WXR page dicts → the CMS import document shape (`import_content`)."""
    from app.shared.domain.slug import generate_slug

    return {
        "format": _CONTENT_FORMAT,
        "version": _CONTENT_VERSION,
        "pages": [
            {
                "title": p["title"],
                # A page without `post_name` still needs a slug here: the
                # content import resolves parents by slug, and a slug-less
                # child could never be re-parented.
                "slug": p.get("slug") or generate_slug(p["title"]),
                "body_html": p.get("content") or "",
                "excerpt": p.get("excerpt"),
                "status": p.get("status") or "draft",
                "parent_slug": p.get("parent_slug"),
                # The featured image resolved from `_thumbnail_id`, and the
                # SEO the author tuned in Rank Math. Both were parsed and
                # dropped here: the page import shape carried neither, so a
                # migrated page lost its cover and its search metadata.
                "cover_image_url": p.get("cover_image_url"),
                "seo_title": (p.get("seo") or {}).get("title"),
                "seo_description": (p.get("seo") or {}).get("description"),
                "seo_focus_keyword": (p.get("seo") or {}).get("focus_keyword"),
            }
            for p in pages
        ],
    }


async def _apply_author_display_name(
    db: Any, parsed: dict[str, Any], *, author_id: uuid.UUID
) -> None:
    """Attribute the import to the operator who ran it — NOT the file's author.

    An earlier version adopted the WXR file's first author block (``آروکس``)
    as the importing user's display name. That was wrong and the owner
    corrected it: the article's author is the person who brought the data in
    — the operator who uploaded the XML — because they are the one publishing
    it on THIS site. The old site's author is a persona that belongs to the
    old site; borrowing their name would misattribute the post and put a
    stranger's byline on the storefront.

    What actually needs to happen is the opposite: make sure the importing
    user HAS a usable public name, so the byline is not the phone-tail
    fallback ("کاربر 0000"). If their profile is blank, derive a name from
    what we know about them — display name if set, else first+last, else the
    login/phone itself. Nothing from the file is written.
    """
    from sqlalchemy import select

    from app.modules.users.domain.models import User, UserProfile

    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == author_id))
    ).scalar_one_or_none()
    if profile is not None and (profile.display_name or "").strip():
        # The operator already has a public name — use theirs, not ours.
        return
    user = await db.get(User, author_id)
    if user is None:
        return
    # The phone is the login identifier; a byline of the raw number reads
    # better than "کاربر 0000" and the operator can change it in their
    # profile later. Only used when the profile carries no name at all.
    fallback_name = (getattr(user, "phone", "") or "").strip() or None
    if not fallback_name:
        return
    if profile is None:
        profile = UserProfile(user_id=author_id, display_name=fallback_name)
        db.add(profile)
    else:
        profile.display_name = fallback_name
    await db.flush()
    logger.info("wxr_author_set_to_importer", user_id=str(author_id))


async def import_wxr(
    db: Any,
    parsed: dict[str, Any],
    *,
    author_id: uuid.UUID,
    skip_existing: bool = True,
    sideload_images: bool = True,
) -> dict[str, Any]:
    """Import a parsed WXR file (posts, comments, pages) in one transaction.

    ``sideload_images`` fetches the file's remote images into the media
    library and rewrites the URLs before anything is stored — the same
    download-and-import step WordPress's own importer runs, and the only way
    an imported article survives the old site being switched off. A single
    failed image is counted, not fatal.

    Returns the blog import's stats extended with page counts and the parser's
    ``parsed`` counts, so the caller can show what the file held versus what
    landed.
    """
    from app.modules.blog.application.transfer_service import BlogTransferService
    from app.modules.content.application.transfer_service import import_content

    await _apply_author_display_name(db, parsed, author_id=author_id)

    image_stats: dict[str, int] = {"images_imported": 0, "images_failed": 0}
    if sideload_images:
        image_stats = await _sideload_content_images(db, parsed, uploader_id=author_id)

    # Pages first (flush only), blog last (its commit commits both).
    page_counts: dict[str, int] = {}
    pages = parsed.get("pages") or []
    for start in range(0, len(pages), _PAGE_BATCH):
        batch = await import_content(
            db,
            _pages_document(pages[start : start + _PAGE_BATCH]),
            author_id=author_id,
        )
        for key, value in batch.items():
            page_counts[key] = page_counts.get(key, 0) + int(value)

    stats = await BlogTransferService.import_json(
        db, parsed, author_id=author_id, skip_existing=skip_existing
    )

    result: dict[str, Any] = {
        "posts": stats.get("posts", 0),
        "categories": stats.get("categories", 0),
        "tags": stats.get("tags", 0),
        "comments": stats.get("comments", 0),
        "skipped": stats.get("skipped", 0),
        "comments_skipped": stats.get("comments_skipped", 0),
        "pages_created": page_counts.get("pages_created", 0),
        "pages_updated": page_counts.get("pages_updated", 0),
        "pages_reparented": page_counts.get("pages_reparented", 0),
        # Pages the storefront refused (a reserved slug like WooCommerce's
        # `cart`) — reported so "18 pages in the file, 17 imported" is
        # visible instead of looking like a clean run.
        "pages_skipped": page_counts.get("pages_skipped", 0),
        "images_imported": image_stats.get("images_imported", 0),
        "images_failed": image_stats.get("images_failed", 0),
        "parsed": parsed.get("counts", {}),
    }
    logger.info("wxr_imported", **{k: v for k, v in result.items() if k != "parsed"})
    return result
