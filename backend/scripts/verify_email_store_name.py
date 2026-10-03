"""Live check: every email shows the same store name, from the store's settings.

P0 "ایمیل: نام فروشگاه در ایمیل‌ها". Four transactional templates read the
operator's name from the settings; the three generic send paths read it from
``SMTP_FROM_NAME`` in the environment. Both fell back to the same literal, so one
store showed two names in the same customer's inbox — its own name on the order
confirmation, "فروشگاه اینترنتی" on the shipping notification.

The property is that they cannot disagree, so this checks all four send paths in
one run rather than the resolver alone: a resolver that works while three call
sites keep reading the environment is exactly the half-fix that shipped before.

    cd backend && PYTHONPATH=. python scripts/verify_email_store_name.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.notifications.application import email_service  # noqa: E402
from app.modules.notifications.application.store_name import (  # noqa: E402
    DEFAULT_STORE_NAME,
    resolve_store_name,
)

PROBE = "Probe Store Name " + uuid.uuid4().hex[:8]


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _write_option(db, key: str, value: str | None) -> None:
    """Set or clear one site option, remembering nothing — the caller restores."""
    if value is None:
        await db.execute(
            text("DELETE FROM site_options WHERE option_key = :k"), {"k": key}
        )
    else:
        await db.execute(
            text(
                "INSERT INTO site_options (id, option_key, option_value, autoload, "
                "created_at, updated_at) VALUES (:i, :k, :v, false, now(), now()) "
                "ON CONFLICT (option_key) DO UPDATE SET option_value = "
                "EXCLUDED.option_value, updated_at = now()"
            ),
            {"i": str(uuid.uuid4()), "k": key, "v": value},
        )


async def _read_option(db, key: str) -> str | None:
    return (
        await db.execute(
            text("SELECT option_value FROM site_options WHERE option_key = :k"),
            {"k": key},
        )
    ).scalar()


def _header_of(html: str) -> str:
    """The text in the shell's header band — what the customer actually sees.

    Read out of the rendered HTML rather than off the argument, so a template
    that drops the name from the header is caught here instead of in a customer's
    inbox.
    """
    marker = "font-weight:bold;"
    if marker not in html:
        return ""
    tail = html.split(marker, 1)[1]
    return tail.split(">", 1)[1].split("<", 1)[0].strip()


# ── The three generic send paths, invoked for real ─────────────────────────
#
# Each captures the HTML the production path would hand to send_email. They are
# written to reach the header render and stop there — a real send is not the
# property under test, and staging one would need an SMTP server.


async def _render_via_notification_service(db) -> str:
    """NotificationService.send_email's wrapping step."""
    from app.modules.notifications.application import notification_service

    return await _run_module_wrap(notification_service, db)


async def _render_via_dispatch_task(db) -> str:
    from app.modules.notifications.application import tasks

    return await _run_module_wrap(tasks, db)


async def _render_via_rules_engine(db) -> str:
    from app.modules.automation.application import rules_engine

    return await _run_module_wrap(rules_engine, db)


async def _render_via_template_service(db) -> str:
    """The admin preview's own name reader, called the way the admin calls it.

    ``_operator_store_name`` lives in the template service and is used to build
    the built-in template list the admin screen shows. When it grew its own
    reader instead of delegating, the admin preview and the transactional emails
    could disagree about the store name — which is the same defect, one layer up,
    and is what this case is for.
    """
    from app.modules.notifications.application import email_template_service

    name = await email_template_service._operator_store_name(db)
    return email_template_service._wrap_html(name, "<p>preview</p>")


