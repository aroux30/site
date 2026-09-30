"""Default site options seed (WordPress parity).

Seeds the site_options table with sensible defaults matching WordPress's
initial option set. Run once after migration or on first boot.

Usage:
    from app.modules.settings.application.default_options import seed_defaults
    await seed_defaults(db)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.settings.application.site_options_service import SiteOptionsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Default options matching WordPress wp_options equivalents
DEFAULTS: dict[str, str] = {
    # General
    "blogname": "فروشگاه",
    "blogdescription": "یک سایت فروشگاهی",
    # Left empty on purpose. Five readers use `home`/`siteurl` as the public
    # origin (feeds, OPML, sitemaps, newsletter links) and they all fall back
    # to the deployment's own env, so a seed of "https://example.com" was
    # published into every feed link, sitemap loc and password-reset URL on a
    # store that had moved on from it. An operator sets these once in Settings.
    "siteurl": "",
    "home": "",
    "admin_email": "admin@example.com",
    # The storefront contact card reads this. Empty by default: an unset store
    # should show nothing rather than a placeholder address, and the
    # /public/branding endpoint falls back to admin_email only when it is a
    # real address.
    "contact_email": "",
    "date_format": "Y/m/d",
    "time_format": "H:i",
    "timezone_string": "Asia/Tehran",
    "WPLANG": "fa_IR",

    # Reading / Content — these three are read at runtime.
    # posts_per_page -> blog.api.routes.list_posts
    # posts_per_rss  -> blog.api.routes.rss_feed
    # excerpt_length -> blog_service.list_posts (derived excerpt fallback)
    "posts_per_page": "10",
    "posts_per_rss": "20",
    "excerpt_length": "55",
    "excerpt_more": "...",
    # show_on_front -> storefront home rendering + middleware ("posts" serves
    # the blog index at "/"). page_on_front -> slug of a published CMS page
    # rendered as the static front page when show_on_front == "page".
    "show_on_front": "page",
    "page_on_front": "",

    # Permalink — LIVE. These drive URL generation (RSS feed links, sitemap,
    # storefront link builders via lib/permalinks.ts) and URL resolution (the
    # Next.js middleware rewrites structured paths back onto the canonical
    # file-tree routes). Editing them changes the public URLs.
    "permalink_structure": "/blog/%postname%/",
    "category_base": "category",
    "tag_base": "tag",

    # i18n — comma-separated list of content locales; the first is the default.
    # Content rows carry a locale each (blog_posts.locale / cms_pages.locale);
    # the storefront language switcher and admin translation tooling read this.
    "enabled_locales": "fa",
    "default_locale": "fa",

    # Discussion / Comments
    "default_comment_status": "open",
    "comment_moderation": "1",
    "comment_max_links": "2",
    "comments_per_page": "20",
    "thread_comments": "1",
    "thread_comments_depth": "3",
    # comment_registration -> comments require an authenticated user
    # (blog.application.comment_service.create_comment). "0" keeps guest
    # comments open (this site's default); "1" is the WordPress-flavoured
    # members-only mode.
    "comment_registration": "0",

    # Media
    "thumbnail_size_w": "150",
    "thumbnail_size_h": "150",
    "thumbnail_crop": "1",
    "medium_size_w": "300",
    "medium_size_h": "300",
    "large_size_w": "1024",
    "large_size_h": "1024",
    "uploads_use_yearmonth_folders": "1",
    # site_icon -> media URL rendered as the storefront favicon (app/layout.tsx
    # falls back to the bundled /icons/icon.svg when unset).
    "site_icon": "",

    # Media watermarking on upload (raster images only; read at runtime by
    # media.application.watermark_service). Enabled is off by default.
    "media_watermark_enabled": "0",
    "media_watermark_position": "bottom_right",
    "media_watermark_opacity": "0.35",
    # media_cdn_base_url is also read at runtime (media.application.public_url)
    # but has no seed row: the empty default means "serve from origin".

    # Privacy
    "blog_public": "1",
}


async def seed_defaults(db: AsyncSession) -> int:
    """Seed default options. Skips keys that already exist. Returns count seeded."""
    seeded = 0
    for key, value in DEFAULTS.items():
        existing = await SiteOptionsService.get(db, key)
        if existing is None:
            await SiteOptionsService.set(db, key, value)
            seeded += 1
    return seeded
