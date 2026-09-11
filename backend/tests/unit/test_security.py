"""Unit tests for password hashing and JWT security primitives."""

import uuid

from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
)
from app.core.security.password import hash_password, verify_password


def test_argon2id_password_hashing():
    """Verify password hashing with Argon2id and verification."""
    password = f"Pw!{uuid.uuid4().hex}"
    hashed = hash_password(password)

    # Hash should not be plaintext
    assert hashed != password
    assert hashed.startswith("$argon2")

    # Verification must succeed
    assert verify_password(password, hashed) is True

    # Verification must fail with wrong password
    assert verify_password("WrongPassword999!", hashed) is False


def test_jwt_access_token_creation_and_decoding():
    """Verify JWT access token claims and verification."""
    user_id = str(uuid.uuid4())
    roles = ["customer"]
    permissions = ["orders:read", "cart:write"]

    token = create_access_token(
        subject=user_id,
        extra_claims={
            "roles": roles,
            "permissions": permissions,
        },
    )

    assert isinstance(token, str)
    assert len(token) > 20

    # Verify and decode
    payload = verify_token(token, expected_type="access")
    assert payload["sub"] == user_id
    assert payload["type"] == "access"
    assert payload["roles"] == roles
    assert payload["permissions"] == permissions


def test_jwt_refresh_token_type():
    """Verify refresh token has type 'refresh'."""
    user_id = str(uuid.uuid4())
    refresh_token = create_refresh_token(subject=user_id)

    payload = decode_token(refresh_token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == user_id


def test_production_security_fails_on_placeholder_secret():
    """Verify that in production mode, placeholder secret raises ValueError."""
    import pytest

    from app.core.config.settings import Settings

    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY=f"CHANGE-ME-IN-PRODUCTION-{uuid.uuid4().hex[:8]}",
        )
    assert "Security violation" in str(exc_info.value)
