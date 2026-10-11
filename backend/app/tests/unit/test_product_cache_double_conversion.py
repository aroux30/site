"""Regression: the product cache round-trip must not convert prices twice.

`VariantResponse` field validators convert Rial→Toman. The by-slug route
cached `model_dump_json()` — a response whose prices were ALREADY Toman —
and replayed it through `model_validate_json()`, which re-ran the
validators: every cache hit divided variant prices by 10 again (found by a
visual E2E pass: the PDP displayed 1,000 تومان for a 10,000-Toman variant
while the JSON-LD — built from min_price, computed fresh — said 10,000).

The fix: the cache replay passes `context={"already_toman": True}`, which
tells the validators to skip the conversion. These tests pin both
directions: raw Rial still converts, cached Toman passes through unchanged.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from app.modules.catalog.schemas.catalog import VariantResponse


def _variant_json(price: int) -> str:
    return json.dumps(
        {
            "id": str(uuid.uuid4()),
            "product_id": str(uuid.uuid4()),
            "sku": "T-1",
            "price": price,
            "compare_at_price": price * 2,
            "cost": None,
            "weight": None,
            "is_active": True,
            "position": 0,
            "attributes": None,
            "available": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )


def test_raw_rial_still_converts():
    """A fresh response built from the ORM (Rial) must divide by 10."""
    v = VariantResponse.model_validate_json(_variant_json(100_000))
    assert v.price == 10_000
    assert v.compare_at_price == 20_000


def test_cache_replay_does_not_convert_again():
    """The cached payload is already Toman — replay must leave it alone."""
    v = VariantResponse.model_validate_json(
        _variant_json(10_000), context={"already_toman": True}
    )
    assert v.price == 10_000, (
        "cache replay re-ran the Rial→Toman validator — the exact 10x bug "
        "this flag exists to prevent"
    )
    assert v.compare_at_price == 20_000


def test_route_passes_already_toman_context():
    """Source-level: the cache-hit branch must pass the context flag."""
    import inspect

    from app.modules.catalog.api import routes as catalog_routes

    source = inspect.getsource(catalog_routes.get_product_by_slug)
    assert 'already_toman' in source, (
        "the cache replay must pass context={'already_toman': True}, or "
        "every cache hit divides prices by 10 again"
    )
    # And the cache key must be versioned so poisoned entries are not replayed.
    assert "slug:v2:" in source


def test_validators_read_the_context_flag():
    """All three money validators must honour the flag — missing one leaves a
    field converting twice while its siblings do not."""
    import inspect

    from app.modules.catalog.schemas import catalog as catalog_schemas

    source = inspect.getsource(catalog_schemas.VariantResponse)
    assert source.count("already_toman") >= 3
