"""Custom post entry revisions + scheduled publishing must be a chain, not a
model.

The gap this guards is not "the class does not exist" — it is the shape where
one layer ships alone and every other layer is missing, which is what happened
twice while building this:

* the model and the two migrations were in place with no route, so the whole
  feature was invisible from the API;
* the routes and the service were in place and the list response still omitted
  `scheduled_publish_at`, so the tab rendered a permanently blank schedule
  column — every string was present somewhere, and the feature was dead.

So each layer is checked for what it must *say*, not for what it must contain:

* the model declares the two columns;
* the migrations that add them are on disk and the head is single;
* the service snapshots before the write, not after — a snapshot taken after is
  indistinguishable from the current row, so restore becomes a no-op that reads
  as "restore is broken";
* `publish_scheduled` clears the schedule as it goes, so a repeated run cannot
  republish;
* the routes call the service (not a reimplementation);
* the list and update responses *carry* the schedule, which is the check the
  earlier build failed;
* the client method exists and the tab calls it — a route with no caller is a
  gap, not a feature;
* the beat schedule registers the task under a name the app can resolve.

Every check below fails if its layer is removed or bypassed.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # scripts/wp-parity/ -> site/
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

problems: list[str] = []


def require(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {'ok' if ok else 'FAIL'}")
    if not ok:
        problems.append(f"{label}{': ' + detail if detail else ''}")


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# --- 1. the model ------------------------------------------------------------
model = read(BACKEND / "app/modules/blog/domain/custom_post_types.py")
require("model: entry declares scheduled_publish_at", "scheduled_publish_at" in model)
require("model: entry declares revision_count", "revision_count" in model)
require(
    "model: the revision table exists",
    'class CustomPostEntryRevision' in model
    and 'custom_post_entry_revisions' in model,
)
rev_model = re.search(
    r"class CustomPostEntryRevision.*?(?=\nclass |\Z)", model, re.S
)
rev_src = rev_model.group(0) if rev_model else ""
for col in ("entry_id", "fields", "revision_number", "created_by_id"):
    require(f"model: revision has {col}", col in rev_src)
require(
    "model: the revision cascades when the entry goes",
    "cascade" in rev_src.lower(),
    "without CASCADE, deleting an entry leaves orphan revisions",
)

# --- 2. the migrations, and only one head ------------------------------------
versions = sorted((BACKEND / "alembic/versions").glob("*.py"))
def _alembic_heads() -> tuple[list[str], str]:
    """The heads alembic itself resolves, not a re-derivation of them."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError as exc:  # pragma: no cover
        return [], f"alembic not importable ({exc})"
    ini = next(iter(sorted(BACKEND.glob("alembic.ini"))), None)
    if ini is None:
        return [], "no alembic.ini"
    try:
        # `script_location` in alembic.ini is relative, so alembic resolves it
        # against the process cwd. Every other gate in this suite runs from the
        # site root, which would have made this check report a false failure
        # rather than a real one.
        cfg = Config(str(ini))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        return list(script.get_heads()), ""
    except Exception as exc:  # a broken chain raises here, not at upgrade time
        return [], f"{type(exc).__name__}: {exc}"


versions = sorted((BACKEND / "alembic/versions").glob("*.py"))
rev_ids: dict[str, str] = {}
for f in versions:
    m = re.search(r'''^revision(?::\s*str)?\s*=\s*["']([^"']+)''', read(f), re.M)
    if m:
        rev_ids[m.group(1)] = f.name

