"""Author slugs — the URL a person's byline lives at.

WordPress gives every author a `user_nicename`, and the author archive is
`/author/<that>`. This schema has carried the column since the beginning with
a migration that filled it once and no writer at all, so every account created
since has had an empty author slug and its archive 404s. A blank column is
worse than a missing one: the archive code checks for the column and falls back
to the display name, so the store shows a plausible-looking author page that is
not the one it links to.

The rules here are the ones WordPress applies and the two that matter in
practice:

* **derived from the name, transliterated.** A Persian name has to produce
  something a URL can carry. Transliterating rather than percent-encoding keeps
  the slug readable and stable — a percent-encoded name changes shape when a
  browser normalises it.
* **unique, always.** The column is `unique=True`, and two authors named
  "علی رضایی" is not an edge case on a store. So the slug is taken against the
  column, not against the name: a second Ali gets `ali-rezaei-2`, and the
  first keeps the clean one.

Deliberately not a database default or a model validator. Both would have to
run a uniqueness query, which a validator cannot do without a session, and the
result would be a slug that looks assigned but is not unique — the failure this
whole function exists to prevent.
"""

from __future__ import annotations

import re
import uuid

#: Persian and Arabic letters to Latin, which is what makes a slug readable for
#: a Persian author rather than a row of percent signs. Applied longest-match
#: first, so a letter that is a prefix of a longer one is not stolen.
_TRANSLITERATE = {
    "آ": "a", "أ": "a", "إ": "i", "ا": "a",
    "ب": "b", "پ": "p", "ت": "t", "ث": "s", "ج": "j", "چ": "ch",
    "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
    "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t",
    "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "gh", "ک": "k",
    "ك": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n", "و": "o",
    "ه": "h", "ی": "i", "ي": "i", "ة": "h", "ء": "", "ئ": "i",
    "ؤ": "o", "ﻻ": "la",
}

#: Everything that is not a letter or a digit, once transliteration has run.
_NON_SLUG = re.compile(r"[^a-z0-9]+")

#: WordPress caps at 50 characters for a nicename. Short enough to stay a
#: readable URL, long enough for a full Persian name transliterated.
MAX_LENGTH = 50


def slugify_author(name: str, *, fallback: str | None = None) -> str:
    """A readable, URL-safe slug for a display name.

    Empty input falls back to the caller's ``fallback`` and then to ``"user"``,
    because a name of only characters that transliterate to nothing is a real
    input (a name written entirely in a script not covered above) and must still
    produce a usable slug rather than an empty string that every unique check
    then collides on.
    """
    out: list[str] = []
    for char in (name or "").strip():
        lower = char.lower()
        if lower in _TRANSLITERATE:
            out.append(_TRANSLITERATE[lower])
        else:
            out.append(lower)

    slug = _NON_SLUG.sub("-", "".join(out)).strip("-")[:MAX_LENGTH].strip("-")
    if slug:
        return slug
    if fallback:
        return slugify_author(fallback)
    return "user"


async def unique_author_slug(
    db,
    name: str,
    *,
    fallback: str | None = None,
) -> str:
    """A slug for ``name`` that no user holds.

    Checked against the column, not the name, because the column is what is
    unique and two people can share a name. The suffix is a counter rather than
    a random string so a person's own URL stays predictable across attempts —
    they can be told their address is `/author/ali-rezaei-2` and it will not
    change tomorrow.
    """
    from sqlalchemy import select

    from app.modules.users.domain.models import User

    base = slugify_author(name, fallback=fallback)

    taken = (await db.execute(
        select(User.author_slug).where(User.author_slug.is_not(None))
    )).scalars().all()
    used = {s for s in taken if s}

    if base not in used:
        return base

    for suffix in range(2, 1000):
        candidate = f"{base}-{suffix}"
        if candidate not in used:
            return candidate
    # Unreachable in practice; a fallthrough that still returns something valid
    # beats one that returns a slug already in the column.
    return f"{base}-{uuid.uuid4().hex[:8]}"
