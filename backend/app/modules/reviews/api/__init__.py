"""Reviews module API – exposes ``router`` for inclusion in the app."""

from app.modules.reviews.api.routes import router

__all__ = ["router"]
