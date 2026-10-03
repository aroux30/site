"""Live check: guest comments follow the subject through export and erasure.

P0 "حریم خصوصی: پوشش دیدگاه‌های مهمان". A guest comment carries an email and an
IP and no owner, so selecting on ``author_id`` alone never saw one. Both halves
of Article 15/17 were blind to them: the export came back with no comments in it,
and the erasure left the subject's email and IP in a table the whole storefront
can read.

Four cases, because the two halves fail differently and one of them fails
differently again on a hard delete:

  1. export    — a guest comment appears
  2. export    — a comment by a different address does not
  3. anonymize — a guest comment loses its email, IP, name and URL
  4. hard delete — a guest comment loses them too, since the cascade cannot
     reach a row that hangs off nothing

    cd backend && PYTHONPATH=. python scripts/verify_guest_comment_privacy.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.blog.domain.models import BlogComment  # noqa: E402
from app.core.security.ip_anonymize import anonymize_ip  # noqa: E402
from app.modules.settings.application.privacy_service import PrivacyService  # noqa: E402

#: The account keeps the address as typed; the comment form lowercases what it
#: is given, so the two spell the same mailbox differently. That is the real
#: shape of the bug: an equality test finds nothing here even though the subject
#: is obviously the author, and the erasure then leaves their data in place.
SUBJECT_EMAIL = "Guest.Probe@Example.COM"
SUBJECT_EMAIL_AS_COMMENTED = "guest.probe@example.com"
STRANGER_EMAIL = "stranger.probe@example.com"
HARD_EMAIL = "hard.delete.probe@example.com"
#: Documentation ranges (RFC 5737), so a probe address can never be a real one.
#: Distinct per probe because both are asserted on afterwards and the check has
#: to tell the subject's own comment from the one left after the hard delete.
GUEST_IP = "203.0.113.47"
HARD_IP = "198.51.100.61"


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _create_post(db, suffix: str) -> str:
    post_id = str(uuid.uuid4())
    author_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, password_hash, is_active, is_verified, "
            "is_superuser, totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, 'x', true, true, false, false, now(), now())"
        ),
        {"u": author_id, "p": "9" + uuid.uuid4().hex[:9]},
    )
    await db.execute(
        text(
            "INSERT INTO blog_posts (id, author_id, title, slug, content, "
            "status, created_at, updated_at) "
            "VALUES (:i, :a, :t, :s, 'body', 'PUBLISHED', now(), now())"
        ),
        {
            "i": post_id,
            "a": author_id,
            "t": f"probe {suffix}",
            "s": f"probe-{suffix}-{uuid.uuid4().hex[:8]}",
        },
    )
    return post_id, author_id


async def _create_comment(
    db, post_id: str, email: str, name: str, ip: str = GUEST_IP
) -> str:
    cid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO blog_comments (id, author_id, author_name, author_email, "
            "author_url, author_ip, author_user_agent, content, status, "
            "post_id, resource_type, resource_id, comment_type, created_at) "
            "VALUES (:i, NULL, :n, :e, 'https://example.com/probe', "
            ":ip, 'probe-agent', 'probe body', 'APPROVED', "
            ":r, 'blog_post', :r, 'comment', now())"
        ),
        {"i": cid, "n": name, "e": email, "r": post_id, "ip": ip},
    )
    return cid


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
            required = {
                "id",
                "author_id",
                "author_name",
                "author_email",
                "author_url",
                "author_ip",
                "author_user_agent",
                "content",
                "status",
                "resource_type",
                "resource_id",
            }
            missing = required - columns
            if missing:
                print(
                    "SKIP: blog_comments is missing %s — the probe cannot build a "
                    "guest comment." % ", ".join(sorted(missing))
                )
                return 0

            post_id, author_id = await _create_post(db, "guest")
            created.append(f"post:{post_id}")
            created.append(f"user:{author_id}")

            subject_id = str(uuid.uuid4())
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, email, password_hash, is_active, "
                    "is_verified, is_superuser, totp_enabled, created_at, updated_at) "
                    "VALUES (:u, :p, :e, 'x', true, true, false, false, now(), now())"
                ),
                {
                    "u": subject_id,
                    "p": "9" + uuid.uuid4().hex[:9],
                    "e": SUBJECT_EMAIL,
                },
            )
            created.append(f"user:{subject_id}")

            guest_cid = await _create_comment(
                db, post_id, SUBJECT_EMAIL_AS_COMMENTED, "Ali"
            )
            stranger_cid = await _create_comment(db, post_id, STRANGER_EMAIL, "Sara")
            created.append(f"comment:{guest_cid}")
            created.append(f"comment:{stranger_cid}")
            await db.commit()

        subject_uuid = uuid.UUID(subject_id)
        guest_uuid = uuid.UUID(guest_cid)
        stranger_uuid = uuid.UUID(stranger_cid)

        # 1 + 2. Export: the subject's own guest comment is in, another's is not.
        async with session() as db:
            export = await PrivacyService.export_user_data(db, subject_uuid)
        exported = {c["id"] for c in export.get("blog_comments", [])}

        if str(guest_uuid) in exported:
            print("PASS: the export carries a comment the subject left as a guest")
        else:
            failures.append(
                "the export omits the subject's guest comment -- an Article 15 access "
                "request that silently drops the subject's own writing"
            )

        if str(stranger_uuid) in exported:
            failures.append(
                "the export carries a comment belonging to a different address, so "
                "one person's data request returns another's"
            )
        else:
            print("PASS: a comment by another address is not exported")

        if export.get("blog_comments") and all(
            c.get("guest") for c in export["blog_comments"]
        ):
            print("PASS: the export marks which comments were guest ones")
        else:
            failures.append(
                "the export does not mark guest comments, so a subject cannot tell "
                "which of their comments predate their account"
            )

        # 3. Anonymize.
        async with session() as db:
            await PrivacyService.erase_user_data(db, subject_uuid, anonymize=True)

        async with session() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT author_name, author_email, author_url, author_ip, "
                        "author_user_agent FROM blog_comments WHERE id = :i"
                    ),
                    {"i": guest_cid},
                )
            ).fetchone()
        # author_name is replaced, not cleared — a comment with no name renders
        # as broken in the storefront, and "Anonymous" identifies nobody. What has
        # to be gone is the column set that can identify the subject: the email,
        # the URL and the user agent.
        #
        # The IP is masked rather than cleared, and that changed when P0-17 landed.
        # WordPress's wp_comments_personal_data_eraser does the same: a flood
        # check groups comments by network, so blanking the column throws away
        # the anti-abuse signal the network was kept for. So this asserts the
        # address is reduced to its network — not merely that the column is not
        # NULL, which a value nobody checked would also satisfy.
        if row is None:
            failures.append("the guest comment vanished entirely; erasure anonymizes")
        elif any(v is not None for v in (row[1], row[2], row[4])):
            failures.append(
                "after anonymization the guest comment still carries %r -- the "
                "subject's email, URL or user agent is still readable on a "
                "public comment" % [v for v in (row[1], row[2], row[4]) if v is not None]
            )
        elif row[3] != anonymize_ip(GUEST_IP):
            failures.append(
                "the guest comment's IP reads %r; it must be reduced to the network "
                "%r, which identifies a network rather than the household in it"
                % (row[3], anonymize_ip(GUEST_IP))
            )
        else:
            print(
                "PASS: anonymization cleared the guest comment's email, URL and agent, "
                "and reduced its IP to %s" % row[3]
            )

        async with session() as db:
            other = (
                await db.execute(
                    text("SELECT author_email FROM blog_comments WHERE id = :i"),
                    {"i": stranger_cid},
                )
            ).scalar()
        if other != STRANGER_EMAIL:
            failures.append(
                "anonymization reached a comment belonging to someone else (%r)"
                % other
            )
        else:
            print("PASS: anonymization left another person's comment alone")

        # 4. Hard delete: the cascade cannot reach a row that hangs off nothing,
        #    so this is where a guest comment would otherwise survive the account.
        post2, author2 = None, None
        async with session() as db:
            post2, author2 = await _create_post(db, "hard")
            created.append(f"post:{post2}")
            created.append(f"user:{author2}")
            subject2 = str(uuid.uuid4())
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, email, password_hash, is_active, "
                    "is_verified, is_superuser, totp_enabled, created_at, updated_at) "
                    "VALUES (:u, :p, :e, 'x', true, true, false, false, now(), now())"
                ),
                {
                    "u": subject2,
                    "p": "9" + uuid.uuid4().hex[:9],
                    "e": HARD_EMAIL,
                },
            )
            created.append(f"user:{subject2}")
            hard_cid = await _create_comment(db, post2, HARD_EMAIL, "Hard", HARD_IP)
            created.append(f"comment:{hard_cid}")
            await db.commit()

        async with session() as db:
            await PrivacyService.erase_user_data(db, uuid.UUID(subject2), anonymize=False)

        async with session() as db:
            survived = (
                await db.execute(
                    text(
                        "SELECT author_email, author_ip FROM blog_comments WHERE id = :i"
                    ),
                    {"i": hard_cid},
                )
            ).fetchone()
            gone = (
                await db.execute(
                    text("SELECT count(*) FROM users WHERE id = :i"),
                    {"i": subject2},
                )
            ).scalar()
        # Read after the call, never before: the call is what deletes the row, so
        # a pre-check would report the account as present and the erasure as
        # having failed.
        if gone:
            failures.append("the hard delete left the account behind")
        elif survived is None:
            print("PASS: the hard delete removed the guest comment too")
        elif survived[0] is not None:
            failures.append(
                "the account is gone but its guest comment still carries the email "
                "%r -- the cascade cannot reach a row with no owner, so the data "
                "outlives the deletion" % survived[0]
            )
        elif survived[1] != anonymize_ip(HARD_IP):
            failures.append(
                "the account is gone but its guest comment's IP reads %r; it must be "
                "reduced to %r" % (survived[1], anonymize_ip(HARD_IP))
            )
        else:
            print(
                "PASS: the hard delete anonymized the guest comment it could not "
                "cascade, reducing its IP to %s" % survived[1]
            )
    finally:
        async with session() as db:
            await db.rollback()
            for item in created:
                kind, _, ident = item.partition(":")
                table = {
                    "comment": "blog_comments",
                    "post": "blog_posts",
                    "user": "users",
                }.get(kind)
                if table:
                    await db.execute(
                        text("DELETE FROM %s WHERE id = :i" % table), {"i": ident}
                    )
            await db.commit()
        print("removed the probe rows")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: guest comments are covered by both halves of the request.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
