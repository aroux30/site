import pytest
import pyotp
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.core.security.mfa import (
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code,
    generate_backup_codes,
    get_webauthn_registration_challenge,
)
from app.core.security.casbin_enforcer import get_casbin_enforcer
from app.core.security.rate_limiter import BruteForceProtector


def test_totp_mfa_flow():
    secret = generate_totp_secret()
    assert len(secret) == 32

    uri = get_totp_uri(secret, "user-123", "TestPlatform")
    assert "otpauth://totp/" in uri
    assert "TestPlatform" in uri

    current_code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, current_code) is True
    assert verify_totp_code(secret, "000000") is False

    backup_codes = generate_backup_codes(5)
    assert len(backup_codes) == 5
    for code in backup_codes:
        assert "-" in code
        assert len(code) == 11


def test_webauthn_registration_challenge():
    challenge = get_webauthn_registration_challenge(
        user_id="usr-99", username="testuser"
    )
    assert "challenge" in challenge
    assert challenge["rp"]["name"] == "Iranian E-Commerce Platform"
    assert challenge["user"]["name"] == "testuser"


def test_casbin_enforcement():
    enforcer = get_casbin_enforcer()
    # super_admin can do anything
    assert enforcer.enforce("super_admin", "default", "any_resource", "any_action") is True
    # admin can read/write users
    assert enforcer.enforce("admin", "default", "users", "read") is True
    assert enforcer.enforce("admin", "default", "users", "write") is True
    # customer cannot delete users
    assert enforcer.enforce("customer", "default", "users", "delete") is False


@pytest.mark.asyncio
async def test_bruteforce_protector_lockout():
    mock_redis = AsyncMock()
    protector = BruteForceProtector(max_attempts=3, lockout_seconds=600, window_seconds=600)
    protector.redis = mock_redis

    # Test failure increments
    mock_redis.incr.return_value = 1
    with patch("app.core.security.rate_limiter.get_redis", return_value=mock_redis):
        att = await protector.record_failure("09121234567")
        assert att == 1
        mock_redis.expire.assert_called_once()

    # Test lockout threshold reached (3 attempts)
    mock_redis.incr.return_value = 3
    with patch("app.core.security.rate_limiter.get_redis", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await protector.record_failure("09121234567")
        assert exc_info.value.status_code == 429
        mock_redis.set.assert_called_once()

    # Test check_lockout raises 429 when locked
    mock_redis.get.return_value = "1"
    mock_redis.ttl.return_value = 450
    with patch("app.core.security.rate_limiter.get_redis", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await protector.check_lockout("09121234567")
        assert exc_info.value.status_code == 429
        assert "450 ثانیه" in exc_info.value.detail
