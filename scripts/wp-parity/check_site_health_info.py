"""Live test for the Site Health info tab (wave 6 #84).

Two things must hold, and only the second is interesting:

  1. The endpoint returns a usable snapshot (server, database, storage, settings).
  2. **No secret is in it.** The service uses an allow-list rather than
     masking secret-looking names, because a denylist is a bet that every
     future secret matches one of the patterns — and this payload gets pasted
     into support tickets.

The second assertion is the one worth writing. A test that only checks the
endpoint returns 200 would pass against a version that dumped the whole
settings table.

Run:  python scripts/wp-parity/check_site_health_info.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

# Anything matching these must never appear as a key or a value in the payload.
SECRET_MARKERS = (
    "secret",
    "password",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "jwt",
    "merchant",
    "sms_key",
    "dsn",
)


def flatten(obj, path: str = "") -> list[tuple[str, str]]:
    """Every (key, value-as-text) pair, flattened, for scanning."""
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append((f"{path}.{k}" if path else str(k), ""))
            out.extend(flatten(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(flatten(v, f"{path}[{i}]"))
    else:
        out.append((path, str(obj)))
    return out


def main() -> int:
    from app.core.database.session import async_session_factory
    from app.modules.settings.application.site_health_service import SiteHealthService

    async def run() -> dict:
        async with async_session_factory() as db:
            return await SiteHealthService.debug_info(db)

    try:
        info = asyncio.run(run())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: debug_info raised: {exc!r}")
        return 1

    sections = info.get("sections", {})
    print("sections:", ", ".join(sorted(sections)) or "(none)")

    # ── 1. usable content ──────────────────────────────────────────────────
    required = {"server", "database", "settings"}
    missing = sorted(required - set(sections))
    if missing:
        print(f"FAIL: missing section(s): {missing}")
        return 1
    if not sections["server"].get("python"):
        print("FAIL: server.python is empty — the snapshot is not usable")
        return 1

    # ── 2. no secrets ──────────────────────────────────────────────────────
    pairs = flatten(info)
    leaks: list[str] = []
    for key, value in pairs:
        low = key.lower()
        for marker in SECRET_MARKERS:
            # A key named e.g. "api_docs_enabled" is fine; "api_key" is not.
            if marker in low and low.strip(".") != "settings":
                leaks.append(f"key looks like a secret: {key}")
        for marker in SECRET_MARKERS:
            if marker in value.lower() and len(value) > 12:
                leaks.append(f"value at {key} contains {marker!r}: {value[:60]}")

    if leaks:
        print("\nFAIL: the info payload exposes something secret-looking:")
        for leak in sorted(set(leaks))[:10]:
            print(f"  - {leak}")
        return 1

    total = len(pairs)
    print(f"flattened fields    : {total}")
    print("\nPASS: the info tab is populated and contains no secret-shaped field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())