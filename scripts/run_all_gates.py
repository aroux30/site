#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One command that runs every invariant gate, and says which class failed.

There is no CI workflow in this repository — `.github/` was removed at the
user's request — so "CI" here means this: a single entry point that a person or
a runner invokes before calling work done.

It exists because of a measured failure mode. Over one day the P2 deliveries
regressed three times while the tree was being edited by three sessions at
once: a Celery task was dropped from a rewritten module while its beat entry
stayed, three plugin hooks shipped declared but never dispatched, and the
emails' template resolver was bypassed by its callers. Each was caught only
because something looked, by hand, at the right moment. Anything that is only
checked when somebody remembers to check it is not a gate.

Three classes, reported separately because they fail for different reasons:

* ``source``  — reads the code; no database, runs anywhere.
* ``live``    — reads the database; skipped loudly when none is reachable, and
  never counted as a pass. A gate that cannot run has not passed.
* ``sabotage`` — deliberately breaks one thing per P2 item and asserts the
  guard notices. Slow by nature; it is the price of knowing a green gate is
  green for a reason.

Usage:
    python scripts/run_all_gates.py            # source + live
    python scripts/run_all_gates.py --sabotage # also the sabotage audit
    python scripts/run_all_gates.py --only NAME # one gate, by name
Exit: 0 when everything applicable passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, "backend")
PY = sys.executable

