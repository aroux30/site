"""Live check: the audit field-level change capture actually records diffs.

The "تاریخچه تغییرات فیلدها" tab could never show anything (found live,
2026-10-06). Two independent breaks sat behind it:

  1. ``change_tracking`` — the module that installs the SQLAlchemy flush
     hooks — was imported by no boot path. The hook never ran in any
     process, so ``entity_change_logs`` stayed empty forever.
  2. Even imported, every capture insert failed the table's CHECK
     constraints: the ORM persists enum *member names* ('UPDATE', 'USER',
     'API'), while the live database had been created with the lowercase
     *values* ('update', 'user', 'api'). The hook is fail-soft, so the
     failure was a warning log and an empty table — never a visible error.

This script drives the real hook against the live database. Every write
happens in a transaction that is rolled back, so the committed tables are
left exactly as found:

  price change    -> one row appears, with the exact integer before/after
  actor binding   -> the row carries the bound actor and request id
  untracked field -> no row (tracking is opt-in, never blanket)
  zero residue    -> the committed change-log count is unchanged

    cd backend && PYTHONPATH=. python scripts/verify_change_tracking.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

import structlog  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import Session as SyncSession  # noqa: E402

from app.core.security.actor_context import actor_scope  # noqa: E402
from app.modules.audit.application import change_tracking as ct  # noqa: E402
from app.modules.audit.domain.entity_changelog import (  # noqa: E402
    ChangeActorType,
    ChangeOperation,
    ChangeSource,
    EntityChangeLog,
)
from app.modules.catalog.domain.models import ProductVariant  # noqa: E402
from app.modules.users.domain.models import User  # noqa: E402


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DATABASE_URL not found — run from backend/ with its .env present")


async def main() -> int:
    failures: list[str] = []

    # ── 1. The hook is installed and every default entity is routed ──
    if not (
        ct._INSTALLED and event.contains(SyncSession, "after_flush", ct._after_flush)
    ):
        failures.append(
            "flush hook is not installed — importing "
            "app.modules.audit.application.change_tracking must install it"
        )
    missing = sorted(set(ct.TRACKED_ENTITIES) - set(ct.REGISTERED_ENTITIES))
    if missing:
        failures.append(f"tracked entities failed to register: {missing}")

    engine = create_async_engine(_database_url())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        baseline = (
            await db.execute(select(func.count()).select_from(EntityChangeLog))
        ).scalar_one()
        variant = (
            await db.execute(select(ProductVariant).limit(1))
        ).scalar_one_or_none()
        actor_id = (await db.execute(select(User.id).limit(1))).scalar_one_or_none()

    if variant is None:
        print("SKIP: no product variant exists to exercise")
        await engine.dispose()
        return 0

    # ── 2. A tracked change (price) is captured with its exact diff ──
    orig = int(variant.price)
    new_price = orig + 1234
    request_id = f"verify-ct-{uuid.uuid4()}"
    async with factory() as db:
        try:
            obj = await db.get(ProductVariant, variant.id)
            structlog.contextvars.bind_contextvars(request_id=request_id)
            try:
                with actor_scope(actor_id, source="service"):
                    obj.price = new_price
                    await db.flush()
            finally:
                structlog.contextvars.clear_contextvars()

            rows = (
                (
                    await db.execute(
                        select(EntityChangeLog).where(
                            EntityChangeLog.entity_id == str(obj.id)
                        )
                    )
                )
                .scalars()
                .all()
            )
            if len(rows) != 1:
                failures.append(
                    f"price change produced {len(rows)} change rows, expected 1 — "
                    "hook not running, or a CHECK constraint rejected the insert "
                    "(check backend logs for change_tracking_persist_failed)"
                )
            else:
                row = rows[0]
                expected_diff = [
                    {"field": "price", "old_value": orig, "new_value": new_price}
                ]
                expected_actor_type = (
                    ChangeActorType.USER if actor_id else ChangeActorType.SYSTEM
                )
                if row.operation != ChangeOperation.UPDATE:
                    failures.append(f"operation stored as {row.operation!r}")
                if row.changed_fields != expected_diff:
                    failures.append(
                        f"diff mismatch: {row.changed_fields!r} != {expected_diff!r}"
                    )
                if row.actor_id != actor_id:
                    failures.append(f"actor not captured: {row.actor_id!r}")
                if row.actor_type != expected_actor_type:
                    failures.append(f"actor type stored as {row.actor_type!r}")
                if row.source != ChangeSource.SERVICE:
                    failures.append(f"source stored as {row.source!r}")
                if row.request_id != request_id:
                    failures.append(
                        f"request id not captured: {row.request_id!r} != {request_id!r}"
                    )
        except Exception as exc:  # noqa: BLE001
            failures.append(
                f"price-change capture raised {type(exc).__name__}: {exc} — "
                "pre-fix, the CHECK-constraint mismatch poisoned the transaction"
            )
        finally:
            await db.rollback()

    # ── 3. An untracked field change produces nothing ──
    async with factory() as db:
        try:
            obj = await db.get(ProductVariant, variant.id)
            obj.barcode = f"verify-{uuid.uuid4().hex[:12]}"  # not a tracked field
            await db.flush()
            rows = (
                (
                    await db.execute(
                        select(EntityChangeLog).where(
                            EntityChangeLog.entity_id == str(obj.id)
                        )
                    )
                )
                .scalars()
                .all()
            )
            if rows:
                failures.append(
                    f"an untracked field (barcode) produced {len(rows)} change row(s)"
                )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"untracked-field probe raised {type(exc).__name__}: {exc}")
        finally:
            await db.rollback()

    # ── 4. Zero residue: this script must not have written anything ──
    async with factory() as db:
        after = (
            await db.execute(select(func.count()).select_from(EntityChangeLog))
        ).scalar_one()
    if after != baseline:
        failures.append(
            f"committed change-log count moved from {baseline} to {after} — "
            "a rolled-back write escaped"
        )

    await engine.dispose()

    if failures:
        print("FAIL — change capture is not working:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — field-level change capture works end to end:")
    print("  hook installed; price diff, actor and request id captured;")
    print("  untracked fields ignored; committed tables untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
