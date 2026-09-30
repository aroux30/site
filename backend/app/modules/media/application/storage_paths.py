"""Filesystem layout of the local media store.

One module owns the answer to "where does an asset's file live?", because the
answer is used from three places that used to disagree:

* the upload path, which writes the bytes,
* ``GET /uploads/{path}``, which serves them by URL,
* the variant renderer, which reads the source image to resize it.

The upload wrote a flat ``media/<name>`` while the database column claimed a
sharded ``media/<hex[:2]>/<name>``, and the serving route did not exist at all —
so the same logical file had three different stories. These helpers are pure
(both take the root as an argument) so they are unit-testable without a running
app or database.
"""

from __future__ import annotations

from pathlib import Path

#: Subdirectory of the uploads root that holds original files.
MEDIA_SUBDIR = "media"


def resolve_served_file(uploads_root: Path, url_path: str) -> Path | None:
    """Map a request path from ``/uploads/...`` to a public media file.

    Returns ``None`` when the path escapes the media root or names no regular
    file. This is the security boundary for the public serving route: the
    returned path is always a real file underneath ``<uploads_root>/media``.

    The public root is ``<UPLOAD_DIR>/media``, NOT ``UPLOAD_DIR``. Four other
    modules write private data under the same upload root — ``invoices/``
    (buyer name, phone and address), ``digital_assets/`` (paid files),
    ``dataexchange/`` and ``report-runs/``. Confining the route to the media
    subdirectory is what keeps those unreachable; the previous version
    confined it to the upload root, which served all four to anonymous callers.

    Stored ``file_url`` values include the ``media/`` segment
    (``/uploads/media/<name>``, see ``media_service.upload_file``), and that
    exact string is what arrives in ``url_path`` because the route is mounted at
    ``/uploads/{file_path:path}``. So the leading segment is accepted and
    stripped rather than treated as part of the name — a stored URL must keep
    resolving, and a bare filename must keep working for hand-written links.
    """
    relative = url_path
    head, _, tail = url_path.partition("/")
    if head == MEDIA_SUBDIR and tail:
        # Already scoped: the caller is replaying a stored file_url.
        relative = tail
    public_root = (uploads_root / MEDIA_SUBDIR).resolve()
    candidate = (public_root / relative).resolve()
    # is_relative_to, not a string prefix test: a prefix test would accept a
    # sibling directory whose name merely starts with the root's name.
    if not candidate.is_relative_to(public_root) or not candidate.is_file():
        return None
    return candidate


def original_file_for(uploads_root: Path, file_url: str) -> Path:
    """The canonical on-disk path for an asset, derived from its served URL.

    ``file_url`` is ``/uploads/media/<name>``; originals are stored flat under
    ``<root>/media/``. This is the primary lookup — it matches what the upload
    actually wrote.
    """
    return uploads_root / MEDIA_SUBDIR / Path(file_url).name


def candidate_sources(uploads_root: Path, file_url: str, file_path: str | None) -> list[Path]:
    """Every path an asset's bytes may occupy, most authoritative first.

    ``file_path`` is consulted last: rows written before the layout was aligned
    may point at a sharded location the upload never produced, so a missing
    stored path must not shadow the real file.
    """
    candidates = [original_file_for(uploads_root, file_url)]
    if file_path:
        candidates.append(uploads_root / file_path)
    return candidates
