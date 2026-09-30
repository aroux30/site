"""RSS/Atom feed generation for blog posts (WordPress parity).

Generates standards-compliant RSS 2.0 and Atom 1.0 feeds for published blog
posts, served at /api/v1/blog/feed/{rss,atom}. Feeds exist for the whole blog
and for a single category or tag (/feed/rss/{slug}, /feed/atom/{slug}); every
item URL is shaped by the ``permalink_structure`` site option the same way
the storefront resolves paths, so a feed never advertises a dead link.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import NotFoundError
from app.modules.blog.domain.models import (
    BlogCategory,
    BlogPost,
    BlogPostStatus,
    BlogPostTag,
    BlogTag,
    PostVisibility,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ── Formatting helpers ───────────────────────────────────────────────────


def _rfc822(dt: datetime | None) -> str:
    """Format a datetime as RFC 822 (RSS pubDate)."""
    if dt is None:
        return ""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _iso8601(dt: datetime | None) -> str:
    """Format a datetime as ISO 8601 (Atom published/updated); now when None.

    Naive datetimes (possible from legacy rows or in-memory objects) are
    assumed to be UTC.
    """
    if dt is None:
        return datetime.now(UTC).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _escape_xml(text: str) -> str:
    """Escape text for an XML text node or attribute value.

    Feed bodies carry user content: an unescaped ampersand makes the whole
    document unparseable, and a bare "<" lets a comment author inject their
    own elements into the feed every reader consumes.
    """
    from xml.sax.saxutils import escape

    return escape(text or "", {'"': "&quot;", "'": "&apos;"})


def _cdata(text: str) -> str:
    """Wrap in CDATA to allow HTML in RSS content."""
    return f"<![CDATA[{text}]]>"


def _post_link(root: str, post: BlogPost, permalink_structure: str | None) -> str:
    """Public URL of one post, shaped by the permalink structure option.

    Falls back to the canonical file-tree path when no structure is given or
    the structure is the default one, so the feed never advertises a path the
    site would not resolve.
    """
    from app.shared.permalinks import PermalinkParts, build_post_path, is_default_structure

    if not permalink_structure or is_default_structure(permalink_structure):
        return f"{root}/blog/{xml_escape(post.slug)}"

    published = post.published_at or datetime.now(UTC)
    parts = PermalinkParts(
        postname=xml_escape(post.slug),
        post_id=str(post.id),
        year=f"{published.year:04d}",
        monthnum=f"{published.month:02d}",
        day=f"{published.day:02d}",
        category=xml_escape(post.category.slug) if post.category else "",
        author="",
    )
    return f"{root}{build_post_path(permalink_structure, parts)}"


def _feed_title(site_title: str, category: BlogCategory | None, tag: BlogTag | None) -> str:
    """Channel/feed title, suffixed with the term name when filtered."""
    if category is not None:
        return f"{site_title} — {category.name}"
    if tag is not None:
        return f"{site_title} — #{tag.name}"
    return site_title


# ── Post selection ───────────────────────────────────────────────────────


async def resolve_feed_term(
    db: AsyncSession,
    slug: str,
) -> tuple[str, BlogCategory | BlogTag]:
    """Resolve a term-feed slug to its object: category first, then tag.

    Returns ("category" | "tag", term). Raises NotFoundError when the slug
    matches neither — a feed must 404, never silently render an empty channel.
    """
    category = (
        await db.execute(select(BlogCategory).where(BlogCategory.slug == slug))
    ).scalar_one_or_none()
    if category is not None:
        return "category", category
    tag = (await db.execute(select(BlogTag).where(BlogTag.slug == slug))).scalar_one_or_none()
    if tag is not None:
        return "tag", tag
    raise NotFoundError("BlogCategory", f"No category or tag with slug '{slug}'")


def _feed_query(
    *,
    category_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    locale: str | None = None,
    limit: int = 20,
) -> Select:
    """SELECT for published posts, optionally scoped to a category/tag.

    Private posts are excluded outright (WordPress does the same — a feed is
    an anonymous channel and must never carry members-only content).
    Password-protected posts stay in the feed as-title-only; their bodies are
    masked in ``_feed_body``'s callers.
    """
    stmt = (
        select(BlogPost)
        .options(selectinload(BlogPost.category))
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            BlogPost.visibility != PostVisibility.PRIVATE,
        )
    )
    if category_id is not None:
        stmt = stmt.where(BlogPost.category_id == category_id)
    if tag_id is not None:
        stmt = stmt.join(BlogPostTag, BlogPostTag.post_id == BlogPost.id).where(
            BlogPostTag.tag_id == tag_id
        )
    if locale:
        stmt = stmt.where(BlogPost.locale == locale)
    return stmt.order_by(BlogPost.published_at.desc().nullslast()).limit(limit)


# WordPress's placeholder for protected posts in feeds/lists.
_PROTECTED_EXCERPT = "خلاصه‌ای برای این نوشته‌ی محافظت‌شده نمایش داده نمی‌شود."


def feed_excerpt(post: BlogPost) -> str:
    """Excerpt for one feed item: masked for protected posts, else authored."""
    if post.visibility == PostVisibility.PASSWORD:
        return _PROTECTED_EXCERPT
    return post.excerpt or ""


async def prepare_feed_posts(
    db: Any, posts: list[BlogPost], *, use_excerpt: bool = False
) -> None:
    """Resolve each post's feed body in place, before the sync builders run.

    Kept separate from the builders so ``build_rss_xml`` / ``build_atom_xml`` /
    ``build_comments_rss_xml`` stay pure string functions. Resolving here means
    one code path serves every feed format, so a fourth format cannot forget
    the step — which is how the raw ``[block slug=…]`` token reached readers.
    """
    for post in posts:
        post.feed_body = await feed_body(post, use_excerpt=use_excerpt, db=db)  # type: ignore[attr-defined]


def _prepared_body(post: BlogPost) -> str:
    """The body resolved by :func:`prepare_feed_posts`, or the raw content.

    The fallback keeps a builder usable on its own (a caller that never went
    through the preparation step still gets something, just unrendered).
    """
    return getattr(post, "feed_body", None) or post.content or ""


async def feed_body(post: BlogPost, *, use_excerpt: bool = False, db: Any = None) -> str:
    """Body for one feed item, in the shape the operator configured.

    Three things were wrong here and all three are WordPress-parity gaps:

    - **Password-protected posts** are withheld entirely. A password prompt
      cannot exist inside a feed reader, so no body is the only safe answer;
      the title and link still work.
    - **Reusable blocks and shortcodes were never resolved.** Storage keeps
      the authored tokens, display resolves them, and the feed is display — so
      a post containing ``[block slug="x"]`` published the literal token to
      every subscriber. A ``[gallery]`` in a feed body was a bare marker.
    - **``rss_use_excerpt`` was seeded and read by nothing**, so a site that
      asked for excerpts in its feed always got full bodies.
    """
    if post.visibility == PostVisibility.PASSWORD:
        return ""
    if use_excerpt:
        return feed_excerpt(post)
    if db is not None:
        from app.modules.blog.application.blog_service import BlogService

        return await BlogService(db)._render_content(post.content or "")
    return post.content or ""


async def _fetch_feed_posts(
    db: AsyncSession,
    *,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    locale: str | None = None,
    limit: int = 20,
) -> tuple[BlogCategory | None, BlogTag | None, list[BlogPost]]:
    """Resolve the slug filters, then fetch that scope's published posts."""
    category: BlogCategory | None = None
    tag: BlogTag | None = None
    if category_slug:
        category = (
            await db.execute(select(BlogCategory).where(BlogCategory.slug == category_slug))
        ).scalar_one_or_none()
        if category is None:
            raise NotFoundError("BlogCategory", f"Category '{category_slug}' not found")
    if tag_slug:
        tag = (
            await db.execute(select(BlogTag).where(BlogTag.slug == tag_slug))
        ).scalar_one_or_none()
        if tag is None:
            raise NotFoundError("BlogTag", f"Tag '{tag_slug}' not found")

    stmt = _feed_query(
        category_id=category.id if category else None,
        tag_id=tag.id if tag else None,
        locale=locale,
        limit=limit,
    )
    posts = (await db.execute(stmt)).scalars().unique().all()
    return category, tag, list(posts)


