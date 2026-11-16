"""Unit tests for themetok1 Alembic migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest


def test_theme1_migration_metadata():
    migration_file = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "2026_11_16_theme1_add_site_themes_and_page_template_category.py"
    assert migration_file.exists(), f"Migration file not found at {migration_file}"

    spec = importlib.util.spec_from_file_location("theme1_migration", migration_file)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "theme1"
    assert mod.down_revision == "pagebld1"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)
