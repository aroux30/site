"""User-verification admin routes.

Mirrors the plugin's three tabs: settings (Telegram), the log report, and
(the user list itself lives on the existing admin users API — the
``is_verified`` flag and its filter are there). This router owns the two
surfaces that had no home: config and the verification log.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.core.security.rate_limiter import limiter
from app.modules.userverify.application import verification_config
from app.modules.userverify.application.verification_service import VerificationService

admin_router = APIRouter(prefix="/admin/user-verification", tags=["admin-userverify"])

_require_read = Depends(RequirePermissions("userverify:read"))
_require_write = Depends(RequirePermissions("userverify:write"))

_ADMIN_READ_LIMIT = "120/minute"
_ADMIN_WRITE_LIMIT = "20/minute"


class VerificationConfigResponse(BaseModel):
    config: dict[str, Any]


class VerificationConfigUpdateRequest(BaseModel):
    config: dict[str, Any]


class VerificationLogItem(BaseModel):
    id: str
    user_id: str
    user_phone: str | None = None
    admin_id: str
    admin_phone: str | None = None
    status: bool
    ip_address: str | None = None
    created_at: str | None = None


class VerificationLogResponse(BaseModel):
    items: list[VerificationLogItem]
    total: int


@admin_router.get(
    "/config",
    response_model=VerificationConfigResponse,
    summary="Admin — get user-verification config",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_READ_LIMIT)
async def admin_get_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> VerificationConfigResponse:
    config = await verification_config.get_config(db)
    return VerificationConfigResponse(config=verification_config.public_view(config))


@admin_router.put(
    "/config",
    response_model=VerificationConfigResponse,
    summary="Admin — update user-verification config",
    dependencies=[_require_write],
)
@limiter.limit(_ADMIN_WRITE_LIMIT)
async def admin_update_config(
    request: Request,
    payload: VerificationConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> VerificationConfigResponse:
    config = await verification_config.set_config(db, payload.config)
    await db.commit()
    return VerificationConfigResponse(config=verification_config.public_view(config))


@admin_router.get(
    "/logs",
    response_model=VerificationLogResponse,
    summary="Admin — verification decision log",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_READ_LIMIT)
async def admin_list_logs(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    q: str | None = Query(None, min_length=1, max_length=100),
    date_from: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> VerificationLogResponse:
    items, total = await VerificationService.list_logs(
        db, skip=skip, limit=limit, q=q, date_from=date_from, date_to=date_to,
    )
    return VerificationLogResponse(
        items=[VerificationLogItem(**item) for item in items], total=total
    )


@admin_router.get(
    "/logs/export",
    summary="Admin — export verification logs as CSV",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_WRITE_LIMIT)
async def admin_export_logs(
    request: Request,
    q: str | None = Query(None, min_length=1, max_length=100),
    date_from: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export all filtered verification logs as a CSV file (UTF-8 BOM)."""
    items, _total = await VerificationService.list_logs(
        db, skip=0, limit=10_000, q=q, date_from=date_from, date_to=date_to,
    )

    buf = io.StringIO()
    # UTF-8 BOM so Excel on Windows opens it correctly
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(["شماره کاربر", "وضعیت", "توسط (شماره ادمین)", "آدرس IP", "تاریخ"])
    for item in items:
        writer.writerow([
            item.get("user_phone") or item.get("user_id", ""),
            "احراز شد" if item.get("status") else "لغو احراز",
            item.get("admin_phone") or item.get("admin_id", ""),
            item.get("ip_address") or "",
            item.get("created_at") or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=verification-logs.csv",
        },
    )
