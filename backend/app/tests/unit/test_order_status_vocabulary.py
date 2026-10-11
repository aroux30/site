"""The 7-status vocabulary (2026-10-11) and its two payment-waiting states.

Owner decision: WooCommerce-style lifecycle for a digital store. The key
distinction is between the two payment-waiting states, because they have
OPPOSITE expiry rules:

  WAITING_PAYMENT_GATEWAY — gateway order; the callback decides. Abandoned ones expire
                    to CANCELED on a timer.
  WAITING_PAYMENT_CARD    — card-to-card; a human must eyeball the receipt. Must NEVER
                    expire, however late the admin gets.

Auto-cancelling WAITING_PAYMENT_CARD would destroy a sale whose money has already
landed in the account. That is the single most expensive mistake this
vocabulary makes possible, so it is pinned by a test rather than a comment.
"""

from __future__ import annotations

import inspect

import pytest


def test_enum_has_exactly_the_seven_owner_statuses():
    from app.modules.orders.domain.models import OrderStatus

    assert {m.value for m in OrderStatus} == {
        "waiting_payment_gateway",
        "waiting_payment_card",
        "pending",
        "processing",
        "completed",
        "canceled",
        "refunded",
    }


def test_physical_store_statuses_are_gone():
    """The removed six modelled packing/shipping — a digital store has none.

    Asserted by name rather than by count so a future addition fails loudly
    instead of silently satisfying a length check.
    """
    from app.modules.orders.domain.models import OrderStatus

    values = {m.value for m in OrderStatus}
    for gone in (
        "confirmed",
        "packing",
        "shipped",
        "delivered",
        "on_hold",
        "returned",
        "partially_refunded",
    ):
        assert gone not in values, f"{gone} is back — this store is digital"


def test_chain_is_the_short_linear_fulfilment_path():
    from app.modules.orders.application.order_service import _VALID_TRANSITIONS
    from app.modules.orders.domain.models import OrderStatus

    assert _VALID_TRANSITIONS[OrderStatus.PENDING] == frozenset(
        {OrderStatus.PROCESSING, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    )
    assert _VALID_TRANSITIONS[OrderStatus.PROCESSING] == frozenset(
        {OrderStatus.COMPLETED, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    )


def test_both_payment_waiting_states_advance_to_pending():
    from app.modules.orders.application.order_service import _VALID_TRANSITIONS
    from app.modules.orders.domain.models import OrderStatus

    # A gateway callback and an admin approval both land on the same state:
    # paid, and now the operator's problem.
    for waiting in (OrderStatus.WAITING_PAYMENT_GATEWAY, OrderStatus.WAITING_PAYMENT_CARD):
        assert OrderStatus.PENDING in _VALID_TRANSITIONS[waiting], (
            f"{waiting} has no path to the operator's lane — a paid order would "
            "be stuck with nobody able to work on it"
        )


def test_terminal_states_have_no_exit():
    from app.modules.orders.application.order_service import _VALID_TRANSITIONS
    from app.modules.orders.domain.models import OrderStatus

    for terminal in (OrderStatus.COMPLETED, OrderStatus.CANCELED, OrderStatus.REFUNDED):
        assert _VALID_TRANSITIONS[terminal] == frozenset()


def test_every_non_terminal_state_can_be_refunded():
    """An admin can refund an order that never got paid for."""
    from app.modules.orders.application.order_service import _VALID_TRANSITIONS
    from app.modules.orders.domain.models import OrderStatus

    for status in OrderStatus:
        if _VALID_TRANSITIONS[status]:
            assert OrderStatus.REFUNDED in _VALID_TRANSITIONS[status], (
                f"{status} cannot be refunded — money could get stuck with no "
                "order state to record it"
            )


# ── The expiry rule ────────────────────────────────────────────────────────


def test_stale_sweep_targets_waiting_payment_gateway_and_nothing_else():
    """The Celery sweep must filter on WAITING_PAYMENT_GATEWAY alone.

    Read from the source rather than trusting the docstring: the filter is
    what decides which rows a mass UPDATE can touch, and a widened filter
    here auto-cancels paid orders.
    """
    from app.modules.orders.application import tasks

    src = inspect.getsource(tasks)
    assert "OrderStatus.WAITING_PAYMENT_GATEWAY" in src, (
        "the sweep no longer filters on WAITING_PAYMENT_GATEWAY — check what it "
        "cancels before shipping this"
    )
    # The dangerous statuses must not appear as a sweep filter.
    for forbidden in (
        "filter_by(status=OrderStatus.PENDING)",
        "filter_by(status=OrderStatus.WAITING_PAYMENT_CARD)",
        "status.in_([OrderStatus.PENDING",
    ):
        assert forbidden not in src, (
            f"the sweep can cancel {forbidden} — a card-to-card order must "
            "wait for an admin, and a paid PENDING order is the operator's"
        )


def test_sweep_source_never_mentions_waiting_payment_card_as_a_candidate():
    """A belt-and-braces check on the whole task module.

    WAITING_PAYMENT_CARD appearing anywhere near the candidate query would mean the
    no-auto-cancel rule is one refactor away from being broken.
    """
    from app.modules.orders.application import tasks

    src = inspect.getsource(tasks)
    query_lines = [
        line
        for line in src.splitlines()
        if "select(Order)" in line or "filter_by(status" in line
    ]
    for line in query_lines:
        assert "WAITING_PAYMENT_CARD" not in line, (
            f"the candidate query references WAITING_PAYMENT_CARD: {line.strip()!r}"
        )


def test_customer_can_cancel_from_all_three_pre_completion_states():
    from app.modules.orders.application.order_service import _CUSTOMER_CANCELABLE
    from app.modules.orders.domain.models import OrderStatus

    assert set(_CUSTOMER_CANCELABLE) == {
        OrderStatus.WAITING_PAYMENT_GATEWAY,
        OrderStatus.WAITING_PAYMENT_CARD,
        OrderStatus.PENDING,
    }


def test_opening_status_is_chosen_by_payment_method():
    """Checkout must not file a card-to-card order as auto-expiring."""
    from app.modules.checkout.application.checkout_service import _is_card_to_card

    for slug in ("card_to_card", "CARD_TO_CARD", "card-transfer", "Card To Card", "c2c"):
        assert _is_card_to_card(slug) is True, f"{slug!r} should need a human"

    for slug in ("zarinpal", "wallet", "online", "", None):
        assert _is_card_to_card(slug) is False, f"{slug!r} must not be gated on an admin"


@pytest.mark.parametrize("slug", ["zarinpal", "wallet"])
def test_gateway_methods_open_in_waiting_payment_gateway(slug):
    from app.modules.checkout.application.checkout_service import _is_card_to_card
    from app.modules.orders.domain.models import OrderStatus

    opening = (
        OrderStatus.WAITING_PAYMENT_CARD if _is_card_to_card(slug) else OrderStatus.WAITING_PAYMENT_GATEWAY
    )
    assert opening is OrderStatus.WAITING_PAYMENT_GATEWAY