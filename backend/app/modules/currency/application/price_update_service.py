"""The USD→Toman price sweep (the plugin's ``execute_price_update``).

Order of operations, mirroring the WordPress plugin:

1. Resolve a rate — Nobitex API first (the plugin's ``fetch_current_rate``),
   manual rate as fallback. No usable rate → the run FAILS and is recorded;
   the plugin would have used its default manual rate silently.
2. Rewrite every variant that carries a ``usd_price``:
   ``new_price = smart_round(usd_price × rate)``; with a ``usd_sale_price``
   the sale becomes the charged price and the base becomes the struck-through
   ``compare_at_price`` — exactly the plugin's regular/sale mapping.
3. Record one history row (``usd_price_updates``) and refresh the runtime
   state on the config row.

Differences from the plugin, each deliberate:

* One transaction for the whole sweep. The plugin saved products one by one;
  a crash halfway left half the catalog on the new rate and half on the old.
  Here a mid-sweep failure rolls back every price write and records the error.
* Only *changed* prices are written. The plugin re-saved every managed
  product on every run, which rewrote identical values and (in this project)
  would emit an audit entry and a search-sync event per product per run.
* The rounding is integer Rial throughout (ADR-012); USD values are exact
  ``Decimal``s from the column, never floats.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.catalog.domain.models import ProductVariant
from app.modules.currency.application import rate_config
from app.modules.currency.application.nobitex_client import Transport, fetch_rate_rial
from app.modules.currency.domain.models import UsdPriceUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def smart_round_rial(value_rial: Decimal, rounding_toman: int) -> int:
    """Round a Rial amount to the nearest multiple of ``rounding_toman`` Toman.

    The plugin's ``smart_round_price`` (PHP ``round``, half away from zero)
    translated to the site's money unit: the rounding value is entered in
    Toman and applied on the Rial value as ``rounding_toman × 10`` Rial.
    Example (plugin's own): 111,612 Toman with rounding 200 → 111,600.
    """
    step_rial = max(1, int(rounding_toman)) * 10
    if step_rial <= 1:
        return int(value_rial.to_integral_value(rounding=ROUND_HALF_UP))
    steps = (value_rial / step_rial).to_integral_value(rounding=ROUND_HALF_UP)
    return int(steps) * step_rial


async def resolve_rate_rial(
    config: dict[str, Any], transport: Transport | None = None
) -> tuple[int | None, str]:
    """The rate to use, and where it came from: ``("api" | "manual" | "none")``."""
    if config.get("api_enabled", True):
        rate = await fetch_rate_rial(transport)
        if rate is not None:
            return rate, "api"
    manual = int(config.get("manual_rate_rial", 0) or 0)
    if manual > 0:
        return manual, "manual"
    return None, "none"


async def count_managed_variants(db: AsyncSession) -> int:
    """How many variants currently carry a USD price (the sweep's working set)."""
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(ProductVariant)
                .where(ProductVariant.usd_price.is_not(None))
            )
        ).scalar_one()
    )


