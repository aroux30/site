"""Unit tests for the order state machine transition rules."""

import pytest
from app.core.exceptions.handlers import ValidationError
from app.modules.orders.application.order_service import (
    _CUSTOMER_CANCELABLE,
    _VALID_TRANSITIONS,
    _generate_order_number,
    _validate_transition,
)
from app.modules.orders.domain.models import OrderStatus


def test_order_number_format():
    """Verify generated order number matches ORD-YYYYMMDD-XXXX."""
    order_num = _generate_order_number()
    assert order_num.startswith("ORD-")
    parts = order_num.split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 4  # 4-char random code


def test_valid_forward_transitions():
    """Verify standard happy path transitions are allowed."""
    # PENDING -> CONFIRMED
    _validate_transition(OrderStatus.PENDING, OrderStatus.CONFIRMED)

    # CONFIRMED -> PROCESSING
    _validate_transition(OrderStatus.CONFIRMED, OrderStatus.PROCESSING)

    # PROCESSING -> PACKING
    _validate_transition(OrderStatus.PROCESSING, OrderStatus.PACKING)

    # PACKING -> SHIPPED
    _validate_transition(OrderStatus.PACKING, OrderStatus.SHIPPED)

    # SHIPPED -> DELIVERED
    _validate_transition(OrderStatus.SHIPPED, OrderStatus.DELIVERED)

    # DELIVERED -> COMPLETED
    _validate_transition(OrderStatus.DELIVERED, OrderStatus.COMPLETED)


def test_invalid_transitions_rejected():
    """Verify illegal transitions raise ValidationError."""
    # Cannot jump from PENDING directly to DELIVERED or COMPLETED
    with pytest.raises(ValidationError):
        _validate_transition(OrderStatus.PENDING, OrderStatus.DELIVERED)

    with pytest.raises(ValidationError):
        _validate_transition(OrderStatus.PENDING, OrderStatus.COMPLETED)

    # Cannot transition out of terminal state COMPLETED
    with pytest.raises(ValidationError):
        _validate_transition(OrderStatus.COMPLETED, OrderStatus.PENDING)

    # Cannot transition out of terminal state CANCELED
    with pytest.raises(ValidationError):
        _validate_transition(OrderStatus.CANCELED, OrderStatus.CONFIRMED)


def test_customer_cancelable_statuses():
    """Verify which statuses customers are permitted to cancel."""
    assert OrderStatus.PENDING in _CUSTOMER_CANCELABLE
    assert OrderStatus.CONFIRMED in _CUSTOMER_CANCELABLE
    assert OrderStatus.SHIPPED not in _CUSTOMER_CANCELABLE
    assert OrderStatus.COMPLETED not in _CUSTOMER_CANCELABLE
