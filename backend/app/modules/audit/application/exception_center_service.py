"""Operational Exception Center application service.

Conforms to Phase 32 / Rule 32 / ADMIN-003:
Captures, logs, alerts, and manages operational anomalies across commerce, payments,
inventory, search, and shipping.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.modules.audit.application import audit_service
from app.modules.audit.domain.operational_exceptions import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    OperationalExceptionDomain,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OperationalExceptionCenter:
    """Central registry and workflow manager for operational anomalies."""

    def __init__(self) -> None:
        # Fast in-memory operational registry for real-time alerting
        self._registry: dict[uuid.UUID, OperationalExceptionDomain] = {}

    async def record_exception(
        self,
        db: AsyncSession | None,
        *,
        exception_type: ExceptionType,
        severity: ExceptionSeverity,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> OperationalExceptionDomain:
        """Record an operational anomaly, publish audit log, and structure error telemetry."""
        record = OperationalExceptionDomain(
            id=uuid.uuid4(),
            exception_type=exception_type,
            severity=severity,
            status=ExceptionStatus.OPEN,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            created_at=datetime.now(UTC),
        )
        self._registry[record.id] = record

        log_data = {
            "exception_id": str(record.id),
            "exception_type": record.exception_type.value,
            "severity": record.severity.value,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
        }

        if severity == ExceptionSeverity.CRITICAL:
            await logger.aerror("operational_exception_critical", **log_data)
        elif severity == ExceptionSeverity.HIGH:
            await logger.aerror("operational_exception_high", **log_data)
        else:
            await logger.awarn("operational_exception_warning", **log_data)

        if db is not None:
            await audit_service.log_action(
                db,
                actor_id=actor_id,
                action=f"EXCEPTION_{exception_type.value}",
                resource=entity_type,
                resource_id=uuid.UUID(entity_id) if len(entity_id) == 36 else None,
                after=details,
                extra_data={
                    "severity": severity.value,
                    "exception_id": str(record.id),
                },
            )

        return record

    def get_exception(self, exception_id: uuid.UUID) -> OperationalExceptionDomain | None:
        return self._registry.get(exception_id)

    def assign_owner(
        self, exception_id: uuid.UUID, owner_id: uuid.UUID
    ) -> OperationalExceptionDomain | None:
        item = self._registry.get(exception_id)
        if item:
            item.assign(owner_id)
            logger.info(
                "operational_exception_assigned",
                exception_id=str(exception_id),
                owner_id=str(owner_id),
            )
        return item

    def resolve_exception(
        self, exception_id: uuid.UUID, notes: str
    ) -> OperationalExceptionDomain | None:
        item = self._registry.get(exception_id)
        if item:
            item.resolve(notes)
            logger.info(
                "operational_exception_resolved", exception_id=str(exception_id), notes=notes
            )
        return item

    def list_exceptions(
        self,
        severity: ExceptionSeverity | None = None,
        status: ExceptionStatus | None = None,
    ) -> Sequence[OperationalExceptionDomain]:
        """List active operational exceptions filtered by status and severity."""
        results = list(self._registry.values())
        if severity:
            results = [r for r in results if r.severity == severity]
        if status:
            results = [r for r in results if r.status == status]
        return sorted(results, key=lambda r: r.created_at, reverse=True)


# Global singleton instance
exception_center = OperationalExceptionCenter()
