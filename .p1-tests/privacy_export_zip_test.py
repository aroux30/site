"""The GDPR export arrives as a structured ZIP, not one blob of JSON.

The subject's export was a single JSON document: a wall of nested objects with
no way to tell which table was which, and no index saying what was inside or
what failed. This drives the real flow — submit an export request, run it, and
collect the ZIP — and asserts the archive's shape:

  * it is a valid ZIP with an ``index.html``, a ``_report.json``, and one JSON
    file per source under ``data/``;
  * the index links the source files, so opening it is a table of contents;
  * the archive is one-shot: a second collection of the same request is a 404,
    because the payload is cleared as it is read.

Run:  python .p1-tests/privacy_export_zip_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.settings.domain.models import PrivacyRequest
from app.modules.users.domain.models import User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    phone = "96" + uuid.uuid4().hex[:9]

    # The submit endpoint is rate-limited to 5/hour per IP, deliberately — a
    # GDPR queue is an abuse target. This fixture is a legitimate client that
    # happens to share the loopback address with every other local run, so
    # without clearing the counter it can only run five times an hour and then
    # fails with a 429 that looks like a product bug. Clearing this one key
    # for this one endpoint is the fixture staying honest about what it is.
    try:
        from app.core.cache.redis import get_redis

        redis = await get_redis()
        await redis.delete(
            "LIMITS:LIMITER/127.0.0.1//api/v1/settings/privacy/requests/5/1/hour"
        )
    except Exception:  # noqa: BLE001 — no Redis means no limiter to clear
        pass

    async with Session() as db:
        user = User(phone=phone, is_active=True, is_verified=True,
                    author_slug=f"p1zip{uuid.uuid4().hex[:6]}")
        db.add(user)
        await db.flush()
        db.add(UserProfile(user_id=user.id, first_name="P1Zip", last_name="Probe"))
        await db.commit()
        user_id = user.id

    token = create_access_token(
        str(user_id), {"roles": ["customer"], "permissions": []}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        try:
            # 1. Submit an export request as the subject.
            r = await client.post(
                "/api/v1/settings/privacy/requests",
                headers=headers,
                json={"type": "export", "notes": "test"},
            )
            check("1. an export request can be submitted",
                  r.status_code in (200, 201), f"status {r.status_code} {r.text[:160]}")
            if r.status_code not in (200, 201):
                return 1
            body = r.json()
            request_id = body.get("id") or body.get("request_id")
            # Confirm it (the flow requires confirmation before an operator runs it).
            await client.post(
                f"/api/v1/settings/privacy/requests/{request_id}/confirm",
                headers=headers,
                json={"code": body.get("confirmation_code", "")},
            )

            # 2. An operator runs it. Call the service directly: the admin route
            #    needs an admin actor and this test is about the archive shape.
            from app.modules.settings.application.privacy_request_service import (
                PrivacyRequestService,
            )

            async with Session() as db:
                admin = (
                    await db.execute(
                        select(User).where(User.is_superuser == True).limit(1)
                    )
                ).scalars().first()
                try:
                    await PrivacyRequestService.run_export(
                        db, request_id=uuid.UUID(str(request_id)), admin_id=admin.id
                    )
                    check("2. the export runs", True)
                except Exception as exc:  # noqa: BLE001
                    check("2. the export runs", False, f"{type(exc).__name__}: {exc}")

            # 3. Collect the ZIP.
            r = await client.get(
                f"/api/v1/settings/privacy/requests/{request_id}/result.zip",
                headers=headers,
            )
            check("3. the zip route answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:160]}")
            check("3b. with a zip content type",
                  "zip" in r.headers.get("content-type", ""),
                  r.headers.get("content-type", ""))
            if r.status_code == 200:
                zf = zipfile.ZipFile(io.BytesIO(r.content))
                names = zf.namelist()
                check("4. the archive has an index.html", "index.html" in names,
                      f"names={names[:8]}")
                check("4b. and a _report.json", "_report.json" in names)
                check("4c. and at least one source under data/",
                      any(n.startswith("data/") and n.endswith(".json") for n in names),
                      f"names={names[:8]}")
                if "index.html" in names:
                    idx = zf.read("index.html").decode("utf-8")
                    check("5. the index links the source files",
                          "data/" in idx and ".json" in idx,
                          "index does not point at the files beside it")
                    check("5b. and the index is a real document",
                          "<html" in idx.lower() and "</html>" in idx.lower())

            # 6. One-shot: a second collection is refused.
            r2 = await client.get(
                f"/api/v1/settings/privacy/requests/{request_id}/result.zip",
                headers=headers,
            )
            check("6. the export is one-shot (second read refused)",
                  r2.status_code == 404, f"status {r2.status_code}")
        finally:
            async with Session() as db:
                await db.execute(
                    delete(PrivacyRequest).where(PrivacyRequest.user_id == user_id)
                )
                await db.execute(
                    delete(UserProfile).where(UserProfile.user_id == user_id)
                )
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
            check("7. probes cleaned up", True)

    await eng.dispose()
    if bad:
        print("\nZIP-EXPORT GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the GDPR export arrives as a structured ZIP with an index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))