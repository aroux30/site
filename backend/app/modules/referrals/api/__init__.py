"""Referrals API package.

Exports both routers the ``app.main`` loader resolves by name: the public
``router`` (mounted at ``/api/v1/referrals``) and the staff ``admin_router``
(mounted at ``/api/v1`` with its own ``/admin/referrals`` prefix).
"""

from app.modules.referrals.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
