"""Orchestration service: ImportJob / ExportJob lifecycle over the pipeline.

State machine (import):
    draft -> mapping -> validating -> ready -> importing -> completed|failed

Every transition is guarded so the API can never run steps out of order, and
``execute`` honours the job's idempotency key: re-executing a completed job
is a no-op that returns the stored stats instead of re-upserting 5,000 rows.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.dataexchange.application.adapters import get_adapter, list_entity_types
from app.modules.dataexchange.application import pipeline
from app.modules.dataexchange.domain.models import (
    ExportJob,
    ExportJobStatus,
    ImportJob,
    ImportJobStatus,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Import job CRUD + transitions
# ---------------------------------------------------------------------------


async def create_import_job(
    db: Any,
    *,
    entity_type: str,
    file_bytes: bytes,
    filename: str,
    created_by: uuid.UUID | None,
) -> ImportJob:
    adapter = get_adapter(entity_type)  # raises for unknown entity types
    headers, rows = pipeline.parse_upload(file_bytes, filename)
    stored_path = pipeline.store_upload(file_bytes, filename)
    job = ImportJob(
        entity_type=adapter.entity_type,
        status=ImportJobStatus.DRAFT,
        original_filename=filename or "upload",
        stored_file_path=stored_path,
        detected_headers=headers,
        stats={"total": len(rows), "valid": 0, "invalid": 0, "imported": 0, "skipped": 0},
        created_by=created_by,
    )
    db.add(job)
    await db.flush()
    await logger.ainfo(
        "dataexchange_import_created",
        job_id=str(job.id),
        entity_type=entity_type,
        rows=len(rows),
    )
    return job


async def get_import_job(db: Any, job_id: uuid.UUID) -> ImportJob:
    job = await db.get(ImportJob, job_id)
    if job is None:
        raise NotFoundError("ImportJob")
    return job


async def list_import_jobs(
    db: Any, *, entity_type: str | None = None, page: int = 1, page_size: int = 20
) -> tuple[list[ImportJob], int]:
    conditions = []
    if entity_type:
        conditions.append(ImportJob.entity_type == entity_type)
    total = (
        await db.execute(select(func.count()).select_from(ImportJob).where(*conditions))
    ).scalar() or 0
    stmt = (
        select(ImportJob)
        .where(*conditions)
        .order_by(ImportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def set_mapping(db: Any, job_id: uuid.UUID, mapping: dict[str, str]) -> ImportJob:
    job = await get_import_job(db, job_id)
    if job.status not in (ImportJobStatus.DRAFT, ImportJobStatus.MAPPING):
        raise ConflictError(detail="مرحله نگاشت ستون‌ها در این وضعیت قابل تغییر نیست")
    adapter = get_adapter(job.entity_type)
    known = set(adapter.column_keys)
    unknown = [v for v in mapping.values() if v and v not in known]
    if unknown:
        raise ValidationError(f"ستون‌های ناشناخته در نگاشت: {', '.join(unknown)}")
    mapped = {v for v in mapping.values() if v}
    missing = [k for k in adapter.required_keys if k not in mapped]
    if missing:
        labels = {c.key: c.label for c in adapter.columns}
        raise ValidationError(
            "ستون‌های الزامی نگاشت نشده‌اند: " + "، ".join(labels[k] for k in missing)
        )
    job.column_mapping = mapping
    job.status = ImportJobStatus.MAPPING
    await db.flush()
    return job


async def validate_import_job(db: Any, job_id: uuid.UUID) -> ImportJob:
    """Dry run: coerce + validate every row, persist stats and error report."""
    job = await get_import_job(db, job_id)
    if job.status not in (ImportJobStatus.MAPPING, ImportJobStatus.READY):
        raise ConflictError(detail="قبل از اعتبارسنجی، نگاشت ستون‌ها را کامل کنید")
    adapter = get_adapter(job.entity_type)
    job.status = ImportJobStatus.VALIDATING
    await db.flush()

    _headers, rows = pipeline.parse_job_file(job)
    mapped = pipeline.apply_mapping(rows, job.column_mapping or {})
    valid, errors, stats = pipeline.validate_rows(mapped, adapter)
    job.stats = stats
    job.error_report_path = pipeline.write_error_report(job.id, errors)
    job.status = ImportJobStatus.READY if stats["invalid"] == 0 else ImportJobStatus.MAPPING
    await db.flush()
    await logger.ainfo(
        "dataexchange_import_validated",
        job_id=str(job.id),
        valid=stats["valid"],
        invalid=stats["invalid"],
    )
    return job


async def execute_import_job(
    db: Any, job_id: uuid.UUID, *, idempotency_key: str | None = None
) -> ImportJob:
    """Run the import. Idempotent: a completed job returns stored stats.

    Validation is re-run at execute time so rows are never upserted from a
    stale dry-run (file on disk cannot change, but the adapter or DB can).
    """
    job = await get_import_job(db, job_id)
    if job.status == ImportJobStatus.COMPLETED:
        return job  # idempotent no-op
    if job.status == ImportJobStatus.IMPORTING:
        raise ConflictError(detail="این job در حال اجراست")
    if job.status not in (ImportJobStatus.MAPPING, ImportJobStatus.READY, ImportJobStatus.FAILED):
        raise ConflictError(detail="job در وضعیت قابل اجرا نیست")
    adapter = get_adapter(job.entity_type)

    if idempotency_key:
        job.idempotency_key = idempotency_key
    job.status = ImportJobStatus.IMPORTING
    await db.flush()

    try:
        _headers, rows = pipeline.parse_job_file(job)
        mapped = pipeline.apply_mapping(rows, job.column_mapping or {})
        valid, validation_errors, stats = pipeline.validate_rows(mapped, adapter)
        exec_stats, exec_errors = await pipeline.execute_import(db, job, adapter, valid)
        exec_stats.update({"valid": stats["valid"], "invalid": stats["invalid"], "total": stats["total"]})
        job.stats = exec_stats
        all_errors = validation_errors + exec_errors
        job.error_report_path = pipeline.write_error_report(job.id, all_errors)
        job.status = ImportJobStatus.COMPLETED
    except Exception as exc:
        job.status = ImportJobStatus.FAILED
        await db.flush()
        await logger.aexception("dataexchange_import_failed", job_id=str(job.id), error=str(exc))
        raise
    await db.flush()
    await logger.ainfo(
        "dataexchange_import_completed",
        job_id=str(job.id),
        imported=job.stats.get("imported"),
        skipped=job.stats.get("skipped"),
    )
    return job


def suggest_mapping(job: ImportJob) -> dict[str, str]:
    """Auto-guessed mapping for the job's detected headers."""
    adapter = get_adapter(job.entity_type)
    return pipeline.auto_guess_mapping(job.detected_headers or [], adapter)


