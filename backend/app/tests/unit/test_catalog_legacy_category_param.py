"""Legacy ``?category=`` on GET /catalog/products must filter, not vanish.

The storefront and external clients used ``?category=<uuid-or-slug>`` before
the typed ``category_id`` / ``category_slug`` params existed. The route
silently dropped the unknown query parameter, so a category-scoped link
returned the ENTIRE catalog (measured live 2026-10-21: 5,159 rows for every
value, including a slug that does not exist). A filter that answers "all
products" is worse than an error: the page looks like a category page and
shows the whole shop.

These are source pins, matching this project's pin-style tests: they fail if
the parameter is removed from the signature or the parsing block is deleted.
The live behaviour is covered by tests/e2e/product-category-sync.spec.ts.
"""

from __future__ import annotations

from pathlib import Path

ROUTES = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "catalog"
    / "api"
    / "routes.py"
)


def _src() -> str:
    return ROUTES.read_text(encoding="utf-8")


def test_list_products_accepts_legacy_category_param() -> None:
    src = _src()
    assert "category: str | None = Query(" in src, (
        "GET /catalog/products must declare the legacy `category` query "
        "parameter; without it FastAPI ignores the value and the endpoint "
        "returns the whole catalog"
    )


def test_legacy_category_is_parsed_into_typed_filter() -> None:
    src = _src()
    # UUID → category_id, anything else → category_slug. Both branches must
    # exist or one URL form silently stops filtering.
    assert "category_id = uuid.UUID(category.strip())" in src
    assert "category_slug = category.strip()" in src


def test_legacy_category_only_applies_when_typed_params_absent() -> None:
    src = _src()
    # Explicit category_id/category_slug win; the legacy param is a fallback.
    assert "if category and category_id is None and category_slug is None:" in src
