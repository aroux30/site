"""Accounting API routers (admin-only surface in v1)."""

from app.modules.accounting.api.routes import admin_router

__all__ = ["admin_router"]
