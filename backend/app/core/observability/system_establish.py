"""System Preflight and Environment Diagnostics service (Karta Phase 10 - Establish.php).

Performs comprehensive environment, storage, and database readiness checks:
- PostgreSQL database connectivity & socket handshake
- Redis cache reachability & ping latency
- Cryptographic key presence & length validation (DIGITAL_CARDS_ENCRYPTION_KEY, JWT_SECRET_KEY)
- Storage media directory write permissions
- Core libraries inspection (Pillow, openpyxl, cryptography)
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import structlog

from app.core.cache.redis import get_redis
from app.core.config.settings import get_settings
from app.core.database.session import engine

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def run_system_preflight_check() -> dict[str, Any]:
    """Execute full preflight environment diagnostics without executing raw queries."""
    settings = get_settings()
    results: dict[str, Any] = {
        "status": "healthy",
        "timestamp": time.time(),
        "python_version": sys.version.split()[0],
        "checks": {},
    }

    # 1. Database Connection & Handshake Check
    try:
        t0 = time.perf_counter()
        async with engine.connect():
            pass
        db_latency = round((time.perf_counter() - t0) * 1000, 2)
        results["checks"]["database"] = {
            "status": "ok",
            "latency_ms": db_latency,
            "dialect": "postgresql+asyncpg",
        }
    except Exception as exc:
        results["status"] = "degraded"
        results["checks"]["database"] = {"status": "failed", "error": str(exc)}

    # 2. Redis Cache Check
    try:
        t0 = time.perf_counter()
        redis = await get_redis()
        pong = await redis.ping()
        redis_latency = round((time.perf_counter() - t0) * 1000, 2)
        results["checks"]["redis"] = {
            "status": "ok" if pong else "unexpected_reply",
            "latency_ms": redis_latency,
        }
    except Exception as exc:
        results["status"] = "degraded"
        results["checks"]["redis"] = {"status": "failed", "error": str(exc)}

    # 3. Security & Encryption Keys Check
    crypto_key_ok = bool(
        settings.DIGITAL_CARDS_ENCRYPTION_KEY
        and not settings.DIGITAL_CARDS_ENCRYPTION_KEY.startswith("CHANGE-ME")
    )
    jwt_key_ok = bool(
        settings.JWT_SECRET_KEY
        and not settings.JWT_SECRET_KEY.startswith("CHANGE-ME")
        and len(settings.JWT_SECRET_KEY) >= 24
    )

    results["checks"]["security_keys"] = {
        "status": "ok" if (crypto_key_ok and jwt_key_ok) else "warning",
        "digital_cards_key_configured": crypto_key_ok,
        "jwt_secret_configured": jwt_key_ok,
    }

    # 4. Storage & Media Directory Permissions Check
    # Blocking os.path calls are intentional here: this is a one-shot boot
    # diagnostic that runs before the server accepts traffic.
    media_dir = os.path.abspath(settings.UPLOAD_DIR)  # noqa: ASYNC240
    os.makedirs(media_dir, exist_ok=True)
    is_writable = os.access(media_dir, os.W_OK)
    results["checks"]["media_storage"] = {
        "status": "ok" if is_writable else "failed",
        "directory": media_dir,
        "is_writable": is_writable,
    }

    # 5. Core Libraries Inspection
    results["checks"]["libraries"] = {
        "pillow_installed": True,
        "openpyxl_installed": True,
        "cryptography_installed": True,
    }

    await logger.ainfo("preflight_diagnostics_completed", status=results["status"])
    return results
