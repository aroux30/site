"""Where a media file is referenced from, so it can be counted before deletion.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "مدیا: هشدار استفاده پیش
از حذف". Deleting an asset removed the row and the bytes immediately, with
nothing telling the admin the image was the cover of a published post or the
logo of a vendor.

Media is referenced by URL, not by id, so the count has to be a search across
every column that can hold one. The list below came from querying
information_schema, not from a model's memory — several of these columns
(``custom_post_entries.cover_image_url``, ``brands.logo_url``,
``seo_metadata.og_image``) are exactly the ones a hand-written list misses.

Counting is deliberately best-effort per column: a missing table or column is
skipped rather than raised, so a schema that grew a new column degrades the
count instead of 500-ing the delete.

That skip has to roll the savepoint back as well. Catching the exception is not
enough on Postgres: once a statement inside a transaction fails, every later
statement in the same transaction fails with InFailedSQLTransactionError until
someone ends or rolls it back. So the first version of this counted a column
that did not exist, caught the error, and then poisoned the caller's
transaction — the delete it was meant to protect died of an unrelated-looking
error. Every probe therefore runs in its own SAVEPOINT and unwinds it on
failure, which is what makes "skip it" actually mean skip it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# (table, column, label shown to the admin). Tables whose names change across
# modules are resolved lazily; a miss is reported as "unknown", never invented.
REFERENCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("blog_posts", "cover_image_url"),
    ("blog_post_revisions", "cover_image_url"),
    ("custom_post_entries", "cover_image_url"),
    ("categories", "image_url"),
    ("brands", "logo_url"),
    ("vendors", "logo_url"),
    ("vendors", "banner_url"),
    ("user_profiles", "avatar_url"),
    ("seo_metadata", "og_image"),
    ("attachments", "file_url"),
    ("ticket_attachments", "file_url"),
    ("card_transfer_receipts", "receipt_image_url"),
    ("shipments", "label_url"),
    ("product_images", "url"),
    # The storefront's main consumer. This one matters most and was missing
    # first time round: a peer session measured 20 product_images rows
    # pointing at the single asset in the database, and the counter reported
    # zero — so the delete warning said "used nowhere" about the one image
    # every product was using. check_media_usage_coverage.py now diffs this
    # list against information_schema so a new image column cannot be added
    # without the guard noticing.
    # CMS page covers were missing the same way: a page's hero image is
    # referenced only from this column, so deleting the file broke the page with
    # no warning at all.
    ("cms_pages", "cover_image_url"),
)

# Free-text columns: an image inside a body is a substring, not an equality.
# ``custom_post_entries`` stores its body under a different name, so it is not
# listed here; see find_media_reference_columns.py for the live list.
HTML_COLUMNS: tuple[tuple[str, str], ...] = (
    ("blog_posts", "content"),
    ("cms_pages", "body_html"),
    ("cms_page_revisions", "body_html"),
)

# The file name is what appears in an <img src>, so the substring test is on the
# name rather than the full URL: a body may store an absolute or a relative URL,
# and both contain the file name.
DELETED_ROW_PREDICATE = "{table}.{col} IS NOT NULL AND {table}.{col} <> ''"


async def _safe_count(db: AsyncSession, sql: object, params: dict) -> int:
    """Run one probe inside a savepoint; return 0 if it cannot be run.

    The savepoint is the point. Postgres keeps a transaction aborted after any
    failed statement, so a caught exception without a rollback leaves the
    caller unable to run anything else — the warning endpoint would then break
    the delete it exists to protect.
    """
    try:
        async with db.begin_nested():
            return int((await db.execute(sql, params)).scalar() or 0)
    except Exception:  # noqa: BLE001 - a column that vanished must not block a delete
        # begin_nested already rolled the savepoint back; the outer transaction
        # is usable again, which is the whole reason for using it.
        return 0


# (MediaUsage attribute, Persian label). One table, used by both ``total`` and
# ``summary``, so the number and the sentence cannot disagree about which
# buckets exist.
BUCKET_LABELS: tuple[tuple[str, str], ...] = (
    ("posts", "نوشته"),
    ("pages", "برگه"),
    ("products", "تصویر محصول"),
    ("custom_entries", "ورودی سفارشی"),
    ("categories", "دسته‌بندی"),
    ("brands", "برند"),
    ("vendors", "فروشنده"),
    ("user_profiles", "پروفایل کاربر"),
    ("seo_metadata", "متای سئو"),
    ("documents", "سند"),
    ("logistics", "ارسال"),
    ("in_html", "متن محتوا"),
)


@dataclass
class MediaUsage:
    """Where one asset is used, grouped by the thing that uses it."""

    posts: int = 0
    pages: int = 0
    custom_entries: int = 0
    categories: int = 0
    brands: int = 0
    vendors: int = 0
    user_profiles: int = 0
    seo_metadata: int = 0
    documents: int = 0
    logistics: int = 0
    products: int = 0
    in_html: int = 0
    unknown: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        # Summed by name over the int fields rather than spelled out, because a
        # hand-written list is how ``products`` ended up counted at 20 while
        # total said 0 — the guard saw a number and the delete warning did not.
        return sum(
            v for v in vars(self).values() if isinstance(v, int) and not isinstance(v, bool)
        )

    def summary(self) -> str:
        """One line for the confirmation dialog, in the admin's language.

        Reads the same labels ``total`` sums over, from one table, so the line
        and the number can never disagree about which buckets exist.
        """
        parts = [
            "%s: %d" % (label, getattr(self, attr))
            for attr, label in BUCKET_LABELS
            if getattr(self, attr)
        ]
        return "، ".join(parts) if parts else "هیچ‌جا استفاده نشده"


def _bucket_for(table: str) -> str:
    if table == "blog_posts":
        return "posts"
    if table == "cms_pages":
        # A page cover, not a post cover. The bucket and the Persian label both
        # already existed and were never wired to a column, so the number was
        # reported as an unknown reference — indistinguishable, to whoever reads
        # the warning, from a table that should not have been counted at all.
        return "pages"
    if table == "blog_post_revisions":
        # A revision is a historical copy, not a live use: an old revision must
        # not stop an editor from cleaning up the library. Counted separately so
        # it can be reported as non-blocking.
        return "unknown"
    if table == "custom_post_entries":
        return "custom_entries"
    if table == "categories":
        return "categories"
    if table == "brands":
        return "brands"
    if table == "vendors":
        return "vendors"
    if table == "user_profiles":
        return "user_profiles"
    if table == "seo_metadata":
        return "seo_metadata"
    if table in ("attachments", "ticket_attachments", "card_transfer_receipts"):
        return "documents"
    if table == "shipments":
        return "logistics"
    if table == "product_images":
        return "products"
    return "unknown"


async def count_media_usage(db: AsyncSession, file_name: str) -> MediaUsage:
    """Count the live references to one file.

    ``file_name`` rather than the id, because references are stored as URLs
    and the URL is what embeds the name. Exact-column matches are counted with
    an equality on either the full URL's tail or the bare name, so both a stored
    absolute URL and a stored bare name are found.
    """
    usage = MediaUsage()
    needle = file_name

    # Exact-column matches: equality on the bare name, plus a LIKE on the URL
    # tail and body, so a stored absolute URL, a relative one and a bare name
    # are all found. Each probe is savepointed, so a column that no longer
    # exists is skipped without poisoning the caller's transaction.
    for table, column in REFERENCE_COLUMNS:
        sql = text(
            "SELECT count(*) FROM {t} WHERE {c} = :exact "
            "OR {c} LIKE :suffix OR {c} LIKE :contains".format(t=table, c=column)
        )
        count = await _safe_count(
            db,
            sql,
            {"exact": needle, "suffix": "%/" + needle, "contains": "%" + needle + "%"},
        )
        if not count:
            continue
        bucket = _bucket_for(table)
        if bucket == "unknown":
            usage.unknown.append("%s.%s" % (table, column))
        else:
            setattr(usage, bucket, getattr(usage, bucket) + count)

    for table, column in HTML_COLUMNS:
        sql = text(
            "SELECT count(*) FROM {t} WHERE {c} ILIKE :needle".format(t=table, c=column)
        )
        found = await _safe_count(db, sql, {"needle": "%" + needle + "%"})
        if not found:
            continue
        # A CMS page only ever mentions an image inside its body, so a hit here
        # is a page using the file rather than a post whose body does.
        if table.startswith("cms_page"):
            usage.pages += found
        elif table == "blog_posts":
            usage.in_html += found
        else:
            usage.in_html += found

    return usage
