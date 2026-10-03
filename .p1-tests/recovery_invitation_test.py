"""Recovery mode's invitation key: minted, hashed at rest, verified, one-time.

P1 "ابزارها: حالت بازیابی". The pause/resume page existed; the email with a
recovery link and a temporary login key did not — so a locked-out operator had
a webpage they could not reach the panel to use. This exercises the key
lifecycle, which is the part a security property depends on:

  * a key can only be issued while the site is paused;
  * the stored state never contains the plaintext key (a hash only);
  * the right key verifies, a wrong or empty one does not;
  * an expired key does not verify.

Run:  python .p1-tests/recovery_invitation_test.py
"""

from __future__ import annotations

import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

from app.core.exceptions.recovery_mode import PAUSE_FILE, RecoveryMode

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    was_paused = RecoveryMode.is_paused()
    try:
        # Start clean.
        RecoveryMode.resume()

        # 1. Refused when not paused.
        r = RecoveryMode.issue_invitation()
        check("1. a key is refused when the site is not paused",
              r.get("issued") is False, str(r))

        # 2. Pause, then issue.
        RecoveryMode.pause()
        r = RecoveryMode.issue_invitation()
        check("2. a key is issued while paused", r.get("issued") is True, str(r))
        key = r.get("key", "")
        check("2b. and the plaintext key is returned to the caller", bool(key))

        # 3. The stored state holds a hash, never the plaintext.
        state = json.loads(PAUSE_FILE.read_text(encoding="utf-8"))
        check("3. the pause file stores a hash, not the key",
              "recovery_key_hash" in state and key not in json.dumps(state),
              "the plaintext key is in the pause file")
        check("3b. and that hash is not the key itself",
              state.get("recovery_key_hash") != key)

        # 4. Verification.
        check("4. the right key verifies", RecoveryMode.verify_invitation(key) is True)
        check("4b. a wrong key does not", RecoveryMode.verify_invitation("nope") is False)
        check("4c. an empty key does not", RecoveryMode.verify_invitation("") is False)

        # 5. An expired key does not verify. Rewrite the stored expiry into the
        #    past and re-check — the key never expires on its own in a test.
        state["recovery_key_until"] = "2000-01-01T00:00:00+00:00"
        PAUSE_FILE.write_text(json.dumps(state), encoding="utf-8")
        check("5. an expired key does not verify",
              RecoveryMode.verify_invitation(key) is False)

        # 6. Resuming clears the pause (and the key with it).
        RecoveryMode.pause()
        RecoveryMode.resume()
        check("6. resume clears the pause", RecoveryMode.is_paused() is False)
        check("6b. and a key cannot be verified after resume",
              RecoveryMode.verify_invitation(key) is False)
    finally:
        # Never leave the site paused because of a test.
        RecoveryMode.resume()
        if was_paused:
            RecoveryMode.pause()

    if bad:
        print("\nRECOVERY GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the recovery key is minted only while paused, hashed at "
          "rest, verified, and expires.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())