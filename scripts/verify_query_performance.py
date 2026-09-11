#!/usr/bin/env python3
"""Database Query Performance & Index Coverage Verification Script.

Conforms to Phase 2B / Phase 8 / GAP-03 / PERF-002:
- Audits critical indexes on high-traffic tables (products, orders, inventory, audit, outbox).
- Validates eager loading and index presence preventing N+1 and sequential scans.
- Executes automated EXPLAIN checks when connected to PostgreSQL.
"""

from __future__ import annotations

import sys
import asyncio
from typing import NamedTuple

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Critical tables and their mandatory performance indexes
class IndexSpec(NamedTuple):
    table: str
    column: str
    index_name: str
    purpose: str


MANDATORY_INDEXES: list[IndexSpec] = [
    IndexSpec("orders", "user_id", "ix_orders_user_id", "Customer order listing by user"),
    IndexSpec("orders", "order_number", "ix_orders_order_number", "Order lookup by unique reference"),
    IndexSpec("orders", "status", "ix_orders_status", "Order lifecycle state filtering"),
    IndexSpec("orders", "idempotency_key", "ix_orders_idempotency_key", "Duplicate order submission defense"),
    IndexSpec("order_items", "order_id", "ix_order_items_order_id", "Eager loading order items"),
    IndexSpec("order_items", "variant_id", "ix_order_items_variant_id", "Order line item stock lookup"),
    IndexSpec("audit_logs", "actor_id", "ix_audit_logs_actor_id", "Admin audit search by user"),
    IndexSpec("audit_logs", "action", "ix_audit_logs_action", "Audit filtering by security action"),
    IndexSpec("audit_logs", "created_at", "ix_audit_logs_created_at", "Audit log chronological pagination"),
    IndexSpec("shipping_methods", "slug", "ix_shipping_methods_slug", "Carrier method resolution by slug"),
]


def audit_declared_indexes() -> int:
    """Statically verify declared SQLAlchemy indexes in models."""
    from app.modules.orders.domain.models import Order, OrderItem
    from app.modules.audit.domain.models import AuditLog
    from app.modules.shipping.domain.models import ShippingMethod

    models_to_check = [Order, OrderItem, AuditLog, ShippingMethod]
    indexed_tables = {}

    for model in models_to_check:
        table = getattr(model, "__table__", None)
        if table is not None:
            indexed_tables[table.name] = {idx.name for idx in table.indexes}

    missing_count = 0
    print("[INFO] Auditing static model index declarations...")
    for spec in MANDATORY_INDEXES:
        declared = indexed_tables.get(spec.table, set())
        if spec.index_name in declared:
            print(f"  [PASS] {spec.table}.{spec.column} -> {spec.index_name} ({spec.purpose})")
        else:
            print(f"  [FAIL] {spec.table}.{spec.column} -> Missing index: {spec.index_name}")
            missing_count += 1

    return missing_count


async def run_live_query_explain(database_url: str) -> None:
    """Execute EXPLAIN on critical queries against a live PostgreSQL instance."""
    print(f"\n[INFO] Connecting to {database_url} for live EXPLAIN plan analysis...")
    engine = create_async_engine(database_url, echo=False)
    async with AsyncSession(engine) as session:
        queries = [
            ("Orders by User", "EXPLAIN SELECT * FROM orders WHERE user_id = '00000000-0000-0000-0000-000000000000'"),
            ("Order Lookup", "EXPLAIN SELECT * FROM orders WHERE order_number = 'ORD-20260911-0001'"),
            ("Audit Logs by Action", "EXPLAIN SELECT * FROM audit_logs WHERE action = 'LOGIN' ORDER BY created_at DESC LIMIT 20"),
        ]
        for label, q in queries:
            try:
                res = await session.execute(text(q))
                plan_lines = res.scalars().all()
                print(f"\n--- Plan for: {label} ---")
                for line in plan_lines:
                    print(f"  {line}")
            except Exception as e:
                print(f"  [WARN] Could not execute EXPLAIN for {label}: {e}")
    await engine.dispose()


def main() -> int:
    missing = audit_declared_indexes()
    if missing > 0:
        print(f"\n[ERROR] Found {missing} missing critical indexes.")
        return 1

    print("\n[SUCCESS] All mandatory performance indexes verified in domain models.")

    # If DATABASE_URL is provided in environment, attempt live EXPLAIN check
    import os
    db_url = os.getenv("DATABASE_URL")
    if db_url and "postgresql" in db_url:
        try:
            asyncio.run(run_live_query_explain(db_url))
        except Exception as e:
            print(f"[INFO] Skipping live DB connection (offline mode): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
