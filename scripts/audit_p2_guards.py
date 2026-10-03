#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabotage every guard this P2 work added, and record which ones notice.

A guard that cannot fail is not a guard. Each entry below breaks one specific
piece of the P2 change in a way a plausible refactor could, then runs the test
or script that is supposed to catch it. A guard that stays green under its own
sabotage is reported as UNGUARDED, because that is the state it would ship in
after the next careless edit.

Every sabotage is reverted from a backup taken immediately before it, and the
tree is verified identical afterwards — a half-restored file here would be worse
than a missing guard.

**Do not run this while another session is editing the tree.** Every entry in
CASES writes a real source file, breaks it, and writes it back. On a shared
tree that window is not private: another session's test run reads the broken
file, and one that was green moments earlier is red for reasons that have
nothing to do with its own code. This happened for real on 2026-10-02 — the
blog sanitiser in ``update_post`` was missing for the length of one audit run
and the P0 session reported a security regression that this file had caused.
The revert does eventually land; the window in between is real and belongs to
somebody else.

`scripts/verify_p2_frozen.py` is the entry point for the final verdict, and it
runs this audit last, after checking the tree has been still. Run it there, or
run this directly only when you are the only session touching these files.

Usage:  python scripts/audit_p2_guards.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

# <repo>/scripts/audit_p2_guards.py -> one level up is the repo root.
# realpath, not abspath: when the module is loaded from a relative path,
# abspath resolves against the *current* directory and lands outside the
# repo, which makes every sabotage target silently not exist.
_HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(_HERE)
assert os.path.isdir(os.path.join(ROOT, "backend")), (
    f"repo root resolved wrong: {ROOT}"
)
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

PY = sys.executable


class Sabotage:
    """Break one file, run a command, put the file back.

    ``relpath`` is relative to the repo root, so a guard script under
    ``<repo>/scripts`` and a service under ``<repo>/backend/app`` are addressed
    the same way.
    """

    def __init__(self, relpath: str, old: str, new: str, label: str) -> None:
        self.path = os.path.join(ROOT, relpath)
        self.old = old
        self.new = new
        self.label = label

    def apply(self) -> bool:
        if not os.path.isfile(self.path):
            return False
        src = open(self.path, encoding="utf-8").read()
        if self.old not in src:
            return False
        open(self.path, "w", encoding="utf-8").write(src.replace(self.old, self.new, 1))
        return True


