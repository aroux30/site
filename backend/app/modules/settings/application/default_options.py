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
    # How often the settings screen asks the operator to confirm the admin
    # address is still theirs (WordPress's admin_email_check_interval). A
    # working-but-abandoned address is otherwise the recovery channel forever.
    "admin_email_check_interval": "180",
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

    # Privacy — LIVE. Read by comment_ip_retention_service.mask_expired_ips, which
    # reduces the author IP of any comment older than this to its network (/24 for
    # IPv4, /64 for IPv6). A full address is kept for this long because a
    # moderation backlog is measured in hours, not months; an operator handling a
    # dispute can raise it. "0" masks every comment on the next scheduled run.
    "privacy.ip_retention_days": "30",
    # How long a produced GDPR export stays readable, in hours. 24 is the
    # default; clamped to 1..720 (30 days) on read. Read by
    # privacy_request_service.export_result_ttl, so changing it changes the
    # expiry of exports produced after the change.
    "privacy.export_retention_hours": "24",
    # Which CMS page is the privacy policy. A slug, not an id, so it survives a
    # database restore and is editable by hand — WordPress stores
    # ``wp_page_for_privacy_policy`` as a post id and silently breaks when the
    # ids change under a migration. Empty means "no policy published", which is
    # the honest default for a store that has not written one yet: the form
    # links render nothing rather than linking to a page that does not exist.
    # Read by privacy_policy_service, which serves /settings/public/privacy-policy.
    "privacy.policy_page": "",

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
    # require_name_email: a guest comment must carry a name and an email.
    # "0" keeps guest comments open, which is this site's default; the flag is
    # enforced in CommentService.create_comment, not just hinted at in the form,
    # because the API is the same endpoint the form posts to.
    "require_name_email": "0",
    # Akismet, the external half of WordPress's spam decision. Seeded EMPTY,
    # which is a real state and not a placeholder to be filled in: with no key
    # the client makes no request at all and the local `spam_filter` engine
    # decides alone — exactly what WordPress does with no key configured. Seeded
    # with a value instead, every store would start sending comment text to a
    # third party nobody asked it to.
    "spam_akismet_api_key": "",
    # Empty means the public rest.akismet.com; set it to a self-hosted endpoint
    # to keep comment text inside the shop's own network.
    "spam_akismet_api_url": "",
    # Comment notifications, WordPress's "Comments Notify" and "Moderation
    # Notify". Both on: the email path was built to be used, and shipping it
    # switched off would look like broken SMTP rather than a setting.
    "comments_notify": "1",
    "moderation_notify": "1",
    # Refuse comments on a post or page older than this many days.
    # close_comments_days_old is WordPress's close_comments_for_old_posts
    # pair, collapsed into one number so there is one field to explain and one
    # thing to get wrong. 0 never closes.
    "close_comments_days_old": "0",
    # Auto-approve someone who already has an approved comment. Off by default
    # because it is a trust decision: a returning commenter stops waiting a day
    # for their second comment to appear, and the queue stops filling with
    # replies to replies from people already known to the store. It keys on the
    # email and, for guests, the name with it — never the name alone.
    "comment_previously_approved": "0",
    # Registration is open by default on a storefront: a shop that cannot take
    # an order from a new customer is not a shop. Switched off it is not a
    # deletion — existing customers still log in, and a store in pre-launch
    # does not need a public form collecting numbers it cannot yet serve.
    "registration_enabled": "1",
    # Who a new account becomes. "customer" is the safe default; naming a role
    # with more power here is how a sign-up form hands out admin rights, so the
    # value is checked against the roles that exist rather than trusted.
    "registration_default_role": "customer",
    # Hold new accounts for an operator's approval. Off by default: a shop that
    # cannot take an order from a new customer is not a shop. A wholesale
    # storefront or a closed beta turns it on, and the account is created
    # pending with no session until an operator approves it.
    "registration_approval_required": "0",
    # Rate ceilings per address, on top of the 15-second flood check. The flood
    # window stops a burst; these stop a bot posting steadily for an hour, which
    # the flood window never notices. 0 disables each one.
    "comments_per_hour": "5",
    "comments_per_day": "20",
    "comments_per_page": "20",
    # WordPress's big_image_size_threshold. A modern phone camera produces
    # 4000px files that no storefront shows at full size; shipping them whole is
    # the difference between a product page that loads and one that does not.
    # 0 disables. Only downscales, never upscales.
    "big_image_size_threshold": "2560",
    # Which end of a thread a reader sees first. asc = oldest first, which is
    # what a conversation wants; desc = newest first, which is what a store
    # showing recent feedback usually wants. WordPress calls this comment_order.
    "comment_order": "asc",
    "thread_comments": "1",
    "thread_comments_depth": "3",
    # comment_registration -> comments require an authenticated user
    # (blog.application.comment_service.create_comment). "0" keeps guest
    # comments open (this site's default); "1" is the WordPress-flavoured
    # members-only mode.
    "comment_registration": "0",

    # Revisions — how many content snapshots to keep per blog post, the
    # equivalent of WordPress's WP_POST_REVISIONS. Read by
    # BlogService._prune_revisions. "-1" keeps every snapshot and disables
    # pruning entirely; the value is clamped to 1..500 on read, so a typo here
    # cannot empty the history or turn pruning off by accident.
    "post_revisions_to_keep": "20",

    # Media
    "thumbnail_size_w": "150",
    "thumbnail_size_h": "150",
    "thumbnail_crop": "1",
    "medium_size_w": "300",
    "medium_size_h": "300",
    "large_size_w": "1024",
    "large_size_h": "1024",
    # Operator-registered sizes (WordPress's add_image_size). A JSON array of
    # {name, width, height, crop}; read by image_processor.resolve_image_sizes
    # at generation time, so a new size applies to images uploaded after it is
    # added. Empty means "only the four built-ins".
    "custom_image_sizes": "[]",
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

    # URL embeds (oEmbed/Open Graph, read by content.application.embed_service).
    # The cache window was a module constant; 168 hours is the WordPress
    # default. Clamped to 1..720 on read.
    "embed_cache_ttl_hours": "168",
    # Comma-separated host allowlist for the provider path. Empty means "no
    # allowlist" — every provider resolves, which is the behaviour before the
    # option existed. A host outside the list still gets the Open Graph card;
    # the SSRF guard runs regardless.
    "embed_allowed_hosts": "",

    # Privacy
    "blog_public": "1",
    # robots_extra_rules: operator-added lines appended verbatim to the
    # storefront's /robots.txt (WordPress's "robots.txt" filter). The built-in
    # rules (allow/disallow and the sitemap line) are generated; this is the
    # escape hatch for a crawl rule that had no home — a shop blocking a
    # specific crawler, or adding a Crawl-delay. Read by the storefront
    # app/robots.txt route; empty means "only the generated rules".
    "robots_extra_rules": "",

    # Avatars — WordPress's show_avatars / avatar_default / avatar_rating.
    # show_avatars: "1" renders avatars site-wide; "0" hides them (both the
    #   uploaded image and the Gravatar fallback), matching WP's "Avatars" toggle.
    # avatar_default: the gravatar `d=` param used when a visitor has no
    #   Gravatar — one of mp/identicon/monsterid/wavatar/retro/robohash/blank/404.
    # avatar_rating: the gravatar `r=` param — g/pg/r/x.
    # Read by shared.content.gravatar.avatar_options; a bad stored value is
    # coerced to the safe default rather than forwarded to Gravatar.
    "show_avatars": "1",
    "avatar_default": "mp",
    "avatar_rating": "g",
    # Upload ceilings. Seeded to the values that used to be module constants,
    # so a fresh install and an upgraded one behave identically until an operator
    # changes them. Read per upload by MediaService.resolve_size_limit.
    # A new post starts in this category (by slug) and with this format. Both
    # were seeded and never read, so every post had to be categorised by hand.
    "default_category": "",
    "default_post_format": "standard",
    "media_max_file_size_mb": "10",
    "media_max_media_file_size_mb": "100",
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
