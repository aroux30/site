"""Audit background Celery tasks.

The reconciliation scan runs on a conservative schedule via Beat. It is
idempotent under at-least-once execution: every finding carries a unique dedupe
key, so a re-run (or two overlapping runs) converges on the same rows and only
bumps ``occurrence_count`` / ``last_detected_at``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.audit.application.lifecycle_auditor import audit_order_lifecycle
from app.modules.audit.application.reconciliation_service import scan
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _reconcile_payments_async() -> dict[str, Any]:
    """Run the read-only reconciliation scanner in its own transaction.

    The scan writes only reconciliation findings (plus the audit trail of any
    lifecycle decision); it never mutates a payment, order, refund, webhook or
    inventory row and never contacts a provider.
    """
    async with async_session_factory() as db:
        try:
            result = await scan(db)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            await logger.aerror("reconciliation_scan_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}

    await logger.ainfo(
        "reconciliation_scan_task_completed",
        detected=result.detected,
        created=result.created,
        updated=result.updated,
        truncated=result.truncated,
    )
    return {
        "status": "success",
        "detected": result.detected,
        "created": result.created,
        "updated": result.updated,
        "truncated": result.truncated,
    }


@celery_app.task(
    name="app.modules.audit.application.tasks.reconcile_payments",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def reconcile_payments() -> dict[str, Any]:
    """Celery task entrypoint: scheduled read-only payment reconciliation scan."""
    return asyncio.run(_reconcile_payments_async())


async def _audit_order_lifecycle_async() -> dict[str, Any]:
    """Run the read-only cross-axis order lifecycle audit in its own transaction.

    It reads orders, shipments and refunds and writes only lifecycle findings.
    No order, shipment, refund, payment or inventory row is ever mutated.
    """
    async with async_session_factory() as db:
        try:
            result = await audit_order_lifecycle(db)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            await logger.aerror("order_lifecycle_audit_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}

    await logger.ainfo(
        "order_lifecycle_audit_task_completed",
        detected=result.detected,
        created=result.created,
        updated=result.updated,
        truncated=result.truncated,
    )
    return {
        "status": "success",
        "detected": result.detected,
        "created": result.created,
        "updated": result.updated,
        "truncated": result.truncated,
    }


@celery_app.task(
    name="app.modules.audit.application.tasks.audit_order_lifecycle",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def audit_order_lifecycle_task() -> dict[str, Any]:
    """Celery task entrypoint: scheduled read-only order lifecycle audit."""
    return asyncio.run(_audit_order_lifecycle_async())
