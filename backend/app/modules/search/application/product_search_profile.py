"""Product search field weights, shared by every product search builder.

The product index has two consumers — the plain search service and the
faceted one — and the profile was duplicated byte-for-byte between them. Any
weighting change therefore had to be made twice, and nothing stopped the two
from drifting: `frontend/app/(store)/search/page.tsx` calls the plain
`GET /catalog/products`, not the faceted endpoint, so a change to the faceted
copy never reached the page customers actually use.

Both now build from :data:`PRODUCT_SEARCH_FIELDS` and :data:`PRODUCT_FUZZINESS`.
"""

from __future__ import annotations

from typing import Any

#: Boosted field profile. `name` outranks everything (a shopper types the
#: product name), then tags and brand, then description and category.
PRODUCT_SEARCH_FIELDS: list[str] = [
    "name^3",
    "description",
    "tags^2",
    "brand_name^2",
    "category_name",
]

PRODUCT_FUZZINESS = "AUTO"
#: One leading character excluded from fuzziness so a single-letter query does
#: not match the whole catalogue.
PRODUCT_PREFIX_LENGTH = 2
PRODUCT_MINIMUM_SHOULD_MATCH = "75%"


def product_multi_match(query: str) -> dict[str, Any]:
    """The shared ``multi_match`` clause for a product text query."""
    return {
        "multi_match": {
            "query": query,
            "fields": list(PRODUCT_SEARCH_FIELDS),
            "type": "best_fields",
            "fuzziness": PRODUCT_FUZZINESS,
            "prefix_length": PRODUCT_PREFIX_LENGTH,
            "minimum_should_match": PRODUCT_MINIMUM_SHOULD_MATCH,
        },
    }
