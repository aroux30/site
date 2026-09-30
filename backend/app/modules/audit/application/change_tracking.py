"""Field-level change capture via SQLAlchemy flush events (ERP feature #9).

The :class:`~app.modules.audit.domain.entity_changelog.EntityChangeLog` table
answers "who changed product price from X to Y, and when?" — the existing action
log records *what happened*, never *what the value used to be*. This module is
the writer side: it listens on ``Session.after_flush`` and records per-field
before/after pairs for a **configurable, opt-in** entity set. Nothing outside
:data:`TRACKED_ENTITIES` is ever examined — there is no global blanket tracking.

Why ``after_flush``
-------------------
SQLAlchemy keeps the session in pre-flush state while ``after_flush`` runs
(new/dirty/deleted lists still populated, attribute history unconsumed), but
the INSERT/UPDATE/DELETE has already been emitted. Capturing there means:

* rows carry real primary keys (``session.new`` ids are assigned);
* a business flush that raised never produced a change row;
* the log write rides the same transaction, so it commits or rolls back with
  the business change it describes.

Contract with the business transaction
--------------------------------------
* **Observation-only** — the hook reads ORM state and never mutates a business
  object.
* **Fail-soft** — any exception is caught and logged at WARNING. Change capture
  can never block, slow or roll back the business flush.
* **Integer money stays integer** — values go through
  :func:`~app.modules.audit.application.audit_service._jsonify`; Rial amounts
  remain Python ``int`` end to end. No float is ever introduced here.
* **PII stays out** — every value passes through the project's masking helpers
  (:mod:`app.core.security.data_protection`), so a diff can never leak a card
  PAN, IBAN, national code or password.
* **Secrets never enter** — the only columns ever read are the ones listed in
  :data:`TRACKED_ENTITIES`; tokens and hashes are not among them.

Configuration
-------------
::

    "variant": {
        "fields": ["price", "compare_at_price", "cost", "is_active"],
        "operations": ["create", "update", "delete"],   # optional subset
        "sources": ["api", "admin"],                    # optional gate
        "enabled": True,
    }

:func:`register_tracked_entity` adds entries at runtime and is idempotent;
:func:`install_change_tracking` attaches the listeners exactly once.

Actor provenance
----------------
:func:`app.core.security.actor_context.resolve_provenance` supplies the actor
from the request/task context; with nothing bound the entry is attributed to
``system`` (or ``celery`` inside a worker task) rather than to any user.
"""

from __future__ import annotations

import traceback
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import event, insert
from sqlalchemy.orm import Session

