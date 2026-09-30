"""Shortcode processor for blog/CMS content (WordPress parity).

Supports a registry of shortcode handlers that transform bracket-delimited
tags in post HTML into rendered output:

    [gallery ids="1,2,3" columns="3"]
    [youtube url="https://youtube.com/watch?v=xxx"]
    [embed url="..."]
    [button text="Click" link="/products"]

Usage:
    from app.shared.content.shortcodes import process_shortcodes
    rendered_html = process_shortcodes(raw_html)

Handlers are registered via the @shortcode decorator:

    @shortcode("gallery")
    def render_gallery(attrs: dict[str, str], content: str) -> str:
        ...
"""

from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING, Callable

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Type for shortcode handler: (attrs, inner_content) -> rendered HTML
ShortcodeHandler = Callable[[dict[str, str], str], str]

# An async handler additionally receives the session, for shortcodes that must
# read the database to render — the gallery resolves asset ids to file URLs.
AsyncShortcodeHandler = Callable[[dict[str, str], str, "AsyncSession"], "Awaitable[str]"]

# Registry of shortcode name -> handler
_HANDLERS: dict[str, ShortcodeHandler | AsyncShortcodeHandler] = {}

# Matches [tag attr="val" ...] or [tag attr="val"]content[/tag]
_SHORTCODE_RE = re.compile(
    r"\[(\w+)"              # opening tag name
    r"((?:\s+\w+="          # attributes start
    r'(?:"[^"]*"|'          # double-quoted value
    r"'[^']*'|"             # single-quoted value
    r"[^\s\]]+))*)"         # unquoted value
    r"\s*\]"                # closing bracket
    r"(?:(.*?)\[/\1\])?"    # optional inner content + closing tag
    , re.DOTALL
)

_ATTR_RE = re.compile(r'(\w+)=["\']([^"\']*)["\']')


def shortcode(name: str) -> Callable[[ShortcodeHandler], ShortcodeHandler]:
    """Decorator to register a shortcode handler."""
    def decorator(fn: ShortcodeHandler) -> ShortcodeHandler:
        _HANDLERS[name] = fn
        return fn
    return decorator


def _parse_attrs(attr_string: str) -> dict[str, str]:
    """Parse shortcode attributes into a dict."""
    return dict(_ATTR_RE.findall(attr_string))


