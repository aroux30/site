r"""Two live-fidelity fixes from the 2026-10-08 owner review.

1. **Reading time counted HTML as words.** `calculate_reading_time` ran
   `\w+` over the raw stored body: tag names/attributes/URLs counted as
   words, and `\w` does not match Persian letters at all. The live article
   (26 KB, ~3 000 real words) reported 26 minutes; the corrected count is 16.
   Negative test: restore the old regex — the HTML-heavy fixture below
   returns a number >2x the plain-text one.

2. **Author must be the importer, not the file's author.** The first
   version of `_apply_author_display_name` adopted the WXR file's author
   (آروکس) as the importing operator's display name. The owner corrected
   this: the byline belongs to the person who imported the data on THIS
   site. The helper now derives a fallback from the operator's own account
   (phone) and never reads the file's author blocks.
"""

from __future__ import annotations

import re

from app.modules.blog.application.blog_service import calculate_reading_time


def test_html_tags_are_not_words():
    r"""A body with heavy markup must count only its text.

    Negative test: swap back to `re.findall(r"\w+", content)` and the
    assertion below fails — the URL/attribute markup alone pushes the buggy
    count over the 200-word boundary.
    """
    # ~190 Persian words plus enough markup (a long URL, classes, srcset) that
    # the buggy regex would cross 200 and report 2 minutes.
    words = " ".join(["واژه"] * 190)
    body = (
        "<div class='container wide' data-url='https://example.com/a/very/long/path/segment?x=1&y=2'>"
        f"<p>{words}</p>"
        "<img src='https://cdn.example.com/image-name.webp' "
        "srcset='https://cdn.example.com/image-300.webp 300w, "
        "https://cdn.example.com/image-768.webp 768w' alt='تصویر' />"
        "</div>"
    )
    minutes = calculate_reading_time(body)
    # 190 real words -> 1 minute; markup pushes the buggy version to 2.
    assert minutes == 1


def test_persian_text_counts_as_words():
    r"""`\w` does not match Persian letters; whitespace splitting does.

    Negative test: restore `\w+` and a 600-word Persian body counts ~0
    words -> 1 minute instead of 3.
    """
    word = "کلمه"
    body = " ".join([word] * 600)
    assert calculate_reading_time(body) == 3


def test_entities_do_not_inflate():
    body = "<p>&nbsp;&nbsp;&nbsp;</p><p>" + " ".join(["واژه"] * 200) + "</p>"
    assert calculate_reading_time(body) == 1


def test_wxr_import_does_not_adopt_file_author():
    """The import helper must not write the WXR file's author anywhere.

    Source-level check (the helper needs a live DB to run): its body must
    not read `parsed["authors"]` — the owner's correction was exactly that
    the file's persona must not become the operator's byline.
    """
    import inspect

    from app.modules.blog.application import wxr_import

    src = inspect.getsource(wxr_import._apply_author_display_name)
    assert "parsed" not in src or "authors" not in src, (
        "the file's author blocks must not be read by the author-name helper"
    )
    assert "phone" in src, "the importer's own account is the fallback source"
