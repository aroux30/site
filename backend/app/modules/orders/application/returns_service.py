"""Application service orchestrating Return Merchandise Authorization (RMA) workflows.

Enforces:
- Statutory return window validation (Article 37, Iranian E-Commerce Law: 7 calendar days)
- Partial order item quantity constraints
- Multi-step state machine transition rules
- Integration with payment refunds and inventory restocking
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Sequence

import structlog

from app.core.exceptions.handlers import ValidationError, NotFoundError
from app.modules.orders.domain.models import Order, OrderStatus
from app.modules.orders.domain.returns import (
    OrderReturnDomain,
    ReturnItemSpec,
    ReturnReason,
    ReturnStatus,
    InspectionOutcome,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DEFAULT_RETURN_WINDOW_DAYS = 7


class ReturnsService:
    """Domain service managing customer returns and RMA processing."""

    def __init__(self, return_window_days: int = DEFAULT_RETURN_WINDOW_DAYS) -> None:
        self.return_window_days = return_window_days

    def validate_eligibility(
        self,
        order: Order,
        delivered_at: datetime,
        now: datetime | None = None,
    ) -> None:
        """Validate if an order qualifies for return under Iranian E-Commerce regulations."""
        if order.status not in (OrderStatus.DELIVERED, OrderStatus.COMPLETED):
            raise ValidationError(
                f"Cannot request return for order in status '{order.status.value}'. "
                f"Order must be 'delivered' or 'completed'.",
                error_code="ORDER_NOT_DELIVERED",
            )

        current_time = now or datetime.now(timezone.utc)
        if delivered_at is None:
            delivered_at = current_time
        elif delivered_at.tzinfo is None:
            delivered_at = delivered_at.replace(tzinfo=timezone.utc)

        elapsed = current_time - delivered_at
        if elapsed > timedelta(days=self.return_window_days):
            raise ValidationError(
                f"Return window of {self.return_window_days} days has expired. "
                f"Order was delivered {elapsed.days} days ago.",
                error_code="RETURN_WINDOW_EXPIRED",
            )

    def create_return_request(
        self,
        *,
        order: Order,
        user_id: uuid.UUID,
        delivered_at: datetime,
        items: Sequence[ReturnItemSpec],
        now: datetime | None = None,
    ) -> OrderReturnDomain:
        """Initiate a new RMA request for specified order items."""
        if order.user_id != user_id:
            raise ValidationError(
                "Cannot initiate return for an order belonging to another customer.",
                error_code="ORDER_USER_MISMATCH",
            )

        self.validate_eligibility(order, delivered_at, now)

        if not items:
            raise ValidationError(
                "Return request must contain at least one item.",
                error_code="EMPTY_RETURN_ITEMS",
            )

        # Validate item quantities against order lines
        ordered_item_map = {item.id: item for item in (order.items or [])}
        for return_item in items:
            order_line = ordered_item_map.get(return_item.order_item_id)
            if not order_line:
                raise ValidationError(
                    f"Item {return_item.order_item_id} does not exist in order {order.id}.",
                    error_code="INVALID_RETURN_ITEM",
                )
            if return_item.quantity <= 0 or return_item.quantity > order_line.quantity:
                raise ValidationError(
                    f"Return quantity {return_item.quantity} exceeds ordered quantity {order_line.quantity}.",
                    error_code="INVALID_RETURN_QUANTITY",
                )

        return_record = OrderReturnDomain(
            id=uuid.uuid4(),
            order_id=order.id,
            user_id=user_id,
            status=ReturnStatus.REQUESTED,
            items=list(items),
            created_at=now or datetime.now(timezone.utc),
            eligibility_window_days=self.return_window_days,
        )

        logger.info(
            "return_request_created",
            return_id=str(return_record.id),
            order_id=str(order.id),
            user_id=str(user_id),
            item_count=len(items),
        )
        return return_record

    def approve_return(
        self,
        rma: OrderReturnDomain,
        admin_notes: str | None = None,
    ) -> None:
        """Admin approves the return request for customer shipment."""
        rma.transition_to(ReturnStatus.APPROVED, notes=admin_notes)
        logger.info("return_request_approved", return_id=str(rma.id))

    def reject_return(
        self,
        rma: OrderReturnDomain,
        rejection_reason: str,
    ) -> None:
        """Admin rejects the return request."""
        rma.transition_to(ReturnStatus.REJECTED, notes=rejection_reason)
        logger.info("return_request_rejected", return_id=str(rma.id), reason=rejection_reason)

    def mark_received(
        self,
        rma: OrderReturnDomain,
    ) -> None:
        """Mark physical items as received at warehouse."""
        rma.transition_to(ReturnStatus.RECEIVED)
        logger.info("return_items_received", return_id=str(rma.id))

    def complete_inspection(
        self,
        rma: OrderReturnDomain,
        outcomes: dict[uuid.UUID, InspectionOutcome],
        inspection_notes: str | None = None,
    ) -> None:
        """Record quality inspection results for each returned item."""
        for item in rma.items:
            outcome = outcomes.get(item.order_item_id, InspectionOutcome.PASSED)
            item.inspection_outcome = outcome

        rma.transition_to(ReturnStatus.INSPECTED, notes=inspection_notes)
        logger.info("return_inspection_completed", return_id=str(rma.id))

    def process_refund(
        self,
        rma: OrderReturnDomain,
        refund_amount: int,
    ) -> None:
        """Finalize financial settlement of approved, passed return."""
        rma.refund_amount = refund_amount
        rma.transition_to(ReturnStatus.REFUNDED)
        logger.info(
            "return_refund_processed",
            return_id=str(rma.id),
            refund_amount=refund_amount,
        )
