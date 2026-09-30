"""Admin API for the generic import/export framework.

All endpoints are admin-only (``dataexchange:read`` / ``dataexchange:write``).
Files are served through :class:`FileResponse` — the raw storage path is
never exposed in API responses.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.dataexchange.application import exchange_service
from app.modules.dataexchange.schemas.exchange import (
    AutoMappingResponse,
    EntityInfo,
    ExecuteImportRequest,
    ExportJobCreateRequest,
    ExportJobListResponse,
    ExportJobResponse,
    ImportJobListResponse,
    ImportJobResponse,
    SetMappingRequest,
    SetMappingResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Empty public router keeps main.py's router contract satisfied; all real
# endpoints are admin-only by design.
router = APIRouter(tags=["dataexchange"])

admin_router = APIRouter(prefix="/admin", tags=["admin-dataexchange"])

_require_read = Depends(RequirePermissions("dataexchange:read"))
_require_write = Depends(RequirePermissions("dataexchange:write"))


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@admin_router.get(
    "/data-exchange/entities",
    response_model=list[EntityInfo],
    summary="List importable/exportable entity types and their columns (admin)",
    dependencies=[_require_read],
)
async def list_entities() -> list[dict]:
    return exchange_service.supported_entities()


# ---------------------------------------------------------------------------
# Import jobs
# ---------------------------------------------------------------------------


@admin_router.post(
    "/import-jobs",
    response_model=ImportJobResponse,
    status_code=201,
    summary="Upload a CSV/XLSX file and create an import job (admin)",
    dependencies=[_require_write],
)
async def create_import_job(
    entity_type: str = Form(...),
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ImportJobResponse:
    content = await file.read()
    if not content:
        raise ValidationError("فایل خالی است")
    job = await exchange_service.create_import_job(
        db,
        entity_type=entity_type,
        file_bytes=content,
        filename=file.filename or "upload.csv",
        created_by=user_id,
    )
    return ImportJobResponse.from_job(job)


@admin_router.get(
    "/import-jobs",
    response_model=ImportJobListResponse,
    summary="List import jobs (admin)",
    dependencies=[_require_read],
)
async def list_import_jobs(
    entity_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ImportJobListResponse:
    jobs, total = await exchange_service.list_import_jobs(
        db, entity_type=entity_type, page=page, page_size=page_size
    )
    return ImportJobListResponse(
        items=[ImportJobResponse.from_job(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/import-jobs/{job_id}",
    response_model=ImportJobResponse,
    summary="Import job detail with stats (admin)",
    dependencies=[_require_read],
)
async def get_import_job(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ImportJobResponse:
    job = await exchange_service.get_import_job(db, job_id)
    return ImportJobResponse.from_job(job)


@admin_router.get(
    "/import-jobs/{job_id}/auto-mapping",
    response_model=AutoMappingResponse,
    summary="Auto-guess column mapping from the file's headers (admin)",
    dependencies=[_require_read],
)
async def auto_mapping(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> AutoMappingResponse:
    job = await exchange_service.get_import_job(db, job_id)
    return AutoMappingResponse(mapping=exchange_service.suggest_mapping(job))


@admin_router.post(
    "/import-jobs/{job_id}/mapping",
    response_model=SetMappingResponse,
    summary="Set the column mapping for an import job (admin)",
    dependencies=[_require_write],
)
async def set_mapping(
    job_id: uuid.UUID,
    body: SetMappingRequest,
    db: AsyncSession = Depends(get_db),
) -> SetMappingResponse:
    job = await exchange_service.set_mapping(db, job_id, body.mapping)
    return SetMappingResponse(job=ImportJobResponse.from_job(job))


@admin_router.post(
    "/import-jobs/{job_id}/validate",
    response_model=ImportJobResponse,
    summary="Dry-run validation of every row (admin)",
    dependencies=[_require_write],
)
async def validate_import_job(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ImportJobResponse:
    job = await exchange_service.validate_import_job(db, job_id)
    return ImportJobResponse.from_job(job)


@admin_router.post(
    "/import-jobs/{job_id}/execute",
    response_model=ImportJobResponse,
    summary="Queue a validated import job for background execution (admin, idempotent)",
    dependencies=[_require_write],
)
async def execute_import_job(
    job_id: uuid.UUID,
    body: ExecuteImportRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> ImportJobResponse:
    """Hand the job to the worker instead of running it inside the request.

    ``execute_import_job`` parses a whole CSV/XLSX and writes every row, which
    takes seconds to minutes on a real file. Awaiting it here held the HTTP
    connection open for the entire import, behind whatever proxy timeout sits
    in front — so a large import failed at the edge after the work had already
    been done, and the operator had no job to look at.

    The Celery task was already registered and idempotent; nothing ever called
    it. Queueing is best-effort in the same direction the rest of the app uses:
    if the broker is unreachable the work falls back to running inline rather
    than silently dropping an operator's import.
    """
    from app.modules.dataexchange.application.tasks import execute_import_job_task

    job = await exchange_service.get_import_job(db, job_id)
    idempotency_key = body.idempotency_key if body else None

    queued = False
    try:
        execute_import_job_task.delay(str(job_id), idempotency_key)
        queued = True
    except Exception:
        logger.exception("dataexchange_enqueue_failed", job_id=str(job_id))

    if queued:
        return ImportJobResponse.from_job(job)

    job = await exchange_service.execute_import_job(
        db, job_id, idempotency_key=idempotency_key
    )
    return ImportJobResponse.from_job(job)


@admin_router.get(
    "/import-jobs/{job_id}/errors",
    summary="Download the row-level error report CSV (admin)",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
async def download_error_report(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    job = await exchange_service.get_import_job(db, job_id)
    if not job.error_report_path:
        raise NotFoundError("ErrorReport", detail="گزارش خطایی برای این job ثبت نشده است")
    return FileResponse(
        job.error_report_path,
        filename=f"import-errors-{job_id.hex[:12]}.csv",
        media_type="text/csv; charset=utf-8",
    )


# ---------------------------------------------------------------------------
# Export jobs
# ---------------------------------------------------------------------------


@admin_router.post(
    "/export-jobs",
    response_model=ExportJobResponse,
    status_code=201,
    summary="Create an export job for an entity with filters (admin)",
    dependencies=[_require_write],
)
async def create_export_job(
    body: ExportJobCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ExportJobResponse:
    """Create the job row, then generate the file on the worker.

    The service used to run ``pipeline.run_export`` inline, which streams every
    matching row to a CSV — on a large catalog that is minutes inside a request.
    The job row and the generation are split so the request returns as soon as
    there is something to poll, and the same best-effort fallback applies: if
    the broker is unreachable the export runs inline rather than never running.
    """
    from app.modules.dataexchange.application.tasks import run_export_job_task

    job = await exchange_service.create_export_job(
        db, entity_type=body.entity_type, filters=body.filters, created_by=user_id,
        generate=False,
    )
    await db.commit()

    try:
        run_export_job_task.delay(str(job.id))
    except Exception:
        logger.exception("dataexchange_export_enqueue_failed", job_id=str(job.id))
        # Broker down: fall back to generating now rather than leaving a job
        # that will never complete.
        job = await exchange_service.generate_export_file(db, job.id)

    return ExportJobResponse.from_job(job)


@admin_router.get(
    "/export-jobs",
    response_model=ExportJobListResponse,
    summary="List export jobs (admin)",
    dependencies=[_require_read],
)
async def list_export_jobs(
    entity_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ExportJobListResponse:
    jobs, total = await exchange_service.list_export_jobs(
        db, entity_type=entity_type, page=page, page_size=page_size
    )
    return ExportJobListResponse(
        items=[ExportJobResponse.from_job(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/export-jobs/{job_id}",
    response_model=ExportJobResponse,
    summary="Export job detail (admin)",
    dependencies=[_require_read],
)
async def get_export_job(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ExportJobResponse:
    job = await exchange_service.get_export_job(db, job_id)
    return ExportJobResponse.from_job(job)


@admin_router.get(
    "/export-jobs/{job_id}/download",
    summary="Download the generated export CSV (admin)",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
async def download_export(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    job = await exchange_service.get_export_job(db, job_id)
    if not job.result_path:
        raise NotFoundError("ExportFile", detail="خروجی این job هنوز آماده نیست")
    return FileResponse(
        job.result_path,
        filename=f"{job.entity_type}-export-{job.id.hex[:12]}.csv",
        media_type="text/csv; charset=utf-8",
    )
