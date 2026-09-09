"""Approval workflow application service.

Handles request creation, listing, retrieval, review actions, and execution
of automated side-effects upon approval.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.approvals.domain.models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalLevel,
    ApprovalRequest,
    ApprovalStatus,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


async def _execute_side_effects(
    db: AsyncSession,
    request: ApprovalRequest,
    actor_id: uuid.UUID,
) -> None:
    """Execute domain side-effects when an approval request is approved."""
    resource = (request.resource or "").lower().strip()
    req_type = (request.type or "").lower().strip()
    payload = request.data or {}

    await logger.ainfo(
        "approval_executing_side_effects",
        request_id=str(request.id),
        resource=resource,
        type=req_type,
        actor_id=str(actor_id),
    )

    # 1. Product Price Change
    if resource in ("product_price", "product_variant", "variant_price") or "price" in req_type:
        try:
            from app.modules.catalog.domain.models import ProductVariant

            variant_id_raw = payload.get("variant_id") or request.resource_id
            if variant_id_raw:
                variant_id = uuid.UUID(str(variant_id_raw))
                variant = await db.get(ProductVariant, variant_id)
                if variant:
                    new_price = payload.get("new_price") or payload.get("price")
                    if new_price is not None:
                        variant.price = int(new_price)
                    compare_at_price = payload.get("compare_at_price")
                    if compare_at_price is not None:
                        variant.compare_at_price = int(compare_at_price)
                    await logger.ainfo(
                        "approval_side_effect_price_updated",
                        variant_id=str(variant_id),
                        new_price=new_price,
                    )
        except Exception as exc:
            await logger.aerror(
                "approval_side_effect_price_error",
                error=str(exc),
                request_id=str(request.id),
            )

    # 2. Product Publish
    elif resource in ("product_publish", "product") or "publish" in req_type:
        try:
            from app.modules.catalog.domain.models import Product, ProductStatus

            product_id_raw = request.resource_id or payload.get("product_id")
            if product_id_raw:
                product_id = uuid.UUID(str(product_id_raw))
                product = await db.get(Product, product_id)
                if product:
                    product.status = ProductStatus.PUBLISHED
                    product.is_active = True
                    await logger.ainfo(
                        "approval_side_effect_product_published",
                        product_id=str(product.id),
                    )
        except Exception as exc:
            await logger.aerror(
                "approval_side_effect_publish_error",
                error=str(exc),
                request_id=str(request.id),
            )

    # 3. Refund Execution
    elif resource in ("refund", "payment_refund") or "refund" in req_type:
        try:
            from app.modules.payments.application.payment_service import (
                _get_payment_or_raise,
                refund_payment,
            )

            payment_id_raw = request.resource_id or payload.get("payment_id")
            if payment_id_raw:
                payment_id = uuid.UUID(str(payment_id_raw))
                payment = await _get_payment_or_raise(db, payment_id)
                amount = int(payload.get("amount", payment.amount))
                reason = request.reason or payload.get("reason", "Approved by manager")

                await refund_payment(
                    db,
                    payment_id=payment_id,
                    amount=amount,
                    reason=reason,
                    actor_id=actor_id,
                )
                await logger.ainfo(
                    "approval_side_effect_refund_completed",
                    payment_id=str(payment_id),
                    amount=amount,
                )
        except Exception as exc:
            await logger.aerror(
                "approval_side_effect_refund_error",
                error=str(exc),
                request_id=str(request.id),
            )

    else:
        await logger.ainfo(
            "approval_side_effect_unhandled_or_generic",
            resource=resource,
            request_id=str(request.id),
        )


class ApprovalService:
    """Approval workflow service providing core domain actions."""

    @staticmethod
    async def create_request(
        db: AsyncSession,
        requester_id: uuid.UUID,
        type: str,
        resource: str,
        resource_id: Optional[uuid.UUID] = None,
        level: ApprovalLevel | str = ApprovalLevel.LOW,
        data: Optional[dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Submit a new approval request."""
        if isinstance(level, str):
            try:
                level_enum = ApprovalLevel(level.lower())
            except ValueError:
                level_enum = ApprovalLevel.LOW
        else:
            level_enum = level

        approval_request = ApprovalRequest(
            requester_id=requester_id,
            type=type,
            resource=resource,
            resource_id=resource_id,
            level=level_enum,
            status=ApprovalStatus.PENDING,
            data=data,
            reason=reason,
        )
        db.add(approval_request)
        await db.commit()

        # Reload with relationships
        return await ApprovalService.get_request(db, approval_request.id)  # type: ignore[return-value]

    @staticmethod
    async def list_requests(
        db: AsyncSession,
        status: Optional[ApprovalStatus | str] = None,
        level: Optional[ApprovalLevel | str] = None,
        resource: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ApprovalRequest], int]:
        """List approval requests matching optional filters with pagination."""
        stmt = (
            select(ApprovalRequest)
            .options(
                selectinload(ApprovalRequest.requester),
                selectinload(ApprovalRequest.actions).selectinload(ApprovalAction.actor),
            )
        )
        count_stmt = select(func.count(ApprovalRequest.id))

        if status is not None:
            if isinstance(status, str):
                try:
                    status_enum = ApprovalStatus(status.lower())
                except ValueError:
                    status_enum = None
            else:
                status_enum = status
            if status_enum is not None:
                stmt = stmt.where(ApprovalRequest.status == status_enum)
                count_stmt = count_stmt.where(ApprovalRequest.status == status_enum)

        if level is not None:
            if isinstance(level, str):
                try:
                    level_enum = ApprovalLevel(level.lower())
                except ValueError:
                    level_enum = None
            else:
                level_enum = level
            if level_enum is not None:
                stmt = stmt.where(ApprovalRequest.level == level_enum)
                count_stmt = count_stmt.where(ApprovalRequest.level == level_enum)

        if resource is not None and resource.strip():
            resource_val = resource.strip()
            stmt = stmt.where(ApprovalRequest.resource == resource_val)
            count_stmt = count_stmt.where(ApprovalRequest.resource == resource_val)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = stmt.order_by(ApprovalRequest.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def get_request(
        db: AsyncSession,
        request_id: uuid.UUID,
    ) -> Optional[ApprovalRequest]:
        """Fetch an approval request by its ID with requester and actions loaded."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id)
            .options(
                selectinload(ApprovalRequest.requester),
                selectinload(ApprovalRequest.actions).selectinload(ApprovalAction.actor),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def review_request(
        db: AsyncSession,
        request_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: ApprovalActionType | str,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        """Review (approve or reject) a pending approval request."""
        request = await ApprovalService.get_request(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found",
            )

        if request.status != ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval request already has status '{request.status.value}'",
            )

        if isinstance(action, str):
            try:
                action_enum = ApprovalActionType(action.lower())
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid approval action '{action}'",
                ) from exc
        else:
            action_enum = action

        # Create action record
        approval_action = ApprovalAction(
            request_id=request.id,
            actor_id=actor_id,
            action=action_enum,
            comment=comment,
        )
        db.add(approval_action)

        # Update request status
        if action_enum == ApprovalActionType.APPROVE:
            request.status = ApprovalStatus.APPROVED
            await _execute_side_effects(db, request, actor_id)
        else:
            request.status = ApprovalStatus.REJECTED

        await db.commit()

        # Reload with updated relations
        reloaded = await ApprovalService.get_request(db, request.id)
        return reloaded or request


# Module-level aliases for direct functional imports
create_request = ApprovalService.create_request
list_requests = ApprovalService.list_requests
get_request = ApprovalService.get_request
review_request = ApprovalService.review_request
