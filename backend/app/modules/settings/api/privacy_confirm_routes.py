"""Email confirmation for data-subject requests (WordPress ``wp_send_user_request``).

Kept as its own router module rather than appended to ``routes.py``: that file
is the settings kitchen sink, and a new module is the merge-safe place to add
routes while other sessions work elsewhere in it. Composed into the package
``router`` by ``__init__``, so the public paths are unchanged.

P1 "حریم خصوصی: جریان ایمیلی تأیید درخواست".
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id

router = APIRouter()


class PrivacyRequestEmailConfirmRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    token: str = Field(..., min_length=8, max_length=500)


@router.post(
    "/privacy/requests/{request_id}/send-email-confirmation",
    summary="Email a confirmation link for one of your own requests",
)
async def send_privacy_email_confirmation(
    request_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mail a confirmation link to the account's address.

    The second path beside the SMS OTP: a subject whose number changed, or who
    is travelling without their SIM, otherwise cannot confirm their own
    request. Owner-scoped like every other method on the service — the subject
    comes from the token, never from the path.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    return await PrivacyRequestService.issue_email_confirmation(
        db, user_id=user_id, request_id=request_id
    )


@router.post(
    "/privacy/requests/confirm-by-email",
    summary="Confirm a request with the emailed token (no session required)",
)
async def confirm_privacy_request_by_email(
    body: PrivacyRequestEmailConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Redeem an emailed confirmation link.

    Unauthenticated on purpose, like the email-change confirmation: the token
    was mailed to the account's own address, so possession is the proof, and
    requiring a session would break the flow for anyone confirming from a
    device that is not signed in. High-entropy, stored hashed, single-use.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    request = await PrivacyRequestService.confirm_by_email_token(db, token=body.token)
    return {
        "id": str(request.id),
        "type": request.type.value if hasattr(request.type, "value") else str(request.type),
        "status": (
            request.status.value if hasattr(request.status, "value") else str(request.status)
        ),
        "confirmed_at": request.confirmed_at.isoformat() if request.confirmed_at else None,
    }