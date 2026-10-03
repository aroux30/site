"""Tests for the media edit chain (source_asset_id / edit_operation).

Non-destructive editing produced one asset row per crop/resize/rotate with no
link between them. These tests cover the two things that link makes possible:
walking the chain back to the original, and listing the steps.

The walk is tested against an in-memory chain rather than a database, because
the interesting failure is a cycle or a truncated chain — a shape a fixture
database makes hard to build and a plain dict list makes trivial.
"""

from __future__ import annotations

import uuid

import pytest

import app.modules.media.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.media.domain.models import MediaAsset


def _asset(source_id=None, operation=None, created=1):
    return MediaAsset(
        id=uuid.uuid4(),
        uploader_id=None,
        file_name="a.jpg",
        file_path="media/a.jpg",
        file_url="/uploads/media/a.jpg",
        file_size=1,
        mime_type="image/jpeg",
        source_asset_id=source_id,
        edit_operation=operation,
    )


# ------------------------------------------------------------- the columns


def test_lineage_columns_exist():
    assert hasattr(MediaAsset, "source_asset_id")
    assert hasattr(MediaAsset, "edit_operation")


def test_lineage_is_nullable():
    # An uploaded original has no parent. Making these NOT NULL would mean every
    # upload has to invent one.
    assert MediaAsset.__table__.c.source_asset_id.nullable is True
    assert MediaAsset.__table__.c.edit_operation.nullable is True


def test_lineage_is_indexed():
    # The history panel walks children of a root; without the index that is a
    # full scan of the library on every open.
    indexed = {c.name for c in MediaAsset.__table__.c if c.index}
    assert "source_asset_id" in indexed


# ------------------------------------------------------------- the walk


def _walk(chain: dict, start: uuid.UUID):
    """The loop restore_original runs, over a plain id -> parent map."""
    seen = {start}
    current = start
    while True:
        parent = chain.get(current)
        if parent is None:
            return current
        if parent in seen:
            raise AssertionError("cycle")
        seen.add(parent)
        current = parent


def test_a_standalone_asset_is_its_own_original():
    asset_id = uuid.uuid4()
    assert _walk({}, asset_id) == asset_id


def test_one_edit_resolves_to_the_original():
    root, child = uuid.uuid4(), uuid.uuid4()
    assert _walk({child: root}, child) == root


def test_a_chain_of_four_resolves_to_the_root():
    root = uuid.uuid4()
    chain, prev = {}, root
    for _ in range(3):
        nxt = uuid.uuid4()
        chain[nxt] = prev
        prev = nxt
    assert _walk(chain, prev) == root


def test_a_cycle_terminates_rather_than_hanging():
    a, b = uuid.uuid4(), uuid.uuid4()
    # A cycle cannot be written through the editor, but the walk must not hang
    # if one ever appears: a session-blocking request on a corrupt row.
    with pytest.raises(AssertionError):
        _walk({b: a, a: b}, b)


# ------------------------------------------- the chain link is actually written


def test_registering_a_derived_asset_writes_the_link():
    """The columns existing is not the feature.

    Found by the guard audit: every test here checked the model's shape, so
    deleting ``source_asset_id=source.id`` from ``register_derived_asset`` left
    the whole file green. Without that write the chain does not exist — the
    history endpoint returns the original's only and "restore the original"
    returns the asset the caller already had.
    """
    import inspect

    from app.modules.media.application import media_service

    src = inspect.getsource(media_service.MediaService.register_derived_asset)
    assert "source_asset_id=source.id" in src, (
        "a derived asset is registered with no parent, so the edit chain does "
        "not exist and neither the history nor restore-original can work"
    )
    assert "edit_operation=suffix" in src, (
        "without the operation name the history cannot read as a list of steps"
    )


def test_derived_assets_point_at_the_asset_that_was_edited():
    """Not at the original of the original.

    Editing a rotated image has to link to the rotation, not to the upload, or
    "undo one step" walks past the step the operator is looking at.
    """
    import inspect

    from app.modules.media.application import media_service

    src = inspect.getsource(media_service.MediaService.register_derived_asset)
    # The parent is whatever was passed in as source_asset_id, not re-derived.
    assert "source = await MediaService.get_asset(db, source_asset_id)" in src
