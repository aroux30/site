"""JWT access / refresh token creation and verification.

Tokens use HS256 by default and carry a ``sub`` (subject / user-id),
``type`` (access | refresh), and standard ``exp`` / ``iat`` claims.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

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
        "jti": uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    # python-jose is untyped; encode() returns a plain str at runtime.
    return cast("str", jwt.encode(payload, _SECRET, algorithm=_ALGORITHM))


def create_refresh_token(
    subject: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived refresh JWT.

    Carries a unique ``jti`` claim so two tokens minted within the same
    second (same ``iat``/``exp``) are never identical — required because the
    session table enforces uniqueness on the stored refresh-token value.
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": uuid4().hex,
    }
    # python-jose is untyped; encode() returns a plain str at runtime.
    return cast("str", jwt.encode(payload, _SECRET, algorithm=_ALGORITHM))


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


def create_recovery_token(
    cart_id: UUID | str,
    user_id: UUID | str,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived, single-purpose bearer JWT that authorizes access
    to exactly one cart. Carries no claim beyond the cart and its owner so a
    leaked link cannot act on any other resource.
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.CART_RECOVERY_TOKEN_TTL_DAYS)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "recovery",
        "cart_id": str(cart_id),
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": uuid4().hex,
    }
    return cast("str", jwt.encode(payload, _SECRET, algorithm=_ALGORITHM))


def verify_recovery_token(token: str) -> tuple[UUID, UUID]:
    """Verify a recovery token and return ``(cart_id, user_id)``.

    Any token issue — bad signature, expiry, wrong type — is rejected the same
    way, so the endpoint cannot be probed into revealing which carts exist.
    """
    payload = verify_token(token, expected_type="recovery")
    cart_id = payload.get("cart_id")
    sub = payload.get("sub")
    if not cart_id or not sub:
        raise UnauthorizedError(detail="Invalid recovery token")
    return UUID(str(cart_id)), UUID(str(sub))