#: (gate name, needs a database). Kept as a list rather than a glob so a new
#: gate cannot be added without being classified here — a gate that nobody
#: knows whether it needs a DB is a gate that quietly never runs.
GATES: list[tuple[str, bool]] = [
    ("check_p2_deliveries", False),
    ("check_author_slug_paths", True),
    ("check_users_role_filter", True),
    ("check_users_bulk_and_sessions", True),
    ("check_remember_me_and_email_verification", True),
    ("check_display_name_and_admin_email", True),
    ("check_privacy_email_zip_policy", True),
    ("check_avatar_upload", True),
    ("check_registration_approval", True),
    ("check_passkey_flow", True),
    ("check_admin_app_passwords", True),
    ("check_basic_auth_app_password", True),
    ("check_hooks_dispatched", False),
    ("check_scheduled_tasks", False),
    ("check_admin_nav", False),
    ("check_editor_allowlists", False),
    ("check_private_post_leak", False),
    ("check_publish_and_quickedit", False),
    ("check_comment_avatar_path", False),
    ("check_comment_resource_addressing", False),
    ("check_media_usage_coverage", False),
    ("check_revision_pruning", False),
    ("check_server_pagination", False),
    ("check_sitemap_archives", False),
    ("check_sitemap_images", False),
    ("check_store_identity_reaches", False),
    ("check_doc_references", False),
    ("check_scripts_runnable", False),
    ("check_healthz", True),
    ("check_site_health_info", True),
    ("check_stored_html", True),
    ("check_bulk_posts", True),
    ("check_jsonb_null_semantics", False),
    ("check_guest_comment_coverage", False),
    ("check_comment_ip_retention", False),
    ("check_privacy_policy_reaches_forms", False),
    ("check_email_store_name", False),
    ("check_admin_api_clients_are_called", False),
    ("check_enum_storage_contract", False),
    ("check_comment_ip_reaches_panel", False),
    ("check_comment_moderation_links", False),
    ("check_comment_shortcuts_wired", False),
    ("check_comment_trash_reachable", False),
    ("check_enum_round_trip", False),
    ("check_gap_list_evidence", False),
    ("check_media_attach_wired", False),
    ("check_media_folder_wired", False),
    ("check_media_routes_reachable", False),
    ("check_media_custom_sizes", True),
    ("check_media_date_filter", True),
    ("check_media_replace", True),
    ("check_media_trash_http", True),
    ("check_watermark_wired", True),
    ("check_site_health_email_disk", True),
    ("check_accessibility_wired", False),
    ("check_no_truncated_sources", False),
    ("check_password_strength_behaviour", False),
    ("check_password_strength_wired", False),
    ("check_pending_badge_wired", False),
    ("check_registration_switch_wired", False),
    ("check_comment_resource_constraint", False),
    ("check_page_lock_autosave_wired", False),
    ("check_no_cross_session_sabotage", False),
    ("check_settings_options_wired", False),
    ("check_settings_tabs", False),
    ("check_privacy_export_zip", True),
    ("check_scheduled_jobs_page", False),
    ("check_recovery_invitation", False),
    ("check_menu_locations_and_picker", True),
    ("check_media_page_features", False),
    ("check_media_undo_redo", True),
    ("check_admin_bar_contextual", False),
    ("check_privacy_policy_selector", False),
    ("check_oembed_channels", False),
    ("check_widget_types_wired", False),
    ("check_sitemap_single_surface", False),
    # The gate that catches the one this registry exists to prevent.
    ("check_every_gate_is_registered", False),
    # Quick edit for CMS pages: component, state, trigger, and the payload
    # the dialog actually sends.
    ("check_page_quick_edit_wired", False),
    # Lock take-over: service method -> route -> client -> hook -> button,
    # for posts and pages alike.
    ("check_lock_takeover_wired", False),
    # A negative test whose restore did not run: imports cleanly, fails at
    # runtime, and nothing looks for it.
    ("check_no_sabotage_left_in_source", False),
    # A second stdout wrapper closes the first one's buffer, so importing
    # a gate crashes whichever module imported it first.
    ("check_stdout_guards_are_idempotent", False),
    # The byline field: on the row, in the query, at the constructor, and in
    # the formatter — each can be missing while the others are present.
    ("check_author_display_name_wired", False),
    # A content type archive: public route, a client that is not the admin one,
    # and a page that renders the declared fields.
    ("check_content_type_archive_wired", False),
    # oEmbed discovery per page, and an endpoint that answers the link it emits.
    ("check_oembed_discovery_wired", False),
    # WXR import: the parser is run against a real WordPress-shaped file,
    # because the three ways it breaks are invisible to a source check.
    ("check_wxr_import_behaviour", False),
    # The admin bar sends ?search=<slug>; the list must read it, and the
    # search must match the slug it was given.
    ("check_admin_search_deeplink_wired", False),
    # The ten WordPress media shortcodes, and the schemes they refuse as a
    # source.
    ("check_shortcode_coverage", False),
    # The custom-taxonomy archive: terms, a term's posts, and the pages
    # that reach both.
    ("check_taxonomy_archive_wired", False),
    # Custom post entry revisions + scheduled publishing, as a chain. The model
    # and both migrations shipped first with no route, and the route later
    # shipped with a list response that omitted the schedule — so the gate walks
    # model → migration → service → route → task → client → UI and each layer
    # must be present *and* carrying the fields, not merely named.
    ("check_cpt_revision_wired", False),
    # Akismet: the check AND the feedback loop. The transport seam was once
    # invoked as a bare callable, so every request raised TypeError, the broad
    # except turned it into "no opinion", and the feature sent nothing while
    # every string a presence-check looks for stayed in place.
    ("check_akismet_wired", False),
    # Every task the beat schedule names must be dispatchable. The beat entry
    # for scheduled blog posts outlived its celery wrapper, so the worker
    # answered "Received unregistered task" every minute and scheduled posts
    # stayed drafts — while three presence gates agreed everything was fine.
    ("check_beat_tasks_registered", False),
    # A Site Health run that stored "which check failed" and "how long it took"
    # without either reaching the screen: the service computes both, so the gate
    # has to walk service → API → type → page rather than trust any one of them.
    ("check_site_health_runs", False),
    ("check_oembed_discovery_ssrf", False),
    # Every migration must be unique, have real parents, and reach a head — and
    # no parent may be merged twice, which is what actually aborts `upgrade head`
    # on an empty database. `alembic heads == current` cannot see any of this.
    ("check_migration_revisions_unique", False),
    # The only check that exercises a deployment: the whole chain against an
    # empty schema. `alembic heads == current` compares one migrated database
    # against itself and cannot see an order that only fails from empty.
    #
    # True, not False, and the distinction is not cosmetic. With `False` a
    # machine with no database reports this as a FAILURE, which is a lie about
    # a check that never ran; with `True` the runner looks for a connection
    # error and reports it as skipped. It does not create its own database — it
    # makes a schema inside the one the application uses, so it needs that
    # connection the same way any other DB gate does.
    ("check_migration_chain_from_empty", True),

    # RSS/Atom import: the parser is run against real feeds, the output
    # is checked against the keys import_json actually reads, a hostile
    # feed link is parsed and inspected for injected handlers, and every
    # link from parser to admin screen is asserted.
    ("check_feed_import_chain", False),

]

#: Substrings that mean "the database was not reachable", as opposed to "the
#: gate ran and found something". Only the former may be reported as skipped.
NO_DB_MARKERS = (
    "connectionrefused",
    "could not connect",
    "operationalerror",
    "name or service not known",
    "connection error",
    "password authentication failed",
    "econnrefused",
    "localhost:5432",
)


