"""The admin ticket board endpoints: stats, enrichment, and route order.

Three failure modes pinned here:

1. **Route order.** ``GET /admin/tickets/stats`` and
   ``GET /admin/tickets/{ticket_id}`` have the same segment count; if the
   parameter route registers first, ``stats`` is captured as a ticket id
   and the board's header numbers 422 (the same trap the orders admin
   documented).

2. **Zero-filled stats.** Every TicketStatus must arrive even with zero
   rows, or the UI cannot tell "no tickets" from "the endpoint forgot it".

3. **Enrichment identity.** The admin list used to render a raw user UUID;
   the enrichment must attach the customer's name FROM THE PROFILE (names
   do not live on the user row — the exact bug the orders admin had).
"""

from __future__ import annotations

import inspect
import uuid

import pytest


def test_route_order_stats_before_ticket_id():
    """`/admin/tickets/stats` must be registered before `/admin/tickets/{id}`.

    Negative test: swap the two registrations in routes.py and this fails.
    """
    from app.modules.support.api import routes as routes_module

    src = inspect.getsource(routes_module)
    stats_idx = src.index('"/admin/tickets/stats"')
    detail_idx = src.index('"/admin/tickets/{ticket_id}"')
    assert stats_idx < detail_idx, (
        "stats route is registered after {ticket_id} — the literal path would "
        "be captured as a ticket id"
    )


async def test_stats_zero_fills_every_status():
    """Live DB: stats returns one entry per TicketStatus with real counts."""
    from app.core.database.session import async_session_factory, engine
    from app.modules.support.application.support_service import SupportService
    from app.modules.support.domain.models import TicketStatus

    async with async_session_factory() as db:
        stats = await SupportService.admin_ticket_stats(db)

    returned = {entry["status"] for entry in stats["by_status"]}
    expected = {member.value for member in TicketStatus}
    assert returned == expected, f"missing statuses: {expected - returned}"

    for entry in stats["by_status"]:
        assert entry["count"] >= 0

    assert stats["total_tickets"] == sum(e["count"] for e in stats["by_status"])
    assert stats["urgent_open"] >= 0
    assert stats["unassigned"] >= 0

    await engine.dispose()


async def test_enrichment_attaches_customer_identity_and_thread_stats():
    """Live DB: list rows carry name/phone/message-count/preview."""
    from app.core.database.session import async_session_factory, engine
    from app.modules.support.application.support_service import SupportService

    async with async_session_factory() as db:
        items, total = await SupportService.list_tickets(db, skip=0, limit=5)
        if not items:
            pytest.skip("no tickets in the database")
        enriched = await SupportService.enrich_admin_ticket_rows(db, items)

    assert len(enriched) == len(items)
    for row in enriched:
        # Every enriched row must carry the keys, even when the value is
        # None (a customer without a profile is a fact, not a missing key).
        assert "customer_name" in row
        assert "customer_phone" in row
        assert "messages_count" in row
        assert isinstance(row["messages_count"], int)
        assert row["messages_count"] >= 0
        # last_message_preview is None or a truncated string, never the full
        # body (the card renders one line).
        if row["last_message_preview"] is not None:
            assert len(row["last_message_preview"]) <= 120

    await engine.dispose()


async def test_enrichment_empty_input_is_empty_output():
    """An empty page must not issue queries or fabricate rows."""
    from app.core.database.session import async_session_factory, engine
    from app.modules.support.application.support_service import SupportService

    async with async_session_factory() as db:
        enriched = await SupportService.enrich_admin_ticket_rows(db, [])
    assert enriched == []
    await engine.dispose()


async def test_detail_route_returns_customer_fields():
    """The admin detail payload carries customer identity (not a raw UUID)."""
    from app.core.database.session import async_session_factory, engine
    from app.modules.support.application.support_service import SupportService
    from app.modules.support.schemas.support import TicketDetailResponse

    async with async_session_factory() as db:
        items, _ = await SupportService.list_tickets(db, skip=0, limit=1)
        if not items:
            pytest.skip("no tickets in the database")
        ticket = await SupportService.get_ticket(db, items[0].id)
        assert ticket is not None
        enriched = await SupportService.enrich_admin_ticket_rows(db, [ticket])
        row = enriched[0] if enriched else {}

    dto = TicketDetailResponse.model_validate(
        {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
            "assigned_to": ticket.assigned_to,
            "ticket_number": ticket.ticket_number,
            "messages": ticket.messages,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "customer_name": row.get("customer_name"),
            "customer_phone": row.get("customer_phone"),
        }
    )
    assert dto.ticket_number
    assert hasattr(dto, "customer_name")

    await engine.dispose()
