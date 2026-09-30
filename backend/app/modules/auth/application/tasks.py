"""Authentication and security background Celery tasks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import structlog
from sqlalchemy import CursorResult, delete

from app.core.database.session import async_session_factory
from app.modules.users.domain.models import OTPRequest, UserSession
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _cleanup_expired_otps_async() -> dict[str, Any]:
    """Delete OTP requests that have expired or are older than 24 hours."""
    now = datetime.now(UTC)
    threshold = now - timedelta(hours=24)

    async with async_session_factory() as db:
        try:
            stmt = delete(OTPRequest).where(
                (OTPRequest.expires_at <= now) | (OTPRequest.created_at <= threshold)
            )
            result = cast("CursorResult[Any]", await db.execute(stmt))
            deleted_otps = int(result.rowcount or 0)

            # Also delete revoked or expired sessions
            session_stmt = delete(UserSession).where(
                (UserSession.is_revoked.is_(True)) | (UserSession.expires_at <= now)
            )
            sess_result = cast("CursorResult[Any]", await db.execute(session_stmt))
            deleted_sessions = int(sess_result.rowcount or 0)

            await db.commit()
            await logger.ainfo(
                "auth_cleanup_complete",
                deleted_otps=deleted_otps,
                deleted_sessions=deleted_sessions,
            )
            return {
                "status": "success",
                "deleted_otps": deleted_otps,
                "deleted_sessions": deleted_sessions,
            }
        except Exception as exc:
            await db.rollback()
            await logger.aerror("auth_cleanup_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}


# Retry policy (audit R5): this task is idempotent (re-running cannot
# duplicate money movement or state transitions), so transient
# DB/Elasticsearch/Redis errors are retried with exponential backoff.
@celery_app.task(
    name="app.modules.auth.application.tasks.cleanup_expired_otps",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def cleanup_expired_otps() -> dict[str, Any]:
    """Celery beat task entrypoint for cleaning up expired OTPs."""
    return asyncio.run(_cleanup_expired_otps_async())
