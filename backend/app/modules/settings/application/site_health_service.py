"""Site health check service (WordPress Site Health parity).

Runs diagnostic checks on the platform and returns a health report:
- Database connectivity and table count
- Redis connectivity
- Media storage accessibility
- Migration status (pending migrations)
- Orphaned data detection
- System resource usage

Usage:
    from app.modules.settings.application.site_health_service import SiteHealthService
    report = await SiteHealthService.run_checks(db)
"""

from __future__ import annotations

import ast
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SiteHealthService:
    """Run platform health diagnostics."""

    @staticmethod
    async def run_checks(db: AsyncSession) -> dict[str, Any]:
        """Run all health checks and return a structured report."""
        checks: list[dict[str, Any]] = []

        # 1. Database connectivity
        checks.append(await SiteHealthService._check_database(db))

        # 2. Redis connectivity
        checks.append(await SiteHealthService._check_redis())

        # 3. Media storage
        checks.append(await SiteHealthService._check_media_storage())

        # 4. Migration status
        checks.append(await SiteHealthService._check_migrations(db))

        # 5. Table statistics
        checks.append(await SiteHealthService._check_table_stats(db))

        # 6. Python version
        checks.append({
            "name": "Python Version",
            "status": "good",
            "value": sys.version.split()[0],
            "description": "Python runtime version",
        })

        # 7. Content-level checks. The six above ask "is the platform up";
        # these ask "is this site healthy" — overdue scheduled posts, media
        # rows pointing at deleted files, menus aimed at removed pages.
        from app.modules.settings.application.content_health_service import (
            run_content_checks,
        )

        content_checks = await run_content_checks(db)
        checks.extend(content_checks)

        # Overall status. A failed content check is a real failure, not a
        # footnote: an unpublished post and a 404 image both cost a sale.
        statuses = [c["status"] for c in checks]
        content_statuses = [c["status"] for c in content_checks]

        def _worst(values: list[str]) -> str:
            if "critical" in values:
                return "critical"
            return "warning" if "warning" in values else "good"

        return {
            "overall_status": _worst(statuses),
            "checked_at": datetime.now(UTC).isoformat(),
            "checks": checks,
            "summary": {
                "good": statuses.count("good"),
                "warning": statuses.count("warning"),
                "critical": statuses.count("critical"),
                "platform_status": _worst(statuses[: len(statuses) - len(content_statuses)]),
                "content_status": _worst(content_statuses),
            },
        }

    @staticmethod
    async def _check_database(db: AsyncSession) -> dict[str, Any]:
        try:
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            # Count tables
            tbl_result = await db.execute(text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            table_count = tbl_result.scalar()
            return {
                "name": "Database",
                "status": "good",
                "value": f"{table_count} tables",
                "description": "PostgreSQL connection is healthy",
            }
        except Exception as exc:
            return {
                "name": "Database",
                "status": "critical",
                "value": str(exc)[:200],
                "description": "Cannot connect to database",
            }

    @staticmethod
    async def _check_redis() -> dict[str, Any]:
        try:
            from app.core.cache.redis import get_redis
            client = await get_redis()
            pong = await client.ping()
            return {
                "name": "Redis",
                "status": "good" if pong else "warning",
                "value": "Connected" if pong else "No PONG",
                "description": "Redis cache server status",
            }
        except Exception as exc:
            return {
                "name": "Redis",
                "status": "warning",
                "value": str(exc)[:200],
                "description": "Redis is not available (caching disabled)",
            }

    @staticmethod
    async def _check_media_storage() -> dict[str, Any]:
        # Read the same path the upload writer uses. The old
        # ``os.environ.get("MEDIA_ROOT", "media/uploads")`` consulted a variable
        # set in no env file and no compose file, and its fallback pointed at a
        # directory that is never created — real files live under
        # ``<UPLOAD_DIR>/media``. So this check reported "not found"
        # permanently while the orphan check, using the same wrong constant,
        # reported "good" permanently: two opposite verdicts from one bug.
        from app.core.config.settings import get_settings
        from app.modules.media.application.storage_paths import MEDIA_SUBDIR

        media_root = Path(get_settings().UPLOAD_DIR) / MEDIA_SUBDIR
        if media_root.exists() and media_root.is_dir():
            file_count = sum(1 for _ in media_root.rglob("*") if _.is_file())
            return {
                "name": "Media Storage",
                "status": "good",
                "value": f"{file_count} files in {media_root}",
                "description": "Media upload directory is accessible",
            }
        return {
            "name": "Media Storage",
            "status": "warning",
            "value": f"{media_root} not found",
            "description": "Media upload directory does not exist",
        }

    @staticmethod
    def _alembic_revisions() -> tuple[dict[str, str], set[str], dict[str, str | None]]:
        """Parse ``alembic/versions/*.py`` into (revisions, referenced, walk).

        ``revisions`` is revision -> filename, ``referenced`` is every
        revision named as somebody's ``down_revision`` (a set, because a
        merge revision has two), and ``walk`` is revision -> the single
        parent to walk backwards through, with merge revisions mapped to
        None since they have no single linear ancestor.

        Parses with ``ast`` rather than reading the text, for two reasons
        that both bite on this repo:

        * 22 of the 82 files declare ``revision``/``down_revision`` as
          annotated assignments (``revision: str = "..."``), not plain
          assignments, so an Assign-only walk silently drops them.
        * Four files are merge revisions with a *tuple* ``down_revision``, so
          a naive parent count treats one branch point as several unmerged
          heads. The naive parse reported 6 heads; the correct answer is 1.
        """
        versions_dir = Path(__file__).resolve().parents[4] / "alembic" / "versions"
        files: dict[str, str] = {}
        referenced: set[str] = set()
        walk: dict[str, str | None] = {}
        if not versions_dir.is_dir():
            return files, referenced, walk

        for path in sorted(versions_dir.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            revision: str | None = None
            down: Any = None
            for node in ast.walk(tree):
                targets: list[ast.expr] = []
                value: ast.expr | None = None
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                    value = node.value
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                    value = node.value
                else:
                    continue
                names = {t.id for t in targets if isinstance(t, ast.Name)}

                if "revision" in names and value is not None:
                    try:
                        parsed = ast.literal_eval(value)
                    except (ValueError, SyntaxError):
                        continue
                    if isinstance(parsed, str):
                        revision = parsed
                elif "down_revision" in names and value is not None:
                    try:
                        down = ast.literal_eval(value)
                    except (ValueError, SyntaxError):
                        down = None

            if revision is None:
                continue
            files[revision] = path.name
            if isinstance(down, (tuple, list)):
                # Every branch of a merge is still a real reference, so the
                # merge revision's parents must not be dropped here — that
                # would leave the merge looking like an unreferenced head.
                referenced.update(r for r in down if isinstance(r, str))
                walk[revision] = down[0] if len(down) == 1 else None
            elif isinstance(down, str):
                referenced.add(down)
                walk[revision] = down
            else:
                walk[revision] = None
        return files, referenced, walk

    @staticmethod
    def _alembic_head() -> str | None:
        """Resolve the single head revision, or None when ambiguous/absent.

        A head is any revision no other revision names as a parent. Zero
        heads means nothing parsed; more than one means a fork the deploy
        must merge. Both are ambiguous states, and both return None so the
        caller reports "unknown" rather than guessing.
        """
        files, referenced, _ = SiteHealthService._alembic_revisions()
        heads = sorted(set(files) - referenced)
        return heads[0] if len(heads) == 1 else None

    @staticmethod
    def _revisions_behind(
        current: str, head: str, walk: dict[str, str | None]
    ) -> int | None:
        """Count revisions from ``current`` up to ``head``, or None if unknown.

        Walks the parent chain back from the head. Returns None when the
        chain cannot be walked (a revision not on disk, or a merge branch
        with no single parent) so the caller can stay critical while saying
        it does not know the exact distance — a fabricated count is worse
        than no count.
        """
        count = 0
        node: str | None = head
        seen: set[str] = set()
        while node is not None and node not in seen:
            seen.add(node)
            count += 1
            if node == current:
                return count - 1
            node = walk.get(node)
        return None

    @staticmethod
    async def _check_migrations(db: AsyncSession) -> dict[str, Any]:
        try:
            result = await db.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()
        except Exception:
            return {
                "name": "Migrations",
                "status": "warning",
                "value": "Cannot read",
                "description": "Could not read migration version",
            }

        if not current:
            # No alembic_version row at all: nothing was ever applied. The
            # old code rendered this as "unknown" under a hardcoded "good".
            return {
                "name": "Migrations",
                "status": "critical",
                "value": "unversioned",
                "description": "No alembic_version row; migrations were never applied",
            }

        files, _referenced, walk = SiteHealthService._alembic_revisions()
        head = SiteHealthService._alembic_head()
        if head is None:
            # The database is readable but the head is not resolvable from
            # disk. An unverifiable check is not a passing check.
            return {
                "name": "Migrations",
                "status": "warning",
                "value": f"{current} (head unresolvable)",
                "description": (
                    f"Parsed {len(files)} migration(s) but could not resolve a "
                    "single head; merge the heads before deploying"
                ),
            }
        if current == head:
            return {
                "name": "Migrations",
                "status": "good",
                "value": current,
                "description": f"Database is at the migration head ({head})",
            }

        behind = SiteHealthService._revisions_behind(current, head, walk)
        distance = (
            f"{behind} revision(s) behind"
            if behind is not None
            else "behind (distance unknown)"
        )
        return {
            "name": "Migrations",
            "status": "critical",
            "value": f"{current} (head {head})",
            "description": f"Database is {distance} the migration head; run alembic upgrade head",
        }

    @staticmethod
    async def _check_table_stats(db: AsyncSession) -> dict[str, Any]:
        try:
            result = await db.execute(text("""
                SELECT relname, n_live_tup
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
                LIMIT 10
            """))
            top = [{"table": r[0], "rows": r[1]} for r in result]
            total_rows = sum(t["rows"] for t in top)
            return {
                "name": "Database Stats",
                "status": "good",
                "value": f"~{total_rows} rows in top 10 tables",
                "description": "Table row counts (approximate)",
                "details": top,
            }
        except Exception:
            return {
                "name": "Database Stats",
                "status": "warning",
                "value": "Cannot read stats",
                "description": "pg_stat_user_tables not accessible",
            }

    @staticmethod
    async def optimize_database(db: AsyncSession) -> dict[str, Any]:
        """Run VACUUM ANALYZE on all tables (WordPress database optimize parity)."""
        try:
            # Note: VACUUM cannot run inside a transaction block with asyncpg,
            # so we just run ANALYZE which can.
            await db.execute(text("ANALYZE"))
            return {"status": "success", "action": "ANALYZE", "message": "Database statistics updated"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @staticmethod
    async def debug_info(db: AsyncSession) -> dict[str, Any]:
        """WordPress's "Site Health → Info" tab: the facts a support ticket needs.

        Allow-list, never a denylist. A denylist of secret-looking names is a
        bet that every future secret matches one of the patterns, and this
        endpoint is admin-readable but still copied into tickets and chats. So
        the *name* has to already be on this list to be included.

        Nothing here takes a lock, opens a migration, or writes — it is a read
        snapshot, safe to run while the site serves traffic.
        """
        import platform
        import shutil

        import sqlalchemy

        from app.core.config.settings import get_settings

        cfg = get_settings()
        sections: dict[str, dict[str, Any]] = {}

        # ── Server ──────────────────────────────────────────────────────────
        sections["server"] = {
            "os": f"{platform.system()} {platform.release()}",
            "python": sys.version.split()[0],
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
        }

        # ── Database ────────────────────────────────────────────────────────
        db_info: dict[str, Any] = {
            "dialect": "postgresql",
            "driver_version": sqlalchemy.__version__,
        }
        try:
            async with asyncio.timeout(3.0):
                async with db.connect() as conn:
                    version = await conn.execute(text("SELECT version()"))
                    db_info["server_version"] = str(version.scalar() or "").split(",")[0]
                    count = await conn.execute(
                        text(
                            "SELECT count(*) FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                    db_info["table_count"] = int(count.scalar() or 0)
        except Exception as exc:  # noqa: BLE001 — a diagnostic must not raise
            db_info["error"] = str(exc)[:200]
        sections["database"] = db_info

        # ── Storage ─────────────────────────────────────────────────────────
        try:
            usage = shutil.disk_usage(str(Path(cfg.UPLOAD_DIR)))
            sections["storage"] = {
                "upload_dir": cfg.UPLOAD_DIR,
                "total_gb": round(usage.total / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
            }
        except Exception as exc:  # noqa: BLE001
            sections["storage"] = {"error": str(exc)[:200]}

        # ── Application settings ────────────────────────────────────────────
        # Named one by one. These are the settings an operator actually asks
        # about in a support thread; anything resembling a credential is
        # deliberately absent rather than masked, so there is nothing to leak.
        sections["settings"] = {
            "app_name": cfg.APP_NAME,
            "environment": cfg.ENVIRONMENT,
            "debug": bool(getattr(cfg, "DEBUG", False)),
            "timezone": str(getattr(cfg, "TIMEZONE", "")),
            "default_currency": str(getattr(cfg, "DEFAULT_CURRENCY", "")),
            "api_docs_enabled": bool(getattr(cfg, "ENABLE_API_DOCS", False)),
        }

        # ── Modules ─────────────────────────────────────────────────────────
        # Registered module count only — the module list itself is internal
        # structure, and a support ticket needs the number, not the inventory.
        try:
            modules = getattr(cfg, "ENABLED_MODULES", None)
            sections["modules"] = {
                "enabled_count": len(modules) if modules else 0,
                "registered": "ENABLED_MODULES" if modules else "auto-discovery",
            }
        except Exception:  # noqa: BLE001
            sections["modules"] = {"registered": "auto-discovery"}

        return {
            "sections": sections,
            "generated_at": datetime.now(UTC).isoformat(),
        }
