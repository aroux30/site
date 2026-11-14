"""Source-pin and contract tests for category hierarchy, parent relations, and circular reference safety."""

from __future__ import annotations

from pathlib import Path

SERVICE_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "catalog"
    / "application"
    / "catalog_service.py"
).read_text(encoding="utf-8")

SCHEMA_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "catalog"
    / "schemas"
    / "catalog.py"
).read_text(encoding="utf-8")

REPO_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "catalog"
    / "infrastructure"
    / "catalog_repository.py"
).read_text(encoding="utf-8")

FACETED_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "search"
    / "application"
    / "faceted_search_service.py"
).read_text(encoding="utf-8")


def test_category_response_has_parent_name_field() -> None:
    """CategoryResponse must declare parent_name so clients can display parent without N+1 requests."""
    assert "parent_name: str | None = None" in SCHEMA_SRC, (
        "CategoryResponse must have `parent_name: str | None = None`"
    )


def test_circular_parent_reference_check_uses_slug_hierarchy() -> None:
    """Circular parent check must split path by '/' and check slug, not raw UUID against slug path."""
    assert "curr_slug in parent.path.split(\"/\")" in SERVICE_SRC, (
        "Circular reference check must test if current slug is in parent.path.split('/')"
    )


def test_category_service_updates_children_paths_recursively() -> None:
    """When a category's path changes, its children's paths must also be updated."""
    assert "_update_children_paths" in SERVICE_SRC, (
        "CategoryService must implement `_update_children_paths` to preserve subtree hierarchy consistency"
    )


def test_category_service_list_populates_parent_names() -> None:
    """CategoryService.list must bulk-load parent_names to avoid N+1 queries."""
    assert "parent_names = dict(p_res.all())" in SERVICE_SRC
    assert "resp.parent_name = parent_names.get(c.parent_id)" in SERVICE_SRC


def test_product_repository_category_filtering_includes_descendants() -> None:
    """Filtering products by parent category must also include descendant subcategories."""
    assert "Category.path.like(func.concat(cat_path_subq, \"/%\"))" in REPO_SRC, (
        "ProductRepository must match descendant categories via path prefix matching"
    )


def test_faceted_search_post_filter_includes_category_ancestors() -> None:
    """Faceted search post_filter must match category_ancestors to return subcategories when parent is filtered."""
    assert '{"terms": {"category_ancestors": slugs}}' in FACETED_SRC, (
        "FacetedSearchService must match category_ancestors for hierarchical filtering"
    )