# ── RSS 2.0 ──────────────────────────────────────────────────────────────


def build_rss_xml(
    posts: list[BlogPost],
    *,
    base_url: str = "https://example.com",
    site_title: str = "وبلاگ",
    site_description: str = "آخرین مطالب وبلاگ",
    permalink_structure: str | None = None,
    category: BlogCategory | None = None,
    tag: BlogTag | None = None,
    feed_path: str = "/blog/feed/rss",
) -> str:
    """Render an RSS 2.0 channel for the given posts (pure string building)."""
    root = base_url.rstrip("/")
    now = _rfc822(datetime.now(UTC))

    items: list[str] = []
    for post in posts:
        post_url = _post_link(root, post, permalink_structure)
        category_xml = ""
        if post.category:
            category_xml = f"      <category>{xml_escape(post.category.name)}</category>"

        item = f"""    <item>
      <title>{xml_escape(post.title)}</title>
      <link>{post_url}</link>
      <guid isPermaLink="true">{post_url}</guid>
      <pubDate>{_rfc822(post.published_at)}</pubDate>
      <description>{xml_escape(feed_excerpt(post))}</description>
      <content:encoded>{_cdata(_prepared_body(post))}</content:encoded>
{category_xml}
    </item>"""
        items.append(item)

    feed_url = f"{root}{feed_path}"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{xml_escape(_feed_title(site_title, category, tag))}</title>
    <link>{root}/blog</link>
    <description>{xml_escape(site_description)}</description>
    <language>fa</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{feed_url}" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>"""


