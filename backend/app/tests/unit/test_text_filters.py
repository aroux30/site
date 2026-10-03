"""Tests for the WordPress text filters (wpautop / wptexturize / emoji).

These are display-only transforms, so every assertion is about the output
string, not about a database. A test that cannot fail is not a test: the
negative cases below (text that must NOT be touched) exist to catch a filter
that is too eager.
"""

from __future__ import annotations

import pytest

from app.shared.content.text_filters import (
    wp_staticize_emoji,
    wpautop,
    wpautop_texturize_emoji,
    wptexturize,
)


# --------------------------------------------------------------- wpautop


def test_single_line_gets_a_paragraph():
    assert wpautop("سلام دنیا") == "<p>سلام دنیا</p>"


def test_blank_line_separates_paragraphs():
    out = wpautop("خط اول\n\nخط دوم")
    assert out.count("<p>") == 2
    assert "<p>خط اول</p>" in out
    assert "<p>خط دوم</p>" in out


def test_three_blank_lines_still_make_one_break():
    out = wpautop("a\n\n\n\nb")
    assert out.count("<p>") == 2, "extra blank lines must not make empty paragraphs"
    assert "<p></p>" not in out


def test_single_newline_is_not_a_paragraph_break():
    # One newline inside a paragraph is a soft wrap, exactly as in WordPress.
    out = wpautop("a\nb")
    assert out.count("<p>") == 1
    assert "\nb" in out, "the soft line break must survive"


def test_existing_block_markup_is_left_alone():
    body = "<h2>عنوان</h2>\n\nمتن"
    out = wpautop(body)
    assert "<h2>عنوان</h2>" in out
    assert "<p>متن</p>" in out
    assert out.count("<p>") == 1, "the heading must not be wrapped in a <p>"


def test_newline_between_two_blocks_makes_no_empty_paragraph():
    body = "<p>یک</p>\n<p>دو</p>"
    out = wpautop(body)
    assert out.count("<p>") == 2
    assert "<p></p>" not in out
    assert out.strip() == "<p>یک</p>\n<p>دو</p>"


def test_pre_block_content_is_untouched():
    body = "توضیح\n\n<pre><code>def f():\n    return 1\n</code></pre>\n\nپایان"
    out = wpautop(body)
    assert "def f():\n    return 1" in out, "code indentation must survive verbatim"
    assert out.count("<p>") == 2


def test_html_comment_is_preserved_not_wrapped():
    out = wpautop("<!-- note -->\n\nمتن")
    assert "<!-- note -->" in out
    assert "<!-- note --></p>" not in out


def test_empty_and_none_input():
    assert wpautop("") == ""
    assert wpautop(None) == ""


def test_script_body_is_not_turned_into_prose():
    # drop_code_blocks runs at sanitize time, but a body that still carries one
    # must not have its source wrapped in a paragraph.
    out = wpautop("<script>var a = 1</script>")
    assert "<p>var a" not in out


# --------------------------------------------------------------- texturize


def test_ellipsis_and_dashes():
    assert wptexturize("wait...") == "wait…"
    assert wptexturize("a --- b") == "a — b"
    assert wptexturize("a -- b") == "a – b"


def test_symbols():
    assert wptexturize("(c)") == "©"
    assert wptexturize("(r) 2026") == "® 2026"
    assert wptexturize("(tm)") == "™"


def test_apostrophe_in_contraction():
    assert wptexturize("don't") == "don’t"
    assert wptexturize("it's") == "it’s"


def test_inch_mark_inside_a_word():
    assert wptexturize('6"') == "6”"


def test_persian_text_is_untouched():
    # Persian uses the same characters the curly-quote pass looks for as word
    # boundaries, so this is the case most likely to regress.
    src = "قیمت محصول ۱۲۰ هزار تومان است"
    assert wptexturize(src) == src


def test_phone_number_is_not_mangled():
    # The full wptexturize squares numbers; a storefront must not do that.
    assert wptexturize("09121234567") == "09121234567"


# --------------------------------------------------------------- emoji


def test_known_token_becomes_unicode():
    assert wp_staticize_emoji(":smile:") == "\U0001f604"
    assert wp_staticize_emoji("سلام :tada:") == "سلام \U0001f389"


def test_unknown_token_stays_literal():
    assert wp_staticize_emoji(":not_an_emoji:") == ":not_an_emoji:"


def test_url_is_not_mistaken_for_a_token():
    # "https://example.com" has colons; a naive scan would eat the rest of it.
    src = "لینک: https://example.com/path"
    assert wp_staticize_emoji(src) == src


# --------------------------------------------------------------- chain


def test_chain_wraps_and_texturizes():
    out = wpautop_texturize_emoji("it's fine...\n\nSee :tada:")
    assert "<p>it’s fine…</p>" in out
    assert "\U0001f389" in out


def test_chain_leaves_code_verbatim():
    out = wpautop_texturize_emoji("<pre>don't touch...</pre>")
    assert "don't touch..." in out, "typographic quotes must not enter a code sample"
    assert "don’t" not in out


def test_chain_does_not_emoji_shortcode_like_text():
    out = wpautop_texturize_emoji("[block slug=\"x\"]")
    assert ":x" not in out or ":smile:" not in out
    assert 'slug="x"' in out


@pytest.mark.parametrize(
    "body,expected_blocks",
    [
        ("", 0),
        ("تک‌خط", 1),
        ("a\n\nb", 2),
        ("a\n\n\nb", 2),
        ("<h2>h</h2>\n\na", 2),   # the heading itself plus the paragraph
        ("<p>a</p>\n<p>b</p>", 2),
    ],
)
def test_block_count_is_exact(body, expected_blocks):
    out = wpautop(body)
    # A <p> the filter added counts once, whether it was generated or authored.
    assert out.count("<p>") + out.count("</h2>") == expected_blocks


def test_shortcode_token_keeps_its_quotes():
    # A typographed quote inside a shortcode attribute makes the parser read one
    # attribute named slug=“news”, so the token must reach the renderer intact.
    out = wpautop_texturize_emoji('متن\n\n[block slug="news"]')
    assert 'slug="news"' in out
    assert "news”" not in out and "“news" not in out


def test_attribute_quotes_survive():
    out = wpautop_texturize_emoji('<p dir="rtl">سلام</p>')
    assert 'dir="rtl"' in out


def test_a_bare_code_element_is_not_typographed():
    """``<code>`` on its own, with no ``<pre>`` wrapper.

    Found by the guard audit: the existing test wraps the sample in
    ``<pre><code>``, and ``<pre>`` stashes the whole block before ``<code>`` is
    ever considered — so dropping ``code`` from the preserve list changed
    nothing and every test stayed green. Inline code is the case that has no
    ``<pre>`` around it, and it is the one an editor produces when someone
    selects a variable name and formats it.
    """
    out = wpautop_texturize_emoji("<p>Use <code>don't</code> here</p>")
    assert "<code>don't</code>" in out, (
        "a code element was typographed: the straight apostrophe inside it is "
        "literal, not prose, and curly quotes in code break copy-paste"
    )