from app.core.security.actor_context import resolve_provenance
from app.modules.audit.application.audit_service import _jsonify
from app.modules.audit.domain.entity_changelog import (
    ChangeActorType,
    ChangeOperation,
    ChangeSource,
    EntityChangeLog,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapper

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Characters stored per text value. Longer text is cut and the entry is
#: flagged ``truncated=True``; the full value is unrecoverable by design and
#: the flag is what makes that visible to a reviewer.
MAX_FIELD_LENGTH: int = 4_000

#: Stand-in for a value whose type has no JSON-safe form.
_UNSERIALIZABLE = "[unserializable]"

#: Whole-value redaction marker (mirrors data_protection._MASK).
_REDACTED = "[REDACTED]"


# ── Default tracking configuration ───────────────────────────────────────────

#: Entity type -> captured-field configuration. This is the complete v1 list;
#: anything absent is never inspected. Field names here are *data*, not code:
#: they are validated against the mapper at registration time and an unknown
#: name is reported (never silently captured).
TRACKED_ENTITIES: dict[str, dict[str, Any]] = {
    "product": {
        "fields": [
            "is_active",
            "status",
            "min_order_quantity",
            "max_order_quantity",
        ],
        "operations": ["create", "update", "delete"],
    },
    "variant": {
        "fields": ["price", "compare_at_price", "cost", "is_active"],
        "operations": ["create", "update", "delete"],
    },
    "discount": {
        "fields": [
            "name",
            "type",
            "value",
            "min_cart_amount",
            "max_discount",
            "scope",
            "starts_at",
            "ends_at",
            "is_active",
            "is_stackable",
            "usage_limit",
            "priority",
        ],
        "operations": ["create", "update", "delete"],
    },
    "tax_rule": {
        "fields": [
            "name",
            "rule_type",
            "scope",
            "rate_basis_points",
            "is_active",
            "priority",
            "effective_from",
            "effective_to",
            "exempt_reason",
        ],
        "operations": ["create", "update", "delete"],
    },
    "reorder_rule": {
        "fields": ["min_quantity", "reorder_to", "is_active"],
        "operations": ["create", "update", "delete"],
    },
    "vendor": {
        # PII columns (national_id, iban_number, contact_phone) are tracked on
        # purpose: they are exactly the values an auditor must see *changed*,
        # and they are the reason masking runs on every value.
        "fields": [
            "store_name",
            "slug",
            "commission_rate",
            "is_verified",
            "is_active",
            "contact_phone",
            "national_id",
            "iban_number",
        ],
        "operations": ["create", "update", "delete"],
    },
    "wallet": {
        "fields": ["balance", "is_active"],
        "operations": ["create", "update", "delete"],
    },
    "price_list_rule": {
        "fields": [
            "product_id",
            "variant_id",
            "min_quantity",
            "fixed_price_rial",
            "discount_bp",
        ],
        # Deletes are not snapshotted: a deleted pricing rule's erased values
        # are less forensic than a product price change, and v1 keeps the diff
        # surface focused.
        "operations": ["create", "update"],
    },
}

_VALID_OPERATIONS: frozenset[str] = frozenset(op.value for op in ChangeOperation)

#: entity_type -> {model, fields, operations, sources, enabled}
_REGISTRY: dict[str, dict[str, Any]] = {}

#: Exact model class -> entity_type (O(1) routing; subclasses are not routed).
_MODEL_CLASSES: dict[type[Any], str] = {}

#: Snapshot of the registry for inspection/tests (rebuilt by each registration).
REGISTERED_ENTITIES: dict[str, dict[str, Any]] = {}


# ── Registration ─────────────────────────────────────────────────────────────


def register_tracked_entity(
    entity_type: str,
    *,
    model_cls: type[Any],
    fields: list[str] | None = None,
    operations: list[str] | tuple[str, ...] | None = None,
    sources: list[str] | tuple[str, ...] | None = None,
    enabled: bool = True,
    extend: bool = True,
) -> None:
    """Register (or replace) one tracked entity type. Idempotent.

    ``fields`` are validated against the mapper: unknown names are logged at
    WARNING and dropped, so a typo degrades the audit coverage but can never
    break the boot or capture a non-column attribute.
    """
    from app.core.database.base import Base

    if not (isinstance(model_cls, type) and issubclass(model_cls, Base)):
        raise TypeError(
            f"register_tracked_entity: model_cls for {entity_type!r} must be an ORM model"
        )

    base_fields = TRACKED_ENTITIES.get(entity_type, {}).get("fields") if extend else None
    requested_fields = list(base_fields or []) + list(fields or [])
    if not requested_fields:
        raise ValueError(f"register_tracked_entity: no fields configured for {entity_type!r}")

    if operations is None:
        base_ops = TRACKED_ENTITIES.get(entity_type, {}).get("operations")
        valid_ops = set(base_ops) if base_ops else set(_VALID_OPERATIONS)
    else:
        valid_ops = set(operations)
    unknown_ops = valid_ops - _VALID_OPERATIONS
    if unknown_ops:
        raise ValueError(
            f"register_tracked_entity: unknown operation(s) {sorted(unknown_ops)} "
            f"for {entity_type!r}"
        )

    known_fields = [f for f in requested_fields if hasattr(model_cls, f)]
    unknown_fields = set(requested_fields) - set(known_fields)
    if unknown_fields:
        logger.warning(
            "change_tracking_unknown_field",
            entity_type=entity_type,
            fields=sorted(unknown_fields),
        )

    host_columns = {
        column.key
        for column in model_cls.__mapper__.columns  # type: ignore[attr-defined]
    }
    non_columns = set(known_fields) - host_columns
    if non_columns:
        logger.warning(
            "change_tracking_non_column_field",
            entity_type=entity_type,
            fields=sorted(non_columns),
        )

    _REGISTRY[entity_type] = {
        "model": model_cls,
        "fields": known_fields,
        "operations": valid_ops,
        "sources": set(sources) if sources is not None else None,
        "enabled": bool(enabled),
    }
    _MODEL_CLASSES[model_cls] = entity_type
    REGISTERED_ENTITIES[entity_type] = dict(_REGISTRY[entity_type])

    # Old values are preserved by the before_flush pre-load (see
    # _preserve_previous_values) rather than by the active_history flag: the
    # flag only takes effect when set before the mapper is instrumented, and
    # entities are registered here long after their own modules configured
    # their mappers, so setting it would be a silent no-op.


def _register_default_entities() -> None:
    """Register the default entity set; a broken row is logged, never fatal."""
    from app.modules.catalog.domain.models import Product, ProductVariant
    from app.modules.vendors.domain.models import Vendor
    from app.modules.checkout.domain.tax_models import TaxRuleV2
    from app.modules.discounts.domain.models import Discount
    from app.modules.inventory.domain.models import ReorderRule
    from app.modules.pricing.domain.models import PriceListRule
    from app.modules.wallet.domain.models import Wallet

    defaults: list[tuple[str, type[Any]]] = [
        ("product", Product),
        ("variant", ProductVariant),
        ("discount", Discount),
        ("tax_rule", TaxRuleV2),
        ("reorder_rule", ReorderRule),
        ("vendor", Vendor),
        ("wallet", Wallet),
        ("price_list_rule", PriceListRule),
    ]
    for entity_type, model_cls in defaults:
        try:
            register_tracked_entity(entity_type, model_cls=model_cls)
        except Exception:
            logger.warning(
                "change_tracking_register_failed",
                entity_type=entity_type,
                error=traceback.format_exc(),
            )


# ── Value normalisation, masking, truncation ─────────────────────────────────


def _mask_and_cap(field: str, value: Any) -> tuple[Any, bool]:
    """Normalise one value for JSONB storage.

    Returns ``(value, was_truncated)``. Whole-value secrets are replaced by a
    redaction marker; shape-preserving PII (phone, email, IBAN, national code)
    is masked by the existing helpers; other text is capped at
    :data:`MAX_FIELD_LENGTH`. Numbers — including all Rial integers — pass
    through untouched.
    """
    if value is None or isinstance(value, (int, bool)):
        return value, False

    key = field.lower()

    from app.core.security import data_protection

    if key in data_protection.DEFAULT_SENSITIVE_KEYS:
        return _REDACTED, False

    masker = _MASKERS.get(key)
    if masker is not None and isinstance(value, str):
        try:
            return masker(value), False
        except Exception:  # pragma: no cover - defensive
            return _REDACTED, False

    if isinstance(value, str):
        if len(value) > MAX_FIELD_LENGTH:
            return value[: MAX_FIELD_LENGTH - 1] + "…", True
        return value, False

    return _normalise(value), False


def _normalise(value: Any) -> Any:
    """Make a non-text value JSON-safe, preserving integers exactly.

    Delegates to the audit service's ``_jsonify`` (UUID/datetime/Decimal ->
    canonical text; int/bool/str unchanged) and degrades an exotic type to a
    marker rather than raising — that raise would otherwise surface as a failed
    *business* flush.
    """
    try:
        return _jsonify(value)
    except TypeError:
        logger.warning(
            "change_tracking_unserializable_value",
            value_type=type(value).__name__,
        )
        return _UNSERIALIZABLE


def _maskers() -> dict[str, Any]:
    from app.core.security.data_protection import (
        mask_email,
        mask_iban,
        mask_national_code,
        mask_phone,
    )

    return {
        "phone": mask_phone,
        "contact_phone": mask_phone,
        "mobile": mask_phone,
        "email": mask_email,
        "iban": mask_iban,
        "iban_number": mask_iban,
        "national_code": mask_national_code,
        "national_id": mask_national_code,
    }


_MASKERS: dict[str, Any] = {}


def _load_maskers() -> None:
    """Load the masking helpers once; a failure leaves whole-value redaction."""
    global _MASKERS
    if _MASKERS:
        return
    try:
        _MASKERS = _maskers()
    except Exception:  # pragma: no cover - import-time defensive
        logger.warning("change_tracking_masker_load_failed", error=traceback.format_exc())


def build_changed_fields(
    raw_changes: list[tuple[str, Any, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Turn ``[(field, old, new), …]`` into stored diffs and a truncation flag."""
    _load_maskers()
    changes: list[dict[str, Any]] = []
    truncated = False
    for field, old_raw, new_raw in raw_changes:
        old_value, old_cut = _mask_and_cap(field, _normalise(old_raw) if old_raw is not None else None)
        new_value, new_cut = _mask_and_cap(field, _normalise(new_raw) if new_raw is not None else None)
        truncated = truncated or old_cut or new_cut
        changes.append({"field": field, "old_value": old_value, "new_value": new_value})
    return changes, truncated


# ── Capture ──────────────────────────────────────────────────────────────────


def _entity_type_for(obj: Any) -> str | None:
    return _MODEL_CLASSES.get(type(obj))


def _route(obj: Any) -> tuple[str, dict[str, Any]] | None:
    """Return ``(entity_type, cfg)`` for a tracked, enabled row."""
    entity_type = _MODEL_CLASSES.get(type(obj))
    if entity_type is None:
        return None
    cfg = _REGISTRY.get(entity_type)
    if cfg is None or not cfg["enabled"]:
        return None
    return entity_type, cfg


def _provenance(cfg: dict[str, Any]) -> tuple[uuid.UUID | None, str, str] | None:
    """Resolve ``(actor_id, actor_type, source)`` or ``None`` to skip capture.

    The optional per-entity ``sources`` gate is applied here: an entity
    configured for ``["api", "admin"]`` records nothing from a Celery task.
    """
    actor_id, actor_type, source = resolve_provenance()
    allowed = cfg.get("sources")
    if allowed is not None and source not in allowed:
        return None
    # Normalise onto the stored vocabulary; an unknown actor type is a system
    # actor, never a guess at a user.
    try:
        actor_type = ChangeActorType(actor_type).value
    except ValueError:
        actor_type = ChangeActorType.SYSTEM.value
    try:
        source = ChangeSource(source).value
    except ValueError:
        source = ChangeSource.SERVICE.value
    return actor_id, actor_type, source


def _values_equal(old: Any, new: Any) -> bool:
    """Compare two raw values without coercing types.

    ``True == 1`` in Python, but a flag flip and an integer change are
    different audit facts — the type must match for values to be equal here.
    """
    if type(old) is not type(new):
        return False
    return bool(old == new)


def _history_values(state: Any, field: str) -> tuple[Any, Any, bool]:
    """Return ``(old, new, is_modified)`` for one attribute from ORM history.

    SQLAlchemy's ``History`` has no ``is_modified()`` in 2.x — the documented
    test is ``history.added or history.deleted``.
    """
    attr = state.attrs.get(field)
    if attr is None:
        return None, None, False
    history = attr.history
    if not (history.added or history.deleted):
        return None, None, False
    deleted = list(history.deleted)
    added = list(history.added)
    old = deleted[0] if len(deleted) == 1 else (deleted or None)
    new = added[0] if len(added) == 1 else (added or None)
    return old, new, True


def _build_entry(
    *,
    entity_type: str,
    entity_id: Any,
    operation: ChangeOperation,
    raw_changes: list[tuple[str, Any, Any]],
    provenance: tuple[uuid.UUID | None, str, str],
) -> dict[str, Any] | None:
    """Assemble one insertable row. ``None`` when nothing is worth storing.

    An update that ends with no field diffs (a no-op assignment, or a flush
    that only touched untracked columns) produces no row — this is the no-op
    filter that keeps the table a record of *changes*, not of writes.
    """
    if not raw_changes:
        return None
    changes, truncated = build_changed_fields(raw_changes)
    if not changes:
        return None
    actor_id, actor_type, source = provenance
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id not in (None, "") else "",
        "operation": operation.value,
        "changed_fields": changes,
        "actor_id": actor_id,
        "actor_type": actor_type,
        "request_id": _request_id(),
        "source": source,
        "occurred_at": datetime.now(UTC),
        "truncated": truncated,
    }


def _request_id() -> str | None:
    try:
        context = structlog.contextvars.get_contextvars()
    except Exception:  # pragma: no cover - defensive
        return None
    request_id = context.get("request_id") or context.get("correlation_id")
    return str(request_id) if request_id else None


def collect_change_entries(session: Session) -> list[dict[str, Any]]:
    """Read the session's pending changes into insertable rows.

    Pure with respect to the business objects. Exposed (not private) so the
    capture logic can be unit-tested against any session-like object.
    """
    entries: list[dict[str, Any]] = []

    for obj in session.new:
        routed = _route(obj)
        if routed is None:
            continue
        entity_type, cfg = routed
        if "create" not in cfg["operations"]:
            continue
        provenance = _provenance(cfg)
        if provenance is None:
            continue
        # Creation has no previous state: every tracked field is recorded with
        # old_value=None so the row reads as "this is what it was born with".
        raw = [
            (field, None, getattr(obj, field, None))
            for field in cfg["fields"]
            if hasattr(obj, field)
        ]
        entry = _build_entry(
            entity_type=entity_type,
            entity_id=getattr(obj, "id", None),
            operation=ChangeOperation.CREATE,
            raw_changes=raw,
            provenance=provenance,
        )
        if entry is not None:
            entries.append(entry)

    previous_snapshot: dict[Any, dict[str, Any]] = session.info.get(_PREVIOUS_KEY, {})

    for obj in session.dirty:
        routed = _route(obj)
        if routed is None:
            continue
        entity_type, cfg = routed
        if "update" not in cfg["operations"]:
            continue
        if not session.is_modified(obj, include_collections=False):
            continue
        state = obj.__dict__.get("_sa_instance_state")
        if state is None:  # pragma: no cover - every mapped row has state
            continue
        snapshot = previous_snapshot.get(id(obj))
        raw = []
        for field in cfg["fields"]:
            old_value, new_value, modified = _history_values(state, field)
            if modified:
                # The ORM history is authoritative when it carries a deleted
                # value; otherwise (attribute was expired before assignment)
                # fall back to the pre-flush database snapshot.
                if old_value is None and snapshot is not None and field in snapshot:
                    old_value = snapshot[field]
                raw.append((field, old_value, new_value))
        if not raw:
            # Only untracked columns changed (or the values were reset to what
            # they already were) — nothing to record.
            continue
        # A same-value assignment on an expired attribute rewrites the row with
        # no real change; compare against the snapshot to keep no-ops out.
        if snapshot is not None:
            raw = [
                (field, old, new)
                for field, old, new in raw
                if not _values_equal(old, new)
            ]
            if not raw:
                continue
        provenance = _provenance(cfg)
        if provenance is None:
            continue
        entry = _build_entry(
            entity_type=entity_type,
            entity_id=getattr(obj, "id", None),
            operation=ChangeOperation.UPDATE,
            raw_changes=raw,
            provenance=provenance,
        )
        if entry is not None:
            entries.append(entry)

    for obj in session.deleted:
        routed = _route(obj)
        if routed is None:
            continue
        entity_type, cfg = routed
        if "delete" not in cfg["operations"]:
            continue
        provenance = _provenance(cfg)
        if provenance is None:
            continue
        # Deletion snapshots the values that are about to disappear, with
        # new_value=None (ERPNext transaction-deletion-record pattern).
        raw = [
            (field, getattr(obj, field, None), None)
            for field in cfg["fields"]
            if hasattr(obj, field)
        ]
        entry = _build_entry(
            entity_type=entity_type,
            entity_id=getattr(obj, "id", None),
            operation=ChangeOperation.DELETE,
            raw_changes=raw,
            provenance=provenance,
        )
        if entry is not None:
            entries.append(entry)

    return entries


#: ``session.info`` key holding the pre-flush database snapshot of tracked
#: rows: ``{id(obj): {field: value}}``.
_PREVIOUS_KEY = "change_tracking_previous"


def _preserve_previous_values(session: Session) -> None:
    """Snapshot the modified tracked rows straight from the database.

    An attribute assigned while expired — the normal state after any commit —
    reports an empty ``deleted`` history, and neither ``load_history()`` nor
    the ``active_history`` flag can recover it once the mapper is instrumented
    (which happens at import time, long before entities are registered here).
    The row still holds its old values at ``before_flush``, so the honest
    source is the database itself: one SELECT of the tracked columns per dirty
    row, keyed by primary key, stashed in ``session.info`` for the
    ``after_flush`` diff to read.

    Fail-soft: any failure logs and skips — capture degrades to a missing old
    value and never blocks the business flush.
    """
    from sqlalchemy import select

    previous: dict[Any, dict[str, Any]] = {}
    for obj in session.dirty:
        routed = _route(obj)
        if routed is None:
            continue
        _, cfg = routed
        entity_id = getattr(obj, "id", None)
        if entity_id is None:
            continue
        columns = [getattr(cfg["model"], field) for field in cfg["fields"]]
        try:
            with session.no_autoflush:
                row = session.execute(
                    select(*columns).where(cfg["model"].id == entity_id)
                ).first()
        except Exception:
            logger.warning(
                "change_tracking_preload_failed",
                error=traceback.format_exc(),
            )
            continue
        if row is not None:
            previous[id(obj)] = dict(zip(cfg["fields"], row, strict=False))
    session.info[_PREVIOUS_KEY] = previous


def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:  # noqa: ARG001
    """Load previous values while the rows still hold them.

    Fail-soft like the capture itself: a preload problem degrades the diff to a
    missing old value and must never block the business flush.
    """
    try:
        _preserve_previous_values(session)
    except Exception:
        logger.warning("change_tracking_preload_failed", error=traceback.format_exc())


def _after_flush(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    """Persist field-level diffs for the flush that just succeeded.

    Fail-soft by contract: the business flush has already emitted its SQL, and
    change capture must never be able to undo or block it.
    """
    try:
        entries = collect_change_entries(session)
        if not entries:
            return
        _write_entries(session, entries)
    except Exception:
        logger.warning(
            "change_tracking_persist_failed",
            error=traceback.format_exc(),
        )


def _write_entries(session: Session, entries: list[dict[str, Any]]) -> None:
    """Insert the rows into the caller's transaction.

    Prefers one batched Core insert against the session's connection (no ORM
    unit-of-work involvement, so it cannot recurse into another flush). Falls
    back to ORM ``add_all`` for session doubles and connectionless sessions.
    """
    if isinstance(session, Session) and session.bind is not None:
        session.execute(insert(EntityChangeLog), entries)
        return
    session.add_all([EntityChangeLog(**entry) for entry in entries])


# ── Installation ─────────────────────────────────────────────────────────────

_INSTALLED = False


def install_change_tracking() -> bool:
    """Attach the flush listener exactly once per process.

    Returns ``True`` when this call performed the installation. Idempotent —
    SQLAlchemy raises on a duplicate ``listen`` of a function-based event, so
    the guard is what makes re-imports and test setups safe.
    """
    global _INSTALLED
    if _INSTALLED:
        return False
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "after_flush", _after_flush)
    _INSTALLED = True
    return True


def unregister_tracked_entity(entity_type: str) -> None:
    """Drop one tracked entity (tests only).

    Removes the routing entry and the class reverse-lookup so a fixture can
    register a synthetic model and leave the registry as it found it.
    """
    cfg = _REGISTRY.pop(entity_type, None)
    if cfg is None:
        return
    _MODEL_CLASSES.pop(cfg["model"], None)
    REGISTERED_ENTITIES.pop(entity_type, None)


def uninstall_change_tracking() -> bool:
    """Detach the listeners (tests only)."""
    global _INSTALLED
    if not _INSTALLED:
        return False
    event.remove(Session, "before_flush", _before_flush)
    event.remove(Session, "after_flush", _after_flush)
    _INSTALLED = False
    return True


def is_tracked(model_cls: type[Any]) -> bool:
    """True when ``model_cls`` is a routed, enabled tracked entity."""
    return _MODEL_CLASSES.get(model_cls) in _REGISTRY


def tracked_model(entity_type: str) -> type[Any] | None:
    cfg = _REGISTRY.get(entity_type)
    return cfg["model"] if cfg else None


# ── Boot wiring ──────────────────────────────────────────────────────────────

_register_default_entities()
install_change_tracking()

__all__ = [
    "MAX_FIELD_LENGTH",
    "REGISTERED_ENTITIES",
    "TRACKED_ENTITIES",
    "build_changed_fields",
    "collect_change_entries",
    "install_change_tracking",
    "is_tracked",
    "register_tracked_entity",
    "tracked_model",
    "uninstall_change_tracking",
]