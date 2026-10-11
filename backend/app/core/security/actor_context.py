"""Request/task-scoped actor provenance.

Ambient "who is doing this?" state for code that runs deep inside a call stack
with no actor argument in hand — most importantly the SQLAlchemy change-capture
hook in the audit module, which fires inside ``after_flush`` where no route
signature is reachable.

The actor is *bound*, never inferred: :func:`bind_actor` is called by the
authentication dependencies (HTTP) and by the Celery task pre-run hook (worker).
When nothing has been bound the context reads as ``None`` and callers must fall
back to a system actor — an unbound change must never be attributed to whoever
happened to run last in the same context.

Why a ContextVar and not middleware request state: FastAPI resolves
dependencies in the same task context as the endpoint, and SQLAlchemy's async
bridge copies that context into the greenlet that runs ORM events. A
``ContextVar`` therefore survives the trip from ``Depends(get_current_user_id)``
down into a flush, while ``request.state`` does not.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

#: Source values. Kept as plain strings so this core module stays free of
#: module-level enum imports (the audit module maps them onto ChangeSource).
SOURCE_API = "api"
SOURCE_ADMIN = "admin"
SOURCE_SERVICE = "service"
SOURCE_SEED = "seed"
SOURCE_CELERY = "celery"

KNOWN_SOURCES: frozenset[str] = frozenset(
    {SOURCE_API, SOURCE_ADMIN, SOURCE_SERVICE, SOURCE_SEED, SOURCE_CELERY}
)


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Who is acting, and through which surface.

    ``ip_address``/``user_agent`` describe the originating request. They are
    part of the actor context — not a per-call argument — because the audit
    writers deep in the service layer (RBAC, CMS, settings) have no request
    object in hand; binding them once at the authentication funnel gives
    every audit row its request details without touching 40+ call sites.
    """

    actor_id: uuid.UUID | None = None
    source: str = SOURCE_SERVICE
    ip_address: str | None = None
    user_agent: str | None = None


_actor: ContextVar[ActorContext | None] = ContextVar("current_actor_context", default=None)

#: Sentinel for "argument omitted" — distinct from an explicit ``None``.
_UNSET: Any = object()


def bind_actor(
    actor_id: uuid.UUID | None = None,
    *,
    source: str = SOURCE_API,
    ip_address: Any = _UNSET,
    user_agent: Any = _UNSET,
) -> Token[ActorContext | None]:
    """Bind the acting identity for the current context.

    Returns the ContextVar token so a caller may restore the previous value.
    Idempotent overwrite is intentional: on an admin route the auth dependency
    binds ``api`` first and the permission gate re-binds ``admin`` afterwards,
    which is the value the change log should carry.

    ``ip_address``/``user_agent`` follow *keep-if-omitted* semantics: the
    re-binds above (``api`` → ``admin``, and the ``get_current_user_id``
    re-bind) must not silently drop the request details the first bind
    captured. Pass an explicit value — including ``None`` — to change them.
    """
    previous = _actor.get()
    if ip_address is _UNSET:
        ip_address = previous.ip_address if previous is not None else None
    if user_agent is _UNSET:
        user_agent = previous.user_agent if previous is not None else None
    return _actor.set(
        ActorContext(
            actor_id=actor_id,
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )


def clear_actor() -> None:
    """Drop any bound actor (used between Celery tasks)."""
    _actor.set(None)


def get_actor() -> ActorContext | None:
    """Return the bound actor context, or ``None`` when nothing is bound."""
    return _actor.get()


def current_actor_id() -> uuid.UUID | None:
    ctx = _actor.get()
    return ctx.actor_id if ctx is not None else None


def current_source(default: str = SOURCE_SERVICE) -> str:
    ctx = _actor.get()
    if ctx is None or ctx.source not in KNOWN_SOURCES:
        return default
    return ctx.source


def current_ip_address() -> str | None:
    """The bound request's client IP, or ``None`` outside a request."""
    ctx = _actor.get()
    return ctx.ip_address if ctx is not None else None


def current_user_agent() -> str | None:
    """The bound request's User-Agent header, or ``None`` outside a request."""
    ctx = _actor.get()
    return ctx.user_agent if ctx is not None else None


@contextmanager
def actor_scope(
    actor_id: uuid.UUID | None = None,
    *,
    source: str = SOURCE_SERVICE,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Iterator[ActorContext]:
    """Temporarily bind an actor and restore the previous one on exit.

    Used by tasks and tests that must not leak provenance into the calling
    context.
    """
    token = bind_actor(
        actor_id, source=source, ip_address=ip_address, user_agent=user_agent
    )
    try:
        yield ActorContext(
            actor_id=actor_id,
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    finally:
        _actor.reset(token)


# ── Provenance for the audit trail ───────────────────────────────────────────

#: Actor-type vocabulary shared with the audit change log.
ACTOR_TYPE_USER = "user"
ACTOR_TYPE_SYSTEM = "system"
ACTOR_TYPE_CELERY = "celery"


def _running_in_worker_task() -> bool:
    """True inside a Celery worker task execution (never during publish)."""
    try:
        from celery._state import get_current_worker_task

        return get_current_worker_task() is not None
    except Exception:  # pragma: no cover - celery absent or not yet loaded
        return False


def _in_request_context() -> bool:
    """True when a request/task bound its correlation id to the log context."""
    try:
        import structlog

        context = structlog.contextvars.get_contextvars()
    except Exception:  # pragma: no cover - defensive
        return False
    return bool(context.get("request_id") or context.get("correlation_id"))


def resolve_provenance() -> tuple[uuid.UUID | None, str, str]:
    """Return ``(actor_id, actor_type, source)`` for the current context.

    The fallback chain is deliberately explicit so an unauthenticated change is
    never attributed to a user:

    ============================  ==============  ===========
    context                       actor_type      source
    ============================  ==============  ===========
    bound actor with an id        ``user``        its source
    bound actor without an id     ``system``      its source
    Celery worker task            ``celery``      ``celery``
    HTTP request, no actor        ``system``      ``api``
    anything else (scripts)       ``system``      ``service``
    ============================  ==============  ===========
    """
    ctx = _actor.get()
    if ctx is not None:
        actor_type = ACTOR_TYPE_USER if ctx.actor_id is not None else ACTOR_TYPE_SYSTEM
        source = ctx.source if ctx.source in KNOWN_SOURCES else SOURCE_SERVICE
        return ctx.actor_id, actor_type, source

    if _running_in_worker_task():
        return None, ACTOR_TYPE_CELERY, SOURCE_CELERY

    if _in_request_context():
        return None, ACTOR_TYPE_SYSTEM, SOURCE_API

    return None, ACTOR_TYPE_SYSTEM, SOURCE_SERVICE
