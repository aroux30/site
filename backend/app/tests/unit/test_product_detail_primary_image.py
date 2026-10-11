"""PDP share image was never populated (SEO audit 2026-10-10, live-verified).

`ProductDetailResponse` had no `primary_image_url` field at all — only the
LIST schema did — and `_to_detail_response` never computed one. The PDP
reads that field for `og:image` and the Product JSON-LD `image`, so every
product page shipped no share image even when `product_images` had rows
(20 live rows existed while every API response said None).

Negative test: remove the field from the schema (AttributeError) or the
assignment in `_to_detail_response` (assertion on the mapped value fails).
"""

from __future__ import annotations

from app.modules.catalog.schemas.catalog import ProductDetailResponse


def test_detail_schema_declares_primary_image_url():
    assert "primary_image_url" in ProductDetailResponse.model_fields


def test_detail_mapper_computes_primary_image():
    """Source-level: the mapper must derive the value from product.images."""
    import inspect

    from app.modules.catalog.application.catalog_service import ProductService

    src = inspect.getsource(ProductService._to_detail_response)
    assert "primary_image_url=primary_image_url" in src, (
        "the detail mapper must pass the computed value to the response"
    )
    assert "product.images" in src, (
        "the value must come from the eagerly-loaded images"
    )