# The head count is read from alembic rather than re-derived from the files.
# My first version of this check parsed `down_revision` as a single string, so a
# merge revision — `down_revision = ("a", "b")` — was invisible to it and the
# answer depended on the shape of the chain. Worse, the direction of the error
# was backwards: it reported a clean tree as broken.
heads, heads_err = _alembic_heads()
require(
    "migrations: exactly one head",
    len(heads) == 1,
    f"heads={heads} ({heads_err}) — a second head means `alembic upgrade head` "
    f"is ambiguous and a deployment picks one at random",
)
require(
    "migrations: the columns are actually added, not only declared on the model",
    any(
        "scheduled_publish_at" in read(BACKEND / "alembic/versions" / n)
        for n in rev_ids.values()
    )
    and any(
        "revision_count" in read(BACKEND / "alembic/versions" / n)
        for n in rev_ids.values()
    ),
)
cprev = [n for n in rev_ids.values() if n.startswith("2026_10_03_cprev")]
require(
    "migrations: both of this feature's revisions are on disk",
    len(cprev) == 2,
    f"found {cprev}",
)

# --- 3. the service: the ordering that makes it mean anything ---------------
svc = read(BACKEND / "app/modules/blog/application/custom_post_revision_service.py")
require("service: file is not a stub", len(svc) > 1500, f"{len(svc)} chars")


def call_order(src: str, *names: str) -> list[int]:
    """Positions of the first occurrence of each name, or -1 when absent."""
    return [src.find(n) for n in names]


update_fn = re.search(r"async def update_entry\(.*?\n(?=\nasync def )", svc, re.S)
update_src = update_fn.group(0) if update_fn else ""
snap_at = update_src.find("_snapshot(")
apply_at = update_src.find("setattr(entry, key, value)")
require(
    "service: the snapshot is taken BEFORE the change is applied",
    snap_at != -1 and apply_at != -1 and 0 < snap_at < apply_at,
    f"snapshot@{snap_at} apply@{apply_at} — after the write the newest "
    f"revision IS the current row and restoring it changes nothing",
)
require(
    "service: the first edit moves the counter",
    re.search(r"elif snapshot:", update_src) is not None,
    "without it revision_count can never leave zero, so revisions are never taken",
)
require(
    "service: the counter is bounded so the table cannot grow without limit",
    "DEFAULT_REVISION_LIMIT" in svc,
)

restore_fn = re.search(r"async def restore_revision\(.*?\n(?=\nasync def )", svc, re.S)
restore_src = restore_fn.group(0) if restore_fn else ""
require(
    "service: restore snapshots first, so it is itself undoable",
    "_snapshot(" in restore_src.split("entry.title =")[0],
)
require(
    "service: restoring a revision that does not exist is refused",
    re.search(r"raise NotFoundError", restore_src) is not None,
)

pub_fn = re.search(r"async def publish_scheduled\(.*", svc, re.S)
pub_src = pub_fn.group(0) if pub_fn else ""
require(
    "service: publish_scheduled only takes DRAFT rows",
    "CustomPostTypeStatus.DRAFT" in pub_src,
)
require(
    "service: publish_scheduled clears the schedule as it goes (idempotent)",
    re.search(r"scheduled_publish_at\s*=\s*None", pub_src) is not None,
    "without the clear, a second run republishes and the row cannot be "
    "recovered by moving the date forward",
)
require(
    "service: publish_scheduled leaves a future row alone",
    "<= now" in pub_src,
)

# --- 4. the routes call the service -----------------------------------------
routes = read(BACKEND / "app/modules/blog/api/wp_parity_routes.py")
require("route: list revisions", '"/entries/{entry_id}/revisions"' in routes)
require("route: restore a revision", "/restore" in routes)
for fn in ("list_revisions", "restore_revision"):
    callers = [
        node for node in ast.walk(ast.parse(routes))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == fn
    ]
    require(
        f"route: {fn} is called, not reimplemented inline",
        bool(callers),
        "a route that computes revisions itself is a second implementation "
        "that will drift from the service",
    )

# --- 5. the responses carry the fields (the check this build failed first) --
list_fn = re.search(
    r"async def admin_list_content_entries\(.*?\n(?=\n@admin_router)", routes, re.S
)
list_src = list_fn.group(0) if list_fn else ""
require(
    "route: the list response carries scheduled_publish_at",
    "scheduled_publish_at" in list_src,
    "the tab's schedule column then renders blank for every entry even though "
    "the field is settable — presence without connection",
)
require("route: the list response carries revision_count", "revision_count" in list_src)

