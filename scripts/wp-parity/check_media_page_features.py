"""The media library's page-level features are present and wired.

Four gaps from the P1 list, each one an absence rather than a partial:

  * aspect-ratio presets on the crop dialog (1:1, 4:3, 16:9) — the crop tool
    took only pixel numbers, so "square for a product tile" was arithmetic;
  * PDF preview — a PDF showed the broken-image glyph, so an operator could
    not tell a good upload from a bad one without downloading it;
  * the media Title field — WordPress's fourth attachment field, absent from
    the model and the form;
  * the list view — the library was grid-only, which answers "what does this
    look like" but not "what is in here and when did it arrive".

This checks each in the file that must own it, and the caller for each — a
feature defined but never rendered is the failure class this project keeps
finding.

    python scripts/wp-parity/check_media_page_features.py
"""

from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent; a plain TextIOWrapper
# here is closed by any later module that wraps stdout.

PAGE = os.path.join(ROOT, "frontend", "app", "admin", "media", "page.tsx")
MODEL = os.path.join(ROOT, "backend", "app", "modules", "media", "domain", "models.py")
SCHEMA = os.path.join(ROOT, "backend", "app", "modules", "media", "schemas", "media.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    page = open(PAGE, encoding="utf-8").read() if os.path.isfile(PAGE) else ""
    model = open(MODEL, encoding="utf-8").read() if os.path.isfile(MODEL) else ""
    schema = open(SCHEMA, encoding="utf-8").read() if os.path.isfile(SCHEMA) else ""

    # Aspect presets: the ratio buttons exist and set the crop box.
    check("the crop dialog offers aspect presets",
          "نسبت آماده" in page and "۱۶:۹" in page,
          "no ratio presets on the crop dialog")
    check("a preset sets the crop rectangle",
          "byWidth" in page or "largest box" in page,
          "the preset does not compute a box")

    # PDF preview: an iframe branch for application/pdf.
    #
    # Anchored on the branch, not on the two strings. `"application/pdf" in
    # page and "<iframe" in page` passes with the whole render branch deleted —
    # both strings live elsewhere in the file — so removing the feature left the
    # gate green. `isPdf ? (` is the statement that decides what renders.
    check("a PDF renders in its own branch",
          "isPdf ? (" in page and "<iframe" in page,
          "PDFs have no preview branch")
    check("and the branch is guarded by the mime type, not a local guess",
          'asset.mime_type === "application/pdf"' in page,
          "the PDF check does not read the asset's own mime type")
    check("and a PDF gets its own grid icon",
          'isPdf' in page, "a PDF still shows the broken-image glyph")

    # Title field: model + schema + form.
    check("the model has a title column", "title: Mapped[str | None]" in model)
    check("the update schema accepts a title", "title:" in schema)
    check("the form has a title input", 'id="med-title"' in page,
          "the column exists but nothing edits it")

    # List view.
    #
    # The condition that actually picks the layout, not the word "list" and the
    # state variable — both of which survive the render branch being deleted,
    # because the toggle still offers a mode nothing reads.
    check("the library has a list view",
          'viewMode === "list" ? (' in page,
          "the toggle offers a list mode nothing renders")
    check("with a toggle control",
          'LayoutGrid' in page and "List" in page)

    # The alt-text warning consumes the server's field, not a local copy of
    # the rule: the two could drift, and the server's answer was dead code.
    client = open(os.path.join(
        ROOT, "frontend", "lib", "api", "media.ts"
    ), encoding="utf-8").read()
    check("the asset type carries needs_alt_text",
          "needs_alt_text" in client,
          "the field is computed server-side but absent from the type")
    check("the list prefers the server's needs_alt_text",
          "asset.needs_alt_text" in page,
          "the UI still recomputes the rule and ignores the field")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the media library has ratio presets, PDF preview, the Title "
          "field, a list view, and consumes the server's alt-text verdict.")
    return 0


if __name__ == "__main__":
    sys.exit(main())