def run_pytest(target: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [PY, "-B", "-m", "pytest", target, "-q", "-p", "no:cacheprovider"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=300,
    )
    failed = proc.stdout.count("\nFAILED")
    if failed == 0:
        for line in proc.stdout.splitlines():
            if line.startswith("FAILED"):
                failed = 1
                break
    return failed > 0, proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""


def run_script(relpath: str, env_extra: dict | None = None) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = BACKEND
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [PY, "-B", os.path.join(ROOT, relpath)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    return proc.returncode != 0, (proc.stdout.strip().splitlines() or [""])[-1]


# --------------------------------------------------------------- the guards
#
# Each entry: (sabotage, what it is meant to catch, how to run the guard).
# The wording of `old`/`new` matters: a replacement that only half lands is not
# a real test of the guard, it is a test of the editor.

CASES: list[tuple[Sabotage, str, str]] = [
    # 23-25. call-site guards added after the first audit found three helpers
    # that were correct in isolation and reachable from nowhere.
    (
        Sabotage(
            "backend/app/modules/blog/application/quick_edit_service.py",
            "    " + chr(34) + "meta" + chr(34) + "," + "\n",
            "    # sabotage" + "\n",
            "quick edit accepting a field it no longer writes",
        ),
        "app/tests/unit/test_p2_call_sites.py",
        "the dialog saving and dropping the custom fields",
    ),
    (
        Sabotage(
            "backend/app/modules/settings/application/site_health_service.py",
            "        db.add(row)" + "\n" + "        try:" + "\n" + "            await db.commit()",
            "        if False:  # sabotage" + "\n" + "            db.add(row)"
            + "\n" + "        try:" + "\n" + "            await db.commit()",
            "a health run computed and never stored",
        ),
        "app/tests/unit/test_p2_call_sites.py",
        "the history empty, a fixed problem invisible again",
    ),
    # 26. an inline <code> element swept into the typographer. The pre-wrapped
    # case was already covered; the bare one was not, and the difference is that
    # <pre> stashes first and hides the gap.
    (
        Sabotage(
            "backend/app/shared/content/text_filters.py",
            "pre|code|textarea",
            "pre|textarea",  # sabotage: <code> alone is no longer preserved
            "an inline <code> element typographed",
        ),
        "app/tests/unit/test_text_filters.py",
        "curly quotes inside inline code, breaking copy-paste",
    ),

    # 1. revision restore: replace instead of merge
    (
        Sabotage(
            "backend/app/modules/blog/application/blog_service.py",
            "        await self.db.execute(\n"
            "            sa_delete(BlogPostMeta).where(BlogPostMeta.post_id == post_id)\n"
            "        )",
            "        pass  # sabotage: restore now merges instead of replacing",
            "a revision restore that merges meta instead of replacing it",
        ),
        "app/tests/unit/test_revision_meta_snapshot.py",
        "a key added after the revision survives the restore",
    ),
    # 3. private notes: the type filter removed from the reply tree
    (
        Sabotage(
            "backend/app/modules/blog/application/comment_service.py",
            "        stmt = select(BlogComment).where(\n"
            "            BlogComment.parent_id == parent_id,\n"
            "            # A note is threaded like a comment but is not one. Reading replies\n"
            "            # is the path a public comment view takes, so the filter belongs on\n"
            "            # the query rather than on the caller.\n"
            "            BlogComment.comment_type == COMMENT_TYPE_COMMENT,\n"
            "        )",
            "        stmt = select(BlogComment).where(BlogComment.parent_id == parent_id)",
            "a private note becoming readable through the reply tree",
        ),
        "app/tests/unit/test_comment_notes.py",
        "notes leaking into a public comment thread",
    ),
    # 4. private notes: the public list stops filtering
    (
        Sabotage(
            "backend/app/modules/blog/application/comment_service.py",
            "        elif not include_moderation_fields:\n"
            "            stmt = stmt.where(BlogComment.comment_type == COMMENT_TYPE_COMMENT)",
            "        elif False:  # sabotage\n"
            "            stmt = stmt.where(BlogComment.comment_type == COMMENT_TYPE_COMMENT)",
            "the public comment list returning private notes",
        ),
        "app/tests/unit/test_comment_notes.py",
            "notes appearing in the public comment list",
    ),
    # 5. comment url: the scheme check removed
    (
        Sabotage(
            "backend/app/modules/blog/application/comment_service.py",
            '    if not _COMMENT_URL_RE.match(value):\n        return None',
            "    return value  # sabotage: any scheme accepted",
            "a javascript: commenter URL being stored and linkified",
        ),
        "app/tests/unit/test_comment_author_url.py",
        "a stored XSS in a public comment",
    ),
    # 6. plugin hooks: a declared hook that never fires
    (
        Sabotage(
            "backend/app/modules/blog/application/blog_service.py",
            "        return await registry.apply_filters(HOOK_POST_BODY_RENDER, rendered)",
            "        return rendered  # sabotage: the hook never fires",
            "a declared plugin hook with no dispatch",
        ),
        "scripts/wp-parity/check_hooks_dispatched.py",
        "a plugin binding to a point that never runs",
    ),
    # 7. plugin hooks: the sanitiser no longer runs before the filter
    (
        Sabotage(
            "backend/app/modules/blog/application/blog_service.py",
            '        if update_dict.get("content"):\n'
            '            update_dict["content"] = sanitize_html(update_dict["content"])\n',
            "",
            "a plugin able to re-inject the markup the sanitiser removed",
        ),
        "app/tests/unit/test_plugin_hook_points.py",
        "unsanitised content reaching storage through a hook",
    ),
    # 8. email templates: a caller reads the built-ins again
    (
        Sabotage(
            "backend/app/modules/automation/application/rules_engine.py",
            "            content = await resolve_template(db, str(template_name))",
            "            content = email_service.default_email_templates().get(\n"
            "                str(template_name)\n"
            "            )  # sabotage",
            "an admin's saved template override never reaching a real email",
        ),
        "app/tests/unit/test_email_template_resolver.py",
        "the editor saving a change no email would use",
    ),
    # 9. email templates: the executable-markup guard removed
    (
        Sabotage(
            "backend/app/modules/notifications/application/email_template_service.py",
            "    r\"<\\s*/?\\s*(script|iframe|object|embed|applet|form|base|link|meta)\\b\",",
            "    r\"<\\s*/?\\s*(marquee)\\b\",  # sabotage",
            "a template able to carry <script> or a javascript: link",
        ),
        "app/tests/unit/test_email_templates_and_attachments.py",
        "an operator scripting every order confirmation",
    ),
    # 10. email attachments: the invoice stops being attached
    (
        Sabotage(
            "backend/app/modules/automation/application/outbox_worker.py",
            "            attachments=await _invoice_attachment(db, order, template_name),",
            "            # sabotage: no attachment",
            "the order confirmation losing its invoice",
        ),
        "app/tests/unit/test_email_templates_and_attachments.py",
        "the customer receiving a confirmation with no document",
    ),
    # 11. email attachments: files added before the body
    (
        Sabotage(
            "backend/app/modules/notifications/application/email_service.py",
            "    msg.set_content(text_body or subject, charset=\"utf-8\")",
            "    # sabotage: attachments first, breaking the alternative pair\n"
            "    for item in attachments or []:\n"
            "        fn = str(item.get(\"filename\") or \"\").strip()\n"
            "        data = item.get(\"content\")\n"
            "        if fn and isinstance(data, (bytes, bytearray)):\n"
            "            msg.add_attachment(bytes(data), maintype=\"application\",\n"
            "                               subtype=\"octet-stream\", filename=fn)\n"
            "    msg.set_content(text_body or subject, charset=\"utf-8\")",
            "attachments emitted before the body, breaking the alternative pair",
        ),
        "app/tests/unit/test_email_templates_and_attachments.py",
        "a client picking the wrong body part",
    ),
    # 12. http basic: basic overriding bearer
    (
        Sabotage(
            "backend/app/core/security/dependencies.py",
            "    if credentials is not None:\n"
            "        token = credentials.credentials\n"
            "    elif basic is not None and basic.password:\n"
            "        token = basic.password",
            "    if basic is not None and basic.password:  # sabotage\n"
            "        token = basic.password\n"
            "    elif credentials is not None:\n"
            "        token = credentials.credentials",
            "a bearer session read as a basic password",
        ),
        "app/tests/unit/test_basic_application_password.py",
        "every API client with both headers failing",
    ),
    # 13. embed cache: failures cached for a week
    (
        Sabotage(
            "backend/app/modules/content/application/embed_service.py",
            "        ttl = EMBED_CACHE_TTL_SECONDS if result.get(\"html\") else EMBED_NEGATIVE_TTL_SECONDS",
            "        ttl = EMBED_CACHE_TTL_SECONDS  # sabotage",
            "a transient provider failure cached for a week",
        ),
        "app/tests/unit/test_embed_cache.py",
        "one bad provider response permanent in the page",
    ),
    # 14. upload ceiling: back to a hard-coded constant
    # 16. site health info: the tab unable to reach the database
    (
        Sabotage(
            "backend/app/modules/settings/application/site_health_service.py",
            "                version = await db.execute(text(\"SELECT version()\"))",
            "                async with db.connect() as conn:  # sabotage: no such method\n"
            "                    version = await conn.execute(text(\"SELECT version()\"))",
            "the Info tab reporting a database error forever",
        ),
        "app/tests/unit/test_site_health_runs.py",
        "support never getting the version",
    ),
    # 17. celery: a task module dropped from the include list
    (
        Sabotage(
            "backend/app/worker/celery_app.py",
            '    "app.modules.inventory.application.tasks",\n',
            "",
            "a beat job whose task module is not imported",
        ),
        "app/tests/unit/test_celery_task_registration.py",
        "a scheduled job that fires and dies",
    ),
    # 18. text filters: a transformation silently not applying
    (
        Sabotage(
            "backend/app/shared/content/text_filters.py",
            'text = re.sub(r"(?<=\w)\'(?=\w)", "’", text)',
            'text = text  # sabotage: the apostrophe pass is a no-op',
            "the typographer running but quietly applying nothing",
        ),
        "app/tests/unit/test_text_filters.py",
        "contractions rendering as don't instead of don’t",
    ),
    # 19. text filters: code samples typographed
    # 20. media lineage: the chain link not written
    (
        Sabotage(
            "backend/app/modules/media/application/media_service.py",
            "            source_asset_id=source.id,\n",
            "            # sabotage: no lineage link\n",
            "a derived image that cannot be traced back to its original",
        ),
        "app/tests/unit/test_media_edit_lineage.py",
        "no restore-the-original, no undo",
    ),
    # 21. post defaults: the option read removed
    (
        Sabotage(
            "backend/app/modules/blog/application/blog_service.py",
            '        slug = (await SiteOptionsService.get(self.db, OPTION_DEFAULT_CATEGORY, "")) or ""',
            '        slug = ""  # sabotage: the default category option is ignored',
            "a new post ignoring the configured default category",
        ),
        "app/tests/unit/test_post_defaults.py",
        "every post filed under no category again",
    ),
    # 22. the stored-html gate: not detecting anything
    (
        Sabotage(
            "scripts/wp-parity/check_stored_html.py",
            "                if cleaned == body:\n                    continue",
            "                if cleaned != body:\n                    continue  # sabotage: reports the inverse",
            "the stored-HTML gate reporting nothing",
        ),
        "scripts/wp-parity/check_stored_html.py",
        "an unsanitised row sitting in the database undetected",
    ),
]


def _audit_gates(out: io.TextIOWrapper) -> list[tuple[str, str, bool, str]]:
    """Inject a real regression per gate, and prove the gate goes red.

    The first version of this did the opposite and proved nothing: it broke the
    gate's own reporting line and then checked that the gate exited non-zero. A
    gate that no longer reports anything exits zero, so the check measured its
    own sabotage rather than the gate.

    What is proved instead is the property that matters: **inject the failure
    this gate exists to catch, and require the gate to catch it.** The gate is
    not modified at all. If a gate stays green against the regression it was
    written for, it is not a gate — it is a script that prints PASS.
    """
    results: list[tuple[str, str, bool, str]] = []
    gate_dir = os.path.join(ROOT, "scripts", "wp-parity")
    runner = os.path.join(ROOT, "scripts", "run_all_gates.py")

    # (gate, the file to regress, anchor, replacement, what the regression is)
    injections = [
        (
            "check_enum_storage_contract",
            "backend/app/modules/shipping/domain/models.py",
            'server_default="HOME",',
            'server_default="home",',
            "a column that stores member NAMES gets a server_default that writes "
            "a member VALUE, so every row created outside the ORM raises "
            "LookupError on read — and the existing 173 rows already in the "
            "shipments table would need a migration",
        ),
        (
            "check_store_identity_reaches",
            "backend/app/modules/notifications/application/store_name.py",
            "raw = await SiteOptionsService.get(db, STORE_IDENTITY_OPTION)",
            "raw = \"\"  # injected regression: the setting is read by nothing",
            "the operator's store name stops coming from the settings screen "
            "and falls back to the deployment environment — the read is gone "
            "while the constant that names the key is still nearby",
        ),
        (
            "check_privacy_policy_reaches_forms",
            "frontend/components/privacy/privacy-policy-notice.tsx",
            "    privacyPolicyApi\n      .get()\n",
            "    privacyPolicyApi\n      .getUnused()\n",
            "the notice component stops issuing the request, so every form "
            "renders with an empty policy — the endpoint stays reachable only "
            "by curl. The gate missed this once because it checked the client "
            "*definition* and not the call site, and again because it counted "
            "occurrences across the file rather than per component.",
        ),
        (
            "check_scheduled_tasks",
            "backend/app/modules/settings/application/tasks.py",
            "@shared_task(name=\"app.modules.settings.application.tasks.run_site_health\")",
            "## the scheduled health task was removed  # injected regression",
            "the daily Site Health job's task is gone while its beat entry stays",
        ),
        (
            "check_hooks_dispatched",
            "backend/app/modules/blog/application/blog_service.py",
            "        return await registry.apply_filters(HOOK_POST_BODY_RENDER, rendered)",
            "        return rendered  # injected regression: the hook never fires",
            "a declared plugin hook with no dispatch site",
        ),
        (
            "check_p2_deliveries",
            "backend/app/modules/media/application/media_service.py",
            "            source_asset_id=source.id,",
            "            # injected regression: no chain link",
            "a derived image that cannot be traced back to its original",
        ),
        # The two gates found orphaned on disk by test_gate_runner.py — present
        # but listed nowhere, so they had never run. Being listed is not the same
        # as being known to work, so each is proved here too.
        (
            "check_guest_comment_coverage",
            "backend/app/modules/settings/application/privacy_service.py",
            "[BlogComment.author_id == author_id, BlogComment.author_email.ilike(email)]",
            "[BlogComment.author_id == author_id]  # injected regression",
            "a data-subject export that cannot see owner-less comments",
        ),
        (
            "check_jsonb_null_semantics",
            "backend/app/modules/settings/domain/models.py",
            "        SqlNullOnNone, nullable=True\n",
            "        JSONB, nullable=True  # injected regression: no null() wrapper\n",
            "a JSONB payload column whose 'cleared' rows still hold their data",
        ),
    ]

    for gate, target, anchor, replacement, what in injections:
        # Paths in `injections` are relative to the repository root, which is the
        # only base that spans both trees: a frontend .tsx and a backend module
        # are injected by the same loop. Resolving against `backend/` alone made
        # every frontend target report "does not exist" — a sabotage that never
        # landed, which the layer-1 report would otherwise have read as a gate
        # that failed to notice.
        target_path = os.path.join(ROOT, target)
        if not os.path.isfile(os.path.join(gate_dir, f"{gate}.py")):
            results.append((gate, "missing", False, f"{gate}.py does not exist"))
            continue
        if not os.path.isfile(target_path):
            results.append((gate, "target missing", False, f"{target} does not exist"))
            continue
        backup = tempfile.mktemp(suffix=".bak")
        shutil.copy2(target_path, backup)
        src = open(target_path, encoding="utf-8").read()
        if anchor not in src:
            shutil.copy2(backup, target_path)
            os.remove(backup)
            results.append(
                (gate, "anchor not found", False, f"{what} — the code moved")
            )
            continue
        open(target_path, "w", encoding="utf-8").write(
            src.replace(anchor, replacement, 1)
        )
        try:
            code, _stdout, _stderr = _run_gate(gate)
        finally:
            shutil.copy2(backup, target_path)
            os.remove(backup)
        caught = code != 0
        results.append(
            (
                gate,
                "guarded" if caught else "UNGUARDED",
                caught,
                f"a gate that cannot fail makes every PASS it prints meaningless; "
                f"it did not catch: {what}",
            )
        )

    # Every gate file is reachable from the runner.
    if os.path.isfile(runner):
        runner_src = open(runner, encoding="utf-8").read()
        on_disk = {
            n[:-3]
            for n in os.listdir(gate_dir)
            if n.startswith("check_") and n.endswith(".py")
        }
        unlisted = sorted(g for g in on_disk if f'"{g}"' not in runner_src)
        results.append(
            (
                "every gate is in the runner",
                "guarded" if not unlisted else "UNGUARDED",
                not unlisted,
                f"never run: {unlisted}" if unlisted else "",
            )
        )
    else:
        results.append(("every gate is in the runner", "UNGUARDED", False,
                        "scripts/run_all_gates.py does not exist"))

    return results


def _run_gate(gate: str) -> tuple[int, str, str]:
    """Execute one parity gate with the project's PYTHONPATH."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([BACKEND, env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )
    proc = subprocess.run(
        [PY, "-B", os.path.join("scripts", "wp-parity", f"{gate}.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _tree_is_busy(minutes: float = 3.0) -> list[str]:
    """Tracked files written very recently, as repo-relative paths.

    Used to refuse the sabotage layer on a shared tree. The audit breaks real
    source files for the length of each entry, and on a tree another session is
    editing that window is somebody else's regression report.
    """
    skip = {".next", "node_modules", "__pycache__", ".git", ".pytest_cache", "dist"}
    cutoff = time.time() - minutes * 60
    tracked = ("backend/app", "frontend/app", "frontend/components", "frontend/lib", "scripts")
    hits: list[str] = []
    for rel in tracked:
        base = os.path.join(ROOT, rel)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            for name in filenames:
                if name.endswith((".pyc", ".pyo")):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    if os.path.getmtime(path) > cutoff:
                        hits.append(os.path.relpath(path, ROOT).replace("\\", "/"))
                except OSError:
                    continue
    return sorted(hits)


def main() -> int:
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    results: list[tuple[str, str, bool, str]] = []
    started = time.monotonic()

    # ── The shared-tree refusal ─────────────────────────────────────────────
    #
    # Every case below writes a real source file and writes it back. Run that
    # while another session is editing and its test suite reads the broken file:
    # on 2026-10-02 the P0 session saw a security regression in
    # `update_post` that this audit had caused and had not yet reverted. A
    # warning printed before the damage is not a safeguard, so the sabotage
    # layers are skipped outright and the audit reports that it did not run.
    # `scripts/verify_p2_frozen.py` is the supported entry point: it checks the
    # tree is quiet and only then calls this.
    if "--force" not in sys.argv:
        busy = _tree_is_busy()
        if busy:
            out.write(
                f"REFUSED: {len(busy)} tracked file(s) changed in the last 3 "
                f"minutes. The sabotage layers write real source files, and on a "
                f"tree another session is editing the broken window is its "
                f"regression report, not mine.\n"
            )
            for path in busy[:10]:
                out.write(f"    {path}\n")
            if len(busy) > 10:
                out.write(f"    ... and {len(busy) - 10} more\n")
            out.write(
                "  Wait for the tree to go quiet, or pass --force if you are the "
                "only session touching these files.\n"
            )
            return 3

    # ── Layer 2: the gates themselves ──────────────────────────────────────
    #
    # Everything above proves a P2 *test* notices its sabotage. This proves the
    # *gates* notice: a gate that has never turned red is a gate whose green
    # means nothing, and a gate that is not in the runner at all never runs.
    # Without this layer, every gate in this file could be inert and the audit
    # would still report a clean sheet.
    gate_results = _audit_gates(out)

    for sabotage, guard, why in CASES:
        backup = tempfile.mktemp(suffix=".bak")
        shutil.copy2(sabotage.path, backup)
        applied = sabotage.apply()
        if not applied:
            results.append((sabotage.label, "ANCHOR NOT FOUND", False, why))
            os.remove(backup)
            continue
        try:
            if guard.endswith(".py") and "scripts/" in guard:
                caught, detail = run_script(guard)
            else:
                caught, detail = run_pytest(guard)
        finally:
            shutil.copy2(backup, sabotage.path)
            os.remove(backup)
        results.append((sabotage.label, "guarded" if caught else "UNGUARDED", caught, why))

    total = len(results)
    guarded = sum(1 for r in results if r[2])
    anchors = sum(1 for r in results if r[1] == "ANCHOR NOT FOUND")
    gate_caught = sum(1 for r in gate_results if r[2])

    out.write("P2 guard audit — every guard sabotaged once\n")
    out.write("=" * 78 + "\n")
    out.write("  layer 2: the gates themselves\n")
    for label, status, caught, why in gate_results:
        mark = "ok  " if caught else "GAP "
        out.write(f"  [{mark}] {label}\n")
        if not caught:
            out.write(f"          why it matters: {why}\n")
    out.write("  layer 1: the P2 guards\n")
    for label, status, caught, why in results:
        mark = "ok  " if caught else ("SKIP" if status == "ANCHOR NOT FOUND" else "GAP ")
        out.write(f"  [{mark}] {label}\n")
        if not caught and status != "ANCHOR NOT FOUND":
            out.write(f"          why it matters: {why}\n")
    out.write("=" * 78 + "\n")
    out.write(
        f"  gates: {gate_caught} of {len(gate_results)} turned red on their own sabotage\n"
    )
    out.write(
        f"  guards: {guarded} of {total - anchors} caught their own sabotage "
        f"({anchors} anchor(s) not found, i.e. the code moved).\n"
    )
    out.write(f"{time.monotonic() - started:.0f}s\n")
    if gate_caught != len(gate_results) or guarded != total - anchors:
        return 1
    return 0
    out.flush()
    return 0 if guarded == total - anchors else 1


if __name__ == "__main__":
    sys.exit(main())