tsvc = read(BACKEND / "app/modules/blog/application/taxonomy_service.py")
upd_fn = re.search(r"async def update_entry\(.*?\n(?=\n    @staticmethod)", tsvc, re.S)
upd_src = upd_fn.group(0) if upd_fn else ""
require(
    "service: update_entry snapshots through the revision service",
    "custom_post_revision_service" in upd_src,
)
require(
    "service: update_entry accepts scheduled_publish_at",
    "scheduled_publish_at" in upd_src,
)
require(
    "service: the update response returns what was just saved",
    re.search(r'"scheduled_publish_at":', upd_src) is not None,
    "the row would flash the previous value until a refetch",
)
# A `None` must reach the column, or "unschedule" cannot be expressed.
require(
    "service: an empty schedule clears it (None, not skipped)",
    re.search(r"entry\.scheduled_publish_at\s*=\s*[\s\S]{0,120}?if raw else None", upd_src)
    is not None,
)

# --- 6. the task is registered where the app will find it --------------------
task_src = read(BACKEND / "app/modules/blog/application/tasks.py")
TASK = "app.modules.blog.application.tasks.publish_scheduled_cpt_entries"
require("task: the module exists", TASK in task_src)
require(
    "task: it calls the service, not its own copy of the logic",
    "custom_post_revision_service.publish_scheduled" in task_src,
)
beat = read(BACKEND / "app/worker/celery_app.py")
require(
    "celery: the task name in beat is the one the decorator registers",
    TASK in beat,
    "a mismatch here is the 'unregistered task' failure: the job fires on "
    "schedule and logs a warning nobody reads",
)
require(
    "celery: it is actually on a beat schedule, not just imported",
    re.search(r"publish-scheduled-cpt-entries", beat) is not None,
)

# --- 7. the client and the UI, or it is an API nobody calls -----------------
client = read(FRONTEND / "lib/api/wp-parity.ts")
require("client: entryRevisions is exported",
        re.search(r"entryRevisions", client) is not None)
require("client: restoreEntryRevision is exported",
        re.search(r"restoreEntryRevision", client) is not None)
require("client: both point at the routes",
        "/revisions" in client and "/restore" in client)
require("client: the entry type carries scheduled_publish_at",
        re.search(r"scheduled_publish_at\??:", client) is not None)

tab = read(FRONTEND / "components/admin/blog/content-types-tab.tsx")
require("ui: the tab calls entryRevisions", "contentTypesApi.entryRevisions(" in tab)
require("ui: the tab calls restoreEntryRevision",
        "contentTypesApi.restoreEntryRevision(" in tab)
require("ui: the tab sends the schedule",
        "scheduled_publish_at:" in tab)
require("ui: the tab can clear a schedule (null, not omitted)",
        re.search(r"scheduled_publish_at:[^,}]*\?\s*[^:]*:\s*null", tab) is not None,
        "omitting the key on an emptied field leaves the old time in place "
        "with no way to remove it from the form",
)
require(
    "ui: entering edit mode loads the row's own schedule",
    re.search(r"setEntrySched\(", tab) is not None,
    "starting from \"\" would silently drop a schedule on the next save",
)
require(
    "ui: the schedule is rendered per row, not just settable",
    re.search(r"e\.scheduled_publish_at\s*&&\s*\(", tab) is not None,
    "a form field that writes the value but never reads it back is presence "
    "without connection — the operator cannot tell what is scheduled",
)
require(
    "ui: the rendered date is formatted for the reader",
    "toLocaleString" in tab,
)

# --- 8. a per-entry check the rest of the suite can reuse --------------------
print("\n  (this gate inspects source; the row-level behaviour lives in "
      ".p1-tests/custom_post_revision_test.py)")

if problems:
    print("\nCPT REVISION / SCHEDULING GAPS:")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)
print("\nPASS: model, migrations, service, routes, task, client and UI all "
      "carry it — a snapshot before the write, an undoable restore, and a "
      "schedule that the list actually returns.")
