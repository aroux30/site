"""Blog API router exports."""

from app.modules.blog.api.routes import admin_router, router

# Imported for its side effect: registers the WordPress-parity routes
# (taxonomies, content types, editorial workflow, import/export, breadcrumbs)
# onto the two routers above. Must come after ``routes`` so the routers exist.
from app.modules.blog.api import wp_parity_routes as _wp_parity_routes  # noqa: E402, F401

__all__ = ["admin_router", "router"]
