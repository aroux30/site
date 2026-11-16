"""Unit and integration tests for ThemeService and theme management API."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select, update

from app.core.database.session import async_session_factory
from app.modules.content.application import theme_service
from app.modules.content.domain.theme_models import SiteTheme, ThemeRevision
from app.modules.content.schemas.theme import SiteThemeCreateRequest, SiteThemeUpdateRequest


@pytest.fixture(autouse=True)
async def _dispose_pool_after_test():
    yield
    from app.core.database.session import engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_theme():
    unique_slug = f"test-theme-{uuid.uuid4().hex[:8]}"
    sample_tokens = {
        "primitive": {
            "color": {
                "emerald": {"500": {"$value": "#10b981", "$type": "color"}}
            }
        },
        "semantic": {
            "color": {
                "primary": {"$value": "#059669", "$type": "color"},
                "secondary": {"$value": "#0d9488", "$type": "color"}
            },
            "dimension": {
                "radius": {"$value": "12px", "$type": "dimension"}
            }
        },
        "component": {}
    }

    async with async_session_factory() as db:
        theme = await theme_service.create_theme(
            db,
            name="تم تست واحد",
            slug=unique_slug,
            description="توضیحات تم تست",
            tokens=sample_tokens,
            is_active=False,
        )

        assert theme.id is not None
        assert theme.slug == unique_slug
        assert theme.is_active is False
        assert theme.tokens["semantic"]["color"]["primary"]["$value"] == "#059669"

        # Check that revision 1 was created
        revs = (await db.execute(select(ThemeRevision).where(ThemeRevision.theme_id == theme.id))).scalars().all()
        assert len(revs) >= 1
        assert revs[0].version == 1

        # Query theme by slug
        fetched = await theme_service.get_theme_by_slug(db, unique_slug)
        assert fetched is not None
        assert fetched.id == theme.id


@pytest.mark.asyncio
async def test_activate_theme_single_active_constraint():
    slug1 = f"theme-act1-{uuid.uuid4().hex[:8]}"
    slug2 = f"theme-act2-{uuid.uuid4().hex[:8]}"
    tokens = {
        "semantic": {
            "color": {"primary": {"$value": "#10b981", "$type": "color"}}
        }
    }

    async with async_session_factory() as db:
        # Create two inactive themes
        t1 = await theme_service.create_theme(db, name="تم اول", slug=slug1, tokens=tokens, is_active=False)
        t2 = await theme_service.create_theme(db, name="تم دوم", slug=slug2, tokens=tokens, is_active=False)

        # Activate theme 1
        activated1 = await theme_service.activate_theme(db, t1.id)
        assert activated1.is_active is True

        # Activate theme 2 -> theme 1 must be atomically deactivated
        activated2 = await theme_service.activate_theme(db, t2.id)
        assert activated2.is_active is True

        # Verify theme 1 is now inactive
        refreshed_t1 = await theme_service.get_theme_by_id(db, t1.id)
        assert refreshed_t1.is_active is False

        # Verify active theme lookup returns theme 2
        active_theme = await theme_service.get_active_theme(db)
        assert active_theme is not None
        assert active_theme.id == t2.id
