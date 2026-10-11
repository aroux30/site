"""Tests for the link counter (Rank Math's Link Counter).

Classifies every anchor href as internal / external / anchor / other and
flags posts with no internal link (the content-side orphan). The failure
modes pinned here: a protocol-relative URL (//host) is NOT internal, a
mailto/tel is "other" not external, and the site's own host with and without
www both count as internal.
"""

from __future__ import annotations

from app.modules.seo.application import link_counter_service as lc


HOSTS = lc.site_hosts_from("https://arouxshop.com")


def test_site_hosts_include_www_variant():
    assert "arouxshop.com" in HOSTS
    assert "www.arouxshop.com" in HOSTS


def test_relative_link_is_internal():
    counts = lc.count_links('<a href="/products/x">x</a>', site_hosts=HOSTS)
    assert counts["internal"] == 1


def test_absolute_own_host_is_internal():
    counts = lc.count_links(
        '<a href="https://arouxshop.com/blog">b</a>', site_hosts=HOSTS
    )
    assert counts["internal"] == 1
    assert counts["external"] == 0


def test_www_variant_is_internal():
    counts = lc.count_links(
        '<a href="https://www.arouxshop.com/blog">b</a>', site_hosts=HOSTS
    )
    assert counts["internal"] == 1


def test_foreign_host_is_external():
    counts = lc.count_links('<a href="https://example.com/x">x</a>', site_hosts=HOSTS)
    assert counts["external"] == 1
    assert counts["external_urls"] == ["https://example.com/x"]


def test_protocol_relative_is_not_internal():
    """//host resolves to a foreign host under the page's scheme — treating
    it as internal would hide real external links from the report."""
    counts = lc.count_links('<a href="//cdn.other.com/x">x</a>', site_hosts=HOSTS)
    assert counts["internal"] == 0
    assert counts["external"] == 1


def test_mailto_and_tel_are_other_not_external():
    html = '<a href="mailto:a@b.c">m</a><a href="tel:+123">t</a>'
    counts = lc.count_links(html, site_hosts=HOSTS)
    assert counts["external"] == 0
    assert counts["other"] == 2


def test_pure_anchor_is_anchor():
    counts = lc.count_links('<a href="#section">s</a>', site_hosts=HOSTS)
    assert counts["anchor"] == 1


def test_duplicate_external_urls_deduped_in_list_but_counted():
    html = (
        '<a href="https://example.com/x">1</a>'
        '<a href="https://example.com/x">2</a>'
    )
    counts = lc.count_links(html, site_hosts=HOSTS)
    assert counts["external"] == 2  # every occurrence counted
    assert counts["external_urls"] == ["https://example.com/x"]  # listed once


def test_total_sums_all_kinds():
    html = (
        '<a href="/a">i</a><a href="https://x.com">e</a>'
        '<a href="#s">a</a><a href="mailto:x@y.z">m</a>'
    )
    counts = lc.count_links(html, site_hosts=HOSTS)
    assert counts["total"] == 4


def test_empty_content_zero_counts():
    counts = lc.count_links("", site_hosts=HOSTS)
    assert counts["total"] == 0
    assert counts["external_urls"] == []


def test_uppercase_href_attribute_matched():
    counts = lc.count_links('<a HREF="/x">x</a>', site_hosts=HOSTS)
    assert counts["internal"] == 1


def test_empty_hosts_makes_absolute_external():
    counts = lc.count_links(
        '<a href="https://anything.com/x">x</a>', site_hosts=set()
    )
    assert counts["external"] == 1


def test_site_hosts_from_invalid_url_returns_empty():
    assert lc.site_hosts_from("not a url") == set()
    assert lc.site_hosts_from(None) == set()
