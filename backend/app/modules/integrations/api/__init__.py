"""Integration API surface.

Discovery rule (``app.main._include_routers``): a module exports ``router``
and/or ``admin_router`` — nothing else is mounted. The public inbound
receiver therefore folds into the module ``router`` (its paths carry the
``/inbound/...`` prefix themselves), while management endpoints hang off the
``admin_router`` alongside the existing outbound-webhook admin.
"""

from app.modules.integrations.api.inbound_webhook_routes import admin_router
from app.modules.integrations.api.inbound_webhook_routes import (
    receiver_router as _inbound_receiver_router,
)
from app.modules.integrations.api.routes import router

# Fold every public sub-router into the one object main.py mounts.
#
# NOTE: the outbound-webhook admin router is deliberately NOT included here.
# ``routes.py`` already mounts it on this same router (it needs the paths for
# its own schema), so adding it again registered every /admin/webhooks/*
# handler twice — the later copy was unreachable while still appearing in the
# OpenAPI schema. Guarded by tests/unit/test_router_integrity.py.
router.include_router(_inbound_receiver_router)

__all__ = ["router", "admin_router"]
