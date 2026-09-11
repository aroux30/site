"""Casbin RBAC/ABAC Policy Enforcement Service.

Provides standard Casbin enforcer initialization, policy loading,
and a FastAPI dependency for route-level policy gating.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import casbin
from fastapi import Depends, HTTPException, status

from app.core.security.dependencies import get_current_active_user

logger = logging.getLogger("security.casbin")

_CURRENT_DIR = Path(__file__).resolve().parent
_MODEL_PATH = str(_CURRENT_DIR / "rbac_model.conf")
_POLICY_PATH = str(_CURRENT_DIR / "rbac_policy.csv")

_enforcer: casbin.Enforcer | None = None


def get_casbin_enforcer() -> casbin.Enforcer:
    """Return the singleton Casbin Enforcer instance."""
    global _enforcer  # noqa: PLW0603
    if _enforcer is None:
        try:
            _enforcer = casbin.Enforcer(_MODEL_PATH, _POLICY_PATH)
            logger.info("Casbin enforcer initialized successfully")
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to initialize Casbin enforcer: %s", exc)
            raise
    return _enforcer


class RequireCasbinPolicy:
    """FastAPI dependency to enforce Casbin permissions.

    Evaluates whether the user (or any of their roles) has permission
    to execute *action* on *resource* within *domain*.

    Usage::

        @router.get("/reports", dependencies=[Depends(RequireCasbinPolicy("analytics", "read"))])
        async def get_reports(): ...
    """

    def __init__(self, resource: str, action: str, domain: str = "default") -> None:
        self.resource = resource
        self.action = action
        self.domain = domain

    async def __call__(
        self,
        payload: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        user_id = str(payload.get("sub", ""))
        roles: list[str] = payload.get("roles", [])
        is_superuser: bool = bool(payload.get("is_superuser", False))

        # Superusers bypass policy checks
        if is_superuser or "super_admin" in roles:
            return payload

        enforcer = get_casbin_enforcer()

        # 1. Check direct user ID
        if enforcer.enforce(user_id, self.domain, self.resource, self.action):
            return payload

        # 2. Check each role the user holds
        for role in roles:
            if enforcer.enforce(role, self.domain, self.resource, self.action):
                return payload

        logger.warning(
            "Casbin policy denied: user=%s roles=%s resource=%s action=%s",
            user_id,
            roles,
            self.resource,
            self.action,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"عدم دسترسی: شما مجوز انجام عملیات '{self.action}' روی بخش '{self.resource}' را ندارید.",
        )
