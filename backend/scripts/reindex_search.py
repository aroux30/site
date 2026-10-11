#!/usr/bin/env python
"""Command-line search reindexer for the Elasticsearch projections.

Gap item 8: the storefront search now spans products, blog posts, and CMS
pages, so the reindex tool needs to target each family (or all of them):

    # from backend/
    python scripts/reindex_search.py --index all        # products + blog + cms
    python scripts/reindex_search.py --index products   # product index only
    python scripts/reindex_search.py --index blog       # published blog posts
    python scripts/reindex_search.py --index cms        # published CMS pages

Exit code is 0 when every requested target indexed without errors, 1
otherwise (Elasticsearch unreachable counts as a failure for the CLI —
operators must see it — while in-app callers degrade gracefully).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import pkgutil
import sys
from pathlib import Path

# Allow running as a script from anywhere: put backend/ on sys.path so the
# ``app`` package resolves (mirrors alembic env.py's path bootstrap).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TARGETS = ("products", "blog", "cms")


def _import_every_model_module() -> None:
    """Import every ``<pkg>.domain.models`` so the SQLAlchemy registry is whole.

    Without this the first ORM query dies with "expression 'Payment.order_id'
    failed to locate a name": mapper configuration resolves relationship
    targets by class name across the *entire* registry, and a script that only
    imports the search services has not loaded the modules those names live
    in. The test suite already does exactly this (app/tests/conftest.py); the
    reindex CLI was the one entry point that did not, so it only ever worked
    by accident — when something else happened to import the missing module
    first.
    """
    import app.modules

    for module in pkgutil.walk_packages(app.modules.__path__, "app.modules."):
        name = module.name
        if name.endswith(".domain.models") or name.endswith(".domain.wp_parity_models"):
            importlib.import_module(name)


async def _run(targets: list[str]) -> int:
    _import_every_model_module()
    from app.core.database.session import async_session_factory
    from app.modules.search.application.content_search_service import (
        get_content_search_service,
    )
    from app.modules.search.application.search_service import get_search_service

    exit_code = 0
    async with async_session_factory() as db:
        if "products" in targets:
            result = await get_search_service().reindex_all(db)
            print(f"[products] {result.message}")  # noqa: T201
            exit_code |= 0 if result.success else 1

        content_service = get_content_search_service()
        if "blog" in targets:
            # force=True rebuilds the content indices with the current
            # Persian mapping before the bulk load, keeping mappings in
            # sync with the code across deploys.
            result = await content_service.reindex_blog(db, force=True)
            print(f"[blog] {result.message}")  # noqa: T201
            exit_code |= 0 if result.success else 1

        if "cms" in targets:
            result = await content_service.reindex_cms(db, force=True)
            print(f"[cms] {result.message}")  # noqa: T201
            exit_code |= 0 if result.success else 1

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild Elasticsearch search indices (products / blog / cms).",
    )
    parser.add_argument(
        "--index",
        choices=(*TARGETS, "all"),
        default="all",
        help="Which index family to rebuild (default: all).",
    )
    args = parser.parse_args()
    targets = list(TARGETS) if args.index == "all" else [args.index]
    try:
        return asyncio.run(_run(targets))
    except Exception as exc:
        print(f"reindex failed: {exc}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
