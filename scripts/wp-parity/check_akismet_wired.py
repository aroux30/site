"""Akismet must be a check AND a feedback loop, both behind a real guard.

Two things this file exists to stop, both of which happened while building it:

* **A seam that cannot be called.** The transport was declared as a method
  (`post_form`) and invoked as a bare callable, so every request raised
  `TypeError` — swallowed by a broad `except` into "no opinion". The feature
  was installed, the option was readable, and *nothing was ever sent*. A gate
  that only checked the strings in this file passed the whole time.
* **A loop attached to one of two paths.** `bulk_moderate` does not call
  `moderate_comment`, so wiring feedback into the single-comment path leaves
  the highest-volume source of ground truth — a moderator clearing a spam wave
  — silently unreported.

So the checks are about reachability and ordering, not about the presence of a
class name:

* the transport is invoked through the same method the seam declares;
* the key guard runs *before* the client is built, so an unconfigured site —
  the default — performs no work;
* "no opinion" is `None`, and the only three documented answers are mapped, with
  `undefined` deliberately not mapped to ham;
* a failure is `None`, never `True`: failing closed would let one slow third
  party decide every comment on the store;
* the check is advisory — it can hold a comment the local engine let through,
  but it can never clear one;
* feedback is wired into BOTH moderation paths, after their commits.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # scripts/wp-parity/ -> site/
BACKEND = ROOT / "backend"

problems: list[str] = []


def require(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {'ok' if ok else 'FAIL'}")
    if not ok:
        problems.append(f"{label}{': ' + detail if detail else ''}")


def read(rel: str) -> str:
    return (BACKEND / rel).read_text(encoding="utf-8")


client = read("app/modules/blog/application/akismet_client.py")
feedback = read("app/modules/blog/application/akismet_feedback.py")
service = read("app/modules/blog/application/comment_service.py")
spam = read("app/modules/blog/application/spam_filter.py")

# --- 1. the transport seam is actually callable ------------------------------
require(
    "seam: the protocol declares post_form",
    re.search(r"async def post_form\(", client) is not None,
)
# The failure this catches: invoked as a callable, so every real request raises
# TypeError and the feature silently sends nothing.
require(
    "seam: it is called through .post_form, not as a bare callable",
    len(re.findall(r"await self\._transport\.post_form\(", client)) >= 2,
    "calling the transport directly raises TypeError on every request; the "
    "broad except turns that into 'no opinion', so a configured site sends "
    "nothing and still looks installed",
)
require(
    "seam: no bare call of the transport remains",
    re.search(r"await self\._transport\(", client) is None,
)
require(
    "seam: the default transport implements the same method",
    re.search(
        r"class HttpxTransport:.*?async def post_form\(", client, re.S
    ) is not None,
    "a default that does not implement the seam fails only in production",
)
require(
    "seam: the type annotation names the protocol, not Callable",
    "self._transport: Transport" in client,
)

# --- 2. no key, no work ------------------------------------------------------
check_fn = re.search(
    r"async def check_comment\(.*?(?=\n    async def submit_feedback)", client, re.S
)
check_src = check_fn.group(0) if check_fn else ""
require("guard: check_comment exists", bool(check_src))
key_at = check_src.find("api_key")
early = check_src.find("return None")
require(
    "guard: an empty key returns before anything is built",
    key_at != -1 and early != -1 and key_at < early,
    "without the early return an unconfigured site — the default — pays for a "
    "client per comment",
)
require(
    "guard: a missing site URL also short-circuits (Akismet matches on it)",
    re.search(r"if not blog_url:\s*\n\s*return None", check_src) is not None,
)
require(
    "guard: whitespace-only key counts as no key",
    re.search(r"api_key\.strip\(\)", check_src) is not None,
)

# --- 3. the three answers, and only those ------------------------------------
require(
    "verdict: 'undefined' is not mapped to ham",
    re.search(r'if verdict not in \(SPAM, HAM\):', client) is not None,
    "Akismet answers true / false / undefined, and undefined means it declines "
    "to classify — reading it as ham starts letting spam through",
)
require(
    "verdict: a non-200 is no opinion, not spam",
    re.search(r"if status != 200:[\s\S]{0,120}return None", client) is not None,
)
for exc in ("asyncio.TimeoutError", "OSError"):
    require(
        f"failure: {exc} yields no opinion",
        re.search(rf"except \([^)]*{exc}[^)]*\)[^:]*:[^!]*?return None", check_src)
        is not None,
        "failing closed would let one slow third party hold every comment",
    )
require(
    "failure: an unexpected error is caught rather than reaching the caller",
    "except Exception" in check_src,
)
require("verdict: no opinion is None, not a falsy verdict", "-> AkismetVerdict | None" in check_src)

# --- 4. the check is advisory -------------------------------------------------
local_at = service.index("score_comment(")
remote_at = service.index("_akismet_opinion(")
require(
    "service: the local engine decides first",
    local_at < remote_at,
    f"local@{local_at} after remote@{remote_at}",
)
require(
    "service: Akismet can hold a comment the local engine let through",
    re.search(
        r"if remote is not None and remote\.is_spam and status == CommentStatus\.APPROVED:",
        service,
    )
    is not None,
)
require(
    "service: Akismet can NEVER clear a comment",
    "remote.is_spam" in service
    and not re.search(r"remote\.is_spam\s*==\s*False|not remote\.is_spam", service),
    "clearing on a service verdict would publish spam whenever the service is "
    "wrong or compromised",
)
require(
    "service: the opinion method is called, not inlined",
    "await self._akismet_opinion(" in service,
)
opinion = re.search(r"async def _akismet_opinion\(.*?\n(?=\n    async def )", service, re.S)
op_src = opinion.group(0) if opinion else ""
require(
    "service: the key is read before the client is constructed",
    re.search(r"api_key = await SiteOptionsService\.get[\s\S]*?return None[\s\S]*?"
              r"client: AkismetClient", op_src) is not None,
)
require(
    "service: an exception becomes no opinion, never a failed post",
    "return None" in op_src and "except Exception" in op_src,
)
require(
    "service: the injectable seam exists for tests",
    'getattr(self, "_akismet", None)' in op_src,
)

# --- 5. the feedback loop ----------------------------------------------------
require("loop: the module exists", len(feedback) > 1500, f"{len(feedback)} chars")
require(
    "loop: it reads the key from a site option, not an env secret",
    "SiteOptionsService.get" in feedback
    and "API_KEY_OPTION" in feedback
    and 'API_KEY_OPTION = "spam_akismet_api_key"' in client,
    "an operator-editable option beside the media_watermark_* ones; the "
    "constant is imported rather than re-spelled, so the name is checked at "
    "its definition",
)
require(
    "loop: no key means no submission",
    re.search(r"if not api_key[\s\S]{0,120}return False", feedback) is not None,
)
require(
    "loop: a missing site URL refuses rather than posting an empty blog",
    re.search(r"if not blog_url:[\s\S]{0,160}return False", feedback) is not None,
)
require(
    "loop: spam and ham go to different endpoints",
    "submit-spam" in client and "submit-ham" in client
    and 'if is_spam else f"{base}submit-ham"' in client,
)
require(
    "loop: only a spam decision is trained as spam — a trash is not",
    re.search(r"_SPAM_DECISIONS = \(CommentStatus\.SPAM,\)", feedback) is not None,
    "an operator trashes for tone as often as for adverts; reporting every "
    "trash teaches the service to distrust ordinary speech",
)
# The `return False` sits past any fixed character window, behind a multi-line
# log call whose continuation lines are indented deeper than the handler body.
# What matters is that the handler returns False rather than re-raising, so the
# handler block is taken from its `except` to the next top-level statement.
_ex_at = feedback.index("except Exception")
_ex_block = feedback[_ex_at : feedback.index("\n\n", _ex_at)]
require(
    "loop: a rejected submission is a lost signal, not a failure",
    "return False" in _ex_block,
    f"handler={_ex_block[:160]!r}",
)
require(
    "loop: and none of them re-raises",
    not re.search(r"except [\s\S]{0,400}?raise", feedback),
)

# --- 6. wired into BOTH moderation paths, after the commit -------------------
mod = re.search(
    r"async def moderate_comment\(.*?\n(?=\n    async def get_comment)", service, re.S
)
mod_src = mod.group(0) if mod else ""
commit_at = mod_src.find("await self.db.commit()")
fb_at = mod_src.find("report_moderation")
require("single: moderate_comment feeds the loop", fb_at != -1)
require(
    "single: and does so after the commit",
    commit_at != -1 and fb_at > commit_at,
    "before the commit the row is not yet the decision that was made",
)
require(
    "single: a feedback failure cannot fail the moderation",
    re.search(r"akismet_feedback_skipped", mod_src) is not None,
)

bulk = re.search(
    r"async def bulk_moderate\(.*?\n(?=\n    async def delete_comment)", service, re.S
)
bulk_src = bulk.group(0) if bulk else ""
require(
    "bulk: bulk_moderate feeds the loop too",
    "report_moderation" in bulk_src,
    "bulk_moderate does not call moderate_comment, so wiring only the single "
    "path leaves the highest-volume ground truth unreported",
)
require(
    "bulk: the rows are collected and reported after the batch commit",
    "moderated: list[BlogComment] = []" in bulk_src
    and bulk_src.find("report_moderation") > bulk_src.find("await self.db.commit()"),
)
require(
    "bulk: not inside the per-row try that swallows failures",
    re.search(
        r"for comment in moderated:[\s\S]{0,220}?except Exception", bulk_src
    )
    is not None,
    "inline submissions would be reported as failed moderations",
)
require(
    "bulk: a delete wave sends nothing — there is no comment left to describe",
    re.search(r'if action == "delete":\s*\n\s*await self\.db\.delete\(comment\)\s*\n'
              r"\s*else:\s*\n\s*comment\.status = target\s*\n\s*moderated\.append",
              bulk_src)
    is not None,
)

# The one-click moderator links go through moderate_comment, so they are covered
# — assert that rather than assume it, because it is the highest-value single
# training signal the service gets.
routes = read("app/modules/blog/api/routes.py")
require(
    "links: the email one-click path goes through moderate_comment",
    re.search(r"CommentService\(db\)\.moderate_comment\(", routes) is not None,
)

# --- 7. the local engine is still there, and still the fallback --------------
require(
    "local: spam_filter still exists and still scores",
    "def score_comment(" in spam and "SPAM_SCORE_THRESHOLD" in spam,
    "Akismet is advisory; without the local engine a site with no key has no "
    "filter at all",
)
require(
    "local: the local engine is consulted first in the create path",
    service.index("score_comment(") < service.index("_akismet_opinion("),
)

# --- 8. the option is reachable, and reachable safely -----------------------
# A key nobody can set is a key nobody sets: the settings card is the only place
# an operator edits site options, so the feature has to appear there.
card = (ROOT / "frontend/components/admin/content-settings-card.tsx").read_text(
    encoding="utf-8"
)
for key in ("spam_akismet_api_key", "spam_akismet_api_url"):
    require(f"admin: the settings card exposes {key}", key in card)
require(
    "admin: the card says an empty key is a supported state",
    re.search(r"spam_akismet_api_key[\s\S]{0,700}?خالی\s*=", card) is not None,
    "without the wording an operator reads an empty field as a missing setting "
    "rather than as WordPress's own no-key behaviour",
)

# The save persists `values[key] || null` for every option, so a save taken
# while `values` is still empty writes null across the whole card. The key is
# the one field here whose loss nobody notices until spam arrives.
require(
    "admin: a failed or in-flight load cannot wipe the settings",
    "loadFailed" in card
    and re.search(r"if \(loading \|\| loadFailed\)[\s\S]{0,200}?return;", card)
    is not None,
    "a save after a failed fetch writes null to every option — including the "
    "Akismet key, which is then silently absent",
)
require(
    "admin: the save button reflects that guard",
    re.search(r"disabled=\{saving \|\| loading \|\| loadFailed\}", card) is not None,
)

print("\n  (row-level behaviour: .p1-tests/akismet_feedback_test.py — 32 checks)")

if problems:
    print("\nAKISMET WIRING GAPS:")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)
print("\nPASS: the transport is callable and invoked through its seam, the key "
      "guard runs before any work, 'undefined' is not ham, a failure is no "
      "opinion rather than spam, the check is advisory, and both the single and "
      "bulk moderation paths feed the loop after their commits.")