# Email-template editor: Persian labels + comment-mail fixes (2026-10-06)

## What was reported

The admin email-template editor (`/admin/email-templates`) showed raw English
button labels — `comment_new` and `comment_approved` — beside the four Persian
ones (اسکرین‌شات کاربر).

## Root cause

The backend's `default_email_templates()` ships **six** templates. The two
comment templates (`comment_new`, `comment_approved`) were added later; the
frontend's `TEMPLATE_LABELS` map was never updated, and the tab row falls
through to `?? t.name` — so a missing entry fails nothing and shows English.
This is the same drift class as the order-status label maps
(`order-status-vocabulary-drift` memory note).

## Findings from the investigation (one report, four defects)

While tracing the labels, three more defects in the same feature surfaced —
two of them fixed here, one owned by session 2:

1. **Labels (this fix).** `TEMPLATE_LABELS` covered 4 of 6 templates;
   `VARIABLE_HINTS` was missing 13 variables the built-ins declare
   (`total_toman`, `reset_url`, `post_title`, `commenter_name`, …), so the
   editor's tooltips showed raw tokens.

2. **The editor's save/preview could never work (session 2, fixed 20:00).**
   `sanitize_email_template` refused `<meta>` — and every built-in template
   opens with `<meta charset>` / `<meta name="viewport">`. Saving or
   previewing an *untouched* default failed with a 422. Verified live before
   the fix (`PROBE2: ValidationError`), verified fixed after.

3. **Comment mails bypassed the resolver (this fix).**
   `comment_email_service._send` read `default_email_templates()` directly, so
   an operator's saved override for `comment_new`/`comment_approved` never
   reached a real email — the exact "CRUD real, effect absent" shape the
   resolver exists to close for the order templates. It also read the store
   name from `getattr(get_settings(), "store_name", None)` — a field Settings
   never had — so every comment email was headed "فروشگاه اینترنتی" while the
   order confirmation said the operator's real name ("فروشگاه").

4. **English status in a Persian email (this fix).**
   `{{comment_status}}` carried the raw enum value — "وضعیت این دیدگاه:
   pending". Now mapped to the moderation screen's own wording
   (در انتظار بررسی / تأیید شده / اسپم / زباله‌دان).

## The fix

Backend:

- `backend/app/modules/blog/application/comment_email_service.py` —
  `_send` now calls `resolve_template` (DB first, built-in fallback), the same
  resolver the order paths use; the header store name now flows through it.
  Added `_COMMENT_STATUS_LABELS` and used it for the `comment_status`
  variable.
- `backend/scripts/check_email_template_labels.py` (new gate) — compares
  `TEMPLATE_LABELS` with the backend's template names **in both directions**
  (missing label = English UI; dead label = stale key), and `VARIABLE_HINTS`
  against every declared variable. Reads the canonical set by importing
  `default_email_templates()`, not by grepping source.
- `backend/scripts/negative_test_email_template_labels.py` — proves the gate
  can fail, one property at a time, on a **copy** of the page in a temp
  directory (the gate takes an optional path argument). The real file is
  never written to.
- `backend/scripts/run_gates.py` — registered the new gate.
- `backend/app/tests/unit/test_email_template_resolver.py` — the
  "no caller reads the builtin directly" guard now covers
  `comment_email_service`.
- `backend/app/tests/unit/test_comment_email_status_label.py` (new) — pins the
  Persian status mapping, the rowless-resolver fallback, the store name in
  the rendered header, and that no `{{placeholder}}` survives rendering.

Frontend:

- `frontend/app/admin/email-templates/page.tsx` — `TEMPLATE_LABELS` now
  covers all six templates; `VARIABLE_HINTS` covers all declared variables.
- `frontend/lib/api/notifications.ts` — stale "four transactional emails"
  comment corrected.
- `frontend/scripts/verify-email-template-labels.mjs` (new) — the browser
  half: real Chromium, real admin login, asserts no tab shows a raw name and
  the Persian labels render.

## Verification (all live unless noted)

- `check_email_template_labels.py` → PASS (6 templates, 16 variables).
- `negative_test_email_template_labels.py` → 4/4 sabotages red for their own
  reason; real tree untouched.
- Live browser (`verify-email-template-labels.mjs`): tab row renders
  «انتشار دیدگاه | دیدگاه تازه | تأیید سفارش | ارسال سفارش | بازنشانی رمز
  عبور | پردازش بازگشت وجه»; editor heading «انتشار دیدگاه». PASS.
- Live API probe: save of an untouched built-in body → OK (was 422); preview
  → OK; `resolve_template` returns the override row; override cleaned up
  after the probe (0 rows left).
- Backend: `pytest app/tests/unit` → 226 passed; ruff clean on changed app
  files.
- Frontend: `tsc --noEmit` clean; vitest 24/24.
- Gates: `run_gates.py` → all 6 pass (incl. session 2's
  `check_endpoint_annotations` and `stdlib loggers` gates).

## Previously-open item (now closed by session 2)

The preview pane double-wrapped: it wrapped the full template body (which
already contains the RTL shell) in `_wrap_html` again, so the preview showed
two header bands (DOCTYPE count 2, verified live at 20:39). Session 2 fixed
it in `email_template_service.py`; re-verified 2026-10-07 across all six
templates — DOCTYPE count 1, zero raw `{{variables}}` each.

## Related fix (session 2, same feature)

`run_gates.py` crashed instead of reporting when a failing gate printed
Persian: `subprocess.run(text=True)` decoded child output with the Windows
locale codec (cp1252), a byte like 0x90 raised UnicodeDecodeError in the
reader thread, `proc.stdout` came back `None`, and `sys.stdout.write(None)`
TypeErrored — the runner died at the exact moment it should have named the
failing gate. Fixed with `encoding="utf-8", errors="replace"` (line 118).
Found and reported by session 4; fixed by session 2.
