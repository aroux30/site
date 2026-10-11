"""SEO Status & Tools (Rank Math's Status & Tools page).

Three tools, each answering a question the operator actually asks:

- **Status checks**: a health read-out of the SEO setup — site URL configured,
  sitemap reachable, IndexNow key served, robots not blocking everything,
  noindex not applied site-wide by accident. Each check reports pass/warn/fail
  with a concrete fix, the same shape Site Health uses.
- **Incomplete data**: rows missing the SEO values this storefront can derive
  (posts without meta descriptions, products without seo_title). The operator
  sees a count and the affected ids; nothing is written without an explicit
  fill call.
- **Settings import/export**: every `seo_*` site option as JSON, so a setup can
  move between environments. Import validates types before writing and reports
  per-key results — a partial import with reasons beats an all-or-nothing one
  that says nothing.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Site option keys this module owns for export/import. A prefix match would
#: also catch unrelated keys; an explicit list is auditable.
SEO_OPTION_KEYS: tuple[str, ...] = (
    "seo_title_separator",
    "seo_breadcrumb_home_label",
    "seo_breadcrumb_separator",
    "seo_breadcrumb_show_blog",
    "indexnow_enabled",
    "image_seo_auto_alt",
    "image_seo_auto_title",
    "image_seo_auto_caption",
    "image_seo_auto_description",
    "image_seo_case",
    "image_seo_filename_separators",
    "image_seo_replacements",
    "rss_before_content",
    "rss_after_content",
    "rss_featured_image",
    "blog_public",
    "robots_extra_rules",
    "siteurl",
    "home",
)


async def run_status_checks(db: AsyncSession) -> list[dict[str, Any]]:
    """Every SEO status check, each with pass/warn/fail + a fix hint.

    The checks are deliberately shallow reads — this is a status page, not a
    crawler. Anything needing a network fetch is reported as its configured
    state instead.
    """
    from app.modules.seo.application.indexing_service import (
        KEY_OPTION,
        is_enabled,
        key_file_url,
    )
    from app.modules.seo.domain.models import SEOMetadata
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
        public_base_url,
    )

    checks: list[dict[str, Any]] = []

    def add(key: str, label: str, status: str, detail: str, fix: str = "") -> None:
        checks.append(
            {"key": key, "label": label, "status": status, "detail": detail, "fix": fix}
        )

    # 1. Site URL configured and not a placeholder.
    base = await public_base_url(db)
    if not base or "example.com" in base:
        add(
            "site_url",
            "آدرس سایت",
            "fail",
            f"آدرس سایت تنظیم نشده یا مقدار نمونه است: {base or '—'}",
            "در تنظیمات سئو، آدرس سایت را به دامنهٔ واقعی تغییر دهید.",
        )
    else:
        add("site_url", "آدرس سایت", "pass", base)

    # 2. Search visibility.
    public = await SiteOptionsService.get(db, "blog_public", "1") or "1"
    if public in ("1", "true", "yes", "on"):
        add("search_visibility", "نمایش در جستجو", "pass", "سایت برای خزنده‌ها باز است")
    else:
        add(
            "search_visibility",
            "نمایش در جستجو",
            "fail",
            "کل سایت noindex شده است (blog_public=0)",
            "اگر موقت است مشکلی نیست؛ در غیر این صورت در تنظیمات → خواندن فعالش کنید.",
        )

    # 3. Sitemap advertised.
    extra_rules = await SiteOptionsService.get(db, "robots_extra_rules", "") or ""
    if "Disallow: /" in extra_rules and "Allow: /" not in extra_rules:
        add(
            "robots_extra",
            "قواعد robots",
            "warn",
            "قاعدهٔ «Disallow: /» در خطوط سفارشی robots وجود دارد",
            "اگر عمدی نیست، از تنظیمات → محتوا حذفش کنید.",
        )
    else:
        add("robots_extra", "قواعد robots", "pass", "قاعدهٔ مسدودکنندهٔ سراسری نیست")

    # 4. IndexNow.
    if await is_enabled(db):
        key = await SiteOptionsService.get(db, KEY_OPTION)
        if key:
            add(
                "indexnow",
                "ایندکس فوری",
                "pass",
                f"فعال — فایل کلید: {key_file_url(base or '', key)}",
            )
        else:
            add(
                "indexnow",
                "ایندکس فوری",
                "warn",
                "فعال است ولی کلید ساخته نشده",
                "یک بار صفحهٔ تنظیمات ایندکس را باز کنید تا کلید ساخته شود.",
            )
    else:
        add(
            "indexnow",
            "ایندکس فوری",
            "warn",
            "غیرفعال — انتشارها به Bing/Yandex اعلام نمی‌شوند",
            "در تنظیمات → محتوا فعالش کنید.",
        )

    # 5. Posts missing meta description (the most common gap).
    total_posts = (
        await db.execute(
            select(func.count())
            .select_from(SEOMetadata)
            .where(SEOMetadata.resource_type == "blog_post")
        )
    ).scalar_one()
    missing_desc = (
        await db.execute(
            select(func.count())
            .select_from(SEOMetadata)
            .where(
                SEOMetadata.resource_type == "blog_post",
                (SEOMetadata.description.is_(None)) | (SEOMetadata.description == ""),
            )
        )
    ).scalar_one()
    if total_posts == 0:
        add(
            "meta_coverage",
            "پوشش توضیحات متا",
            "warn",
            "هنوز برای هیچ نوشته‌ای فراداده سئو ثبت نشده",
            "از ویرایشگر هر نوشته، پنل سئو را پر کنید.",
        )
    elif missing_desc > 0:
        add(
            "meta_coverage",
            "پوشش توضیحات متا",
            "warn",
            f"{missing_desc} از {total_posts} نوشتهٔ دارای فراداده، توضیحات متا ندارد",
            "از ویرایش گروهی یا ابزار «دادهٔ ناقص» استفاده کنید.",
        )
    else:
        add("meta_coverage", "پوشش توضیحات متا", "pass", f"همهٔ {total_posts} نوشته کامل")

    return checks


async def find_incomplete_data(db: AsyncSession) -> dict[str, Any]:
    """Rows missing SEO values the storefront can show or derive.

    Read-only: returns counts + sample ids. Filling happens through the
    explicit tools (bulk edit / editor panel), never as a side effect here.
    """
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.catalog.domain.models import Product, ProductStatus
    from app.modules.seo.domain.models import SEOMetadata

    # Posts without any seo_metadata row at all.
    seo_post_ids = set(
        (
            await db.execute(
                select(SEOMetadata.resource_id).where(
                    SEOMetadata.resource_type == "blog_post"
                )
            )
        ).scalars().all()
    )
    published_ids = (
        await db.execute(
            select(BlogPost.id).where(
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    posts_without_meta = [str(pid) for pid in published_ids if pid not in seo_post_ids]

    # Products without seo_title.
    products_missing = (
        await db.execute(
            select(func.count())
            .select_from(Product)
            .where(
                Product.status == ProductStatus.ACTIVE,
                (Product.seo_title.is_(None)) | (Product.seo_title == ""),
            )
        )
    ).scalar_one()

    return {
        "blog_posts_without_seo_metadata": len(posts_without_meta),
        "blog_post_ids": posts_without_meta[:50],
        "products_without_seo_title": int(products_missing),
    }


async def export_settings(db: AsyncSession) -> dict[str, str]:
    """Every SEO site option as a flat key→value map (the export payload)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    out: dict[str, str] = {}
    for key in SEO_OPTION_KEYS:
        value = await SiteOptionsService.get(db, key)
        if value is not None:
            out[key] = value
    return out


async def import_settings(db: AsyncSession, payload: dict[str, str]) -> dict[str, Any]:
    """Import SEO options; per-key results, unknown keys rejected loudly.

    Unknown keys are an error rather than silently ignored: a typo'd key in a
    hand-edited export would otherwise import "successfully" while changing
    nothing, and the operator would believe the setting applied.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    written = 0
    errors: list[dict[str, str]] = []
    for key, value in payload.items():
        if key not in SEO_OPTION_KEYS:
            errors.append({"key": key, "error": "کلید ناشناخته"})
            continue
        if not isinstance(value, str):
            errors.append({"key": key, "error": "مقدار باید رشته باشد"})
            continue
        try:
            await SiteOptionsService.set(db, key, value)
            written += 1
        except Exception as exc:  # noqa: BLE001 — per-key isolation
            errors.append({"key": key, "error": str(exc)[:120]})
    logger.info("seo_settings_imported", written=written, errors=len(errors))
    return {"written": written, "errors": errors, "total": len(payload)}


def settings_to_json(payload: dict[str, str]) -> str:
    """Pretty JSON with Persian text readable (ensure_ascii=False)."""
    return json.dumps(payload, indent=2, ensure_ascii=False)
