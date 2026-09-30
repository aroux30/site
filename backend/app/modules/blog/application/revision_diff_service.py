"""Revision diff: field-level comparison between two stored post snapshots.

Pure string logic (difflib) plus a thin loader that resolves two revision
rows of the same post. The body field additionally carries a compact
word-level inline diff as a list of ``{op, text}`` tokens.
"""

from __future__ import annotations

import difflib
import uuid
from typing import TYPE_CHECKING, Literal

from app.core.exceptions.handlers import NotFoundError
from app.modules.blog.domain.models import BlogPostRevision
from app.modules.blog.schemas.blog import (
    RevisionDiffResponse,
    RevisionDiffToken,
    RevisionFieldDiff,
    RevisionSnapshotRef,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DiffOp = Literal["equal", "insert", "delete"]

# (model attribute, API field key, human label). "body" maps onto the stored
# ``content`` column; the seo_* attributes snapshot the seo_metadata row at
# revision time (NULL for revisions predating the columns).
_DIFF_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("title", "title", "عنوان"),
    ("excerpt", "excerpt", "خلاصه"),
    ("body", "body", "متن"),
    ("slug", "slug", "نامک"),
    ("status", "status", "وضعیت"),
    ("cover_image_url", "cover_image_url", "تصویر شاخص"),
    ("seo_title", "seo_title", "عنوان سئو"),
    ("seo_description", "seo_description", "توضیح سئو"),
)
# Long text fields get the word-level inline treatment; short fields only
# need the plain before/after values.
_INLINE_DIFF_FIELDS = frozenset({"body"})


def word_diff(a_text: str, b_text: str) -> list[RevisionDiffToken]:
    """Compact word-level inline diff as ``{op, text}`` tokens.

    ``equal``+``delete`` tokens joined with single spaces reconstruct A;
    ``equal``+``insert`` reconstructs B. Whitespace runs collapse to single
    spaces — the diff is for display, not byte-exact round-tripping.
    """
    a_words = a_text.split()
    b_words = b_text.split()
    tokens: list[RevisionDiffToken] = []

    def append(op: DiffOp, text: str) -> None:
        if not text:
            return
        # Merge consecutive same-op tokens to keep the list compact.
        if tokens and tokens[-1].op == op:
            tokens[-1] = RevisionDiffToken(op=op, text=f"{tokens[-1].text} {text}")
            return
        tokens.append(RevisionDiffToken(op=op, text=text))

    matcher = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            append("equal", " ".join(a_words[i1:i2]))
        elif op == "delete":
            append("delete", " ".join(a_words[i1:i2]))
        elif op == "insert":
            append("insert", " ".join(b_words[j1:j2]))
        else:  # replace: a chunk was removed where another was added
            append("delete", " ".join(a_words[i1:i2]))
            append("insert", " ".join(b_words[j1:j2]))
    return tokens


def diff_revisions(
    rev_a: BlogPostRevision,
    rev_b: BlogPostRevision,
) -> RevisionDiffResponse:
    """Compare two revisions of the same post, field by field."""
    if rev_a.post_id != rev_b.post_id:
        raise ValueError("Cannot diff revisions of different posts")

    fields: list[RevisionFieldDiff] = []
    changed = False
    for attr, key, label in _DIFF_FIELDS:
        a_value = rev_a.content if attr == "body" else getattr(rev_a, attr)
        b_value = rev_b.content if attr == "body" else getattr(rev_b, attr)
        # Stored NULLs and empty strings mean the same thing for a diff.
        is_changed = (a_value or "") != (b_value or "")
        field = RevisionFieldDiff(
            field=key,
            label=label,
            changed=is_changed,
            a=a_value,
            b=b_value,
        )
        if is_changed and key in _INLINE_DIFF_FIELDS:
            field.inline_diff = word_diff(a_value or "", b_value or "")
        changed = changed or is_changed
        fields.append(field)

    return RevisionDiffResponse(
        post_id=rev_a.post_id,
        rev_a=_ref(rev_a),
        rev_b=_ref(rev_b),
        fields=fields,
        changed=changed,
    )


def _ref(revision: BlogPostRevision) -> RevisionSnapshotRef:
    return RevisionSnapshotRef(
        id=revision.id,
        revision_number=revision.revision_number,
        created_at=revision.created_at,
        created_by=revision.created_by,
    )


async def _get_revision(
    db: AsyncSession,
    post_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> BlogPostRevision:
    revision = await db.get(BlogPostRevision, revision_id)
    if revision is None or revision.post_id != post_id:
        raise NotFoundError(
            "BlogPostRevision",
            f"Revision {revision_id} for post {post_id} not found",
        )
    return revision


async def diff_post_revisions(
    db: AsyncSession,
    post_id: uuid.UUID,
    rev_a_id: uuid.UUID,
    rev_b_id: uuid.UUID,
) -> RevisionDiffResponse:
    """Load two revisions of one post and return their field-level diff."""
    rev_a = await _get_revision(db, post_id, rev_a_id)
    rev_b = await _get_revision(db, post_id, rev_b_id)
    return diff_revisions(rev_a, rev_b)