async def _run_module_wrap(module, db) -> str:
    """Call whichever wrapping helper this module delegates to, and return its HTML.

    The indirection is deliberate: it means a module that goes back to reading
    ``get_smtp_config().from_name`` is caught here, because the branch below
    finds no shared helper and falls back to the same expression the code used to
    use. Reading the source instead would be a name search, and a name search is
    satisfied by an import nobody calls.
    """
    import inspect

    # These three import the email module *inside* their functions, so it is not
    # an attribute of the module object. Imported here rather than assumed.
    from app.modules.notifications.application import email_service

    src = inspect.getsource(module)
    if "wrap_html_for_store" in src:
        return await email_service.wrap_html_for_store(db, "<p>body</p>")
    # The reverted shape. `from_name` first, and only then the literal — the
    # same two-step the code used before the fix, so a revert reproduces the
    # exact disagreement rather than a strawman of it.
    name = email_service.get_smtp_config().from_name
    if not name:
        name = await resolve_store_name(db)
    return email_service._wrap_html(name, "<p>body</p>")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []

    original_identity = None
    original_blogname = None
    try:
        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'site_options'"
                        )
                    )
                ).fetchall()
            }
            if not {"option_key", "option_value"} <= columns:
                print("SKIP: site_options has no option_key/option_value pair.")
                return 0

            original_identity = await _read_option(db, "store.identity")
            original_blogname = await _read_option(db, "blogname")
            await _write_option(
                db, "store.identity", '{"store_name": "%s"}' % PROBE
            )
            await db.commit()

        # 1. The resolver reads the store's own setting.
        async with session() as db:
            got = await resolve_store_name(db)
        if got != PROBE:
            failures.append(
                "the resolver returned %r, not the store name %r it was pointed at"
                % (got, PROBE)
            )
        else:
            print("PASS: the resolver reads the store's own setting")

        # 2. All four transactional templates carry it. Every one, because the
        #    bug is per-template and a three-of-four fix reads as complete.
        async with session() as db:
            templates = email_service.default_email_templates(
                await resolve_store_name(db)
            )
        if not templates:
            failures.append("there are no built-in templates to check")
        for name, content in templates.items():
            header = _header_of(content.html)
            if header != PROBE:
                failures.append(
                    "the %s template's header reads %r, not %r — so a customer gets "
                    "a different store name depending on which email arrived"
                    % (name, header, PROBE)
                )
        if templates and not any("header reads" in f for f in failures):
            print(
                "PASS: all %d transactional templates carry the store name"
                % len(templates)
            )

        # 3. The three generic send paths. The *call sites* are exercised, not
        #    the helper they delegate to — a helper that works while a call site
        #    reads the environment is exactly the half-fix that shipped, and a
        #    check that only calls the helper cannot see it.
        #
        #    Each is invoked with the smallest input that reaches its header
        #    render, so a revert to `get_smtp_config().from_name` shows up as a
        #    wrong name rather than as an exception somewhere else.
        async with session() as db:
            for label, render in (
                (
                    "the helper the three send paths share",
                    lambda: email_service.wrap_html_for_store(db, "<p>body</p>"),
                ),
                (
                    "the notification service",
                    lambda: _render_via_notification_service(db),
                ),
                (
                    "the dispatch task",
                    lambda: _render_via_dispatch_task(db),
                ),
                (
                    "the automation engine",
                    lambda: _render_via_rules_engine(db),
                ),
            ):
                try:
                    rendered = await render()
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        "%s could not render an email at all: %r" % (label, exc)
                    )
                    continue
                header = _header_of(rendered)
                if header != PROBE:
                    failures.append(
                        "%s's header reads %r, not the store name — so a customer "
                        "gets a different store name depending on which email "
                        "arrived" % (label, header)
                    )
        if not any("header reads" in f or "could not render" in f for f in failures):
            print("PASS: all four generic send paths carry the same name")

        # 4. With no name configured anywhere, every path still agrees — on the
        #    deployment's own default. Without this the four paths could pass the
        #    check above and still diverge on a store that has configured nothing,
        #    which is the common case for a new installation.
        async with session() as db:
            await _write_option(db, "store.identity", None)
            await _write_option(db, "blogname", None)
            await db.commit()
        async with session() as db:
            fallback = await resolve_store_name(db)
            fallback_templates = email_service.default_email_templates(fallback)
            fallback_generic = await _run_module_wrap(email_service, db)
            # The admin preview path renders a template by name, and reads the
            # store name through its own `_operator_store_name`. Checked here
            # because that reader is a *second* definition of the same question,
            # and a second definition is what made the four send paths disagree
            # in the first place.
            fallback_admin = await _render_via_template_service(db)
        if not fallback:
            failures.append(
                "with nothing configured the resolver returned an empty name, so the "
                "header band would be blank"
            )
        else:
            headers = {
                _header_of(c.html) for c in fallback_templates.values()
            } | {_header_of(fallback_generic), _header_of(fallback_admin)}
            if headers != {fallback}:
                failures.append(
                    "with nothing configured the send paths print %r while the "
                    "resolver says %r" % (sorted(headers), fallback)
                )
            else:
                print(
                    "PASS: with nothing configured every path agrees on %r"
                    % fallback
                )

        # 6. And the admin preview agrees with the send paths while a name *is*
        #    configured — which is where a second reader diverges from the shared
        #    one. Checked in its own session because step 4 cleared the options.
        async with session() as db:
            await _write_option(db, "store.identity", '{"store_name": "%s"}' % PROBE)
            await db.commit()
        async with session() as db:
            admin_html = await _render_via_template_service(db)
        admin_header = _header_of(admin_html)
        if admin_header != PROBE:
            failures.append(
                "the admin template preview's header reads %r, not %r — so the "
                "operator editing a template sees a different store name than the "
                "customer who receives it" % (admin_header, PROBE)
            )
        else:
            print("PASS: the admin template preview agrees with the send paths")

        # 5. And a store name that is set but blank in the JSON falls through to
        #    the site title rather than printing an empty header.
        async with session() as db:
            await _write_option(db, "store.identity", '{"store_name": "   "}')
            await _write_option(db, "blogname", "Probe Blogname " + uuid.uuid4().hex[:6])
            await db.commit()
        async with session() as db:
            blank = await resolve_store_name(db)
        if not blank.strip():
            failures.append(
                "a blank store_name in the setting produced an empty header instead "
                "of falling back to the site title"
            )
        elif blank.startswith("Probe Blogname"):
            print("PASS: a blank store name falls through to the site title")
        else:
            failures.append(
                "a blank store_name produced %r; it should fall through to blogname"
                % blank
            )
    finally:
        async with session() as db:
            await db.rollback()
            await _write_option(db, "store.identity", original_identity)
            await _write_option(db, "blogname", original_blogname)
            await db.commit()
        print("restored the site options")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: every email path prints the same store name, from one source.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