async def generate_rss_feed(
    db: AsyncSession,
    *,
    base_url: str = "https://example.com",
    site_title: str = "وبلاگ",
    site_description: str = "آخرین مطالب وبلاگ",
    limit: int = 20,
    locale: str | None = None,
    permalink_structure: str | None = None,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    use_excerpt: bool = False,
) -> str:
    """Generate an RSS 2.0 XML feed of published blog posts.

    ``permalink_structure`` (the ``permalink_structure`` site option) shapes
    each item's URL the same way the storefront does — a feed must never
    advertise paths the site does not actually resolve. ``category_slug`` /
    ``tag_slug`` scope the channel to one term and 404 (NotFoundError) when
    the slug is unknown.
    """
    category, tag, posts = await _fetch_feed_posts(
        db,
        category_slug=category_slug,
        tag_slug=tag_slug,
        locale=locale,
        limit=limit,
    )
    await prepare_feed_posts(db, posts, use_excerpt=use_excerpt)
    return build_rss_xml(
        posts,
        base_url=base_url,
        site_title=site_title,
        site_description=site_description,
        permalink_structure=permalink_structure,
        category=category,
        tag=tag,
    )


# ── Atom 1.0 ─────────────────────────────────────────────────────────────


def build_atom_xml(
    posts: list[BlogPost],
    *,
    base_url: str = "https://example.com",
    site_title: str = "وبلاگ",
    site_description: str = "آخرین مطالب وبلاگ",
    permalink_structure: str | None = None,
    category: BlogCategory | None = None,
    tag: BlogTag | None = None,
    feed_path: str = "/blog/feed/atom",
) -> str:
    """Render an Atom 1.0 feed for the given posts (pure string building).

    Correct namespaced XML with a self link, feed-level ``updated``, and per-
    entry ``content type="html"`` (escaped markup, as Atom requires).
    """
    root = base_url.rstrip("/")
    feed_url = f"{root}{feed_path}"
    alternate_url = f"{root}/blog"

    entries: list[str] = []
    updated_values: list[str] = []
    for post in posts:
        post_url = _post_link(root, post, permalink_structure)
        published = post.published_at or post.created_at
        updated = post.updated_at or post.published_at or post.created_at
        entry_updated = _iso8601(updated)
        updated_values.append(entry_updated)
        category_xml = ""
        if post.category:
            category_xml = (
                f'    <category term="{xml_escape(post.category.slug)}"'
                f' label="{xml_escape(post.category.name)}"/>'
            )

        entry = f"""  <entry>
    <id>{post_url}</id>
    <title>{xml_escape(post.title)}</title>
    <link rel="alternate" type="text/html" href="{post_url}"/>
    <published>{_iso8601(published)}</published>
    <updated>{entry_updated}</updated>
    <summary>{xml_escape(feed_excerpt(post))}</summary>
    <content type="html">{xml_escape(_prepared_body(post))}</content>
{category_xml}
  </entry>"""
        entries.append(entry)

    # Feed-level updated: newest entry, or "now" for an empty feed (the
    # element is mandatory in Atom).
    feed_updated = max(updated_values) if updated_values else _iso8601(None)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fa">
  <title>{xml_escape(_feed_title(site_title, category, tag))}</title>
  <subtitle>{xml_escape(site_description)}</subtitle>
  <id>{feed_url}</id>
  <link rel="alternate" type="text/html" href="{alternate_url}"/>
  <link rel="self" type="application/atom+xml" href="{feed_url}"/>
  <updated>{feed_updated}</updated>
  <generator uri="{root}">Iranian E-Commerce Blog</generator>
{chr(10).join(entries)}
</feed>"""


async def generate_atom_feed(
    db: AsyncSession,
    *,
    base_url: str = "https://example.com",
    site_title: str = "وبلاگ",
    site_description: str = "آخرین مطالب وبلاگ",
    limit: int = 20,
    locale: str | None = None,
    permalink_structure: str | None = None,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    use_excerpt: bool = False,
) -> str:
    """Generate an Atom 1.0 XML feed of published blog posts.

    Same scope/permalink rules as :func:`generate_rss_feed`; the channel is
    scoped to a category or tag via ``category_slug``/``tag_slug``.
    """
    category, tag, posts = await _fetch_feed_posts(
        db,
        category_slug=category_slug,
        tag_slug=tag_slug,
        locale=locale,
        limit=limit,
    )
    await prepare_feed_posts(db, posts, use_excerpt=use_excerpt)
    return build_atom_xml(
        posts,
        base_url=base_url,
        site_title=site_title,
        site_description=site_description,
        permalink_structure=permalink_structure,
        category=category,
        tag=tag,
    )


async def generate_term_feed(
    db: AsyncSession,
    *,
    slug: str,
    fmt: str = "rss",
    base_url: str = "https://example.com",
    site_title: str = "وبلاگ",
    site_description: str = "آخرین مطالب وبلاگ",
    limit: int = 20,
    permalink_structure: str | None = None,
) -> str:
    """RSS or Atom feed for one category-or-tag slug (auto-resolved).

    ``fmt`` selects the syndication format ("rss" | "atom"); the slug is
    looked up as a category first, then a tag, and 404s when neither matches.
    """
    kind, term = await resolve_feed_term(db, slug)
    _, _, posts = await _fetch_feed_posts(
        db,
        category_slug=slug if kind == "category" else None,
        tag_slug=slug if kind == "tag" else None,
        limit=limit,
    )
    feed_path = f"/api/v1/blog/feed/{fmt}/{slug}"
    builder = build_atom_xml if fmt == "atom" else build_rss_xml
    return builder(
        posts,
        base_url=base_url,
        site_title=site_title,
        site_description=site_description,
        permalink_structure=permalink_structure,
        category=term if kind == "category" else None,
        tag=term if kind == "tag" else None,
        feed_path=feed_path,
    )


# ── RSS 2.0 for comments (WordPress feed-comments parity) ──────────────────


def build_comments_rss_xml(
    comments: list[Any],
    *,
    base_url: str = "https://example.com",
    title: str = "دیدگاه‌های تازه",
    link: str = "/",
    self_path: str = "/api/v1/blog/feed/comments/rss",
    with_comments: bool = True,
) -> str:
    """Recent-comments feed, RSS 2.0.

    WordPress serves this at /feed/ and readers use it to watch a discussion.
    The post permalink is included on every item so a reader can jump to the
    comment's context, which is the whole point of the format.
    """
    items: list[str] = []
    for c in comments:
        # A comment is polymorphic (blog post or CMS page); only the blog half
        # has a permalink worth linking to.
        post = getattr(c, "post", None)
        post_url = ""
        if post is not None and getattr(post, "slug", None):
            post_url = f"{base_url}/blog/{post.slug}#comment-{getattr(c, 'id', '')}"
        elif getattr(c, "resource_type", "blog_post") == "blog_post":
            post_url = f"{base_url}/blog/"

        author = getattr(c, "author_name", None) or "مهمان"
        content = getattr(c, "content", "") or ""
        excerpt = content if len(content) <= 300 else content[:300] + "…"
        items.append(
            f"<item>\n"
            f"  <title>{_escape_xml(author)}</title>\n"
            f"  <link>{_escape_xml(post_url or link)}</link>\n"
            f"  <guid isPermaLink=\"false\">{getattr(c, 'id', '')}</guid>\n"
            f"  <pubDate>{_rfc822(getattr(c, 'created_at', None))}</pubDate>\n"
            f"  <description>{_escape_xml(excerpt)}</description>\n"
            + (
                f"  <comments>{_escape_xml(post_url)}#comments</comments>\n"
                if post_url
                else ""
            )
            + f"</item>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:wfw="http://wellformedweb.org/CommentAPI/">\n'
        "<channel>\n"
        f"  <title>{_escape_xml(title)}</title>\n"
        f"  <link>{_escape_xml(base_url + link)}</link>\n"
        f'  <atom:link href="{_escape_xml(base_url + self_path)}" rel="self" '
        'type="application/rss+xml"/>\n'
        f"  <description>{_escape_xml(title)}</description>\n"
        f"  <language>fa</language>\n"
        f"  <lastBuildDate>{_rfc822(datetime.now(UTC))}</lastBuildDate>\n"
        f"  {'<wfw:commentRss>' + _escape_xml(base_url + self_path) + '</wfw:commentRss>' if with_comments else ''}\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>"
    )


async def generate_comments_feed(
    db: AsyncSession,
    *,
    post_id: uuid.UUID | None = None,
    limit: int = 20,
) -> tuple[list[Any], str, str]:
    """Fetch recent approved comments and the (title, link) they belong under."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.modules.blog.domain.models import BlogComment, CommentStatus

    # selectinload, not lazy: the builder reads comment.post, and a lazy load
    # inside an async context raises MissingGreenlet rather than returning.
    stmt = (
        select(BlogComment)
        .options(selectinload(BlogComment.post))
        .where(BlogComment.status == CommentStatus.APPROVED)
        .order_by(BlogComment.created_at.desc())
        .limit(limit)
    )
    if post_id is not None:
        stmt = (
            select(BlogComment)
            .options(selectinload(BlogComment.post))
            .where(
                BlogComment.post_id == post_id,
                BlogComment.status == CommentStatus.APPROVED,
            )
            .order_by(BlogComment.created_at.desc())
            .limit(limit)
        )
    comments = list((await db.execute(stmt)).scalars().unique().all())

    title, link = "دیدگاه‌های تازه", "/blog"
    if post_id is not None:
        post = await db.get(BlogPost, post_id)
        if post is None:
            raise NotFoundError("BlogPost", f"Blog post '{post_id}' not found")
        title, link = f"دیدگاه‌های «{post.title}»", f"/blog/{post.slug}"
    return comments, title, link


