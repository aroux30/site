"""Regression tests for refresh-token reuse detection (TASK P11-04).

Opaque refresh-token values are generated per-run with uuid4 — they are
meaningless fixture identifiers, not credentials.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.handlers import UnauthorizedError
from app.modules.users.domain.models import UserSession


def _opaque_token() -> str:
    return f"rt-fixture-{uuid.uuid4().hex}"


@pytest.mark.asyncio
async def test_revoked_refresh_token_reuse_revokes_all_sessions():
    """Replaying a rotated refresh token must kill every active session."""
    from app.modules.auth.application import auth_service

    user_id = uuid.uuid4()
    revoked_token = _opaque_token()
    revoked_session = UserSession(
        user_id=user_id,
        refresh_token=revoked_token,
        is_revoked=True,  # already rotated once
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    other_active = UserSession(
        user_id=user_id,
        refresh_token=_opaque_token(),
        is_revoked=False,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    db = MagicMock()
    db.flush = AsyncMock()

    # 1st execute: find session by token (revoked included)
    find_result = MagicMock(scalar_one_or_none=MagicMock(return_value=revoked_session))
    # 2nd execute: list the user's still-active sessions
    revoke_result = MagicMock()
    revoke_result.scalars.return_value.all.return_value = [other_active]
    db.execute = AsyncMock(side_effect=[find_result, revoke_result])

    with (
        patch(
            "app.modules.auth.application.auth_service.verify_token",
            return_value={"sub": str(user_id)},
        ),
        patch(
            "app.core.logging.security_audit.log_security_event",
        ) as log_event,
        pytest.raises(UnauthorizedError) as exc,
    ):
        await auth_service.refresh_token(
            db,
            token=revoked_token,
            ip_address="1.2.3.4",
            user_agent="test-agent",
        )

    assert "reuse" in str(exc.value.detail).lower()
    # every other active session of the user was revoked
    assert other_active.is_revoked is True
    log_event.assert_called_once()
    assert log_event.call_args.kwargs["event"] == "auth.refresh_token_reuse_detected"


@pytest.mark.asyncio
async def test_unknown_refresh_token_is_plain_invalid():
    """A token that never existed is just invalid — no reuse alarm."""
    from app.modules.auth.application import auth_service

    db = MagicMock()
    find_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    db.execute = AsyncMock(return_value=find_result)
    db.flush = AsyncMock()

    with (
        patch(
            "app.modules.auth.application.auth_service.verify_token",
            return_value={"sub": str(uuid.uuid4())},
        ),
        patch(
            "app.core.logging.security_audit.log_security_event",
        ) as log_event,
        pytest.raises(UnauthorizedError),
    ):
        await auth_service.refresh_token(db, token=_opaque_token())

    log_event.assert_not_called()
