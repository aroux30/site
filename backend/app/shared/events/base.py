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
    """In-process event bus for publishing and subscribing to domain events.

    This is a simple synchronous bus suitable for monolith deployments.  For
    microservice architectures, replace this with a message-broker adapter
    (e.g., RabbitMQ, Kafka).
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Any]] = {}

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Any,
    ) -> None:
        """Register *handler* to be called when *event_type* is published."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Dispatch *event* to all registered handlers."""
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            await handler(event)

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """Dispatch a batch of events in order."""
        for event in events:
            await self.publish(event)


# Module-level singleton
event_bus = EventBus()
