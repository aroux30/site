"""Content API — re-export the router for auto-discovery by main.py."""

from app.modules.content.api.routes import router

__all__ = ["router"]
