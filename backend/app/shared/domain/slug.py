"""URL-safe slug generation with Persian/Arabic transliteration.

Shared by every content-bearing module (catalog, blog, CMS pages). Strapi-style
rule: the slug is derived from the title automatically, but the editor can
always override it manually.
"""

from __future__ import annotations

import re
import unicodedata

_PERSIAN_TO_LATIN: dict[str, str] = {
    "آ": "a",
    "ا": "a",
    "ب": "b",
    "پ": "p",
    "ت": "t",
    "ث": "s",
    "ج": "j",
    "چ": "ch",
    "ح": "h",
    "خ": "kh",
    "د": "d",
    "ذ": "z",
    "ر": "r",
    "ز": "z",
    "ژ": "zh",
    "س": "s",
    "ش": "sh",
    "ص": "s",
    "ض": "z",
    "ط": "t",
    "ظ": "z",
    "ع": "a",
    "غ": "gh",
    "ف": "f",
    "ق": "gh",
    "ک": "k",
    "گ": "g",
    "ل": "l",
    "م": "m",
    "ن": "n",
    "و": "v",
    "ه": "h",
    "ی": "y",
    "ئ": "y",
    "ي": "y",
    "ك": "k",
    "ة": "h",
    "إ": "e",
    "أ": "a",
    "ؤ": "v",
    # Persian digits
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
    # Arabic digits
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
}

# Diacritics / zero-width characters to strip
_DIACRITICS_RE = re.compile(r"[ً-ٰٟۖ-ۭ​-‏‪-‮﻿]")


def generate_slug(text: str, *, fallback: str = "") -> str:
    """Generate a URL-safe slug from text that may contain Persian/Arabic characters.

    Steps:
        1. Strip diacritics and zero-width characters.
        2. Transliterate Persian characters to Latin.
        3. Normalise to ASCII where possible (NFD + strip combining marks).
        4. Lower-case, replace non-alphanum with hyphens, collapse runs, strip edges.

    Returns ``fallback`` when nothing usable remains (e.g. an all-emoji title).
    """
    if not text:
        return fallback

    text = _DIACRITICS_RE.sub("", text)
    text = text.replace("‌", "-")  # Half-space (ZWNJ)
    text = "".join(_PERSIAN_TO_LATIN.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9-]", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or fallback
