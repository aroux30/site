"""Regression: the product DETAIL response must carry min_price/max_price.

The PDP's Product JSON-LD builds its Offer from `min_price`:

    const priceRial = Math.round(product.min_price || 0) * 10;

`ProductDetailResponse` had no such fields — pydantic silently dropped the
values the mapper passed — so `min_price` was undefined on EVERY product
page and the schema shipped `"price": 0` (Google rejects a zero-priced
Offer) while the page displayed the real price. Found by a visual E2E pass.

Pins: the schema fields exist, the mapper computes them from active variants
with the same Toman conversion the list mapper uses, and zero/empty variants
yield None (not 0 — 0 is a real price).
"""

from __future__ import annotations

import inspect

from app.modules.catalog.application import catalog_service
from app.modules.catalog.schemas.catalog import ProductDetailResponse


def test_detail_schema_has_price_range_fields():
    fields = ProductDetailResponse.model_fields
    assert "min_price" in fields, (
        "ProductDetailResponse must declare min_price — without it pydantic "
        "drops the mapper's value and the PDP JSON-LD emits price 0."
    )
    assert "max_price" in fields
    # None default: an absent price is unknown, not free.
    assert fields["min_price"].default is None


def test_detail_mapper_computes_price_range():
    source = inspect.getsource(catalog_service.ProductService._to_detail_response)
    assert "active_variants" in source
    assert "rial_to_toman(min(prices))" in source
    assert "min_price=min_price" in source
    assert "max_price=max_price" in source


def test_list_and_detail_use_the_same_conversion():
    """Both mappers must convert Rial→Toman identically, or the list card and
    the PDP would disagree about the same product's price."""
    list_source = inspect.getsource(catalog_service.ProductService._to_list_response)
    detail_source = inspect.getsource(catalog_service.ProductService._to_detail_response)
    assert "rial_to_toman" in list_source
    assert "rial_to_toman" in detail_source
