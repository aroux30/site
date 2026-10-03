"""Guard: the store name the operator sets has to be read, not just written.

P0 "تنظیمات: مشخصات فروشگاه". `store.identity` was written by the settings
screen and read by nothing — no public endpoint returned it, so the header,
the footer, the SEO metadata and all four transactional emails carried a
string no operator could change.

This asserts the whole chain rather than one link, because the chain is what
was broken: a setting can be stored, exposed over an endpoint, and still never
reach a single pixel if the last hop is missing.

    python scripts/wp-parity/check_store_identity_reaches.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

# The messages carry Persian, and a cp1252 Windows console raises
# UnicodeEncodeError on them — which reads as the guard crashing rather than
# reporting what it found.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]
BRANDING_ROUTE = ROOT / "backend" / "app" / "modules" / "settings" / "api" / "routes.py"
EMAIL_SERVICE = ROOT / "backend" / "app" / "modules" / "notifications" / "application" / "email_service.py"
TEMPLATE_SERVICE = (
    ROOT / "backend" / "app" / "notifications" / "application" / "email_template_service.py"
    if (ROOT / "backend" / "app" / "notifications").exists()
    else ROOT / "backend" / "app" / "modules" / "notifications" / "application" / "email_template_service.py"
)
LAYOUT = ROOT / "frontend" / "app" / "layout.tsx"
SITE_CARD = ROOT / "frontend" / "components" / "admin" / "site-identity-card.tsx"
HEADER = ROOT / "frontend" / "components" / "layout" / "header.tsx"
FOOTER = ROOT / "frontend" / "components" / "layout" / "footer.tsx"

HARD_CODED_STORE_NAME = "فروشگاه آنلاین"
TEMPLATE_DEFAULT = "فروشگاه اینترنتی"  # the email templates' historical default


def read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _response_dict(src: str, function_name: str) -> str:
    """The body of the dict a route returns, or "" when it cannot be found.

    Assembled without escape sequences on purpose: a ``\\n`` written into this
    file's own source turned into a real newline and left an unterminated
    string, which is a confusing way to discover a quoting mistake.
    """
    try:
        segment = src[src.index(function_name) :]
    except ValueError:
        return ""
    open_brace = segment.index("{", segment.index("return"))
    depth = 0
    for i in range(open_brace, len(segment)):
        ch = segment[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return segment[open_brace : i + 1]
    return ""


def _function_body(src: str, signature_fragment: str) -> str:
    """The text of one top-level function, and nothing after it.

    Slicing from the signature to the end of the file is the bug this replaces:
    every later function in the module counts as evidence about the one being
    checked. In `store_name.py` the read is `resolve_store_name`, and the string
    `store.identity` appears in `_name_from_identity` below it — so deleting the
    read left the text present and this gate reported the setting as read. The
    same file held the honest version of this lesson in a comment; it just was
    not applied to the slicing.

    Cuts at the next line that starts a top-level `def`/`async def`/`class`/
    `@decorator`, which is where the function ends in any PEP8-formatted source.
    """
    start = src.index(signature_fragment)
    nxt = re.search(
        r"(?m)^(?:@|async def |def |class )", src[start + len(signature_fragment) :]
    )
    end = start + len(signature_fragment) + (nxt.start() if nxt else len(src))
    return src[start:end]


def main() -> int:
    failures: list[str] = []

    # 1. The public endpoint must expose the name, or the storefront cannot
    #    reach it however clever the frontend is.
    route = read(BRANDING_ROUTE)
    # Scoped to the returned dict, not to the file. A substring check over the
    # whole module passed while the key had been removed from the response,
    # because the name still appeared in the helper's docstring and in the JSON
    # key it parses — so dropping the field was invisible.
    if '"store_name"' not in _response_dict(route, "async def get_public_branding"):
        failures.append(
            "the public branding endpoint does not return store_name, so the "
            "storefront has nothing to read"
        )
    # Scoped to the resolver's code, past its docstring: the prose above it
    # names store.identity too, so a file-level check could not tell whether
    # anything still reads it.
    # Each reader is checked in its own function. An earlier version asked only
    # whether the module mentioned store.identity, and when the endpoint's read
    # was removed the guard stayed green — the email resolver still read the
    # same key, so the substring was still there. Both ends of the chain have to
    # be broken for the setting to be dead.
    readers = {
        "the public branding endpoint": (route, "async def _public_store_name"),
        "the email template resolver": (
            read(TEMPLATE_SERVICE),
            "async def _operator_store_name",
        ),
    }
    # A third reader, added by the P0 store-identity work: the resolver was
    # lifted out of the template service into its own module so the paths with
    # no session (a preview, a health check) could call it too. That move is an
    # improvement, and this gate would have called it a regression by name.
    # The alternative — pointing the check at whichever function exists today —
    # would quietly stop watching the other: a later edit that restored an
    # unread dead copy in the template service would pass. So both are checked
    # and a gate that finds neither still fails.
    store_name_module = ROOT / "backend" / "app" / "modules" / "notifications" / "application" / "store_name.py"
    lifted = store_name_module.is_file()
    if lifted:
        readers["the shared store-name resolver"] = (
            read(store_name_module),
            "async def resolve_store_name",
        )
    for label, (src, function_name) in readers.items():
        # The template-service copy is optional only once the resolver has been
        # lifted: then the other reader is the live one and its absence is the
        # move, not a break. If the function is missing *and* the module was
        # never added, there is no reader at all and this has to fail.
        if (
            lifted
            and function_name == "async def _operator_store_name"
            and function_name not in src
        ):
            continue
        try:
            body_of = _function_body(src, function_name)
        except ValueError:
            body_of = ""
        # Past the docstring: the prose above each function names the key too.
        body_of = re.sub(r'"""[\s\S]*?"""', "", body_of, count=1)
        # A thin alias is a live reader, not a break. `_operator_store_name` was
        # reduced to a one-line delegation once the walk moved to
        # store_name.py, and this gate called that a dead path — which is the
        # mirror image of its own bug: a check that insists on reading the key
        # inside one function cannot tell a delegation from a break. So follow
        # the call instead: a body that hands the work to the module holding
        # `store.identity` still reaches the setting.
        #
        # Both forms of the read are accepted — the literal key, and the
        # constant `store_name.py` reads it through — but only when the *call*
        # is there. Naming a constant is not reading a setting, and an earlier
        # version of this block checked the name: with
        # `SiteOptionsService.get(db, STORE_IDENTITY_OPTION)` deleted, the
        # constant was still nearby and the gate passed on a store whose name
        # had fallen back to the environment. Same shape as the guard that read
        # `privacyPolicyApi` instead of `privacyPolicyApi.get()`.
        if "store.identity" in body_of:
            continue
        if re.search(
            r"SiteOptionsService\.\w+\([^)]*STORE_IDENTITY_OPTION", body_of
        ):
            continue
        if re.search(r"(?<!def )\bresolve_store_name\s*\(", body_of):
            continue
        failures.append(
            "%s never reads store.identity — the key the settings screen "
            "writes is still read by nothing on that path" % label
        )

    # 2. The email templates must take it as an argument.
    email = read(EMAIL_SERVICE)
    if "def default_email_templates(" not in email:
        failures.append(
            "default_email_templates() takes no store name, so the templates "
            "cannot carry the operator's"
        )
    elif "store_name" not in email.split("def default_email_templates(")[1][:600]:
        failures.append("default_email_templates does not use its store_name argument")
    # The default may appear twice: once as the fallback expression, once in
    # the docstring that explains why it exists. Anything else is a template
    # that still prints the placeholder, which is the original bug.
    # Counted where it is actually passed to the wrapper, not where the literal
    # appears. An earlier version stripped every string containing the default,
    # which removed exactly the templates it was supposed to catch — so
    # replacing a template with the placeholder again still passed.
    #
    # Two occurrences are legitimate: the fallback expression and the docstring
    # that explains it. Every other one is a template printing the placeholder.
    email_code = re.sub(r'"""[\s\S]*?"""', "", email)
    email_leftover = 0
    for line in email_code.splitlines():
        if TEMPLATE_DEFAULT not in line:
            continue
        if "or " in line and line.rstrip().endswith('"'):
            continue  # the fallback: name = (store_name or "") or "<default>"
        email_leftover += 1
    if email_leftover:
        failures.append(
            "%d template line(s) still print %r instead of the operator's name"
            % (email_leftover, TEMPLATE_DEFAULT)
        )

    # 3. The resolver must be wired where the templates are looked up.
    templates = read(TEMPLATE_SERVICE)
    if "_operator_store_name" not in templates:
        failures.append(
            "the email template service never resolves the store name, so the "
            "templates keep their hardcoded one"
        )
    elif "default_email_templates(await _operator_store_name(db))" not in templates:
        failures.append(
            "the template lookup does not pass the resolved store name"
        )

    # 4. The frontend chrome must consume it. A hardcoded name left in the
    #    header or footer is the bug itself, whatever the backend does.
    for path, label in ((LAYOUT, "app/layout.tsx"), (HEADER, "header.tsx"), (FOOTER, "footer.tsx")):
        src = read(path)
        if not src:
            failures.append(f"{label} is missing")
            continue
        # Allowed: the SEO keywords, which describe the category rather than
        # the brand — substituting the store's name into them would make the
        # page rank for its own name and nothing else — and the fallbacks that
        # an unset setting resolves to. Anything else is the bug.
        allowed = src.count(HARD_CODED_STORE_NAME) - src.count(
            '|| "%s"' % HARD_CODED_STORE_NAME
        ) - src.count('= "%s";' % HARD_CODED_STORE_NAME)
        leftover = 0
        for line in src.splitlines():
            if HARD_CODED_STORE_NAME not in line:
                continue
            stripped = line.strip()
            if "||" in line or "= " in line or line.strip().startswith("*"):
                continue  # a fallback or a comment
            if stripped == '"%s",' % HARD_CODED_STORE_NAME:
                continue  # an SEO keyword: the category, not the brand
            leftover += 1
        if leftover:
            failures.append(
                "%s hardcodes %r in %d place(s) that are not a fallback, so the "
                "operator's name never reaches the page"
                % (label, HARD_CODED_STORE_NAME, leftover)
            )

    layout = read(LAYOUT)
    if "store_name" not in layout:
        failures.append(
            "the root layout does not read store_name, so every tab title and "
            "search result still says the default"
        )
    # Reading the value is not enough if it is then discarded: the original
    # shape was `const name = "فروشگاه آنلاین";` beside a fetch that did read
    # the setting, and the string check passed while no title used it.
    if re.search(r'const name =\s*"', layout):
        failures.append(
            "the root layout reads store_name and then discards it, so the "
            "operator's name reaches no title"
        )

    # 5. The static front page, the other half of "what the site presents".
    #    The resolver on the backend was complete; what was missing was any way
    #    to set the two keys, which is the same shape of gap as the ones above.
    card = read(SITE_CARD)
    if not card:
        failures.append("the site identity card is missing")
    else:
        # Reading a value is not setting it: the original card loaded both keys
        # and could not write either, so the check has to look at the save path.
        if "show_on_front" not in card or "page_on_front" not in card:
            failures.append(
                "the settings screen cannot set show_on_front/page_on_front, so the "
                "front-page branch the resolver serves is unreachable"
            )
        elif not (
            "siteOptionsApi.set(KEYS.showOnFront" in card
            or "[KEYS.showOnFront," in card
        ):
            failures.append(
                "the settings screen reads show_on_front but never writes it, so "
                "picking a front page changes nothing"
            )
        elif "[KEYS.pageOnFront," not in card:
            failures.append(
                "the settings screen never writes page_on_front, so the chosen "
                "page is not the one the resolver looks up"
            )
        elif "listPages" not in card:
            failures.append(
                "the front-page picker never lists the published pages, so there is "
                "nothing to choose and only a raw slug could be typed"
            )
        else:
            # A draft must not be offered: the resolver asks for published only,
            # so pinning one would produce a setting that silently does nothing.
            if '"published"' not in card and "'published'" not in card:
                failures.append(
                    "the front-page picker does not restrict the list to published "
                    "pages, so a draft could be pinned and then ignored"
                )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d link(s) of the chain are missing." % len(failures))
        return 1

    print(
        "PASS: the store name reaches the storefront, and the settings screen "
        "can set both the branding and the front page."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())