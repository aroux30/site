"""Data-exchange background tasks: async import execution + export generation.

The API enqueues these for large files instead of holding an HTTP request
open; small jobs can still be executed synchronously through the service.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.dataexchange.application import exchange_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _execute_import_async(job_id: str, idempotency_key: str | None) -> dict[str, Any]:
    async with async_session_factory() as db:
        try:
            job = await exchange_service.execute_import_job(
                db, uuid.UUID(job_id), idempotency_key=idempotency_key
            )
            await db.commit()
        except Exception:
            await db.rollback()
            await logger.aexception("dataexchange_execute_task_failed", job_id=job_id)
            raise
    return {"status": "success", "job_id": job_id, "stats": job.stats}


@celery_app.task(
    name="app.modules.dataexchange.application.tasks.execute_import_job_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def execute_import_job_task(job_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
    """Execute a validated import job in the background (idempotent by job status)."""
    return asyncio.run(_execute_import_async(job_id, idempotency_key))


async def _run_export_async(job_id: str) -> dict[str, Any]:
    """Re-run an export job's file generation (used when created async)."""
    from app.modules.dataexchange.application import pipeline
    from app.modules.dataexchange.application.adapters import get_adapter
    from app.modules.dataexchange.domain.models import ExportJob, ExportJobStatus

    async with async_session_factory() as db:
        try:
            job = await db.get(ExportJob, uuid.UUID(job_id))
            if job is None:
                raise ValueError(f"ExportJob {job_id} not found")
            adapter = get_adapter(job.entity_type)
            job.status = ExportJobStatus.PROCESSING
            await db.flush()
            path, row_count = await pipeline.run_export(db, adapter, job.filters or {})
            job.result_path = path
            job.row_count = row_count
            job.status = ExportJobStatus.COMPLETED
            await db.commit()
        except Exception:
            await db.rollback()
            await logger.aexception("dataexchange_export_task_failed", job_id=job_id)
            raise
    return {"status": "success", "job_id": job_id, "row_count": row_count}


@celery_app.task(
    name="app.modules.dataexchange.application.tasks.run_export_job_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def run_export_job_task(job_id: str) -> dict[str, Any]:
    """Generate an export CSV in the background."""
    return asyncio.run(_run_export_async(job_id))
