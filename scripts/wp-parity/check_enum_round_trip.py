"""An enum column must round-trip a row the ORM did not write.

This is the failure the storage contract protects against, and it is invisible
to a test that only uses the ORM: when a column is declared with a lowercase
`server_default` while SQLAlchemy stores member NAMES, every ORM path passes and
the first row written outside it — a raw insert, a bulk load, a restore — raises
LookupError while the result set is still being mapped. The error takes out the
whole listing, not one row.

So this writes rows with raw SQL using the declared default, then reads them
back through the ORM. Anything the model and the database default disagree on
shows up here as a failure rather than in production.

Run:  python scripts/wp-parity/check_enum_round_trip.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

# (table, column, the member NAME the default must write, a column set that
#  satisfies NOT NULL without naming the enum column at all — the insert below
#  deliberately relies on the column default, because that is the only path a
#  model edit cannot fix)
PROBES = [
    ("newsletter_campaigns", "status", "DRAFT"),
    ("newsletter_campaign_recipients", "status", "PENDING"),
    ("cms_pages", "visibility", "PUBLIC"),
]


async def _any_subscriber(db) -> str:
    """Some subscriber's id, creating one if the table is empty.

    The recipients row points at a subscriber, so the probe cannot insert one
    out of nothing — and using a fixed id would collide the moment the database
    is not the one this was written against.
    """
    from app.modules.newsletter.domain.models import NewsletterSubscriber
    from sqlalchemy import text

    row = (await db.execute(
        text("SELECT email FROM newsletter_subscribers LIMIT 1")
    )).first()
    if row is not None:
        # The subscriber table is keyed by email, not by a surrogate id.
        return str(row[0])
    sub = NewsletterSubscriber(email=f"probe-{uuid.uuid4().hex[:10]}@example.com")
    db.add(sub)
    await db.flush()
    return str(sub.id)


async def main() -> int:
    import app.main  # noqa: F401 — registers every model, as the app does
    from sqlalchemy import text, select
    from app.core.database.session import _build_engine, async_sessionmaker

    from app.modules.newsletter.domain.models import (
        NewsletterCampaign,
        NewsletterCampaignRecipient,
    )
    from app.modules.content.domain.models import CmsPage
    from app.modules.blog.domain.models import BlogPost

    by_table = {
        "newsletter_campaigns": (NewsletterCampaign, {"name": "probe", "subject": "s", "body_html": "<p>x</p>"}),
        "newsletter_campaign_recipients": (NewsletterCampaignRecipient, None),
        "cms_pages": (CmsPage, {"slug": f"probe-{uuid.uuid4().hex[:10]}", "title": "probe", "body_html": "<p>x</p>"}),
    }

    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    failures: list[str] = []
    made: list[tuple[str, str]] = []

    async with Session() as db:
        # Debris from a run that died before its cleanup would otherwise make
        # this one fail on a duplicate slug instead of checking anything.
        for stale in (
            "DELETE FROM cms_pages WHERE slug LIKE 'probe-%'",
            "DELETE FROM newsletter_campaigns WHERE name LIKE 'probe%'",
            "DELETE FROM newsletter_subscribers WHERE email LIKE 'probe-%'",
        ):
            await db.execute(text(stale))
        await db.commit()

        for table, column, expected in PROBES:
            model, extra = by_table[table]
            pid = str(uuid.uuid4())

            if table == "newsletter_campaign_recipients":
                # Needs a campaign to point at, so create one through the ORM.
                camp = NewsletterCampaign(name="probe-camp", subject="s", body_html="<p>x</p>")
                db.add(camp)
                await db.flush()
                made.append(("newsletter_campaigns", str(camp.id)))
                await db.execute(
                    text(
                        f"INSERT INTO {table} (id, campaign_id, subscriber_id) "
                        "VALUES (:i, :c, :sub)"
                    ),
                    {
                        "i": pid,
                        "c": str(camp.id),
                        # a subscriber row has to exist for the FK; any real one
                        # will do, the point is the status default
                        "sub": str(await _any_subscriber(db)),
                    },
                )
            else:
                # The enum column is deliberately left out: the insert relies
                # on the column default, which is the thing a model edit cannot
                # fix and the thing a raw insert or a restore actually uses.
                cols = ", ".join(extra.keys())
                placeholders = ", ".join(f":{k}" for k in extra)
                params = {**extra, "i": pid}
                await db.execute(
                    text(f"INSERT INTO {table} (id, {cols}) "
                         f"VALUES (:i, {placeholders})"),
                    params,
                )
            made.append((table, pid))
            await db.commit()

            # The read that used to raise.
            row = (await db.execute(select(model).where(model.id == pid))).scalar_one_or_none()
            got = getattr(row, column, None) if row is not None else None
            value = getattr(got, "value", got)
            ok = got is not None and str(value).lower() == expected.lower()
            print(f"  {table}.{column}: read back as {value!r} — {'ok' if ok else 'MISMATCH'}")
            if not ok:
                failures.append(f"{table}.{column} did not round-trip: {got!r}")

        for table, pid in made:
            await db.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": pid})
        await db.commit()

    await eng.dispose()
    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: every probed enum column reads back a row written outside the ORM.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))