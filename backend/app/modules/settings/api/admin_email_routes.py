"""Admin-email change and review routes (WordPress's ``new_admin_email`` flow).

Kept as its own router module rather than appended to ``routes.py``: that file
is the settings kitchen sink and is being edited concurrently by another
session working in a different area, and a new module is the only merge-safe
place to add routes today. The package ``__init__`` composes both routers, so
the public paths are unchanged.

P1 "کاربران: تغییر ایمیل مدیریتی با تأییدیه و بازبینی دوره‌ای".
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.settings.application.admin_email_service import (
    confirm_admin_email_change,
    confirm_current_admin_email,
    get_admin_email_status,
    request_admin_email_change,
)

router = APIRouter()


class AdminEmailChangeRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    new_email: str = Field(..., min_length=5, max_length=255)


class AdminEmailTokenRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    token: str = Field(..., min_length=8, max_length=500)


@router.get(
    "/settings/admin/admin-email",
    summary="Current, pending and review state of the site admin email (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def admin_email_status(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Everything the settings card needs in one read.

    One call rather than three: the card renders current + pending + review
    together, and a split read can show a pending proposal beside a stale
    "current" value from before it was made.
    """
    return await get_admin_email_status(db)


@router.post(
    "/settings/admin/admin-email/change",
    summary="Propose a new admin email; a confirmation link goes to it (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def request_admin_email_change_route(
    body: AdminEmailChangeRequest,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The address does not move here.

    The confirmation link is mailed to the *new* address and only redeeming it
    moves ``admin_email``. A typo therefore cannot redirect the store's
    password resets to an inbox nobody owns.
    """
    return await request_admin_email_change(
        db, new_email=body.new_email, requested_by=str(actor_id)
    )


@router.post(
    "/settings/admin/admin-email/confirm",
    summary="Redeem the admin-email confirmation token (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def confirm_admin_email_change_route(
    body: AdminEmailTokenRequest,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Admin session AND token required, matching WordPress.

    The token proves the mailbox; the session proves the operator. Either alone
    is weaker than the pair — a forwarded email would otherwise be enough, and
    a stolen session alone cannot redirect the recovery address.
    """
    return await confirm_admin_email_change(
        db, token=body.token, actor_id=str(actor_id)
    )


@router.post(
    "/settings/admin/admin-email/confirm-current",
    summary="Periodic review: this admin email is still correct (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def confirm_current_admin_email_route(
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Records a fresh review timestamp without changing the address."""
    return await confirm_current_admin_email(db, actor_id=str(actor_id))