"""Audit API package — exposes the FastAPI router."""

from app.modules.audit.api.routes import router

__all__ = ["router"]
