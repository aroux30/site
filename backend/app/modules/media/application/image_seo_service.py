"""Image SEO — fill alt/title/caption from the file name at upload time.

Rank Math's Image SEO module rewrites missing ``alt``/``title`` attributes at
render time because WordPress stores nothing on the attachment by default.
This store is the opposite: the media row *is* the store of record for alt,
title, caption and description, and the storefront renders from it. So the
equivalent feature lives where the row is written — ``MediaService.upload_file``
and ``sideload_image`` — and every consumer (storefront, admin library, RSS,
sitemaps) sees the filled value without each having to remember a fallback.

What is filled, and when (all gated by site options, seeded in
``default_options.py``):

- ``alt_text`` ← cleaned file name, when empty (on by default — an image
  without alt is invisible to image search and a WCAG failure).
- ``title`` ← cleaned file name, when empty (on by default).
- ``caption`` / ``description`` ← cleaned file name, when empty (off by
  default; a visible caption is a layout decision).
- Case conversion ("none"/"lower"/"upper") and ``from``→``to`` replacements
  apply to the *generated* text only. Operator-typed text is never touched —
  rewriting what a person wrote is how a "helpful" feature becomes a bug.

The cleaner is deliberately conservative: strip the extension, turn separators
into spaces, drop a trailing size suffix (``-300x200``), collapse whitespace,
and strip a leading UUID-ish token (the upload pipeline stores hex names).
A generated alt of "img 2 final 3" helps nobody, so a name that cleans to
fewer than two characters is treated as absent and nothing is filled.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: WordPress appends -WIDTHxHEIGHT to derivative names; an operator uploading
#: "photo-1024x768.jpg" means "photo", not the size suffix.
_SIZE_SUFFIX = re.compile(r"-\d{2,4}x\d{2,4}$")

#: A leading hex/UUID token (the upload pipeline's disk names) carries no
#: meaning as text: "a1b2c3d4e5f6-my-photo" → "my photo".
_LEADING_TOKEN = re.compile(r"^[0-9a-f]{8,}(?:-[0-9a-f]{4,})*[-_ ]*", re.IGNORECASE)

#: Collapse runs of whitespace after separator conversion.
_WHITESPACE = re.compile(r"\s+")

DEFAULT_SEPARATORS = "-_"


def clean_filename_for_seo(filename: str, separators: str = DEFAULT_SEPARATORS) -> str:
    """Turn a file name into human text, or "" when nothing useful remains.

    Pure and deterministic so the tests can pin every rule; the caller decides
    what an empty result means (nothing gets filled).
    """
    name = filename.strip()
    # Strip a path if one slipped through (defensive: uploads sanitize first).
    name = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    # Remove the extension — only the last dot, so "v1.2-final.jpg" keeps "v1.2".
    if "." in name:
        name = name.rsplit(".", 1)[0]
    name = _SIZE_SUFFIX.sub("", name)
    name = _LEADING_TOKEN.sub("", name)

    # Separators → spaces. A character class built from the operator's set; an
    # empty set means "no conversion" rather than "every character matches".
    if separators:
        name = re.sub(f"[{re.escape(separators)}]+", " ", name)
    name = _WHITESPACE.sub(" ", name).strip()

    # A one-character result ("a", "1") is noise, not a description.
    if len(name) < 2:
        return ""
    return name


def apply_case(text: str, case: str) -> str:
    """Apply the operator's case setting to generated text only."""
    if case == "lower":
        return text.lower()
    if case == "upper":
        return text.upper()
    return text


def apply_replacements(text: str, replacements: list[dict[str, str]]) -> str:
    """Apply from→to replacements in order; malformed pairs are skipped."""
    for pair in replacements:
        if not isinstance(pair, dict):
            continue
        src = str(pair.get("from") or "")
        dst = str(pair.get("to") or "")
        if src:
            text = text.replace(src, dst)
    return text


class _Options:
    """Resolved Image SEO settings — one read per upload, not per field."""

    def __init__(
        self,
        *,
        auto_alt: bool,
        auto_title: bool,
        auto_caption: bool,
        auto_description: bool,
        case: str,
        separators: str,
        replacements: list[dict[str, str]],
    ) -> None:
        self.auto_alt = auto_alt
        self.auto_title = auto_title
        self.auto_caption = auto_caption
        self.auto_description = auto_description
        self.case = case
        self.separators = separators
        self.replacements = replacements


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value not in ("0", "false", "False", "no")


def _parse_replacements(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("image_seo_replacements_unparseable")
        return []
    if not isinstance(parsed, list):
        return []
    return [p for p in parsed if isinstance(p, dict)]


async def load_settings(db: AsyncSession) -> _Options:
    """Read every Image SEO option once; defaults match the seed rows.

    Site options are read from Postgres with no cache layer (documented in
    ``site_options_service``), so this is one query per option — acceptable at
    upload frequency, and it means a settings change applies to the very next
    upload with no restart.
    """
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    async def get(key: str, default: str = "") -> str:
        try:
            value = await SiteOptionsService.get(db, key)
        except Exception:
            logger.warning("image_seo_option_read_failed", key=key)
            return default
        return default if value is None else value

    return _Options(
        auto_alt=_as_bool(await get("image_seo_auto_alt"), True),
        auto_title=_as_bool(await get("image_seo_auto_title"), True),
        auto_caption=_as_bool(await get("image_seo_auto_caption"), False),
        auto_description=_as_bool(await get("image_seo_auto_description"), False),
        case=await get("image_seo_case", "none") or "none",
        separators=await get("image_seo_filename_separators", DEFAULT_SEPARATORS),
        replacements=_parse_replacements(await get("image_seo_replacements")),
    )


def generate_text(options: _Options, filename: str) -> str:
    """The cleaned, cased, replaced text for a file name ("" when unusable)."""
    base = clean_filename_for_seo(filename, options.separators)
    if not base:
        return ""
    base = apply_replacements(base, options.replacements)
    return apply_case(base, options.case)


async def fill_metadata(
    db: AsyncSession,
    *,
    filename: str,
    alt_text: str | None,
    title: str | None,
    caption: str | None,
    description: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Fill empty alt/title/caption/description from *filename*.

    Returns the four values with empties filled per the settings. An operator
    value always wins — this only fills blanks. When the name cleans to
    nothing, every value passes through unchanged.
    """
    options = await load_settings(db)
    generated = generate_text(options, filename)

    if not generated:
        return alt_text, title, caption, description

    def fill(current: str | None, enabled: bool) -> str | None:
        if current is not None and current.strip():
            return current
        return generated if enabled else current

    filled = (
        fill(alt_text, options.auto_alt),
        fill(title, options.auto_title),
        fill(caption, options.auto_caption),
        fill(description, options.auto_description),
    )
    if filled != (alt_text, title, caption, description):
        await logger.ainfo(
            "image_seo_metadata_filled",
            filename=filename,
            generated=generated,
        )
    return filled
