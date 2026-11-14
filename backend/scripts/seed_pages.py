"""CLI wrapper for the core default-pages seed — see
``app/modules/content/application/default_pages.py``.

The seeding itself runs automatically on every backend startup (lifespan);
this script exists for manual runs and for ``start_project.bat``'s visible
bootstrap step. Same idempotency contract: missing pages/FAQs are created,
operator-customized rows are never touched.

Usage: ``python scripts/seed_pages.py`` (from backend/)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database.session import async_session_factory
from app.modules.content.application.default_pages import seed_default_pages


async def seed_pages() -> int:
    async with async_session_factory() as db:
        stats = await seed_default_pages(db)
        await db.commit()
    print(
        "default pages seed done: "
        f"pages_created={stats['pages_created']} "
        f"faqs_created={stats['faqs_created']} "
        f"cache_cleared={stats['cache_cleared']}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(seed_pages()))
    except Exception as exc:  # noqa: BLE001 — the launcher prints and continues
        print(f"seed_pages failed: {exc}", file=sys.stderr)
        sys.exit(1)
