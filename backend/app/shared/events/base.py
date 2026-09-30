"""Domain event base class.

Domain events represent something meaningful that happened in the domain.
They are collected by aggregate roots and dispatched after the unit-of-work
commits, ensuring side-effects (notifications, projections, etc.) only run
when the primary transaction succeeds.

Example::

    class OrderPlaced(DomainEvent):
        order_id: uuid.UUID
        customer_id: uuid.UUID
        total_rials: int
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Immutable record of something that happened in the domain.

    All concrete events should subclass this and add their own fields.
    """

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str = ""
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-set event_type from class name if not explicitly overridden
        if "event_type" not in cls.model_fields or cls.model_fields["event_type"].default == "":
            # We override at instance level via default_factory in subclasses,
            # but also set a class-level fallback.
            pass

    def model_post_init(self, _context: Any) -> None:
        if not self.event_type:
            # Use object.__setattr__ because the model is frozen
            object.__setattr__(self, "event_type", type(self).__name__)


class EventBus:
    """In-process event bus — currently a no-op seam, deliberately kept inert.

    ``record_domain_event`` already writes every domain event to two places
    that do real work: the ``domain_events`` audit table and the transactional
    outbox (``outbox_service``), which the Celery drain consumes. The outbox is
    the live path; this bus is not.

    It has **zero subscribers** across the whole repository. ``publish()``
    therefore iterates an empty list on every call, and the only effect is the
    ``domain_event_bus_dispatch_failed`` warning — which can never fire.

    ``subscribe()`` now raises. Previously it accepted handlers that would be
    silently dropped, so a future handler would look wired and never run — the
    same "live code that does nothing" shape this class is being corrected for.
    If you need in-process reaction to an event today, either:

      * publish it to the outbox (``record_domain_event(..., publish_outbox=True)``)
        and handle it in ``automation/application/outbox_worker.py`` — that runs
        in a worker process and survives a restart; or
      * call the handler directly from the service that raises the event, which
        is honest about being synchronous and in-process.

    To revive this as a real bus, drop the ``raise`` below and register every
    handler at import time — but then audit the outbox path for duplication
    first, because a handler that also runs in the worker would fire twice.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Any]] = {}

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Any,
    ) -> None:
        """Rejected: this bus has no dispatcher and is not the delivery path."""
        raise RuntimeError(
            "EventBus.subscribe() is disabled: the bus has no subscribers and "
            "publish() is a no-op. Use the outbox (record_domain_event with "
            "publish_outbox=True) or call the handler directly. See the "
            "EventBus docstring for how to revive it."
        )

    async def publish(self, event: DomainEvent) -> None:
        """No-op. Kept so existing ``await event_bus.publish(...)`` calls stay valid."""
        return None

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """No-op. See :meth:`publish`."""
        return None


# Module-level singleton
event_bus = EventBus()
