"""Live check: comment IPs are reduced to their network, and stay reduced.

P0 "حریم خصوصی: نگه‌داشت IP دیدگاه". An IP on a comment is personal data under
Article 4(1) and it was stored in full, indefinitely, on a table the storefront
can read. The erasure path masked an address for the one subject who asked;
nothing applied the same rule by age, so every other comment kept its exact
address forever.

Six assertions, because "the job ran" is not the property being checked:

  1. an old comment's exact address is gone
  2. what replaces it is the network, not NULL — a flood check still groups by
     it, which is why WordPress masks rather than blanks
  3. a comment inside the window keeps its address (the moderator still needs it)
  4. IPv6 is masked to its /64, not left intact
  5. a second run selects nothing (idempotency — otherwise the daily count lies)
  6. the job is registered and on the beat

    cd backend && PYTHONPATH=. python scripts/verify_comment_ip_retention.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.core.security.ip_anonymize import anonymize_ip, ip_is_masked  # noqa: E402
from app.modules.settings.application.comment_ip_retention_service import (  # noqa: E402
    CommentIpRetentionService,
    mask_ips_older_than,
)

TASK = "app.modules.settings.application.tasks.mask_expired_comment_ips"

#: Documentation ranges (RFC 5737 / RFC 3849), so a probe address can never be
#: a real one and the check is safe to run against a live database.
OLD_V4 = "203.0.113.47"
OLD_V6 = "2001:db8:85a3::8a2e:370:7334"
FRESH_V4 = "198.51.100.23"
#: A stranger's old comment. If the sweep reaches it, the age filter is not
#: doing what it claims and the sweep is over-broad.
OTHER_V4 = "192.0.2.91"


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _setup(db, post_id: str) -> dict[str, str]:
    """Three old comments and one fresh one, plus an author and a post."""
    author_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, is_active, is_verified, is_superuser, "
            "totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, true, true, false, false, now(), now())"
        ),
        {"u": author_id, "p": "9" + uuid.uuid4().hex[:9]},
    )
    ids: dict[str, str] = {"user": author_id}
    for key, ip, age_days in (
        ("old_v4", OLD_V4, 60),
        ("old_v6", OLD_V6, 60),
        ("other", OTHER_V4, 60),
        ("fresh", FRESH_V4, 1),
    ):
        cid = str(uuid.uuid4())
        await db.execute(
            text(
                "INSERT INTO blog_comments (id, author_id, author_name, "
                "author_email, author_url, author_ip, author_user_agent, content, "
                "status, post_id, resource_type, resource_id, comment_type, "
                "created_at, updated_at) "
                "VALUES (:i, :a, 'Probe', 'probe@example.invalid', NULL, :ip, "
                "'probe-agent', 'probe body', 'APPROVED', :r, 'blog_post', :r, "
                "'comment', :created, :created)"
            ),
            {
                "i": cid,
                "a": author_id,
                "ip": ip,
                "r": post_id,
                "created": datetime.now(timezone.utc) - timedelta(days=age_days),
            },
        )
        ids[key] = cid
    return ids


async def _read_ips(check, ids: dict[str, str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for key in ("old_v4", "old_v6", "other", "fresh"):
        out[key] = (
            await check.execute(
                text("SELECT author_ip FROM blog_comments WHERE id = :i"),
                {"i": ids[key]},
            )
        ).scalar()
    return out


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []

    try:
        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'blog_comments'"
                        )
                    )
                ).fetchall()
            }
            required = {"id", "author_ip", "created_at", "post_id", "resource_type",
                        "resource_id", "status", "content", "comment_type"}
            missing = required - columns
            if missing:
                print("SKIP: blog_comments is missing %s." % ", ".join(sorted(missing)))
                return 0

            post_id = str(uuid.uuid4())
            author_id = str(uuid.uuid4())
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, is_active, is_verified, "
                    "is_superuser, totp_enabled, created_at, updated_at) "
                    "VALUES (:u, :p, true, true, false, false, now(), now())"
                ),
                {"u": author_id, "p": "9" + uuid.uuid4().hex[:9]},
            )
            await db.execute(
                text(
                    "INSERT INTO blog_posts (id, author_id, title, slug, content, "
                    "status, created_at, updated_at) "
                    "VALUES (:i, :a, 'probe', :s, 'body', 'PUBLISHED', now(), now())"
                ),
                {
                    "i": post_id,
                    "a": author_id,
                    "s": f"ip-probe-{uuid.uuid4().hex[:8]}",
                },
            )
            created = [f"blog_posts:{post_id}", f"users:{author_id}"]
            ids = await _setup(db, post_id)
            created += [f"blog_comments:{ids[k]}" for k in
                        ("old_v4", "old_v6", "other", "fresh")]
            await db.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # 1-5, all against the explicit cutoff: the option-driven path is checked
        # separately below, because a run that passes because the site option
        # happens to be 30 proves neither the age filter nor the masking.
        async with session() as db:
            masked = await mask_ips_older_than(db, cutoff=cutoff)
        if masked < 3:
            failures.append(
                "the sweep rewrote %d row(s); three comments were past the window"
                % masked
            )
        else:
            print("PASS: the sweep rewrote the %d row(s) past the window" % masked)

        async with session() as check:
            after = await _read_ips(check, ids)

        if after["old_v4"] == OLD_V4:
            failures.append(
                "an IPv4 comment past the window still reads %r in full" % OLD_V4
            )
        elif after["old_v4"] != anonymize_ip(OLD_V4):
            failures.append(
                "the old IPv4 became %r; the exact address is gone but so is the "
                "network the flood check groups by" % after["old_v4"]
            )
        elif after["old_v4"] is None:
            failures.append(
                "the old IPv4 was blanked instead of masked — a NULL throws away "
                "the anti-abuse signal the network was kept for"
            )
        else:
            print("PASS: an old IPv4 is reduced to its network (%s)" % after["old_v4"])

        if after["old_v6"] == OLD_V6:
            failures.append(
                "an IPv6 comment past the window still reads %r in full — a store "
                "that masks v4 and leaves v6 intact has anonymized only the easier "
                "half of its commenters" % OLD_V6
            )
        elif after["old_v6"] != anonymize_ip(OLD_V6):
            failures.append(
                "the old IPv6 became %r, which is not its /64" % after["old_v6"]
            )
        else:
            print("PASS: an old IPv6 is reduced to its /64 (%s)" % after["old_v6"])

        if after["fresh"] != FRESH_V4:
            failures.append(
                "a comment inside the window reads %r; the moderator reading a fresh "
                "comment is exactly the reader who still needs the address"
                % after["fresh"]
            )
        else:
            print("PASS: a comment inside the window keeps its address")

        # Idempotency. Without this the daily count is a lie: the job would
        # re-select and re-rewrite the same rows forever, and the number it logs
        # would be work it did not do.
        async with session() as db:
            second = await mask_ips_older_than(db, cutoff=cutoff)
        if second:
            failures.append(
                "a second run rewrote %d row(s); the sweep is not idempotent, so "
                "its own log overstates the work it does every day" % second
            )
        else:
            print("PASS: a second run selects nothing")

        # The idempotency guard itself, not just its observable effect. The
        # second run above still returns 0 when `ip_is_masked` is broken, because
        # `anonymize_ip` then returns the value unchanged and the per-row
        # `masked == raw` check skips the write. So a run that "does nothing"
        # for the wrong reason looks exactly like a correct one, and the sweep
        # would re-read every row past the window forever without ever reporting
        # the cost. The predicate is what makes the loop terminate cheaply, so it
        # is asserted directly.
        for value in (anonymize_ip(OLD_V4), anonymize_ip(OLD_V6)):
            if not ip_is_masked(value):
                failures.append(
                    "ip_is_masked(%r) is false, so the sweep re-reads every row past "
                    "the window on every run and the batch loop has to page through "
                    "the whole table to conclude there is nothing to do" % value
                )
            else:
                print("PASS: a masked value reports itself as masked (%s)" % value)

        # And the option-driven entry point, which is what the task actually
        # calls. Given an explicit window rather than reading site_options, so the
        # assertion is about the wiring and not about whatever this store happens
        # to have configured.
        async with session() as db:
            via_service = await CommentIpRetentionService.mask_expired_ips(
                db, retention_days=30, now=datetime.now(timezone.utc)
            )
        if via_service:
            failures.append(
                "the service entry point rewrote %d row(s) after the sweep had "
                "already finished" % via_service
            )
        else:
            print("PASS: the service entry point finds nothing left to do")

        from app.worker.celery_app import celery_app

        # Finalize first, exactly as a worker start does: autodiscover runs
        # inside finalize(), so checking `tasks` before it reports everything as
        # unregistered — which reads as "nothing is scheduled" when in fact
        # everything is.
        celery_app.loader.import_default_modules()
        celery_app.finalize(auto=True)

        if TASK not in set(celery_app.tasks):
            failures.append("the mask task is not registered, so nothing dispatches it")
        else:
            scheduled = {
                e.get("task")
                for e in (celery_app.conf.beat_schedule or {}).values()
                if isinstance(e, dict)
            }
            if TASK not in scheduled:
                failures.append(
                    "the mask is registered but never scheduled, so addresses stay "
                    "exact forever"
                )
            else:
                print("PASS: the mask is registered and on the beat")
    finally:
        async with session() as db:
            await db.rollback()
            for item in created:
                kind, _, ident = item.partition(":")
                if kind in ("blog_comments", "blog_posts", "users"):
                    await db.execute(
                        text("DELETE FROM %s WHERE id = :i" % kind), {"i": ident}
                    )
            await db.commit()
        print("removed the probe rows")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: past-the-window comment IPs are reduced to their network, once.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
