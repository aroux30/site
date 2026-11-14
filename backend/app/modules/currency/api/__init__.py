"""Currency module API.

Exposes ``admin_router`` (staff settings + history). The public ``router``
name is absent on purpose — nothing about the updater is customer-facing;
``app/main.py`` mounts ``admin_router`` when a module has no ``router``.
"""

from app.modules.currency.api.routes import admin_router

__all__ = ["admin_router"]