def process_shortcodes(html: str) -> str:
    """Process all registered shortcodes in the given HTML string.

    Synchronous path: async handlers are left untouched (their token stays in
    the output) so this stays usable from non-async callers.
    """
    def _replace(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        attrs_raw = match.group(2) or ""
        inner = match.group(3) or ""

        handler = _HANDLERS.get(tag_name)
        if handler is None or _is_async_handler(handler):
            return match.group(0)  # leave unknown shortcodes unchanged

        attrs = _parse_attrs(attrs_raw)
        try:
            return handler(attrs, inner)  # type: ignore[arg-type,return-value]
        except Exception:
            logger.warning("shortcode_render_failed", tag=tag_name, attrs=attrs)
            return match.group(0)

    return _SHORTCODE_RE.sub(_replace, html)


def _is_async_handler(handler: ShortcodeHandler | AsyncShortcodeHandler) -> bool:
    """True when a handler needs a session and must be awaited."""
    return inspect.iscoroutinefunction(handler)


async def process_shortcodes_async(db: AsyncSession, html: str) -> str:
    """Process shortcodes with database access for async handlers.

    Sync handlers run exactly as in :func:`process_shortcodes`; async ones get
    the session. A handler that raises leaves its own token in place rather
    than emptying the body, so one bad shortcode cannot delete a post's text.
    """
    patterns: list[tuple[re.Match[str], str, dict[str, str], str]] = []

    def _collect(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        handler = _HANDLERS.get(tag_name)
        if handler is None:
            return match.group(0)
        attrs = _parse_attrs(match.group(2) or "")
        inner = match.group(3) or ""
        patterns.append((match, tag_name, attrs, inner))
        return match.group(0)  # placeholder, substituted below

    staged = _SHORTCODE_RE.sub(_collect, html)

    # Rewrite from the end so each earlier span keeps its original offsets.
    for match, tag_name, attrs, inner in reversed(patterns):
        handler = _HANDLERS.get(tag_name)
        if handler is None:
            continue
        rendered = None
        try:
            if _is_async_handler(handler):
                rendered = await handler(attrs, inner, db)  # type: ignore[arg-type,misc]
            else:
                rendered = handler(attrs, inner)  # type: ignore[arg-type]
        except Exception:
            logger.warning("shortcode_render_failed", tag=tag_name, attrs=attrs)
            continue
        if not isinstance(rendered, str):
            continue
        start, end = match.span()
        staged = staged[:start] + rendered + staged[end:]

    return staged


# ============================================================================
# Built-in Shortcodes
# ============================================================================


@shortcode("youtube")
def _render_youtube(attrs: dict[str, str], content: str) -> str:
    """Render a YouTube embed: [youtube url="..." width="560" height="315"]"""
    url = attrs.get("url", content.strip())
    if not url:
        return ""
    width = attrs.get("width", "560")
    height = attrs.get("height", "315")
    # Extract video ID
    video_id = ""
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0]
    elif "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    if not video_id:
        return f'<a href="{url}">{url}</a>'
    return (
        f'<iframe width="{width}" height="{height}" '
        f'src="https://www.youtube.com/embed/{video_id}" '
        f'frameborder="0" allowfullscreen loading="lazy"></iframe>'
    )


@shortcode("aparat")
def _render_aparat(attrs: dict[str, str], content: str) -> str:
    """Render an Aparat embed: [aparat id="xxxxx"]"""
    video_id = attrs.get("id", content.strip())
    if not video_id:
        return ""
    return (
        f'<iframe src="https://www.aparat.com/video/video/embed/videohash/{video_id}/vt/frame" '
        f'allowfullscreen="true" style="width:100%;aspect-ratio:16/9;border:0" loading="lazy"></iframe>'
    )


@shortcode("button")
def _render_button(attrs: dict[str, str], content: str) -> str:
    """Render a button: [button text="Click" link="/page" color="blue"]"""
    text = attrs.get("text", content.strip() or "Click")
    link = attrs.get("link", "#")
    color = attrs.get("color", "blue")
    return (
        f'<a href="{link}" class="shortcode-button shortcode-button--{color}" '
        f'style="display:inline-block;padding:8px 16px;border-radius:6px;'
        f'text-decoration:none;color:#fff;background:{color}">{text}</a>'
    )


@shortcode("alert")
def _render_alert(attrs: dict[str, str], content: str) -> str:
    """Render an alert box: [alert type="warning"]Message[/alert]"""
    alert_type = attrs.get("type", "info")
    colors = {
        "info": "#e3f2fd", "success": "#e8f5e9",
        "warning": "#fff3e0", "error": "#fbe9e7",
    }
    bg = colors.get(alert_type, colors["info"])
    return (
        f'<div class="shortcode-alert shortcode-alert--{alert_type}" '
        f'style="padding:12px 16px;border-radius:6px;margin:8px 0;background:{bg}">'
        f'{content}</div>'
    )


@shortcode("gallery")
async def _render_gallery(attrs: dict[str, str], content: str, db: AsyncSession) -> str:
    """Render a gallery grid: [gallery ids="id1,id2,id3" columns="3"]

    Resolves each id to the asset's stored ``file_url``. The shortcode used to
    build ``/api/v1/media/{id}/file``, a path no route serves, so every gallery
    image 404'd; assets are served from ``/uploads/...`` and may additionally
    carry a CDN prefix, which is why the URL is read from the row rather than
    reconstructed here.
    """
    import uuid as _uuid
    from html import escape

    from app.modules.media.domain.models import MediaAsset
    from app.modules.media.application.public_url import (
        build_asset_url,
        resolve_cdn_base_url,
    )
    from sqlalchemy import select

    raw_ids = [i.strip() for i in attrs.get("ids", "").split(",") if i.strip()]
    if not raw_ids:
        return ""
    # A stored id is operator-authored text: skip anything that is not a UUID
    # rather than letting it reach the query, and de-duplicate while preserving
    # the authored order.
    ids: list[_uuid.UUID] = []
    seen: set[_uuid.UUID] = set()
    for raw in raw_ids:
        try:
            parsed = _uuid.UUID(raw)
        except (ValueError, AttributeError, TypeError):
            continue
        if parsed not in seen:
            seen.add(parsed)
            ids.append(parsed)
    if not ids:
        return ""

    rows = (
        (
            await db.execute(
                select(MediaAsset.id, MediaAsset.file_url, MediaAsset.alt_text).where(
                    MediaAsset.id.in_(ids)
                )
            )
        )
        .all()
    )
    by_id = {row[0]: (row[1] or "", row[2] or "") for row in rows}
    cdn_base = await resolve_cdn_base_url(db)

    # Authored order, not database order: SELECT ... IN () gives no guarantee.
    items: list[str] = []
    for asset_id in ids:
        file_url, alt_text = by_id.get(asset_id, ("", ""))
        if not file_url:
            continue
        src = escape(build_asset_url(file_url, cdn_base), quote=True)
        alt = escape(alt_text, quote=True)
        items.append(
            f'<div class="shortcode-gallery__item" '
            f'style="flex:0 0 calc(100%/{attrs.get("columns", "3")} - 8px)">'
            f'<img src="{src}" alt="{alt}" loading="lazy" '
            f'style="width:100%;border-radius:4px"/></div>'
        )
    if not items:
        return ""
    return (
        f'<div class="shortcode-gallery" '
        f'style="display:flex;flex-wrap:wrap;gap:8px">{"".join(items)}</div>'
    )


@shortcode("embed")
def _render_embed(attrs: dict[str, str], content: str) -> str:
    """Generic embed: [embed url="..."]"""
    url = attrs.get("url", content.strip())
    if not url:
        return ""
    return (
        f'<iframe src="{url}" style="width:100%;aspect-ratio:16/9;border:0" '
        f'allowfullscreen loading="lazy"></iframe>'
    )
