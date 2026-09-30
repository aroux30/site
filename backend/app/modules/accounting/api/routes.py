"""Accounting feed API — admin accounts, journal, periods and export.

Every endpoint is guarded by ``accounting:read`` / ``accounting:write``
(RequirePermissions pattern, mirroring invoicing and procurement). There is no
customer-facing surface, so only ``admin_router`` is exposed; ``main.py``
mounts it under ``/api/v1/admin/accounting/*``.

Endpoint map:

- ``GET/POST/PATCH /accounts`` — chart of accounts CRUD (no delete: an account
  referenced by a line can never be removed, and deactivation is the intended
  retirement path).
- ``POST /accounts/seed`` — idempotent Iranian-standard skeleton.
- ``GET /journal`` + ``GET /journal/{id}`` — list/detail with balanced lines.
- ``POST /journal`` — manual balanced entry.
- ``POST /journal/{id}/reverse`` — mirrored reversal entry.
- ``GET /journal/verify-chain`` — tamper-evidence check.
- ``GET /periods`` + ``POST /periods/close`` — period close.
- ``GET /export.csv`` + ``GET /export.json`` — external accounting software.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.accounting.application import (
    account_seed,
    export_service,
    journal_service,
)
from app.modules.accounting.application.posting_rules import LineSpec
from app.modules.accounting.domain.models import (
    Account,
    AccountType,
    JournalEntry,
    JournalEntryStatus,
    JournalSourceType,
    JournalLine,
)
from app.modules.accounting.schemas.accounting import (
    AccountCreateRequest,
    AccountListResponse,
    AccountResponse,
    AccountUpdateRequest,
    ChainVerificationResponse,
    ClosePeriodRequest,
    JournalEntryCreateRequest,
    JournalEntryListResponse,
    JournalEntryResponse,
    PeriodCloseResponse,
    PeriodListResponse,
    PeriodResponse,
    ReverseEntryRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

admin_router = APIRouter(prefix="/admin/accounting", tags=["admin-accounting"])

_require_read = Depends(RequirePermissions("accounting:read"))
_require_write = Depends(RequirePermissions("accounting:write"))


# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------


@admin_router.get(
    "/accounts",
    response_model=AccountListResponse,
    summary="List the chart of accounts (admin)",
    dependencies=[_require_read],
)
async def list_accounts(
    type: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    stmt = select(Account).order_by(Account.code.asc())
    if type:
        stmt = stmt.where(Account.type == AccountType(type))
    if is_active is not None:
        stmt = stmt.where(Account.is_active == is_active)
    rows = list((await db.execute(stmt)).scalars().all())
    return AccountListResponse(
        items=[AccountResponse.model_validate(a) for a in rows], total=len(rows)
    )


@admin_router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account (admin)",
    dependencies=[_require_write],
)
async def create_account(
    body: AccountCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    existing = (
        await db.execute(select(Account).where(Account.code == body.code))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            detail=f"حسابی با کد {body.code} از قبل وجود دارد.",
            error_code="ACCOUNT_CODE_EXISTS",
        )
    if body.parent_id is not None and await db.get(Account, body.parent_id) is None:
        raise NotFoundError("Account", "حساب والد یافت نشد")

    account = Account(
        code=body.code.strip(),
        name_fa=body.name_fa.strip(),
        type=AccountType(body.type),
        parent_id=body.parent_id,
        is_active=body.is_active,
        description=body.description,
    )
    db.add(account)
    await db.flush()
    await db.commit()
    return AccountResponse.model_validate(account)


@admin_router.patch(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="Update an account (admin)",
    dependencies=[_require_write],
)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    account = await db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account")

    if body.parent_id is not None:
        if body.parent_id == account.id:
            raise ValidationError(
                detail="حساب نمیتواند والد خودش باشد", error_code="ACCOUNT_SELF_PARENT"
            )
        if await db.get(Account, body.parent_id) is None:
            raise NotFoundError("Account", "حساب والد یافت نشد")
        account.parent_id = body.parent_id
    if body.name_fa is not None:
        account.name_fa = body.name_fa.strip()
    if body.description is not None:
        account.description = body.description
    if body.is_active is not None:
        account.is_active = body.is_active

    await db.flush()
    await db.commit()
    return AccountResponse.model_validate(account)


@admin_router.post(
    "/accounts/seed",
    response_model=AccountListResponse,
    summary="Seed the Iranian-standard chart of accounts (idempotent, admin)",
    dependencies=[_require_write],
)
async def seed_accounts(db: AsyncSession = Depends(get_db)) -> AccountListResponse:
    stats = await account_seed.seed_accounts(db)
    await db.commit()
    rows = list((await db.execute(select(Account).order_by(Account.code.asc()))).scalars().all())
    await logger.ainfo(
        "accounting_seed_endpoint",
        created=len(stats.created),
        skipped=len(stats.skipped),
    )
    return AccountListResponse(
        items=[AccountResponse.model_validate(a) for a in rows], total=len(rows)
    )


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------


@admin_router.get(
    "/journal",
    response_model=JournalEntryListResponse,
    summary="List journal entries (admin)",
    dependencies=[_require_read],
)
async def list_journal_entries(
    fiscal_period: str | None = Query(None),
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> JournalEntryListResponse:
    status_filter: JournalEntryStatus | None = None
    if status:
        try:
            status_filter = JournalEntryStatus(status)
        except ValueError:
            raise ValidationError(
                detail="وضعیت سند نامعتبر است؛ مقادیر مجاز: draft، posted، reversed",
                error_code="INVALID_JOURNAL_STATUS",
            ) from None
    source_filter: JournalSourceType | None = None
    if source_type:
        try:
            source_filter = JournalSourceType(source_type)
        except ValueError:
            raise ValidationError(
                detail="نوع منبع نامعتبر است.",
                error_code="INVALID_SOURCE_TYPE",
            ) from None

    rows, total = await journal_service.list_entries(
        db,
        fiscal_period=fiscal_period,
        status=status_filter,
        source_type=source_filter,
        page=page,
        page_size=page_size,
    )
    return JournalEntryListResponse(
        items=[JournalEntryResponse.from_entry(e) for e in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get(
    "/journal/verify-chain",
    response_model=ChainVerificationResponse,
    summary="Verify the journal hash chain (admin)",
    dependencies=[_require_read],
)
async def verify_journal_chain(
    fiscal_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ChainVerificationResponse:
    report = await journal_service.verify_chain(db, fiscal_period=fiscal_period)
    return ChainVerificationResponse(**report)


@admin_router.post(
    "/journal",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual journal entry (admin)",
    dependencies=[_require_write],
)
async def create_journal_entry(
    body: JournalEntryCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    # Resolve every line to an account *code* so the rule-based create path
    # (which works in codes) is the single creation route.
    codes: list[str] = []
    for line in body.lines:
        if line.account_code:
            codes.append(line.account_code)
        elif line.account_id:
            account = await db.get(Account, line.account_id)
            if account is None:
                raise NotFoundError("Account")
            codes.append(account.code)

    specs: list[LineSpec] = []
    for line, code in zip(body.lines, codes, strict=True):
        specs.append(
            LineSpec(
                account_code=code,
                debit_rial=line.debit_rial,
                credit_rial=line.credit_rial,
                description=line.description,
            )
        )

    entry, _created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.MANUAL,
        source_id=None,
        entry_type="manual",
        description=body.description,
        line_specs=specs,
        entry_date=body.entry_date,
        status=(
            JournalEntryStatus.POSTED if body.post_now else JournalEntryStatus.DRAFT
        ),
        created_by=user_id,
    )
    await db.commit()
    refreshed = await journal_service.get_entry(db, entry.id)
    return JournalEntryResponse.from_entry(refreshed)


@admin_router.get(
    "/journal/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Journal entry detail (admin)",
    dependencies=[_require_read],
)
async def get_journal_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    entry = await journal_service.get_entry(db, entry_id)
    return JournalEntryResponse.from_entry(entry)


@admin_router.post(
    "/journal/{entry_id}/post",
    response_model=JournalEntryResponse,
    summary="Post a draft journal entry (admin)",
    dependencies=[_require_write],
)
async def post_journal_entry(
    entry_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    await journal_service.post_entry(db, entry_id=entry_id, actor_id=user_id)
    await db.commit()
    entry = await journal_service.get_entry(db, entry_id)
    return JournalEntryResponse.from_entry(entry)


@admin_router.post(
    "/journal/{entry_id}/reverse",
    response_model=JournalEntryResponse,
    summary="Reverse a posted journal entry (creates a mirrored entry, admin)",
    dependencies=[_require_write],
)
async def reverse_journal_entry(
    entry_id: uuid.UUID,
    body: ReverseEntryRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    reversal = await journal_service.reverse_entry(
        db, entry_id=entry_id, reason=body.reason, actor_id=user_id
    )
    await db.commit()
    entry = await journal_service.get_entry(db, reversal.id)
    return JournalEntryResponse.from_entry(entry)


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------


@admin_router.get(
    "/periods",
    response_model=PeriodListResponse,
    summary="List fiscal periods and their close status (admin)",
    dependencies=[_require_read],
)
async def list_periods(
    fiscal_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PeriodListResponse:
    rows = await journal_service.list_periods(db, fiscal_period=fiscal_period)
    return PeriodListResponse(
        items=[PeriodResponse.from_period(p) for p in rows], total=len(rows)
    )


@admin_router.post(
    "/periods/close",
    response_model=PeriodCloseResponse,
    summary="Close a Jalali fiscal period (locks its entries, admin)",
    dependencies=[_require_write],
)
async def close_period(
    body: ClosePeriodRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PeriodCloseResponse:
    period = await journal_service.close_period(
        db, fiscal_period=body.fiscal_period, actor_id=user_id
    )
    await db.commit()
    return PeriodCloseResponse(**PeriodResponse.from_period(period).model_dump())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _parse_period_bound(value: str | None, *, end_of_day: bool) -> datetime | None:
    """Parse an export bound: ``YYYY-MM-DD`` (UTC) is the supported form."""
    if not value:
        return None
    raw = value.strip()
    try:
        day = datetime.fromisoformat(raw)
    except ValueError:
        raise ValidationError(
            detail="قالب تاریخ نامعتبر است؛ قالب درست: YYYY-MM-DD",
            error_code="INVALID_DATE",
        ) from None
    if day.tzinfo is None:
        day = day.replace(tzinfo=UTC)
        if end_of_day and day.time() == time(0, 0):
            day = day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return day


@admin_router.get(
    "/export.csv",
    summary="Flat journal-line CSV export (UTF-8 BOM, injection-safe)",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_journal_csv(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    fiscal_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    date_from = _parse_period_bound(from_, end_of_day=False)
    date_to = _parse_period_bound(to, end_of_day=True)
    csv_bytes = await export_service.export_csv(
        db, date_from=date_from, date_to=date_to, fiscal_period=fiscal_period
    )
    filename = export_service.export_filename(
        fiscal_period=fiscal_period, date_from=date_from, date_to=date_to
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_router.get(
    "/export.json",
    summary="Structured journal export for integrations (admin)",
    dependencies=[_require_read],
)
async def export_journal_json(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    fiscal_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    date_from = _parse_period_bound(from_, end_of_day=False)
    date_to = _parse_period_bound(to, end_of_day=True)
    return await export_service.export_json(
        db, date_from=date_from, date_to=date_to, fiscal_period=fiscal_period
    )


# ---------------------------------------------------------------------------
# Health / summary (dashboard tile)
# ---------------------------------------------------------------------------


@admin_router.get(
    "/summary",
    summary="Accounting feed summary (admin)",
    dependencies=[_require_read],
)
async def accounting_summary(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Counts and control totals for the admin dashboard tile."""
    account_count = int(
        (await db.execute(select(func.count()).select_from(Account))).scalar_one()
    )
    entry_stmt = select(
        JournalEntry.status,
        func.count(JournalEntry.id),
        func.coalesce(func.sum(JournalLine.debit_rial), 0),
    ).join(JournalLine, JournalLine.entry_id == JournalEntry.id).group_by(JournalEntry.status)
    by_status = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): {
            "entries": int(row[1]),
            "debit_rial": int(row[2]),
        }
        for row in (await db.execute(entry_stmt)).all()
    }
    return {
        "accounts": account_count,
        "by_status": by_status,
        "periods": len(await journal_service.list_periods(db)),
    }
