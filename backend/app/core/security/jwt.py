"""JWT access / refresh token creation and verification.

Tokens use HS256 by default and carry a ``sub`` (subject / user-id),
``type`` (access | refresh), and standard ``exp`` / ``iat`` claims.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import UnauthorizedError

settings = get_settings()

_ALGORITHM = settings.JWT_ALGORITHM
_SECRET = settings.JWT_SECRET_KEY


def create_access_token(
    subject: UUID | str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived access JWT."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def create_refresh_token(
    subject: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived refresh JWT."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode *without* verifying token type.

    Raises ``UnauthorizedError`` on any JWT issue.
    """
    try:
        payload: dict[str, Any] = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise UnauthorizedError(detail="Token has expired") from None
    except JWTError:
        raise UnauthorizedError(detail="Invalid token") from None


def verify_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    """Decode *and* enforce token type (``access`` or ``refresh``)."""
    payload = decode_token(token)
    if payload.get("type") != expected_type:
        raise UnauthorizedError(detail=f"Expected {expected_type} token")
    return payload
