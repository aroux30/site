# P2 independent verification — 2026-10-03

The P2 session (retired) claimed all 25 items of
`docs/store-relevant-cms-gaps-2026-10-01.md` were closed. Nobody had read the
code. This is an independent, read-only re-verification of every claim, done by
two agents plus direct gate/test runs, with `path:line` evidence for each
verdict.

**Result: 21 verified · 3 partial · 1 missing** (as of 2026-10-03 03:00, after
this session closed items 6, 8 and 10 itself).

## Verified (21)

| # | Item | Evidence |
|---|------|----------|
| 1 | Auto text formatting | `shared/content/text_filters.py` → `render.py` → `blog_service.py`; 26 tests |
| 2 | Meta in Quick Edit + revision restore | `quick-edit-dialog.tsx` → `quick_edit_service.py`; `blog_service.py:676` |
| 3 | Comment author website | `blog-comments.tsx:238,110` → `comment_service.py:144` |
| 4 | Private note (`comment_type note`) | model + migration + moderation tab; 11 tests |
| 5 | Restore original image | `media/page.tsx` + `routes.py` restore-original |
| 6 | **Image undo/redo + save-as-copy** | closed this session — see below |
| 7 | Edit image from content editor | `RichBodyEditor.tsx` → `?asset=` deep link |
| 8 | **Alt-text warning consumes server field** | closed this session — see below |
| 9 | Configurable upload cap | `media_service.py` `resolve_size_limit` + settings card |
| 10 | **Contextual admin-bar edit link** | closed this session — see below |
| 11 | Dismissible admin notices | `admin-notices.tsx` + `notice_service.py` persistence |
| 12 | Date/time format + timezone | `date-settings.ts` → `date.ts`, 13 pages, 12 tests |
| 14 | Content languages UI | `content-settings-card.tsx` + `/public/routing` |
| 17 | Basic auth with app password | `dependencies.py:70-100` |
| 19 | Sanitizer allowlist sync | `check_editor_allowlists.py` PASS (75/76 tags, 42 attrs, 47 CSS) |
| 20 | Scheduled jobs page + Site Health daily | `scheduled-jobs/page.tsx` + beat entry; `check_scheduled_tasks` PASS |
| 21 | Site Health Info tab | 8 sections incl. autoload + scheduled_jobs |
| 22 | i18n string catalogue UI | `admin/i18n/page.tsx` (341 lines) → CRUD routes |
| 23 | Plugin hook dispatch | `check_hooks_dispatched` PASS 14/14 |
| 24 | Editable email templates | `resolve_template` in 3 production callers + UI |
| 25 | Email attachments | `outbox_worker.py:590` → `attachments=` |

## Partial (3) — none in this session's file scope

| # | What is missing |
|---|-----------------|
| 13 | `ping_sites` has zero implementation (default category/format work) |
| 16 | App-password admin routes are all self-scoped; no admin can list/revoke another user's app passwords; no admin UI |
| 18 | Cache is done and configurable, but no **public** proxy for arbitrary URLs — only `/admin/embed` behind `content:write` |

## Missing (1)

| # | Item | Note |
|---|------|------|
| 15 | Importers (Movable Type / Tumblr / Blogger / RSS) | The WXR route p1 added has **zero frontend callers** — `transfer-tab.tsx` accepts only JSON |

## Items closed during this verification session

### 6 — Image undo/redo + save-as-copy

Four live bugs were found and fixed while closing this:

1. **Wrong path base.** All edit routes passed `asset.file_path` (`media/<name>`,
   relative to the uploads root) to `ImageEditor`, which opens it from cwd — the
   file lives at `<UPLOAD_DIR>/media/<name>`. Every crop/resize/rotate/flip/
   optimize raised `FileNotFoundError`. Fixed with `_resolve_edit_source()`.
2. **Wrong parameter.** `_edited_asset` called
   `register_derived_asset(edit_operation=...)`; the service takes `suffix` →
   `TypeError` on every edit. Fixed, and the real operation name is recorded.
