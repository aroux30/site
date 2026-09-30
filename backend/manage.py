"""Backend management CLI (Django ``manage.py`` / Strapi CLI parity).

Usage: ``python manage.py <group> <command> [args]`` — dependency-free
(argparse), async services driven through ``asyncio.run``.

Groups:
  cms       — pages: list / publish / export / import
  webhooks  — list endpoints, show recent deliveries
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


async def _cms_export(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.content.application import transfer_service

    async with async_session_factory() as db:
        doc = await transfer_service.export_content(db)
    payload = json.dumps(doc, ensure_ascii=False, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"exported {len(doc.get('pages', []))} page(s) → {args.output}")
    else:
        print(payload)


async def _cms_import(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.content.application import transfer_service

    with open(args.file, encoding="utf-8") as fh:
        doc = json.load(fh)
    async with async_session_factory() as db:
        counts = await transfer_service.import_content(db, doc)
        await db.commit()
    _print_json(counts)


async def _cms_process_schedules(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.content.application import cms_page_service

    async with async_session_factory() as db:
        counts = await cms_page_service.process_scheduled_pages(db)
        await db.commit()
    _print_json(counts)


async def _webhooks_list(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.integrations.application import webhook_service

    async with async_session_factory() as db:
        endpoints = await webhook_service.list_endpoints(db)
        for ep in endpoints:
            state = "on " if ep.is_active else "off"
            print(f"[{state}] {ep.name:<20} {ep.url}  events={','.join(ep.events)}")
        print(f"— {len(endpoints)} endpoint(s)")


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


async def _webhooks_deliveries(args: argparse.Namespace) -> None:
    from app.core.database.session import async_session_factory
    from app.modules.integrations.application import webhook_service

    async with async_session_factory() as db:
        deliveries = await webhook_service.list_deliveries(db, limit=args.limit)
        for d in deliveries:
            print(f"{d.event:<18} {d.status.value:<8} attempts={d.attempts} http={d.response_status}")


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

    p = cms_sub.add_parser("export", help="Export all CMS content to JSON")
    p.add_argument("-o", "--output")
    p.set_defaults(func=_cms_export)

    p = cms_sub.add_parser("import", help="Import a CMS content JSON file")
    p.add_argument("file")
    p.set_defaults(func=_cms_import)

    p = cms_sub.add_parser("process-schedules", help="Fire due page publish/unpublish")
    p.set_defaults(func=_cms_process_schedules)

    rbac = sub.add_parser("rbac", help="RBAC role/permission operations")
    rbac_sub = rbac.add_subparsers(dest="command", required=True)
    p = rbac_sub.add_parser(
        "seed-permissions",
        help="Upsert the permission catalog and grant it to the admin role (idempotent)",
    )
    p.set_defaults(func=_rbac_seed_permissions)

    wh = sub.add_parser("webhooks", help="Webhook inspection")
    wh_sub = wh.add_subparsers(dest="command", required=True)
    p = wh_sub.add_parser("list", help="List endpoints")
    p.set_defaults(func=_webhooks_list)
    p = wh_sub.add_parser("deliveries", help="Recent deliveries")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=_webhooks_deliveries)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.func(args)) or 0


if __name__ == "__main__":
    sys.exit(main())
