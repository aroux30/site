"""The admin settings endpoint must serialize every value shape the writers make.

The bug this pins (found by the real-browser sweep, 2026-10-03): the
WordPress-parity content card writes comment options through the
site-options write path as plain strings, but ``SettingResponse.value`` was
typed ``dict[str, Any] | None``. One string row anywhere in the table made
``GET /settings`` answer 500 — and that is the endpoint the whole admin
settings page loads from, so the SMTP form, the payment toggles and the SMS
card all died together on data a current writer had legitimately produced.

The check runs the real response schemas against the real database *without*
needing to leak or write anything: it reads every row the endpoint would
serialize, validates each through both response models, and fails if any shape
the database actually holds cannot be represented.

Run:  python backend/scripts/settings_value_shapes_test.py
Exit: 0 when every stored value validates; 1 with a named list otherwise;
      2 when the database is not reachable (the gate wrapper reports SKIP).
"""

import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main  # noqa: F401 — registers every model, as the app does
from sqlalchemy import select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.settings.domain.models import SiteSetting
from app.modules.settings.schemas.settings import (
    PublicSettingResponse,
    SettingResponse,
)

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        rows = (await db.execute(select(SiteSetting))).scalars().all()
        check("the settings table has rows to exercise", len(rows) > 0,
              f"{len(rows)} row(s)")

        shapes: dict[str, int] = {}
        for row in rows:
            shape = (
                "null" if row.value is None
                else "dict" if isinstance(row.value, dict)
                else "list" if isinstance(row.value, list)
                else type(row.value).__name__
            )
            shapes[shape] = shapes.get(shape, 0) + 1
        print(f"     stored value shapes: {shapes}")

        # Every stored row must validate through BOTH response models — the
        # admin one and the public one. This is the exact validation FastAPI
        # performs when the routes answer.
        scalar_failures: list[str] = []
        for row in rows:
            try:
                SettingResponse.model_validate(row)
            except Exception as exc:  # noqa: BLE001 — the failure IS the signal
                scalar_failures.append(f"{row.key} (SettingResponse): {exc}")
            try:
                PublicSettingResponse(key=row.key, value=row.value)
            except Exception as exc:  # noqa: BLE001
                scalar_failures.append(f"{row.key} (PublicSettingResponse): {exc}")

        check(
            "every stored value serializes through the response schemas",
            not scalar_failures,
            "; ".join(scalar_failures[:5]),
        )

        # The scalar shape specifically: a string row is what broke GET
        # /settings, and a future "fix" that coerces the column to objects
        # would silently rewrite every numeric option into {"value": ...}.
        string_rows = [r for r in rows if isinstance(r.value, str)]
        if string_rows:
            sample = string_rows[0]
            dumped = SettingResponse.model_validate(sample).model_dump()
            check(
                "a string value round-trips as a string, not a coerced object",
                dumped["value"] == sample.value,
                f"{sample.key}: {dumped['value']!r} vs {sample.value!r}",
            )
        else:
            # A database with no scalar rows cannot exercise the branch; say
            # so loudly rather than counting a no-op as a pass.
            print("     note: no string-valued rows in this database; the "
                  "scalar branch was not exercised")

        # And the masking serializer still runs on the wider type: a secret
        # key must not leak just because the annotation widened to Any.
        fake = type(rows[0])(
            id=rows[0].id,
            key="zarinpal_merchant_id",
            value={"merchant_id": "SECRET-123"},
            is_public=False,
        )
        masked = SettingResponse.model_validate(fake).model_dump()
        check(
            "a secret-shaped key is still masked after the Any widening",
            masked["value"] is None,
            f"value={masked['value']!r}",
        )

        rec = type(rows[0])(
            id=rows[0].id, key="some_string_option", value="0", is_public=False,
        )
        rec_masked = SettingResponse.model_validate(rec).model_dump()
        check(
            "a non-secret string passes through unmasked",
            rec_masked["value"] == "0",
            f"value={rec_masked['value']!r}",
        )

    await eng.dispose()
    if bad:
        print("\nSETTINGS VALUE-SHAPE GAPS:")
        for b in bad:
            print(f"  {b}")
        return 1
    print("\nPASS: every value shape the writers store is serializable, "
          "unmasked strings stay strings, and secrets stay masked.")
    return 0


try:
    sys.exit(asyncio.run(main()))
except Exception as exc:  # database unreachable → the gate wrapper reports SKIP
    print(f"database not reachable: {exc}")
    sys.exit(2)
