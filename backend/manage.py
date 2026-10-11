"""Backend management CLI (Django ``manage.py`` / Strapi CLI parity).

Usage: ``python manage.py <group> <command> [args]`` — dependency-free
(argparse), async services driven through ``asyncio.run``.

Groups:
  cms       — pages: list / publish / process-schedules
  rbac      — seed permissions from the catalog into the admin role
  db        — alembic current / heads passthrough helpers
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


async def _cms_list(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.content.application import cms_page_service
    from app.modules.content.domain.models import PageStatus

    async with async_session_factory() as db:
        result = await cms_page_service.list_pages(
            db,
            status=PageStatus(args.status) if args.status else None,
            include_trashed=args.trashed,
        )
        for page in result.items:
            print(f"{page.slug:<30} {page.status.value:<10} rev={page.revision_number}  {page.title}")
        print(f"— {result.total} page(s)")


async def _cms_publish(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.content.application import cms_page_service
    from app.modules.content.domain.models import PageStatus
    from app.modules.content.schemas.content import CmsPageUpdateRequest

    async with async_session_factory() as db:
        page = await cms_page_service.get_page_by_slug(db, args.slug, only_published=False)
        updated = await cms_page_service.update_page(
            db, page.id, CmsPageUpdateRequest(status=PageStatus.PUBLISHED)
        )
        await db.commit()
        print(f"published: {updated.slug} (rev {updated.revision_number})")


async def _cms_process_schedules(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.content.application import cms_page_service

    async with async_session_factory() as db:
        counts = await cms_page_service.process_scheduled_pages(db)
        await db.commit()
    _print_json(counts)


async def _rbac_seed_permissions(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.rbac.application.permission_seed import seed_permissions

    async with async_session_factory() as db:
        stats = await seed_permissions(db)
        await db.commit()
    _print_json(
        {
            "permissions_created": stats.permissions_created,
            "permissions_skipped": len(stats.permissions_skipped),
            "permissions_granted_to_admin": stats.permissions_granted_to_admin,
            "admin_role_created": stats.admin_role_created,
            "total_catalog": stats.total_catalog,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manage.py", description=__doc__)
    sub = parser.add_subparsers(dest="group", required=True)

    cms = sub.add_parser("cms", help="CMS page operations")
    cms_sub = cms.add_subparsers(dest="command", required=True)

    p = cms_sub.add_parser("list", help="List pages")
    p.add_argument("--status", choices=["draft", "published", "archived"])
    p.add_argument("--trashed", action="store_true", help="include trashed pages")
    p.set_defaults(func=_cms_list)

    p = cms_sub.add_parser("publish", help="Publish a page by slug")
    p.add_argument("slug")
    p.set_defaults(func=_cms_publish)

    # `cms export` / `cms import` were removed on 2026-10-07 with the
    # «انتقال محتوا» admin page and its JSON document format. Content
    # import/export lives in the «ورود و خروج داده» admin screen
    # (dataexchange module), which covers CMS pages and FAQs as entities.

    p = cms_sub.add_parser("process-schedules", help="Fire due page publish/unpublish")
    p.set_defaults(func=_cms_process_schedules)

    rbac = sub.add_parser("rbac", help="RBAC role/permission operations")
    rbac_sub = rbac.add_subparsers(dest="command", required=True)
    p = rbac_sub.add_parser(
        "seed-permissions",
        help="Upsert the permission catalog and grant it to the admin role (idempotent)",
    )
    p.set_defaults(func=_rbac_seed_permissions)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.func(args)) or 0


if __name__ == "__main__":
    sys.exit(main())
