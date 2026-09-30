"""Reporting API package.

The module's routes are all admin-scoped (``/admin/reports/*`` and
``/admin/saved-reports/*``), so they are exposed as ``admin_router`` — the
router registry mounts it directly under the API prefix, same as the tax
module's ``/admin/tax`` router. ``router`` is an intentionally empty public
router: reports are admin-only by design.
"""

from app.modules.reporting.api.routes import public_router as router
from app.modules.reporting.api.routes import router as admin_router

__all__ = ["admin_router", "router"]
