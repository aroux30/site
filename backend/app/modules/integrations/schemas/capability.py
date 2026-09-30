"""Response schema for the integration capability registry.

The contract defines exactly one capability record shape, and this module
mirrors it field for field. Both endpoints return that same shape:

- ``GET /capabilities`` filters *which records* are returned (customer-visible
  ones); it does not reduce the fields within them.
- ``GET /admin/capabilities`` returns every record.

Publishing one shape rather than two means the two routes cannot drift, and
the response stays a plain list — the generation time is already carried per
record in ``updated_at``, so no envelope is needed.

The schema has no field that could hold a credential, merchant id, token,
host name, endpoint URL, stack trace, or raw environment value, so a secret
cannot leak by widening what is populated — only by adding a field, which is
a visible contract change.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.integrations.domain.status import (
    CapabilityCategory,
    CapabilityReason,
    CapabilityStatus,
)


class CapabilityResponse(BaseModel):
    """One integration capability, exactly as the contract describes it.

    ``configured`` and ``customer_visible`` are both published because both
    are contract fields and neither is sensitive: the first states whether
    local configuration is present, the second whether the capability is meant
    to be shown to customers. ``available_to_customers`` is the derived
    conclusion a customer surface should act on.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    category: CapabilityCategory
    display_name: str
    status: CapabilityStatus
    configured: bool
    customer_visible: bool
    available_to_customers: bool
    reason_code: CapabilityReason
    updated_at: datetime
