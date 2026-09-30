"""Field-level diff between two CMS page revisions (editor history UI).

Revisions are immutable snapshots (see :class:`CmsPageRevision`), so a diff is
a pure comparison of two stored rows: which fields changed, and — for the
large ``body_html`` — word-level inline tokens so the editor can highlight
what exactly moved instead of re-reading two full documents.

Word tokens follow classic inline-diff semantics: a difflib "replace" block is
split into a delete (old words) followed by an insert (new words), so

* concatenating every ``equal`` + ``delete`` token reproduces the old body,
* concatenating every ``equal`` + ``insert`` token reproduces the new body.
"""

from __future__ import annotations

import difflib
import re
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError
from app.modules.content.domain.models import CmsPage, CmsPageRevision
from app.modules.content.schemas.content import (
    RevisionDiffResponse,
    RevisionFieldDiff,
    RevisionRef,
    RevisionWordToken,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Compared fields, in reporting order. The big body text goes last so the
# small scalar fields are skimmable before the inline tokens.
_DIFF_FIELDS: tuple[str, ...] = (
    "title",
    "slug",
    "excerpt",
    "status",
    "seo_title",
    "seo_description",
    "body_html",
)

# A word plus its trailing whitespace; a leading whitespace run only occurs
# at string start (word-trailing runs consume the rest), so no text is lost.
_WORD_TOKEN_RE = re.compile(r"\S+\s*|\s+")


def word_diff(before: str, after: str) -> list[RevisionWordToken]:
    """Word-level inline diff of two bodies as ``{op, text}`` tokens."""
    old_words = _WORD_TOKEN_RE.findall(before or "")
    new_words = _WORD_TOKEN_RE.findall(after or "")
    matcher = difflib.SequenceMatcher(a=old_words, b=new_words, autojunk=False)
    tokens: list[RevisionWordToken] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            tokens.append(RevisionWordToken(op="equal", text="".join(old_words[i1:i2])))
        elif op == "delete":
            tokens.append(RevisionWordToken(op="delete", text="".join(old_words[i1:i2])))
        elif op == "insert":
            tokens.append(RevisionWordToken(op="insert", text="".join(new_words[j1:j2])))
        else:  # replace: split into the delete/insert pair editors render
            tokens.append(RevisionWordToken(op="delete", text="".join(old_words[i1:i2])))
            tokens.append(RevisionWordToken(op="insert", text="".join(new_words[j1:j2])))
    return tokens


def compute_revision_diff(
    rev_a: Any,
    rev_b: Any,
    *,
    page_id: uuid.UUID | None = None,
) -> RevisionDiffResponse:
    """Compare two revision snapshots (ORM rows or stand-ins) field by field.

    ``None`` and empty-string field values compare equal, so clearing an
    optional SEO field is not reported as a phantom change against a fresh
    snapshot.
    """
    fields: list[RevisionFieldDiff] = []
    changed: list[str] = []
    for name in _DIFF_FIELDS:
        before = getattr(rev_a, name, None)
        after = getattr(rev_b, name, None)
        is_changed = (before or "") != (after or "")
        fields.append(
            RevisionFieldDiff(field=name, changed=is_changed, before=before, after=after)
        )
        if is_changed:
            changed.append(name)

    return RevisionDiffResponse(
        page_id=page_id if page_id is not None else rev_a.page_id,
        rev_a=RevisionRef(
            revision_number=rev_a.revision_number,
            created_at=getattr(rev_a, "created_at", None),
            title=rev_a.title or "",
        ),
        rev_b=RevisionRef(
            revision_number=rev_b.revision_number,
            created_at=getattr(rev_b, "created_at", None),
            title=rev_b.title or "",
        ),
        changed_fields=changed,
        fields=fields,
        body_word_diff=word_diff(rev_a.body_html or "", rev_b.body_html or ""),
        identical=not changed,
    )


async def diff_page_revisions(
    db: AsyncSession,
    page_id: uuid.UUID,
    rev_a_number: int,
    rev_b_number: int,
) -> RevisionDiffResponse:
    """Load two revisions of one page by revision number and diff them.

    Revision numbers (not row ids) address revisions here, matching the
    neighboring ``POST /admin/pages/{id}/revisions/{n}/restore`` route.
    """
    page = await db.get(CmsPage, page_id)
    if not page:
        raise NotFoundError("CmsPage", f"CMS page {page_id} not found")

    async def _load(number: int) -> CmsPageRevision:
        rev = (
            await db.execute(
                select(CmsPageRevision).where(
                    CmsPageRevision.page_id == page_id,
                    CmsPageRevision.revision_number == number,
                )
            )
        ).scalar_one_or_none()
        if not rev:
            raise NotFoundError(
                "CmsPageRevision", f"Revision {number} of page {page_id} not found"
            )
        return rev

    rev_a = await _load(rev_a_number)
    rev_b = await _load(rev_b_number)
    diff = compute_revision_diff(rev_a, rev_b, page_id=page_id)
    logger.info(
        "cms_page_revision_diff",
        page_id=str(page_id),
        rev_a=rev_a_number,
        rev_b=rev_b_number,
        changed=len(diff.changed_fields),
    )
    return diff
