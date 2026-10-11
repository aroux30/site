"""Tests for the Rank Math-style meta template engine.

The engine renders ``%title% %sep% %sitename%``-style templates. The failure
modes these tests pin:

- An unknown variable must render EMPTY, not as the literal token — shipping
  ``%unknown%`` into a meta tag is a visible defect on every page.
- A template that renders only whitespace/separators must fall back to the
  caller's default — an empty meta title is worse than a generic one.
- Case wrappers (``%uppercase(%title%)%``... in Rank Math's syntax
  ``%uppercase(x)%``) apply to the wrapped value.
- A resolver that raises must not take the page down.
"""

from __future__ import annotations

import pytest

from app.modules.seo.application.template_engine import (
    VARIABLE_CATALOG,
    TemplateEngine,
    build_variables,
)


def engine(**overrides) -> TemplateEngine:
    base = dict(
        title="راهنمای خرید",
        sitename="فروشگاه من",
        separator="|",
        sitedesc="یک سایت فروشگاهی",
        category="آموزش",
        focus_keyword="خرید آنلاین",
    )
    base.update(overrides)
    return TemplateEngine(build_variables(**base))


def test_standard_title_template():
    result = engine().render_or_default("%title% %sep% %sitename%", "پیش‌فرض")
    assert result == "راهنمای خرید | فروشگاه من"


def test_unknown_variable_renders_empty_not_literal():
    """The literal token must never reach a meta tag."""
    result = engine().render("%title% %nope%")
    assert "%nope%" not in result
    assert result.strip() == "راهنمای خرید"


def test_empty_variable_collapses_separators():
    """`%title% %sep% %category%` with no category must not leave 'Foo | |'."""
    e = engine(category=None)
    result = e.render_or_default("%title% %sep% %category%", "پیش‌فرض")
    # Category renders empty; the doubled separator collapses.
    assert "| |" not in result
    assert result.startswith("راهنمای خرید")


def test_meaningless_render_falls_back_to_default():
    """A template of pure separators is empty for practical purposes."""
    assert engine().render_or_default("%sep%", "پیش‌فرض") == "پیش‌فرض"
    assert engine().render_or_default("  |  ", "پیش‌فرض") == "پیش‌فرض"


def test_case_wrappers():
    e = engine()
    assert e.render("%uppercase(%title%)%") == "راهنمای خرید".upper()
    assert e.render("%lowercase(%sitename%)%") == "فروشگاه من".lower()


def test_ucwords_wrapper():
    e = engine(title="hello world example")
    assert e.render("%ucwords(%title%)%") == "Hello World Example"


def test_customfield_parameter():
    e = TemplateEngine(
        build_variables(custom_fields={"brand": "ایسوس"})
    )
    assert e.render("%customfield(brand)%") == "ایسوس"
    # Unknown key → empty, not the token.
    assert e.render("%customfield(nope)%") == ""


def test_term_parameter():
    e = TemplateEngine(build_variables(terms={"product_cat": "لپ‌تاپ"}))
    assert e.render("%term(product_cat)%") == "لپ‌تاپ"
    assert e.render("%term(unknown)%") == ""


def test_raising_resolver_renders_empty():
    """A broken resolver must not 500 the page."""
    variables = {"boom": lambda _p: (_ for _ in ()).throw(RuntimeError("x"))}
    e = TemplateEngine(variables)
    assert e.render("A%boom%B") == "AB"


def test_randomword_resolver_used():
    e = TemplateEngine(build_variables(random_words=lambda _p: "شعبه۱"))
    assert e.render("%randomword(الف|ب)%") == "شعبه۱"


def test_persian_text_survives_untouched():
    e = engine(title="راهنمای کامل پابجی موبایل ۲۰۲۵")
    result = e.render("%title% %sep% %sitename%")
    assert "پابجی موبایل ۲۰۲۵" in result


def test_catalog_variables_all_render():
    """Every variable the settings UI offers must resolve (or empty), never
    raise — the catalog and the vocabulary cannot drift apart."""
    e = engine()
    for entry in VARIABLE_CATALOG:
        template = entry["name"]
        # Strip the ellipsis form down to something renderable.
        template = template.replace("...", "title")
        rendered = e.render(template)
        assert "%" not in rendered, f"{entry['name']} leaked a literal token"


def test_variable_catalog_is_nonempty_and_has_examples():
    assert len(VARIABLE_CATALOG) >= 20
    for entry in VARIABLE_CATALOG:
        assert entry["name"].startswith("%") and entry["name"].endswith("%")
        assert entry["label"]
