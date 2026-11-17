"""Application service for handling Visual Page Builder form submissions (Phase P4)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.content.domain.models import FormSubmission
from app.modules.content.schemas.forms import FormSubmitRequest, FormSubmitResponse

logger = get_logger("form_submissions")


class FormSubmissionService:
    """Service handling public submissions and admin querying of form_container data."""

    @staticmethod
    async def submit_form(
        db: AsyncSession,
        payload: FormSubmitRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> FormSubmitResponse:
        """Process incoming form submission with honeypot anti-spam defense."""
        # 1. Honeypot check: If bot filled the hidden trap field, silently drop
        if payload.hp_website and payload.hp_website.strip():
            await logger.awarning(
                "form_submission_honeypot_triggered",
                form_id=payload.form_id,
                ip=ip_address,
                trap_value=payload.hp_website[:50],
            )
            # Return plausible success to prevent bot from adapting
            return FormSubmitResponse(
                success=True,
                message="پیام یا فرم شما با موفقیت ثبت شد.",
                submission_id=uuid.uuid4(),
            )

        # 2. Clean submitted data (strip honeypot or internal underscore fields)
        clean_data = {
            k: v
            for k, v in payload.data.items()
            if not k.startswith("_hp") and not k.startswith("__")
        }

        # 3. Persist submission to PostgreSQL
        submission = FormSubmission(
            form_id=payload.form_id.strip(),
            page_id=payload.page_id,
            page_slug=payload.page_slug.strip() if payload.page_slug else None,
            data=clean_data,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            is_read=False,
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)

        await logger.ainfo(
            "form_submission_saved",
            submission_id=str(submission.id),
            form_id=submission.form_id,
            page_slug=submission.page_slug,
        )

        return FormSubmitResponse(
            success=True,
            message="پیام یا فرم شما با موفقیت ثبت شد.",
            submission_id=submission.id,
        )

    @staticmethod
    async def list_submissions(
        db: AsyncSession,
        form_id: str | None = None,
        page_slug: str | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[FormSubmission], int]:
        """Query paginated submissions with optional filters."""
        query = select(FormSubmission)
        count_query = select(func.count()).select_from(FormSubmission)

        if form_id:
            query = query.where(FormSubmission.form_id == form_id.strip())
            count_query = count_query.where(FormSubmission.form_id == form_id.strip())
        if page_slug:
            query = query.where(FormSubmission.page_slug == page_slug.strip())
            count_query = count_query.where(FormSubmission.page_slug == page_slug.strip())
        if unread_only:
            query = query.where(FormSubmission.is_read.is_(False))
            count_query = count_query.where(FormSubmission.is_read.is_(False))

        total_res = await db.execute(count_query)
        total = total_res.scalar_one()

        offset = max(0, (page - 1) * page_size)
        query = query.order_by(FormSubmission.created_at.desc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        items = list(result.scalars().all())
        return items, total

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        submission_id: uuid.UUID,
        is_read: bool = True,
    ) -> FormSubmission | None:
        """Mark a single form submission as read/unread."""
        stmt = (
            update(FormSubmission)
            .where(FormSubmission.id == submission_id)
            .values(is_read=is_read)
            .returning(FormSubmission)
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.scalar_one_or_none()

    @staticmethod
    async def delete_submission(
        db: AsyncSession,
        submission_id: uuid.UUID,
    ) -> bool:
        """Delete a form submission permanently."""
        stmt = delete(FormSubmission).where(FormSubmission.id == submission_id)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0
