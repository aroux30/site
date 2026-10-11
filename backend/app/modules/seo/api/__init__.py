"""SEO API router exports.

The Link Genius routes (internal-link suggestions + keyword maps) are composed
in front of the base SEO routes. Registration order is load-bearing:
``DELETE /admin/seo/link-maps/{id}`` and ``DELETE /admin/seo/{resource_type}/
{resource_id}`` match the same two-segment shape, and FastAPI resolves in
registration order — so the specific Link Genius routes must come first or the
generic metadata-delete handler would answer ``resource_type="link-maps"`` and
silently delete nothing. The same trap is documented for the 404 monitor's
``DELETE /admin/seo/404`` (query-param) route in ``routes.py``.
"""

from fastapi import APIRouter

from app.modules.seo.api.link_genius_routes import (
    admin_router as _link_genius_admin,
)
from app.modules.seo.api.link_genius_routes import (
    public_router as _link_genius_public,
)
from app.modules.seo.api.routes import admin_router as _base_admin
from app.modules.seo.api.routes import router as _base_router

router = APIRouter()
# Public related-posts route first (it is a 3-segment path, but keeping it
# ahead of the generic 2-segment metadata route removes any doubt).
router.include_router(_link_genius_public)
router.include_router(_base_router)

admin_router = APIRouter()
# Link Genius admin routes BEFORE the base admin routes (the shadowing trap).
admin_router.include_router(_link_genius_admin)
admin_router.include_router(_base_admin)

__all__ = ["admin_router", "router"]