# ---------------------------------------------------------------------------
# Export jobs
# ---------------------------------------------------------------------------


async def create_export_job(
    db: Any,
    *,
    entity_type: str,
    filters: dict[str, Any] | None,
    created_by: uuid.UUID | None,
    generate: bool = True,
) -> ExportJob:
    """Create an export job row.

    ``generate=False`` stops after the row, leaving the job PENDING for a
    worker to pick up. The API passes it so the request does not hold a
    connection open while every matching row streams to a CSV; the default
    keeps the old inline behaviour for any internal caller that wants the file
    back immediately.
    """
    adapter = get_adapter(entity_type)
    job = ExportJob(
        entity_type=adapter.entity_type,
        status=ExportJobStatus.PENDING,
        filters=filters or {},
        created_by=created_by,
    )
    db.add(job)
    await db.flush()

    if not generate:
        return job
    return await generate_export_file(db, job.id)


async def generate_export_file(db: Any, job_id: uuid.UUID) -> ExportJob:
    """Run the export for an already-created job.

    Split out of :func:`create_export_job` so the API can create the row, return
    immediately, and let a Celery worker produce the file. The Celery task runs
    the same steps in the same order, so a job created inline and one created by
    the worker end up in identical states.
    """
    job = await db.get(ExportJob, job_id)
    if job is None:
        raise NotFoundError("ExportJob", detail=f"Export job {job_id} not found")
    if job.status is ExportJobStatus.COMPLETED and job.result_path:
        return job  # idempotent: the task may run twice on a retry

    adapter = get_adapter(job.entity_type)
    job.status = ExportJobStatus.PROCESSING
    await db.flush()
    try:
        path, row_count = await pipeline.run_export(db, adapter, job.filters or {})
        job.result_path = path
        job.row_count = row_count
        job.status = ExportJobStatus.COMPLETED
    except Exception:
        job.status = ExportJobStatus.FAILED
        await db.flush()
        raise
    await db.flush()
    await logger.ainfo("dataexchange_export_completed", job_id=str(job.id))
    return job


async def get_export_job(db: Any, job_id: uuid.UUID) -> ExportJob:
    job = await db.get(ExportJob, job_id)
    if job is None:
        raise NotFoundError("ExportJob")
    return job


async def list_export_jobs(
    db: Any, *, entity_type: str | None = None, page: int = 1, page_size: int = 20
) -> tuple[list[ExportJob], int]:
    conditions = []
    if entity_type:
        conditions.append(ExportJob.entity_type == entity_type)
    total = (
        await db.execute(select(func.count()).select_from(ExportJob).where(*conditions))
    ).scalar() or 0
    stmt = (
        select(ExportJob)
        .where(*conditions)
        .order_by(ExportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


def supported_entities() -> list[dict[str, Any]]:
    return list_entity_types()
