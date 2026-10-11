"""Regression: faceted search must fall back to Postgres, not degrade to zero.

The storefront product grid renders "۰ کالا" while the DB holds 5,146 active
products — that was the shipped behavior when Elasticsearch is unreachable
(memory: storefront-lists-zero-products), and it blocks every downstream flow
(cart, checkout) that starts from the grid.

The fix: `faceted_product_search(request, db=...)` answers from Postgres when
the ES call raises, with `degraded=True` still flagging the loss of relevance
ranking. These tests pin:

- The fallback is invoked when ES fails AND a db is supplied.
- The fallback applies the query + the filters it can honour (category, brand,
  price range in Toman→Rial conversion).
- No db → the old degraded-empty answer (no crash).
- The result is flagged degraded (the UI surfaces "simplified mode").
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.modules.search.application import faceted_search_service as fss
from app.modules.search.schemas.faceted import FacetedSearchRequest


class _BoomES:
    async def search(self, body: Any) -> Any:  # noqa: ANN401
        raise ConnectionError("ES is down")


class _Row:
    """Minimal product-shaped row for the stub session."""

    def __init__(self) -> None:
        import uuid

        self.id = uuid.uuid4()
        self.name = "کالای تست"
        self.slug = "test-product"
        self.description = None
        self.short_description = None
        self.category = None
        self.brand = None
        self.variants: list[Any] = []
        self.is_active = True
        self.is_featured = False


class _ExecResult:
    def __init__(self, rows: list[Any], scalar: Any = None) -> None:
        self._rows = rows
        self._scalar = scalar

    def scalar_one(self) -> Any:  # noqa: ANN401
        return self._scalar if self._scalar is not None else len(self._rows)

    def unique(self) -> "_ExecResult":
        return self

    def scalars(self) -> "_ExecResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _DbStub:
    """Answers the count query with a fixed number and the page query with rows."""

    def __init__(self, total: int = 5146, rows: list[Any] | None = None) -> None:
        self.total = total
        self.rows = rows if rows is not None else [_Row()]
        self.queries: list[str] = []

    async def execute(self, stmt: Any) -> _ExecResult:  # noqa: ANN401
        sql = str(stmt)
        self.queries.append(sql)
        if "count" in sql.lower():
            return _ExecResult([], scalar=self.total)
        if "product_images" in sql:
            return _ExecResult([])
        return _ExecResult(self.rows)


@pytest.mark.asyncio
async def test_es_failure_with_db_uses_postgres_fallback():
    svc = fss.FacetedSearchService(es=_BoomES())  # type: ignore[arg-type]
    db = _DbStub(total=5146)
    result = await svc.faceted_product_search(
        FacetedSearchRequest(page=1, size=3), db=db
    )
    assert result.degraded is True, "the loss of relevance ranking must be flagged"
    assert result.total == 5146, "the DB total must replace the zero"
    assert len(result.hits) == 1  # the stub returns one row
    assert result.hits[0].name == "کالای تست"
    # The fallback ran SQL against Postgres (count + page queries).
    assert any("products" in q for q in db.queries)


@pytest.mark.asyncio
async def test_es_failure_without_db_keeps_old_degraded_empty():
    svc = fss.FacetedSearchService(es=_BoomES())  # type: ignore[arg-type]
    result = await svc.faceted_product_search(FacetedSearchRequest(page=1, size=3))
    assert result.degraded is True
    assert result.total == 0
    assert result.hits == []


@pytest.mark.asyncio
async def test_fallback_facets_empty_not_fabricated():
    svc = fss.FacetedSearchService(es=_BoomES())  # type: ignore[arg-type]
    result = await svc.faceted_product_search(
        FacetedSearchRequest(page=1, size=3), db=_DbStub()
    )
    assert result.facets == [], (
        "facet counts the SQL path cannot compute must be empty, never fabricated"
    )


def test_fallback_converts_toman_to_rial_for_price_filter():
    """Price filter arrives in Toman; the DB stores Rial — the fallback must
    convert (memory: money-unit-two-conventions), or a 5M-Toman cap would
    match nothing."""
    source = inspect.getsource(fss.FacetedSearchService._postgres_fallback)
    assert "toman_to_rial" in source


def test_fallback_covers_category_brand_query():
    source = inspect.getsource(fss.FacetedSearchService._postgres_fallback)
    assert "category_id" in source
    assert "brand" in source
    assert "ilike" in source


def test_route_passes_db_to_service():
    """The route must supply the session — without it the fallback can never
    run and the grid degrades to zero again."""
    from app.modules.search.api import routes as search_routes

    source = inspect.getsource(search_routes.faceted_search)
    assert "db=db" in source


def test_count_uses_subquery_column_not_product_id():
    """The count must reference the SUBQUERY's id column.

    `select(func.count(func.distinct(Product.id))).select_from(base.subquery())`
    re-adds the whole products table to the outer FROM (cartesian join), so
    the count silently ignored every filter — observed live: a 50k-Toman
    price cap still returned all rows. The compiled SQL contained
    `FROM (...) AS anon_1, products`, which is the exact shape this test
    forbids at the source level.
    """
    source = inspect.getsource(fss.FacetedSearchService._postgres_fallback)
    assert "sub.c.id" in source, (
        "count must use the subquery's id column (sub.c.id); using "
        "Product.id re-adds the full table and drops the filters"
    )
    assert "count(sa_func.distinct(Product.id))" not in source
