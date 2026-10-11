"""Regression: generated SEO defaults must NOT carry a schema_markup stub.

The storefront's product layout picks `schemaOverride ?? buildProductJsonLd`.
The default-generation branch used to return a name+description-only stub in
`schema_markup` for products with no stored row — so the stub beat the rich
built-in node and every product page silently lost its offers/price/
availability rich result. A generated default is not an operator override;
only a stored row carries schema_markup.

Sabotage check (textual): restoring `schema_markup=schema` in the product or
post branch makes the assertions below fail.
"""

from __future__ import annotations

import inspect

from app.modules.seo.application import seo_service


def _source() -> str:
    return inspect.getsource(seo_service.SEOService._generate_default_seo)


def test_product_default_generation_returns_no_schema_markup():
    source = _source()
    # The product branch must pass schema_markup=None. The stub construction
    # (`schema = {..."@type": "Product"...}`) must not exist at all.
    assert '"@type": "Product"' not in source, (
        "The product default branch must not build a schema stub — it would "
        "shadow the storefront's rich Product node (offers/price)."
    )
    assert '"@type": "Article"' not in source, (
        "The post default branch must not build a schema stub either."
    )


def test_default_generation_never_returns_stored_shaped_markup():
    """Every SEOMetadataResponse in the default branch passes schema_markup=None."""
    source = _source()
    # No assignment of a dict to schema_markup in this method.
    assert "schema_markup=schema" not in source
    assert "schema_markup={" not in source
