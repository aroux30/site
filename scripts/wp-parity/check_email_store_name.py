"""Guard: one store name, and every email path reads it from there.

P0 "ایمیل: نام فروشگاه در ایمیل‌ها". Four transactional templates read the
operator's name from the settings; three generic send paths read it from
``SMTP_FROM_NAME`` in the environment; the admin preview read the settings blob
a third time by hand. Three definitions of one question, and a store that showed
two different names in the same customer's inbox.

The environment is the wrong source and the reason is specific, not stylistic: it
cannot be changed from the panel, it lives in the deployment rather than in the
store's settings, and an operator who renames their shop has no reason to know a
second name exists in a container they do not edit.

The live assertion is backend/scripts/verify_email_store_name.py. This guard is
the one that runs without a database, and its job is the part a live check
cannot catch: **the next** call site someone adds. A new email path wired to the
SMTP config passes every test that exists today and reintroduces the split.

    python scripts/wp-parity/check_email_store_name.py
"""

from __future__ import annotations

import ast
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
BACKEND = ROOT / "backend" / "app"

RESOLVER = BACKEND / "modules" / "notifications" / "application" / "store_name.py"
EMAIL = BACKEND / "modules" / "notifications" / "application" / "email_service.py"
NOTIFY = BACKEND / "modules" / "notifications" / "application" / "notification_service.py"
TASKS = BACKEND / "modules" / "notifications" / "application" / "tasks.py"
TEMPLATE_SVC = (
    BACKEND / "modules" / "notifications" / "application" / "email_template_service.py"
)
RULES = BACKEND / "modules" / "automation" / "application" / "rules_engine.py"
ADMIN_ROUTES = BACKEND / "modules" / "settings" / "api" / "routes.py"

#: Every module allowed to render an email shell. Checked as a list rather than a
#: search because the property is about *all* of them: a new path not on this list
#: has not been looked at, and a guard that only checks the listed ones says
#: nothing about it.
EMAIL_PATHS = (
    ("email_service", EMAIL),
    ("notification_service", NOTIFY),
    ("notification tasks", TASKS),
    ("email template service", TEMPLATE_SVC),
    ("automation rules engine", RULES),
    ("settings admin routes", ADMIN_ROUTES),
)

