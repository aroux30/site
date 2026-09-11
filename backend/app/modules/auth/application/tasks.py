"""Authentication and security background Celery tasks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete

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
            result = await db.execute(stmt)
            deleted_otps = result.rowcount

            # Also delete revoked or expired sessions
            session_stmt = delete(UserSession).where(
                (UserSession.is_revoked.is_(True)) | (UserSession.expires_at <= now)
            )
            sess_result = await db.execute(session_stmt)
            deleted_sessions = sess_result.rowcount

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


@celery_app.task(name="app.modules.auth.application.tasks.cleanup_expired_otps")
def cleanup_expired_otps() -> dict[str, Any]:
    """Celery beat task entrypoint for cleaning up expired OTPs."""
    return asyncio.run(_cleanup_expired_otps_async())
