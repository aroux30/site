"""Approval workflow application service.

Handles request creation, listing, retrieval, review actions, and execution
of automated side-effects upon approval.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.modules.approvals.domain.models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalLevel,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApprovalStepStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


async def _actor_has_role(
    db: AsyncSession, *, actor_id: uuid.UUID, role_slug: str
) -> bool:
    """True when the actor holds the given role, or is a super admin.

    A role-gated step must not be approvable by anyone who happens to have
    ``approvals:write``; the chain says *who*, not just *how many*. A lookup
    failure denies (fail-closed): a step that cannot be verified is not
    silently opened to everyone.
    """
    try:
        from sqlalchemy import select as _select

        from app.modules.rbac.domain.models import Role, UserRole

        row = (
            await db.execute(
                _select(Role.slug)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == actor_id)
            )
        ).scalars().all()
        slugs = {s for s in row if s}
        return role_slug in slugs or "super_admin" in slugs
    except Exception:
        await logger.aexception(
            "approval_role_check_failed",
            actor_id=str(actor_id),
            role_slug=role_slug,
        )
        return False


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

    # 2. Product Publish — the req_type keyword check must not swallow content
    #    requests: a "content_publish" request for a cms_page/blog_post belongs
    #    to branch 4 below, not here.
    elif resource in ("product_publish", "product") or (
        "publish" in req_type and resource not in ("cms_page", "blog_post")
    ):
        try:
            from app.modules.catalog.domain.models import Product, ProductStatus

            product_id_raw = request.resource_id or payload.get("product_id")
            if product_id_raw:
                product_id = uuid.UUID(str(product_id_raw))
                product = await db.get(Product, product_id)
                if product:
                    # ProductStatus has no PUBLISHED member (draft/active/archived);
                    # ACTIVE is the sellable/"published" status used domain-wide.
                    product.status = ProductStatus.ACTIVE
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
            from app.modules.payments.domain.models import Refund, RefundStatus

            payment_id_raw = request.resource_id or payload.get("payment_id")
            if payment_id_raw:
                payment_id = uuid.UUID(str(payment_id_raw))
                payment = await _get_payment_or_raise(db, payment_id)
                # The refundable amount is derived from the payment itself,
                # never from the requester-supplied payload: a submitter must
                # not be able to pick a figure the reviewer never sees.
                # A payload amount may only *reduce* the refund (a partial
                # refund the reviewer explicitly approved); it can never
                # exceed what is actually refundable.
                requested_amount = payload.get("amount")
                already_refunded = await db.scalar(
                    select(func.coalesce(func.sum(Refund.amount), 0)).where(
                        Refund.payment_id == payment_id,
                        Refund.status.in_(
                            [
                                RefundStatus.PENDING,
                                RefundStatus.APPROVED,
                                RefundStatus.PROCESSED,
                            ]
                        ),
                    )
                )
                refundable = payment.amount - int(already_refunded or 0)
                if requested_amount is None:
                    amount = refundable
                else:
                    amount = min(int(requested_amount), refundable)
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

    # 4. Content publish gate (Strapi review-workflows): approving a
    #    publish request flips the draft page/post to published. The payload
    #    carries no content — the reviewer approves what is in the database,
    #    not what the requester claims is there.
    elif resource in ("cms_page", "blog_post"):
        try:
            target_id_raw = request.resource_id or payload.get("page_id") or payload.get("post_id")
            if target_id_raw:
                target_id = uuid.UUID(str(target_id_raw))
                if resource == "cms_page":
                    from app.modules.content.domain.models import CmsPage, PageStatus

                    page = await db.get(CmsPage, target_id)
                    if page and page.status != PageStatus.PUBLISHED:
                        page.status = PageStatus.PUBLISHED
                        if page.published_at is None:
                            page.published_at = datetime.now(UTC)
                else:
                    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

                    post = await db.get(BlogPost, target_id)
                    if post and post.status != BlogPostStatus.PUBLISHED:
                        post.status = BlogPostStatus.PUBLISHED
                        if post.published_at is None:
                            post.published_at = datetime.now(UTC)
                await logger.ainfo(
                    "approval_side_effect_content_published",
                    resource=resource,
                    target_id=str(target_id),
                )
        except Exception as exc:
            await logger.aerror(
                "approval_side_effect_content_publish_error",
                error=str(exc),
                request_id=str(request.id),
            )

    else:
        await logger.ainfo(
            "approval_side_effect_unhandled_or_generic",
            resource=resource,
            request_id=str(request.id),
        )

    # Decoupled event propagation: always emit ApprovalRequestCompleted via Transactional Outbox
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type="ApprovalRequestCompleted",
            aggregate_type="approval_request",
            aggregate_id=str(request.id),
            payload={
                "request_id": str(request.id),
                "resource": resource,
                "resource_id": str(request.resource_id) if request.resource_id else None,
                "type": request.type,
                "status": "APPROVED",
                "actor_id": str(actor_id),
            },
        )
    except Exception as exc:
        await logger.awarning("approval_outbox_publish_failed", error=str(exc))


class ApprovalService:
    """Approval workflow service providing core domain actions."""

    @staticmethod
    async def create_request(
        db: AsyncSession,
        requester_id: uuid.UUID,
        type: str,  # noqa: A002  # API parameter name is the public contract
        resource: str,
        resource_id: uuid.UUID | None = None,
        level: ApprovalLevel | str = ApprovalLevel.LOW,
        data: dict[str, Any] | None = None,
        reason: str | None = None,
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
        await db.flush()

        # Freeze the signature chain the policy demands for this request. No
        # matching policy means no steps — the single-reviewer path.
        from app.modules.approvals.application import policy_service

        await policy_service.materialise_steps(db, approval_request)

        await db.commit()

        # Reload with relationships
        return await ApprovalService.get_request(db, approval_request.id)  # type: ignore[return-value]

    @staticmethod
    async def list_requests(
        db: AsyncSession,
        status: ApprovalStatus | str | None = None,
        level: ApprovalLevel | str | None = None,
        resource: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ApprovalRequest], int]:
        """List approval requests matching optional filters with pagination."""
        stmt = select(ApprovalRequest).options(
            selectinload(ApprovalRequest.requester),
            selectinload(ApprovalRequest.actions).selectinload(ApprovalAction.actor),
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
    ) -> ApprovalRequest | None:
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
        comment: str | None = None,
    ) -> ApprovalRequest:
        """Review (approve or reject) a pending approval request."""
        request = await ApprovalService.get_request(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found",
            )

        # A multi-step chain is reviewable while PENDING (first signature) or
        # IN_REVIEW (further signatures). A single-step request is only ever
        # PENDING until the one review that closes it.
        reviewable = (ApprovalStatus.PENDING, ApprovalStatus.IN_REVIEW)
        if request.status not in reviewable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval request already has status '{request.status.value}'",
            )

        # Separation of duties: the requester can never review their own request.
        if request.requester_id == actor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A user cannot review their own approval request",
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

        if action_enum == ApprovalActionType.REJECT:
            request.status = ApprovalStatus.REJECTED
            # Rejecting any step ends the whole chain: the outstanding steps
            # are moot, and leaving them PENDING would show reviewers work
            # that can never complete.
            for step in request.steps or []:
                if step.status == ApprovalStepStatus.PENDING:
                    step.status = ApprovalStepStatus.SKIPPED
                    step.comment = "با رد درخواست بسته شد"
                    step.acted_at = datetime.now(UTC)
            await db.commit()
            reloaded = await ApprovalService.get_request(db, request.id)
            return reloaded or request

        # ── Approve ──────────────────────────────────────────────────────
        steps = list(request.steps or [])
        if steps:
            current = next(
                (s for s in steps if s.status == ApprovalStepStatus.PENDING), None
            )
            if current is None:  # pragma: no cover - guarded by status check
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Approval chain has no pending step",
                )
            if current.required_role and not await _actor_has_role(
                db, actor_id=actor_id, role_slug=current.required_role
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "این مرحله نیازمند نقش «"
                        f"{current.required_role}» است"
                    ),
                )
            current.status = ApprovalStepStatus.APPROVED
            current.acted_by_id = actor_id
            current.acted_at = datetime.now(UTC)
            current.comment = comment

            remaining = [s for s in steps if s.status == ApprovalStepStatus.PENDING]
            if remaining:
                # More signatures needed — the request stays open.
                request.status = ApprovalStatus.IN_REVIEW
                await db.commit()
                reloaded = await ApprovalService.get_request(db, request.id)
                return reloaded or request
            # Chain complete — fall through to execution.
            request.status = ApprovalStatus.APPROVED
            await _execute_side_effects(db, request, actor_id)
        else:
            # Legacy single-step path: one review closes the request.
            request.status = ApprovalStatus.APPROVED
            await _execute_side_effects(db, request, actor_id)

        await db.commit()

        # Reload with updated relations
        reloaded = await ApprovalService.get_request(db, request.id)
        return reloaded or request


# Module-level aliases for direct functional imports
create_request = ApprovalService.create_request
list_requests = ApprovalService.list_requests
get_request = ApprovalService.get_request
review_request = ApprovalService.review_request
