"""Automated test verifying index coverage and query performance contracts."""

from typing import NamedTuple
import pytest

from app.modules.orders.domain.models import Order, OrderItem
from app.modules.audit.domain.models import AuditLog
from app.modules.shipping.domain.models import ShippingMethod


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


def test_mandatory_indexes_coverage():
    """Verify that all critical performance indexes are declared on models."""
    models_to_check = [Order, OrderItem, AuditLog, ShippingMethod]
    indexed_tables = {}

    for model in models_to_check:
        table = getattr(model, "__table__", None)
        if table is not None:
            indexed_tables[table.name] = {idx.name for idx in table.indexes}

    missing_count = 0
    for spec in MANDATORY_INDEXES:
        declared = indexed_tables.get(spec.table, set())
        assert spec.index_name in declared, f"Missing critical performance index: {spec.table}.{spec.column} -> {spec.index_name}"