# ── RDF 1.0 (WordPress feed-rdf parity) ───────────────────────────────────


def build_rdf_xml(
    posts: list[BlogPost],
    *,
    base_url: str = "https://example.com",
    title: str = "فروشگاه",
    description: str = "",
    link: str = "/",
    self_path: str = "/api/v1/blog/feed/rdf",
) -> str:
    """RDF 1.0 feed (RSS 1.0).

    WordPress still emits this for readers that predate RSS 2.0. The item
    titles live in dc:title because RDF carries the title as an element, not as
    a channel field — getting that wrong yields a feed readers reject.
    """
    root = f"{base_url}{link}"
    items: list[str] = []
    for p in posts:
        url = _post_link(base_url, p, None)
        about = f"{root}#{p.id}"
        items.append(
            "<item rdf:about=\"%s\">\n"
            "  <title>%s</title>\n"
            "  <link>%s</link>\n"
            "  <description>%s</description>\n"
            "  <dc:date>%s</dc:date>\n"
            "  <dc:creator>%s</dc:creator>\n"
            "</item>"
            % (
                _escape_xml(url),
                _escape_xml(p.title),
                _escape_xml(url),
                _escape_xml(p.excerpt or ""),
                _rfc822(p.published_at or p.created_at),
                _escape_xml(""),
            )
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns="http://purl.org/rss/1.0/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel rdf:about="%s">\n'
        "    <title>%s</title>\n"
        "    <link>%s</link>\n"
        "    <description>%s</description>\n"
        '    <items>\n      <rdf:Seq>\n%s\n      </rdf:Seq>\n    </items>\n'
        "  </channel>\n"
        "%s"
        "</rdf:RDF>"
        % (
            _escape_xml(base_url + self_path),
            _escape_xml(title),
            _escape_xml(root),
            _escape_xml(description or title),
            "\n".join("        <rdf:li rdf:resource=\"%s\"/>" % _escape_xml(_post_link(base_url, p, None)) for p in posts),
            "\n".join(items),
        )
    )
