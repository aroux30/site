"""Integration API surface.

Discovery rule (``app.main._include_routers``): a module exports ``router``
and/or ``admin_router`` — nothing else is mounted. This module exports only
``router`` (capability registry endpoints).
"""

from app.modules.integrations.api.routes import router

__all__ = ["router"]
