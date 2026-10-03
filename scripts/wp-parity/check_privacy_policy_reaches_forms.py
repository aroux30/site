"""Guard: the privacy policy reaches the forms that collect personal data.

P0 "حریم خصوصی: اطلاع‌رسانی حریم خصوصی در فرم‌ها". WordPress links the
published policy page from every form that collects personal data. This project
had no setting, no endpoint, and no link — so a visitor who typed a phone number
into registration was never told what would happen to it.

The backend half is the easy half. This guard is mostly about the part that is
easy to ship and easy to leave dead: an endpoint with no consumer. That has
happened in this codebase before, repeatedly, and the shape of the failure is
always the same — a complete, working feature reachable only by curl.

So all four of these have to be true:

  1. a setting names the policy
  2. a public endpoint resolves it
  3. the storefront client reads that endpoint
  4. at least one form that collects personal data renders the link

And one thing that is easy to get wrong and looks right: the link has to be
*conditional*. WordPress's `get_the_privacy_policy_link()` returns an empty
string when no policy is published, and that is the contract — a form that links
to a 404 while asking for consent is worse than a form that says nothing.

    python scripts/wp-parity/check_privacy_policy_reaches_forms.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

DEFAULTS = BACKEND / "app" / "modules" / "settings" / "application" / "default_options.py"
SERVICE = BACKEND / "app" / "modules" / "settings" / "application" / "privacy_policy_service.py"
ROUTES = BACKEND / "app" / "modules" / "settings" / "api" / "routes.py"
CLIENT = FRONTEND / "lib" / "api" / "settings.ts"
NOTICE = FRONTEND / "components" / "privacy" / "privacy-policy-notice.tsx"
REGISTER = FRONTEND / "app" / "(store)" / "register" / "page.tsx"
COMMENTS = FRONTEND / "components" / "blog" / "blog-comments.tsx"

#: Forms that collect personal data, and therefore the ones that must mention it.
#: A name here is a claim that the form exists — the guard checks the render, not
#: the intent.
FORMS = (("registration", REGISTER), ("comment", COMMENTS))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _split_components(source: str) -> list[tuple[str, str]]:
    """Split a notice file into (name, body) for each top-level component.

    Split on the *declaration* of a top-level `export function` / `export const`
    at column zero, not on a name appearing anywhere: a body that mentions
    `PrivacyPolicyNotice` must not be read as if it were that component. Bodies
    are otherwise taken verbatim, so a component whose body contains a nested
    function is not cut in half.
    """
    marks = list(
        re.finditer(
            r"(?m)^export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)",
            source,
        )
    )
    out: list[tuple[str, str]] = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(source)
        out.append((mark.group(1), source[mark.end() : end]))
    return out


def main() -> int:
    failures: list[str] = []
    for path in (DEFAULTS, SERVICE, ROUTES, CLIENT, NOTICE):
        if not path.is_file():
            print("FAIL: %s does not exist" % path)
            return 1

    defaults = read(DEFAULTS)
    service = read(SERVICE)
    routes = read(ROUTES)
    client = read(CLIENT)
    notice = read(NOTICE)

    # 1. The setting.
    if "privacy.policy_page" not in defaults:
        failures.append(
            "no privacy.policy_page option is seeded, so an operator has no way to "
            "name the policy page"
        )

    # 2. The endpoint, public and ahead of the catch-all.
    if '"/public/privacy-policy"' not in routes:
        failures.append(
            "no /settings/public/privacy-policy route, so no form can read the policy"
        )
    else:
        # Declaration order, read from the source. FastAPI matches in order, so a
        # route declared below `/{key}` is captured by it and returns 404 for a
        # setting named "privacy-policy" — the exact symptom of a store with no
        # policy, on a store that has one.
        #
        # The catch-all is the *first* `/{key}` in the file, not any of them:
        # several routes use the pattern for their own key. Comparing against a
        # later occurrence would report the order correct on a file where the
        # privacy route sits below the first one.
        policy_at = routes.index('"/public/privacy-policy"')
        catch_all = routes.find('"/{key}"')
        if catch_all >= 0 and policy_at > catch_all:
            failures.append(
                "the privacy-policy route is declared after the /{key} catch-all, so "
                "FastAPI matches the catch-all first and every caller 404s"
            )
        if "PrivacyPolicyService" not in routes:
            failures.append(
                "the route does not call PrivacyPolicyService, so it cannot resolve "
                "anything even when reached"
            )

    # 3. Only a published, public page may be served. A draft is a document
    #    nobody consented to; a private page is one the operator hid.
    #
    #    Checked as two independent conditions, because writing them as one
    #    `if a or b:` is a choice about the source's shape and not about the
    #    behaviour — the split version is clearer and equally correct, and a
    #    guard that only accepts the combined form goes red on it.
    if "page.status != PageStatus.PUBLISHED" not in service:
        failures.append(
            "the service does not require the policy page to be published, so a "
            "draft can be linked from a consent form"
        )
    if "page.visibility != PageVisibility.PUBLIC" not in service:
        failures.append(
            "the service does not require the policy page to be public, so a hidden "
            "page is linked from a public form — which also leaks that it exists"
        )

    # 4. The storefront client. Checked as a *call*, not as a string: the URL
    #    appears once in this file, and a guard that greps for it is satisfied by
    #    a comment or a dead constant exactly as well as by the request. What
    #    matters is that the client actually issues the call.
    #
    #    Two halves, because one without the other is a shipped-but-dead chain:
    #    the definition (this file issues the request) and the consumption (the
    #    notice component calls it). Checking only the definition is what a first
    #    version of this gate did, and the sabotage proved why: with the notice
    #    no longer calling the API — a file that no longer compiles — the gate
    #    still printed PASS, because the request in `lib/api/settings.ts` was
    #    still there, answered by nobody.
    if "privacyPolicyApi" not in client:
        failures.append(
            "no frontend client reads the endpoint, so the backend half is reachable "
            "only by curl"
        )
    elif not re.search(r"apiClient\.get<[^>]*>\(\s*\n?\s*\"/settings/public/privacy-policy\"", client):
        failures.append(
            "privacyPolicyApi exists but never issues the request for "
            "/settings/public/privacy-policy, so it returns whatever the client "
            "defaults to and every form renders no link"
        )

    # 5. The component, and the conditional.
    if not notice:
        failures.append("there is no privacy-policy notice component")
    else:
        # Every exported component that renders a link has to guard on it, fetch
        # the policy and handle the failure — all three, checked per component.
        #
        # Per component, not per file, and that is the whole point. A guard that
        # counted occurrences across the file passed on a file where two of the
        # three components had stopped fetching: the third one still satisfied
        # the count. Each of these components fetches independently, so a count
        # is not a claim about any one of them.
        components = _split_components(notice)
        if not components:
            failures.append(
                "the notice file exports no component, so no form can render a link"
            )
        for name, body in components:
            if "policy.url" not in body:
                failures.append(
                    "%s renders no privacy-policy link at all" % name
                )
                continue
            if "if (!policy.url" not in body:
                failures.append(
                    "%s renders its link unconditionally, so on a store with no "
                    "published policy it links to a 404 — worse than saying "
                    "nothing, because the form is asking for consent" % name
                )
            # The call has to actually issue a GET. Counting the name is not
            # enough and this gate shipped that mistake once: the client object
            # is still referenced in a body that calls some other method on it,
            # so the name is present and nothing is fetched. Matched per
            # component, because the three of them fetch independently.
            if not re.search(r"privacyPolicyApi\s*\.\s*(?:get|fetch|load)\s*\(", body):
                called = re.search(r"privacyPolicyApi\s*\.\s*(\w+)\s*\(", body)
                if not called:
                    failures.append(
                        "%s renders a link but never calls privacyPolicyApi, so it "
                        "draws an empty policy: the request exists in "
                        "lib/api/settings.ts and is answered by nobody" % name
                    )
                else:
                    failures.append(
                        "%s calls privacyPolicyApi.%s() instead of a GET, so the "
                        "policy it renders is whatever the client defaults to — "
                        "and the form asks for consent on an empty string" % (name, called.group(1))
                    )
            elif ".catch(" not in body:
                failures.append(
                    "%s does not handle a failed lookup, so a policy endpoint "
                    "outage would surface as an unhandled rejection inside the "
                    "form the visitor is filling in" % name
                )

    # 6. The consumers. This is the assertion that catches the shipped-but-dead
    #    shape, and it is per-form: one wired form is not a wired feature.
    for label, path in FORMS:
        if not path.is_file():
            failures.append("the %s form (%s) does not exist" % (label, path))
            continue
        source = read(path)
        if "privacy-policy-notice" not in source:
            failures.append(
                "the %s form collects personal data and renders no privacy-policy "
                "notice; a visitor types a phone number or an email with nothing "
                "telling them what happens to it" % label
            )
        elif not re.search(r"<Privacy(?:PolicyNotice|Clause)\b", source):
            failures.append(
                "the %s form imports the notice but never renders it — an import "
                "with no call site is the dead half of this gap" % label
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d privacy-policy link(s) of the chain are missing." % len(failures))
        return 1
    print(
        "PASS: the policy is set, served, fetched, and rendered in both forms that "
        "collect personal data."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
