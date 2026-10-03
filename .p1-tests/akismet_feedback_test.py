"""Akismet: the check, and the feedback loop.

Stated up front, because it is the honest limit of this file: **the HTTP client
has never been run against the live service.** There is no key and no account,
so nothing here proves Akismet answers `true` for a given comment. What is
verified is the behaviour this codebase owns — which is where every real
failure mode lives:

* **no key, no call.** The site option is empty on every store that has not
  configured it, and WordPress's own behaviour without a key is "publish
  through". The test asserts the transport recorded *zero* requests rather than
  asserting a fallback, because a fallback is exactly what a broken key guard
  looks like from the outside.
* **an unreachable service has no opinion.** Failing closed would let one slow
  third party hold every comment on the store; the test times the service out
  and requires the comment to still be publishable.
* **`undefined` is not ham.** Akismet answers in three words, and reading the
  third as "not spam" would silently start letting spam through the day the
  service declined to classify something.
* **the feedback loop actually fires on the moderator's decision**, including
  through bulk moderation — the path that produces the most ground truth and the
  one a naive implementation skips because it does not call `moderate_comment`.

Run:  python ../.p1-tests/akismet_feedback_test.py
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.application import akismet_client as ac
from app.modules.blog.application import akismet_feedback as fb
from app.modules.blog.application.akismet_client import AkismetClient
from app.modules.blog.domain.models import BlogComment, BlogPost, CommentStatus
from app.modules.users.domain.models import User

TAG = "p1akismet"
bad: list[str] = []


class RecordingTransport:
    """A transport that answers a script and remembers what it was asked.

    Recording the calls is the point: a test that only checks the returned
    verdict cannot tell "the guard short-circuited" from "the call happened and
    returned false", and those are opposite outcomes.
    """

    def __init__(self, status=200, body="true"):
        self.status = status
        self.body = body
        self.calls: list[tuple[str, dict, float]] = []

    async def post_form(self, url, data, *, timeout):
        self.calls.append((url, dict(data), timeout))
        return self.status, self.body


class ExplodingTransport:
    """Every call raises — stands in for a socket that never answers."""

    def __init__(self, exc: BaseException):
        self.exc = exc
        self.calls = 0

    async def post_form(self, url, data, *, timeout):
        self.calls += 1
        raise self.exc


def check(label, ok, detail=""):
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    # --- 1. no key, no request --------------------------------------------
    transport = RecordingTransport(body="true")
    client = AkismetClient(transport=transport)
    verdict = await client.check_comment(
        api_key="", blog_url="https://shop.example",
        user_ip="1.2.3.4", user_agent="curl/8", comment_content="buy now",
    )
    check("1. an empty key produces no opinion", verdict is None, str(verdict))
    check("1b. and makes no request at all", len(transport.calls) == 0,
          f"{len(transport.calls)} calls — this is WordPress without a key")

    verdict = await client.check_comment(
        api_key="   ", blog_url="https://shop.example",
        user_ip="1.2.3.4", user_agent="", comment_content="hi",
    )
    check("1c. a whitespace key is still no key", verdict is None)
    check("1d. still no request", len(transport.calls) == 0)

    # A key but no site URL: Akismet compares the blog against its record, so
    # there is nothing to send and nothing to learn from.
    transport2 = RecordingTransport(body="true")
    verdict = await AkismetClient(transport=transport2).check_comment(
        api_key="k", blog_url="", user_ip="", user_agent="",
        comment_content="x",
    )
    check("2. a key without a site URL sends nothing",
          verdict is None and len(transport2.calls) == 0)

    # --- 2. the three documented answers ------------------------------------
    spam_t = RecordingTransport(body="true")
    v = await AkismetClient(transport=spam_t).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="cheap watches",
    )
    check("3. 'true' is spam", v is not None and v.is_spam, str(v))
    check("3b. and the key goes in the query, per Akismet's API",
          "key=k" in spam_t.calls[0][0], spam_t.calls[0][0])
    check("3c. the caller's IP and text are sent",
          spam_t.calls[0][1].get("user_ip") == "1.2.3.4"
          and spam_t.calls[0][1].get("comment_content") == "cheap watches")

    ham_t = RecordingTransport(body="false")
    v = await AkismetClient(transport=ham_t).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="thanks, this helped",
    )
    check("4. 'false' is ham", v is not None and not v.is_spam, str(v))

    undef_t = RecordingTransport(body="undefined")
    v = await AkismetClient(transport=undef_t).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="x",
    )
    check("5. 'undefined' is NO opinion, not ham", v is None,
          f"{v} — reading it as ham would let spam through when the service "
          f"declines to classify")

    err_t = RecordingTransport(status=500, body="")
    v = await AkismetClient(transport=err_t).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="x",
    )
    check("6. a 5xx is no opinion", v is None, str(v))

    # --- 3. an unreachable service must not decide anything -----------------
    slow = ExplodingTransport(asyncio.TimeoutError())
    v = await AkismetClient(transport=slow).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="a real person's comment",
    )
    check("7. a timeout is no opinion, not spam",
          v is None and slow.calls == 1, f"{v} after {slow.calls} calls")

    boom = ExplodingTransport(RuntimeError("transport blew up"))
    v = await AkismetClient(transport=boom).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="x",
    )
    check("7b. an unexpected client error is also no opinion", v is None, str(v))

    # The self-hosted endpoint is a real option, not a constant.
    selfhosted = RecordingTransport(body="true")
    await AkismetClient(transport=selfhosted).check_comment(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="x",
        api_url="https://akismet.internal/1.1/",
    )
    check("8. a self-hosted endpoint is used as given",
          selfhosted.calls[0][0].startswith("https://akismet.internal/1.1/"),
          selfhosted.calls[0][0])

    # --- 4. the feedback submissions ---------------------------------------
    ham_fb = RecordingTransport(body="")
    ok = await AkismetClient(transport=ham_fb).submit_feedback(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="real", is_spam=False,
    )
    check("9. a moderator's approve goes to submit-ham",
          ok and "submit-ham" in ham_fb.calls[0][0], ham_fb.calls[0][0])
    spam_fb = RecordingTransport(body="")
    await AkismetClient(transport=spam_fb).submit_feedback(
        api_key="k", blog_url="https://shop.example", user_ip="1.2.3.4",
        user_agent="Mozilla", comment_content="junk", is_spam=True,
    )
    check("9b. and their spam decision goes to submit-spam",
          "submit-spam" in spam_fb.calls[0][0], spam_fb.calls[0][0])

    # --- 5. the loop, against real rows -------------------------------------
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    async with Session() as db:
        # Debris from a killed run.
        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogComment).where(
                BlogComment.post_id == stale.id))
            await db.execute(delete(BlogPost).where(BlogPost.id == stale.id))
        await db.execute(delete(User).where(User.email.like(f"%{TAG}%")))
        await db.commit()

        # `phone` is the unique required column; the email is only for the
        # debris sweep above, and a distinct phone per run keeps two concurrent
        # fixtures from deleting each other's rows.
        user = User(
            phone=f"9{TAG[:6].replace('p', '3')}{abs(hash(TAG)) % 10000:04d}",
            email=f"{TAG}@example.test", password_hash="x", is_active=True,
        )
        db.add(user)
        await db.flush()
        post = BlogPost(
            title=f"{TAG} post", slug=f"{TAG}-post",
            content=f"<p>{TAG}</p>", author_id=user.id,
        )
        db.add(post)
        await db.flush()

        async def make_comment(text: str, ip="5.6.7.8") -> BlogComment:
            c = BlogComment(
                post_id=post.id, resource_id=post.id, content=text,
                author_name="Spammer", author_email=f"{uuid.uuid4().hex}@spam.test",
                author_url="http://bit.ly/cheap", author_ip=ip,
                author_user_agent="curl/8.4.0",
                status=CommentStatus.PENDING,
            )
            db.add(c)
            await db.flush()
            return c

        # The IP and user-agent have to survive to the row, or the feedback
        # submission has nothing identifying to send — the field existing on the
        # model is not the field being written.
        c1 = await make_comment("cheap watches at http://bit.ly/x")
        await db.commit()
        fresh = await db.get(BlogComment, c1.id)
        check("10. the row keeps the IP and user-agent feedback needs",
              fresh.author_ip == "5.6.7.8"
              and fresh.author_user_agent == "curl/8.4.0",
              f"{fresh.author_ip} / {fresh.author_user_agent}")

        # No key configured: the loop must do nothing, silently.
        await SiteOptionsService.set(db, ac.API_KEY_OPTION, "")
        await db.commit()
        t = RecordingTransport()
        submitted = await fb.report_moderation(
            db, fresh, status=CommentStatus.SPAM, client=AkismetClient(transport=t))
        check("11. with no key the loop submits nothing",
              submitted is False and len(t.calls) == 0, f"{submitted} / {t.calls}")

        # A key, but the site URL is what Akismet matches against. Missing, so
        # the submission is refused rather than sent with an empty blog.
        await SiteOptionsService.set(db, ac.API_KEY_OPTION, "secret-key")
        await SiteOptionsService.set(db, "site_url", "")
        await db.commit()
        t = RecordingTransport()
        submitted = await fb.report_moderation(
            db, fresh, status=CommentStatus.SPAM, client=AkismetClient(transport=t))
        check("12. a key without a site URL submits nothing",
              submitted is False and len(t.calls) == 0, f"{submitted} / {t.calls}")

        # Both configured: the decision goes out.
        await SiteOptionsService.set(db, "site_url", "https://shop.example/")
        await db.commit()
        t = RecordingTransport()
        submitted = await fb.report_moderation(
            db, fresh, status=CommentStatus.SPAM, client=AkismetClient(transport=t))
        check("13. a moderator's spam decision is submitted",
              submitted is True and len(t.calls) == 1, f"{submitted} / {t.calls}")
        check("13b. addressed to submit-spam",
              bool(t.calls) and "submit-spam" in t.calls[0][0],
              t.calls[0][0] if t.calls else "no call")
        check("13c. carrying the comment's IP, agent and text",
              bool(t.calls)
              and t.calls[0][1].get("user_ip") == "5.6.7.8"
              and t.calls[0][1].get("user_agent") == "curl/8.4.0"
              and t.calls[0][1].get("comment_content")
              == "cheap watches at http://bit.ly/x",
              str(t.calls[0][1]) if t.calls else "no call")
        check("13d. and the key, which the option set to a placeholder",
              bool(t.calls) and "key=secret-key" in t.calls[0][0])

        # Approve is the other half of the loop, and it must not be reported as
        # spam.
        t = RecordingTransport()
        await fb.report_moderation(
            db, fresh, status=CommentStatus.APPROVED,
            client=AkismetClient(transport=t))
        check("14. an approve is reported as ham",
              bool(t.calls) and "submit-ham" in t.calls[0][0],
              t.calls[0][0] if t.calls else "no call")

        # Trash is NOT spam. An operator trashes for tone as often as for
        # adverts, and reporting every one teaches the service to distrust
        # ordinary speech.
        t = RecordingTransport()
        await fb.report_moderation(
            db, fresh, status=CommentStatus.TRASH,
            client=AkismetClient(transport=t))
        check("15. a trash is not reported as spam",
              bool(t.calls) and "submit-ham" in t.calls[0][0],
              "trash reported as spam would train the service on tone, not spam")

        # A rejected submission is a lost signal, never a failed moderation.
        t = RecordingTransport(status=403, body="")
        submitted = await fb.report_moderation(
            db, fresh, status=CommentStatus.SPAM,
            client=AkismetClient(transport=t))
        check("16. a rejected submission is reported as not-sent",
              submitted is False)

        # --- 6. through the real service ------------------------------------
        from app.modules.blog.application.comment_service import CommentService

        c2 = await make_comment("more junk http://bit.ly/y", ip="9.9.9.9")
        await db.commit()
        svc = CommentService(db)
        c2_id = c2.id

        # The loop has to fire through `moderate_comment` — the path the
        # moderation tab and the one-click mail links both take.
        seen: list[str] = []
        recorded = RecordingTransport()

        class Spy(AkismetClient):
            async def submit_feedback(self, **kw):
                seen.append(kw.get("comment_content", ""))
                return await super().submit_feedback(**kw)

        def spy_with(t):
            return Spy(transport=t)

        spy = lambda: spy_with(recorded)  # noqa: E731 — a factory, not an instance
        svc._akismet = spy()
        # The feedback module constructs its own client when none is passed.
        # Patching the constructor, not one instance, is what makes the spy the
        # only client the loop can reach.
        fb.AkismetClient = spy
        await svc.moderate_comment(c2_id, CommentStatus.SPAM)
        check("17. moderating one comment feeds the loop",
              any("bit.ly/y" in s for s in seen), f"submissions={seen}")
        check("17b. and the comment really changed status",
              (await db.get(BlogComment, c2_id)).status == CommentStatus.SPAM)

        # Bulk moderation does not call `moderate_comment`. This is the path
        # that produces the most ground truth — a moderator clearing a wave —
        # and the one that silently skips the loop if only the single path is
        # wired.
        c3 = await make_comment("wave one http://bit.ly/z", ip="9.9.9.9")
        c4 = await make_comment("wave two http://bit.ly/w", ip="9.9.9.8")
        await db.commit()
        seen.clear()
        result = await svc.bulk_moderate([c3.id, c4.id], "spam")
        check("18. bulk moderation succeeded", result["ok"] == 2, str(result))
        check("18b. and fed the loop for BOTH rows",
              len(seen) == 2, f"submissions={seen}")

        # A trash wave is not spam training.
        c5 = await make_comment("rude but human", ip="9.9.9.7")
        c6 = await make_comment("also human", ip="9.9.9.6")
        await db.commit()
        seen.clear()
        t = RecordingTransport()
        svc._akismet = Spy(transport=t)
        fb.AkismetClient = lambda: Spy(transport=t)
        await svc.bulk_moderate([c5.id, c6.id], "trash")
        check("19. a bulk trash is not reported as spam",
              bool(t.calls) and all("submit-ham" in c[0] for c in t.calls),
              str([c[0] for c in t.calls]))

        # --- 7. a comment posts even when the service is dead --------------
        # The local engine must keep deciding on its own. With Akismet
        # configured but unreachable, an ordinary comment still has to reach the
        # front page — the third party is not allowed to become a dependency.
        dead = ExplodingTransport(ConnectionResetError("connection reset"))
        svc._akismet = AkismetClient(transport=dead)
        from app.modules.blog.schemas.blog import BlogCommentCreate

        posted = await svc.create_comment(
            BlogCommentCreate(
                post_id=post.id,
                content="سلام، این یک نظر واقعی و طولانی است که هیچ نشانه‌ای از اسپم ندارد.",
                author_name="مشتری", author_email="customer@example.test",
            ),
            author_ip="4.4.4.4", author_user_agent="curl/8.4.0",
            auto_approve=True,
        )
        check("20. a comment posts even with Akismet unreachable",
              posted is not None and posted.id, str(posted)[:80])
        check("20b. the service was actually consulted (and failed)",
              dead.calls >= 1, f"{dead.calls} calls")
        # `comment_moderation` defaults to on, so every guest comment is
        # PENDING regardless of Akismet. That is the *setting* deciding, not the
        # service — so the comparison has to be made with it off, or this check
        # would pass for the wrong reason and fail for an unrelated one.
        await SiteOptionsService.set(db, "comment_moderation", "0")
        await db.commit()
        posted2 = await svc.create_comment(
            BlogCommentCreate(
                post_id=post.id,
                content="سلام، این یک نظر واقعی و طولانی است که هیچ نشانه‌ای از اسپم ندارد.",
                author_name="مشتری", author_email="customer2@example.test",
            ),
            author_ip="4.4.4.5", author_user_agent="curl/8.4.5",
            auto_approve=True,
        )
        stored_posted = await db.get(BlogComment, posted2.id)
        check("20c. and the local engine did not hold it",
              stored_posted.status == CommentStatus.APPROVED,
              str(stored_posted.status))

        # A spam-looking comment is still held by the local engine alone when
        # the service is dead — the guarantee is one-directional.
        held = await svc.create_comment(
            BlogCommentCreate(
                post_id=post.id,
                # One link (the site's own limit is two) plus a link-shaped
                # author name and URL: the local engine scores those at 9 and 9,
                # well past its threshold of 5.
                content="بهترین ساعت خرید ساعت است",
                author_name="http://spam.example",
                author_url="http://bit.ly/free-money",
            ),
            author_ip="4.4.4.4", author_user_agent="curl/8.4.0",
            auto_approve=True,
        )
        stored_held = await db.get(BlogComment, held.id)
        check("21. the local engine still holds spam with Akismet dead",
              stored_held.status == CommentStatus.PENDING,
              str(stored_held.status))

        # The strongest form of the claim: the same ordinary comment reaches the
        # same status whether the third party answers or throws. If the outage
        # path diverged, an outage would change who sees their comment live.
        svc._akismet = spy_with(RecordingTransport(body="false"))
        healthy = await svc.create_comment(
            BlogCommentCreate(
                post_id=post.id,
                content="سلام، این یک نظر واقعی و طولانی است که هیچ نشانه‌ای از اسپم ندارد.",
                author_name="مشتری", author_email="customer3@example.test",
            ),
            author_ip="4.4.4.6", author_user_agent="curl/8.4.6",
            auto_approve=True,
        )
        stored_healthy = await db.get(BlogComment, healthy.id)
        check("22. a healthy service produces the same outcome as a dead one",
              stored_healthy.status == stored_posted.status,
              f"{stored_healthy.status} vs {stored_posted.status}")

        # Cleanup: options first, since the other fixtures read them.
        await SiteOptionsService.set(db, ac.API_KEY_OPTION, "")
        await SiteOptionsService.set(db, "site_url", "")
        await db.commit()
        for c in (await db.execute(select(BlogComment).where(
                BlogComment.post_id == post.id))).scalars().all():
            await db.delete(c)
        await db.delete(post)
        await db.delete(user)
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nAKISMET GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: no key makes no request, an unreachable or undecided "
          "service has no opinion, 'undefined' is not ham, and a moderator's "
          "decision — single or bulk — reaches the service when configured.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))