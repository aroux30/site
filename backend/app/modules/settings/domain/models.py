"""Site settings domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class SqlNullOnNone(TypeDecorator):
    """Make ``None`` mean SQL NULL on a JSON column, not JSON ``null``.

    Postgres JSONB has two different empties and they are not interchangeable.
    The JSON value ``null`` is a real value that ``IS NOT NULL`` matches, so a
    column "cleared" by writing it is still holding a payload as far as every
    query in the codebase is concerned. Assigning Python ``None`` to a plain
    ``JSONB`` column serializes to exactly that value, silently: the write
    succeeds, the ORM reports ``None`` in memory, and the next read through a
    different session gets a row that never left the table.

    Wrapping the type makes Python ``None`` produce real SQL NULL, which is what
    every ``IS NULL`` / ``IS NOT NULL`` filter in the codebase already assumes.
    Assigning the JSON value ``None`` deliberately is no longer expressible,
    which is the correct trade: nothing in this project stores a meaningful JSON
    ``null``, and the alternative was a column that can never be emptied.
    """

    impl = JSONB
    cache_ok = True

    def bind_processor(self, dialect):
        inner = self.impl_instance.bind_processor(dialect)

        def process(value):
            # Not a short-circuit in process_bind_param: JSONB is itself a
            # TypeDecorator, so wrapping it means the outer decorator's
            # process_bind_param is never consulted -- JSONB's own bind_processor
            # runs first and turns None into the JSON text 'null'. Deciding here
            # is the only layer that actually sees the original Python value.
            return None if value is None else inner(value)

        return process



class SiteSetting(BaseModel):
    """Key-value configuration store for runtime site settings."""

    __tablename__ = "site_settings"
    __table_args__ = (
        Index("ix_site_settings_key", "key"),
        Index("ix_site_settings_group", "group"),
        Index("ix_site_settings_is_public", "is_public"),
    )

    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<SiteSetting(id={self.id}, key={self.key})>"


class SiteHealthRun(BaseModel):
    """One recorded run of the site health checks.

    WordPress runs Site Health twice a day and keeps a page of "background
    updates" history; the equivalent here was a live check that only answered
    the question "is it broken right now". A store whose disk filled up at 3am
    had no way to find out afterwards, because the check had run in a request
    nobody made.

    This table is what makes a scheduled run visible: the beat task writes here
    once a day, the admin screen lists what it found, and a failure that was
    fixed between two visits is still on the record.
    """

    __tablename__ = "site_health_runs"
    __table_args__ = (
        Index("ix_site_health_runs_started_at", "started_at"),
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: "scheduled" for the beat task, "manual" for a button press. A reader
    #: comparing two rows needs to know which is which: a manual run is a
    #: sample of one moment, a scheduled one is the state nobody was watching.
    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'scheduled'"),
    )
    #: The full report as ``run_checks`` produced it, so a later review reads
    #: the checks as they were rather than as they are now.
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    #: Worst status across the checks, precomputed so the list screen does not
    #: have to open every JSON blob to decide what to colour.
    worst_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: Why a run failed to produce a report at all (the worker died, the
    #: database was unreachable). Distinguishes "ran and found problems" from
    #: "did not run", which look identical otherwise.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SiteHealthRun(started_at={self.started_at}, "
            f"trigger={self.trigger}, worst={self.worst_status})>"
        )
