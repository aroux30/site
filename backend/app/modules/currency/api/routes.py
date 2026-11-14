"""Currency (USD→Toman) admin API.

Mirrors the WordPress plugin's admin surface (settings page, "update now"
button, log viewer with clear/download) on the project's conventions:

* GET/PUT ``/admin/currency/config`` — settings (plugin's options form)
* POST ``/admin/currency/update-now`` — the plugin's manual update button
* GET ``/admin/currency/history`` — the plugin's log viewer, paginated and
  filterable from the database instead of a text file
* GET ``/admin/currency/history/export.csv`` — the plugin's "download log"

Rate limits follow the referrals admin panel: reads 120/min, writes 20/min,
export 10/min. The manual update is a write (it rewrites catalog prices).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.core.security.rate_limiter import limiter
from app.modules.currency.application import rate_config
from app.modules.currency.domain.models import UsdPriceUpdate

admin_router = APIRouter(prefix="/admin/currency", tags=["admin-currency"])

_require_read = Depends(RequirePermissions("currency:read"))
_require_write = Depends(RequirePermissions("currency:write"))

_ADMIN_READ_LIMIT = "120/minute"
_ADMIN_WRITE_LIMIT = "20/minute"
_EXPORT_LIMIT = "10/minute"

#: The manual update rewrites the whole USD-priced catalog; a real operator
#: clicks it a few times an hour, a loop is a script.
_UPDATE_LIMIT = "6/minute"


class CurrencyConfigUpdateRequest(BaseModel):
    """Partial config update — only known keys are applied."""

    config: dict[str, Any]


class CurrencyConfigResponse(BaseModel):
    """Full config plus server-computed status fields."""

    config: dict[str, Any]
    #: ISO timestamp of the next automatic run (None = disabled).
    next_run_at: str | None = None
    #: How many variants currently carry a USD price.
    managed_variants: int = 0


class UpdateNowResponse(BaseModel):
    """Outcome of a manual run (also how a failure is reported)."""

    status: str
    rate_rial: int | None = None
    rate_source: str | None = None
    updated_count: int = 0
    scanned: int = 0
    error: str | None = None


class RateHistoryItem(BaseModel):
    """One recorded sweep."""

    id: str
    rate_rial: int
    rate_source: str
    updated_count: int
    scheduled: bool
    status: str
    error: str | None = None
    details: dict[str, Any] | None = None
    created_at: str | None = None


class RateHistoryResponse(BaseModel):
    """Paginated sweep history."""

    items: list[RateHistoryItem]
    total: int


@admin_router.get(
    "/config",
    response_model=CurrencyConfigResponse,
    summary="Admin — get USD rate updater config",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_READ_LIMIT)
async def admin_get_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrencyConfigResponse:
    """Return the updater config, its next run, and the managed-variant count."""
    from app.modules.currency.application.price_update_service import (
        count_managed_variants,
    )

    config = await rate_config.get_config(db)
    return CurrencyConfigResponse(
        config=config,
        next_run_at=rate_config.next_run_at(config),
        managed_variants=await count_managed_variants(db),
    )


@admin_router.put(
    "/config",
    response_model=CurrencyConfigResponse,
    summary="Admin — update USD rate updater config",
    dependencies=[_require_write],
)
@limiter.limit(_ADMIN_WRITE_LIMIT)
async def admin_update_config(
    request: Request,
    payload: CurrencyConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> CurrencyConfigResponse:
    """Upsert the config (only known, non-server-owned keys are applied)."""
    from app.modules.currency.application.price_update_service import (
        count_managed_variants,
    )

    config = await rate_config.set_config(db, payload.config)
    await db.commit()
    return CurrencyConfigResponse(
        config=config,
        next_run_at=rate_config.next_run_at(config),
        managed_variants=await count_managed_variants(db),
    )


@admin_router.post(
    "/update-now",
    response_model=UpdateNowResponse,
    summary="Admin — run the price update now",
    dependencies=[_require_write],
)
@limiter.limit(_UPDATE_LIMIT)
async def admin_update_now(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UpdateNowResponse:
    """Run one sweep immediately (the plugin's manual update button).

    Runs regardless of the ``enabled`` switch and the interval — pressing the
    button IS the explicit intent. The outcome is also recorded in the history
    exactly like a scheduled run, so the button's effect is auditable.
    """
    from app.modules.currency.application.price_update_service import run_price_update

    result = await run_price_update(db, scheduled=False)
    await db.commit()
    return UpdateNowResponse(**result)


@admin_router.get(
    "/history",
    response_model=RateHistoryResponse,
    summary="Admin — rate update history",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_READ_LIMIT)
async def admin_rate_history(
    request: Request,
    status: str | None = Query(
        None, pattern="^(success|failed)$", description="Filter by run outcome"
    ),
    q: str | None = Query(
        None, max_length=100, description="Search variant SKU or product name in the details"
    ),
    date_from: date | None = Query(None, description="Runs on/after this date (inclusive)"),
    date_to: date | None = Query(None, description="Runs on/before this date (inclusive)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RateHistoryResponse:
    """Every recorded sweep, newest first, with its rate and change count.

    Free text (``q``) searches the JSONB detail blob, where SKU and product
    name live — the two identifiers an operator searches by ("which run
    touched SKU-X?"). The filter builder is shared with the CSV export.
    """
    from app.modules.currency.application.rate_history import _build_where

    where = _build_where(status=status, q=q, date_from=date_from, date_to=date_to)

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(UsdPriceUpdate).where(*where)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await db.execute(
                select(UsdPriceUpdate)
                .where(*where)
                .order_by(UsdPriceUpdate.created_at.desc(), UsdPriceUpdate.id.desc())
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return RateHistoryResponse(
        items=[
            RateHistoryItem(
                id=str(row.id),
                rate_rial=row.rate_rial,
                rate_source=row.rate_source,
                updated_count=row.updated_count,
                scheduled=row.scheduled,
                status=row.status,
                error=row.error,
                details=row.details,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ],
        total=total,
    )


@admin_router.get(
    "/history/export.csv",
    summary="Admin — rate update history as Excel-safe CSV",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
@limiter.limit(_EXPORT_LIMIT)
async def admin_rate_history_export(
    request: Request,
    status: str | None = Query(None, pattern="^(success|failed)$"),
    q: str | None = Query(None, max_length=100),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The filtered history as a CSV (UTF-8 BOM, formula-injection hardened).

    Uses the reporting module's builder — the project's single CSV convention.
    """
    from app.modules.currency.application.rate_history import build_rate_history_csv

    csv_bytes = await build_rate_history_csv(
        db, status=status, q=q, date_from=date_from, date_to=date_to
    )
    stamp = date.today().strftime("%Y%m%d")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="usd-rate-history-{stamp}.csv"'},
    )


__all__ = ["admin_router"]
