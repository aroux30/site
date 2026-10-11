"""Checkout API — re-export the router for auto-discovery by ``main.py``.

The tax-engine admin router that used to be exposed here as ``admin_router``
was removed on 2026-10-09 with the whole rule engine (owner's single-rate
decision: the settings field is the only tax authority).
"""

from app.modules.checkout.api.routes import router

__all__ = ["router"]
