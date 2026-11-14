"""Database integration tests for Visual Page Builder Core (Phase P0).

Tests full round-trip persistence against real PostgreSQL:
1. create_page with builder_data compiles body_html and records initial revision
2. update_page updates AST and recompiles body_html
3. restore_revision brings builder_data back intact
4. reject_invalid_ast prevents saving corrupted data
5. page_templates CRUD persists and queries templates
6. revision_pruning bounds revision growth to 20
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select, func

from app.core.database.session import async_session_factory
from app.core.exceptions.handlers import ValidationError
from app.modules.content.application import cms_page_service
from app.modules.content.domain.models import CmsPage, CmsPageRevision, PageStatus, PageTemplate
from app.modules.content.schemas.content import (
    CmsPageCreateRequest,
    CmsPageUpdateRequest,
    PageTemplateCreateRequest,
)


@pytest.fixture(autouse=True)
async def _dispose_pool_after_test():
    yield
    from app.core.database.session import engine

    await engine.dispose()


def _make_sample_ast_dict(title: str, text: str) -> dict:
    return {
        "schemaVersion": 1,
        "title": title,
        "slug": f"slug-{uuid.uuid4().hex[:8]}",
        "global_styles": {},
        "rootElements": [
            {
                "id": "el_sec01",
                "name": "کانتینر اصلی",
                "type": "container",
                "layout": {"kind": "flex", "direction": "column"},
                "children": [
                    {
                        "id": "el_hd01",
                        "name": "سرتیتر",
                        "type": "widget",
                        "widgetType": "heading",
                        "widgetProps": {"text": text, "tag": "h2"},
                        "children": [],
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_create_page_with_builder_data_compiles_html_and_revision():
    slug = f"test-p0-{uuid.uuid4().hex[:8]}"
    ast_dict = _make_sample_ast_dict("صفحه نمونه", "متن هدر تستی")
    ast_dict["slug"] = slug

    async with async_session_factory() as session:
        page_resp = await cms_page_service.create_page(
            session,
            CmsPageCreateRequest(
                title="تست پی صفر",
                slug=slug,
                status=PageStatus.DRAFT,
                builder_data=ast_dict,
            ),
        )
        await session.commit()

        assert page_resp.id is not None
        assert page_resp.builder_data is not None
        assert page_resp.builder_data["title"] == "صفحه نمونه"
        # Verify compiled body_html
        assert '<div class="builder-document" dir="rtl">' in page_resp.body_html
        assert "متن هدر تستی" in page_resp.body_html

        # Verify revision snapshot in database
        stmt = select(CmsPageRevision).where(CmsPageRevision.page_id == page_resp.id)
        revisions = (await session.execute(stmt)).scalars().all()
        assert len(revisions) == 1
        assert revisions[0].revision_number == 1
        assert revisions[0].builder_data is not None
        assert revisions[0].builder_data["title"] == "صفحه نمونه"


@pytest.mark.asyncio
async def test_update_page_with_builder_data_creates_new_revision():
    slug = f"test-update-{uuid.uuid4().hex[:8]}"
    initial_ast = _make_sample_ast_dict("نسخه یک", "سرتیتر نسخه ۱")
    initial_ast["slug"] = slug

    async with async_session_factory() as session:
        page = await cms_page_service.create_page(
            session,
            CmsPageCreateRequest(
                title="تست به‌روزرسانی",
                slug=slug,
                status=PageStatus.DRAFT,
                builder_data=initial_ast,
            ),
        )
        await session.commit()

        # Now update with version 2
        updated_ast = _make_sample_ast_dict("نسخه دو", "سرتیتر نسخه ۲")
        updated_ast["slug"] = slug

        updated_page = await cms_page_service.update_page(
            session,
            page.id,
            CmsPageUpdateRequest(
                builder_data=updated_ast,
            ),
        )
        await session.commit()

        assert updated_page.revision_number == 2
        assert "سرتیتر نسخه ۲" in updated_page.body_html

        # Check that both revisions exist
        revisions = await cms_page_service.list_revisions(session, page.id)
        assert len(revisions) == 2
        assert revisions[0].revision_number == 2
        assert revisions[1].revision_number == 1


@pytest.mark.asyncio
async def test_restore_revision_restores_builder_data():
    slug = f"test-restore-{uuid.uuid4().hex[:8]}"
    ast_v1 = _make_sample_ast_dict("برگه قدیمی", "محتوای نسخه اول")
    ast_v1["slug"] = slug

    async with async_session_factory() as session:
        page = await cms_page_service.create_page(
            session,
            CmsPageCreateRequest(
                title="تست بازیابی",
                slug=slug,
                status=PageStatus.DRAFT,
                builder_data=ast_v1,
            ),
        )
        await session.commit()

        # Update to v2
        ast_v2 = _make_sample_ast_dict("برگه جدید", "محتوای نسخه دوم")
        ast_v2["slug"] = slug
        await cms_page_service.update_page(
            session,
            page.id,
            CmsPageUpdateRequest(builder_data=ast_v2),
        )
        await session.commit()

        # Restore v1
        restored = await cms_page_service.restore_revision(
            session,
            page.id,
            revision_number=1,
        )
        await session.commit()

        assert restored.revision_number == 3  # Rollback is recorded as new revision
        assert restored.builder_data["title"] == "برگه قدیمی"
        assert "محتوای نسخه اول" in restored.body_html


@pytest.mark.asyncio
async def test_reject_corrupted_ast_on_save():
    slug = f"test-corrupt-{uuid.uuid4().hex[:8]}"
    corrupted_ast = {
        "schemaVersion": 1,
        "title": "خراب",
        "slug": slug,
        "rootElements": [
            {
                "id": "el_dup01",
                "name": "یک",
                "type": "widget",
                "widgetType": "heading",
            },
            {
                "id": "el_dup01",  # duplicate ID
                "name": "دو",
                "type": "widget",
                "widgetType": "button",
            },
        ],
    }

    async with async_session_factory() as session:
        with pytest.raises(ValidationError):
            await cms_page_service.create_page(
                session,
                CmsPageCreateRequest(
                    title="تست خرابی",
                    slug=slug,
                    status=PageStatus.DRAFT,
                    builder_data=corrupted_ast,
                ),
            )


@pytest.mark.asyncio
async def test_page_template_crud():
    sample_ast = _make_sample_ast_dict("قالب هدر", "عنوان قالب")
    slug = f"tpl-{uuid.uuid4().hex[:8]}"

    async with async_session_factory() as session:
        # Create template
        tpl = await cms_page_service.create_template(
            session,
            PageTemplateCreateRequest(
                title="قالب تستی ۱",
                slug=slug,
                template_type="section",
                builder_data=sample_ast,
            ),
        )
        await session.commit()

        assert tpl.id is not None
        assert tpl.template_type == "section"

        # List templates
        templates = await cms_page_service.list_templates(session, template_type="section")
        assert any(t.id == tpl.id for t in templates)

        # Get template
        fetched = await cms_page_service.get_template(session, tpl.id)
        assert fetched.title == "قالب تستی ۱"

        # Delete template
        await cms_page_service.delete_template(session, tpl.id)
        await session.commit()

        with pytest.raises(Exception):
            await cms_page_service.get_template(session, tpl.id)


@pytest.mark.asyncio
async def test_revision_pruning_bounds_at_twenty():
    slug = f"test-prune-{uuid.uuid4().hex[:8]}"
    initial_ast = _make_sample_ast_dict("برگه با ریویژن زیاد", "نسخه ۰")
    initial_ast["slug"] = slug

    async with async_session_factory() as session:
        page = await cms_page_service.create_page(
            session,
            CmsPageCreateRequest(
                title="تست پرانینگ",
                slug=slug,
                status=PageStatus.DRAFT,
                builder_data=initial_ast,
            ),
        )
        await session.commit()

        # Update 23 times (total 24 revisions created)
        for i in range(1, 24):
            new_ast = _make_sample_ast_dict("برگه با ریویژن زیاد", f"نسخه {i}")
            new_ast["slug"] = slug
            await cms_page_service.update_page(
                session,
                page.id,
                CmsPageUpdateRequest(builder_data=new_ast),
            )
            await session.commit()

        # Check count of revisions in database
        stmt = (
            select(func.count(CmsPageRevision.id))
            .where(CmsPageRevision.page_id == page.id)
        )
        total_revisions = (await session.execute(stmt)).scalar_one()
        # Must be bounded at exactly 20
        assert total_revisions == 20

