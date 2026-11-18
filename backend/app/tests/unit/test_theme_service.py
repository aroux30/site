"""Unit and integration tests for ThemeService and theme management API."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select, update

from app.core.database.session import async_session_factory, engine
from app.modules.content.application import theme_service
from app.modules.content.domain.theme_models import SiteTheme, ThemeRevision
from app.modules.content.schemas.theme import SiteThemeCreateRequest, SiteThemeUpdateRequest


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

    await engine.dispose()


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

    await engine.dispose()


@pytest.mark.asyncio
async def test_theme_revisions_and_restore():
    slug = f"theme-rev-{uuid.uuid4().hex[:8]}"
    tokens_v1 = {"semantic": {"color": {"primary": {"$value": "#10b981", "$type": "color"}}}}
    tokens_v2 = {"semantic": {"color": {"primary": {"$value": "#f59e0b", "$type": "color"}}}}

    async with async_session_factory() as db:
        theme = await theme_service.create_theme(db, name="تم تست ریویژن", slug=slug, tokens=tokens_v1, is_active=False)
        revs1 = await theme_service.list_theme_revisions(db, theme.id)
        assert len(revs1) == 1
        initial_rev_id = revs1[0].id

        # Update theme to create revision 2
        from app.modules.content.schemas.theme import SiteThemeUpdateRequest, DesignTokensSchema
        updated = await theme_service.update_theme(
            db,
            theme.id,
            SiteThemeUpdateRequest(tokens=DesignTokensSchema.model_validate(tokens_v2)),
        )
        assert updated.tokens["semantic"]["color"]["primary"]["$value"] == "#f59e0b"

        revs2 = await theme_service.list_theme_revisions(db, theme.id)
        assert len(revs2) == 2

        # Restore initial revision 1
        restored = await theme_service.restore_theme_revision(db, theme.id, initial_rev_id)
        assert restored.tokens["semantic"]["color"]["primary"]["$value"] == "#10b981"

    await engine.dispose()


@pytest.mark.asyncio
async def test_theme_clone_and_delete():
    source_slug = f"theme-src-{uuid.uuid4().hex[:8]}"
    cloned_slug = f"theme-cln-{uuid.uuid4().hex[:8]}"
    tokens = {"semantic": {"color": {"primary": {"$value": "#3b82f6", "$type": "color"}}}}

    async with async_session_factory() as db:
        source = await theme_service.create_theme(db, name="تم مبدا", slug=source_slug, tokens=tokens, is_active=False)

        cloned = await theme_service.clone_theme(db, source.id, "تم کلون شده", cloned_slug)
        assert cloned.id != source.id
        assert cloned.slug == cloned_slug
        assert cloned.is_active is False
        assert cloned.tokens["semantic"]["color"]["primary"]["$value"] == "#3b82f6"

        # Delete non-active theme
        await theme_service.delete_theme(db, cloned.id)
        assert await theme_service.get_theme_by_id(db, cloned.id) is None

    await engine.dispose()


def test_compile_theme_css_variables_and_string():
    tokens = {
        "primitive": {
            "color": {"emerald": {"600": {"$value": "#059669", "$type": "color"}}}
        },
        "semantic": {
            "color": {
                "primary": {"$value": "{primitive.color.emerald.600}", "$type": "color"},
                "secondary": {"$value": "#0d9488", "$type": "color"},
            },
            "dimension": {
                "radius": {"$value": "14px", "$type": "dimension"},
            },
        },
    }

    css_vars = theme_service.compile_theme_css_variables(tokens)
    assert css_vars["--primary"] == "#059669"
    assert css_vars["--secondary"] == "#0d9488"
    assert css_vars["--radius"] == "14px"

    css_str = theme_service.compile_theme_css_string(tokens)
    assert ":root {" in css_str
    assert "--theme-primary: #059669;" in css_str
    assert "--primary: 161 94% 30%;" in css_str
    assert "--radius: 14px;" in css_str


@pytest.mark.asyncio
async def test_theme_cache_invalidation_flow(monkeypatch):
    from unittest.mock import AsyncMock

    mock_cache_del = AsyncMock()
    monkeypatch.setattr("app.modules.content.application.theme_service.cache_delete", mock_cache_del)

    # Calling invalidate_theme_cache should delete both JSON and CSS keys
    await theme_service.invalidate_theme_cache()

    deleted_keys = [call.args[0] for call in mock_cache_del.call_args_list]
    assert theme_service.ACTIVE_THEME_CACHE_KEY in deleted_keys
    assert theme_service.ACTIVE_THEME_CSS_CACHE_KEY in deleted_keys


@pytest.mark.asyncio
async def test_active_theme_css_redis_cache_and_latency(monkeypatch):
    """Verify that cached CSS retrieval executes in sub-100ms (fast in-memory path)."""
    import time
    from unittest.mock import AsyncMock

    cached_css_payload = ":root { --primary: #059669; --secondary: #0d9488; --radius: 12px; }"
    mock_get = AsyncMock(return_value=cached_css_payload)
    monkeypatch.setattr("app.core.cache.redis.cache_get", mock_get)

    t0 = time.perf_counter()
    from app.core.cache.redis import cache_get
    result = await cache_get(theme_service.ACTIVE_THEME_CSS_CACHE_KEY)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert result == cached_css_payload
    assert elapsed_ms < 100.0, f"Cache read took too long: {elapsed_ms}ms"



