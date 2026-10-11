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
    # Left empty on purpose. Four readers use `home`/`siteurl` as the public
    # origin (feeds, OPML, sitemaps) and they all fall back
    # to the deployment's own env, so a seed of "https://example.com" was
    # published into every feed link, sitemap loc and password-reset URL on a
    # store that had moved on from it. An operator sets these once in Settings.
    "siteurl": "",
    "home": "",
    # `admin_email`, `admin_email_check_interval` and `contact_email` were
    # removed on 2026-10-07 with the email feature. The storefront contact
    # card now shows the phone number only.
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

    # Discussion / Comments
    "default_comment_status": "open",
    "comment_moderation": "1",
    "comment_max_links": "2",
    # `require_name_email` was removed on 2026-10-07: the comment form no
    # longer collects an email address at all (the column was dropped), so a
    # guest comment always carries a name only.
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
    # `comments_notify` / `moderation_notify` were removed on 2026-10-07 with
    # the comment notification emails they switched.
    # Refuse comments on a post or page older than this many days.
    # close_comments_days_old is WordPress's close_comments_for_old_posts
    # pair, collapsed into one number so there is one field to explain and one
    # thing to get wrong. 0 never closes.
    "close_comments_days_old": "0",
    # Auto-approve someone who already has an approved comment. Off by default
    # because it is a trust decision: a returning commenter stops waiting a day
    # for their second comment to appear, and the queue stops filling with
    # replies to replies from people already known to the store. It keys on
    # the name (the email column was removed on 2026-10-07).
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
    # cannot take an order from a new customer is not a shop. An invite-only
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

    # Image SEO (Rank Math Pro parity: the Image SEO module). All applied at
    # upload time by media.application.image_seo_service — the storefront
    # stores alt/title/caption on the asset row, so the fix belongs where the
    # row is written rather than at render time.
    # image_seo_auto_alt: fill alt_text from the (cleaned) file name when the
    # uploader left it empty. An image without alt is invisible to image
    # search and a WCAG failure, so the default is on.
    "image_seo_auto_alt": "1",
    # image_seo_auto_title: fill title from the cleaned file name when empty.
    "image_seo_auto_title": "1",
    # image_seo_auto_caption: fill caption from the cleaned file name when
    # empty. Off by default — a visible caption under every image is a layout
    # decision, not an SEO default (Rank Math gates it behind a setting too).
    "image_seo_auto_caption": "0",
    # image_seo_auto_description: fill description (the long text field) from
    # the cleaned file name when empty. Off by default, same reasoning.
    "image_seo_auto_description": "0",
    # image_seo_case: "none" | "lower" | "upper" — case applied to the
    # auto-generated text only, never to operator-typed text (Rank Math's
    # img_title_change_case / alt case settings).
    "image_seo_case": "none",
    # image_seo_filename_separators: characters in the original file name that
    # become spaces in the generated text ("my-product_photo.jpg" →
    # "my product photo"). Stored as the set, so an operator can add one.
    "image_seo_filename_separators": "-_",
    # image_seo_replacements: JSON array of {"from": "...", "to": "..."} pairs
    # applied to the generated text (Rank Math's image_replacements). Empty
    # means no replacements.
    "image_seo_replacements": "[]",

    # RSS feed extras (Rank Math's RSS module): text the operator wants around
    # every feed item's body — a signature, a sponsorship note, a link back.
    # Empty means nothing is injected; the feed stays byte-identical to before.
    "rss_before_content": "",
    "rss_after_content": "",
    # rss_featured_image: include the post cover as <media:content> in RSS
    # items. Feeds are read where images do not render inline, so the value is
    # giving readers (and feed-based scrapers) the image URL itself. On by
    # default, matching Rank Math.
    "rss_featured_image": "1",

    # Titles & Meta (Rank Math's Titles & Meta panel): one default
    # title/description template per content type, plus the global separator.
    # Rendered by seo.application.titles_meta_service with the variable engine
    # in seo.application.template_engine. Empty/unset = the built-in default
    # (DEFAULT_TITLE_TEMPLATES in that module), so these rows document the
    # initial values rather than being required.
    "seo_title_separator": "|",
    "seo_default_title_template_post": "%title% %sep% %sitename%",
    "seo_default_description_template_post": "%excerpt%",
    "seo_default_title_template_page": "%title% %sep% %sitename%",
    "seo_default_description_template_page": "%excerpt%",
    "seo_default_title_template_product": "%title% %sep% خرید و بررسی",
    "seo_default_description_template_product": "%excerpt%",
    "seo_default_title_template_category": "%title% %sep% %sitename%",
    "seo_default_description_template_category": "بهترین قیمت و مشخصات محصولات %title%",
    "seo_default_title_template_tag": "%title% %sep% %sitename%",
    "seo_default_description_template_tag": "مطالب مرتبط با %title%",
    "seo_default_title_template_author": "نوشته‌های %title% %sep% %sitename%",
    "seo_default_description_template_author": "همهٔ نوشته‌های %title%",
    "seo_default_title_template_archive": "%title% %sep% %sitename%",
    "seo_default_description_template_archive": "آرشیو %title%",
    "seo_default_title_template_home": "%sitename% %sep% %sitedesc%",
    "seo_default_description_template_home": "%sitedesc%",

    # Breadcrumbs (Rank Math's Breadcrumbs panel). The storefront renders the
    # trail and its BreadcrumbList JSON-LD; these options shape both, so the
    # visible trail and the structured data can never disagree.
    # seo_breadcrumb_home_label: the first crumb's text ("خانه" by default).
    "seo_breadcrumb_home_label": "خانه",
    # seo_breadcrumb_separator: the glyph BETWEEN crumbs in the visible trail.
    # The JSON-LD carries no separator (it is structured, not rendered), so
    # this option is presentation-only.
    "seo_breadcrumb_separator": "/",
    # seo_breadcrumb_show_blog: include the "وبلاگ" crumb in post trails.
    # Off = Home > Category > Post (Rank Math's "remove blog from crumbs").
    "seo_breadcrumb_show_blog": "1",

    # Local SEO (Rank Math's Local SEO): the store's own business profile.
    # Read by seo.application.local_seo_service, which builds the
    # LocalBusiness JSON-LD; empty fields are omitted from the node, never
    # emitted blank. A single business — not a multi-location directory.
    "local_seo_business_name": "",
    "local_seo_business_type": "Store",
    "local_seo_address": "",
    "local_seo_telephone": "",
    "local_seo_opening_hours": "",
    "local_seo_price_range": "",
    "local_seo_latitude": "",
    "local_seo_longitude": "",

    # URL embeds (oEmbed/Open Graph, read by content.application.embed_service).
    # The cache window was a module constant; 168 hours is the WordPress
    # default. Clamped to 1..720 on read.
    "embed_cache_ttl_hours": "168",
    # Comma-separated host allowlist for the provider path. Empty means "no
    # allowlist" — every provider resolves, which is the behaviour before the
    # option existed. A host outside the list still gets the Open Graph card;
    # the SSRF guard runs regardless.
    "embed_allowed_hosts": "",

    # Visibility / robots.txt
    "blog_public": "1",
    # robots_extra_rules: operator-added lines appended verbatim to the
    # storefront's /robots.txt (WordPress's "robots.txt" filter). The built-in
    # rules (allow/disallow and the sitemap line) are generated; this is the
    # escape hatch for a crawl rule that had no home — a shop blocking a
    # specific crawler, or adding a Crawl-delay. Read by the storefront
    # app/robots.txt route; empty means "only the generated rules".
    "robots_extra_rules": "",

    # `show_avatars` / `avatar_default` / `avatar_rating` were removed on
    # 2026-10-07 with the Gravatar feature (it keyed on email addresses).
    # Upload ceilings. Seeded to the values that used to be module constants,
    # so a fresh install and an upgraded one behave identically until an operator
    # changes them. Read per upload by MediaService.resolve_size_limit.
    # A new post starts in this category (by slug) and with this format. Both
    # were seeded and never read, so every post had to be categorised by hand.
    "default_category": "",
    "default_post_format": "standard",
    "media_max_file_size_mb": "10",
    "media_max_media_file_size_mb": "100",

    # Wallet module switches. Each wallet capability is independently
    # toggleable so an operator can disable one surface (say withdrawals, while
    # a bank integration is being sorted out) without touching the others. The
    # master ``wallet_enabled`` gates the module as a whole; when it is "0"
    # every wallet route below it refuses. Read at request time by
    # wallet.api.routes via SiteOptionsService — never cached, so a toggle takes
    # effect on the next request. Default "1": the store ships with a working
    # wallet. Enforced (not merely displayed) — see the route-level guards.
    "wallet_enabled": "1",
    # Gateway top-ups (charge the wallet through an online payment).
    "wallet_deposit_enabled": "1",
    # Customer withdrawal requests (submit → admin review → manual payout).
    "wallet_withdraw_enabled": "1",
    # Peer-to-peer wallet transfers between customers.
    "wallet_transfer_enabled": "1",
    # Admin balance adjustments (credit/debit a customer wallet from the panel).
    "wallet_admin_adjust_enabled": "1",

    # Storefront feature switches owned by the shopfeatures module (no dedicated
    # admin panel of their own). Same contract as the wallet switches above:
    # read at request time, never cached, enforced by a route guard AND mirrored
    # in the client so the entry points disappear rather than erroring.
    # Compare has no backend at all (localStorage only), so its switch purely
    # gates the storefront rendering.
    "wishlist_enabled": "1",
    "compare_enabled": "1",
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
