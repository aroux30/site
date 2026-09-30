"""Recovery mode: a fatal error pauses the site instead of serving a white page.

WordPress parity. Without this, an unhandled exception on a storefront route
returns a bare 500 and the shop simply disappears — an admin has no signal and
no way to get back in. Here a fatal error flips a pause flag: every request
then renders a recovery page that names the error, and the operator resumes
from the admin (or the flag expires and the site starts serving again).

Deliberately not a crash reporter: it changes what the *customer* sees, which
is the difference between a lost sale and a lost afternoon.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: A file rather than Redis: the pause must survive a Redis outage, which is
#: one of the things that can cause the fatal error in the first place.
PAUSE_FILE = Path(os.environ.get("RECOVERY_MODE_FILE", "/tmp/recovery-mode-paused"))

DEFAULT_PAUSE_MINUTES = 60
EXTENDED_PAUSE_MINUTES = 240
MAX_PAUSE_MINUTES = 1440

RECOVERY_PAGE = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>حالت بازیابی</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
      display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
 .card{{max-width:32rem;padding:2rem;border:1px solid #334155;border-radius:1rem;background:#1e293b}}
 h1{{font-size:1.25rem;margin:0 0 .75rem}} p{{line-height:1.8;color:#94a3b8}}
 code{{background:#0f172a;padding:.15rem .4rem;border-radius:.25rem;color:#fca5a5;font-size:.8rem}}
</style></head><body><div class="card">
<h1>سایت در حالت بازیابی است</h1>
<p>یک خطای جدی رخ داده و سایت برای جلوگیری از نمایش صفحهٔ خراب موقتاً متوقف شده است.
جزئیات خطا برای مدیر ارسال شده است.</p>
<p>پس از رفع مشکل، مدیر می‌تواند سایت را از پنل مدیریت دوباره فعال کند.</p>
<p><code>{reference}</code></p>
</div></body></html>"""


class RecoveryMode:
    """The pause state, and the page that stands in for the site while paused."""

    @staticmethod
    def _read() -> dict[str, Any] | None:
        if not PAUSE_FILE.exists():
            return None
        try:
            return json.loads(PAUSE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    @staticmethod
    def is_paused() -> bool:
        """True while the pause window is open."""
        state = RecoveryMode._read()
        if state is None:
            return False
        try:
            return datetime.now(timezone.utc) < datetime.fromisoformat(state["until"])
        except (KeyError, ValueError):
            return False

    @staticmethod
    def state() -> dict[str, Any] | None:
        return RecoveryMode._read()

    @staticmethod
    def pause(reference: str | None = None) -> dict[str, Any]:
        """Enter recovery mode; returns the state and a reference id."""
        current = RecoveryMode._read() or {}
        extensions = int(current.get("extensions", 0))
        minutes = (
            DEFAULT_PAUSE_MINUTES,
            EXTENDED_PAUSE_MINUTES,
            MAX_PAUSE_MINUTES,
        )[min(extensions, 2)]
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        state = {
            "until": until.isoformat(),
            "extensions": extensions + 1,
            "reference": reference or current.get("reference") or str(uuid.uuid4()),
            "entered_at": current.get("entered_at") or datetime.now(timezone.utc).isoformat(),
        }
        try:
            PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
            PAUSE_FILE.write_text(json.dumps(state), encoding="utf-8")
        except OSError:
            # If the flag cannot be written, recovery mode cannot work; log it
            # rather than masking the original fatal error.
            logger.exception("recovery_mode_pause_file_unwritable")
            return {**state, "persisted": False}
        logger.error("recovery_mode_paused until=%s reference=%s", state["until"], state["reference"])
        return {**state, "persisted": True}

    @staticmethod
    def resume(reference: str | None = None) -> bool:
        """Leave recovery mode. False when the site was not paused."""
        if PAUSE_FILE.exists():
            try:
                PAUSE_FILE.unlink()
            except OSError:
                logger.exception("recovery_mode_pause_file_unremovable")
                return False
            logger.warning("recovery_mode_resumed reference=%s", reference)
            return True
        return False

    @staticmethod
    def response(reference: str | None = None) -> str:
        state = RecoveryMode._read() or {}
        return RECOVERY_PAGE.format(reference=reference or state.get("reference", "—"))
