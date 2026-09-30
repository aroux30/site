"""RBAC API package — exposes the FastAPI router."""

from app.modules.rbac.api.routes import router

__all__ = ["router"]