def _run(argv: list[str], timeout: int = 300) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([BACKEND, env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )
    try:
        proc = subprocess.run(
            [PY, "-B", *argv],
            cwd=ROOT,
            env=env,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    # Decode explicitly with errors="replace" instead of text=True. text=True
    # decodes with the console's codec — cp1252 on Windows — and a gate whose
    # output contains a byte cp1252 cannot map raises UnicodeDecodeError inside
    # subprocess.run, which returns stdout=None and turns the whole runner into
    # a crash at `stdout + stderr`. That is a guard dying at the moment it
    # found something: the one gate with a finding takes the suite down with
    # it, and the finding is never reported. A runner must survive every gate's
    # output, including output it cannot decode.
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def _looks_like_no_database(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in NO_DB_MARKERS)


def _last_meaningful_line(text: str) -> str:
    for line in reversed([ln.strip() for ln in text.splitlines() if ln.strip()]):
        if line.startswith(("PASS", "FAIL")) or line:
            return line
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sabotage", action="store_true", help="also run the guard audit")
    parser.add_argument("--only", help="run one gate by name")
    parser.add_argument(
        "--json", action="store_true", help="machine-readable, for a CI runner"
    )
    args = parser.parse_args()

    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    selected = [g for g in GATES if not args.only or g[0] == args.only]
    if args.only and not selected:
        out.write(f"no gate named {args.only!r}\n")
        return 2

    rows: list[tuple[str, str, str, float]] = []
    started = time.monotonic()

    #: Gates whose own work legitimately takes longer than the default budget.
    #: `check_publish_and_quickedit` runs 30 fixture scripts against one
    #: database — measured at 283s, i.e. 94% of the default. Any ordinary
    #: slowdown pushed it over, and the runner killed it, so the suite reported
    #: "timeout after 300s" for a gate whose 30 fixtures all pass. The budget
    #: has to fit the gate, not the other way round.
    SLOW_GATES = {"check_publish_and_quickedit": 900}

    for name, needs_db in selected:
        gate_path = os.path.join("scripts", "wp-parity", f"{name}.py")
        if not os.path.isfile(os.path.join(ROOT, gate_path)):
            rows.append((name, "MISSING", f"{gate_path} does not exist", 0.0))
            continue
        began = time.monotonic()
        code, stdout, stderr = _run(
            [gate_path], timeout=SLOW_GATES.get(name, 300)
        )
        took = time.monotonic() - began
        combined = stdout + stderr
        if code == 0:
            rows.append((name, "pass", _last_meaningful_line(stdout), took))
        elif code == 2 and "SKIP" in (stdout + stderr):
            # The gate told us it could not run — a fixture directory is absent,
            # say. That is not a pass and not a failure either, and counting it
            # as either is how a suite goes green without having executed.
            rows.append((name, "SKIP (not run)", _last_meaningful_line(stdout), took))
        elif needs_db and _looks_like_no_database(combined):
            # Loudly skipped, and counted as neither pass nor fail: a gate that
            # could not run has told us nothing, and reporting it as green is the
            # one outcome that would be a lie.
            rows.append((name, "SKIP (no database)", "database not reachable", took))
        else:
            rows.append((name, "FAIL", _last_meaningful_line(combined), took))

    if args.sabotage:
        audit = os.path.join("scripts", "audit_p2_guards.py")
        if os.path.isfile(os.path.join(ROOT, audit)):
            began = time.monotonic()
            code, stdout, stderr = _run([audit], timeout=900)
            rows.append(
                (
                    "audit_p2_guards",
                    "pass" if code == 0 else "FAIL",
                    _last_meaningful_line(stdout + stderr),
                    time.monotonic() - began,
                )
            )

    if args.json:
        import json

        print(
            json.dumps(
                [
                    {"gate": n, "status": s, "detail": d, "seconds": round(t, 1)}
                    for n, s, d, t in rows
                ],
                indent=2,
            )
        )
    else:
        out.write("\ninvariant gates\n")
        out.write("-" * 78 + "\n")
        for name, status, detail, took in rows:
            out.write(f"  {name:<34} {status:<18} {took:5.1f}s\n")
            if status == "FAIL":
                out.write(f"      {detail}\n")
        out.write("-" * 78 + "\n")

    passed = sum(1 for _, s, _, _ in rows if s == "pass")
    failed = [n for n, s, _, _ in rows if s == "FAIL"]
    missing = [n for n, s, _, _ in rows if s == "MISSING"]
    skipped = [n for n, s, _, _ in rows if s.startswith("SKIP")]

    if not args.json:
        out.write(
            f"{passed} passed, {len(failed)} failed, {len(skipped)} skipped, "
            f"{len(missing)} missing   ({time.monotonic() - started:.0f}s)\n"
        )
        if skipped:
            out.write(
                "  skipped gates have verified nothing. Start the database and "
                "re-run before believing this is green.\n"
            )
    for name in missing:
        out.write(f"  MISSING GATE: {name}\n")

    return 1 if failed or missing else 0


if __name__ == "__main__":
    sys.exit(main())