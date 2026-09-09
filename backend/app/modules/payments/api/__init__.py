"""Payment API package – exports the router for inclusion in the app."""

from app.modules.payments.api.routes import router

__all__ = ["router"]
