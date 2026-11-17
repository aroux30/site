"""Unit tests for Visual Page Builder Form Builder submissions and honeypot protection (Phase P4)."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory, engine
from app.modules.content.application.form_submission_service import FormSubmissionService
from app.modules.content.domain.models import FormSubmission
from app.modules.content.schemas.forms import FormSubmitRequest


@pytest.mark.asyncio
async def test_form_submission_persists_clean_data():
    async with async_session_factory() as db_session:
        req = FormSubmitRequest(
            form_id="contact_form_01",
            page_slug="contact-us",
            data={
                "full_name": "سارا محمدی",
                "email": "sara@example.com",
                "message": "درخواست همکاری فروش",
                "accept_terms": True,
            },
        )

        resp = await FormSubmissionService.submit_form(
            db_session,
            req,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )

        assert resp.success is True
        assert resp.submission_id is not None

        # Query back from DB
        items, total = await FormSubmissionService.list_submissions(
            db_session, form_id="contact_form_01"
        )
        assert total >= 1
        saved = next(s for s in items if s.id == resp.submission_id)
        assert saved.form_id == "contact_form_01"
        assert saved.page_slug == "contact-us"
        assert saved.data["full_name"] == "سارا محمدی"
        assert saved.data["email"] == "sara@example.com"
        assert saved.data["accept_terms"] is True
        assert saved.ip_address == "192.168.1.100"
        assert saved.is_read is False

    await engine.dispose()


@pytest.mark.asyncio
async def test_form_submission_honeypot_drops_spam_silently():
    async with async_session_factory() as db_session:
        spam_req = FormSubmitRequest(
            form_id="lead_form_02",
            page_slug="landing",
            data={"name": "SpamBot", "email": "spam@bot.com"},
            _hp_website="http://spam-link.ru",  # Bot filled honeypot!
        )

        resp = await FormSubmissionService.submit_form(
            db_session,
            spam_req,
            ip_address="10.0.0.1",
            user_agent="SpamCrawler 1.0",
        )

        # Returns success to deceive bot
        assert resp.success is True

        # But MUST NOT be in DB!
        items, total = await FormSubmissionService.list_submissions(
            db_session, form_id="lead_form_02"
        )
        assert total == 0
        assert not any(s.id == resp.submission_id for s in items)

    await engine.dispose()


@pytest.mark.asyncio
async def test_form_submission_mark_as_read_and_delete():
    async with async_session_factory() as db_session:
        req = FormSubmitRequest(
            form_id="feedback_01",
            data={"score": 5, "comment": "عالی"},
        )
        resp = await FormSubmissionService.submit_form(db_session, req)
        sub_id = resp.submission_id
        assert sub_id is not None

        # Mark as read
        updated = await FormSubmissionService.mark_as_read(db_session, sub_id, is_read=True)
        assert updated is not None
        assert updated.is_read is True

        # Delete
        deleted = await FormSubmissionService.delete_submission(db_session, sub_id)
        assert deleted is True

        # Verify gone
        items, total = await FormSubmissionService.list_submissions(db_session, form_id="feedback_01")
        assert not any(s.id == sub_id for s in items)

    await engine.dispose()