#: The one expression that must not appear in an email path. Matched as a call
#: rather than as a substring so `from_name` used for the envelope — which is a
#: different field with a legitimately different source — does not trip it.
BAD_NAME_SOURCE = re.compile(r"_wrap_html\(\s*[^,]*from_name", re.S)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    failures: list[str] = []
    if not RESOLVER.is_file():
        print("FAIL: %s does not exist, so there is no single source to point at" % RESOLVER)
        return 1
    resolver = read(RESOLVER)
    tree = ast.parse(resolver)

    # 1. The resolver has to exist and be the one place that reads the options.
    if "async def resolve_store_name(" not in resolver:
        failures.append(
            "there is no resolve_store_name, so every consumer will keep inventing "
            "its own reader and they will drift apart again"
        )
    else:
        # Parsed, not grepped. The two options it reads are the property, and this
        # module's docstring names both in prose, so a substring search is
        # satisfied by the documentation of the behaviour being checked.
        #
        # What matters is the two module-level *assignments*. A string that only
        # appears inside a docstring is prose; a string that is the value of a
        # module constant is code. Reading assignments and not bare constants is
        # what makes the difference — the docstring mentions ``store.identity``
        # as prose and the constant is assigned the same characters.
        assigned = {
            node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and any(
                isinstance(t, ast.Name) and t.id.startswith(
                    ("STORE_IDENTITY_OPTION", "BLOGNAME_OPTION")
                )
                for t in node.targets
            )
        }
        for required in ("store.identity", "blogname"):
            if required not in assigned:
                failures.append(
                    "resolve_store_name no longer reads %r, so a store that only "
                    "set one of them gets a different name depending on which email "
                    "arrives" % required
                )
        # Both halves of the fallback, and read from the *syntax tree* rather
        # than the text: this module's own docstring names SMTP_FROM_NAME twice,
        # so a substring search is satisfied by the prose that describes the
        # behaviour it is checking for. That is the same shape as the
        # `ipv4_mapped` case in check_comment_ip_retention — the name is in the
        # file, the behaviour is not.
        code_strings = {
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        code_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        code_attrs = {
            n.attr
            for n in ast.walk(tree)
            if isinstance(n, ast.Attribute)
        }
        if "SMTP_FROM_NAME" not in code_attrs:
            failures.append(
                "the resolver has no environment fallback, so a deployment with an "
                "empty settings table prints the default instead of the name the "
                "operator configured in the container"
            )
        # A Name, not a string: DEFAULT_STORE_NAME is a module constant, so the
        # check for it is a name reference. Looking for the literal instead would
        # never match, and the guard would be red on a healthy file.
        if "DEFAULT_STORE_NAME" not in code_names:
            failures.append(
                "the resolver has no final fallback, so a deployment with neither a "
                "setting nor SMTP_FROM_NAME raises instead of rendering an email"
            )

    # 2. No email path may take its name from the SMTP config.
    for label, path in EMAIL_PATHS:
        if not path.is_file():
            failures.append("the %s (%s) does not exist" % (label, path.name))
            continue
        source = read(path)
        # The call itself, with the name argument inlined. A module that builds
        # the name in a variable first would slip past; that is checked below by
        # requiring every path to go through the shared helper instead.
        for m in BAD_NAME_SOURCE.finditer(source):
            snippet = " ".join(m.group(0).split())[:80]
            failures.append(
                "the %s renders an email header from the SMTP config (%s). That is "
                "the environment's name, not the store's — an operator who renamed "
                "their shop in Settings gets the old name here."
                % (label, snippet)
            )

    # 3. And every path must actually go through the resolver for the name. This
    #    is the assertion that catches the *next* call site, which no live check
    #    can: a new module with its own `_wrap_html(name, ...)` would render
    #    correctly in isolation and be the third definition.
    #
    #    `_wrap_html` itself is the right function to call — it is the renderer,
    #    not a second source of the name. What must not appear is a *name*
    #    argument that is not the shared one, so the check is on the argument,
    #    not on the call.
    if "async def wrap_html_for_store(" not in read(EMAIL):
        failures.append(
            "email_service has no wrap_html_for_store, so the send paths have "
            "nothing shared to delegate to"
        )
    RESOLVED_NAME = re.compile(
        r"_wrap_html\(\s*(?:await\s+_operator_store_name\(db\)"
        r"|await\s+resolve_store_name\(db\)"
        r"|store_name\b"
        r"|name\b)",
        re.S,
    )
    for label, path in EMAIL_PATHS:
        if not path.is_file() or path == EMAIL:
            continue
        source = read(path)
        for m in re.finditer(r"_wrap_html\(", source):
            call = source[m.start() : m.start() + 200]
            if not RESOLVED_NAME.match(call):
                snippet = " ".join(call.split())[:70]
                failures.append(
                    "the %s renders an email header with a name that did not come "
                    "from the shared resolver (%s…) — so its header is whatever "
                    "the caller happened to pass" % (label, snippet)
                )

    # 4. The admin preview's reader must delegate, not re-implement. It is the one
    #    place a second definition survived the first fix, and it is invisible
    #    from the send paths.
    svc = read(TEMPLATE_SVC)
    # Parsed. The alias's own docstring explains that it delegates over
    # ``resolve_store_name`` — in prose — so a substring search over the function
    # is satisfied by the sentence describing the behaviour being checked, and a
    # function that stopped delegating stays green.
    if "async def _operator_store_name(" in svc:
        try:
            svc_tree = ast.parse(svc)
        except SyntaxError:
            failures.append(
                "the template service does not parse, so nothing about it can be "
                "checked"
            )
            svc_tree = None
        if svc_tree is not None:
            fn = next(
                (
                    n
                    for n in ast.walk(svc_tree)
                    if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == "_operator_store_name"
                ),
                None,
            )
            if fn is None:
                failures.append(
                    "the template service no longer defines _operator_store_name, so "
                    "the admin preview's store name has no single source"
                )
            else:
                called = {
                    n.func.id
                    for n in ast.walk(fn)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                } | {
                    n.func.attr
                    for n in ast.walk(fn)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                }
                if "resolve_store_name" not in called:
                    failures.append(
                        "the template service reads the store name itself instead of "
                        "delegating to resolve_store_name — a second definition of "
                        "the same question, which is how the four send paths came to "
                        "disagree"
                    )

    # 5. And the preview's own store_name must be the resolved one, not a sample.
    #    Accepted by the argument check above, so it has to be checked here or a
    #    module that assigns `store_name = "فروشگاه نمونه"` is indistinguishable
    #    from one that resolved it. Read from the dict literal in the function,
    #    not from its text: this docstring names _operator_store_name in prose as
    #    well, so a substring search cannot tell the two apart.
    preview_fn = None
    if svc_tree is not None:
        preview_fn = next(
            (
                n
                for n in ast.walk(svc_tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "preview"
            ),
            None,
        )
    if preview_fn is None:
        failures.append(
            "the template service has no preview function, so the store name the "
            "operator edits against is not checked at all"
        )
    else:
        takes_db = "db" in {
            a.arg
            for a in (
                list(preview_fn.args.args) + list(preview_fn.args.kwonlyargs)
            )
        }
        if not takes_db:
            failures.append(
                "the admin preview takes no session, so it cannot resolve the store "
                "name and must be reading it from somewhere else"
            )
        sample_value = None
        for node in ast.walk(preview_fn):
            if (
                isinstance(node, ast.Dict)
                and node.keys
                and any(
                    isinstance(k, ast.Constant) and k.value == "store_name"
                    for k in node.keys
                )
            ):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value == "store_name":
                        sample_value = v
        if sample_value is None:
            failures.append(
                "the admin preview declares no store_name sample, so the header it "
                "shows the operator is undefined"
            )
        elif not (
            isinstance(sample_value, ast.Await)
            or (
                isinstance(sample_value, ast.Call)
                and isinstance(sample_value.func, ast.Name)
                and sample_value.func.id == "_operator_store_name"
            )
        ):
            failures.append(
                "the admin preview fills store_name with %s rather than the resolved "
                "name, so the operator edits against a header the customer will "
                "never see"
                % ast.dump(sample_value)[:60]
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d email store-name link(s) are broken." % len(failures))
        return 1
    print(
        "PASS: one resolver, and every email path reads the store name through it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