3. **Response shape mismatch.** The client read `data.items` off a route that
   returns a bare array → history panel never rendered. Fixed in the client.
4. **`list_edit_history` returned only direct children of the root.** For a
   chain `a → b → c` it returned `[b]` — no root, no current. `is_current`
   matched nothing, so undo/redo had no index. Rewritten to walk the chain.
5. **The EXIF route had the same wrong path base** and it was *silent*:
   `extract_exif` swallows its own exception and returns `{}`, so an operator
   saw "no camera data" for a photo that had plenty. Fixed with the same
   `_resolve_edit_source()` helper.

Then: `duplicate_asset` service + route + UI (save-as-copy, no chain link, own
derivatives), undo/redo buttons walking the chain, clickable history steps.

Gate: `check_media_undo_redo` (19 checks, sabotage-proven). Fixture:
`.p1-tests/media_undo_redo_test.py`.

### 8 — Alt-text field consumption

`needs_alt_text` (server `computed_field`) was never read by the UI, which
recomputed the rule locally — the server's answer was dead code. The client
type now carries the field and the list prefers it, with the local rule only
as a fallback for routes that predate the field.

### 10 — Contextual admin-bar link

`editTargetFor(pathname)` maps `/blog/<slug>`, `/products/<slug>` and
`/<page-slug>` to the owning admin screen; non-object storefront routes are
excluded. Products admin now reads `?search=` and matches slug, so the link
lands on the object rather than the full catalogue. The blog and pages admin
lists read `?search=` on mount too (added by the blog session, quoting this
session's comment), so all three links land on a filtered list.

Gate: `check_admin_bar_contextual`. **The gate's first version had the
"presence instead of connection" flaw** — it grepped for `"editTarget &&"`,
which a `{false && editTarget && (` sabotage still contains. Anchored regex
fixed it; the sabotage now turns it red.

## Method notes

- Every "verified" verdict required the full chain: backend → typed client →
  a UI component that actually calls it. A route with no caller was treated as
  not done.
- Gates were **executed**, not eyeballed: `check_editor_allowlists`,
  `check_hooks_dispatched`, `check_scheduled_tasks` all run live.
- Backend unit tests for the P2 areas were run individually: 181 tests across
  12 files, all passing.
- Known limitation: the whole-suite result on a tree three sessions are editing
  is a snapshot. `scripts/verify_p2_frozen.py` exists for a verdict on a quiet
  tree and refuses to print a clean one while files are moving.

---

## Update — 2026-10-03 (later): the four open rows, resolved

The four rows left open at 03:00 were re-measured after the sessions finished:

| # | then | now | evidence |
|---|------|-----|----------|
| 13 | `ping_sites` absent | **deliberately rejected** | ping_sites is dead (XML-RPC ping services are defunct). Default category + default post format *are* implemented (`blog_service.py:414`, `:441`). Recorded as a conscious "will not build", not an omission. |
| 15 | Importers missing | **built** | `dataexchange/application/feed_parser.py` (RSS 2.0 + Atom, stdlib ElementTree), route (`preview_feed_import`, `import_feed`), client `data-exchange.ts`, UI card in `admin/data-exchange/page.tsx`. Gate `check_feed_import_chain` PASS. |
| 16 | "admin cannot manage another user's app passwords" | **already complete** | `user-sessions-dialog.tsx:66` / `:107`, rendered at `users/page.tsx:801`. The 03:00 measurement predated the file (mtime 02:24 → measured before it landed). Gate `check_admin_app_passwords` PASS (behavioural). |
| 18 | "no public proxy for arbitrary URLs" | **already complete** | `routes.py:1811` `@router.get("/oembed/1.0/embed")` → `_resolve(db, url, …)` for any address, with the SSRF guard and OG fallback. |

**Final P2 count: 24 verified · 1 consciously rejected (13) · 0 open.**

Two rows (16, 18) were *false gaps in my own earlier measurement* — a stale snapshot read as current state. See `a-green-check-does-not-date-the-bug`.
