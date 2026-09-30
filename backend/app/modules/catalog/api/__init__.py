"""Catalog API – exposes the ``router`` consumed by the application factory."""

from app.modules.catalog.api.routes import router

__all__ = ["router"]
