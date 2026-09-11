"""Base entity mixin for domain models.

Provides identity (UUID), audit timestamps, and equality semantics based on
the entity's ``id`` rather than object identity.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


class Entity:
    """Base class for all domain entities.

    Two entities are considered equal if they share the same type and ``id``.
    """

    __slots__ = ("created_at", "id", "updated_at")

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,  # noqa: A002  # API parameter name is the public contract
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id: uuid.UUID = id or uuid.uuid4()
        self.created_at: datetime = created_at or datetime.now(UTC)
        self.updated_at: datetime = updated_at or datetime.now(UTC)

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp to *now*."""
        self.updated_at = datetime.now(UTC)

    # ── Equality / hashing ────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id}>"


class AggregateRoot(Entity):
    """An entity that is also the root of an aggregate.

    Aggregate roots collect domain events that are dispatched after the
    unit-of-work commits successfully.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._events: list[Any] = []

    def register_event(self, event: Any) -> None:
        """Record a domain event to be dispatched later."""
        self._events.append(event)

    def collect_events(self) -> list[Any]:
        """Return and clear all pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events
