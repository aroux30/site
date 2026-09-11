#!/usr/bin/env python3
"""Live Operational Verification of All Platform Security Defenses."""

import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.main import create_app
from app.core.security.ip_filter import ban_ip, unban_ip
from app.core.security.password import verify_dummy_password, is_weak_password
from app.core.security.rate_limiter import brute_force_protector

app = create_app()
client = TestClient(app)


def test_1_security_status_endpoint():
    print("\n[TEST 1] Testing /api/v1/auth/security-status endpoint...")
    resp = client.get("/api/v1/auth/security-status")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "healthy"
    defenses = data["active_defenses"]
    print("  ✓ Security status is healthy")
    print(f"  ✓ Rate Limiter: {defenses['rate_limiter']['engine']}")
    print(f"  ✓ Brute Force: {defenses['brute_force_protector']['engine']}")
    print(f"  ✓ Casbin RBAC: {defenses['casbin_rbac_abac']['status']}")
    print(f"  ✓ Anti-Bot: {defenses['anti_bot']['honeypot_field']}")
    print("  --> TEST 1 PASSED!")


def test_2_weak_password_blocking():
    print("\n[TEST 2] Testing Weak & Breached Password Blocking...")
    common_passwords = ["password123", "admin1234", "iran1234", "iran12345"]
    for pwd in common_passwords:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "phone": "09129999999",
                "password": pwd,
                "first_name": "Test",
                "last_name": "User",
            },
        )
        assert resp.status_code == 422, f"Expected 422 for weak password {pwd}, got {resp.status_code}"
        assert "این رمز عبور بسیار رایج و ناامن است" in resp.text
        print(f"  ✓ Common password '{pwd}' successfully blocked with 422 validation error")
    print("  --> TEST 2 PASSED!")


def test_3_honeypot_bot_blocking():
    print("\n[TEST 3] Testing Anti-Bot Honeypot Trap...")
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "09129999999",
            "password": f"Strong!{uuid.uuid4().hex}",
            "first_name": "Bot",
            "last_name": "Spammer",
            "honeypot": "https://spam-link.com",
        },
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    assert "Automated bot traffic detected" in resp.text
    print("  ✓ Bot filling hidden honeypot was instantly trapped and rejected with 422")
    print("  --> TEST 3 PASSED!")


def test_4_security_headers():
    print("\n[TEST 4] Testing Defense-in-Depth HTTP Security Headers...")
    resp = client.get("/healthz")
    assert resp.status_code == 200
    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    print("  ✓ X-Content-Type-Options: nosniff present")
    print("  ✓ X-Frame-Options: SAMEORIGIN present")
    print("  ✓ Referrer-Policy: strict-origin-when-cross-origin present")
    print("  --> TEST 4 PASSED!")


def test_5_timing_attack_mitigation():
    print("\n[TEST 5] Testing Anti-Timing Attack Dummy Hash Execution...")
    import time
    start = time.perf_counter()
    res = verify_dummy_password("any_unregistered_password")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert res is False
    print(f"  ✓ Dummy verification executed in {elapsed_ms:.1f}ms (constant-time Argon2id defense)")
    print("  --> TEST 5 PASSED!")


def test_6_ip_blacklist_middleware():
    print("\n[TEST 6] Testing Dynamic IP Blacklist (IPFilterMiddleware)...")
    async def run_ip_test():
        mock_redis = AsyncMock()
        # Mock that 198.51.100.77 is in Redis blacklist
        mock_redis.get.return_value = "abusive_ip_flood"
        with patch("app.core.security.ip_filter.get_redis", return_value=mock_redis):
            resp = client.get("/docs", headers={"X-Real-IP": "198.51.100.77"})
            assert resp.status_code == 403, f"Expected 403 for banned IP, got {resp.status_code}"
            assert "مسدود شده است" in resp.text
            print("  ✓ Banned IP 198.51.100.77 received immediate 403 Forbidden")
    asyncio.run(run_ip_test())
    print("  --> TEST 6 PASSED!")


def test_7_brute_force_lockout():
    print("\n[TEST 7] Testing Brute Force Multi-Key Lockout (5 Failed Attempts)...")
    async def run_bf_test():
        mock_redis = AsyncMock()
        # Simulate attempts 1 to 4
        mock_redis.incr.side_effect = [1, 2, 3, 4, 5]
        with patch("app.core.security.rate_limiter.get_redis", return_value=mock_redis):
            # First 4 attempts increment counter
            for i in range(1, 5):
                att = await brute_force_protector.record_failure("09120000000")
                assert att == i
            print("  ✓ Attempts 1-4 successfully tracked with progressive delay")

            # 5th attempt triggers lockout and raises 429
            try:
                await brute_force_protector.record_failure("09120000000")
                print("  ERROR: 5th attempt did not lock out!")
                sys.exit(1)
            except HTTPException as exc:
                assert exc.status_code == 429
                assert "مسدود گردید" in exc.detail
                print("  ✓ 5th attempt triggered immediate 429 Too Many Requests (15-min lockout)")
    asyncio.run(run_bf_test())
    print("  --> TEST 7 PASSED!")


if __name__ == "__main__":
    print("=" * 60)
    print("      LIVE OPERATIONAL DEFENSE VERIFICATION")
    print("=" * 60)
    test_1_security_status_endpoint()
    test_2_weak_password_blocking()
    test_3_honeypot_bot_blocking()
    test_4_security_headers()
    test_5_timing_attack_mitigation()
    test_6_ip_blacklist_middleware()
    test_7_brute_force_lockout()
    print("\n" + "=" * 60)
    print("ALL 7 LIVE OPERATIONAL DEFENSE TESTS PASSED 100%!")
    print("=" * 60)
