"""BI API: period-over-period comparison on top of the reporting layer.

Deliberately thin. The reporting module owns report generation; this module
runs the *same* report twice and diffs the results. Reimplementing the
queries here would mean two definitions of "gross sales" that drift apart,
which is the failure mode every second reporting stack eventually has.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.bi.application import comparison as cmp

router = APIRouter()
_ADMIN = "/admin"

#: Report types whose output supports a totals comparison. A report whose
#: totals are not numeric would produce an empty delta list, which is more
#: confusing than a clear refusal.
COMPARABLE_REPORTS = ("sales", "stock", "vendor_settlement", "tax_vat")


@router.get(
    f"{_ADMIN}/compare",
    dependencies=[Depends(RequirePermissions("reports:read"))],
    summary="Compare a report against a previous period (admin)",
)
async def compare_report(
    db: AsyncSession = Depends(get_db),
    report_type: str = Query(..., description="sales | stock | vendor_settlement | tax_vat"),
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    mode: cmp.ComparisonMode = Query(
        cmp.ComparisonMode.PREVIOUS_PERIOD,
        description="previous_period | same_period_last_year",
    ),
    group_by: str | None = Query(None),
    warehouse_id: uuid.UUID | None = Query(None),
    vendor_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    row_key: str | None = Query(
        None,
        description="Column to match rows on (e.g. category, vendor). Omit for totals only.",
    ),
) -> dict[str, Any]:
    """Run a report for the window and for its comparison window, then diff.

    Requires ``reports:read`` — the same permission that reading the report
    itself needs, because this returns the same data twice.
    """
    from app.core.exceptions.handlers import ValidationError
    from app.modules.reporting.application import report_service

    if report_type not in COMPARABLE_REPORTS:
        raise ValidationError(
            f"این نوع گزارش قابل مقایسه نیست: {report_type}",
            error_code="REPORT_NOT_COMPARABLE",
        )

    prev_from, prev_to = cmp.previous_window(date_from, date_to, mode)

    async def _run(from_date: date, to_date: date) -> Any:
        return await report_service.generate_report(
            db,
            report_type,
            date_from=from_date,
            date_to=to_date,
            group_by=group_by,
            warehouse_id=warehouse_id,
            vendor_id=vendor_id,
            category_id=category_id,
            low_stock_only=False,
        )

    # The two runs are independent reads of the same session, so they overlap
    # rather than queue: the endpoint takes as long as the slower report, not
    # as long as both. ``asyncio.gather`` on one AsyncSession is safe here
    # because both branches only read — a write would interleave on the same
    # connection and must stay sequential.
    current, previous = await asyncio.gather(
        _run(date_from, date_to),
        _run(prev_from, prev_to),
    )

    payload: dict[str, Any] = {
        "report_type": report_type,
        "mode": mode.value if hasattr(mode, "value") else str(mode),
        "current_window": {"from": date_from, "to": date_to},
        "previous_window": {"from": prev_from, "to": prev_to},
        "totals": [d.to_dict() for d in cmp.compare_totals(current.totals, previous.totals)],
    }

    if row_key:
        metrics = [
            c.key for c in current.columns if c.kind in ("int", "money")
        ]
        if metrics:
            payload["rows"] = cmp.compare_rows(
                current.rows,
                previous.rows,
                key_field=row_key,
                metrics=metrics,
            )
            payload["row_key"] = row_key
            payload["metrics"] = metrics

    return payload


@router.get(
    f"{_ADMIN}/comparable-reports",
    dependencies=[Depends(RequirePermissions("reports:read"))],
    summary="Which reports support comparison (admin)",
)
async def comparable_reports() -> dict[str, Any]:
    """The allow-list, so the UI does not hard-code report types."""
    return {
        "reports": list(COMPARABLE_REPORTS),
        "modes": [m.value for m in cmp.ComparisonMode],
    }


__all__ = ["router"]
