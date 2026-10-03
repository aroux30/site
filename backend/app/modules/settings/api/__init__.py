"""Settings API package.

Exposes two routers:

* ``router`` — the main settings router, mounted by main.py under
  ``/api/v1/settings``;
* ``admin_router`` — the admin-email change/review routes (WordPress's
  ``new_admin_email`` flow), mounted by main.py under ``/api/v1`` with the
  full ``/settings/admin/...`` path written in the module. It is a separate
  module because ``routes.py`` was being edited by another session when this
  landed, and appending to it would have been the one merge-unsafe thing to do.
"""

from app.modules.settings.api.admin_email_routes import router as admin_router
from app.modules.settings.api.privacy_confirm_routes import router as privacy_confirm_router
from app.modules.settings.api.routes import router as _settings_router

# The privacy email-confirmation routes are composed onto the main router here
# rather than appended to routes.py: that file was being edited by another
# session, and an include from the package is the merge-safe way to add paths
# under the same /settings prefix. `include_router` mutates the target router,
# so the composed result is what main.py mounts.
_settings_router.include_router(privacy_confirm_router)
router = _settings_router

__all__ = ["router", "admin_router"]
