"""Chat API package.

Exports both routers the ``app.main`` loader resolves by name: the public
``router`` (mounted at ``/api/v1/chat``) and the staff ``admin_router``
(mounted at ``/api/v1`` with its own ``/admin/chat`` prefix).
"""

from app.modules.chat.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
