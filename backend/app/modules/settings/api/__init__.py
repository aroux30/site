"""Settings API package.

Exposes one router, ``router``, mounted by main.py under
``/api/v1/settings``. The separate ``admin_router`` (WordPress's
``new_admin_email`` change/review flow) was removed on 2026-10-07 with the
rest of the email feature; ``admin_router`` is no longer exported.
"""

from app.modules.settings.api.routes import router as _settings_router

router = _settings_router

__all__ = ["router"]
