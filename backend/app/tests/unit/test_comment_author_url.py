"""Tests for the commenter-site field's server-side normalisation.

The column, the create schema and the public response all carried
``author_url`` while nothing rendered it. The moment a renderer linkifies it,
an unchecked value becomes a stored XSS served to every reader, so the check
belongs on the way in — an API client or an import can write the column too.
"""

from __future__ import annotations

import pytest

from app.modules.blog.application.comment_service import _normalize_comment_url


@pytest.mark.parametrize(
    "raw",
    [
        "https://example.com",
        "http://example.com/path?a=1",
        "https://sub.example.co.uk/page#anchor",
        "HTTPS://EXAMPLE.COM",
    ],
)
def test_http_urls_pass_through(raw):
    assert _normalize_comment_url(raw) is not None


@pytest.mark.parametrize(
    "raw",
    [
        "javascript:alert(1)",
        "JavaScript:alert(document.cookie)",
        "  javascript:alert(1)  ",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "ftp://example.com",
        "example.com",
        "www.example.com",
        "//example.com",
        "https://",
        "javascript\n:alert(1)",
    ],
)
def test_non_http_schemes_are_refused(raw):
    assert _normalize_comment_url(raw) is None, (
        "a value that is not an absolute http(s) URL must never be stored"
    )


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_empty_is_none(raw):
    assert _normalize_comment_url(raw) is None


def test_length_is_capped_to_the_column():
    # The column is String(500). A longer value would be stored or rejected by
    # the database rather than by us, which turns a bad comment into a 500.
    out = _normalize_comment_url("https://example.com/" + "a" * 900)
    assert out is not None
    assert len(out) <= 500


def test_surrounding_whitespace_is_trimmed():
    assert _normalize_comment_url("  https://example.com  ") == "https://example.com"


def test_spaces_inside_a_url_are_refused():
    # The renderer's own guard refuses these too; the two must agree, or a
    # stored value and a rendered one diverge.
    assert _normalize_comment_url("https://exa mple.com") is None