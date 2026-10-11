"""Tests for advanced redirects (Rank Math Redirections parity).

Pins the new behaviors:

- 301/302/307/308 carry a destination; 410/451 must NOT (their meaning is
  "not coming back" — a 410 pointing at a live page is a contradiction).
- Regex rules: invalid patterns rejected at write time (a stored invalid
  pattern would be silently skipped forever), $1 back-references substituted.
- CSV export/import round-trip; malformed rows reported with line numbers.
- The matcher order: exact beats wildcard beats regex.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions.handlers import ValidationError
from app.modules.seo.application import redirect_service as rs
from app.modules.seo.domain.models import RedirectRule


def _rule(**overrides) -> RedirectRule:
    defaults = dict(
        id=uuid.uuid4(),
        from_path="/old",
        to_path="/new",
        status_code=301,
        is_active=True,
        is_regex=False,
    )
    defaults.update(overrides)
    return RedirectRule(**defaults)


# ── status-code validation ────────────────────────────────────────────────


def test_410_rejects_a_target():
    with pytest.raises(ValidationError, match="مقصد نمی‌پذیرد"):
        rs._validate_status(410, "/somewhere")


def test_451_rejects_a_target():
    with pytest.raises(ValidationError, match="مقصد نمی‌پذیرد"):
        rs._validate_status(451, "/somewhere")


def test_410_without_target_is_valid():
    rs._validate_status(410, None)  # must not raise


def test_307_and_308_require_a_target():
    for code in (307, 308):
        with pytest.raises(ValidationError, match="به مقصد نیاز دارد"):
            rs._validate_status(code, None)


def test_unknown_code_rejected():
    with pytest.raises(ValidationError):
        rs._validate_status(999, "/x")


def test_all_codes_accepted_with_correct_shape():
    for code in rs.CODES_WITH_TARGET:
        rs._validate_status(code, "/target")
    for code in rs.CODES_WITHOUT_TARGET:
        rs._validate_status(code, None)


# ── regex validation ──────────────────────────────────────────────────────


def test_invalid_regex_rejected_at_write_time():
    with pytest.raises(ValidationError, match="regex"):
        rs._validate_regex("/(unclosed")


def test_empty_regex_rejected():
    with pytest.raises(ValidationError):
        rs._validate_regex("   ")


def test_valid_regex_accepted():
    assert rs._validate_regex(r"^/products/(\d+)$") == r"^/products/(\d+)$"


# ── regex target expansion ────────────────────────────────────────────────


def test_dollar_backreference_substituted():
    result = rs.apply_regex_target(r"^/old/(\d+)$", "/new/$1", "/old/42")
    assert result == "/new/42"


def test_regex_no_match_returns_none():
    assert rs.apply_regex_target(r"^/old/(\d+)$", "/new/$1", "/other/42") is None


def test_regex_multiple_groups():
    result = rs.apply_regex_target(
        r"^/blog/([a-z]+)/(\d+)$", "/posts/$1/$2", "/blog/tech/7"
    )
    assert result == "/posts/tech/7"


def test_regex_extra_group_expands_empty():
    result = rs.apply_regex_target(r"^/a/(\d+)$", "/b/$1/$2", "/a/5")
    assert result == "/b/5/"


# ── matcher priority ──────────────────────────────────────────────────────


def test_exact_beats_wildcard_beats_regex():
    rules = [
        _rule(from_path="/x/*", to_path="/wild"),
        _rule(from_path=r"^/x/exact$", to_path="/regex", is_regex=True),
        _rule(from_path="/x/exact", to_path="/exact"),
    ]
    match = rs.match_redirect("/x/exact", rules)
    assert match is not None and match.to_path == "/exact"


def test_wildcard_beats_regex():
    rules = [
        _rule(from_path=r"^/x/.*$", to_path="/regex", is_regex=True),
        _rule(from_path="/x/*", to_path="/wild"),
    ]
    match = rs.match_redirect("/x/deep/path", rules)
    assert match is not None and match.to_path == "/wild"


def test_regex_used_when_nothing_else_matches():
    rules = [
        _rule(from_path=r"^/products/(\d+)$", to_path="/p/$1", is_regex=True),
    ]
    match = rs.match_redirect("/products/42", rules)
    assert match is not None and match.is_regex


def test_invalid_stored_regex_skipped_not_fatal():
    rules = [
        _rule(from_path="/(unclosed", to_path="/x", is_regex=True),
        _rule(from_path="/ok", to_path="/fine"),
    ]
    match = rs.match_redirect("/ok", rules)
    assert match is not None and match.to_path == "/fine"


def test_inactive_rules_never_match():
    rules = [_rule(from_path="/x", to_path="/y", is_active=False)]
    assert rs.match_redirect("/x", rules) is None


# ── CSV round-trip ────────────────────────────────────────────────────────


def test_csv_export_has_bom_and_header():
    csv_text = rs.export_redirects_csv([_rule()])
    assert csv_text.startswith("﻿")
    assert "source,target,status" in csv_text


def test_csv_round_trip():
    rules = [
        _rule(from_path="/a", to_path="/b", status_code=307),
        _rule(from_path=r"^/r/(\d+)$", to_path="/s/$1", is_regex=True),
        _rule(from_path="/gone", to_path=None, status_code=410),
    ]
    exported = rs.export_redirects_csv(rules)
    parsed = rs.parse_redirects_csv(exported)
    assert len(parsed) == 3
    assert parsed[0]["status_code"] == 307
    assert parsed[1]["is_regex"] is True
    assert parsed[2]["to_path"] is None
    assert parsed[2]["status_code"] == 410


def test_csv_accepts_rank_math_header_names():
    content = "source,target,status\n/old,/new,301\n"
    parsed = rs.parse_redirects_csv(content)
    assert parsed[0]["from_path"] == "/old"


def test_csv_missing_source_column_rejected():
    with pytest.raises(ValidationError, match="source"):
        rs.parse_redirects_csv("target,status\n/new,301\n")


def test_csv_bad_status_row_reported_with_line():
    content = "source,target,status\n/a,/b,abc\n"
    with pytest.raises(ValidationError, match="سطر 2"):
        rs.parse_redirects_csv(content)


def test_csv_rows_without_source_skipped():
    content = "source,target,status\n,/b,301\n/a,/b,301\n"
    parsed = rs.parse_redirects_csv(content)
    assert len(parsed) == 1
    assert parsed[0]["from_path"] == "/a"
