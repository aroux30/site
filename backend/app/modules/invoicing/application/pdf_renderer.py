"""PDF rendering seam for archived fiscal documents.

No PDF library (weasyprint / reportlab / xhtml2pdf) is currently in
``pyproject.toml``, and the invoicing hardening scope forbids adding a
dependency. The archived document is therefore the rendered HTML snapshot
(byte-for-byte what ``GET /orders/{id}/invoice`` produces at post time),
written through the same local storage convention as the media module
(``UPLOAD_DIR`` root, server-generated path).

:func:`get_renderer` returns the configured renderer; with none configured it
returns :class:`HtmlArchiveRenderer`, which "renders" by returning the HTML
bytes unchanged with an ``text/html`` content type. Dropping in a real PDF
backend later means implementing :class:`PdfRenderer` and registering it —
the call site (:func:`invoice_service.archive_document`) does not change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.core.config.settings import get_settings


@runtime_checkable
class PdfRenderer(Protocol):
    """Interface for rendering a document HTML snapshot to archival bytes."""

    content_type: str
    file_extension: str

    def render(self, html: str) -> bytes:
        """Render *html* to the archived byte payload."""
        ...


class PdfNotConfiguredError(RuntimeError):
    """Raised when a PDF-only operation runs without a configured renderer."""


class HtmlArchiveRenderer:
    """Fallback renderer: archives the HTML snapshot itself.

    This keeps the post-time archival pipeline fully functional (the fiscal
    document has a frozen, downloadable artifact) until a real PDF backend is
    introduced. ``PdfRenderer`` conformance is structural: the returned bytes
    are HTML and the content type says so.
    """

    content_type = "text/html; charset=utf-8"
    file_extension = ".html"

    def render(self, html: str) -> bytes:
        return html.encode("utf-8")


_renderer: PdfRenderer | None = None


def register_renderer(renderer: PdfRenderer) -> None:
    """Install the process-wide renderer (e.g. a WeasyPrint adapter)."""
    global _renderer
    _renderer = renderer


def get_renderer() -> PdfRenderer:
    """Return the configured renderer, or the HTML-archive fallback."""
    return _renderer if _renderer is not None else HtmlArchiveRenderer()


def archive_document(*, document_key: str, html: str) -> tuple[str, str]:
    """Render *html* and persist the bytes under the upload root.

    Returns ``(archive_path, content_type)``. The path is server-generated
    under ``<UPLOAD_DIR>/invoices/`` — caller-supplied text never reaches a
    filesystem path (same rule as the media module).
    """
    renderer = get_renderer()
    payload = renderer.render(html)

    settings = get_settings()
    base_dir = Path(getattr(settings, "UPLOAD_DIR", "media")) / "invoices"
    base_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240  # trivial local metadata op
    safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in document_key)
    file_name = f"{safe_key}{renderer.file_extension}"
    (base_dir / file_name).write_bytes(payload)

    return str(Path("invoices") / file_name), renderer.content_type
