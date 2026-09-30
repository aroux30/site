"""Checkout API — re-export the router for auto-discovery by ``main.py``.

Also exposes ``admin_router`` (tax engine v1 admin endpoints); ``main.py``
auto-mounts it under the API prefix when present.
"""

from app.modules.checkout.api.routes import router
from app.modules.checkout.api.tax_routes import router as admin_router

__all__ = ["router", "admin_router"]
