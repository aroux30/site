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
    async def record_run(
        db: AsyncSession,
        *,
        trigger: str = "scheduled",
    ) -> dict[str, Any]:
        """Run the checks, store the result, and return it.

        The stored copy is what makes a problem that was fixed between two
        visits still visible; without it the screen only ever answers "is it
        broken right now", which is the same answer the live endpoint gives.

        A run that could not be recorded is not a failed run: the checks
        already produced their report and the caller needs it either way, so
        the storage error is logged and the report returned. Losing history
        must never turn into losing the diagnosis.
        """
        from datetime import UTC, datetime

        from app.modules.settings.domain.models import SiteHealthRun

        started = datetime.now(UTC)
        try:
            report = await SiteHealthService.run_checks(db)
        except Exception as exc:  # noqa: BLE001 — the point is to record it
            report = {"checks": [], "error": str(exc)[:500]}

        worst = _worst_status(report.get("checks") or [])
        # Taken once, and used for both the row and the returned report. Two
        # `datetime.now()` calls would make the stored duration and the reported
        # one differ by the time the dict was built — small, and exactly the kind
        # of difference that makes two numbers from the same run disagree.
        finished = datetime.now(UTC)
        row = SiteHealthRun(
            started_at=started,
            finished_at=finished,
            trigger=trigger,
            report=report,
            worst_status=worst,
            error=(report.get("error") or None),
        )
        db.add(row)
        try:
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("site_health_run_not_recorded", error=str(exc))
            await db.rollback()
        else:
            logger.info(
                "site_health_run_recorded",
                trigger=trigger,
                worst=worst,
            )
        report["run_id"] = str(row.id) if row.id else None
        report["trigger"] = trigger
        report["started_at"] = started.isoformat()
        report["worst_status"] = worst
        # On the returned report as well as the stored row: the admin screen
        # shows the run it just triggered without re-reading the history, and a
        # duration it cannot show for the run in front of the operator is the
        # one they will ask about.
        report["duration_ms"] = int((finished - started).total_seconds() * 1000)
        return report

    @staticmethod
    async def list_runs(db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
        """Recent runs, newest first, for the history list."""
        from sqlalchemy import select

        from app.modules.settings.domain.models import SiteHealthRun

        stmt = (
            select(SiteHealthRun)
            .order_by(SiteHealthRun.started_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        rows = (await db.execute(stmt)).scalars().all()
        history: list[dict[str, Any]] = []
        for r in rows:
            checks = (r.report or {}).get("checks") or []
            # The two questions a support thread actually opens with are "what
            # broke last night?" and "is it still broken?". Both are answerable
            # from the row, and neither was on it:
            #
            # * duration — a run that took 40s and one that took 400ms look
            #   identical in the history otherwise, so a slow check that passes
            #   reads exactly like a healthy one. It is computed here from the
            #   two timestamps already stored rather than added as a column: the
            #   same value, and no migration for it.
            # * the failing checks — `error` covers a run that raised, which is
            #   the rare case. The common one is a run that completed with two
            #   checks in warning, and those names were in the report on the
            #   row and nowhere in the list, so the operator had to expand every
            #   entry to find out which check was unhappy.
            duration_ms = None
            if r.started_at and r.finished_at:
                try:
                    duration_ms = int(
                        (r.finished_at - r.started_at).total_seconds() * 1000
                    )
                except TypeError:
                    # A naive and an aware timestamp cannot be subtracted; the
                    # row is still worth listing, just without a duration.
                    duration_ms = None
            history.append(
                {
                    "id": str(r.id),
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": (
                        r.finished_at.isoformat() if r.finished_at else None
                    ),
                    "duration_ms": duration_ms,
                    "trigger": r.trigger,
                    "worst_status": r.worst_status,
                    "error": r.error,
                    # Names and statuses only. The full report is on the row and
                    # reachable by id; the list does not need it, and shipping
                    # every check's description on every row is a page of JSON
                    # nobody reads.
                    "checks": [
                        {"name": c.get("name"), "status": c.get("status")}
                        for c in checks
                    ],
                    "failing_checks": [
                        c.get("name")
                        for c in checks
                        if c.get("status") in ("warning", "critical")
                    ],
                }
            )
        return history

    @staticmethod
    async def get_run(db: AsyncSession, run_id: str) -> dict[str, Any] | None:
        """One run with its full report, or None."""
        import uuid as _uuid

        from sqlalchemy import select

        from app.modules.settings.domain.models import SiteHealthRun

        try:
            parsed = _uuid.UUID(str(run_id))
        except (TypeError, ValueError):
            return None
        row = (
            await db.execute(select(SiteHealthRun).where(SiteHealthRun.id == parsed))
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "trigger": row.trigger,
            "worst_status": row.worst_status,
            "error": row.error,
            "report": row.report or {},
        }

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

        # 6. Email delivery configuration. The most common total-but-silent
        #    failure a store has: SMTP unset means no notification, no reset
        #    link and no order confirmation, with nothing red anywhere.
        checks.append(await SiteHealthService._check_email(db))

        # 7. Disk space on the uploads volume. A store that fills its disk
        #    stops accepting uploads and, worse, stops writing invoices — and
        #    the first symptom is a 500 on checkout. WordPress's Site Health
        #    reports this for the same reason.
        checks.append(SiteHealthService._check_disk_space())

        # 8. Loopback reachability. WordPress's Site Health tests this because
        #    a site that cannot reach its own origin breaks the things that
        #    fetch it: cron pings, webhook retries, social previews, and any
        #    server-side call through the public URL. It is checked here as a
        #    real request to the configured origin, with the failure reported
        #    as a warning rather than a crash — a health check that cannot run
        #    must say so, not take the report down with it.
        checks.append(await SiteHealthService._check_loopback())

        # 9. Debug mode. WordPress's Site Health warns when WP_DEBUG is on in
        #    a production site because it turns error detail into a leak. The
        #    same holds here: the API's error envelope is deliberately terse,
        #    and a debug flag that widens it is worth flagging the moment it is
        #    on where customers can reach it.
        checks.append(SiteHealthService._check_debug_mode())

        # 10. Database character encoding. WordPress checks utf8mb4 for the
        #     same reason we check UTF8: a database not set up for full Unicode
        #     silently mangles emoji and non-Latin scripts — and this store is
        #     Persian, so the failure would be visible on every product name.
        checks.append(await SiteHealthService._check_database_encoding(db))

        # 11. Autoloaded options size. WordPress's "autoloaded options" check:
        #     every autoloaded row is read on every request, so a bloated set
        #     is a per-request tax. The threshold is generous — this is a
        #     warning that something huge got stored, not a tuning target.
        checks.append(await SiteHealthService._check_autoloaded_options(db))

        # 12. Python version
        checks.append({
            "name": "Python Version",
            "status": "good",
            "value": sys.version.split()[0],
            "description": "Python runtime version",
        })

        # Content-level checks. The platform checks above ask "is the platform
        # up"; these ask "is this site healthy" — overdue scheduled posts, media
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

    #: WordPress warns past 800 KB of autoloaded options. Kept in bytes and
    #: applied to the sum of option_value lengths, which is what actually
    #: travels on every settings read.
    _AUTOLOAD_WARN_BYTES = 800 * 1024

    @staticmethod
    async def _check_autoloaded_options(db: AsyncSession) -> dict[str, Any]:
        """How much data is loaded on every request via autoloaded options.

        WordPress's check, for the same reason: an autoloaded option is read
        on every settings resolution, and a few large ones turn into a
        per-request cost nobody attributes to settings. Reported as a warning
        past a generous threshold — the point is to catch something huge that
        was stored, not to police a healthy install.
        """
        try:
            result = await db.execute(text(
                "SELECT COALESCE(SUM(LENGTH(option_value)), 0), COUNT(*) "
                "FROM site_options WHERE autoload = true"
            ))
            total_bytes, count = result.one()
            total_bytes = int(total_bytes or 0)
            count = int(count or 0)
            kb = round(total_bytes / 1024)
            status = (
                "warning"
                if total_bytes > SiteHealthService._AUTOLOAD_WARN_BYTES
                else "good"
            )
            return {
                "name": "Autoloaded Options",
                "status": status,
                "value": f"{count} options, {kb} KB",
                "description": (
                    "حجم گزینه‌های autoload بالاست؛ هر درخواست آن را می‌خواند. "
                    "گزینه‌های حجیم را از autoload خارج کنید."
                    if status == "warning"
                    else "Autoloaded settings are within a normal size"
                ),
            }
        except Exception as exc:  # noqa: BLE001 — a health check never raises
            return {
                "name": "Autoloaded Options",
                "status": "warning",
                "value": str(exc)[:200],
                "description": "Could not measure the autoloaded options",
            }

    @staticmethod
    async def _check_database_encoding(db: AsyncSession) -> dict[str, Any]:
        """Whether the database is set up for full Unicode.

        WordPress's utf8mb4 check, adapted: PostgreSQL's equivalent is the
        database's ``server_encoding``/``encoding`` being UTF8. A store whose
        database is not UTF8 corrupts every non-ASCII name — and this store is
        Persian, so that is not a corner case but the default content.
        """
        try:
            result = await db.execute(text("SHOW server_encoding"))
            encoding = str(result.scalar() or "").upper()
            if encoding == "UTF8":
                return {
                    "name": "Database Encoding",
                    "status": "good",
                    "value": encoding,
                    "description": "The database stores full Unicode",
                }
            return {
                "name": "Database Encoding",
                "status": "warning",
                "value": encoding or "unknown",
                "description": (
                    "کدگذاری دیتابیس UTF8 نیست؛ ممکن است نام‌ها و متن‌های فارسی "
                    "خراب شوند."
                ),
            }
        except Exception as exc:  # noqa: BLE001 — a health check never raises
            return {
                "name": "Database Encoding",
                "status": "warning",
                "value": str(exc)[:200],
                "description": "Could not read the database encoding",
            }

    @staticmethod
    def _check_debug_mode() -> dict[str, Any]:
        """Whether the app is running with debug on.

        Debug mode widens error responses and is never wanted on a site real
        customers reach — the danger is not the setting existing but it being
        left on after someone turned it on to diagnose a bug. Reported as a
        warning, not a critical: the store still works; it just says more than
        it should when something breaks.
        """
        from app.core.config.settings import get_settings

        try:
            settings_obj = get_settings()
            debug = bool(
                getattr(settings_obj, "DEBUG", False)
                or getattr(settings_obj, "ENVIRONMENT", "") == "development"
            )
            return {
                "name": "Debug Mode",
                "status": "warning" if debug else "good",
                "value": "on" if debug else "off",
                "description": (
                    "حالت دیباگ روشن است؛ جزئیات خطا ممکن است به کاربر نشان "
                    "داده شود. در محیط تولید خاموشش کنید."
                    if debug
                    else "Running with production error handling"
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "name": "Debug Mode",
                "status": "warning",
                "value": str(exc)[:200],
                "description": "Could not read the debug flag",
            }

    @staticmethod
    async def _check_loopback() -> dict[str, Any]:
        """Whether the server can reach its own public origin.

        The URL comes from the same resolver the server-side fetches use
        (`apiInternalUrl`'s backend twin: `settings.API_BASE_URL` or the
        site URL), not a hardcoded localhost — a check against localhost would
        pass in every environment and answer a question nobody asked.

        A 2xx/3xx is good. Anything else, including a connection error, is a
        warning: the site is serving this very report, so it is up; what may
        be broken is the path from the server to itself through the public
        address, which affects cron pings and webhooks, not customers.
        """
        import httpx

        try:
            from app.core.config.settings import get_settings

            settings_obj = get_settings()
            base = (
                getattr(settings_obj, "API_BASE_URL", "")
                or getattr(settings_obj, "SITE_URL", "")
                or "http://localhost:8000"
            ).rstrip("/")
            url = f"{base}/healthz"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
            if resp.status_code < 400:
                return {
                    "name": "Loopback Request",
                    "status": "good",
                    "value": f"{resp.status_code} from {url}",
                    "description": "The server can reach its own origin",
                }
            return {
                "name": "Loopback Request",
                "status": "warning",
                "value": f"{resp.status_code} from {url}",
                "description": (
                    "سرور به نشانی عمومی خودش نمیرسد؛ کرون و webhookها "
                    "ممکن است کار نکنند."
                ),
            }
        except Exception as exc:  # noqa: BLE001 — a health check never raises
            return {
                "name": "Loopback Request",
                "status": "warning",
                "value": str(exc)[:200],
                "description": (
                    "سرور به نشانی عمومی خودش نمیرسد؛ کرون و webhookها "
                    "ممکن است کار نکنند."
                ),
            }

    @staticmethod
    def _check_disk_space() -> dict[str, Any]:
        """Free space on the uploads volume.

        Thresholds are percentages, not bytes: a 2 TB volume with 1 GB free is
        in trouble and a 20 GB volume with 5 GB free is not, and the operator
        reads "87% used" without needing to know the disk's size. Critical
        below 5%, a warning below 15% — the point is to warn while there is
        still room to act, not to announce the outage after it starts.
        """
        import shutil

        try:
            from app.core.config.settings import get_settings

            target = Path(getattr(get_settings(), "UPLOAD_DIR", "media"))
            # The directory may not exist yet on a fresh install; stat its
            # nearest existing parent rather than reporting a false alarm.
            while not target.exists() and target.parent != target:
                target = target.parent
            usage = shutil.disk_usage(str(target))
            used_pct = round(usage.used / usage.total * 100)
            free_gb = round(usage.free / (1024**3), 1)
            status = "critical" if used_pct >= 95 else ("warning" if used_pct >= 85 else "good")
            return {
                "name": "Disk Space",
                "status": status,
                "value": f"{used_pct}% used, {free_gb} GB free",
                "description": f"Uploads volume at {target}",
            }
        except Exception as exc:  # noqa: BLE001 — a health check never raises
            return {
                "name": "Disk Space",
                "status": "warning",
                "value": str(exc)[:200],
                "description": "Could not read the uploads volume usage",
            }

    @staticmethod
    async def _check_email(db: AsyncSession) -> dict[str, Any]:
        """Can the site send email at all?

        WordPress's Site Health asks this because the failure is silent and
        total: every notification, reset link and order confirmation depends on
        SMTP, and without it they all simply stop — no error anywhere the
        operator looks. The check is configuration-only (is SMTP set, and does
        it name a host?), not a send: a health check that emails someone every
        run is its own problem, and the settings page's test button already
        covers delivery.

        Runtime overrides stored in the database win over the environment, the
        same resolution the sender uses, so a store configured through the
        panel is not told it is unconfigured.
        """
        try:
            from app.modules.notifications.application import email_service

            overrides = None
            try:
                from app.modules.settings.api.routes import _load_smtp_overrides

                overrides = await _load_smtp_overrides(db)
            except Exception:  # noqa: BLE001 — env-only config is still a config
                overrides = None

            config = email_service.get_smtp_config(overrides)
            if not config.is_configured:
                return {
                    "name": "Email Delivery",
                    "status": "warning",
                    "value": "SMTP not configured",
                    "description": (
                        "ایمیلها ارسال نمیشوند: تنظیمات SMTP در صفحهٔ تنظیمات "
                        "تکمیل نشده است. تا آن زمان همهٔ اعلانها بیصدا از "
                        "دست میروند."
                    ),
                }
            return {
                "name": "Email Delivery",
                "status": "good",
                "value": f"SMTP configured ({config.host})",
                "description": "Email sending is configured",
            }
        except Exception as exc:
            return {
                "name": "Email Delivery",
                "status": "warning",
                "value": str(exc)[:200],
                "description": "Could not resolve the email configuration",
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
                # Through the session, not ``db.connect()``: AsyncSession has
                # no connect() and the call raised AttributeError, which the
                # except below turned into a bare "error" row. The Info tab has
                # been reporting a database error since it shipped, and a
                # diagnostic that cannot reach the database is the worst place
                # for that to hide.
                version = await db.execute(text("SELECT version()"))
                db_info["server_version"] = str(version.scalar() or "").split(",")[0]
                count = await db.execute(
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

        # ── Migrations ──────────────────────────────────────────────────────
        # The applied revision is the first thing a support thread asks for
        # after a version: "we are on 7.2" is not a question, "which revision is
        # stamped" is. Read from the table rather than from the scripts on
        # disk, because the disk says what *could* be applied and the table says
        # what *was*.
        try:
            async with asyncio.timeout(3.0):
                # See the note in the database section: the session is the
                # connection; there is no db.connect().
                rev = await db.execute(text("SELECT version_num FROM alembic_version"))
                rows = [str(r[0]) for r in rev.fetchall()]
                autoload = await db.execute(
                    text("SELECT count(*) FROM site_options WHERE autoload = true")
                )
                total_opts = await db.execute(text("SELECT count(*) FROM site_options"))
            sections["migrations"] = {
                "current_revision": rows[0] if len(rows) == 1 else rows,
                # More than one row means the database is mid-merge; saying so is
                # the useful fact, where reporting the first row would look
                # normal.
                "in_consistent_state": len(rows) > 1,
            }
            # Autoload is WordPress's own Info row and the one that explains a
            # slow boot: every autoloaded option is read on every request.
            sections["options"] = {
                "autoloaded_count": int(autoload.scalar() or 0),
                "total_count": int(total_opts.scalar() or 0),
            }
        except Exception as exc:  # noqa: BLE001 — a diagnostic must not raise
            sections["migrations"] = {"error": str(exc)[:200]}

        # ── Scheduled jobs ──────────────────────────────────────────────────
        # What the beat is configured to fire, not whether it fired. A support
        # ticket asking "is the reminder job on?" is answered by the schedule;
        # whether it is *running* is the beat-heartbeat check's job, and the two
        # answer different questions.
        try:
            from app.worker.celery_app import celery_app

            jobs = []
            for name, entry in (celery_app.conf.beat_schedule or {}).items():
                sched = entry.get("schedule")
                jobs.append(
                    {
                        "name": name,
                        "task": entry.get("task"),
                        # A Schedule object renders as its repr; that is enough
                        # for "every 30 minutes" and does not require reaching
                        # into Celery's internals for the human-readable form.
                        "schedule": str(sched) if sched is not None else None,
                    }
                )
            sections["scheduled_jobs"] = {
                "count": len(jobs),
                "jobs": sorted(jobs, key=lambda j: j["name"]),
            }
        except Exception as exc:  # noqa: BLE001
            sections["scheduled_jobs"] = {"error": str(exc)[:200]}

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


#: Order of severity, for folding a list of checks into one status.
_STATUS_RANK = {"good": 0, "unknown": 1, "warning": 2, "critical": 3}


def _worst_status(checks: list[dict[str, Any]]) -> str | None:
    """The worst status across a set of checks.

    A status the ranking does not know about is treated as ``warning`` rather
    than ignored: a new check that invents a status must show up on the history
    list as something to look at, not as silence.
    """
    worst = None
    for check in checks:
        status = str((check or {}).get("status") or "unknown")
        rank = _STATUS_RANK.get(status, 2)
        if worst is None or rank > _STATUS_RANK[worst]:
            worst = status if status in _STATUS_RANK else "warning"
    return worst