async def run_price_update(
    db: AsyncSession,
    *,
    scheduled: bool,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Run one sweep. Records its outcome on the config row either way.

    Never raises for an expected failure (an unreachable API with no manual
    rate, a mid-sweep error): the failure is recorded and reported in the
    return value, so a failed run is visible in the admin instead of turning
    into a Celery retry storm. Unexpected errors re-raise after recording.
    """
    config = await rate_config.get_config(db)
    try:
        rate_rial, source = await resolve_rate_rial(config, transport)
        if rate_rial is None:
            error = (
                "نرخی در دسترس نیست: اتصال به نوبیتکس ناموفق بود و نرخ دستی ثبت نشده است."
            )
            await _record_failure(db, config, error, scheduled=scheduled)
            return _result("failed", error=error)
        return await _apply_rate(db, config, rate_rial, source, scheduled=scheduled)
    except Exception as exc:
        # Roll back every partial write first — a half-updated catalog is the
        # one outcome worse than no update — then record why the run failed.
        await db.rollback()
        await logger.aexception("usd_price_update_failed")
        error = f"{type(exc).__name__}: {exc}"[:500]
        await _record_failure(db, config, error, scheduled=scheduled)
        return _result("failed", error=error)


def _result(
    status: str,
    *,
    rate_rial: int | None = None,
    rate_source: str | None = None,
    updated_count: int = 0,
    scanned: int = 0,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "rate_rial": rate_rial,
        "rate_source": rate_source,
        "updated_count": updated_count,
        "scanned": scanned,
        "error": error,
    }


async def _apply_rate(
    db: AsyncSession,
    config: dict[str, Any],
    rate_rial: int,
    source: str,
    *,
    scheduled: bool,
) -> dict[str, Any]:
    rounding_toman = int(config.get("price_rounding_toman", 100))

    variants = list(
        (
            await db.execute(
                select(ProductVariant).where(ProductVariant.usd_price.is_not(None))
            )
        )
        .scalars()
        .all()
    )

    changed: list[dict[str, Any]] = []
    touched_products: dict[uuid.UUID, str] = {}

    for variant in variants:
        usd_price = Decimal(str(variant.usd_price))
        if usd_price <= 0:  # defensive: a hand-edited row cannot zero a price
            continue
        base_rial = smart_round_rial(usd_price * rate_rial, rounding_toman)

        usd_sale = (
            Decimal(str(variant.usd_sale_price))
            if variant.usd_sale_price is not None
            else None
        )
        if usd_sale is not None and usd_sale > 0:
            new_price = smart_round_rial(usd_sale * rate_rial, rounding_toman)
            new_compare: int | None = base_rial
        else:
            new_price = base_rial
            new_compare = None

        if new_price <= 0:  # pragma: no cover — rate is sanity-bounded
            continue
        if variant.price == new_price and variant.compare_at_price == new_compare:
            continue  # unchanged: no write, no audit row, no search-sync event

        old_price, old_compare = variant.price, variant.compare_at_price
        variant.price = new_price
        variant.compare_at_price = new_compare
        changed.append(
            {
                "variant_id": str(variant.id),
                "sku": variant.sku,
                "product_id": str(variant.product_id),
                "product_name": variant.product.name if variant.product else "",
                "usd_price": str(usd_price),
                "usd_sale_price": str(usd_sale) if usd_sale is not None else None,
                "old_price": old_price,
                "old_compare": old_compare,
                "new_price": new_price,
                "new_compare": new_compare,
            }
        )
        if variant.product is not None:
            touched_products[variant.product_id] = variant.product.slug

    # Price feeds the Elasticsearch projection (sorting by price, range
    # filters), so every product whose price moved gets the same
    # ProductUpdated event an admin edit would publish.
    from app.shared.events.outbox_service import OutboxService

    for product_id in touched_products:
        try:
            await OutboxService.publish(
                db,
                event_type="ProductUpdated",
                aggregate_type="product",
                aggregate_id=str(product_id),
                payload={"product_id": str(product_id)},
            )
        except Exception:  # search sync is best-effort, never blocks pricing
            await logger.awarning(
                "usd_price_outbox_publish_skipped", product_id=str(product_id)
            )

    # The slug-keyed product-detail cache (300s TTL) would serve stale prices
    # after a sweep; delete the exact keys of the products that changed.
    from app.core.cache.redis import cache_delete

    for product_id, slug in touched_products.items():
        try:
            await cache_delete(f"catalog:product:slug:v2:{slug}")
        except Exception:  # pragma: no cover — cache is not the source of truth
            await logger.awarning("usd_price_cache_bust_skipped", product_id=str(product_id))

    now_iso = datetime.now(UTC).isoformat()
    updated_count = len(changed)

    if config.get("log_enabled", True):
        db.add(
            UsdPriceUpdate(
                rate_rial=rate_rial,
                rate_source=source,
                updated_count=updated_count,
                scheduled=scheduled,
                status="success",
                details={"scanned": len(variants), "changed": changed},
            )
        )

    await rate_config.update_runtime_state(
        db,
        last_rate_rial=rate_rial,
        last_source=source,
        last_update_at=now_iso,
        last_attempt_at=now_iso,
        last_status="success",
        last_error=None,
        last_updated_count=updated_count,
    )
    await logger.ainfo(
        "usd_price_update_done",
        rate_rial=rate_rial,
        rate_source=source,
        scanned=len(variants),
        updated=updated_count,
        scheduled=scheduled,
    )
    return _result(
        "success",
        rate_rial=rate_rial,
        rate_source=source,
        updated_count=updated_count,
        scanned=len(variants),
    )


async def _record_failure(
    db: AsyncSession,
    config: dict[str, Any],
    error: str,
    *,
    scheduled: bool,
) -> None:
    """Record a failed run; keep the last known-good rate untouched."""
    now_iso = datetime.now(UTC).isoformat()
    if config.get("log_enabled", True):
        db.add(
            UsdPriceUpdate(
                rate_rial=int(config.get("last_rate_rial", 0) or 0),
                rate_source="none",
                updated_count=0,
                scheduled=scheduled,
                status="failed",
                error=error,
            )
        )
    await rate_config.update_runtime_state(
        db,
        last_attempt_at=now_iso,
        last_status="failed",
        last_error=error,
    )
    await logger.awarning("usd_price_update_recorded_failure", error=error)


__all__ = [
    "count_managed_variants",
    "resolve_rate_rial",
    "run_price_update",
    "smart_round_rial",
]
