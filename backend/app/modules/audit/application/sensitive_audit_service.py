"""Staff sensitive data access audit service (Karta Phase 7/9 - Admin Audit Trail).

Implements:
- Logging operator access to decrypted PINs, unmasked card PANs, and bulk exports
- Immutable audit record creation using the central AuditLog ledger
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.modules.audit.domain.models import AuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def log_sensitive_access(
    db: AsyncSession,
    actor_id: uuid.UUID,
    # One of: "view_decrypted_pin", "view_unmasked_card",
    # "bulk_export_cards", "approve_receipt"
    action: str,
    resource: str,  # "digital_card", "user_bank_card", "card_transfer_receipt"
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an immutable audit entry when staff accesses sensitive customer data."""
    safe_actor_id = uuid.UUID(str(actor_id))
    safe_resource_id = uuid.UUID(str(resource_id)) if resource_id else None

    entry = AuditLog(
        actor_id=safe_actor_id,
        action=action.strip(),
        resource=resource.strip(),
        resource_id=safe_resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        extra_data=extra_metadata,
    )
    db.add(entry)
    await db.flush()

    await logger.awarning(
        "sensitive_data_accessed_by_staff",
        actor_id=str(safe_actor_id),
        action=action,
        resource=resource,
        resource_id=str(safe_resource_id) if safe_resource_id else None,
        ip=ip_address,
    )
    return entry
