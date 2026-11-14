"""Server-Sent Events stream for live chat.

An SSE upgrade over the 4s poller: the client opens one long-lived connection
and receives new messages as they are written. The stream is a *notification*
channel — it only says "there are messages newer than N"; the client still
fetches them over the normal endpoint. That keeps the stream cheap (no payload
serialization per tick) and means a dropped stream degrades to polling with no
special handling.

Design notes:

* **DB-polled, not pub/sub.** The chat writes already land in Postgres; adding
  Redis pub/sub would be a second source of truth and a second failure mode.
  The generator polls the message table on a short interval and yields only
  changes, which is what the client needs and nothing more.
* **Bounded lifetime.** Each connection lives at most ``_MAX_SECONDS`` so a
  stuck client cannot pin a worker connection forever; the browser's
  ``EventSource`` reconnects automatically.
* **Heartbeat comments.** A ``: ping`` every ``_PING_SECONDS`` keeps proxies and
  load balancers from closing an idle stream.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.database.session import async_session_factory
from app.modules.chat.application.chat_service import ChatService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()

#: How often the generator checks the message table.
_POLL_SECONDS = 2.0
#: A comment-only keepalive interval (proxies close idle connections).
_PING_SECONDS = 15.0
#: Hard cap on one connection's lifetime; EventSource reconnects transparently.
_MAX_SECONDS = 300.0


async def _event_stream(session_key: str, last_id: int) -> AsyncIterator[str]:
    """Yield SSE frames: a ``messages`` event when new rows appear, else pings."""
    elapsed = 0.0
    since_ping = 0.0
    # Tell the browser how long to wait before reconnecting (ms).
    yield "retry: 5000\n\n"
    while elapsed < _MAX_SECONDS:
        async with async_session_factory() as db:
            rows = await ChatService.list_messages_since(db, session_key, last_id)
        if rows:
            last_id = rows[-1].id
            payload = {
                "last_id": last_id,
                "count": len(rows),
                "roles": [str(r.role) for r in rows],
            }
            yield f"event: messages\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            since_ping = 0.0
        else:
            since_ping += _POLL_SECONDS
            if since_ping >= _PING_SECONDS:
                yield ": ping\n\n"
                since_ping = 0.0
        await asyncio.sleep(_POLL_SECONDS)
        elapsed += _POLL_SECONDS


@router.get(
    "/stream",
    summary="Live chat event stream (SSE)",
)
async def stream(
    request: Request,
    session_key: str,
    last_id: int = 0,
) -> StreamingResponse:
    """Open an SSE stream for one session.

    Public like the other widget routes: the session key is the capability (an
    unguessable client-generated id), matching the poll endpoints' access model.
    ``X-Accel-Buffering: no`` disables nginx response buffering so events are not
    held until the connection closes.
    """
    return StreamingResponse(
        _event_stream(session_key, last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
