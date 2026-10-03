"""Tests for the configurable upload ceiling.

The ceiling was a module constant, so raising the video limit needed a code
change and a redeploy. It is now a site option with the constants as fallback.

The fallback is the load-bearing part: the options table is unavailable during
a first-boot upload and whenever the site-options read fails, and a limit that
cannot be read must degrade to the default rather than reject every file.
"""

from __future__ import annotations

import pytest

import app.modules.media.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.media.application.media_service import (
    ABSOLUTE_MAX_FILE_SIZE_MB,
    MAX_FILE_SIZE_BYTES,
    MAX_MEDIA_FILE_SIZE_BYTES,
    _clamp_mb,
    category_for,
    max_size_for,
)


# ------------------------------------------------------- the default path


def test_default_image_ceiling():
    assert max_size_for("image/jpeg") == MAX_FILE_SIZE_BYTES


def test_default_video_ceiling():
    assert max_size_for("video/mp4") == MAX_MEDIA_FILE_SIZE_BYTES


def test_pdf_uses_the_image_ceiling():
    # A product manual is not a video; giving it 100 MB would let a shopper
    # upload a 90 MB "PDF" that is a video in disguise.
    assert max_size_for("application/pdf") == MAX_FILE_SIZE_BYTES


def test_unknown_mime_uses_the_image_ceiling():
    assert max_size_for("application/octet-stream") == MAX_FILE_SIZE_BYTES


# --------------------------------------------------------------- clamping


def test_zero_falls_back():
    assert _clamp_mb(0, 10) == 10


def test_negative_falls_back():
    assert _clamp_mb(-5, 10) == 10


def test_oversized_value_is_capped():
    # A typo of "204800" must not become a 200 GB allowance.
    assert _clamp_mb(204800, 10) == ABSOLUTE_MAX_FILE_SIZE_MB


def test_sane_value_passes_through():
    assert _clamp_mb(250, 10) == 250


# -------------------------------------------------------------- categories


def test_categories_split_correctly():
    assert category_for("image/png") == "image"
    assert category_for("audio/mpeg") == "audio"
    assert category_for("video/webm") == "video"
    assert category_for("application/pdf") == "document"
    assert category_for("application/zip") == "unknown"


# ----------------------------------------------- the fallback must not throw


class _ExplodingDb:
    async def execute(self, *a, **k):
        raise RuntimeError("the options table is not reachable")


@pytest.mark.asyncio
async def test_an_unreadable_option_falls_back_to_the_default(monkeypatch):
    from app.modules.media.application import media_service as ms

    class _Opts:
        @staticmethod
        async def get_int(db, key, default, minimum=None, maximum=None):
            return default

    monkeypatch.setattr(
        "app.modules.settings.application.site_options_service.SiteOptionsService",
        _Opts,
    )
    image_mb, media_mb = await ms.max_size_for_mb(_ExplodingDb())
    assert image_mb == MAX_FILE_SIZE_BYTES // (1024 * 1024)
    assert media_mb == MAX_MEDIA_FILE_SIZE_BYTES // (1024 * 1024)


@pytest.mark.asyncio
async def test_resolve_applies_the_caller_cap(monkeypatch):
    from app.modules.media.application import media_service as ms

    class _Opts:
        @staticmethod
        async def get_int(db, key, default, minimum=None, maximum=None):
            return default

    monkeypatch.setattr(
        "app.modules.settings.application.site_options_service.SiteOptionsService",
        _Opts,
    )
    wide = await ms.resolve_size_limit(_ExplodingDb(), "image/jpeg", None)
    tight = await ms.resolve_size_limit(_ExplodingDb(), "image/jpeg", 1024)
    assert wide == MAX_FILE_SIZE_BYTES
    assert tight == 1024, "a caller cap must tighten, never be ignored"


@pytest.mark.asyncio
async def test_a_caller_cannot_widen_the_limit(monkeypatch):
    from app.modules.media.application import media_service as ms

    class _Opts:
        @staticmethod
        async def get_int(db, key, default, minimum=None, maximum=None):
            return default

    monkeypatch.setattr(
        "app.modules.settings.application.site_options_service.SiteOptionsService",
        _Opts,
    )
    # A thumbnail route passing a huge cap must not raise the ceiling above the
    # configured one, or it would defeat the setting entirely.
    got = await ms.resolve_size_limit(_ExplodingDb(), "image/jpeg", 10**12)
    assert got == MAX_FILE_SIZE_BYTES